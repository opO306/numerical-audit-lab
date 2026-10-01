"""EXP in the A-Numeric VM -- deterministic_exp_v1 (A_NUMERIC_EXECUTION_STACK_V1.md 3.9).

Meaning: the EXACT mathematical e^x of the represented input, rounded ONCE by
the profile -- the rule every other instruction follows. It is a value, not an
algorithm: an executor whose bits differ is wrong, however it computes.

Why this is computable exactly: for a rational x != 0, e^x is transcendental
(Lindemann-Weierstrass), while every rounding boundary of every profile is
rational. So e^x never sits ON a boundary, and a rigorous enclosure refined
until both ends round alike always ends. x = 0 gives exactly 1.

The enclosure uses only integers: y = x / 2^k is pushed outward to the grid
2^-M (e^y is increasing), e^y is bracketed by a Taylor sum with floor/ceil
directed terms plus a remainder bound, and k squarings (floor/ceil) give
lo <= e^x 2^M <= hi.
"""
from __future__ import annotations

from fractions import Fraction

from .profiles import VMHalt

# ln 2 = 0.693147... < 0.6932. Used only to decide whole ranges early (a result
# that certainly overflows / certainly rounds to zero). tests check it with the
# enclosure itself: e^0.6932 > 2.
LN2_UPPER = Fraction(6932, 10000)


def _taylor(Y: int, M: int) -> tuple[int, int]:
    """(lo, hi) with lo <= e^(Y/2^M) * 2^M <= hi, for |Y| <= 2^(M-8)."""
    a, neg = abs(Y), Y < 0
    one = 1 << M
    t_lo = t_hi = one                       # |y|^i / i! * 2^M, rounded down / up
    s_lo = s_hi = one
    i = 0
    while True:
        i += 1
        t_lo = (t_lo * a) // (i << M)
        t_hi = -((-t_hi * a) // (i << M))
        if neg and i & 1:
            s_lo, s_hi = s_lo - t_hi, s_hi - t_lo
        else:
            s_lo, s_hi = s_lo + t_lo, s_hi + t_hi
        if t_hi <= 1:
            break
    # |remainder| <= t_i * |y| / (i + 1 - |y|) <= t_i <= t_hi <= 1 (|y| <= 2^-8); margin 2 * t_hi + 2
    r = 2 * t_hi + 2
    return s_lo - r, s_hi + r


def enclosure(x: Fraction, M: int, k: int) -> tuple[int, int]:
    """(lo, hi) with lo <= e^x * 2^M <= hi, using y = x / 2^k and k squarings."""
    num, den = x.numerator, x.denominator << k
    y_lo = (num << M) // den                # floor(y 2^M)
    y_hi = -((-num << M) // den)            # ceil(y 2^M)
    lo, _ = _taylor(y_lo, M)
    _, hi = _taylor(y_hi, M)
    lo = max(lo, 0)
    for _ in range(k):
        lo = (lo * lo) >> M
        hi = -((-hi * hi) >> M)
    return lo, hi


def _round(profile, v: Fraction):
    try:
        return "value", profile.from_exact(v)
    except VMHalt as h:
        return "halt", h.reason


def exp_exact_rounded(profile, x: Fraction):
    """The profile's raw value of e^x rounded once, or VMHalt('overflow')."""
    fx = hasattr(profile, "frac_bits")
    # whole ranges decided early -- rigorous because LN2_UPPER > ln 2
    if fx:
        W, F = profile.width, profile.frac_bits
        if x > (W - F) * LN2_UPPER:          # e^x > 2^(W-F) > largest value
            raise VMHalt("overflow")
        if x < -(F + 2) * LN2_UPPER:         # e^x < 2^-(F+2), below half a step
            return profile.from_exact(0)
        base = F + 16
    else:
        if x > 1024 * LN2_UPPER:             # e^x > 2^1024
            raise VMHalt("overflow")
        if x < -1076 * LN2_UPPER:            # e^x < 2^-1076, below half the smallest subnormal
            return profile.from_exact(0)
        base = 1150
    b = max(0, x.numerator.bit_length() - x.denominator.bit_length() + 1) if x else 0   # |x| < 2^b
    k = b + 8                                                                           # |y| <= 2^-8
    extra = 64
    while True:
        M = base + 2 * k + extra
        lo, hi = enclosure(x, M, k)
        a, b_ = _round(profile, Fraction(lo, 1 << M)), _round(profile, Fraction(hi, 1 << M))
        if a == b_:
            if a[0] == "halt":
                raise VMHalt(a[1])
            return a[1]
        extra *= 2                           # never on a boundary (x != 0), so this ends
