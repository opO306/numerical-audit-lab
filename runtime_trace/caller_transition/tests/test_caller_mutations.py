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
from runtime_trace.caller_transition.tests.test_caller_fix1_mutations import _rebuild


ROOT = Path(__file__).resolve().parents[3]
CALLER = ROOT / "runtime_trace" / "caller_transition"
CASE = "audited-attempt-05-readproof-01"
BASE_CAPTURE = CALLER / "artifacts" / CASE
BASE_TRANSITION = (
    CALLER
    / "artifacts"
    / "producer-fix-round2"
    / CASE
    / "transition.json"
)


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _transition_case(
    tmp_path: Path, mutate: Callable[[dict], None]
) -> tuple[Path, Path, object]:
    transition = json.loads(BASE_TRANSITION.read_text(encoding="utf-8"))
    mutate(transition)
    path = tmp_path / "transition.json"
    path.write_bytes(_canonical(transition))
    pins = replace(_PRODUCTION_CASE_PINS[CASE], transition_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    return BASE_CAPTURE, path, pins


def _raw_case(
    tmp_path: Path, mutate: Callable[[list[dict]], None]
) -> tuple[Path, Path, object]:
    return _rebuild(tmp_path, lambda bundle: mutate(bundle["rows"]))


def _assert_refused(
    paths: tuple, expected_codes: set[str]
) -> CheckerRefused:
    with pytest.raises(CheckerRefused) as caught:
        if len(paths) == 3:
            _check_bundle_with_pins(*paths, root=ROOT)
        else:
            check_transition(*paths, root=ROOT)
    assert caught.value.code in expected_codes
    return caught.value


def test_component_bits_changed_is_refused(tmp_path: Path) -> None:
    paths = _transition_case(
        tmp_path,
        lambda t: t["bindings"]["carry"][0].__setitem__(
            "center_bits", "0x3f70000000000001"
        ),
    )
    _assert_refused(paths, {"CARRY_BINDING"})


def test_same_bits_wrong_dynamic_id_is_refused(tmp_path: Path) -> None:
    def mutate(t: dict) -> None:
        lane = t["bindings"]["carry"][0]
        lane["endpoint_memory_value_id"] = lane["copy_source_value_id"]

    _assert_refused(_transition_case(tmp_path, mutate), {"CARRY_BINDING"})


def test_component_swap_is_refused(tmp_path: Path) -> None:
    def mutate(t: dict) -> None:
        carry = t["bindings"]["carry"]
        carry[0], carry[1] = carry[1], carry[0]

    _assert_refused(_transition_case(tmp_path, mutate), {"CARRY_SET"})


def test_component_omission_is_refused(tmp_path: Path) -> None:
    _assert_refused(
        _transition_case(tmp_path, lambda t: t["bindings"]["carry"].pop()),
        {"CARRY_SET"},
    )


def test_component_duplication_is_refused(tmp_path: Path) -> None:
    def mutate(t: dict) -> None:
        t["bindings"]["carry"].append(copy.deepcopy(t["bindings"]["carry"][0]))

    _assert_refused(_transition_case(tmp_path, mutate), {"CARRY_SET"})


def test_stale_previous_endpoint_is_refused(tmp_path: Path) -> None:
    def mutate(t: dict) -> None:
        t["bindings"]["carry"][2]["endpoint_memory_value_id"] = (
            "v:boundary:step:full_v"
        )

    _assert_refused(_transition_case(tmp_path, mutate), {"CARRY_BINDING"})


def test_other_acquisition_boundary_is_refused() -> None:
    fresh_transition = (
        CALLER
        / "artifacts"
        / "producer-fix-round2"
        / "fresh-closure-fresh-01-readproof-01"
        / "transition.json"
    )
    _assert_refused(
        (BASE_CAPTURE, fresh_transition),
        {"TRUST_PATH"},
    )


def test_caller_record_deletion_with_repaired_hashes_is_refused(tmp_path: Path) -> None:
    _assert_refused(
        _raw_case(tmp_path, lambda rows: rows.pop(715)),
        {"TRACE_SEQUENCE", "TRACE_FLOW", "CAPTURE_BOUNDARY"},
    )


def test_caller_record_reordering_with_repaired_hashes_is_refused(
    tmp_path: Path,
) -> None:
    def mutate(rows: list[dict]) -> None:
        rows[714], rows[715] = rows[715], rows[714]

    _assert_refused(
        _raw_case(tmp_path, mutate),
        {"TRACE_SEQUENCE", "TRACE_FLOW", "TRACE_STATE_LINK"},
    )


def test_changed_form_only_is_refused(tmp_path: Path) -> None:
    def mutate(t: dict) -> None:
        t["bindings"]["carry"][2]["form"]["box"] = "0x0.0p+0"

    _assert_refused(_transition_case(tmp_path, mutate), {"FORM_BINDING"})


def test_semantic_write_change_with_repaired_hashes_is_refused(tmp_path: Path) -> None:
    def mutate(rows: list[dict]) -> None:
        rows[714]["possible_memory_writes"][0]["after_bits"] = (
            "0x00000000000000000000000000000001"
        )
        rows[714]["possible_memory_writes"][0]["value_changed"] = True

    _assert_refused(_raw_case(tmp_path, mutate), {"WRITE_SET"})


def test_same_value_protected_store_omission_is_refused(tmp_path: Path) -> None:
    def mutate(rows: list[dict]) -> None:
        rows[715]["possible_memory_writes"] = []

    _assert_refused(_raw_case(tmp_path, mutate), {"SEQUENCE_RECEIPT"})


def test_incomplete_gradient_zero_coverage_is_refused(tmp_path: Path) -> None:
    def mutate(rows: list[dict]) -> None:
        write = rows[714]["possible_memory_writes"][0]
        write["size"] = 8
        write["before_bits"] = "0x3f70100000000000"
        write["after_bits"] = "0x0000000000000000"

    _assert_refused(
        _raw_case(tmp_path, mutate), {"WRITE_SET", "GRADIENT_COVERAGE"}
    )


@pytest.mark.parametrize("binding", ["time", "dt"])
def test_wrong_scalar_load_provenance_is_refused(
    tmp_path: Path, binding: str
) -> None:
    def mutate(t: dict) -> None:
        t["bindings"][binding]["actual_source_receipt"][
            "source_memory_address"
        ] += 8

    expected = "TIME_PROVENANCE" if binding == "time" else "DT_PROVENANCE"
    _assert_refused(_transition_case(tmp_path, mutate), {expected})


def test_pointer_identity_receipt_cannot_hide_rebinding(tmp_path: Path) -> None:
    def mutate(t: dict) -> None:
        receipt = t["bindings"]["pointer_identity"]["q"]
        receipt["second_step_address"] += 16
        receipt["same_memory_region"] = True

    _assert_refused(_transition_case(tmp_path, mutate), {"POINTER_IDENTITY"})
