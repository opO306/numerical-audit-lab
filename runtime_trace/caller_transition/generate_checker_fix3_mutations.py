"""Generate complete saved-input mutation evidence for Task 2 fix round 3.

The production checker accepts only its literal acquisition pins.  This module
keeps that path closed: semantic mutation cases call the private checker entry
with a test-only pin object, while the public trust-path case calls the public
entry point and proves that coherent local repinning is unavailable there.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import shutil
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable

from runtime_trace.caller_transition.checker import (
    CheckerRefused,
    _PRODUCTION_CASE_PINS,
    _check_bundle_with_pins,
    _require_origin_role,
    check_transition,
    derive_possible_write_effects,
)


ROOT = Path(__file__).resolve().parents[2]
CASE = "audited-attempt-05-readproof-01"
RAW = ROOT / "runtime_trace" / "caller_transition" / "artifacts" / CASE
TRANSITION = (
    ROOT
    / "runtime_trace"
    / "caller_transition"
    / "artifacts"
    / "producer-fix-round2"
    / CASE
    / "transition.json"
)
CHECKER = ROOT / "runtime_trace" / "caller_transition" / "checker.py"
NORMAL_REPORTS = (
    ROOT
    / "runtime_trace"
    / "caller_transition"
    / "artifacts"
    / "checker"
    / "fix-round2"
)
UPPER = 0x1122334455667788


@dataclass(frozen=True)
class MutationSpec:
    name: str
    expected_code: str
    declared_refusal_stage: str
    mutate: Callable[[dict[str, Any]], None]
    input_kind: str = "RAW_BUNDLE_AND_TRANSITION"
    trust_mode: str = "TEST_ONLY_REPIN"
    receipt_preflight: str = "PASSED"


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_canonical(value))


def _input_hashes(case_dir: Path) -> dict[str, str]:
    return {
        path.relative_to(case_dir).as_posix(): _sha(path)
        for path in sorted((case_dir / "input").rglob("*"))
        if path.is_file()
    }


def _source_raw_hashes() -> dict[str, str]:
    return {path.name: _sha(path) for path in sorted(RAW.iterdir()) if path.is_file()}


def _load_bundle(raw: Path, transition: Path) -> dict[str, Any]:
    return {
        "rows": [json.loads(line) for line in (raw / "caller_trace.jsonl").read_text().splitlines()],
        "capture": json.loads((raw / "capture.json").read_text()),
        "execution": json.loads((raw / "execution.json").read_text()),
        "seal": json.loads((raw / "acquisition_seal.json").read_text()),
        "transition": json.loads(transition.read_text()),
    }


def _remap_receipts(bundle: dict[str, Any], mapping: dict[int, int]) -> None:
    """Remap every sequence-bearing field in the accepted capture schemas."""
    def visit(value: object) -> None:
        if isinstance(value, dict):
            for key, item in list(value.items()):
                if key == "sequence" or key.endswith("_sequence"):
                    if isinstance(item, int):
                        if item not in mapping:
                            raise ValueError(f"removed sequence still declared: {key}={item}")
                        value[key] = mapping[item]
                elif key.endswith("_sequences"):
                    if not isinstance(item, list) or not all(
                        isinstance(number, int) and number in mapping for number in item
                    ):
                        raise ValueError(f"unmappable sequence list: {key}={item!r}")
                    value[key] = [mapping[number] for number in item]
                else:
                    visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)

    visit(bundle["capture"])
    visit(bundle["transition"])


def _sparse_remap(bundle: dict[str, Any], mapping: dict[int, int]) -> None:
    """Construct the deliberately stale receipt variants retained from fix2."""
    def visit(value: object) -> None:
        if isinstance(value, dict):
            for key, item in list(value.items()):
                if key == "sequence" or key.endswith("_sequence"):
                    if isinstance(item, int) and item in mapping:
                        value[key] = mapping[item]
                elif key.endswith("_sequences") and isinstance(item, list):
                    value[key] = [mapping[number] for number in item if number in mapping]
                else:
                    visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)

    visit(bundle["capture"])
    visit(bundle["transition"])


def _repair_counts(bundle: dict[str, Any]) -> None:
    rows = bundle["rows"]
    counts = {
        "rows": len(rows),
        "pre_memory_observations": sum(len(row["pre_memory_observations"]) for row in rows),
        "pre_memory_observation_failures": sum(
            observation["status"] != "OK"
            for row in rows
            for observation in row["pre_memory_observations"]
        ),
        "possible_memory_writes": sum(len(row["possible_memory_writes"]) for row in rows),
        "same_value_writes": sum(
            write["value_changed"] is False
            for row in rows
            for write in row["possible_memory_writes"]
        ),
        "indirect_memory_controls": sum(
            row["assembly"].lstrip().startswith(("jmp    *", "call   *")) for row in rows
        ),
        "returns": sum(row["assembly"].strip().split()[0] == "ret" for row in rows),
        "pops": sum(row["assembly"].strip().split()[0] == "pop" for row in rows),
        "leaves": sum(row["assembly"].strip().split()[0] == "leave" for row in rows),
    }
    bundle["capture"]["counts"] = copy.deepcopy(counts)
    for key, value in counts.items():
        bundle["transition"]["readproof"][key] = value


def _materialize_raw(
    case_dir: Path,
    mutate: Callable[[dict[str, Any]], None],
    *,
    repair_counts: bool = True,
) -> tuple[Path, Path, object, dict[str, str]]:
    raw = case_dir / "input" / "raw"
    transition_path = case_dir / "input" / "transition.json"
    shutil.copytree(RAW, raw)
    shutil.copy2(TRANSITION, transition_path)
    bundle = _load_bundle(raw, transition_path)
    mutate(bundle)
    if repair_counts:
        _repair_counts(bundle)

    previous = bundle["rows"][0]["previous_chain"]
    for row in bundle["rows"]:
        row["previous_chain"] = previous
        unsigned = {key: value for key, value in row.items() if key != "record_chain"}
        row["record_chain"] = hashlib.sha256(_canonical(unsigned)).hexdigest()
        previous = row["record_chain"]
    trace_bytes = b"".join(_canonical(row) + b"\n" for row in bundle["rows"])
    (raw / "caller_trace.jsonl").write_bytes(trace_bytes)

    capture = bundle["capture"]
    capture["record_count"] = len(bundle["rows"])
    capture["trace_sha256"] = hashlib.sha256(trace_bytes).hexdigest()
    capture["final_chain"] = previous
    _write(raw / "capture.json", capture)
    _write(raw / "execution.json", bundle["execution"])
    for name in bundle["seal"]["exact_file_name_set"]:
        bundle["seal"]["sealed_files"][name] = _sha(raw / name)
    _write(raw / "acquisition_seal.json", bundle["seal"])

    transition = bundle["transition"]
    transition["capture"]["record_count"] = len(bundle["rows"])
    transition["authentication"]["trace_sha256"] = capture["trace_sha256"]
    transition["authentication"]["final_chain"] = previous
    transition["authentication"]["capture_sha256"] = _sha(raw / "capture.json")
    transition["authentication"]["execution_sha256"] = _sha(raw / "execution.json")
    transition["authentication"]["seal_sha256"] = _sha(raw / "acquisition_seal.json")
    _write(transition_path, transition)

    base = _PRODUCTION_CASE_PINS[CASE]
    pins = replace(
        base,
        transition_sha256=_sha(transition_path),
        seal_sha256=_sha(raw / "acquisition_seal.json"),
        capture_sha256=_sha(raw / "capture.json"),
        execution_sha256=_sha(raw / "execution.json"),
        trace_sha256=capture["trace_sha256"],
        trace_final_chain=previous,
        sealed_files=copy.deepcopy(bundle["seal"]["sealed_files"]),
    )
    return raw, transition_path, pins, _input_hashes(case_dir)


def _materialize_transition(
    case_dir: Path, mutate: Callable[[dict[str, Any]], None]
) -> tuple[Path, Path, object, dict[str, str]]:
    transition_path = case_dir / "input" / "transition.json"
    transition = json.loads(TRANSITION.read_text())
    mutate(transition)
    _write(transition_path, transition)
    pins = replace(_PRODUCTION_CASE_PINS[CASE], transition_sha256=_sha(transition_path))
    return RAW, transition_path, pins, _input_hashes(case_dir)


def _propagate(rows: list[dict[str, Any]], sequence: int, register: str, value: str) -> None:
    rows[sequence]["post"]["gpr"][register] = value
    for row in rows[sequence + 1 :]:
        row["pre"]["gpr"][register] = value
        row["post"]["gpr"][register] = value


def _delete(bundle: dict[str, Any], repaired: bool) -> None:
    rows = bundle["rows"]
    rows.pop(106)
    retained = [row["sequence"] for row in rows]
    mapping = {old: new for new, old in enumerate(retained)}
    rows[105]["next_pc"] = rows[106]["pc"]
    rows[105]["post"]["gpr"]["rip"] = f"0x{rows[106]['pc']:016x}"
    if repaired:
        _remap_receipts(bundle, mapping)
    for index, row in enumerate(rows):
        row["sequence"] = index


def _reorder(bundle: dict[str, Any], repaired: bool) -> None:
    rows = bundle["rows"]
    rows[104], rows[105] = rows[105], rows[104]
    retained = [row["sequence"] for row in rows]
    mapping = {old: new for new, old in enumerate(retained)}
    rows[103]["next_pc"] = rows[104]["pc"]
    rows[103]["post"]["gpr"]["rip"] = f"0x{rows[104]['pc']:016x}"
    rows[104]["pre"] = copy.deepcopy(rows[103]["post"])
    rows[104]["next_pc"] = rows[105]["pc"]
    rows[104]["post"]["gpr"]["rip"] = f"0x{rows[105]['pc']:016x}"
    rows[105]["pre"] = copy.deepcopy(rows[104]["post"])
    rows[105]["next_pc"] = rows[106]["pc"]
    rows[105]["post"] = copy.deepcopy(rows[106]["pre"])
    if repaired:
        _remap_receipts(bundle, mapping)
    else:
        _sparse_remap(bundle, {104: 105, 105: 104})
    for index, row in enumerate(rows):
        row["sequence"] = index


def _upper_xmm(bundle: dict[str, Any]) -> None:
    def with_upper(bits: str) -> str:
        return f"0x{((UPPER << 64) | (int(bits, 16) & ((1 << 64) - 1))):032x}"

    for row in bundle["rows"]:
        sequence = row["sequence"]
        if sequence <= 707:
            row["pre"]["xmm"]["xmm0"] = with_upper(row["pre"]["xmm"]["xmm0"])
        if sequence <= 706:
            row["post"]["xmm"]["xmm0"] = with_upper(row["post"]["xmm"]["xmm0"])
    bundle["capture"]["first_step_return"]["pre"]["context"] = copy.deepcopy(
        bundle["rows"][0]["pre"]
    )
    bundle["capture"]["first_step_return"]["post_context"] = copy.deepcopy(
        bundle["rows"][0]["post"]
    )


def _flip_observation(sequence: int) -> Callable[[dict[str, Any]], None]:
    def mutate(bundle: dict[str, Any]) -> None:
        observation = bundle["rows"][sequence]["pre_memory_observations"][0]
        observation["bytes_hex"] = (
            int(observation["bytes_hex"], 16) ^ 1
        ).to_bytes(observation["size"], "big").hex()

    return mutate


def _transition_specs() -> list[MutationSpec]:
    def unknown_antecedent(transition: dict[str, Any]) -> None:
        transition["antecedent"].update(label="unknown-case", capture_label="unknown-case")

    return [
        MutationSpec("component-bits-changed", "CARRY_BINDING", "carry-binding", lambda t: t["bindings"]["carry"][0].__setitem__("center_bits", "0x3f70000000000001"), "TRANSITION_ONLY"),
        MutationSpec("same-bits-wrong-dynamic-id", "CARRY_BINDING", "carry-binding", lambda t: t["bindings"]["carry"][0].__setitem__("endpoint_memory_value_id", t["bindings"]["carry"][0]["copy_source_value_id"]), "TRANSITION_ONLY"),
        MutationSpec("component-swap", "CARRY_SET", "carry-binding", lambda t: t["bindings"]["carry"].__setitem__(slice(0, 2), [t["bindings"]["carry"][1], t["bindings"]["carry"][0]]), "TRANSITION_ONLY"),
        MutationSpec("component-omission", "CARRY_SET", "carry-binding", lambda t: t["bindings"]["carry"].pop(), "TRANSITION_ONLY"),
        MutationSpec("component-duplication", "CARRY_SET", "carry-binding", lambda t: t["bindings"]["carry"].append(copy.deepcopy(t["bindings"]["carry"][0])), "TRANSITION_ONLY"),
        MutationSpec("stale-previous-endpoint", "CARRY_BINDING", "carry-binding", lambda t: t["bindings"]["carry"][2].__setitem__("endpoint_memory_value_id", "v:boundary:step:full_v"), "TRANSITION_ONLY"),
        MutationSpec("changed-form-only", "FORM_BINDING", "form-binding", lambda t: t["bindings"]["carry"][2]["form"].__setitem__("box", "0x0.0p+0"), "TRANSITION_ONLY"),
        MutationSpec("wrong-time-provenance", "TIME_PROVENANCE", "time-provenance", lambda t: t["bindings"]["time"]["actual_source_receipt"].__setitem__("source_memory_address", t["bindings"]["time"]["actual_source_receipt"]["source_memory_address"] + 8), "TRANSITION_ONLY"),
        MutationSpec("wrong-dt-provenance", "DT_PROVENANCE", "dt-provenance", lambda t: t["bindings"]["dt"]["actual_source_receipt"].__setitem__("source_memory_address", t["bindings"]["dt"]["actual_source_receipt"]["source_memory_address"] + 8), "TRANSITION_ONLY"),
        MutationSpec("pointer-rebinding-receipt", "POINTER_IDENTITY", "pointer-identity", lambda t: t["bindings"]["pointer_identity"]["q"].__setitem__("second_step_address", t["bindings"]["pointer_identity"]["q"]["second_step_address"] + 16), "TRANSITION_ONLY"),
        MutationSpec("unknown-antecedent", "UNSUPPORTED_ANTECEDENT", "antecedent-selection", unknown_antecedent, "TRANSITION_ONLY", receipt_preflight="NOT_REACHED"),
        MutationSpec("antecedent-coherent-local-repin", "ANTECEDENT_PIN", "antecedent-pin", lambda t: t["antecedent"].__setitem__("numeric_ir_sha256", "0" * 64), "TRANSITION_ONLY"),
    ]


def _raw_specs() -> list[MutationSpec]:
    specifications = [
        MutationSpec("dense-record-deletion", "TRACE_CONTROL_TARGET", "control-flow-semantics", lambda b: _delete(b, True)),
        MutationSpec("dense-record-reordering", "TRACE_CONTROL_TARGET", "control-flow-semantics", lambda b: _reorder(b, True)),
        MutationSpec("semantic-write-alteration", "WRITE_SET", "memory-write-semantics", lambda b: b["rows"][714]["possible_memory_writes"][0].update(after_bits="0x00000000000000000000000000000001", value_changed=True)),
        MutationSpec("same-value-store-omission", "WRITE_SET", "memory-write-semantics", lambda b: b["rows"][715].__setitem__("possible_memory_writes", [])),
        MutationSpec("incomplete-zero-coverage", "WRITE_SET", "memory-write-semantics", lambda b: b["rows"][714]["possible_memory_writes"][0].update(size=8, before_bits="0x3f70100000000000", after_bits="0x0000000000000000")),
        MutationSpec("indirect-target-source-byte", "TRACE_CONTROL_TARGET", "control-flow-semantics", lambda b: b["rows"][4]["pre_memory_observations"][0].__setitem__("bytes_hex", "a12b6b0000000000")),
        MutationSpec("return-target-source-byte", "TRACE_CONTROL_TARGET", "control-flow-semantics", lambda b: b["rows"][0]["pre_memory_observations"][0].__setitem__("bytes_hex", "20367baeff7f0000")),
    ]
    for name, sequence in (
        ("time-source-byte", 718),
        ("dt-source-byte", 723),
        ("full-v-source-byte", 726),
        ("cpointer-source-byte", 722),
        ("half-ndim-source-byte", 724),
        ("n-source-byte", 725),
    ):
        specifications.append(MutationSpec(name, "REGISTER_SEMANTICS", "register-semantics", _flip_observation(sequence)))
    specifications.extend(
        [
            MutationSpec("tls-destination-address", "WRITE_SET", "memory-write-semantics", lambda b: b["rows"][369]["possible_memory_writes"][0].__setitem__("address", b["rows"][369]["possible_memory_writes"][0]["address"] + 8)),
            MutationSpec("required-read-omission", "MEMORY_OBSERVATION", "memory-read-coverage", lambda b: b["rows"][718].__setitem__("pre_memory_observations", [])),
            MutationSpec("gradient-push-source-byte", "WRITE_SET", "memory-write-semantics", lambda b: b["rows"][721]["pre_memory_observations"][0].__setitem__("bytes_hex", "21648e0200000000")),
            MutationSpec("q-register-def-use", "REGISTER_SEMANTICS", "register-semantics", lambda b: _propagate(b["rows"], 719, "rcx", "0x0000000002ebaed1")),
            MutationSpec("latent-register-def-use", "REGISTER_SEMANTICS", "register-semantics", lambda b: _propagate(b["rows"], 720, "r9", "0x0000000002f34161")),
            MutationSpec("structured-process-identity", "EXECUTION_AUTH", "execution-authentication", lambda b: b["execution"]["process_identity"].__setitem__("proc_stat_start_time_ticks", 12882), receipt_preflight="NOT_REACHED"),
            MutationSpec("source-receipt-omission", "SOURCE_SET", "source-pin-validation", lambda b: b["execution"]["source_sha256_before_execution"].pop("runtime_trace/semantics.py")),
            MutationSpec("module-receipt-omission", "MODULE_SET", "module-pin-validation", lambda b: b["execution"]["frozen_module_sha256_set"].pop(), receipt_preflight="NOT_REACHED"),
        ]
    )
    return specifications


def _fix2_raw_specs() -> list[MutationSpec]:
    return [
        MutationSpec("movsd-memory-upper64", "REGISTER_SEMANTICS", "register-semantics", _upper_xmm),
        MutationSpec("dense-deletion-stale-receipts", "SEQUENCE_RECEIPT", "sequence-receipt-preflight", lambda b: _delete(b, False), receipt_preflight="REFUSED"),
        MutationSpec("dense-deletion-fully-repaired", "TRACE_CONTROL_TARGET", "control-flow-semantics", lambda b: _delete(b, True)),
        MutationSpec("dense-reorder-stale-receipts", "SEQUENCE_RECEIPT", "sequence-receipt-preflight", lambda b: _reorder(b, False), receipt_preflight="REFUSED"),
        MutationSpec("dense-reorder-fully-repaired", "TRACE_CONTROL_TARGET", "control-flow-semantics", lambda b: _reorder(b, True)),
    ]


def _save_result(
    case_dir: Path,
    spec: MutationSpec,
    exc: CheckerRefused,
    actual_input_hashes: dict[str, str],
    *,
    source_raw_sha256: dict[str, str] | None = None,
) -> dict[str, Any]:
    if exc.code != spec.expected_code:
        raise RuntimeError(
            f"{spec.name}: expected {spec.expected_code}, got {exc.code}: {exc.reason}"
        )
    result = {
        "schema": "gala-caller-transition-checker-fix3-mutation-result-v1",
        "name": spec.name,
        "verdict": "REFUSED",
        "code": exc.code,
        "reason": exc.reason,
        "trust_mode": spec.trust_mode,
        "input_kind": spec.input_kind,
        "declared_refusal_stage": spec.declared_refusal_stage,
        "receipt_preflight": spec.receipt_preflight,
        "actual_input_hashes": actual_input_hashes,
    }
    receipt = {
        "schema": "gala-caller-transition-checker-fix3-mutation-receipt-v1",
        "name": spec.name,
        "source_case": CASE,
        "expected_refusal_code": spec.expected_code,
        "trust_mode": spec.trust_mode,
        "input_kind": spec.input_kind,
        "declared_refusal_stage": spec.declared_refusal_stage,
        "receipt_preflight": spec.receipt_preflight,
        "actual_input_hashes": actual_input_hashes,
    }
    if source_raw_sha256 is not None:
        receipt["source_raw_sha256"] = source_raw_sha256
    _write(case_dir / "mutation-receipt.json", receipt)
    _write(case_dir / "result.json", result)
    return result


def _run_spec(out: Path, spec: MutationSpec, source_hashes: dict[str, str]) -> dict[str, Any]:
    case_dir = out / "cases" / spec.name
    case_dir.mkdir(parents=True)
    if spec.input_kind == "TRANSITION_ONLY":
        raw, transition, pins, hashes = _materialize_transition(case_dir, spec.mutate)
        source_receipt = source_hashes
    else:
        repair_counts = spec.receipt_preflight != "REFUSED"
        raw, transition, pins, hashes = _materialize_raw(
            case_dir, spec.mutate, repair_counts=repair_counts
        )
        source_receipt = None
    try:
        _check_bundle_with_pins(raw, transition, pins, root=ROOT)
    except CheckerRefused as exc:
        return _save_result(
            case_dir, spec, exc, hashes, source_raw_sha256=source_receipt
        )
    raise RuntimeError(f"mutation was accepted: {spec.name}")


def _run_public_case(out: Path) -> tuple[MutationSpec, dict[str, Any]]:
    spec = MutationSpec(
        "public-coherent-repin",
        "TRUST_PATH",
        "production-trust-gate",
        lambda b: b["rows"][4]["pre_memory_observations"][0].__setitem__(
            "bytes_hex", "a12b6b0000000000"
        ),
        trust_mode="PUBLIC_RIGID_PRODUCTION",
        receipt_preflight="NOT_REACHED",
    )
    case_dir = out / "cases" / spec.name
    case_dir.mkdir(parents=True)
    raw, transition, _pins, hashes = _materialize_raw(case_dir, spec.mutate)
    try:
        check_transition(raw, transition, root=ROOT)
    except CheckerRefused as exc:
        return spec, _save_result(case_dir, spec, exc, hashes)
    raise RuntimeError("public coherent repin was accepted")


def _run_unknown_instruction(out: Path) -> tuple[MutationSpec, dict[str, Any]]:
    spec = MutationSpec(
        "unknown-instruction-effect",
        "UNKNOWN_INSTRUCTION_EFFECT",
        "closed-instruction-decoder",
        lambda _bundle: None,
        "STRUCTURED_UNIT_FIXTURE",
        "UNIT_CLOSED_DECODER",
        "NOT_APPLICABLE",
    )
    case_dir = out / "cases" / spec.name
    case_dir.mkdir(parents=True)
    fixture = {
        "schema": "gala-caller-transition-unknown-instruction-fixture-v1",
        "assembly": "stosq  %rax,(%rdi)",
        "row": {
            "sequence": 9,
            "pc": 0x1000,
            "instruction_bytes": "48ab",
            "pre": {"gpr": {"rax": "0x0000000000000001", "rdi": "0x2000", "rsp": "0x3000"}},
            "post": {"gpr": {"rax": "0x0000000000000001", "rdi": "0x2008", "rsp": "0x3000"}},
        },
    }
    fixture_path = case_dir / "input" / "fixture.json"
    _write(fixture_path, fixture)
    try:
        derive_possible_write_effects(fixture["row"], fixture["assembly"])
    except CheckerRefused as exc:
        return spec, _save_result(case_dir, spec, exc, _input_hashes(case_dir))
    raise RuntimeError("unknown instruction fixture was accepted")


def _run_wrong_origin(out: Path) -> tuple[MutationSpec, dict[str, Any]]:
    spec = MutationSpec(
        "same-bits-wrong-origin-role",
        "ABI_PROVENANCE",
        "abi-origin-role",
        lambda _bundle: None,
        "STRUCTURED_UNIT_FIXTURE",
        "UNIT_STRUCTURED_FIXTURE",
        "NOT_APPLICABLE",
    )
    case_dir = out / "cases" / spec.name
    case_dir.mkdir(parents=True)
    fixture = {
        "schema": "gala-caller-transition-origin-fixture-v1",
        "location": "xmm0_time",
        "value_bits": "0x3fa0000000000000",
        "required_role": "time",
        "origin": {
            "kind": "Load",
            "sequence": 718,
            "address": 36493040,
            "width": 8,
            "memory_origin": {
                "kind": "AuthenticatedMemoryRoot",
                "case": CASE,
                "address": 36493040,
                "captured_before_sequence": 718,
                "width": 8,
                "role": "dt",
            },
        },
    }
    fixture_path = case_dir / "input" / "fixture.json"
    _write(fixture_path, fixture)
    try:
        _require_origin_role(fixture["origin"], fixture["required_role"], fixture["location"])
    except CheckerRefused as exc:
        return spec, _save_result(case_dir, spec, exc, _input_hashes(case_dir))
    raise RuntimeError("wrong origin-role fixture was accepted")


def generate(out: Path) -> dict[str, Any]:
    if out.exists():
        raise FileExistsError(f"exclusive output already exists: {out}")
    (out / "cases").mkdir(parents=True)
    source_hashes = _source_raw_hashes()
    ordered: list[tuple[MutationSpec, dict[str, Any]]] = []
    for spec in _transition_specs() + _raw_specs():
        ordered.append((spec, _run_spec(out, spec, source_hashes)))
    ordered.append(_run_public_case(out))
    ordered.append(_run_unknown_instruction(out))
    for spec in _fix2_raw_specs():
        ordered.append((spec, _run_spec(out, spec, source_hashes)))
    ordered.append(_run_wrong_origin(out))

    report_hashes = {
        case: _sha(NORMAL_REPORTS / case / "checker_report.json")
        for case in (CASE, "fresh-closure-fresh-01-readproof-01")
    }
    manifest = {
        "schema": "gala-caller-transition-checker-fix3-mutation-manifest-v1",
        "source_case": CASE,
        "source_raw_sha256": source_hashes,
        "source_transition_sha256": _sha(TRANSITION),
        "checker_sha256": _sha(CHECKER),
        "generator_sha256": _sha(Path(__file__)),
        "authoritative_fix2_normal_report_sha256": report_hashes,
        "case_count": len(ordered),
        "cases": [
            {
                "name": spec.name,
                "verdict": result["verdict"],
                "code": result["code"],
                "trust_mode": spec.trust_mode,
                "input_kind": spec.input_kind,
                "declared_refusal_stage": spec.declared_refusal_stage,
                "receipt_preflight": spec.receipt_preflight,
                "actual_input_hashes": result["actual_input_hashes"],
                "receipt_sha256": _sha(out / "cases" / spec.name / "mutation-receipt.json"),
                "result_sha256": _sha(out / "cases" / spec.name / "result.json"),
            }
            for spec, result in ordered
        ],
        "all_refused": all(result["verdict"] == "REFUSED" for _spec, result in ordered),
        "production_trust_override_exposed": False,
    }
    if len(ordered) != 41:
        raise RuntimeError(f"expected 41 retained cases, generated {len(ordered)}")
    _write(out / "manifest.json", manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(generate(args.out.resolve()), sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
