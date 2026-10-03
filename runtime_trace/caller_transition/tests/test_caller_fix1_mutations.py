from __future__ import annotations

import copy
import hashlib
import json
import shutil
from dataclasses import replace
from pathlib import Path
from typing import Callable

import pytest

from runtime_trace.caller_transition.checker import (
    CheckerRefused,
    _PRODUCTION_CASE_PINS,
    _check_bundle_with_pins,
    check_transition,
)


ROOT = Path(__file__).resolve().parents[3]
CALLER = ROOT / "runtime_trace" / "caller_transition"
CASE = "audited-attempt-05-readproof-01"
RAW = CALLER / "artifacts" / CASE
TRANSITION = CALLER / "artifacts" / "producer-fix-round2" / CASE / "transition.json"


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def _rebuild(tmp_path: Path, mutate: Callable[[dict], None]):
    raw = tmp_path / "raw"
    shutil.copytree(RAW, raw)
    transition_path = tmp_path / "transition.json"
    shutil.copy2(TRANSITION, transition_path)
    bundle = {
        "rows": [json.loads(line) for line in (raw / "caller_trace.jsonl").read_text().splitlines()],
        "capture": json.loads((raw / "capture.json").read_text()),
        "execution": json.loads((raw / "execution.json").read_text()),
        "seal": json.loads((raw / "acquisition_seal.json").read_text()),
        "transition": json.loads(transition_path.read_text()),
    }
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
    (raw / "capture.json").write_bytes(_canonical(capture))
    (raw / "execution.json").write_bytes(_canonical(bundle["execution"]))
    for name in bundle["seal"]["exact_file_name_set"]:
        bundle["seal"]["sealed_files"][name] = hashlib.sha256((raw / name).read_bytes()).hexdigest()
    (raw / "acquisition_seal.json").write_bytes(_canonical(bundle["seal"]))
    transition = bundle["transition"]
    transition["capture"]["record_count"] = len(bundle["rows"])
    transition["authentication"]["trace_sha256"] = capture["trace_sha256"]
    transition["authentication"]["final_chain"] = previous
    transition["authentication"]["capture_sha256"] = hashlib.sha256((raw / "capture.json").read_bytes()).hexdigest()
    transition["authentication"]["execution_sha256"] = hashlib.sha256((raw / "execution.json").read_bytes()).hexdigest()
    transition["authentication"]["seal_sha256"] = hashlib.sha256((raw / "acquisition_seal.json").read_bytes()).hexdigest()
    transition_path.write_bytes(_canonical(transition))
    base = _PRODUCTION_CASE_PINS[CASE]
    pins = replace(
        base,
        transition_sha256=hashlib.sha256(transition_path.read_bytes()).hexdigest(),
        seal_sha256=hashlib.sha256((raw / "acquisition_seal.json").read_bytes()).hexdigest(),
        capture_sha256=hashlib.sha256((raw / "capture.json").read_bytes()).hexdigest(),
        execution_sha256=hashlib.sha256((raw / "execution.json").read_bytes()).hexdigest(),
        trace_sha256=capture["trace_sha256"],
        trace_final_chain=previous,
        sealed_files=copy.deepcopy(bundle["seal"]["sealed_files"]),
    )
    return raw, transition_path, pins


def _refused(paths, code: str) -> CheckerRefused:
    with pytest.raises(CheckerRefused) as caught:
        _check_bundle_with_pins(*paths, root=ROOT)
    assert caught.value.code == code
    return caught.value


def _remap_receipts(bundle: dict, mapping: dict[int, int]) -> None:
    def visit(value, parent_key=""):
        if isinstance(value, dict):
            for key, item in list(value.items()):
                if key == "sequence" or key.endswith("_sequence"):
                    if isinstance(item, int) and item in mapping:
                        value[key] = mapping[item]
                elif key.endswith("_sequences") and isinstance(item, list):
                    value[key] = [mapping[number] for number in item if number in mapping]
                else:
                    visit(item, key)
        elif isinstance(value, list):
            for item in value:
                visit(item, parent_key)
    visit(bundle["capture"])
    visit(bundle["transition"])


def test_fix1_deletion_fixture_is_exposed_as_stale_before_semantics(tmp_path: Path) -> None:
    def mutate(bundle: dict) -> None:
        rows = bundle["rows"]
        old = [row["sequence"] for row in rows]
        rows.pop(106)
        rows[105]["next_pc"] = rows[106]["pc"]
        rows[105]["post"]["gpr"]["rip"] = f"0x{rows[106]['pc']:016x}"
        mapping = {number: index for index, number in enumerate(old) if number != 106}
        for index, row in enumerate(rows):
            row["sequence"] = index
        _remap_receipts(bundle, mapping)

    _refused(_rebuild(tmp_path, mutate), "SEQUENCE_RECEIPT")


