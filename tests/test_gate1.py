"""Gate 1: the correct program raises no alarm, every check can fire, and the headline facts hold."""
import hashlib

import pytest

import run_gate1
from benchmarks.gate1.collision import B64, EXACT, MUTANTS, run, sut
from benchmarks.gate1.scenarios import SCENARIOS
from lab.claim import audit_steps
from lab.gate1_checks import CHECKS, ORACLE_FREE, reference_com, reference_impulse, run_check
from lab.gate1_state import dot, sub
from lab.independence import ROOT

PREDICTIONS_SHA256 = "3a803a6db1306799e20c52cef02319fa3626195ced40f449489237cb6414ca26"


@pytest.fixture(scope="module")
def det():
    return run_gate1.build()[0]


def test_predictions_file_is_the_sealed_one():
    raw = (ROOT / "benchmarks/gate1/predictions.json").read_bytes().replace(b"\r\n", b"\n")
    assert hashlib.sha256(raw).hexdigest() == PREDICTIONS_SHA256


@pytest.mark.parametrize("sc", list(SCENARIOS))
def test_correct_program_equals_both_independent_references(sc):
    s = SCENARIOS[sc]
    assert run(s, "M0", EXACT)[0] == reference_impulse(s) == reference_com(s)


@pytest.mark.parametrize("sc", list(SCENARIOS))
@pytest.mark.parametrize("check", list(CHECKS))
def test_no_false_alarm_on_the_correct_program(sc, check):
    detected, note = run_check(check, SCENARIOS[sc], sut("M0", EXACT))
    assert detected is False, note


def test_every_check_fires_on_some_bug(det):
    for c in CHECKS:
        assert any(det["matrix"][m][sc][c] for m in MUTANTS if m != "M0" for sc in SCENARIOS), c


def test_headline_results(det):
    assert det["baseline_false_alarms"] == []
    assert det["every_bug_caught_somewhere_by_oracle_free_checks"] is True
    assert det["any_single_oracle_free_check_catches_all_7"] is False
    assert all(len(c) == 2 for c in det["minimal_oracle_free_check_sets_covering_all_7"])
    assert det["bugs_caught_by_each_oracle_free_check (any scenario, of 7)"]["C3"] == 2      # momentum is weak


def test_absolute_coordinate_bug_passes_every_conservation_law(det):
    for sc in SCENARIOS:
        assert not any(det["matrix"]["M5"][sc][c] for c in ("C3", "C4", "C4b"))


def test_why_s1_hides_m4_and_m6_from_the_references(det):
    s = SCENARIOS["S1"]
    assert dot(s.v2, sub(s.r2, s.r1)) == 0                  # v2 . d = 0, so v1.d == (v1 - v2).d on this input
    for m in ("M4", "M6"):
        assert det["equivalent_on_input"][m]["S1"] is True
        assert not det["matrix"][m]["S1"]["C1"] and det["matrix"][m]["S1"]["C5"]


def test_posthoc_control_reference_with_the_same_extra_inputs_catches_what_metamorphic_checks_caught(det):
    ctl = det["POSTHOC_control_C1_on_the_transformed_inputs"]
    for m in MUTANTS[1:]:
        for sc in SCENARIOS:
            if any(det["matrix"][m][sc][c] for c in ORACLE_FREE):
                assert ctl[m][sc], (m, sc)


def test_numeric_layer_sees_rounding_but_not_logic(det):
    n = det["numeric_layer"]
    assert not any(any(v.values()) for v in n["N1_on_logic_bugs"].values())
    assert sum(n["N1_on_R1"].values()) == 5 and n["N1_on_R1"]["S2"] is False


def test_binary64_audit_accepts_every_step_of_the_correct_program():
    for s in SCENARIOS.values():
        assert audit_steps(B64, run(s, "M0", B64)[1].steps) == []


def test_report_is_deterministic():
    assert run_gate1.build()[0] == run_gate1.build()[0]
