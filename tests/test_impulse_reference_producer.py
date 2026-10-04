"""AUTHOR PHYSICAL-STATE checks. No runtime activation or J verification."""
import copy
from fractions import Fraction as Q
import json
import subprocess
import sys
import pytest
from impulse_reference_support import input_object,encoded,reference_policy,nominal_diagnostic
from test_impulse_reference_primitives import module


@pytest.mark.parametrize('q',[(6,2,1),(-6,-2,-1),(0,6,0)])
def test_private_whole_vector_matches_diagnostic(q):
    import mpmath as mp
    obj=input_object(q);data=encoded(obj);old=copy.deepcopy(obj)
    result=module('producer').evaluate_reference(data,reference_policy(obj))
    assert result.layers['producer']=='RESOLVED' and result.raw is not None
    assert result.opposite==tuple(-v for v in result.raw)
    assert result.layers['publication']=='NOT_PUBLISHED' and result.layers['rechecker']=='NOT_RUN'
    cert=json.loads(result.certificate)
    assert tuple(int(v) for v in cert['raw_J'])==result.raw and 'final_interval' not in cert
    assert len(cert['proof']['exp_plan'])==9 and data==encoded(obj) and obj==old
    with mp.workdps(150):
        radius=mp.sqrt(sum(mp.mpf(v)**2 for v in q));_,vp=nominal_diagnostic(radius)
        for k,lane in enumerate(result.scaled_intervals):
            expected=-vp*mp.mpf(q[k])/radius*20*2**80
            lo=mp.mpf(lane.lo.numerator)/lane.lo.denominator
            hi=mp.mpf(lane.hi.numerator)/lane.hi.denominator
            assert lo<=expected<=hi
            # Numeric differential check, explicitly not a soundness oracle.
            assert result.raw[k]==int(mp.nint(expected))


def test_runtime_entry_is_unbound_and_no_nonlinear_activation():
    obj=input_object();r=module('producer').produce(encoded(obj))
    f=json.loads(r.failure)
    assert f['phase']=='POLICY' and f['reason']=='POLICY_UNBOUND' and f['resource_kind'] is None
    assert r.raw is None and r.certificate is None and r.layers['execution']=='STOP'


@pytest.mark.parametrize('q,reason',[((0,0,0),'SINGULAR_SEPARATION'),((0,1,0),'PHYSICAL_DOMAIN')])
def test_domain_refusal_precedes_policy_and_zero(q,reason):
    obj=input_object(q);r=module('producer').produce(encoded(obj));f=json.loads(r.failure)
    assert f['phase']=='PHYSICAL_DOMAIN' and f['reason']==reason and r.raw is None


def test_exhaustion_no_partial_vector_no_last_approximation():
    obj=input_object((0,6,1));obj['budget'].update(N0='1',P0='8',N_max='1',P_max='8',max_attempts='1',exp_order_max='1')
    r=module('producer').evaluate_reference(encoded(obj),reference_policy(obj));f=json.loads(r.failure)
    assert r.raw is None and r.certificate is None and f['status']['producer']=='UNPROVED'
    assert f['reason'] in ['RESOURCE_CAP','ROUNDING_UNPROVED'] and f['resource_kind'] in ['ORDER',None]


def test_atomic_lane_decisions_overflow_dominates_unproved():
    m=module('interval');p=module('producer')
    resolved=m.Interval(Q(2),Q(2));ambiguous=m.Interval(Q(49,100),Q(51,100));overflow=m.Interval(Q(1<<96),Q(1<<96))
    raw,reason=p.decide_vector((resolved,ambiguous,overflow))
    assert raw is None and reason=='RAW_UNREPRESENTABLE'
    raw,reason=p.decide_vector((resolved,ambiguous,resolved))
    assert raw is None and reason=='ROUNDING_UNPROVED'


def test_failure_closed_fields_and_resource_enum():
    obj=input_object();obj['budget']['integer_bit_max']='8'
    r=module('producer').evaluate_reference(encoded(obj),reference_policy(obj));f=json.loads(r.failure)
    assert set(f)=={'schema','status','phase','reason','resource_kind','spec_sha256','state_sha256','occurrence_sha256','budget_sha256','attempt_count','attempt_digest'}
    assert f['resource_kind']=='BIT' and f['attempt_count'] is None and len(r.failure)<=4096


def test_integer_and_artifact_boundary_before_conversion():
    w=module('wire');limit=10**4096
    assert len(w.decimal(limit-1))==4096 and len(w.decimal(-(limit-1)))==4097
    for value in (limit,limit+1,-limit,-limit-1):
        with pytest.raises(w.WireFailure):w.decimal(value)
    assert w.decimal(0)=='0'
    assert len(w.canonical_bytes('x'*(1048576-3)))==1048576
    with pytest.raises(w.WireFailure) as err:w.canonical_bytes('x'*(1048576-2))
    assert err.value.reason=='ARTIFACT_LIMIT'


def test_host_lower_digit_limit_is_bounded_in_separate_process():
    # Test process only: production never changes the process-global setting.
    code="from independent_checker.c1b1.impulse.wire import decimal,WireFailure; import sys; sys.set_int_max_str_digits(640)\ntry: decimal(10**700)\nexcept WireFailure as e: assert (e.reason,e.kind)==('HOST_SERIALIZATION_LIMIT','HOST_DECIMAL')\nelse: raise AssertionError('expected bounded host refusal')"
    r=subprocess.run([sys.executable,'-c',code],capture_output=True)
    assert r.returncode==0,r.stderr


@pytest.mark.parametrize('payload',[b'{"x":"1","x":"2"}\n',b'{"x":true}\n',b'{"x":1}\n',b'{"x":NaN}\n',b'['*8+b']'*8+b'\n'])
def test_wire_rejects_duplicate_bool_number_and_depth(payload):
    with pytest.raises(module('wire').WireFailure):module('wire').parse(payload)


def test_policy_schedule_and_conflicting_refinements():
    obj=input_object();p=reference_policy(obj)
    assert list(p.attempts())==[(0,128,128),(1,256,256),(2,512,512)]
    m=module('interval');validate=module('producer').check_refinements
    validate((m.Interval(Q(0),Q(2)),)*3,(m.Interval(Q(1),Q(3)),)*3)
    with pytest.raises(ValueError):validate((m.Interval(Q(0),Q(1)),)*3,(m.Interval(Q(2),Q(3)),)*3)
