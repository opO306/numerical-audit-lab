import json
import hashlib
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]


def test_nsteps2_harness_is_exactly_one_token_change():
    old = (ROOT / "runtime_trace/harness.py").read_bytes()
    new = (ROOT / "runtime_trace/harness_nsteps2.py").read_bytes()
    assert old.count(b"n_steps=1") == 1
    assert new == old.replace(b"n_steps=1", b"n_steps=2", 1)
    assert b'"n_steps": 1' in new


def test_output_directory_creation_is_exclusive(tmp_path):
    from runtime_trace.caller_transition.run_acquisition import ensure_exclusive_output

    target = tmp_path / "new"
    ensure_exclusive_output(target)
    marker = target / "preserved"
    marker.write_text("original", encoding="utf-8")
    with pytest.raises(FileExistsError):
        ensure_exclusive_output(target)
    assert marker.read_text(encoding="utf-8") == "original"


@pytest.mark.parametrize(
    "digest",
    [
        "a6ac98736304bb9f6a92e473bba45da10d9b5b99f8019e2ca15eb6a7f86234fc",
        "3a15d66867d83762c7f2f1e37359cb8f6c5743edb369c65285cb0b1c4f7498bf",
    ],
)
def test_module_resolver_opens_only_hash_registered_packaged_elf(digest):
    from runtime_trace.caller_transition.module_resolver import resolve_module

    path = resolve_module(ROOT, digest)
    assert path.is_file()
    assert path.read_bytes().startswith(b"\x7fELF")


def test_module_resolver_refuses_unknown_digest():
    from runtime_trace.caller_transition.module_resolver import ResolverRefused, resolve_module

    with pytest.raises(ResolverRefused, match="unregistered"):
        resolve_module(ROOT, "0" * 64)


@pytest.mark.parametrize("case", ["audited-attempt-05", "fresh-closure-fresh-01"])
def test_fresh_capture_is_controlled_stop_with_complete_raw_contract(case):
    from runtime_trace.caller_transition.capture_contract import validate_capture

    evidence = ROOT / "runtime_trace/caller_transition/artifacts" / case
    capture = json.loads((evidence / "capture.json").read_text(encoding="utf-8"))
    summary = validate_capture(capture, root=ROOT)
    assert summary["verdict"] == "CONTROLLED_STOP"
    assert summary["body_instructions_executed"] == 0
    assert summary["record_count"] == len(
        (evidence / "caller_trace.jsonl").read_text(encoding="utf-8").splitlines()
    )
    assert capture["first_step_entry"]["abi"]["n"] == 1
    assert capture["first_step_entry"]["abi"]["half_ndim"] == 2
    assert capture["second_step_entry"]["abi"]["n"] == 1
    assert capture["second_step_entry"]["abi"]["half_ndim"] == 2
    assert capture["second_step_entry"]["abi"]["t_bits"] == "0x3fa0000000000000"
    assert capture["second_step_entry"]["abi"]["dt_bits"] == "0x3f90000000000000"
    assert capture["old_capture_continuation_present"] is False
    first_pointers = capture["first_step_entry"]["abi"]["pointers"]
    second_pointers = capture["second_step_entry"]["abi"]["pointers"]
    for component in ["q", "full_v", "latent", "gradient"]:
        assert second_pointers[component] == first_pointers[component]
    for boundary in ["first_step_entry", "first_step_return", "second_step_entry"]:
        inventory = capture[boundary]["thread_inventory"]
        assert sum(item["selected_owner"] for item in inventory) == 1
        assert all(item["stopped_under_all_stop"] for item in inventory)


def test_two_acquisitions_are_distinct_processes():
    base = ROOT / "runtime_trace/caller_transition/artifacts"
    a = json.loads((base / "audited-attempt-05/execution.json").read_text())
    b = json.loads((base / "fresh-closure-fresh-01/execution.json").read_text())
    assert a["launcher_pid"] != b["launcher_pid"]
    assert a["inferior_pid"] != b["inferior_pid"]
    assert a["antecedent_label"] == "attempt-05"
    assert b["antecedent_label"] == "closure-fresh-01"


def test_execution_receipt_hashes_every_acquisition_source():
    execution = json.loads(
        (ROOT / "runtime_trace/caller_transition/artifacts/audited-attempt-05/execution.json").read_text()
    )
    assert set(execution["source_sha256_before_execution"]) == {
        "runtime_trace/harness.py",
        "runtime_trace/harness_nsteps2.py",
        "runtime_trace/caller_transition/gdb_acquire.py",
        "runtime_trace/caller_transition/write_effects.py",
        "runtime_trace/caller_transition/module_resolver.py",
        "runtime_trace/caller_transition/frozen_modules/manifest.json",
        "runtime_trace/caller_transition/run_acquisition.py",
    }
    for relative, digest in execution["source_sha256_before_execution"].items():
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == digest
