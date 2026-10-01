"""Hard inputs for binary64 and fixed-point arithmetic (R1-0).

The earlier VM checks used a sha256 counter over broad families. Such inputs
almost never sit exactly on, or within a hair of, a rounding boundary, so a
rounding rule that is wrong ONLY there (ties away from zero, double rounding
through a wider format, overflow decided before rounding, ...) passes them.
These cases are built to sit there on purpose:

  * exact ties and near-ties of ADD/SUB/MUL, at every exponent range;
  * quotients and square roots within one or two ulps of a midpoint
    (radicand / dividend = nearest binary64 to midpoint**2 / midpoint*divisor);
  * underflow ties (to zero, and the largest-subnormal / smallest-normal edge);
  * the overflow edge 2**1024 - 2**970 approached from both sides;
  * SUM / DOT cases whose sequential rounding differs from the exact sum;
  * fixed point: exhaustive over a small format, targeted ties in a wide one.

Everything is built from integers and exact Fractions; nothing is random.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from .oracle import MAX_MAG, SIGN, to_bits, value

TWO = Fraction(2)


@dataclass(frozen=True)
class Case:
    op: str          # add sub mul div sqrt sum dot
    args: tuple      # bit patterns; for sum a tuple of patterns, for dot (xs, ys)
    family: str


def exact_bits(x: Fraction) -> int | None:
    """Pattern of x if x is exactly a finite binary64 value, else None."""
    if x == 0:
        return 0
    try:
        f = float(x)                                  # correctly rounded by CPython
    except OverflowError:
        return None
    if Fraction(f) != x:
        return None
    return to_bits(f)


def pow2(e: int) -> int:
    b = exact_bits(TWO ** e)
    assert b is not None, e
    return b


def neg(b: int) -> int:
    return b ^ SIGN


def nudge(b: int, k: int) -> int | None:
    """Pattern k steps away in magnitude (same sign); None if it leaves the finite range."""
    m = (b & ~SIGN) + k
    if not 0 <= m <= MAX_MAG:
        return None
    return (b & SIGN) | m


# 53-bit significands: powers of two, odd/even low bits, all ones, patterns
MANTS = [1 << 52, (1 << 52) + 1, (1 << 52) + 2, (1 << 52) + 3, (1 << 53) - 1, (1 << 53) - 2,
         0x1B6DB6DB6DB6DB, 0x15555555555555, (1 << 52) + (1 << 51) + 1, 0x1FFFFFFFFFFFF0]
NORMAL_FIELDS = [2, 3, 52, 53, 54, 500, 1022, 1023, 1024, 1500, 2044, 2045, 2046]
SMALL_ODD = [3, 5, 7, 9, 15, 17, 255, (1 << 26) + 1, (1 << 52) + 1, (1 << 53) - 1]
MAX = MAX_MAG
MIN_SUB = 1


def _add_cases():
    out = []
    for m in MANTS:
        for field in NORMAL_FIELDS:
            a = (field << 52) | (m - (1 << 52))
            e_half = field - 1076                       # exponent of half an ulp of a
            if e_half < -1074:
                continue
            h = pow2(e_half)
            bs = [h, nudge(h, -1), nudge(h, 1), exact_bits(TWO ** (e_half + 1))]
            if e_half - 1 >= -1074:
                q = pow2(e_half - 1)                    # quarter ulp: tie just below a power of two
                bs += [q, nudge(q, 1), nudge(q, -1)]
            if e_half - 60 >= -1074:
                bs.append(pow2(e_half - 60))            # far below: sticky only
            for b in bs:
                if b is None:
                    continue
                out += [Case("add", (a, b), "add_tie"), Case("sub", (a, b), "add_tie"),
                        Case("add", (neg(a), b), "add_tie"), Case("sub", (neg(a), neg(b)), "add_tie")]
    # subnormal / normal edge, cancellation
    min_normal = pow2(-1022)
    largest_sub = min_normal - 1
    for a, b in [(largest_sub, MIN_SUB), (largest_sub, largest_sub), (min_normal, neg(MIN_SUB)),
                 (min_normal, neg(largest_sub)), (nudge(min_normal, 1), neg(min_normal)),
                 (to_bits(1.0), neg(nudge(to_bits(1.0), -1))), (MAX, neg(nudge(MAX, -1)))]:
        out.append(Case("add", (a, b), "add_edge"))
    return out


def _mul_cases():
    out = []
    for target in [-1080, -1076, -1075, -1074, -1073, -1060, -1030, -1024, -1023, -1022, -1021,
                   -1, 0, 1, 1000, 1021, 1022, 1023]:
        ea = target // 2
        for m in MANTS:
            a = exact_bits(Fraction(m) * TWO ** (ea - 52))
            for k in SMALL_ODD:
                b = exact_bits(Fraction(k) * TWO ** (target - ea - k.bit_length() + 1))
                if a is None or b is None:
                    continue
                out.append(Case("mul", (a, b), "mul_tie"))
                out.append(Case("mul", (neg(a), b), "mul_tie"))
    return out


def _div_cases():
    out = []
    divisors = [Fraction(m) * TWO ** s for m in MANTS[:6] for s in (-52, 0, 40)]
    for e in (-1074, -1060, -1030, -1023, -1022, -1, 0, 1, 1000, 1023):
        for t in MANTS:
            if e < -1022:
                j = t >> (52 - (e + 1074))                              # j * 2**-1074 ~ 2**e
                q_mid = Fraction(2 * j + 1) * TWO ** -1075               # midpoint of the subnormal grid
            else:
                q_mid = Fraction(2 * t + 1) * TWO ** (e - 53)
            for d in divisors:
                db = exact_bits(d)
                try:
                    a0 = float(q_mid * d)
                except OverflowError:
                    continue
                if a0 == 0.0 or db is None:
                    continue
                for k in (-2, -1, 0, 1, 2):
                    a = nudge(to_bits(a0), k)
                    if a is not None:
                        out.append(Case("div", (a, db), "div_near_mid"))
    return out


def _sqrt_cases():
    out = []
    for e in (-537, -536, -530, -520, -511, -1, 0, 1, 510, 511):
        for t in MANTS:
            mid = Fraction(2 * t + 1) * TWO ** (e - 53)
            try:
                x0 = float(mid * mid)
            except OverflowError:
                continue
            if x0 == 0.0:
                continue
            for k in (-3, -2, -1, 0, 1, 2, 3):
                x = nudge(to_bits(x0), k)
                if x is not None:
                    out.append(Case("sqrt", (x,), "sqrt_near_mid"))
    for t in (1, 3, 5, (1 << 26) + 1, (1 << 26) - 1):
        for s in (-1074, -600, -2, 0, 2, 400):
            x = exact_bits(Fraction(t * t) * TWO ** s)
            if x is not None and s % 2 == 0:
                out.append(Case("sqrt", (x,), "sqrt_exact"))
    return out


def _edge_cases():
    one = to_bits(1.0)
    half = to_bits(0.5)
    min_normal = pow2(-1022)
    largest_sub = min_normal - 1
    e970 = pow2(970)
    cases = [
        # underflow ties
        ("mul", MIN_SUB, half), ("mul", MIN_SUB, nudge(half, 1)), ("mul", MIN_SUB, nudge(half, -1)),
        ("mul", 3, half), ("mul", 5, half), ("mul", MIN_SUB, to_bits(0.75)), ("mul", MIN_SUB, to_bits(0.25)),
        ("mul", exact_bits(2 - TWO ** -52), pow2(-1023)),          # (2**53-1)*2**-1075: largest-sub / min-normal tie
        ("mul", exact_bits(2 - TWO ** -51), pow2(-1023)),
        ("mul", nudge(exact_bits(2 - TWO ** -52), -1), pow2(-1023)),
        ("div", MIN_SUB, to_bits(2.0)), ("div", 3, to_bits(2.0)), ("div", MIN_SUB, to_bits(3.0)),
        ("div", min_normal, exact_bits(TWO ** 52 + TWO)), ("div", largest_sub, nudge(one, -1)),
        ("div", min_normal, nudge(one, 1)),
        # overflow edge: exact magnitude 2**1024 - 2**970 is the first that halts
        ("add", MAX, e970), ("add", MAX, nudge(e970, -1)), ("sub", neg(MAX), e970),
        ("sub", neg(MAX), nudge(e970, -1)), ("add", nudge(MAX, -1), e970),
        ("mul", MAX, nudge(one, 1)), ("mul", MAX, one), ("mul", pow2(1023), to_bits(2.0)),
        ("mul", pow2(512), pow2(511)), ("mul", nudge(pow2(512), -1), pow2(512)),
        ("mul", exact_bits(TWO ** 1023 * (2 - TWO ** -52)), nudge(one, 1)),
        ("div", MAX, nudge(one, -1)), ("div", MAX, half), ("div", MAX, one), ("div", pow2(1023), half),
        ("div", nudge(MAX, -1), nudge(one, -1)), ("div", MAX, nudge(one, -2)),
        ("sqrt", MAX), ("sqrt", nudge(MAX, -1)), ("sqrt", MIN_SUB), ("sqrt", 2), ("sqrt", largest_sub),
        ("sqrt", min_normal),
    ]
    out = []
    for op, *args in cases:
        assert all(a is not None for a in args), (op, args)
        out.append(Case(op, tuple(args), "edge"))
    return out


def _sum_cases():
    one, e970 = to_bits(1.0), pow2(970)
    t53, t54, t106 = pow2(-53), pow2(-54), pow2(-106)
    sums = [
        (one, t53), (one, t53, t106), (one, t53, neg(t106)), (one, t54, t54), (one, t54, t54, t54),
        (one,) + (t54,) * 2 + (neg(t106),), (MAX, MAX, neg(MAX)), (MAX, e970), (MAX, e970, neg(MIN_SUB)),
        (MAX, nudge(e970, -1)), (neg(MAX), neg(e970)), (MAX, e970, neg(e970), e970),
        (1 << 63, 1 << 63), (1 << 63, 0), (one, neg(one)), (neg(one), one, 1 << 63),
        (MIN_SUB,) * 3, (pow2(-1022), neg(MIN_SUB)), (to_bits(3.0), t53, neg(to_bits(2.0))),
        tuple(pow2(-k) for k in range(0, 60)), tuple(neg(pow2(-k)) for k in range(0, 60)),
    ]
    out = [Case("sum", s, "sum") for s in sums]
    x = exact_bits(1 + TWO ** -30)
    x2 = exact_bits(1 + TWO ** -29)
    dots = [
        ((x, neg(one)), (x, x2)),                       # exact 2**-60; per-step rounding gives 0
        ((one, pow2(-27)), (one, pow2(-26))),           # 1 + 2**-53: exact tie -> 1
        ((one, pow2(-27), pow2(-60)), (one, pow2(-26), one)),
        ((pow2(1023), pow2(1023), neg(pow2(1023))), (one, one, one)),   # no intermediate overflow
        ((MAX, pow2(485)), (one, pow2(485))),            # MAX + 2**970: overflow edge
        ((to_bits(2.0 ** 53), one, one, to_bits(-(2.0 ** 53))), (one, one, one, one)),
    ]
    out += [Case("dot", d, "dot") for d in dots]
    return out


def binary64_cases() -> list[Case]:
    return _add_cases() + _mul_cases() + _div_cases() + _sqrt_cases() + _edge_cases() + _sum_cases()


def exact_of(case: Case) -> Fraction:
    """The exact mathematical value a case asks for (for SQRT: the radicand)."""
    a = case.args
    if case.op == "add":
        return value(a[0]) + value(a[1])
    if case.op == "sub":
        return value(a[0]) - value(a[1])
    if case.op == "mul":
        return value(a[0]) * value(a[1])
    if case.op == "div":
        return value(a[0]) / value(a[1])
    if case.op == "sqrt":
        return value(a[0])
    if case.op == "sum":
        return sum((value(b) for b in a), Fraction(0))
    if case.op == "dot":
        xs, ys = a
        return sum((value(p) * value(q) for p, q in zip(xs, ys)), Fraction(0))
    raise ValueError(case.op)


# ---------------------------------------------------------------------------
# Fixed point
# ---------------------------------------------------------------------------

def fx_exhaustive_pairs(width: int):
    lo, hi = -(1 << (width - 1)), (1 << (width - 1)) - 1
    for a in range(lo, hi + 1):
        for b in range(lo, hi + 1):
            yield a, b


def fx_wide_ties(width: int, frac_bits: int):
    """(op, a, b) raw pairs whose exact result sits on or next to a half step, and at the range edge."""
    hi = (1 << (width - 1)) - 1
    one = 1 << frac_bits
    out = []
    for k in (1, 3, 5, 7, 2 ** 20 + 1, 2 ** 31 - 1):
        for s in (0, 1, -1):
            # MUL: a * (one/2 + s) ... product low F bits exactly half a step for odd k
            out.append(("mul", k, one // 2 + s))
            out.append(("mul", -k, one // 2 + s))
            # DIV: (k/2**F) / 2 lands on a half step for odd k
            out.append(("div", k + s, 2 * one))
            out.append(("div", -(k + s), 2 * one))
    out += [("mul", hi, one + 1), ("mul", hi, one), ("mul", hi, one - 1), ("div", hi, one - 1), ("div", hi, one + 1),
            ("mul", -hi - 1, one), ("mul", -hi - 1, -one), ("div", -hi - 1, -one), ("div", 1, 3), ("div", -1, 3)]
    return out
