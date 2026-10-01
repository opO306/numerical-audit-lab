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


# --- benchmark 3: frozen GenDot fixture --------------------------------------

from benchmarks.gate0 import gendot  # noqa: E402
from benchmarks.gate0 import gendot_generate  # noqa: E402


def test_gendot_fixture_is_frozen_and_never_regenerated(monkeypatch, capsys):
    assert gendot.load()["parameters"] == {"n": 50, "c": "1e25", "seed": 20261001, "prng": "Python random.Random (MT19937)"}
    assert gendot_generate.main() == 1                          # refuses: the fixture exists
    assert "frozen" in capsys.readouterr().out


def test_gendot_two_exact_paths_agree_and_audit_the_generator(oracles):
    assert gendot.exact_fraction() == gendot.exact_integer()
    o = gendot.exact_integer()
    assert judge_claim(o, B64, gendot.load()["generator_d_bits"])[0] is Verdict.VALID
    assert 10**26 < gendot.condition_number() < 10**27


def test_gendot_naive_loop_fails_and_matches_the_host_cpu():
    o = gendot.exact_integer()
    run = execute(gendot.program("naive"), B64, gendot.OUT)
    assert audit_steps(B64, run.steps) == []
    assert judge_claim(o, B64, run.final)[0] is Verdict.INVALID
    assert run.final == gendot.hardware_naive_bits()


def test_gendot_vm_dot_is_correctly_rounded_by_specification():
    o = gendot.exact_integer()
    run = execute(gendot.program("vm_dot"), B64, gendot.OUT)
    assert audit_steps(B64, run.steps) == []
    assert judge_claim(o, B64, run.final)[0] is Verdict.VALID
