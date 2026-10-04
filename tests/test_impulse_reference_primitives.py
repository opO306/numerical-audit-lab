"""SYNTHETIC PRIMITIVE fixtures: exact inequalities, not physical J evidence."""
from fractions import Fraction as Q
import importlib
import pytest


def module(name):
    try:
        return importlib.import_module('independent_checker.c1b1.impulse.' + name)
    except ModuleNotFoundError:
        pytest.fail('reference primitive not implemented: ' + name)


def context(**kw):
    return module('resource').ResourceAccount(bit_max=100000, num_bit_max=100000,
        den_bit_max=100000, work_max=10**15, **kw)


def test_signed_four_corners_and_invalid_interval():
    m=module('interval'); c=context()
    v=m.mul(m.Interval(Q(-2),Q(3)),m.Interval(Q(-5),Q(7)),c)
    assert (v.lo,v.hi)==(Q(-15),Q(21))
    with pytest.raises(ValueError): m.Interval(Q(2),Q(1))
    with pytest.raises(TypeError): m.Interval(0.1,0.2)


def test_positive_reciprocal_and_integer_power():
    m=module('interval'); c=context()
    a=m.Interval(Q(2),Q(4)); inv=m.reciprocal(a,c)
    assert (inv.lo,inv.hi)==(Q(1,4),Q(1,2))
    sq=m.power(m.Interval(Q(-2),Q(3)),2,c)
    assert (sq.lo,sq.hi)==(Q(0),Q(9))
    with pytest.raises(ValueError): m.reciprocal(m.Interval(Q(0),Q(1)),c)


@pytest.mark.parametrize('x,n',[(Q(9,4),8),(Q(2),16),(Q(1,65536),1),(Q(1,65536),16)])
def test_sqrt_exact_squared_containment(x,n):
    v=module('sqrt_enclosure').sqrt_enclosure(x,n,context())
    assert v.lo>=0 and v.lo*v.lo<=x<=v.hi*v.hi
    if x==Q(9,4): assert v.lo==v.hi==Q(3,2)
    if n==1: assert v.lo==0 and v.hi>0
    if n==16 and x==Q(1,65536): assert v.lo==v.hi==Q(1,256)


def alternating_oracle(x,terms=60):
    """Independent negative alternating Taylor bracketing for 0<=x<=1."""
    s=Q(1); t=Q(1)
    for k in range(1,terms+1): t=t*(-x)/k; s+=t
    next_term=t*(-x)/(terms+1)
    return min(s,s+next_term),max(s,s+next_term)


@pytest.mark.parametrize('x',[Q(0),Q(1,100),Q(1,2),Q(1)])
def test_exp_contains_independent_alternating_series(x):
    v,order,s=module('exp_enclosure').exp_enclosure(module('interval').Interval(x,x),80,150,context())
    lo,hi=alternating_oracle(x)
    assert v.lo<=lo<=hi<=v.hi
    if x==0: assert v.lo==v.hi==1


def test_large_exp_no_cutoff_and_tail_order_limit():
    e=module('exp_enclosure'); m=module('interval')
    v,_,_=e.exp_enclosure(m.Interval(Q(100),Q(100)),256,300,context())
    assert 0<v.lo<=v.hi<Q(1,10**40)
    with pytest.raises(module('resource').ResourceLimit) as err:
        e.exp_enclosure(m.Interval(Q(1,2),Q(1,2)),80,1,context())
    assert err.value.kind=='ORDER'


@pytest.mark.parametrize('lo,hi,raw',[(Q(7,4),Q(9,4),2),(Q(3,2),Q(3,2),2),
    (Q(5,2),Q(5,2),2),(Q(-5,2),Q(-5,2),-2),(Q(5,2),Q(7,2),None),
    (Q(-7,2),Q(-5,2),None),(Q(49,100),Q(51,100),None)])
def test_even_odd_cell_and_negative_ties(lo,hi,raw):
    d=module('rounding').decide_scaled(module('interval').Interval(lo,hi))
    assert d.raw==raw
    assert d.reason==('ROUNDING_UNPROVED' if raw is None else None)


def test_overflow_asymmetric_ties_and_opposite():
    m=module('interval'); decide=module('rounding').decide_scaled; low=-(1<<95);high=(1<<95)-1
    assert decide(m.Interval(Q(low)-Q(1,2),Q(low)-Q(1,2))).reason=='OPPOSITE_RAW_UNREPRESENTABLE'
    assert decide(m.Interval(Q(low)-Q(3,4),Q(low)-Q(3,4))).reason=='RAW_UNREPRESENTABLE'
    assert decide(m.Interval(Q(high)+Q(1,2),Q(high)+Q(1,2))).reason=='RAW_UNREPRESENTABLE'
    assert decide(m.Interval(Q(low)-10,Q(high)+10)).reason=='ROUNDING_UNPROVED'


def test_resource_guard_before_large_shift_or_cross_product():
    r=module('resource');c=r.ResourceAccount(bit_max=32,num_bit_max=32,den_bit_max=32,work_max=10**8)
    with pytest.raises(r.ResourceLimit):c.shift(1,10**9)
    assert c.operations==0
    c=r.ResourceAccount(bit_max=32,num_bit_max=32,den_bit_max=32,work_max=1)
    with pytest.raises(r.ResourceLimit) as err:c.multiply(3,4)
    assert err.value.kind=='WORK' and c.operations==0
