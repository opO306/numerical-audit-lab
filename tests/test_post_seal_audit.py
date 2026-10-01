"""Regression record for the post-seal change of the oracle cross-check tolerance.
docs/AUDIT_POST_SEAL_ORACLE_TOLERANCE.md explains each assertion."""
from fractions import Fraction

import mpmath
import pytest

from benchmarks.gate0 import muller, rump
from lab.claim import MIN_AGREE_DIGITS, agree_digits, settle_oracle
from lab.verdict import Refused

ORIGINAL_DIGITS = 200
ORIGINAL_BITS = int(ORIGINAL_DIGITS * 3.33) + 20          # 686, what the first implementation computed with
ORIGINAL_AGREE = ORIGINAL_DIGITS - 10                     # the first implementation's rule


def _muller_exact():
    return {"closed_form": muller.closed_form(), "direct_rational": muller.exact_iteration()[muller.N]}


def _nudge(angle, rel):
    name, val, agree = angle
    with mpmath.workdps(agree + 60):
        return (name, val * (1 + rel), agree)


def test_original_rule_really_refused_a_correct_muller_oracle():
    """The REFUSED that started the change, reproduced: the run was right, the rule was wrong."""
    hp = muller.mp_iteration(ORIGINAL_BITS)[muller.N]
    with pytest.raises(Refused):
        settle_oracle(_muller_exact(), ("mpmath_200_digits", hp, ORIGINAL_AGREE))


def test_measured_loss_matches_the_declared_derivation():
    """|error| / u grows like 20^n; the declared loss must cover it."""
    hp = muller.mp_iteration(ORIGINAL_BITS)[muller.N]
    t = muller.closed_form()
    with mpmath.workdps(800):
        loss = mpmath.log10(abs(hp - mpmath.mpf(t.numerator) / t.denominator) / mpmath.mpf(2) ** -ORIGINAL_BITS)
    assert 37 < loss < muller.DECLARED_LOSS_DIGITS <= 30 * mpmath.log10(20) + 1


def test_rump_tolerance_is_unchanged_from_the_original_rule():
    assert rump.oracle_inputs()[1][2] == ORIGINAL_AGREE


def test_new_muller_window_is_inside_the_original_window():
    """No value the original rule would have rejected is accepted now: 1e-350 is tighter than 1e-190."""
    assert muller.oracle_inputs()[1][2] == agree_digits(400, 40) == 350 > ORIGINAL_AGREE


@pytest.mark.parametrize("rel", ["1e-200", "1e-300", "1e-345"])
def test_wrong_values_the_original_window_would_have_passed_are_now_refused(rel):
    exact, angle = muller.oracle_inputs()
    with pytest.raises(Refused):
        settle_oracle(exact, _nudge(angle, mpmath.mpf(rel)))


def test_tolerance_boundary_is_where_the_formula_puts_it():
    exact, angle = muller.oracle_inputs()
    settle_oracle(exact, _nudge(angle, mpmath.mpf("1e-360")))         # inside 1e-350: accepted
    with pytest.raises(Refused):
        settle_oracle(exact, _nudge(angle, mpmath.mpf("1e-349")))     # outside: refused


def test_floor_blocks_fixing_a_refusal_by_declaring_a_huge_loss():
    hp = muller.mp_iteration(ORIGINAL_BITS)[muller.N]
    loose = agree_digits(ORIGINAL_DIGITS, 95)
    assert loose < MIN_AGREE_DIGITS
    with pytest.raises(Refused, match="floor"):
        settle_oracle(_muller_exact(), ("mpmath_200_digits", hp, loose))


def test_the_tolerance_never_moves_the_oracle_value():
    exact, angle = muller.oracle_inputs()
    assert settle_oracle(exact, angle).value == Fraction(3**31 + 5**31, 3**30 + 5**30)


# --- final confirmation: the numbers in the audit table, pinned ----------------

def _numbers(digits: int, agree: int) -> dict:
    bits = int(digits * 3.33) + 20
    hp = muller.mp_iteration(bits)[muller.N]
    t = muller.closed_form()
    with mpmath.workdps(900):
        T = mpmath.mpf(t.numerator) / t.denominator
        err = abs(mpmath.mpf(hp) - T)
        tol = mpmath.mpf(10) ** (-agree) * max(abs(T), 1)
        return {"bits": bits, "available": float(bits * mpmath.log10(2)), "err": err, "tol": tol,
                "loss": float(mpmath.log10(err / mpmath.mpf(2) ** -bits)), "kept": float(-mpmath.log10(err / abs(T)))}


def test_audit_table_before_change():
    n = _numbers(200, ORIGINAL_AGREE)
    assert n["bits"] == 686 and 206.5 < n["available"] < 206.6
    assert mpmath.mpf("3.70e-169") < n["err"] < mpmath.mpf("3.72e-169")
    assert mpmath.mpf("4.99e-190") < n["tol"] < mpmath.mpf("5.01e-190")
    assert 38.0 < n["loss"] < 38.2                                   # implicit allowance was only 10
    assert 169.0 < n["kept"] < 169.2 < 190                           # kept < required  ->  REFUSED
    assert n["err"] / n["tol"] > mpmath.mpf("7e20")


def test_audit_table_after_change():
    agree = muller.oracle_inputs()[1][2]
    n = _numbers(400, agree)
    assert agree == 350 and n["bits"] == 1352 and 406.9 < n["available"] < 407.1
    assert mpmath.mpf("2.84e-370") < n["err"] < mpmath.mpf("2.86e-370")
    assert mpmath.mpf("4.99e-350") < n["tol"] < mpmath.mpf("5.01e-350")
    assert 37.4 < n["loss"] < 37.5 < muller.DECLARED_LOSS_DIGITS
    assert 350 < 370.2 < n["kept"] < 370.3                           # kept >= required  ->  passes
    assert n["err"] / n["tol"] < mpmath.mpf("6e-21")


def test_available_minus_loss_explains_kept_digits():
    """kept ~= available - loss (+ log10|x30| ~ 0.7, since tolerance is relative to |x30| ~ 5)."""
    for digits, agree in ((200, ORIGINAL_AGREE), (400, 350)):
        n = _numbers(digits, agree)
        assert abs(n["kept"] - (n["available"] - n["loss"] + 0.699)) < 0.01
