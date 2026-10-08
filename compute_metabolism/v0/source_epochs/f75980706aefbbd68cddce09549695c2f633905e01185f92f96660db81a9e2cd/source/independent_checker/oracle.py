"""Exact-rational judge of one correctly rounded result (R1-0).

Shares no code with a_numeric: it never *computes* a rounding. It takes a
claimed result and asks whether the exact mathematical value lies inside the
result's rounding interval -- half the gap to each neighbour, ties allowed only
on an even last bit. Neighbours come from bit-pattern arithmetic on the
magnitude, values from the host's exact float -> Fraction conversion.

For SQRT the exact root is irrational, so the check squares the interval ends
(both are >= 0) and compares with the radicand -- still exact.

Outcomes a checker can demand: a finite result, a signed zero, or an
"overflow" (the exact magnitude reaches 2**1024 - 2**970, the point where
nearest-even leaves the finite binary64 values -- A-Binary64-Finite halts there).
"""
from __future__ import annotations

import struct
from fractions import Fraction

SIGN = 1 << 63
MAX_MAG = 0x7FEFFFFFFFFFFFFF                  # largest finite magnitude pattern
OVERFLOW_AT = Fraction(2) ** 1024 - Fraction(2) ** 970


def to_float(b: int) -> float:
    return struct.unpack("<d", struct.pack("<Q", b))[0]


def to_bits(x: float) -> int:
    return struct.unpack("<Q", struct.pack("<d", x))[0]


def value(b: int) -> Fraction:
    """Exact value of a finite pattern (host float -> Fraction is exact)."""
    if (b >> 52) & 0x7FF == 0x7FF:
        raise ValueError(f"{b:016x} is not finite")
    return Fraction(to_float(b))


def _mag_value(m: int) -> Fraction:
    return value(m)


def _interval(m: int) -> tuple[Fraction, Fraction]:
    """Rounding interval of the magnitude pattern m (0 <= m <= MAX_MAG)."""
    here = _mag_value(m)
    lo = Fraction(0) if m == 0 else (here + _mag_value(m - 1)) / 2
    hi = OVERFLOW_AT if m == MAX_MAG else (here + _mag_value(m + 1)) / 2
    return lo, hi


def expected_kind(exact: Fraction) -> str:
    if exact == 0:
        return "zero"
    return "overflow" if abs(exact) >= OVERFLOW_AT else "finite"


def judge(exact: Fraction, result: int | None) -> str | None:
    """None if `result` (a pattern, or None for an overflow halt) is the correctly
    rounded value of `exact` under nearest-even; otherwise a reason. The sign of an
    exact zero is not judged here (it is a separate rule per operation)."""
    kind = expected_kind(exact)
    if kind == "overflow":
        return None if result is None else "expected overflow halt"
    if result is None:
        return "halted but the exact value is finite"
    if (result >> 52) & 0x7FF == 0x7FF:
        return "non-finite pattern"
    m = result & ~SIGN
    if kind == "zero":
        return None if m == 0 else "exact zero rounded to non-zero"
    if (result >> 63) != (exact < 0):
        return "wrong sign"
    x = abs(exact)
    lo, hi = _interval(m)
    if x < lo or x > hi:
        return "outside the rounding interval"
    if (x == lo and m != 0 or x == hi) and m & 1:
        return "tie not resolved to even"
    return None


def judge_sqrt(radicand: Fraction, result: int | None) -> str | None:
    if radicand < 0:
        return None if result is None else "sqrt of a negative must halt"
    if result is None:
        return "halted on a non-negative radicand"
    if radicand == 0:
        return None if result & ~SIGN == 0 else "sqrt(0) must be zero"
    if result >> 63:
        return "negative root"
    lo, hi = _interval(result)
    if radicand < lo * lo or radicand > hi * hi:
        return "outside the rounding interval"
    if (radicand == lo * lo or radicand == hi * hi) and result & 1:
        return "tie not resolved to even"
    return None


def tie_position(exact: Fraction, result: int | None) -> str:
    """Where the exact value sits relative to the result's interval -- used to prove a
    case family really exercises ties and near-ties (non-vacuity)."""
    if result is None or exact == 0:
        return "other"
    lo, hi = _interval(result & ~SIGN)
    x = abs(exact)
    if x in (lo, hi):
        return "tie"
    width = hi - lo
    if min(x - lo, hi - x) * 2 ** 20 < width:
        return "near_tie"
    return "interior"


# ---------------------------------------------------------------------------
# Fixed point FX(W, F): raw ints v meaning v / 2**F in [-2**(W-1), 2**(W-1) - 1].
# ---------------------------------------------------------------------------

def judge_fx(exact: Fraction, result: int | None, width: int, frac_bits: int) -> str | None:
    scaled = exact * 2 ** frac_bits
    lo, hi = -(1 << (width - 1)), (1 << (width - 1)) - 1
    # nearest-even integer to `scaled`, computed by bracketing (not by a rounding routine)
    fl = scaled.numerator // scaled.denominator
    d = scaled - fl
    candidates = [fl] if d < Fraction(1, 2) else [fl + 1] if d > Fraction(1, 2) else [fl if fl % 2 == 0 else fl + 1]
    want = candidates[0]
    if not lo <= want <= hi:
        return None if result is None else "expected overflow halt"
    if result is None:
        return "halted but the rounded value is in range"
    return None if result == want else f"expected {want}, got {result}"


def judge_fx_sqrt(radicand: Fraction, result: int | None, width: int, frac_bits: int) -> str | None:
    if radicand < 0:
        return None if result is None else "sqrt of a negative must halt"
    if result is None:
        return "halted on a non-negative radicand"
    if result < 0:
        return "negative root"
    lo, hi = Fraction(2 * result - 1, 2 ** (frac_bits + 1)), Fraction(2 * result + 1, 2 ** (frac_bits + 1))
    if result == 0:
        lo = Fraction(0)
    if radicand < lo * lo or radicand > hi * hi:
        return "outside the rounding interval"
    return None
