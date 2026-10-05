"""Whole closed interval containment, with signed96 asymmetric overflow."""
from dataclasses import dataclass
from fractions import Fraction as Q

MIN_RAW = -(1 << 95)
MAX_RAW = (1 << 95) - 1


@dataclass(frozen=True)
class Decision:
    raw: int | None
    reason: str | None


def nearest_even(q,c=None):
    floor, rem = divmod(q.numerator, q.denominator) if c is None else c.divmod(q.numerator,q.denominator)
    twice = 2 * rem if c is None else c.multiply(2,rem)
    def increment(value):
        return value + 1 if c is None else c.add(value,1)
    if twice < q.denominator:
        return floor
    if twice > q.denominator:
        return increment(floor)
    return floor if floor % 2 == 0 else increment(floor)


def decide_scaled(y,c=None):
    c=c or y.account
    def compare(a,b):return (a>b)-(a<b) if c is None else c.compare(a,b)
    def add(a,b):return a+b if c is None else c.qadd(a,b)
    lower=add(Q(MIN_RAW),Q(-1,2));upper=add(Q(MAX_RAW),Q(1,2))
    if compare(y.hi,lower)<0 or compare(y.lo,upper)>=0:
        return Decision(None, 'RAW_UNREPRESENTABLE')
    # Endpoint only proposes a cell; both endpoints must independently fit.
    m = nearest_even(y.lo,c)
    left, right = add(Q(m),Q(-1,2)), add(Q(m),Q(1,2))
    fits = compare(left,y.lo)<=0 and compare(y.hi,right)<=0 if m % 2 == 0 else compare(left,y.lo)<0 and compare(y.hi,right)<0
    if not fits:
        return Decision(None, 'ROUNDING_UNPROVED')
    if m < MIN_RAW or m > MAX_RAW:
        return Decision(None, 'RAW_UNREPRESENTABLE')
    if -m < MIN_RAW or -m > MAX_RAW:
        return Decision(None, 'OPPOSITE_RAW_UNREPRESENTABLE')
    return Decision(m, None)
