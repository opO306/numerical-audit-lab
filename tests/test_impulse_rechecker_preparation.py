"""Author binding integration only; the pinned V2 is never executed."""
import copy,json
import pytest
from impulse_reference_support import input_object,encoded,reference_policy
from independent_checker.c1b1.impulse.producer import evaluate_reference
from independent_checker.c1b1.impulse.certificate import source_identity

@pytest.fixture(scope='module')
def example():
    obj=input_object((0,6,1));r=evaluate_reference(encoded(obj),reference_policy(obj))
    assert r.raw is not None
    return obj,json.loads(r.certificate)

def test_independent_binding_preparation_and_disabled_call(example):
    from independent_checker.c1b1.impulse.rechecker_adapter import prepare,invoke
    obj,cert=example;before=copy.deepcopy((obj,cert))
    p=prepare(encoded(obj),encoded(cert),expected_producer_sha256=source_identity())
    assert p.state=='PREPARED_ONLY' and p.zero_axes==(True,False,False)
    assert p.legacy[0] is None and p.legacy[1]['input']['component']==1
    assert p.legacy[1]['input']['dr_raw']==obj['state']['atoms'][1]['position_raw']
    assert all(e['mode']=='full' for e in p.legacy[1]['proof']['exp'])
    assert p.legacy[1]['output']['raw']==cert['raw_J'][1]
    assert (obj,cert)==before
    with pytest.raises(RuntimeError,match='POLICY_UNBOUND'):invoke(p)

@pytest.mark.parametrize('mutation',['momentum','position','occurrence','budget','spec','producer',
    'rechecker','zero','raw','rate','mode','order','unknown','reason','count','precision'])
def test_adapter_rejects_forged_binding_or_closed_proof(example,mutation):
    from independent_checker.c1b1.impulse.rechecker_adapter import prepare,BindingRefusal
    obj,cert=copy.deepcopy(example)
    if mutation=='momentum':obj['state']['atoms'][0]['momentum_raw'][0]='1'
    elif mutation=='position':obj['state']['atoms'][1]['position_raw'][0]='1'
    elif mutation=='occurrence':obj['acquisition']['record_id']='c'*64
    elif mutation=='budget':obj['budget']['work_unit_max']='1'
    elif mutation=='spec':cert['spec_sha256']='f'*64
    elif mutation=='producer':cert['producer_source_sha256']='f'*64
    elif mutation=='rechecker':cert['rechecker_source_sha256']='f'*64
    elif mutation=='zero':cert['proof']['lane_kinds'][1]='EXACT_ZERO_AXIS'
    elif mutation=='raw':cert['raw_J'][0]='1'
    elif mutation=='rate':cert['proof']['exp_plan'][0]['rate']['n']='0'
    elif mutation=='mode':cert['proof']['exp_plan'][0]['mode']='zero_floor'
    elif mutation=='order':cert['proof']['exp_plan'][0]['order']='1000001'
    elif mutation=='unknown':cert['extra']='forbidden'
    elif mutation=='reason':cert['reason']=None
    elif mutation=='count':cert['attempt_count']='4'
    elif mutation=='precision':cert['proof']['sqrt_bits']='129'
    with pytest.raises(BindingRefusal):prepare(encoded(obj),encoded(cert),expected_producer_sha256=source_identity())

def test_exact_pinned_source_bytes_verified_without_import():
    from independent_checker.c1b1.impulse.rechecker_adapter import verify_checker_source
    path='current/c1b1-impulse-design-conditions-2026-10-04/provenance/objects/ad1a66091ec743359565f3d19affbef800c70192.blob.raw'
    assert verify_checker_source(path)=='180d5a19bbea606594912e95b3c210b5a7739995afa39c5300959faef8b94d96'
