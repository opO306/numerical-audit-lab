"""Toy allocation basis tests, not production allocator approval."""
from fractions import Fraction as Q
import pytest
from independent_checker.c1b1.impulse.resource import ResourceAccount,ResourceLimit

def account(**kw):
    from independent_checker.c1b1.impulse.resource import AllocationBasis
    return ResourceAccount(bit_max=10000,num_bit_max=10000,den_bit_max=10000,work_max=10**20,
        allocation_basis=AllocationBasis(64,4,30,8),temp_max=kw.get('temp',10**9),live_max=kw.get('live',10**9))

@pytest.mark.parametrize('kind,limits',[('TEMP_ALLOCATION',{'temp':1}),('LIVE_ALLOCATION',{'live':1})])
def test_allocation_refusal_before_operation(kind,limits):
    c=account(**limits)
    with pytest.raises(ResourceLimit) as err:c.multiply(3,7)
    assert err.value.kind==kind and c.operations==c.work==0

def test_live_accounting_retains_all_results_conservatively():
    c=account();c.multiply(3,7);first=c.predicted_live_bytes;c.multiply(2,11)
    assert c.predicted_live_bytes>first>0 and c.peak_temporary_bytes>0

def test_pow_entire_bound_checked_before_first_product():
    c=account()
    with pytest.raises(ResourceLimit):c.qpower(Q(3,2),10**9)
    assert c.operations==0
