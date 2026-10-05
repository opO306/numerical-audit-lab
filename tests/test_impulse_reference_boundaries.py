"""Additional exact branch, wire and failure-state checks."""
import copy,json
from fractions import Fraction as Q
import pytest
from impulse_reference_support import input_object,encoded,reference_policy
from test_impulse_reference_primitives import module,context

def test_negative_power_exact_and_outward_dyadic():
    m=module('interval');v=m.power(m.Interval(Q(2),Q(4)),-3,context())
    assert (v.lo,v.hi)==(Q(1,64),Q(1,8))
    v=m.widen(m.Interval(Q(-1,3),Q(1,3)),8,context())
    assert (v.lo,v.hi)==(Q(-86,256),Q(86,256))

def test_seven_container_depth_allows_leaf_at_eight():
    w=module('wire');obj='leaf'
    for _ in range(7):obj=[obj]
    assert w.parse(w.canonical_bytes(obj))==obj
    with pytest.raises(w.WireFailure):w.canonical_bytes([obj])

@pytest.mark.parametrize('field,value,reason,kind',[
    ('temporary_allocation_bytes','1','RESOURCE_CAP','TEMP_ALLOCATION'),
    ('live_allocation_bytes','1','RESOURCE_CAP','LIVE_ALLOCATION'),
    ('input_parse_bytes','1','RESOURCE_CAP','PARSE_BYTES'),
    ('private_certificate_bytes','1','ARTIFACT_LIMIT','ARTIFACT_BYTES'),
    ('exp_order_max','1','RESOURCE_CAP','ORDER')])
def test_caps_and_immutability(field,value,reason,kind):
    obj=input_object();obj['budget'][field]=value;before=copy.deepcopy(obj);data=encoded(obj)
    r=module('producer').evaluate_reference(data,reference_policy(obj));f=json.loads(r.failure)
    assert (f['reason'],f['resource_kind'])==(reason,kind)
    assert r.raw is r.opposite is r.certificate is None
    assert obj==before and data==encoded(obj) and r.layers['execution']=='STOP'
    if field=='private_certificate_bytes':assert r.layers['producer']=='RESOLVED'

def test_wrong_spec_refused_and_failure_path_immutable():
    obj=input_object();obj['spec_sha256']='f'*64;before=copy.deepcopy(obj)
    r=module('producer').evaluate_reference(encoded(obj),reference_policy(obj))
    assert json.loads(r.failure)['reason']=='BINDING_MISMATCH' and obj==before
    assert r.raw is None and r.certificate is None

def test_real_interrupted_attempt_in_digest_not_h0():
    from independent_checker.c1b1.impulse.attempt import INITIAL_DIGEST,append_attempt
    obj=input_object();obj['budget']['integer_bit_max']='8'
    r=module('producer').evaluate_reference(encoded(obj),reference_policy(obj))
    expected=append_attempt(INITIAL_DIGEST,dict(t='0',N='128',P='128',producer='UNPROVED',rechecker='NOT_RUN',reason='RESOURCE_CAP'))
    assert json.loads(r.failure)['attempt_digest']==expected.hex()

def test_exact_long_derivative_identity():
    m=module('interval');p=module('potential');d=module('derivative')
    # Independent derivative of -3*5*R^-4 with a specified damping slope 7:
    # -3*(7/R^4 - 4*5/R^5), at R=2, is 9/16.
    terms=p.Terms((),(p.LongTerm(m.point(3),2,m.point(5),m.point(7),m.point(2)),),())
    result=d.derivative(terms,context())
    assert result.lo==result.hi==Q(9,16)

def test_tt_and_leading_branches_against_separate_exact_series():
    import math
    m=module('interval');p=module('potential');s=module('spec').load_spec()
    c=module('resource').ResourceAccount(bit_max=100000,num_bit_max=100000,den_bit_max=100000,work_max=10**40)
    r=Q(3);terms=p.evaluate_terms(s,m.point(r),128,300,c)
    # Reconstruct the needed exp bracket with an independent alternating series,
    # after exact halving; no producer primitive is an expected-value helper.
    def exp_bracket(z):
        squarings=0
        while z>Q(1,2):z/=2;squarings+=1
        t=total=Q(1)
        for k in range(1,181):t*=(-z)/k;total+=t
        nxt=t*(-z)/181;lo,hi=sorted((total,total+nxt))
        for _ in range(squarings):lo*=lo;hi*=hi
        return lo,hi
    numerator=1+sum(s.constants[f'RET_A_{k}']*r**k for k in range(1,6))
    denominator=1+sum(s.constants[f'RET_B_{k}']*r**k for k in range(1,7))
    np=sum(k*s.constants[f'RET_A_{k}']*r**(k-1) for k in range(1,6))
    dp=sum(k*s.constants[f'RET_B_{k}']*r**(k-1) for k in range(1,7))
    gp=(np*denominator-numerator*dp)/denominator**2
    idx=0
    for family,klo,khi,extra in [('BO',3,8,1),('REL',2,4,0),('QED',3,4,0)]:
        eta=s.constants[f'eta_{family}'];z=eta*r;elo,ehi=exp_bracket(z)
        for k in range(klo,khi+1):
            term=terms.long[idx];idx+=1;last=2*k+extra
            series=sum(z**l/math.factorial(l) for l in range(last+1))
            b=eta*z**last/math.factorial(last)
            leading=numerator/denominator if family=='BO' and k==3 else (0 if family=='REL' and k==2 else 1)
            expected_lo,expected_hi=leading-ehi*series,leading-elo*series
            slope_lo,slope_hi=elo*b,ehi*b
            if family=='BO' and k==3:slope_lo+=gp;slope_hi+=gp
            assert term.damping.lo<=expected_lo<=expected_hi<=term.damping.hi
            assert term.damping_slope.lo<=slope_lo<=slope_hi<=term.damping_slope.hi
