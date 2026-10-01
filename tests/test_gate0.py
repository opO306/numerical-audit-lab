"""Gate 0 benchmarks, checked piece by piece (fast; run_gate0.py builds the full report)."""
from fractions import Fraction

import mpmath
import pytest

from benchmarks.gate0 import muller, rump
from benchmarks.gate0.harness import execute
from lab.claim import Profile, audit_steps, judge_claim, settle_oracle
from lab.verdict import Refused, Verdict

B64, EXACT = Profile("binary64"), Profile("exact")


@pytest.fixture(scope="module")
def oracles():
    return {m.NAME: settle_oracle(*m.oracle_inputs()).value for m in (rump, muller)}


def test_oracles_from_independent_derivations(oracles):
    assert oracles["rump"] == Fraction(-54767, 66192)
    assert oracles["muller"] == muller.closed_form(30)


@pytest.mark.parametrize("variant", ["sequential", "sum"])
def test_rump_every_step_right_final_answer_wrong(oracles, variant):
    run = execute(rump.program(variant), B64, rump.OUT)
    assert audit_steps(B64, run.steps) == []                 # each rounding is correct...
    assert judge_claim(oracles["rump"], B64, run.final)[0] is Verdict.INVALID   # ...the answer is not


def test_muller_binary64_converges_to_the_wrong_fixed_point(oracles):
    run = execute(muller.program(), B64, muller.OUT)
    assert audit_steps(B64, run.steps) == []
    assert run.final == "4059000000000000"                    # binary64 100.0
    assert judge_claim(oracles["muller"], B64, run.final)[0] is Verdict.INVALID


@pytest.mark.parametrize("mod,prog", [(rump, rump.program()), (muller, muller.program())])
def test_exact_profile_reproduces_the_oracle(oracles, mod, prog):
    run = execute(prog, EXACT, mod.OUT)
    assert audit_steps(EXACT, run.steps) == []
    assert judge_claim(oracles[mod.NAME], EXACT, run.final)[0] is Verdict.VALID


def test_halted_run_is_refused_not_failed(oracles):
    run = execute(rump.program(), Profile("fx", 64, 32), rump.OUT)
    assert run.halt is not None and run.final is None
    assert judge_claim(oracles["rump"], Profile("fx", 64, 32), run.final)[0] is Verdict.REFUSED


def test_disagreeing_derivations_are_refused():
    exact, mp = rump.oracle_inputs()
    with pytest.raises(Refused):
        settle_oracle({"literature": exact["literature"], "other": exact["literature"] + Fraction(1, 10**40)}, mp)
    name, val, agree = mp
    with mpmath.workdps(agree + 40):
        with pytest.raises(Refused):
            settle_oracle(exact, (name, val * (1 + mpmath.mpf(10) ** -100), agree))
