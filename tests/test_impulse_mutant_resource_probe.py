"""Small preallocation counterexample: removing a guard cannot exhaust RAM."""
import pytest
from independent_checker.c1b1.impulse.resource import ResourceAccount,ResourceLimit

def test_small_resource_guard():
    c=ResourceAccount(bit_max=32,num_bit_max=32,den_bit_max=32,work_max=10000)
    with pytest.raises(ResourceLimit) as err:c.shift(1,64)
    assert err.value.kind=='BIT' and c.operations==0
