import argparse
import hashlib
import json
from pathlib import Path

from .capture_contract import CaptureRefused, validate_capture, validate_trace_bytes


class ProducerRefused(ValueError):
    pass


ANTECEDENTS = {
    "attempt-05": {
        "numeric_ir": "runtime_trace/numeric_ir/artifacts/attempt-05/numeric_ir.json",
        "correspondence": "runtime_trace/numeric_ir/v2/artifacts/attempt-05/correspondence.json",
    },
    "closure-fresh-01": {
        "numeric_ir": "runtime_trace/numeric_ir/artifacts/closure-fresh-01/numeric_ir.json",
        "correspondence": "runtime_trace/numeric_ir/v2/artifacts/closure-fresh-01/correspondence.json",
    },
}
TARGET_ORDER = [("q", 0), ("q", 8), ("full_v", 0), ("full_v", 8), ("latent", 0), ("latent", 8)]


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _overlap(a, size_a, b, size_b):
    return a < b + size_b and b < a + size_a


def _endpoint(numeric, correspondence):
    result = []
    for component, offset in TARGET_ORDER:
        candidates = [value for value in numeric["values"]
                      if value.get("storage") == {"space": "buffer", "name": component,
                                                   "byte_offset": offset, "width": 8}
                      and value.get("producer", {}).get("role") == "copy_result"]
        if not candidates:
            raise ProducerRefused(f"missing endpoint memory write {component}[{offset}]")
        value = candidates[-1]
        source_slices = value.get("source_slices", [])
        if len(source_slices) != 1 or source_slices[0].get("width") != 8:
            raise ProducerRefused("endpoint COPY chain")
        source_value_id = source_slices[0]["value_id"]
        direct_binding = next((item for item in correspondence["state_bindings"]
                               if item["value_id"] == value["value_id"] and item["byte_offset"] == 0), None)
        binding = direct_binding
        if binding is None:
            binding = next((item for item in correspondence["state_bindings"]
                            if item["value_id"] == source_value_id and item["byte_offset"] == 0), None)
        if binding is not None:
            form, state_id = binding["form"], binding["state_id"]
        else:
            operation = next((item for item in correspondence["operations"]
                              if item["output_value_id"] == source_value_id), None)
            if operation is None:
                raise ProducerRefused("endpoint Form source absent")
            form, state_id = operation["output_form"], operation["output_state_id"]
        result.append({"component": component, "byte_offset": offset,
                       "endpoint_memory_value_id": value["value_id"],
                       "endpoint_memory_state_id": direct_binding["state_id"] if direct_binding else None,
                       "old_endpoint_state_binding_present": direct_binding is not None,
                       "copy_source_value_id": source_value_id,
                       "form_source_state_id": state_id, "center_bits": value["raw_bits"],
                       "form": form, "transformation_class": "A_PURE_COPY",
                       "no_intervening_write": True})
    return result


def _low64(context, name):
    return "0x" + context["xmm"][name][-16:]


