"""QDIV-SIGN exact declared-work boundaries; author regressions only."""
from fractions import Fraction as Q

import pytest

from independent_checker.c1b1.impulse.resource import ResourceAccount, ResourceLimit


def account(cap):
    return ResourceAccount(bit_max=100000, num_bit_max=100000,
                           den_bit_max=100000, work_max=cap)


@pytest.mark.parametrize('divisor', [Q(1), Q(-1)])
@pytest.mark.parametrize('cap', [40, 43])
def test_qdiv_sign_refuses_under_complete_cost(divisor, cap):
    c = account(cap)
    with pytest.raises(ResourceLimit) as err:
        c.qdiv(Q(1), divisor)
    assert err.value.kind == 'WORK'
    # All three 4-unit products precede the 32-unit normalization.
    assert (c.work, c.operations) == (12, 3)


@pytest.mark.parametrize('divisor,expected', [(Q(1), Q(1)), (Q(-1), Q(-1))])
def test_qdiv_sign_at_exact_cost(divisor, expected):
    c = account(44)
    assert c.qdiv(Q(1), divisor) == expected
    assert (c.work, c.operations) == (44, 4)


def test_qdiv_zero_divisor_does_not_start_arithmetic():
    c = account(44)
    with pytest.raises(ValueError):
        c.qdiv(Q(1), Q(0))
    assert c.work == c.operations == 0


@pytest.mark.parametrize('a,b,expected', [
    (Q(0), Q(-3, 7), Q(0)),
    (Q(7, 3), Q(-5, 2), Q(-14, 15)),
    (Q(-7, 3), Q(-5, 2), Q(14, 15)),
    (Q(-7, 3), Q(5, 2), Q(-14, 15)),
])
def test_qdiv_exact_signed_rational_meaning(a, b, expected):
    assert account(10**9).qdiv(a, b) == expected
