"""Runtime implementation oracle written from the closed normative relations."""
import itertools
import pytest
from independent_checker.c1b1.impulse.spec import load_spec
from independent_checker.c1b1.impulse.producer import failure

PRODUCERS = ['NOT_STARTED','RESOLVED','UNPROVED','REFUSED','ERROR']
RECHECKERS = ['NOT_RUN','ACCEPTED','REJECTED','NOT_PROVED','ERROR']
NON_SUCCESS = ['SCHEMA_INVALID','BINDING_MISMATCH','POLICY_UNBOUND','SINGULAR_SEPARATION',
    'PHYSICAL_DOMAIN','RAW_UNREPRESENTABLE','OPPOSITE_RAW_UNREPRESENTABLE','RESOURCE_CAP',
    'ROUNDING_UNPROVED','RECHECK_UNPROVED','RECHECK_REJECTED','ACQUISITION_NOT_AVAILABLE',
    'EXECUTOR_MISMATCH','ARITHMETIC_REFUSED','ARTIFACT_LIMIT','HOST_SERIALIZATION_LIMIT','PROGRAMMING_ANOMALY']
EXPECTED = {('RESOLVED','NOT_RUN'):[None],('RESOLVED','ACCEPTED'):[None],
    ('RESOLVED','REJECTED'):['RECHECK_REJECTED'],('RESOLVED','NOT_PROVED'):['RECHECK_UNPROVED'],
    ('RESOLVED','ERROR'):['PROGRAMMING_ANOMALY'],('UNPROVED','NOT_RUN'):['ROUNDING_UNPROVED','RESOURCE_CAP'],
    ('REFUSED','NOT_RUN'):NON_SUCCESS[:7],('ERROR','NOT_RUN'):['PROGRAMMING_ANOMALY']}

def attempt(producer='RESOLVED',rechecker='NOT_RUN',reason=None):
    return dict(t='0',N='128',P='128',producer=producer,rechecker=rechecker,reason=reason)

@pytest.mark.parametrize('producer,rechecker,reason',list(itertools.product(
    PRODUCERS,RECHECKERS,NON_SUCCESS+[None,'null','','SUCCESS','OK'])))
def test_all_550_closed_relations(producer,rechecker,reason):
    from independent_checker.c1b1.impulse.attempt import validate_attempt
    obj=attempt(producer,rechecker,reason)
    if reason in EXPECTED.get((producer,rechecker),[]):
        assert validate_attempt(obj)==obj
    else:
        with pytest.raises(ValueError):validate_attempt(obj)

@pytest.mark.parametrize('field,value',[('producer','UNKNOWN'),('rechecker','UNKNOWN'),
    ('t','-1'),('N','0'),('P','7'),('t',0),('N','01'),('reason','RESOLVED_SUCCESS')])
def test_attempt_invalid_fields(field,value):
    from independent_checker.c1b1.impulse.attempt import validate_attempt
    obj=attempt();obj[field]=value
    with pytest.raises(ValueError):validate_attempt(obj)

def test_rolling_digest_literal_vectors_and_required_null():
    from independent_checker.c1b1.impulse.attempt import INITIAL_DIGEST,append_attempt
    assert INITIAL_DIGEST.hex()=='71440aac921a3a7ccda50b94757d27b25b8d1479f074cdabbcf80d37e62bb0cb'
    obj=attempt();expected='4127e8735c008c88f0e9105fe8e895d60bc7776a778277763bf8d6bb940aa41e'
    assert append_attempt(INITIAL_DIGEST,obj).hex()==expected
    assert append_attempt(INITIAL_DIGEST,dict(reversed(list(obj.items())))).hex()==expected
    for changed in [dict((k,v) for k,v in obj.items() if k!='reason'),dict(obj,reason='null'),dict(obj,extra=None)]:
        with pytest.raises(ValueError):append_attempt(INITIAL_DIGEST,changed)
    with pytest.raises(ValueError):append_attempt(INITIAL_DIGEST.hex(),obj)

def test_approved_clarification_pin_and_frozen_table():
    spec=load_spec()
    assert spec.sha256=='3c3773b306700b0cf2dced1a618ae73ad81c7dd4abbf36764fc6ec3191ff2bc1'
    with pytest.raises(TypeError):spec.wire['phases'][0]='OTHER'

@pytest.mark.parametrize('reason,kind',[(None,None),('null',None),('SUCCESS',None),
    ('RESOURCE_CAP','UNKNOWN'),('ROUNDING_UNPROVED','BIT'),('RESOURCE_CAP',None)])
def test_failure_null_and_resource_incompatibility(reason,kind):
    with pytest.raises(ValueError):failure(reason,'COMPUTE',kind,producer='UNPROVED')

def test_failure_boundary_uses_4096_bytes():
    from independent_checker.c1b1.impulse.wire import canonical_bytes,WireFailure
    assert len(canonical_bytes('x'*4093,4096))==4096
    with pytest.raises(WireFailure):canonical_bytes('x'*4094,4096)
