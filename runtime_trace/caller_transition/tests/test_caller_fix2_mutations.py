from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from runtime_trace.caller_transition.checker import (
    CheckerRefused,
    _check_bundle_with_pins,
    _require_origin_role,
)
from runtime_trace.caller_transition.tests.test_caller_checker import CASES, ROOT, _paths
from runtime_trace.caller_transition.tests.test_caller_fix1_mutations import _rebuild


UPPER = 0x1122334455667788


def _with_upper(bits: str) -> str:
    return f"0x{((UPPER << 64) | (int(bits, 16) & ((1 << 64) - 1))):032x}"


def _refusal(paths: tuple[Path, Path, object]) -> CheckerRefused:
    with pytest.raises(CheckerRefused) as caught:
        _check_bundle_with_pins(*paths, root=ROOT)
    return caught.value


def _remap_declared_receipts(bundle: dict, mapping: dict[int, int]) -> None:
    def visit(value: object) -> None:
        if isinstance(value, dict):
            for key, item in list(value.items()):
                if key == "sequence" or key.endswith("_sequence"):
                    if isinstance(item, int):
                        assert item in mapping, (key, item)
                        value[key] = mapping[item]
                elif key.endswith("_sequences"):
                    assert isinstance(item, list)
                    assert all(isinstance(number, int) and number in mapping for number in item)
                    value[key] = [mapping[number] for number in item]
                else:
                    visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)

    visit(bundle["capture"])
    visit(bundle["transition"])


def _repair_count_receipts(bundle: dict) -> None:
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


def test_memory_form_movsd_clears_upper_64_bits_at_actual_rows(tmp_path: Path) -> None:
    def mutate(bundle: dict) -> None:
        for row in bundle["rows"]:
            sequence = row["sequence"]
            if sequence <= 707:
                row["pre"]["xmm"]["xmm0"] = _with_upper(row["pre"]["xmm"]["xmm0"])
            if sequence <= 706:
                row["post"]["xmm"]["xmm0"] = _with_upper(row["post"]["xmm"]["xmm0"])
        bundle["capture"]["first_step_return"]["pre"]["context"] = copy.deepcopy(bundle["rows"][0]["pre"])
        bundle["capture"]["first_step_return"]["post_context"] = copy.deepcopy(bundle["rows"][0]["post"])

    refused = _refusal(_rebuild(tmp_path, mutate))
    assert refused.code == "REGISTER_SEMANTICS"
    assert "sequence 615" in refused.reason


@pytest.mark.parametrize(("case", "_label"), CASES)
def test_normal_report_serializes_all_nine_final_abi_origin_chains(case: str, _label: str) -> None:
    from runtime_trace.caller_transition.checker import check_transition

    report = check_transition(*_paths(case), root=ROOT)
    chains = report["abi_origin_chains"]
    assert list(chains) == [
        "rcx_q",
        "r8_full_v",
        "r9_latent",
        "stack_gradient",
        "xmm0_time",
        "xmm1_dt",
        "rdi_cpotential",
        "rsi_n",
        "rdx_half_ndim",
    ]
    assert [chains[name]["role"] for name in chains] == [
        "q",
        "full_v",
        "latent",
        "gradient",
        "time",
        "dt",
        "cpotential",
        "n",
        "half_ndim",
    ]
    assert chains["xmm0_time"]["origin"]["kind"] == "Load"
    assert chains["xmm1_dt"]["origin"]["kind"] == "Load"
    assert chains["stack_gradient"]["origin"]["kind"] == "Store"
    assert report["origin_provenance_complete"] is True

    def sequences(origin: object) -> list[int]:
        found: list[int] = []
        if isinstance(origin, dict):
            if isinstance(origin.get("sequence"), int):
                found.append(origin["sequence"])
            for value in origin.values():
                found.extend(sequences(value))
        elif isinstance(origin, list):
            for value in origin:
                found.extend(sequences(value))
        return found

    assert sequences(chains["rcx_q"]["origin"])[:6] == [719, 539, 522, 360, 54]
    assert sequences(chains["r9_latent"]["origin"])[:6] == [720, 582, 450, 359, 55]
    assert sequences(chains["r8_full_v"]["origin"])[:2] == [726, 726]
    assert sequences(chains["stack_gradient"]["origin"])[:2] == [721, 721]


def test_same_bits_with_wrong_origin_role_is_refused() -> None:
    fixture = {
        "kind": "Load",
        "sequence": 718,
        "address": 36493040,
        "width": 8,
        "memory_origin": {
            "kind": "AuthenticatedMemoryRoot",
            "case": "audited-attempt-05-readproof-01",
            "address": 36493040,
            "captured_before_sequence": 718,
            "width": 8,
            "role": "dt",
        },
    }
    with pytest.raises(CheckerRefused) as caught:
        _require_origin_role(fixture, "time", "xmm0_time")
    assert caught.value.code == "ABI_PROVENANCE"


