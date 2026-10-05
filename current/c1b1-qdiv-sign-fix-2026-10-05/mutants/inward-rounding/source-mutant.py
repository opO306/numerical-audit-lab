"""Exact rational interval composition; reversed endpoints are errors."""
from dataclasses import dataclass,field
from fractions import Fraction as Q


@dataclass(frozen=True)
class Interval:
    lo: Q
    hi: Q
    account: object=field(default=None,repr=False,compare=False)

    def __post_init__(self):
        if not isinstance(self.lo, Q) or not isinstance(self.hi, Q):
            raise TypeError('exact Fraction endpoints required')
        if self.lo is self.hi:return
        reversed_order=self.account.compare(self.lo,self.hi)>0 if self.account is not None else self.lo>self.hi
        if reversed_order:
            raise ValueError('unordered interval')


def point(q):
    if type(q) is int:
        q = Q(q)
    return Interval(q, q)


def add(a, b, c):
    return Interval(c.qadd(a.lo, b.lo), c.qadd(a.hi, b.hi),c)


def neg(a,c=None):
    c=c or a.account
    if c is None:return Interval(-a.hi,-a.lo)
    return Interval(c.qneg(a.hi),c.qneg(a.lo),c)


def sub(a, b, c):
    return add(a, neg(b,c), c)


def extrema(values, c):
    lo = hi = values[0]
    for value in values[1:]:
        if c.compare(value, lo) < 0:
            lo = value
        if c.compare(value, hi) > 0:
            hi = value
    return Interval(lo, hi,c)


def mul(a, b, c):
    return extrema([c.qmul(x, y) for x, y in
                    ((a.lo,b.lo),(a.lo,b.hi),(a.hi,b.lo),(a.hi,b.hi))], c)


def reciprocal(a, c):
    if c.compare(a.lo,Q(0)) <= 0:
        raise ValueError('positive interval required')
    return Interval(c.qdiv(Q(1), a.hi), c.qdiv(Q(1), a.lo),c)


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
    if n % 2 == 0 and c.compare(a.lo,Q(0))<=0 and c.compare(a.hi,Q(0))>=0:
        return Interval(Q(0),left if c.compare(left,right)>0 else right,c)
    return extrema([left, right], c)


def widen(a, bits, c):
    scale = c.shift(1, bits)
    def scaled(x):
        return c.divmod(c.multiply(x.numerator, scale), x.denominator)
    lo, lo_rem = scaled(a.lo)
    lo = c.add(lo,int(lo_rem != 0))
    hi, rem = scaled(a.hi)
    return Interval(c.fraction(lo, scale), c.fraction(c.add(hi, int(rem != 0)), scale),c)
