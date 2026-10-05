"""Small regressions for author-side final review findings."""
import copy,json
from fractions import Fraction as Q
import pytest
from impulse_reference_support import input_object,encoded,reference_policy
from independent_checker.c1b1.impulse import contracts,interval,producer,rechecker_adapter,resource,rounding
from independent_checker.c1b1.impulse.spec import load_spec
from independent_checker.c1b1.impulse.certificate import source_identity

def tiny():return resource.ResourceAccount(bit_max=20,num_bit_max=20,den_bit_max=20,work_max=10**12)

def test_constructor_cross_products_precharged():
    c=tiny()
    with pytest.raises(resource.ResourceLimit) as err:
        interval.add(interval.Interval(Q(1,251),Q(1,241)),interval.Interval(Q(1,239),Q(1,233)),c)
    assert err.value.kind=='BIT' and c.peak_integer_bits<=20

def test_rounding_and_refinement_comparisons_precharged():
    c=tiny();v=interval.Interval(Q(1,251),Q(1,241))
    with pytest.raises(resource.ResourceLimit):rounding.decide_scaled(v,c)
    # Two input rational endpoint bounds fit 20 bits; their cross product does not.
    a=interval.Interval(Q(1,60001),Q(2,60001));b=interval.Interval(Q(1,60007),Q(2,60007))
    with pytest.raises(resource.ResourceLimit):producer.check_refinements((a,)*3,(b,)*3,c)

@pytest.mark.parametrize('bad',['acquisition-key','budget-key','last-atom-key','last-decimal','budget-decimal','long-decimal'])
def test_entire_input_syntax_before_first_int(monkeypatch,bad):
    obj=input_object()
    if bad=='acquisition-key':obj['acquisition']['extra']='x'
    elif bad=='budget-key':obj['budget']['extra']='x'
    elif bad=='last-atom-key':obj['state']['atoms'][1]['extra']='x'
    elif bad=='last-decimal':obj['state']['atoms'][1]['momentum_raw'][2]='01'
    elif bad=='budget-decimal':obj['budget']['legacy_digit_max']='01'
    else:obj['state']['atoms'][1]['momentum_raw'][2]='1'*4097
    calls=[];real=contracts.integer
    def spy(*a,**kw):calls.append(a);return real(*a,**kw)
    monkeypatch.setattr(contracts,'integer',spy)
    with pytest.raises(contracts.ContractFailure):contracts.validate_input(encoded(obj),load_spec())
    assert calls==[]

@pytest.fixture(scope='module')
def candidate():
    obj=input_object();r=producer.evaluate_reference(encoded(obj),reference_policy(obj))
    return obj,json.loads(r.certificate)

@pytest.mark.parametrize('bad',['input-late-key','input-late-decimal','certificate-key','last-order','last-rate'])
def test_adapter_entire_schema_before_first_int(monkeypatch,candidate,bad):
    obj,cert=copy.deepcopy(candidate)
    if bad=='input-late-key':obj['acquisition']['extra']='x'
    elif bad=='input-late-decimal':obj['budget']['legacy_digit_max']='01'
    elif bad=='certificate-key':cert['extra']='x'
    elif bad=='last-order':cert['proof']['exp_plan'][-1]['order']='01'
    else:cert['proof']['exp_plan'][-1]['rate']['d']='01'
    calls=[];real=rechecker_adapter._int
    def spy(*a,**kw):calls.append(a);return real(*a,**kw)
    monkeypatch.setattr(rechecker_adapter,'_int',spy)
    with pytest.raises(rechecker_adapter.BindingRefusal):rechecker_adapter.prepare(encoded(obj),encoded(cert),expected_producer_sha256=source_identity())
    assert calls==[]
