from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from runtime_trace.caller_transition.checker import (
    CheckerRefused,
    check_transition,
    derive_possible_write_effects,
)


ROOT = Path(__file__).resolve().parents[3]
CALLER = ROOT / "runtime_trace" / "caller_transition"

CASES = (
    ("audited-attempt-05-readproof-01", "attempt-05"),
    ("fresh-closure-fresh-01-readproof-01", "closure-fresh-01"),
)


def _paths(case: str) -> tuple[Path, Path]:
    return (
        CALLER / "artifacts" / case,
        CALLER / "artifacts" / "producer-fix-round2" / case / "transition.json",
    )


@pytest.mark.parametrize(("case", "label"), CASES)
def test_checker_accepts_controlled_stop_and_reports_independently_derived_counts(
    case: str, label: str
) -> None:
    capture_dir, transition = _paths(case)

    report = check_transition(capture_dir, transition, root=ROOT)

    assert report["verdict"] == "CHECKER_PASS"
    assert report["antecedent_label"] == label
    assert report["record_count"] == 728
    assert report["possible_write_count"] == 111
    assert report["same_value_write_count"] == 21
    assert report["pre_memory_observation_count"] == 219
    assert report["indirect_control_count"] == 16
    assert report["return_count"] == 23
    assert report["carry_binding_count"] == 6
    assert report["gradient_zero_coverage_bytes"] == 16
    assert report["second_step_body_instructions_executed"] == 0
    assert report["conditional_on_external_form_audit"] is True
    assert report["external_audit_performed_by_checker"] is False


def test_two_accepted_cases_are_distinct_process_acquisitions() -> None:
    reports = [check_transition(*_paths(case), root=ROOT) for case, _ in CASES]

    assert reports[0]["inferior_pid"] != reports[1]["inferior_pid"]
    assert reports[0]["capture_sha256"] != reports[1]["capture_sha256"]
    assert reports[0]["trace_sha256"] != reports[1]["trace_sha256"]
    assert reports[0]["machine_scope"] == reports[1]["machine_scope"]
    assert reports[0]["process_independence_only"] is True
    assert reports[1]["process_independence_only"] is True


def test_unknown_antecedent_is_refused_before_semantic_binding(tmp_path: Path) -> None:
    capture_dir, transition_path = _paths("audited-attempt-05-readproof-01")
    transition = json.loads(transition_path.read_text(encoding="utf-8"))
    transition["antecedent"]["label"] = "unknown-case"
    transition["antecedent"]["capture_label"] = "unknown-case"
    transition["antecedent"]["requested_label_matches_capture"] = True
    mutated = tmp_path / "transition.json"
    mutated.write_text(json.dumps(transition), encoding="utf-8")

    with pytest.raises(CheckerRefused) as caught:
        check_transition(capture_dir, mutated, root=ROOT)

    assert caught.value.code == "TRUST_PATH"


def test_unknown_memory_effect_refuses_closed() -> None:
    row = {
        "sequence": 9,
        "pc": 0x1000,
        "instruction_bytes": "48ab",
        "pre": {"gpr": {"rax": "0x0000000000000001", "rdi": "0x2000", "rsp": "0x3000"}},
        "post": {"gpr": {"rax": "0x0000000000000001", "rdi": "0x2008", "rsp": "0x3000"}},
    }

    with pytest.raises(CheckerRefused) as caught:
        derive_possible_write_effects(row, "stosq  %rax,(%rdi)")

    assert caught.value.code == "UNKNOWN_INSTRUCTION_EFFECT"


def test_old_v1_case_is_refused_as_superseded() -> None:
    capture = CALLER / "artifacts" / "audited-attempt-05"
    transition = CALLER / "artifacts" / "producer-fix-round1" / "audited-attempt-05" / "transition.json"

    with pytest.raises(CheckerRefused) as caught:
        check_transition(capture, transition, root=ROOT)

    assert caught.value.code == "SUPERSEDED_EVIDENCE"
