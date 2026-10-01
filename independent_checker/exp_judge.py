"""R1 for EXP: judge a claimed e^x with rigorous interval arithmetic (mpmath.iv).

Independent of a_numeric (no import): the VM encloses e^x with its own integer
Taylor/squaring scheme; this judge asks mpmath's interval exp for an
enclosure [a, b] and checks that the WHOLE enclosure rounds to the claimed
result. If the enclosure still straddles a rounding boundary, precision is
raised; e^x (x != 0 rational) is never exactly on a boundary, so this ends --
a cap turns it into "undecided" instead of a wrong verdict.

mpmath is not treated as the only truth (N5): tests/test_audit_exp_judge.py
first checks the judge against known digits of e, against exp(x)exp(-x) = 1,
and requires it to reject every one-step neighbour of an answer.
"""
from __future__ import annotations

from fractions import Fraction

import mpmath

from .oracle import MAX_MAG, OVERFLOW_AT, SIGN, _interval, value

HALF_MIN_SUBNORMAL = Fraction(1, 2 ** 1075)
B64_OVERFLOW_FROM = Fraction(710)
B64_ZERO_UNTIL = Fraction(-746)


def _exact(raw) -> Fraction:
    """An mpmath raw value (sign, man, exp, bc) as an exact Fraction. Converting through mpmath.mpf
    would ROUND to the global precision -- possibly inward, which an enclosure must never do."""
    sign, man, exp, _ = raw
    if man == 0 and exp != 0:
        raise ValueError("non-finite interval endpoint")
    v = Fraction(man) * Fraction(2) ** exp
    return -v if sign else v


def enclose(x: Fraction, prec: int) -> tuple[Fraction, Fraction]:
    """Rigorous [a, b] containing e^x (x a dyadic rational)."""
    mpmath.iv.prec = prec
    num = mpmath.iv.mpf(x.numerator)          # exact: |numerator| < 2^64 and the denominator is a power of two
    den = mpmath.iv.mpf(x.denominator)
    lo, hi = mpmath.iv.exp(num / den)._mpi_
    return _exact(lo), _exact(hi)


def _b64_verdict(a: Fraction, b: Fraction, result) -> str | None:
    """None = the enclosure proves `result`; 'wrong' = it proves something else; 'straddle' = undecided."""
    if a >= OVERFLOW_AT:
        return None if result == "overflow" else "wrong"
    if b < HALF_MIN_SUBNORMAL:
        return None if result == 0 else "wrong"
    if result == "overflow" or not isinstance(result, int):
        return "wrong" if b < OVERFLOW_AT else "straddle"
    if result >> 63:
        return "wrong"
    m = result & ~SIGN
    if m > MAX_MAG:
        return "wrong"
    lo, hi = _interval(m)
    if m == 0:
        lo, hi = Fraction(0), HALF_MIN_SUBNORMAL
    if lo < a and b < hi:
        return None
    if b <= lo or a >= hi:
        return "wrong"
    return "straddle"


def judge_exp_b64(x_bits: int, result, max_prec: int = 4096) -> str | None:
    """None if `result` (a pattern, or "overflow") is e^x correctly rounded; else a reason."""
    x = value(x_bits)
    if x == 0:
        return None if result == 0x3FF0000000000000 else "exp(0) must be exactly 1"
    # whole ranges (tests prove both with interval exp): e^710 > 2^1024, e^-746 < 2^-1076
    if x >= B64_OVERFLOW_FROM:
        return None if result == "overflow" else "expected overflow"
    if x <= B64_ZERO_UNTIL:
        return None if result == 0 else "expected +0"
    prec = 200
    while prec <= max_prec:
        a, b = enclose(x, prec)
        v = _b64_verdict(a, b, result)
        if v is None:
            return None
        if v == "wrong":
            return "outside the rounding interval"
        prec *= 2
    return "undecided at max precision"


def judge_exp_fx(x_raw: int, result, width: int, frac_bits: int, max_prec: int = 4096) -> str | None:
    """FX(W, F): result is a raw integer or "overflow"."""
    x = Fraction(x_raw, 2 ** frac_bits)
    hi_raw = (1 << (width - 1)) - 1
    if x == 0:
        return None if result == 1 << frac_bits else "exp(0) must be exactly 1"
    # whole ranges, since e > 2 and e^-2 < 1/4: e^x > 2^x >= 2^W beyond every value;
    # e^x < 4^-(F+2) below half a step
    if x >= width:
        return None if result == "overflow" else "expected overflow"
    if x <= -(frac_bits + 2):
        return None if result == 0 else "expected 0"
    prec = 200
    while prec <= max_prec:
        a, b = enclose(x, prec)
        sa, sb = a * 2 ** frac_bits, b * 2 ** frac_bits      # in raw units
        # nearest integer of each end (e^x, x != 0, is never exactly half-way)
        ra = (sa.numerator * 2 // sa.denominator + 1) // 2
        rb = (sb.numerator * 2 // sb.denominator + 1) // 2
        if ra == rb:
            want = "overflow" if ra > hi_raw else ra
            return None if result == want else f"expected {want}"
        prec *= 2
    return "undecided at max precision"


def ulp_position(x_bits: int, prec: int = 200) -> Fraction:
    """Where e^x sits between its two neighbouring binary64 values, as a fraction of the gap
    (0.5 = exactly half-way). Used to FIND hard inputs, not to judge."""
    import math
    a, b = enclose(value(x_bits), prec)
    v = (a + b) / 2
    f = float(v)
    lo = math.nextafter(f, -math.inf) if Fraction(f) > v else f
    hi = math.nextafter(lo, math.inf)
    return (v - Fraction(lo)) / (Fraction(hi) - Fraction(lo))