def test_stale_deleted_sequence_receipt_refuses_before_control_semantics(tmp_path: Path) -> None:
    def mutate(bundle: dict) -> None:
        rows = bundle["rows"]
        rows.pop(106)
        rows[105]["next_pc"] = rows[106]["pc"]
        rows[105]["post"]["gpr"]["rip"] = f"0x{rows[106]['pc']:016x}"
        for index, row in enumerate(rows):
            row["sequence"] = index

    refused = _refusal(_rebuild(tmp_path, mutate))
    assert refused.code == "SEQUENCE_RECEIPT"


def test_fully_remapped_deletion_reaches_control_semantics(tmp_path: Path) -> None:
    def mutate(bundle: dict) -> None:
        rows = bundle["rows"]
        rows.pop(106)
        retained_old_sequences = [row["sequence"] for row in rows]
        mapping = {old_sequence: new_sequence for new_sequence, old_sequence in enumerate(retained_old_sequences)}
        rows[105]["next_pc"] = rows[106]["pc"]
        rows[105]["post"]["gpr"]["rip"] = f"0x{rows[106]['pc']:016x}"
        _remap_declared_receipts(bundle, mapping)
        for index, row in enumerate(rows):
            row["sequence"] = index
        _repair_count_receipts(bundle)
        assert bundle["transition"]["readproof"]["rows"] == 727
        assert bundle["capture"]["second_step_entry"]["argument_sources"]["t"]["instruction_sequence"] == 717
        assert bundle["transition"]["readproof"]["final_abi_source_observations"][-1]["sequence"] == 726
        assert bundle["transition"]["bindings"]["gradient"]["write_sequences"] == [713, 714]

    refused = _refusal(_rebuild(tmp_path, mutate))
    assert refused.code == "TRACE_CONTROL_TARGET"


def test_fully_remapped_reorder_reaches_control_semantics(tmp_path: Path) -> None:
    def mutate(bundle: dict) -> None:
        rows = bundle["rows"]
        rows[104], rows[105] = rows[105], rows[104]
        retained_old_sequences = [row["sequence"] for row in rows]
        mapping = {old_sequence: new_sequence for new_sequence, old_sequence in enumerate(retained_old_sequences)}
        rows[103]["next_pc"] = rows[104]["pc"]
        rows[103]["post"]["gpr"]["rip"] = f"0x{rows[104]['pc']:016x}"
        rows[104]["pre"] = copy.deepcopy(rows[103]["post"])
        rows[104]["next_pc"] = rows[105]["pc"]
        rows[104]["post"]["gpr"]["rip"] = f"0x{rows[105]['pc']:016x}"
        rows[105]["pre"] = copy.deepcopy(rows[104]["post"])
        rows[105]["next_pc"] = rows[106]["pc"]
        rows[105]["post"] = copy.deepcopy(rows[106]["pre"])
        _remap_declared_receipts(bundle, mapping)
        for index, row in enumerate(rows):
            row["sequence"] = index
        _repair_count_receipts(bundle)
        assert bundle["transition"]["readproof"]["rows"] == 728
        assert bundle["capture"]["second_step_entry"]["argument_sources"]["t"]["instruction_sequence"] == 718
        assert bundle["transition"]["readproof"]["final_abi_source_observations"][-1]["sequence"] == 727

    refused = _refusal(_rebuild(tmp_path, mutate))
    assert refused.code == "TRACE_CONTROL_TARGET"


def test_fix2_evidence_saves_generator_and_actual_mutated_inputs() -> None:
    evidence = ROOT / "runtime_trace" / "caller_transition" / "artifacts" / "checker" / "fix-round2" / "mutations"
    manifest = json.loads((evidence / "manifest.json").read_text())
    assert manifest["all_refused"] is True
    assert [item["code"] for item in manifest["cases"]] == [
        "REGISTER_SEMANTICS",
        "SEQUENCE_RECEIPT",
        "TRACE_CONTROL_TARGET",
        "SEQUENCE_RECEIPT",
        "TRACE_CONTROL_TARGET",
        "ABI_PROVENANCE",
    ]
    generator = ROOT / "runtime_trace" / "caller_transition" / "generate_checker_fix2_mutations.py"
    assert hashlib.sha256(generator.read_bytes()).hexdigest() == manifest["generator_sha256"]
    for item in manifest["cases"]:
        case_dir = evidence / "cases" / item["name"]
        result_path = case_dir / "result.json"
        receipt_path = case_dir / "mutation-receipt.json"
        assert hashlib.sha256(result_path.read_bytes()).hexdigest() == item["result_sha256"]
        assert hashlib.sha256(receipt_path.read_bytes()).hexdigest() == item["receipt_sha256"]
        result = json.loads(result_path.read_text())
        assert result["verdict"] == "REFUSED"
        for relative, digest in result["actual_input_hashes"].items():
            path = case_dir / relative
            assert path.is_file()
            assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
        if item["trust_mode"] == "TEST_ONLY_REPIN":
            assert (case_dir / "input" / "raw" / "caller_trace.jsonl").is_file()
            assert (case_dir / "input" / "transition.json").is_file()
        else:
            assert (case_dir / "input" / "fixture.json").is_file()
