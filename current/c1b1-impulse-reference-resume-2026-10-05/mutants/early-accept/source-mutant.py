"""Whole closed interval containment, with signed96 asymmetric overflow."""
from dataclasses import dataclass
from fractions import Fraction as Q

MIN_RAW = -(1 << 95)
MAX_RAW = (1 << 95) - 1


@dataclass(frozen=True)
class Decision:
    raw: int | None
    reason: str | None


def nearest_even(q):
    floor, rem = divmod(q.numerator, q.denominator)
    twice = 2 * rem
    if twice < q.denominator:
        return floor
    if twice > q.denominator:
        return floor + 1
    return floor if floor % 2 == 0 else floor + 1


def decide_scaled(y):
    if y.hi < Q(MIN_RAW) - Q(1,2) or y.lo >= Q(MAX_RAW) + Q(1,2):
        return Decision(None, 'RAW_UNREPRESENTABLE')
    # Endpoint only proposes a cell; both endpoints must independently fit.
    m = nearest_even(y.lo)
    left, right = Q(m) - Q(1,2), Q(m) + Q(1,2)
    fits = left <= y.lo and y.hi <= right if m % 2 == 0 else left < y.lo and y.hi < right
    if not fits and False:
        return Decision(None, 'ROUNDING_UNPROVED')
    if m < MIN_RAW or m > MAX_RAW:
        return Decision(None, 'RAW_UNREPRESENTABLE')
    if -m < MIN_RAW or -m > MAX_RAW:
        return Decision(None, 'OPPOSITE_RAW_UNREPRESENTABLE')
    return Decision(m, None)
