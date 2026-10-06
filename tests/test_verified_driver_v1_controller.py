"""TDD authority sequencing with markers; not numerical certification."""
from dataclasses import replace
import pytest
from tests.verified_driver_v1_support import ROOT, LEDGER
from tests.verified_driver_v1_control_support import marker_driver, MarkerGate
from verified_driver.v1.controller import VerifiedChainDriver
from verified_driver.v1.gate import V1Gate

def test_three_publications_precede_exactly_one_resume_each_and_retry(tmp_path):
    d=marker_driver(tmp_path); result=d.run(3,'positive')
    assert result.verdict=='ACCEPT',result
    assert d.store.current()[1].generation==3 and d.session.markers==[1,2,3] and d.session.finished
    assert len(d.store.chain())==4
    d._make_session=lambda *a: pytest.fail('terminal retry launched a process')
    assert d.run(3,'positive').state_id==result.state_id

def test_third_edge_refusal_preserves_s2_and_blocks_body4(tmp_path):
    d=marker_driver(tmp_path,4,MarkerGate(refuse=3)); result=d.run(4,'bad')
    assert result.verdict=='STOP' and result.generation==2
    assert d.session.markers==[1,2,3] and d.session.stopped

@pytest.mark.parametrize('exc',[RuntimeError('checker crash'),TimeoutError('checker timeout'),MemoryError('resource refusal')])
def test_checker_or_resource_failure_never_resumes(tmp_path,exc):
    d=marker_driver(tmp_path,gate=MarkerGate(exception=exc)); result=d.run(3,'bad')
    assert result.verdict=='STOP' and result.generation==0 and d.session.markers==[1]

@pytest.mark.parametrize('point,generation',[('before_current_replace',0),('after_current_replace_before_token',1),('after_token_before_resume',1)])
def test_precise_current_crash_table(tmp_path,point,generation):
    def crash(p):
        if p==point: raise RuntimeError('injected crash '+p)
    d=marker_driver(tmp_path,hook=crash)
    if point=='before_current_replace': d.store._crash_hook=crash
    result=d.run(3,'crash')
    assert result.verdict=='STOP' and result.generation==generation
    assert d.store.recover()[1].generation==generation and d.session.markers==[1] and d.session.stopped

def test_stale_event_predecessor_stops_before_gate(tmp_path):
    d=marker_driver(tmp_path)
    original=d._make_session
    def factory(*a):
        s=original(*a); start=s.start
        def bad(): return replace(start(),predecessor_id='f'*64)
        s.start=bad; return s
    d._make_session=factory
    assert d.run(3,'stale').generation==0 and d.session.markers==[1]

def test_pass_cannot_resume_before_current(tmp_path):
    d=marker_driver(tmp_path)
    d._gate=MarkerGate(callback=lambda k:d.session.resume(None))
    result=d.run(3,'early'); assert result.verdict=='STOP' and result.generation==0 and d.session.markers==[1]

def test_prior_acceptance_cannot_authorize_next_edge(tmp_path):
    d=marker_driver(tmp_path); gate=MarkerGate(); first=[]
    class Reused:
        def evaluate(self,*args):
            if not first: first.append(gate.evaluate(*args))
            return first[0]
    d._gate=Reused(); result=d.run(3,'reused')
    assert result.verdict=='STOP' and result.generation==1 and d.session.markers==[1,2]

def test_production_gate_refuses_test_only_checkpoint_before_workers(tmp_path):
    from tests.live_chain_fixture import checkpoint
    from verified_driver.v1.model import chain_genesis
    cp,cid,_=checkpoint(tmp_path/'fixture',chain_genesis(ROOT,3),1)
    with pytest.raises(ValueError,match='TEST_ONLY'):
        V1Gate().evaluate(cid,cp,chain_genesis(ROOT,3),tmp_path/'out',ROOT)

def test_run_root_must_not_alias_store(tmp_path):
    d=marker_driver(tmp_path)
    with pytest.raises(ValueError): VerifiedChainDriver(ROOT,d.store,d.store.root,LEDGER)
