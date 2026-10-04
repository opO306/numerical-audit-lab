"""Static specification tests only; never import/run the impulse producer."""
import hashlib
import importlib.util
import json
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1]
NEW=ROOT/'specs/c1b1-independent-impulse-v1-attempt-reason-null'
OLD=ROOT/'specs/c1b1-independent-impulse-v1'
AUDIT=ROOT/'audit/c1b1-attempt-reason-null-2026-10-05/check_spec.py'
PRODUCERS=('NOT_STARTED','RESOLVED','UNPROVED','REFUSED','ERROR')
RECHECKERS=('NOT_RUN','ACCEPTED','REJECTED','NOT_PROVED','ERROR')
EXPECTED={
    ('RESOLVED','NOT_RUN'):[None],
    ('RESOLVED','ACCEPTED'):[None],
    ('RESOLVED','NOT_PROVED'):['RECHECK_UNPROVED'],
    ('RESOLVED','REJECTED'):['RECHECK_REJECTED'],
    ('RESOLVED','ERROR'):['PROGRAMMING_ANOMALY'],
    ('UNPROVED','NOT_RUN'):['ROUNDING_UNPROVED','RESOURCE_CAP'],
    ('REFUSED','NOT_RUN'):['SCHEMA_INVALID','BINDING_MISMATCH','POLICY_UNBOUND',
        'SINGULAR_SEPARATION','PHYSICAL_DOMAIN','RAW_UNREPRESENTABLE','OPPOSITE_RAW_UNREPRESENTABLE'],
    ('ERROR','NOT_RUN'):['PROGRAMMING_ANOMALY'],
}


def checker():
    assert AUDIT.is_file(), 'static spec checker has not been implemented'
    spec=importlib.util.spec_from_file_location('attempt_reason_static_checker',AUDIT)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def wire():
    assert (NEW/'proof-wire.json').is_file(), 'clarification spec has not been issued'
    return json.loads((NEW/'proof-wire.json').read_text(encoding='ascii'))


def tuple_for(producer,rechecker,reason):
    return {'t':'0','N':'128','P':'128','producer':producer,'rechecker':rechecker,'reason':reason}


@pytest.mark.parametrize('producer,rechecker,reason,want',[
    ('RESOLVED','NOT_RUN',None,True),('RESOLVED','ACCEPTED',None,True),
    ('RESOLVED','NOT_RUN','ROUNDING_UNPROVED',False),('UNPROVED','NOT_RUN',None,False),
    ('RESOLVED','NOT_PROVED',None,False),('RESOLVED','NOT_PROVED','RECHECK_UNPROVED',True)])
def test_requested_attempt_relations(producer,rechecker,reason,want):
    assert checker().validate_attempt(tuple_for(producer,rechecker,reason),wire()) is want


@pytest.mark.parametrize('producer',PRODUCERS)
@pytest.mark.parametrize('rechecker',RECHECKERS)
def test_every_status_pair_and_every_existing_reason(producer,rechecker):
    w=wire();c=checker()
    for reason in [None]+w['reasons']+['SUCCESS','RESOLVED_SUCCESS','OK','UNKNOWN']:
        want=reason in EXPECTED.get((producer,rechecker),[])
        assert c.validate_attempt(tuple_for(producer,rechecker,reason),w) is want


def test_closed_table_complete_unique_and_no_new_reason_enum():
    w=wire();prior=json.loads((OLD/'proof-wire.json').read_text())
    rows=w['attempt_tuple_contract']['compatibility_table']
    expected={(p,r):EXPECTED.get((p,r),[]) for p in PRODUCERS for r in RECHECKERS}
    assert len(rows)==25
    assert {(v['producer'],v['rechecker']):v['allowed_reasons'] for v in rows}==expected
    assert w['reasons']==prior['reasons']


@pytest.mark.parametrize('edit',['missing','extra','null_non_success','t_number','t_negative','N_zero','P_small','unknown_producer','unknown_rechecker','reason_bool','oversized_N'])
def test_tuple_is_closed_typed_and_reason_is_always_present(edit):
    a=tuple_for('RESOLVED','NOT_RUN',None)
    if edit=='missing':del a['reason']
    elif edit=='extra':a['diagnostic']='x'
    elif edit=='null_non_success':a['producer']='REFUSED'
    elif edit=='t_number':a['t']=0
    elif edit=='t_negative':a['t']='-1'
    elif edit=='N_zero':a['N']='0'
    elif edit=='P_small':a['P']='7'
    elif edit=='unknown_producer':a['producer']='SUCCESS'
    elif edit=='unknown_rechecker':a['rechecker']='SUCCESS'
    elif edit=='reason_bool':a['reason']=False
    elif edit=='oversized_N':a['N']='1'+'0'*4096
    assert checker().validate_attempt(a,wire()) is False


def test_canonical_null_digest_and_missing_key_are_distinct():
    c=checker();a=tuple_for('RESOLVED','NOT_RUN',None)
    exact=b'{"N":"128","P":"128","producer":"RESOLVED","reason":null,"rechecker":"NOT_RUN","t":"0"}\n'
    assert c.canonical(a)==exact
    h0=hashlib.sha256(b'LAB_C1B1_ATTEMPTS_V1\0').digest()
    assert c.rolling_step(h0,a,wire())==hashlib.sha256(h0+exact).digest()
    missing=dict(a);del missing['reason']
    assert c.canonical(missing)!=exact
    with pytest.raises(ValueError):c.rolling_step(h0,missing,wire())


def test_failure_reason_remains_non_null_and_schema_unchanged():
    c=checker();w=wire();prior=json.loads((OLD/'proof-wire.json').read_text())
    for key in ['closed_object_keys','resource_failure_record','reasons','resource_kinds','resource_kind_rule','failure_attempt_count_bound','limits','types']:
        assert w[key]==prior[key]
    assert len(w['closed_object_keys']['Failure'])==11
    for reason in w['reasons']:assert c.valid_failure_reason(reason,w)
    for bad in [None,'SUCCESS','OK','',False,0]:assert not c.valid_failure_reason(bad,w)


def test_canonical_hash_graph_and_semantic_delta_are_minimal():
    assert checker().check_package(NEW,OLD)['result']=='PASS'
