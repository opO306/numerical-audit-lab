"""R1-0: A-Numeric VM on hard inputs, judged by code that shares nothing with it.

docs/current/A_NUMERIC_EXECUTION_STACK_V1.md 3.8. The earlier VM tests used a
sha256 counter; three rounding defects that live only on rounding boundaries
passed them (M4, M6, M9 below). The judge is itself checked first: it must
accept independent hardware results and reject every one-step neighbour.
"""
from __future__ import annotations

import ast
import math
from collections import Counter
from fractions import Fraction
from math import isqrt
from pathlib import Path

import pytest

import numeric_core.profiles as P
from numeric_core import Binary64Finite, FixedPoint, VMHalt
from independent_checker import (audit_binary64, audit_fx_exhaustive, audit_fx_wide, binary64_cases, exact_of,
                                       judge, judge_sqrt, tie_position)
from independent_checker.audit import check_case
from independent_checker.oracle import SIGN, to_bits, to_float

ROOT = Path(__file__).resolve().parents[1]
CASES = binary64_cases()
SCALAR = [c for c in CASES if c.op in ("add", "sub", "mul", "div", "sqrt")]


class Halting:
    """Executor adapter: a VMHalt becomes its reason string."""

    def __init__(self, profile) -> None:
        self.profile = profile

    def __getattr__(self, name):
        fn = getattr(self.profile, name)

        def call(*args):
            try:
                return fn(*args)
            except VMHalt as halt:
                return halt.reason
        return call


def _hardware(case):
    x = [to_float(b) for b in case.args]
    try:
        r = {"add": lambda: x[0] + x[1], "sub": lambda: x[0] - x[1], "mul": lambda: x[0] * x[1],
             "div": lambda: x[0] / x[1], "sqrt": lambda: math.sqrt(x[0])}[case.op]()
    except OverflowError:
        return "overflow"
    return "overflow" if math.isinf(r) else to_bits(r)


def _vm(case, profile=None):
    ex = Halting(profile or Binary64Finite())
    if case.op == "sum":
        return ex.sum(list(case.args))
    if case.op == "dot":
        return ex.dot(*case.args)
    return getattr(ex, case.op)(*case.args)


# --- the judge is not sacred -------------------------------------------------

def test_audit_imports_neither_the_vm_nor_the_engine() -> None:
    for path in (ROOT / "independent_checker").glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                names = [node.module or ""]
            for n in names:
                assert not n.split(".")[0] in ("a_numeric", "engine", "numeric_core"), (path.name, n)


def test_judge_accepts_every_independent_hardware_result() -> None:
    for case in SCALAR:
        assert check_case(case, _hardware(case)) is None, case


def test_judge_rejects_every_one_step_neighbour() -> None:
    """Includes the tie cases: there the odd neighbour is exactly as close, and only
    the even rule tells them apart."""
    rejected = ties = 0
    for case in SCALAR:
        good = _hardware(case)
        if isinstance(good, str) or good & ~SIGN == 0:
            continue
        exact = exact_of(case)
        ties += case.op != "sqrt" and tie_position(exact, good) == "tie"
        for step in (-1, 1):
            m = (good & ~SIGN) + step
            if 0 <= m <= 0x7FEFFFFFFFFFFFFF:
                bad = (good & SIGN) | m
                problem = judge_sqrt(exact, bad) if case.op == "sqrt" else judge(exact, bad)
                assert problem is not None, (case, hex(bad))
                rejected += 1
    assert rejected > 20000 and ties > 500


def test_cases_really_sit_on_boundaries() -> None:
    """Non-vacuity: exact ties and near-ties per operation, both sides of the overflow edge."""
    pos = Counter()
    for case in CASES:
        if case.op != "sqrt":
            got = _vm(case)
            pos[case.op, tie_position(exact_of(case), None if isinstance(got, str) else got)] += 1
    for op, n in (("add", 200), ("sub", 200), ("mul", 100), ("div", 100)):
        assert pos[op, "tie"] >= n, (op, pos[op, "tie"])
        assert pos[op, "near_tie"] >= n, (op, pos[op, "near_tie"])
    assert pos["sum", "tie"] and pos["dot", "tie"]
    edge = [c for c in CASES if c.family == "edge" and c.op in ("add", "sub", "mul", "div")]
    outcomes = Counter(_vm(c) == "overflow" for c in edge)
    assert outcomes[True] >= 5 and outcomes[False] >= 15


# --- the VM on hard inputs ---------------------------------------------------

def test_vm_binary64_passes_every_hard_case() -> None:
    assert audit_binary64(Halting(Binary64Finite()), CASES) == []


def test_vm_binary64_matches_hardware_on_hard_cases() -> None:
    for case in SCALAR:
        assert _vm(case) == _hardware(case), case


def test_vm_sum_matches_fsum_where_fsum_is_defined() -> None:
    """math.fsum is a third, independent exact-sum algorithm (Shewchuk). It cannot
    judge intermediate overflow (raises) or the zero sign (returns +0), so those
    cases are left to the judge."""
    compared = 0
    for case in (c for c in CASES if c.op == "sum"):
        try:
            want = math.fsum(to_float(b) for b in case.args)
        except OverflowError:
            continue
        if want == 0 or math.isinf(want):
            continue
        assert _vm(case) == to_bits(want), case
        compared += 1
    assert compared >= 12


