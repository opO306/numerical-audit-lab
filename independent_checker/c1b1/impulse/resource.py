"""Mathematical pre-operation bounds. No allocator/OS approval is implied."""
from fractions import Fraction as Q
from math import isqrt


class ResourceLimit(Exception):
    def __init__(self, kind):
        self.kind = kind
        super().__init__(kind)


class ResourceAccount:
    def __init__(self, *, bit_max, num_bit_max, den_bit_max, work_max):
        if any(type(x) is not int or x <= 0 for x in
               (bit_max, num_bit_max, den_bit_max, work_max)):
            raise ValueError('invalid mathematical limits')
        self.bit_max, self.num_bit_max = bit_max, num_bit_max
        self.den_bit_max, self.work_max = den_bit_max, work_max
        self.work = self.operations = self.peak_integer_bits = 0

    def pre(self, bits, work):
        if bits > self.bit_max:
            raise ResourceLimit('BIT')
        if work > self.work_max - self.work:
            raise ResourceLimit('WORK')
        self.work += work
        self.operations += 1
        self.peak_integer_bits = max(bits, self.peak_integer_bits)

    def add(self, a, b):
        bits = max(abs(a).bit_length(), abs(b).bit_length()) + 1
        self.pre(bits, bits)
        return a + b

    def multiply(self, a, b):
        A, B = abs(a).bit_length(), abs(b).bit_length()
        self.pre(A + B, (A + 1) * (B + 1))
        return a * b

    def shift(self, a, n):
        if type(n) is not int or n < 0:
            raise ValueError('invalid shift')
        bits = abs(a).bit_length() + n + 1
        self.pre(bits, bits)
        return a << n

    def divmod(self, a, b):
        if b <= 0:
            raise ValueError('positive divisor required')
        A, B = abs(a).bit_length(), b.bit_length()
        self.pre(max(A, B) + 1, (A + 1) * (B + 1)**2)
        return divmod(a, b)

    def isqrt(self, a):
        if a < 0:
            raise ValueError('nonnegative radicand required')
        A = a.bit_length()
        self.pre(A + 1, (A + 1)**3)
        return isqrt(a)

    def fraction(self, n, d=1):
        if d <= 0:
            raise ValueError('positive denominator required')
        A, B = abs(n).bit_length(), d.bit_length()
        M = max(A, B)
        self.pre(M + 1, (2*M + 2) * (M + 1)**3)
        result = Q(n, d)
        if abs(result.numerator).bit_length() > self.num_bit_max or result.denominator.bit_length() > self.den_bit_max:
            raise ResourceLimit('RATIONAL_BIT')
        return result

    def qadd(self, a, b):
        n = self.add(self.multiply(a.numerator, b.denominator),
                     self.multiply(b.numerator, a.denominator))
        return self.fraction(n, self.multiply(a.denominator, b.denominator))

    def qmul(self, a, b):
        return self.fraction(self.multiply(a.numerator, b.numerator),
                             self.multiply(a.denominator, b.denominator))

    def qdiv(self, a, b):
        if b == 0:
            raise ValueError('zero divisor')
        sign = 1 if b > 0 else -1
        return self.fraction(self.multiply(a.numerator, b.denominator)*sign,
                             self.multiply(a.denominator, abs(b.numerator)))

    def compare(self, a, b):
        u = self.multiply(a.numerator, b.denominator)
        v = self.multiply(b.numerator, a.denominator)
        self.pre(max(abs(u).bit_length(), abs(v).bit_length())+1,
                 max(abs(u).bit_length(), abs(v).bit_length())+1)
        return (u > v) - (u < v)
