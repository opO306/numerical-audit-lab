"""Mathematical pre-operation bounds. No allocator/OS approval is implied."""
from fractions import Fraction as Q
from math import isqrt
from dataclasses import dataclass


@dataclass(frozen=True)
class AllocationBasis:
    """Parameterized allocation model; never an approved platform majorant.

    Every operation retains its entire predicted footprint in the live
    ledger, even after Python releases objects. Workspace covers overlapping
    input copies, integer results, division/gcd scratch and Fraction objects.
    The multiplier/layout must be independently validated before activation.
    """
    header_bytes: int
    limb_bytes: int
    limb_bits: int
    workspace_multiplier: int

    def __post_init__(self):
        if any(type(v) is not int or v<=0 for v in vars(self).values()):
            raise ValueError('invalid allocation basis')

    def footprint(self,bits):
        return self.workspace_multiplier*(self.header_bytes+self.limb_bytes*((bits+self.limb_bits-1)//self.limb_bits))


# Bounded author fixture model only. No production instance/OS approval.
AUTHOR_ALLOCATION_BASIS = AllocationBasis(64,4,30,8)


class ResourceLimit(Exception):
    def __init__(self, kind):
        self.kind = kind
        super().__init__(kind)


class ResourceAccount:
    def __init__(self, *, bit_max, num_bit_max, den_bit_max, work_max,
                 allocation_basis=None,temp_max=None,live_max=None):
        if any(type(x) is not int or x <= 0 for x in
               (bit_max, num_bit_max, den_bit_max, work_max)):
            raise ValueError('invalid mathematical limits')
        self.bit_max, self.num_bit_max = bit_max, num_bit_max
        self.den_bit_max, self.work_max = den_bit_max, work_max
        self.work = self.operations = self.peak_integer_bits = 0
        if allocation_basis is not None and (not isinstance(allocation_basis,AllocationBasis) or
                any(type(x) is not int or x<=0 for x in (temp_max,live_max))):
            raise ValueError('allocation limits/basis required together')
        if allocation_basis is None and (temp_max is not None or live_max is not None):
            raise ValueError('allocation basis required')
        self.allocation_basis=allocation_basis
        self.temp_max,self.live_max=temp_max,live_max
        self.predicted_live_bytes=self.peak_temporary_bytes=0

    def pre(self, bits, work):
        if bits > self.bit_max:
            raise ResourceLimit('BIT')
        if work > self.work_max - self.work:
            raise ResourceLimit('WORK')
        predicted=0 if self.allocation_basis is None else self.allocation_basis.footprint(bits)
        if self.allocation_basis is not None:
            if predicted>self.temp_max:raise ResourceLimit('TEMP_ALLOCATION')
            if predicted>self.live_max-self.predicted_live_bytes:raise ResourceLimit('LIVE_ALLOCATION')
        self.predicted_live_bytes+=predicted
        self.peak_temporary_bytes=max(predicted,self.peak_temporary_bytes)
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

    def qneg(self,a):
        return self.fraction(self.multiply(a.numerator,-1),a.denominator)

    def qmul(self, a, b):
        return self.fraction(self.multiply(a.numerator, b.numerator),
                             self.multiply(a.denominator, b.denominator))

    def qdiv(self, a, b):
        if b.numerator == 0:
            raise ValueError('zero divisor')
        sign = 1 if b.numerator > 0 else -1
        numerator = self.multiply(a.numerator, b.denominator)
        numerator = numerator * sign
        denominator = self.multiply(a.denominator, abs(b.numerator))
        return self.fraction(numerator, denominator)

    def qpower(self, a, n):
        if type(n) is not int or n<0:raise ValueError('nonnegative exponent required')
        largest=max(abs(a.numerator).bit_length(),a.denominator.bit_length(),1)
        # Inspect the whole uncancelled result before any power/product.
        if n>self.bit_max//largest:raise ResourceLimit('BIT')
        if self.allocation_basis is not None:
            prediction=self.allocation_basis.footprint(max(1,largest*n))
            if prediction>self.temp_max:raise ResourceLimit('TEMP_ALLOCATION')
            if prediction>self.live_max-self.predicted_live_bytes:raise ResourceLimit('LIVE_ALLOCATION')
        result=Q(1)
        for _ in range(n):result=self.qmul(result,a)
        return result

    def compare(self, a, b):
        u = self.multiply(a.numerator, b.denominator)
        v = self.multiply(b.numerator, a.denominator)
        self.pre(max(abs(u).bit_length(), abs(v).bit_length())+1,
                 max(abs(u).bit_length(), abs(v).bit_length())+1)
        return (u > v) - (u < v)
