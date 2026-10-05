"""Positive Taylor reciprocal, range reduction, every-squaring widening."""
from fractions import Fraction as Q
from .interval import Interval, widen, mul
from .resource import ResourceLimit


def exp_enclosure(x, bits, order_max, c):
    if x.lo.numerator < 0 or bits < 8 or type(order_max) is not int or order_max < 0:
        raise ValueError('invalid exponential request')
    if x.lo == x.hi == 0:
        return Interval(Q(1), Q(1)), 0, 0
    ylo, yhi, s = -x.hi, -x.lo, 0
    while c.compare(yhi,Q(1,2)) > 0:
        ylo = c.qdiv(ylo, Q(2)); yhi = c.qdiv(yhi, Q(2)); s += 1
    tolerance = c.fraction(1, c.shift(1, bits))
    slo = shi = tlo = thi = Q(1)
    for n in range(order_max + 1):
        next_lo = c.qdiv(c.qmul(tlo, ylo), Q(n+1))
        next_hi = c.qdiv(c.qmul(thi, yhi), Q(n+1))
        tail_den = c.qadd(Q(1), c.qneg(c.qdiv(yhi, Q(n+2))))
        if tail_den.numerator <= 0:
            raise ValueError('tail denominator is not positive')
        tail = c.qdiv(next_hi, tail_den)
        enclosure = Interval(c.qdiv(Q(1), c.qadd(shi, tail)), c.qdiv(Q(1), slo),c)
        if c.compare(c.qadd(enclosure.hi, c.qneg(enclosure.lo)), tolerance) <= 0:
            break
        slo = c.qadd(slo, next_lo); shi = c.qadd(shi, next_hi)
        tlo, thi = next_lo, next_hi
    else:
        raise ResourceLimit('ORDER')
    enclosure = widen(enclosure, bits, c)
    for _ in range(s):
        enclosure = widen(mul(enclosure, enclosure, c), bits, c)
    return enclosure, n, s
