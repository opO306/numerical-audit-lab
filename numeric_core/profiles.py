"""Number profiles of the A-Numeric VM (docs/current/A_NUMERIC_EXECUTION_STACK_V1.md, 3.2-3.3).

Each profile defines what ADD, MUL, SQRT ... *mean* in A. The implementation
uses only exact Python integers (and Fraction for the EXACT profile): every
operation computes the exact result first and then rounds it by the profile's
rule, so the meaning never depends on the host's floating point, math library
or compiler.

Anything a profile cannot represent halts with a reason (VMHalt) -- there is
no silent overflow, saturation, NaN or infinity.
"""
from __future__ import annotations

from fractions import Fraction
from math import isqrt


class VMHalt(Exception):
    """A canonical halt: the computation left the profile's contract."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class VMRejected(Exception):
    """The one canonical rejection: a program or input is refused BEFORE running,
    so no host-language error (KeyError, assert, ...) can ever stand in for A's meaning."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code


def _as_exact(value) -> Fraction:
    if type(value) is bool or isinstance(value, float):
        raise TypeError("literals must be int, Fraction or 'n/d' strings -- never float or bool")
    if isinstance(value, (int, Fraction)):
        return Fraction(value)
    if isinstance(value, str):
        return Fraction(value)
    raise TypeError(f"unsupported literal {value!r}")


# ---------------------------------------------------------------------------
# FX(W, F): signed W-bit fixed point with F fractional bits.
# ---------------------------------------------------------------------------

def _round_shift(x: int, shift: int) -> int:
    """x / 2**shift rounded to nearest, ties to even (exact for negative x too)."""
    if shift == 0:
        return x
    q = x >> shift                       # floor
    rem = x - (q << shift)               # 0 <= rem < 2**shift
    half = 1 << (shift - 1)
    if rem > half or (rem == half and q & 1):
        q += 1
    return q


def _div_round(num: int, den: int) -> int:
    """num / den rounded to nearest, ties to even."""
    sign = -1 if (num < 0) != (den < 0) else 1
    q, r = divmod(abs(num), abs(den))
    if 2 * r > abs(den) or (2 * r == abs(den) and q & 1):
        q += 1
    return sign * q


class FixedPoint:
    """Values are raw ints v meaning v / 2**F, confined to [-2**(W-1), 2**(W-1) - 1].

    MUL forms the exact 2W-bit product before rounding; DIV and SQRT round the
    exact result to nearest, ties to even. Leaving the range halts.
    """

    capabilities = frozenset({"ADD", "SUB", "MUL", "DIV", "NEG", "ABS", "SQRT", "EXP", "CMP"})

    def __init__(self, width: int, frac_bits: int) -> None:
        if not (2 <= width and 0 <= frac_bits < width):
            raise ValueError("need 0 <= F < W")
        self.width, self.frac_bits = width, frac_bits
        self.lo, self.hi = -(1 << (width - 1)), (1 << (width - 1)) - 1
        self.name = f"FX({width},{frac_bits})"

    def _check(self, v: int) -> int:
        if not self.lo <= v <= self.hi:
            raise VMHalt("overflow")
        return v

    def from_exact(self, value) -> int:
        x = _as_exact(value)
        return self._check(_div_round(x.numerator << self.frac_bits, x.denominator))

    def to_exact(self, v: int) -> Fraction:
        return Fraction(v, 1 << self.frac_bits)

    def add(self, a: int, b: int) -> int:
        return self._check(a + b)

    def sub(self, a: int, b: int) -> int:
        return self._check(a - b)

    def neg(self, a: int) -> int:
        return self._check(-a)

    def abs(self, a: int) -> int:
        return self._check(abs(a))

    def mul(self, a: int, b: int) -> int:
        return self._check(_round_shift(a * b, self.frac_bits))

    def div(self, a: int, b: int) -> int:
        if b == 0:
            raise VMHalt("division_by_zero")
        return self._check(_div_round(a << self.frac_bits, b))

    def sqrt(self, a: int) -> int:
        if a < 0:
            raise VMHalt("sqrt_of_negative")
        n = a << self.frac_bits
        r = isqrt(n)
        if n - r * r > r:                # n > (r + 1/2)**2 - 1/4; no exact ties exist
            r += 1
        return self._check(r)

    def exp(self, a: int) -> int:
        """deterministic_exp_v1: exact e^x rounded once (a_numeric/exp.py)."""
        from .exp import exp_exact_rounded
        return exp_exact_rounded(self, self.to_exact(a))

    def sum(self, values) -> int:
        """Exact integer sum, range-checked once: no intermediate can overflow, so
        the order of the terms cannot matter."""
        return self._check(sum(values))

    def dot(self, xs, ys) -> int:
        """Exact products, exact sum, ONE rounding by 2**F, range-checked once."""
        return self._check(_round_shift(sum(a * b for a, b in zip(xs, ys)), self.frac_bits))

    def cmp(self, a: int, b: int) -> int:
        return (a > b) - (a < b)

    def valid_raw(self, v) -> bool:
        return type(v) is int and self.lo <= v <= self.hi

    def encode(self, v: int) -> str:
        return str(v)


