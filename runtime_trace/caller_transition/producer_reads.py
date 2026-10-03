"""Fail-closed v2 producer for sealed caller read-proof acquisitions."""
import argparse
import hashlib
import json
from pathlib import Path
import re

from .producer import ANTECEDENTS, TARGET_ORDER, _endpoint, _low64, _overlap
from .read_effects import ReadsRefused, required_reads
from .run_acquisition_reads import EXPECTED_MODULES, SOURCE_PATHS, canonical


class ProducerReadsRefused(ValueError):
    pass


SEALED_NAMES = sorted([
    "caller_trace.jsonl", "capture.json", "execution.json", "first_step_disassembly.txt",
    "gdb.log", "harness_diff.json", "module_pinset.json", "source_pinset.json",
])
ANTECEDENT_HASHES = {
    "attempt-05": {
        "numeric_ir": "bbb912c041cb47cf2f3814d416a298c3c6469c35a47c9b7cda629c11415586ba",
        "correspondence": "3edd42937e58c7655dc951d3683802ffddd5ae7cbfda27c5793d6cb42c7d35f3",
    },
    "closure-fresh-01": {
        "numeric_ir": "c34576f87bd4abc5bdc5fc2f67e68251ec30d5659776ade984fd15ab2bcb5296",
        "correspondence": "a692db2f6f3b5b9a45de71cf8516fef4c8d2cdc8b173c6cdb20259c5812c572f",
    },
}


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ProducerReadsRefused(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _load(path, canonical_required=False):
    raw = Path(path).read_bytes()
    try:
        value = json.loads(raw, object_pairs_hook=_pairs)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ProducerReadsRefused(f"invalid JSON: {path}") from exc
    if canonical_required and raw != canonical(value):
        raise ProducerReadsRefused(f"noncanonical JSON: {path}")
    return value, raw


def _numeric(context):
    values = {name: int(value, 16) for name, value in context["gpr"].items()}
    values["eflags"] = context["eflags"]
    return values


def _validate_bundle(evidence, root, label):
    seal, seal_raw = _load(evidence / "acquisition_seal.json", True)
    if seal.get("schema") != "caller-transition-acquisition-seal-v1":
        raise ProducerReadsRefused("acquisition seal schema")
    if seal.get("antecedent_label") != label:
        raise ProducerReadsRefused("seal antecedent label")
    if seal.get("exact_file_name_set") != SEALED_NAMES or seal.get("file_count") != len(SEALED_NAMES):
        raise ProducerReadsRefused("sealed file-name set")
    if set(seal.get("sealed_files", {})) != set(SEALED_NAMES):
        raise ProducerReadsRefused("sealed file hash set")
    actual_names = sorted(path.name for path in evidence.iterdir())
    if actual_names != sorted(SEALED_NAMES + ["acquisition_seal.json"]):
        raise ProducerReadsRefused("acquisition directory exact file set")
    for name in SEALED_NAMES:
        if _sha((evidence / name).read_bytes()) != seal["sealed_files"][name]:
            raise ProducerReadsRefused(f"sealed file hash: {name}")

    execution, execution_raw = _load(evidence / "execution.json", True)
    capture, capture_raw = _load(evidence / "capture.json", True)
    source_pinset, source_pinset_raw = _load(evidence / "source_pinset.json", True)
    module_pinset, module_pinset_raw = _load(evidence / "module_pinset.json", True)
    if execution.get("schema") != "caller-transition-execution-v2":
        raise ProducerReadsRefused("execution schema")
    if capture.get("schema") != "gala-caller-transition-capture-v2":
        raise ProducerReadsRefused("capture schema")
    if capture.get("verdict") != "CONTROLLED_STOP":
        raise ProducerReadsRefused("capture verdict")
    if execution.get("antecedent_label") != label or capture.get("antecedent_label") != label:
        raise ProducerReadsRefused("acquisition antecedent label")
    if capture.get("execution_sha256") != _sha(execution_raw):
        raise ProducerReadsRefused("capture execution hash")
    if source_pinset.get("schema") != "caller-transition-source-pinset-v1":
        raise ProducerReadsRefused("source pinset schema")
    if source_pinset.get("exact_key_set") != sorted(SOURCE_PATHS):
        raise ProducerReadsRefused("source pinset exact key set")
    if set(source_pinset.get("files", {})) != set(SOURCE_PATHS):
        raise ProducerReadsRefused("source pinset files")
    for relative, digest in source_pinset["files"].items():
        if _sha((root / relative).read_bytes()) != digest:
            raise ProducerReadsRefused(f"source pin mismatch: {relative}")
    source_id = _sha(source_pinset_raw)
    if execution.get("source_pinset_sha256") != source_id or capture.get("source_pinset_sha256") != source_id:
        raise ProducerReadsRefused("source pinset authentication")
    if execution.get("source_sha256_before_execution") != source_pinset["files"]:
        raise ProducerReadsRefused("execution source receipt")
    if execution.get("source_receipt_key_set") != sorted(SOURCE_PATHS):
        raise ProducerReadsRefused("execution source key receipt")

    if module_pinset.get("schema") != "caller-transition-module-pinset-v1":
        raise ProducerReadsRefused("module pinset schema")
    if set(module_pinset.get("modules", {})) != EXPECTED_MODULES:
        raise ProducerReadsRefused("module pinset exact hashes")
    module_id = _sha(module_pinset_raw)
    if execution.get("module_pinset_sha256") != module_id or capture.get("module_pinset_sha256") != module_id:
        raise ProducerReadsRefused("module pinset authentication")
    if set(capture.get("module_sha256_set", [])) != EXPECTED_MODULES:
        raise ProducerReadsRefused("capture module hash set")
    if {item["sha256"] for item in capture.get("modules", {}).values()} != EXPECTED_MODULES:
        raise ProducerReadsRefused("loaded module hash set")

    trace_raw = (evidence / "caller_trace.jsonl").read_bytes()
    if capture.get("trace_sha256") != _sha(trace_raw):
        raise ProducerReadsRefused("capture trace hash")
    rows = []
    chain = "0" * 64
    observation_count = failure_count = write_count = same_value_count = 0
    indirect_count = return_count = pop_count = leave_count = 0
    for expected_sequence, line in enumerate(trace_raw.splitlines()):
        try:
            row = json.loads(line, object_pairs_hook=_pairs)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ProducerReadsRefused("trace JSON") from exc
        if row.get("schema") != "gala-caller-transition-instruction-v2" or row.get("sequence") != expected_sequence:
            raise ProducerReadsRefused("trace schema or dense sequence")
        if row.get("previous_chain") != chain:
            raise ProducerReadsRefused("trace previous chain")
        payload = {key: value for key, value in row.items() if key != "record_chain"}
        chain = _sha(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode())
        if row.get("record_chain") != chain:
            raise ProducerReadsRefused("trace record chain")
        for side in ("pre", "post"):
            bases = row.get(side, {}).get("segment_bases", {})
            if set(bases) != {"fs_base", "gs_base"} or any(
                not re.fullmatch(r"0x[0-9a-f]{16}", value) for value in bases.values()
            ):
                raise ProducerReadsRefused("segment base receipt")
        registers = _numeric(row["pre"])
        segments = {name: int(value, 16) for name, value in row["pre"]["segment_bases"].items()}
        try:
            required = required_reads(row["assembly"], registers, segments, row["pc"],
                                      len(bytes.fromhex(row["instruction_bytes"])))
        except ReadsRefused as exc:
            raise ProducerReadsRefused(str(exc)) from exc
        observed = row.get("pre_memory_observations", [])
        for item in observed:
            observation_count += 1
            if item.get("status") != "OK" or item.get("timing") != "PRE_INSTRUCTION":
                failure_count += 1
            raw_hex = item.get("bytes_hex")
            if not isinstance(raw_hex, str) or not re.fullmatch(r"[0-9a-f]*", raw_hex):
                raise ProducerReadsRefused("memory observation raw hex")
            if len(raw_hex) != item.get("size", -1) * 2:
                raise ProducerReadsRefused("memory observation width")
        for descriptor in required:
            matches = [item for item in observed if all(item.get(key) == descriptor[key]
                       for key in ("address", "size", "kind", "operand"))]
            if len(matches) != 1:
                raise ProducerReadsRefused("missing or duplicate required memory observation")
        writes = row.get("possible_memory_writes", [])
        write_count += len(writes)
        same_value_count += sum(not item.get("value_changed") for item in writes)
        for item in observed:
            if item.get("kind") == "READ_MODIFY_WRITE":
                matches = [write for write in writes if write["address"] == item["address"]
                           and write["size"] == item["size"]]
                if len(matches) != 1:
                    raise ProducerReadsRefused("read/modify/write write receipt")
                before_raw = int(matches[0]["before_bits"], 16).to_bytes(item["size"], "little").hex()
                if before_raw != item["bytes_hex"]:
                    raise ProducerReadsRefused("read/modify/write preimage")
        indirect_count += sum(item["kind"] == "INDIRECT_CONTROL" for item in observed)
        opcode = re.sub(r"^(?:lock\s+)", "", row["assembly"].strip()).split()[0]
        return_count += opcode in {"ret", "retq"}
        pop_count += opcode in {"pop", "popq"}
        leave_count += opcode == "leave"
        rows.append(row)
    if len(rows) != capture.get("record_count") or chain != capture.get("final_chain"):
        raise ProducerReadsRefused("trace count or final chain")
    counts = {"rows": len(rows), "pre_memory_observations": observation_count,
              "pre_memory_observation_failures": failure_count,
              "possible_memory_writes": write_count, "same_value_writes": same_value_count,
              "indirect_memory_controls": indirect_count, "returns": return_count,
              "pops": pop_count, "leaves": leave_count}
    if capture.get("counts") != counts or failure_count != 0:
        raise ProducerReadsRefused("capture read/write/control counts")
    if capture.get("required_memory_observations_complete") is not True:
        raise ProducerReadsRefused("required memory observation completeness")
    if capture.get("controlled_stop_receipt", {}).get("second_step_body_instructions_executed") != 0:
        raise ProducerReadsRefused("second body executed")
    return {"seal": seal, "seal_raw": seal_raw, "execution": execution,
            "execution_raw": execution_raw, "capture": capture, "capture_raw": capture_raw,
            "trace_raw": trace_raw, "rows": rows, "counts": counts,
            "source_id": source_id, "module_id": module_id, "final_chain": chain}


def _observation(row, address, size):
    matches = [item for item in row["pre_memory_observations"]
               if item["address"] == address and item["size"] == size and item["status"] == "OK"]
    if len(matches) != 1:
        raise ProducerReadsRefused("final ABI source observation")
    return matches[0]


def produce(evidence, label, output, root=None):
    evidence, output = Path(evidence).resolve(), Path(output)
    summary_path = output.with_name("summary.json")
    if output.exists() or summary_path.exists():
        raise FileExistsError(output if output.exists() else summary_path)
    root = Path(root or Path(__file__).resolve().parents[2]).resolve()
    if root not in evidence.parents:
        raise ProducerReadsRefused("evidence outside repository")
    if label not in ANTECEDENTS:
        raise ProducerReadsRefused("unsupported antecedent label")
    bundle = _validate_bundle(evidence, root, label)
    capture, rows = bundle["capture"], bundle["rows"]

    paths = ANTECEDENTS[label]
    numeric_raw = (root / paths["numeric_ir"]).read_bytes()
    correspondence_raw = (root / paths["correspondence"]).read_bytes()
    if _sha(numeric_raw) != ANTECEDENT_HASHES[label]["numeric_ir"]:
        raise ProducerReadsRefused("numeric antecedent immutable pin")
    if _sha(correspondence_raw) != ANTECEDENT_HASHES[label]["correspondence"]:
        raise ProducerReadsRefused("correspondence antecedent immutable pin")
    numeric, correspondence = json.loads(numeric_raw), json.loads(correspondence_raw)
    carry = _endpoint(numeric, correspondence)
    pointers = capture["first_step_entry"]["abi"]["pointers"]
    second = capture["second_step_entry"]["abi"]
    second_pointers = second["pointers"]
    pointer_identity = {}
    for component in ["q", "full_v", "latent", "gradient"]:
        if second_pointers[component] != pointers[component]:
            raise ProducerReadsRefused(f"second-entry {component} pointer identity")
        pointer_identity[component] = {"first_step_address": pointers[component],
                                       "second_step_address": second_pointers[component],
                                       "same_memory_region": True}
    first_bits = capture["first_step_return"]["post_component_bits"]
    for binding in carry:
        component, index = binding["component"], binding["byte_offset"] // 8
        if first_bits[component][index] != binding["center_bits"]:
            raise ProducerReadsRefused("first-step endpoint differs from audited antecedent")
        if second["component_bits"][component][index] != binding["center_bits"]:
            raise ProducerReadsRefused("second entry center differs from endpoint")
    for row in rows:
        for write in row["possible_memory_writes"]:
            for component in ["q", "full_v", "latent"]:
                if _overlap(write["address"], write["size"], pointers[component], 16):
                    raise ProducerReadsRefused(f"intervening write overlaps carried {component}")

    gradient_address = pointers["gradient"]
    zero_bytes, gradient_writes = set(), []
    for row in rows:
        for write in row["possible_memory_writes"]:
            if _overlap(write["address"], write["size"], gradient_address, 16):
                lo = max(write["address"], gradient_address)
                hi = min(write["address"] + write["size"], gradient_address + 16)
                zero_bytes.update(range(lo, hi))
                gradient_writes.append({"sequence": row["sequence"], **write})
    if zero_bytes != set(range(gradient_address, gradient_address + 16)):
        raise ProducerReadsRefused("gradient zero coverage incomplete")
    if second["component_bits"]["gradient"] != ["0x0000000000000000"] * 2:
        raise ProducerReadsRefused("gradient is not exact zero")

    final_sources = []
    for sequence, size in [(718, 8), (721, 8), (722, 8), (723, 8), (724, 4), (725, 8), (726, 8)]:
        row = rows[sequence]
        required = [item for item in row["pre_memory_observations"] if item["kind"] == "EXPLICIT"]
        if len(required) != 1 or required[0]["size"] != size:
            raise ProducerReadsRefused(f"final ABI raw source coverage: {sequence}")
        final_sources.append({"sequence": sequence, **required[0]})
    call_stack = [item for item in rows[727]["pre_memory_observations"]
                  if item["kind"] == "ABI_STACK_ARGUMENT"]
    if len(call_stack) != 1 or call_stack[0]["address"] != int(rows[727]["pre"]["gpr"]["rsp"], 16):
        raise ProducerReadsRefused("final ABI gradient stack source")
    final_sources.append({"sequence": 727, **call_stack[0]})
    entry_gradient = second.get("stack_argument_observations", {}).get("gradient", {})
    if entry_gradient.get("bytes_hex") != call_stack[0]["bytes_hex"]:
        raise ProducerReadsRefused("entry gradient stack observation")

    t_bits, dt_bits = second["t_bits"], second["dt_bits"]
    time_sources = [row["sequence"] for row in rows
                    if _low64(row["post"], "xmm0") == t_bits and _low64(row["pre"], "xmm0") != t_bits]
    dt_changes = [row["sequence"] for row in rows
                  if _low64(row["post"], "xmm1") != _low64(row["pre"], "xmm1")]
    sources = capture["second_step_entry"].get("argument_sources", {})
    if sources.get("t", {}).get("source_bits") != t_bits or sources.get("dt", {}).get("source_bits") != dt_bits:
        raise ProducerReadsRefused("second-entry argument source receipt")
    if sources["t"]["instruction_sequence"] not in time_sources or sources["dt"]["instruction_sequence"] not in dt_changes:
        raise ProducerReadsRefused("second-entry argument source sequence")

    save_all = []
    endpoint_centers = {item["center_bits"] for item in carry[:4]}
    for row in rows:
        for write in row["possible_memory_writes"]:
            if write["kind"] == "EXPLICIT" and write["size"] == 8 and write["after_bits"] in endpoint_centers:
                if all(not _overlap(write["address"], 8, address, 16) for address in pointers.values()):
                    save_all.append({"sequence": row["sequence"], **write})

    evidence_relative = str(evidence.relative_to(root)).replace("\\", "/")
    authentication = {
        "acquisition_directory": evidence_relative,
        "seal_path": f"{evidence_relative}/acquisition_seal.json",
        "seal_sha256": _sha(bundle["seal_raw"]),
        "sealed_file_name_set": bundle["seal"]["exact_file_name_set"],
        "execution_path": f"{evidence_relative}/execution.json",
        "execution_sha256": _sha(bundle["execution_raw"]),
        "capture_path": f"{evidence_relative}/capture.json",
        "capture_sha256": _sha(bundle["capture_raw"]),
        "trace_path": f"{evidence_relative}/caller_trace.jsonl",
        "trace_sha256": _sha(bundle["trace_raw"]), "final_chain": bundle["final_chain"],
        "source_pinset_path": f"{evidence_relative}/source_pinset.json",
        "source_pinset_sha256": bundle["source_id"],
        "module_pinset_path": f"{evidence_relative}/module_pinset.json",
        "module_pinset_sha256": bundle["module_id"],
        "antecedent_pinset": ANTECEDENT_HASHES[label],
    }
    transition = {
        "schema": "gala-caller-transition-v2", "verdict": "PRODUCED",
        "producer": {"source_sha256": _sha(Path(__file__).read_bytes()),
                     "read_classifier_sha256": _sha((Path(__file__).parent / "read_effects.py").read_bytes()),
                     "imports_or_executes_second_v2_block": False},
        "antecedent": {"label": label, "capture_label": capture["antecedent_label"],
            "requested_label_matches_capture": True, "numeric_ir_path": paths["numeric_ir"],
            "numeric_ir_sha256": _sha(numeric_raw), "correspondence_path": paths["correspondence"],
            "correspondence_sha256": _sha(correspondence_raw),
            "relation": "fresh read-proof execution linked to distinct externally audited antecedent"},
        "authentication": authentication,
        "capture": {"record_count": len(rows), "inferior_pid": capture["inferior_pid"],
                    "process_identity": capture["process_identity"],
                    "controlled_stop_receipt": capture["controlled_stop_receipt"]},
        "readproof": {"memory_observation_policy_id": capture["memory_observation_policy_id"],
            "segment_base_policy_id": capture["segment_base_policy_id"], **bundle["counts"],
            "required_memory_observations_complete": True, "segment_bases_complete": True,
            "final_abi_source_observations": final_sources,
            "second_entry_gradient_stack_observation": entry_gradient},
        "bindings": {"pointer_identity": pointer_identity, "carry": carry,
            "gradient": {"root_kind": "FRESH_EXACT_ZERO", "center_bits": ["0x0000000000000000"] * 2,
                "form": {"coef": ["0x0.0p+0"] * 4, "box": "0x0.0p+0"},
                "write_sequences": sorted({item["sequence"] for item in gradient_writes}),
                "full_byte_coverage": True},
            "time": {"root_kind": "FRESH_SCHEDULE_LOAD", "center_bits": t_bits,
                "schedule_index": 2, "source_instruction_sequences": time_sources,
                "actual_source_receipt": sources["t"],
                "form": {"coef": ["0x0.0p+0"] * 4, "box": "0x0.0p+0"}},
            "dt": {"root_kind": "FRESH_ENTRY_ROOT", "center_bits": dt_bits,
                "provenance_kind": "ACTUAL_CALL_ARGUMENT", "caller_change_sequences": dt_changes,
                "actual_source_receipt": sources["dt"],
                "form": {"coef": ["0x0.0p+0"] * 4, "box": "0x0.0p+0"}},
            "entry_registers": {"xmm0": {"root_kind": "FRESH_ENTRY_ROOT", "inherits_prior_form": False},
                                "xmm1": {"root_kind": "FRESH_ENTRY_ROOT", "inherits_prior_form": False}}},
        "write_set": {"all_possible_writes_recorded": True, "same_value_stores_included": True,
            "carried_region_overlaps": [], "gradient_writes": gradient_writes,
            "save_all_copy_candidates": save_all},
        "shared_form_basis": {"k": 4, "meaning": "computed-minus-true",
            "namespace": f"externally-audited:{label}:{_sha(correspondence_raw)}",
            "preserved_across_all_six_carries": True, "reseeded": False,
            "conditional_on_externally_audited_endpoint_semantics": True},
        "native_execution_has_form_objects": False, "second_step_body_executed": False,
        "second_v2_block_imported_or_executed": False,
        "scope": "prospective second-step input at native entry; second body excluded",
    }
    encoded = canonical(transition)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.open("xb").write(encoded)
    summary = {"schema": "gala-caller-transition-summary-v2", "verdict": "PRODUCED",
               "antecedent_label": label, "transition_sha256": _sha(encoded),
               "acquisition_seal_sha256": authentication["seal_sha256"],
               "caller_record_count": len(rows), "pre_memory_observation_count": bundle["counts"]["pre_memory_observations"],
               "pre_memory_observation_failure_count": 0, "carry_binding_count": len(TARGET_ORDER),
               "second_step_body_instructions_executed": 0,
               "status": "IMPLEMENTED / INDEPENDENT CHECKER PENDING"}
    summary_path.open("xb").write(canonical(summary))
    return transition


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", required=True)
    parser.add_argument("--antecedent", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--root")
    args = parser.parse_args(argv)
    try:
        produce(args.evidence, args.antecedent, args.out, root=args.root)
    except (ProducerReadsRefused, FileExistsError, OSError, KeyError, TypeError, ValueError) as exc:
        print(json.dumps({"verdict": "REFUSED", "reason": str(exc)}), file=__import__("sys").stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
