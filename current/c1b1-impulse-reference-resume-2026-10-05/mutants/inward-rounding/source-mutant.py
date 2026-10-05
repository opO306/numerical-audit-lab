"""Exact rational interval composition; reversed endpoints are errors."""
from dataclasses import dataclass
from fractions import Fraction as Q


@dataclass(frozen=True)
class Interval:
    lo: Q
    hi: Q

    def __post_init__(self):
        if not isinstance(self.lo, Q) or not isinstance(self.hi, Q):
            raise TypeError('exact Fraction endpoints required')
        if self.lo > self.hi:
            raise ValueError('unordered interval')


def point(q):
    if type(q) is int:
        q = Q(q)
    return Interval(q, q)


def add(a, b, c):
    return Interval(c.qadd(a.lo, b.lo), c.qadd(a.hi, b.hi))


def neg(a):
    return Interval(-a.hi, -a.lo)


def sub(a, b, c):
    return add(a, neg(b), c)


def extrema(values, c):
    lo = hi = values[0]
    for value in values[1:]:
        if c.compare(value, lo) < 0:
            lo = value
        if c.compare(value, hi) > 0:
            hi = value
    return Interval(lo, hi)


def mul(a, b, c):
    return extrema([c.qmul(x, y) for x, y in
                    ((a.lo,b.lo),(a.lo,b.hi),(a.hi,b.lo),(a.hi,b.hi))], c)


def reciprocal(a, c):
    if a.lo <= 0:
        raise ValueError('positive interval required')
    return Interval(c.qdiv(Q(1), a.hi), c.qdiv(Q(1), a.lo))


def power(a, n, c):
    if type(n) is not int:
        raise TypeError('integer exponent required')
    if n < 0:
        return power(reciprocal(a, c), -n, c)
    def scalar(x):
        return c.qpower(x,n)
    left, right = scalar(a.lo), scalar(a.hi)
    if n == 0:
        return point(1)
    if n % 2 == 0 and a.lo <= 0 <= a.hi:
        return Interval(Q(0), max(left, right))
    return extrema([left, right], c)


def widen(a, bits, c):
    scale = c.shift(1, bits)
    def scaled(x):
        return c.divmod(c.multiply(x.numerator, scale), x.denominator)
    lo, lo_rem = scaled(a.lo)
    lo = c.add(lo,int(lo_rem != 0))
    hi, rem = scaled(a.hi)
    return Interval(c.fraction(lo, scale), c.fraction(c.add(hi, int(rem != 0)), scale))