# ---------------------------------------------------------------------------
# A-Binary64-Finite: the finite binary64 values, one correct rounding
# (nearest-even) per operation, no fused operations, subnormals kept. Unlike
# IEEE 754 it never produces NaN or infinity -- it halts instead.
# Values are the raw 64-bit patterns as Python ints.
# ---------------------------------------------------------------------------

_MANT = 1 << 52
_EMIN = -1074                         # exponent of the smallest subnormal's unit


def _decode(bits: int):
    """-> (sign, m, e) with value (-1)**sign * m * 2**e, m >= 0."""
    if not 0 <= bits < 1 << 64:
        raise TypeError("binary64 values are 64-bit patterns")
    sign = bits >> 63
    field = (bits >> 52) & 0x7FF
    frac = bits & (_MANT - 1)
    if field == 0x7FF:
        raise VMHalt("non_finite_value")
    if field == 0:
        return sign, frac, _EMIN
    return sign, frac | _MANT, field - 1075


def _encode(sign: int, q: int, e: int) -> int:
    """value = q * 2**e with q < 2**53 and e >= _EMIN (as produced by _round)."""
    if q >= _MANT:
        field = e + 1075
        if field >= 0x7FF:
            raise VMHalt("overflow")
        return (sign << 63) | (field << 52) | (q - _MANT)
    assert e == _EMIN
    return (sign << 63) | q


def _ge_pow2(num: int, den: int, k: int) -> bool:
    """num/den >= 2**k"""
    return num >= den << k if k >= 0 else num << -k >= den


def _round(sign: int, num: int, den: int, shift: int) -> int:
    """Round the exact positive value num/den * 2**shift to binary64, nearest-even."""
    assert num > 0 and den > 0
    k = num.bit_length() - den.bit_length()
    if not _ge_pow2(num, den, k):
        k -= 1                               # now 2**k <= num/den < 2**(k+1)
    e = max(k + shift - 52, _EMIN)           # unit of the last mantissa bit
    t = shift - e
    if t >= 0:
        num <<= t
    else:
        den <<= -t
    q, rem = divmod(num, den)
    if 2 * rem > den or (2 * rem == den and q & 1):
        q += 1
    if q == 1 << 53:
        q, e = _MANT, e + 1
    return _encode(sign, q, e)


def _signed_zero(sign: int) -> int:
    return sign << 63


def _exact_sum_terms(terms):
    """terms: (sign, m, e). Exact sum, one rounding. Zero-sign rule (order-free):
    an exactly-zero result is -0 only if every term is -0, otherwise +0."""
    emin = min(e for _, _, e in terms)
    s = sum((-1) ** sg * (m << (e - emin)) for sg, m, e in terms)
    if s == 0:
        return _signed_zero(int(all(sg == 1 and m == 0 for sg, m, _ in terms)))
    return _round(int(s < 0), abs(s), 1, emin)


