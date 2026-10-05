from fractions import Fraction as Q
from .interval import Interval


def sqrt_enclosure(r2, bits, c):
    if not isinstance(r2, Q) or r2.numerator < 0 or type(bits) is not int or bits < 1:
        raise ValueError('invalid radius request')
    scaled = c.shift(r2.numerator, 2*bits)
    floor, _ = c.divmod(scaled, r2.denominator)
    a = c.isqrt(floor)
    square = c.multiply(a, a)
    exact = c.multiply(square, r2.denominator) == scaled
    denominator = c.shift(1, bits)
    return Interval(c.fraction(a, denominator),
                    c.fraction(a if exact else c.add(a, 1), denominator),c)
