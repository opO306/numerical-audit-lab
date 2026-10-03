"""Generate versioned Task 2 fix-round-2 checker mutation evidence.

This evidence generator is deliberately separate from the production checker
CLI.  It creates test-only repinned bundles so repaired attacks reach the
independent semantic core; it cannot alter production literal pins.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import shutil
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable

from runtime_trace.caller_transition.checker import (
    CheckerRefused,
    _PRODUCTION_CASE_PINS,
    _check_bundle_with_pins,
    _require_origin_role,
)


ROOT = Path(__file__).resolve().parents[2]
CASE = "audited-attempt-05-readproof-01"
RAW = ROOT / "runtime_trace" / "caller_transition" / "artifacts" / CASE
TRANSITION = (
    ROOT / "runtime_trace" / "caller_transition" / "artifacts"
    / "producer-fix-round2" / CASE / "transition.json"
)
UPPER = 0x1122334455667788


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_canonical(value))


def _remap_receipts(bundle: dict[str, Any], mapping: dict[int, int]) -> None:
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


def _broken_sparse_remap(bundle: dict[str, Any], mapping: dict[int, int]) -> None:
    """Reproduce the superseded fix1 sparse-map behavior for a stale receipt case."""
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
            for row in rows for observation in row["pre_memory_observations"]
        ),
        "possible_memory_writes": sum(len(row["possible_memory_writes"]) for row in rows),
        "same_value_writes": sum(
            write["value_changed"] is False
            for row in rows for write in row["possible_memory_writes"]
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


def _load_bundle(raw: Path, transition: Path) -> dict[str, Any]:
    return {
        "rows": [json.loads(line) for line in (raw / "caller_trace.jsonl").read_text().splitlines()],
        "capture": json.loads((raw / "capture.json").read_text()),
        "execution": json.loads((raw / "execution.json").read_text()),
        "seal": json.loads((raw / "acquisition_seal.json").read_text()),
        "transition": json.loads(transition.read_text()),
    }


def _materialize(
    case_dir: Path, mutate: Callable[[dict[str, Any]], None]
) -> tuple[Path, Path, object, dict[str, str]]:
    raw = case_dir / "input" / "raw"
    transition_path = case_dir / "input" / "transition.json"
    shutil.copytree(RAW, raw)
    shutil.copy2(TRANSITION, transition_path)
    bundle = _load_bundle(raw, transition_path)
    mutate(bundle)

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
    capture["counts"]["rows"] = len(bundle["rows"])
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
    hashes = {
        str(path.relative_to(case_dir)).replace("\\", "/"): _sha(path)
        for path in sorted((case_dir / "input").rglob("*")) if path.is_file()
    }
    return raw, transition_path, pins, hashes


def _upper_xmm(bundle: dict[str, Any]) -> None:
    def with_upper(bits: str) -> str:
        return f"0x{((UPPER << 64) | (int(bits, 16) & ((1 << 64) - 1))):032x}"

    for row in bundle["rows"]:
        sequence = row["sequence"]
        if sequence <= 707:
            row["pre"]["xmm"]["xmm0"] = with_upper(row["pre"]["xmm"]["xmm0"])
        if sequence <= 706:
            row["post"]["xmm"]["xmm0"] = with_upper(row["post"]["xmm"]["xmm0"])
    bundle["capture"]["first_step_return"]["pre"]["context"] = copy.deepcopy(bundle["rows"][0]["pre"])
    bundle["capture"]["first_step_return"]["post_context"] = copy.deepcopy(bundle["rows"][0]["post"])


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
    if repaired:
        _repair_counts(bundle)


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
        _broken_sparse_remap(bundle, {104: 105, 105: 104})
    for index, row in enumerate(rows):
        row["sequence"] = index
    if repaired:
        _repair_counts(bundle)


def _run_bundle_case(
    root: Path, name: str, mutate: Callable[[dict[str, Any]], None],
    expected: str, receipt_preflight: str,
) -> dict[str, Any]:
    case_dir = root / "cases" / name
    case_dir.mkdir(parents=True)
    raw, transition, pins, hashes = _materialize(case_dir, mutate)
    try:
        _check_bundle_with_pins(raw, transition, pins, root=ROOT)
    except CheckerRefused as exc:
        result = {
            "schema": "gala-caller-transition-checker-fix2-mutation-result-v1",
            "verdict": "REFUSED", "code": exc.code, "reason": exc.reason,
            "trust_mode": "TEST_ONLY_REPIN", "receipt_preflight": receipt_preflight,
            "actual_input_hashes": hashes,
        }
    else:
        raise RuntimeError(f"mutation was accepted: {name}")
    if result["code"] != expected:
        raise RuntimeError(f"{name}: expected {expected}, got {result['code']}: {result['reason']}")
    receipt = {
        "schema": "gala-caller-transition-checker-fix2-mutation-receipt-v1",
        "name": name, "source_case": CASE, "expected_refusal_code": expected,
        "trust_mode": "TEST_ONLY_REPIN", "receipt_preflight": receipt_preflight,
        "actual_input_hashes": hashes,
    }
    _write(case_dir / "mutation-receipt.json", receipt)
    _write(case_dir / "result.json", result)
    return result


def generate(out: Path) -> dict[str, Any]:
    if out.exists():
        raise FileExistsError(f"exclusive output already exists: {out}")
    (out / "cases").mkdir(parents=True)
    specifications = [
        ("movsd-memory-upper64", _upper_xmm, "REGISTER_SEMANTICS", "PASSED"),
        ("dense-deletion-stale-receipts", lambda bundle: _delete(bundle, False), "SEQUENCE_RECEIPT", "REFUSED"),
        ("dense-deletion-fully-repaired", lambda bundle: _delete(bundle, True), "TRACE_CONTROL_TARGET", "PASSED"),
        ("dense-reorder-stale-receipts", lambda bundle: _reorder(bundle, False), "SEQUENCE_RECEIPT", "REFUSED"),
        ("dense-reorder-fully-repaired", lambda bundle: _reorder(bundle, True), "TRACE_CONTROL_TARGET", "PASSED"),
    ]
    results = {
        name: _run_bundle_case(out, name, mutate, expected, preflight)
        for name, mutate, expected, preflight in specifications
    }

    origin_dir = out / "cases" / "same-bits-wrong-origin-role"
    origin_dir.mkdir(parents=True)
    fixture = {
        "schema": "gala-caller-transition-origin-fixture-v1",
        "location": "xmm0_time", "value_bits": "0x3fa0000000000000",
        "required_role": "time",
        "origin": {
            "kind": "Load", "sequence": 718, "address": 36493040, "width": 8,
            "memory_origin": {
                "kind": "AuthenticatedMemoryRoot", "case": CASE,
                "address": 36493040, "captured_before_sequence": 718,
                "width": 8, "role": "dt",
            },
        },
    }
    fixture_path = origin_dir / "input" / "fixture.json"
    _write(fixture_path, fixture)
    try:
        _require_origin_role(fixture["origin"], fixture["required_role"], fixture["location"])
    except CheckerRefused as exc:
        origin_result = {
            "schema": "gala-caller-transition-checker-fix2-mutation-result-v1",
            "verdict": "REFUSED", "code": exc.code, "reason": exc.reason,
            "trust_mode": "UNIT_STRUCTURED_FIXTURE",
            "actual_input_hashes": {"input/fixture.json": _sha(fixture_path)},
        }
    else:
        raise RuntimeError("wrong-role origin fixture was accepted")
    if origin_result["code"] != "ABI_PROVENANCE":
        raise RuntimeError(f"wrong origin refusal: {origin_result}")
    _write(origin_dir / "mutation-receipt.json", {
        "schema": "gala-caller-transition-checker-fix2-mutation-receipt-v1",
        "name": "same-bits-wrong-origin-role", "expected_refusal_code": "ABI_PROVENANCE",
        "trust_mode": "UNIT_STRUCTURED_FIXTURE",
        "actual_input_hashes": origin_result["actual_input_hashes"],
    })
    _write(origin_dir / "result.json", origin_result)
    results["same-bits-wrong-origin-role"] = origin_result

    manifest = {
        "schema": "gala-caller-transition-checker-fix2-mutation-manifest-v1",
        "generator_sha256": _sha(Path(__file__)),
        "source_case": CASE,
        "cases": [
            {
                "name": name, "verdict": result["verdict"], "code": result["code"],
                "trust_mode": result["trust_mode"],
                "result_sha256": _sha(out / "cases" / name / "result.json"),
                "receipt_sha256": _sha(out / "cases" / name / "mutation-receipt.json"),
            }
            for name, result in results.items()
        ],
        "all_refused": all(result["verdict"] == "REFUSED" for result in results.values()),
    }
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