class Binary64Finite:
    capabilities = frozenset({"ADD", "SUB", "MUL", "DIV", "NEG", "ABS", "SQRT", "EXP", "CMP"})
    name = "A-Binary64-Finite"

    def from_exact(self, value) -> int:
        x = _as_exact(value)
        if x == 0:
            return 0
        return _round(int(x < 0), abs(x.numerator), x.denominator, 0)

    def to_exact(self, bits: int) -> Fraction:
        sign, m, e = _decode(bits)
        v = Fraction(m) * (Fraction(2) ** e)
        return -v if sign else v

    def add(self, a: int, b: int) -> int:
        sa, ma, ea = _decode(a)
        sb, mb, eb = _decode(b)
        emin = min(ea, eb)
        s = (-1) ** sa * (ma << (ea - emin)) + (-1) ** sb * (mb << (eb - emin))
        if s == 0:
            # nearest-even: exact zero sum is +0, except (-0) + (-0) = -0
            return _signed_zero(1 if (sa and sb and ma == 0 and mb == 0) else 0)
        return _round(int(s < 0), abs(s), 1, emin)

    def neg(self, a: int) -> int:
        _decode(a)
        return a ^ (1 << 63)

    def sub(self, a: int, b: int) -> int:
        return self.add(a, self.neg(b))

    def abs(self, a: int) -> int:
        _decode(a)
        return a & ~(1 << 63)

    def mul(self, a: int, b: int) -> int:
        sa, ma, ea = _decode(a)
        sb, mb, eb = _decode(b)
        if ma == 0 or mb == 0:
            return _signed_zero(sa ^ sb)
        return _round(sa ^ sb, ma * mb, 1, ea + eb)

    def div(self, a: int, b: int) -> int:
        sa, ma, ea = _decode(a)
        sb, mb, eb = _decode(b)
        if mb == 0:
            raise VMHalt("division_by_zero")
        if ma == 0:
            return _signed_zero(sa ^ sb)
        return _round(sa ^ sb, ma, mb, ea - eb)

    def sqrt(self, a: int) -> int:
        sa, ma, ea = _decode(a)
        if ma == 0:
            return a                          # sqrt(+-0) = +-0
        if sa:
            raise VMHalt("sqrt_of_negative")
        if ea & 1:
            ma, ea = ma << 1, ea - 1
        p = max(0, (111 - ma.bit_length()) // 2)   # r gets >= 55 bits: 53 kept + 2 guard
        n = ma << (2 * p)
        r = isqrt(n)
        sticky = int(r * r != n)
        # true root lies in (r, r + 1) when inexact; r + 1/2 rounds identically because
        # every rounding boundary sits at least 2 bits above r's last bit. With only
        # 2 guard bits the sticky bit decides real cases (tested against hardware).
        return _round(0, 2 * r + sticky, 2, ea // 2 - p)

    def exp(self, a: int) -> int:
        """deterministic_exp_v1: exact e^x rounded once (a_numeric/exp.py)."""
        from .exp import exp_exact_rounded
        return exp_exact_rounded(self, self.to_exact(a))

    def sum(self, values) -> int:
        return _exact_sum_terms([_decode(v) for v in values])

    def dot(self, xs, ys) -> int:
        terms = []
        for a, b in zip(xs, ys):
            sa, ma, ea = _decode(a)
            sb, mb, eb = _decode(b)
            terms.append((sa ^ sb, ma * mb, ea + eb))
        return _exact_sum_terms(terms)

    def cmp(self, a: int, b: int) -> int:
        x, y = self.to_exact(a), self.to_exact(b)
        return (x > y) - (x < y)

    def valid_raw(self, v) -> bool:
        return type(v) is int and 0 <= v < 1 << 64 and (v >> 52) & 0x7FF != 0x7FF

    def encode(self, bits: int) -> str:
        return f"{bits:016x}"


# ---------------------------------------------------------------------------
# EXACT: rationals. Reference only; cannot take square roots.
# ---------------------------------------------------------------------------

class Exact:
    capabilities = frozenset({"ADD", "SUB", "MUL", "DIV", "NEG", "ABS", "CMP"})
    name = "EXACT"

    def from_exact(self, value) -> Fraction:
        return _as_exact(value)

    def to_exact(self, v: Fraction) -> Fraction:
        return v

    def add(self, a, b):
        return a + b

    def sub(self, a, b):
        return a - b

    def neg(self, a):
        return -a

    def abs(self, a):
        return abs(a)

    def mul(self, a, b):
        return a * b

    def div(self, a, b):
        if b == 0:
            raise VMHalt("division_by_zero")
        return a / b

    def sum(self, values):
        return sum(values, Fraction(0))

    def dot(self, xs, ys):
        return sum((a * b for a, b in zip(xs, ys)), Fraction(0))

    def cmp(self, a, b):
        return (a > b) - (a < b)

    def valid_raw(self, v) -> bool:
        return type(v) is Fraction

    def encode(self, v: Fraction) -> str:
        return f"{v.numerator}/{v.denominator}"