def test_fix1_reorder_fixture_is_exposed_as_stale_before_semantics(tmp_path: Path) -> None:
    def mutate(bundle: dict) -> None:
        rows = bundle["rows"]
        rows[104], rows[105] = rows[105], rows[104]
        rows[103]["next_pc"] = rows[104]["pc"]
        rows[103]["post"]["gpr"]["rip"] = f"0x{rows[104]['pc']:016x}"
        rows[104]["pre"] = copy.deepcopy(rows[103]["post"])
        rows[104]["next_pc"] = rows[105]["pc"]
        rows[104]["post"]["gpr"]["rip"] = f"0x{rows[105]['pc']:016x}"
        rows[105]["pre"] = copy.deepcopy(rows[104]["post"])
        rows[105]["next_pc"] = rows[106]["pc"]
        rows[105]["post"] = copy.deepcopy(rows[106]["pre"])
        mapping = {104: 105, 105: 104}
        for index, row in enumerate(rows):
            row["sequence"] = index
        _remap_receipts(bundle, mapping)

    _refused(_rebuild(tmp_path, mutate), "SEQUENCE_RECEIPT")


def test_repaired_indirect_target_bytes_reach_control_semantics(tmp_path: Path) -> None:
    def mutate(bundle: dict) -> None:
        row = bundle["rows"][4]
        row["pre_memory_observations"][0]["bytes_hex"] = "a12b6b0000000000"

    _refused(_rebuild(tmp_path, mutate), "TRACE_CONTROL_TARGET")


def test_repaired_return_stack_bytes_reach_control_semantics(tmp_path: Path) -> None:
    def mutate(bundle: dict) -> None:
        row = bundle["rows"][0]
        row["pre_memory_observations"][0]["bytes_hex"] = "20367baeff7f0000"

    _refused(_rebuild(tmp_path, mutate), "TRACE_CONTROL_TARGET")


@pytest.mark.parametrize("sequence", [718, 723, 726])
def test_repaired_final_abi_memory_bytes_reach_register_semantics(tmp_path: Path, sequence: int) -> None:
    def mutate(bundle: dict) -> None:
        obs = bundle["rows"][sequence]["pre_memory_observations"][0]
        obs["bytes_hex"] = (int(obs["bytes_hex"], 16) ^ 1).to_bytes(obs["size"], "big").hex()

    _refused(_rebuild(tmp_path, mutate), "REGISTER_SEMANTICS")


def test_repaired_tls_destination_address_is_refused(tmp_path: Path) -> None:
    def mutate(bundle: dict) -> None:
        bundle["rows"][369]["possible_memory_writes"][0]["address"] += 8

    _refused(_rebuild(tmp_path, mutate), "WRITE_SET")


def test_missing_required_memory_read_is_refused(tmp_path: Path) -> None:
    def mutate(bundle: dict) -> None:
        bundle["rows"][718]["pre_memory_observations"] = []

    _refused(_rebuild(tmp_path, mutate), "SEQUENCE_RECEIPT")


def test_gradient_push_uses_observed_source_bytes(tmp_path: Path) -> None:
    def mutate(bundle: dict) -> None:
        bundle["rows"][721]["pre_memory_observations"][0]["bytes_hex"] = "21648e0200000000"

    _refused(_rebuild(tmp_path, mutate), "WRITE_SET")


def test_q_register_copy_cannot_be_propagated_by_claimed_state(tmp_path: Path) -> None:
    def mutate(bundle: dict) -> None:
        changed = "0x0000000002ebaed1"
        bundle["rows"][719]["post"]["gpr"]["rcx"] = changed
        for row in bundle["rows"][720:]:
            row["pre"]["gpr"]["rcx"] = changed
            row["post"]["gpr"]["rcx"] = changed

    _refused(_rebuild(tmp_path, mutate), "REGISTER_SEMANTICS")


def test_structured_process_identity_is_literal(tmp_path: Path) -> None:
    def mutate(bundle: dict) -> None:
        bundle["execution"]["process_identity"]["proc_stat_start_time_ticks"] += 1

    _refused(_rebuild(tmp_path, mutate), "EXECUTION_AUTH")


def test_coherently_repinned_execution_cannot_omit_module_pin(tmp_path: Path) -> None:
    def mutate(bundle: dict) -> None:
        bundle["execution"]["frozen_module_sha256_set"].pop()

    _refused(_rebuild(tmp_path, mutate), "MODULE_SET")


def test_public_path_rejects_coherently_repinned_bundle(tmp_path: Path) -> None:
    raw, transition, _pins = _rebuild(
        tmp_path, lambda bundle: bundle["rows"][4]["pre_memory_observations"][0].__setitem__("bytes_hex", "a12b6b0000000000")
    )
    with pytest.raises(CheckerRefused) as caught:
        check_transition(raw, transition, root=ROOT)
    assert caught.value.code == "TRUST_PATH"


def test_missing_source_receipt_is_refused_after_test_repin(tmp_path: Path) -> None:
    def mutate(bundle: dict) -> None:
        bundle["execution"]["source_sha256_before_execution"].pop("runtime_trace/semantics.py")

    _refused(_rebuild(tmp_path, mutate), "SOURCE_SET")