@pytest.mark.parametrize("width,frac_bits", [(8, 3), (6, 0), (7, 6)])
def test_vm_fixed_point_exhaustive_small_formats(width, frac_bits) -> None:
    assert audit_fx_exhaustive(Halting(FixedPoint(width, frac_bits)), width, frac_bits) == []


def test_vm_fixed_point_wide_ties() -> None:
    assert audit_fx_wide(Halting(FixedPoint(64, 32)), 64, 32) == []


# --- fault injection: defects that live only on boundaries -------------------

_ORIG_ROUND, _ORIG_ENCODE = P._round, P._encode


def _scaled(num, den, shift):
    k = num.bit_length() - den.bit_length()
    if not P._ge_pow2(num, den, k):
        k -= 1
    e = max(k + shift - 52, P._EMIN)
    t = shift - e
    return (num << t, den, e) if t >= 0 else (num, den << -t, e)


def _to_bits_p(num, den, shift, p):
    """nearest-even to p significant bits, no exponent limit (for double-rounding mutants)."""
    k = num.bit_length() - den.bit_length()
    if not P._ge_pow2(num, den, k):
        k -= 1
    e = k + shift - (p - 1)
    num, den = (num << (shift - e), den) if shift >= e else (num, den << (e - shift))
    q, rem = divmod(num, den)
    if 2 * rem > den or (2 * rem == den and q & 1):
        q += 1
    return q, e


def m_ties_away(sign, num, den, shift):
    num, den, e = _scaled(num, den, shift)
    q, rem = divmod(num, den)
    q += 2 * rem >= den
    if q == 1 << 53:
        q, e = P._MANT, e + 1
    return _ORIG_ENCODE(sign, q, e)


def m_truncate(sign, num, den, shift):
    num, den, e = _scaled(num, den, shift)
    return _ORIG_ENCODE(sign, num // den, e)


def m_double_64(sign, num, den, shift):
    q, e = _to_bits_p(num, den, shift, 64)
    return _ORIG_ROUND(sign, q, 1, e)


def m_double_subnormal(sign, num, den, shift):
    q, e = _to_bits_p(num, den, shift, 53)
    return _ORIG_ROUND(sign, q, 1, e)


def m_saturate(sign, q, e):
    try:
        return _ORIG_ENCODE(sign, q, e)
    except VMHalt:
        return (sign << 63) | 0x7FEFFFFFFFFFFFFF


def m_early_overflow(sign, num, den, shift):
    if Fraction(num, den) * Fraction(2) ** shift > Fraction(to_float(0x7FEFFFFFFFFFFFFF)):
        raise VMHalt("overflow")
    return _ORIG_ROUND(sign, num, den, shift)


def m_sqrt_no_sticky(self, a):
    sa, ma, ea = P._decode(a)
    if ma == 0:
        return a
    if sa:
        raise VMHalt("sqrt_of_negative")
    if ea & 1:
        ma, ea = ma << 1, ea - 1
    p = max(0, (111 - ma.bit_length()) // 2)
    return P._round(0, 2 * isqrt(ma << (2 * p)), 2, ea // 2 - p)


def m_fx_ties_away(x, shift):
    if shift == 0:
        return x
    q = x >> shift
    return q + (x - (q << shift) >= 1 << (shift - 1))


def m_fx_div_ties_toward_zero(num, den):
    sign = -1 if (num < 0) != (den < 0) else 1
    q, r = divmod(abs(num), abs(den))
    return sign * (q + (2 * r > abs(den)))


def m_fx_mul_floor(self, a, b):
    return self._check((a * b) >> self.frac_bits)


MUTANTS = {
    # name: (patch target, replacement, missed by the sha256 tests of tests/test_a_numeric_vm.py?)
    "M1 binary64 ties away from zero": ((P, "_round"), m_ties_away, False),
    "M2 binary64 truncation": ((P, "_round"), m_truncate, False),
    "M3 double rounding through 64 bits": ((P, "_round"), m_double_64, False),
    "M4 subnormal double rounding": ((P, "_round"), m_double_subnormal, True),
    "M5 overflow saturates to MAX": ((P, "_encode"), m_saturate, False),
    "M6 overflow decided before rounding": ((P, "_round"), m_early_overflow, True),
    "M7 sqrt without sticky bit": ((P.Binary64Finite, "sqrt"), m_sqrt_no_sticky, False),
    "M8 FX ties away from zero": ((P, "_round_shift"), m_fx_ties_away, False),
    "M9 FX DIV ties toward zero": ((P, "_div_round"), m_fx_div_ties_toward_zero, True),
    "M10 FX MUL floor": ((P.FixedPoint, "mul"), m_fx_mul_floor, False),
}


@pytest.mark.parametrize("name", sorted(MUTANTS))
def test_every_injected_rounding_defect_is_caught(name, monkeypatch) -> None:
    (obj, attr), fn, _ = MUTANTS[name]
    monkeypatch.setattr(obj, attr, fn)
    found = len(audit_binary64(Halting(Binary64Finite()), CASES))
    found += len(audit_fx_exhaustive(Halting(FixedPoint(8, 3)), 8, 3))
    found += len(audit_fx_wide(Halting(FixedPoint(64, 32)), 64, 32))
    assert found > 0, name
