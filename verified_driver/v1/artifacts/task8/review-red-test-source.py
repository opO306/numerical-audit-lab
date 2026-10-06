"""Fresh internal-review regressions, including prefix mutation before resume."""
from tests.verified_driver_v1_control_support import marker_driver
import copy
import pytest
from verified_driver.v1.replay import ReplayEngine,ReplayTransition,ReplayComparator
from verified_driver.v1.model import content_id
from tests.verified_driver_v1_replay_support import prepared,replay_driver,ReplayMarkerGate,proof_document

def test_certified_master_prefix_mutation_after_current_blocks_first_resume(tmp_path):
    driver=marker_driver(tmp_path)
    def mutate(point):
        if point=='after_current_replace_before_token':
            path=driver.session.master_trace;raw=path.read_bytes();path.write_bytes(b'X'+raw[1:])
    driver._crash_hook=mutate
    result=driver.run(3,'prefix-after-current')
    assert result.verdict=='STOP' and result.generation==1
    assert driver.store.recover()[1].generation==1
    assert driver.session.markers==[1] and driver.session.stopped

def test_replay_only_genesis_never_dispatches_live_run(tmp_path):
    driver=marker_driver(tmp_path);calls=[]
    driver.run=lambda *args:calls.append(args)
    result=ReplayEngine(lambda:driver,driver.store).recover(3,'genesis-only',continue_live=False)
    assert calls==[]
    assert result.verdict=='REPLAYED' and result.generation==0
    assert driver.store.current()[1].generation==0 and driver.session is None

def test_replay_prefix_mutation_before_intermediate_resume_stops(tmp_path):
    original=prepared(tmp_path);fresh=replay_driver(original)
    class Changed(ReplayMarkerGate):
        def observe(self,*args):
            report=super().observe(*args);p=fresh.session.master_trace;raw=p.read_bytes();p.write_bytes(b'X'+raw[1:]);return report
    fresh._gate=Changed()
    result=ReplayEngine(lambda:fresh,original.store).recover(4,'prefix-replay',continue_live=False)
    assert result.verdict=='STOP' and result.generation==2 and fresh.session.markers==[1]

@pytest.mark.parametrize('tail',['step999/q/0','step2/latent/0','step2/q/8','step2/q/0/unrelated-producer'])
def test_repaired_transition_hash_cannot_replace_logical_form_source(tmp_path,tail):
    driver=prepared(tmp_path);document=copy.deepcopy(proof_document(driver))
    candidate=document['fresh_anchor'];candidate['forms'][0]['source_state_id']='f'*64+'/'+tail
    document['replay_proofs'][-1]['checker_report']['candidate']=copy.deepcopy(candidate)
    document['replay_proofs'][-1]['checker_report_sha256']=content_id(document['replay_proofs'][-1]['checker_report'])
    with pytest.raises(ValueError):driver.store.add_replay_transition(document)
    assert driver.store.current()[1].generation==2

@pytest.mark.parametrize('changed',['none','producer','byte'])
def test_real_state_id_shape_preserves_dynamic_source_coordinates(changed):
    from dataclasses import replace
    from tests.test_verified_driver_v1_replay import pair
    stored,observed=pair();old=[];new=[]
    for i,(a,b) in enumerate(zip(stored.forms,observed.forms)):
        tail=f'step1/v:r{100+i}:result:byte:0'
        old.append(replace(a,source_state_id='state:'+stored.live_session_id+'/'+tail))
        if i==0 and changed=='producer':tail=tail.replace(':result:',':copy:')
        if i==0 and changed=='byte':tail=tail.removesuffix(':0')+':8'
        new.append(replace(b,source_state_id='state:'+observed.live_session_id+'/'+tail))
    stored=replace(stored,forms=tuple(old));observed=replace(observed,forms=tuple(new),stored_position_id=stored.content_hash)
    if changed=='none':ReplayComparator.compare(stored,observed)
    else:
        with pytest.raises(ValueError):ReplayComparator.compare(stored,observed)