def produce(evidence, label, output, root=None):
    evidence, output = Path(evidence), Path(output)
    summary_path = output.with_name("summary.json")
    if output.exists() or summary_path.exists():
        raise FileExistsError(output if output.exists() else summary_path)
    root = Path(root or Path(__file__).resolve().parents[2]).resolve()
    if label not in ANTECEDENTS:
        raise ProducerRefused("unsupported antecedent label")
    try:
        capture = json.loads((evidence / "capture.json").read_text(encoding="utf-8"))
        validate_capture(capture, root)
        trace_raw = (evidence / "caller_trace.jsonl").read_bytes()
        rows = validate_trace_bytes(capture, trace_raw)
    except (OSError, json.JSONDecodeError, CaptureRefused, KeyError, TypeError) as exc:
        raise ProducerRefused(str(exc)) from exc
    if capture.get("unknown_effects_refused") is not True:
        raise ProducerRefused("unknown effects were not refused")
    paths = ANTECEDENTS[label]
    numeric_raw = (root / paths["numeric_ir"]).read_bytes()
    correspondence_raw = (root / paths["correspondence"]).read_bytes()
    numeric, correspondence = json.loads(numeric_raw), json.loads(correspondence_raw)
    carry = _endpoint(numeric, correspondence)
    pointers = capture["first_step_entry"]["abi"]["pointers"]
    first_bits = capture["first_step_return"]["post_component_bits"]
    second = capture["second_step_entry"]["abi"]
    for binding in carry:
        component, index = binding["component"], binding["byte_offset"] // 8
        if first_bits[component][index] != binding["center_bits"]:
            raise ProducerRefused("fresh first-step endpoint differs from audited antecedent")
        if second["component_bits"][component][index] != binding["center_bits"]:
            raise ProducerRefused("second entry center differs from endpoint")
    for row in rows:
        for write in row["possible_memory_writes"]:
            for component in ["q", "full_v", "latent"]:
                if _overlap(write["address"], write["size"], pointers[component], 16):
                    raise ProducerRefused(f"intervening write overlaps carried {component}")
    gradient_address = pointers["gradient"]
    zero_bytes = set()
    gradient_writes = []
    for row in rows:
        for write in row["possible_memory_writes"]:
            if _overlap(write["address"], write["size"], gradient_address, 16):
                lo, hi = max(write["address"], gradient_address), min(write["address"] + write["size"], gradient_address + 16)
                zero_bytes.update(range(lo, hi))
                gradient_writes.append({"sequence": row["sequence"], **write})
    if zero_bytes != set(range(gradient_address, gradient_address + 16)):
        raise ProducerRefused("gradient zero coverage incomplete")
    if second["component_bits"]["gradient"] != ["0x0000000000000000"] * 2:
        raise ProducerRefused("gradient is not exact zero at second entry")
    t_bits, dt_bits = second["t_bits"], second["dt_bits"]
    time_sources = [row["sequence"] for row in rows
                    if _low64(row["post"], "xmm0") == t_bits and _low64(row["pre"], "xmm0") != t_bits]
    dt_changes = [row["sequence"] for row in rows
                  if _low64(row["post"], "xmm1") != _low64(row["pre"], "xmm1")]
    sources = capture["second_step_entry"].get("argument_sources", {})
    if sources.get("t", {}).get("source_bits") != t_bits or sources.get("dt", {}).get("source_bits") != dt_bits:
        raise ProducerRefused("second-entry argument source receipt")
    if sources["t"]["instruction_sequence"] not in time_sources:
        raise ProducerRefused("time source sequence")
    if sources["dt"]["instruction_sequence"] not in dt_changes:
        raise ProducerRefused("dt source sequence")
    save_all = []
    endpoint_centers = {item["center_bits"] for item in carry[:4]}
    for row in rows:
        for write in row["possible_memory_writes"]:
            if write["kind"] == "EXPLICIT" and write["size"] == 8 and write["after_bits"] in endpoint_centers:
                if all(not _overlap(write["address"], 8, address, 16) for address in pointers.values()):
                    save_all.append({"sequence": row["sequence"], **write})
    transition = {"schema": "gala-caller-transition-v1", "verdict": "PRODUCED",
        "producer": {"source_sha256": _sha(Path(__file__).read_bytes()),
            "capture_contract_sha256": _sha((Path(__file__).parent / "capture_contract.py").read_bytes()),
            "imports_or_executes_second_v2_block": False},
        "antecedent": {"label": label, "numeric_ir_path": paths["numeric_ir"],
            "numeric_ir_sha256": _sha(numeric_raw), "correspondence_path": paths["correspondence"],
            "correspondence_sha256": _sha(correspondence_raw),
            "relation": "fresh execution endpoint linked to distinct externally audited antecedent"},
        "capture": {"capture_sha256": _sha((evidence / "capture.json").read_bytes()),
            "trace_sha256": _sha(trace_raw), "record_count": len(rows),
            "inferior_pid": capture["inferior_pid"], "controlled_stop_receipt": capture["controlled_stop_receipt"]},
        "bindings": {"carry": carry,
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
        "scope": "prospective second-step input at native entry; second body excluded"}
    encoded = (json.dumps(transition, sort_keys=True, separators=(",", ":")) + "\n").encode()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.open("xb").write(encoded)
    summary = {"schema": "gala-caller-transition-summary-v1", "verdict": "PRODUCED",
               "antecedent_label": label, "transition_sha256": _sha(encoded),
               "caller_record_count": len(rows), "carry_binding_count": 6,
               "protected_carry_write_overlap_count": 0, "gradient_zero_coverage_bytes": len(zero_bytes),
               "second_step_body_instructions_executed": 0,
               "status": "IMPLEMENTED / INDEPENDENT CHECKER PENDING"}
    summary_path.open("xb").write((json.dumps(summary, sort_keys=True, separators=(",", ":")) + "\n").encode())
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
    except (ProducerRefused, FileExistsError) as exc:
        print(json.dumps({"verdict": "REFUSED", "reason": str(exc)}), file=__import__("sys").stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
