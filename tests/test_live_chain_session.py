from dataclasses import replace
from pathlib import Path
import os, sys
import pytest
from verified_driver.v1.live_chain.session import LiveGalaSession
from verified_driver.v1.live_chain.gdb_live import drive_barriers
from verified_driver.v1.live_chain.protocol import TokenLedger
from verified_driver.v1.live_chain.checkpoint import CheckpointSealer
from tests.verified_driver_v1_support import ROOT, LEDGER

class FixtureSession(LiveGalaSession):
    def _command(self): return [sys.executable,str(ROOT/'tests/live_chain_worker.py')]

def certify_fixture(session,event,k):
    identity=CheckpointSealer(session.run_root).seal(session.master_trace,event,session.metadata,session.run_root/f'checkpoint{k}')
    session.bind_checkpoint(identity,session.run_root/f'checkpoint{k}',str(k)*64,k-1)
    if not hasattr(session,'fixture_tokens'): session.fixture_tokens=TokenLedger()
    return session.fixture_tokens.issue(session_id=event.session_id,barrier_seq=k,
      predecessor_generation=k-1,candidate_generation=k,checkpoint_id=identity,state_id=str(k)*64,current_state_id=str(k)*64)

def test_private_pipe_token_runs_exactly_one_next_body(tmp_path):
    session=FixtureSession(ROOT,tmp_path/'run',3,LEDGER)
    try:
        event=session.start()
        assert event.completed_step==1 and session.is_paused_at(event)
        assert (session.run_root/'body1').is_file() and not (session.run_root/'body2').exists()
        token=certify_fixture(session,event,1); event2=session.resume(token)
        assert event2.completed_step==2 and (session.run_root/'body2').is_file()
        assert not (session.run_root/'body3').exists()
        assert not session.is_paused_at(event)
        token2=certify_fixture(session,event2,2)
        event3=session.resume(token2)
        assert event3.barrier_kind=='FINAL_TERMINAL'
        assert session.finish(None)['normal_exit'] is True
        assert not (session.run_root/'body4').exists()
    finally: session.terminate('test finished')

@pytest.mark.parametrize('attack',['stale','foreign','wrong_checkpoint','unbound','duplicate'])
def test_bad_token_cannot_enter_next_body(tmp_path,attack):
    session=FixtureSession(ROOT,tmp_path/'run',3,LEDGER)
    try:
        e=session.start(); token=certify_fixture(session,e,1)
        if attack=='duplicate':
            session.resume(token)
            with pytest.raises(ValueError): session.resume(token)
            assert not (session.run_root/'body3').exists(); return
        if attack=='foreign': token=replace(token,session_id='f'*64)
        if attack=='wrong_checkpoint': token=replace(token,checkpoint_id='f'*64)
        if attack=='stale': token=replace(token,barrier_seq=2,predecessor_generation=1,candidate_generation=2)
        if attack=='unbound': session._binding=None
        with pytest.raises(ValueError): session.resume(token)
        assert not (session.run_root/'body2').exists()
    finally: session.terminate('test finished')

def test_final_terminal_refuses_numerical_resume(tmp_path):
    session=FixtureSession(ROOT,tmp_path/'run',1,LEDGER)
    try:
        e=session.start()
        token=certify_fixture(session,e,1)
        with pytest.raises(ValueError): session.resume(token)
        assert not (session.run_root/'body2').exists()
    finally: session.terminate('test finished')

def test_gdb_barrier_wait_occurs_before_next_body_instructions():
    events=[]
    class Backend:
        def prepare(self): events.append('original init and step1 entry')
        def body(self,k): events.append(f'body{k}')
        def handoff(self,k): events.append(f'caller{k}-entry{k+1}')
        def terminal(self): events.append('terminal')
        def barrier(self,k,kind): events.append(f'pause{k}'); return k
        def wait(self,event,kind):
            events.append(f'wait{event}')
            if event==1: raise EOFError('controller died before acceptance')
        def finish(self): events.append('finish')
    with pytest.raises(EOFError): drive_barriers(Backend(),3)
    assert events==['original init and step1 entry','body1','caller1-entry2','pause1','wait1']
