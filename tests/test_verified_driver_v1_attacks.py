"""Task 7 attacks: TEST_ONLY markers/saved evidence, never fresh Gala authority."""
from dataclasses import replace
from pathlib import Path
import copy
import json
import os
import sys
import pytest
from verified_driver.v1.model import canonical_bytes, digest_bytes, chain_genesis
from verified_driver.v1.replay import ReplayEngine
from verified_driver.v1.live_chain.checker import check_edge
from verified_driver.v1.live_chain.producer import build_edge
from tests.verified_driver_v1_support import ROOT, LEDGER, ZERO, successor
from tests.verified_driver_v1_control_support import marker_driver, MarkerGate
from tests.verified_driver_v1_replay_support import prepared, replay_driver, ReplayMarkerGate
from tests.test_verified_driver_v1_replay_transition import inventory
from tests.test_live_chain_session import FixtureSession, certify_fixture
from tests.live_chain_fixture import checkpoint, rehash_derived

OTHER='0x3fc0000000000000'

@pytest.fixture(scope='module')
def evidence():
    rows=[]
    yield rows
    junit=next((a.split('=',1)[1] for a in sys.argv if a.startswith('--junitxml=')),None)
    if junit:
        from runtime_trace.regular_nstep.resources import reserve_writer
        root=Path(os.environ['GIT_WORK_TREE'])
        out=root/'verified_driver/v1/artifacts/task7'/(Path(junit).stem.replace('-junit','')+'-attack-results.json')
        raw=canonical_bytes({'schema':'TASK7_TEST_ONLY_ATTACK_RESULTS_V1','rows':rows,
             'fresh_gala_executed':False,'formal_certification':False})
        reserve_writer(len(raw))
        with out.open('xb') as stream: stream.write(raw)

def stopped(evidence,name,d,result,generation,markers):
    current=d.store.recover()[1].generation
    evidence.append({'attack':name,'scope':'TEST_ONLY_CONTROLLER','verdict':result.verdict,
        'generation':current,'markers':d.session.markers,'reason':result.reason,
        'expected_generation':generation,'expected_markers':markers})
    assert result.verdict=='STOP' and result.generation==current==generation,result
    assert d.session.markers==markers and d.session.stopped

def altered(state,attack):
    if attack in ('q','full_v','latent'):
        values=(OTHER,)+getattr(state,attack+'_bits')[1:]
        fields={attack+'_bits':values,
            'forms':tuple(replace(f,center_bits=OTHER) if f.component==attack and f.byte_offset==0 else f for f in state.forms)}
        if attack!='latent': fields['public_bits']=values+state.full_v_bits if attack=='q' else state.q_bits+values
        return replace(state,**fields)
    if attack=='coefficient': return replace(state,forms=(replace(state.forms[0],coefficients=('0x1.0000000000000p-52',)+state.forms[0].coefficients[1:]),)+state.forms[1:])
    if attack=='box': return replace(state,forms=(replace(state.forms[0],box='0x1.0000000000000p-50'),)+state.forms[1:])
    if attack=='form_reset': return replace(state,forms=tuple(replace(f,coefficients=('0x0.0p+0',)*4,box='0x0.0p+0') for f in state.forms))
    if attack=='t': return replace(state,next_t_bits=OTHER)
    if attack=='source': return replace(state,source_binding='f'*64)
    if attack=='gradient': return replace(state,gradient_bits=(OTHER,ZERO))
    raise AssertionError(attack)

def test_positive_and_idempotent_transaction_retry(tmp_path,evidence):
    d=marker_driver(tmp_path); result=d.run(3,'positive')
    before=inventory(d.store)
    d._make_session=lambda *args:pytest.fail('retry started a numerical session')
    assert d.run(3,'positive')==result and inventory(d.store)==before
    assert result.verdict=='ACCEPT' and result.generation==3 and d.session.markers==[1,2,3]
    evidence.append({'attack':'positive_and_transaction_retry','scope':'TEST_ONLY_CONTROLLER','verdict':'PASS','generation':3,'markers':[1,2,3]})

@pytest.mark.parametrize('attack',['q','full_v','latent','coefficient','box','form_reset','t','source','gradient'])
def test_post_check_candidate_cannot_escape_exact_acceptance_binding(tmp_path,evidence,attack):
    class Changed(MarkerGate):
        def evaluate(self,*args):
            state,receipt=super().evaluate(*args)
            return altered(state,attack),receipt
    d=marker_driver(tmp_path,gate=Changed()); result=d.run(3,'mutation')
    stopped(evidence,'post_check_'+attack,d,result,0,[1])

@pytest.mark.parametrize('attack',['receipt_reuse','resume_before_check','resume_before_current','certified_prefix','source_change'])
def test_publication_and_pause_guards(tmp_path,evidence,attack):
    d=marker_driver(tmp_path)
    if attack=='receipt_reuse':
        gate=MarkerGate(); first=[]
        class Reused:
            def evaluate(self,*args):
                if not first:first.append(gate.evaluate(*args))
                return first[0]
        d._gate=Reused()
    elif attack=='resume_before_check': d._gate=MarkerGate(callback=lambda k:d.session.resume(None))
    elif attack=='resume_before_current':
        d.store._crash_hook=lambda point:d.session.resume(None) if point=='before_current_replace' else None
    else:
        factory=d._make_session
        def changed(*args):
            s=factory(*args)
            if attack=='source_change':
                start=s.start
                def start_changed():
                    event=start(); s.sources=dict(s.sources); s.sources[next(iter(s.sources))]='f'*64
                    return event
                s.start=start_changed
            else:
                emit=s.emit
                def emit_changed(pred):
                    event=emit(pred)
                    if pred.generation==1:
                        raw=s.master_trace.read_bytes(); s.master_trace.write_bytes(b'X'+raw[1:])
                    return event
                s.emit=emit_changed
            return s
        d._make_session=changed
    result=d.run(3,'guard')
    generation=1 if attack in ('receipt_reuse','certified_prefix') else 0
    stopped(evidence,attack,d,result,generation,[1,2] if generation else [1])

@pytest.mark.parametrize('attack',['wrong_parent','foreign_session','skipped_barrier','duplicate_barrier'])
def test_barrier_splice_never_advances_authority(tmp_path,evidence,attack):
    d=marker_driver(tmp_path); factory=d._make_session
    def changed(*args):
        s=factory(*args); emit=s.emit; old=[]
        def bad(pred):
            event=emit(pred)
            if attack=='duplicate_barrier':
                if old:return old[0]
                old.append(event); return event
            if attack=='wrong_parent':return replace(event,predecessor_id='f'*64)
            if attack=='foreign_session':return replace(event,session_id='f'*64)
            return replace(event,completed_step=2,barrier_seq=2)
        s.emit=bad;return s
    d._make_session=changed; result=d.run(3,'barrier')
    generation=int(attack=='duplicate_barrier')
    stopped(evidence,attack,d,result,generation,[1,2] if generation else [1])

@pytest.mark.parametrize('exc',[RuntimeError('checker crash'),TimeoutError('checker timeout'),MemoryError('resource refusal')],ids=['checker_crash','checker_timeout','resource_refusal'])
def test_checker_failure_stops_before_next_body(tmp_path,evidence,exc):
    d=marker_driver(tmp_path,gate=MarkerGate(exception=exc)); result=d.run(3,'failure')
    stopped(evidence,str(exc),d,result,0,[1])

@pytest.mark.parametrize('point,generation',[('before_current_replace',0),('after_current_replace_before_token',1),('after_token_before_resume',1)])
def test_exact_current_crash_boundary(tmp_path,evidence,point,generation):
    def crash(where):
        if where==point:raise RuntimeError('controlled crash '+point)
    d=marker_driver(tmp_path,hook=crash)
    if generation==0:d.store._crash_hook=crash
    result=d.run(3,'crash'); stopped(evidence,point,d,result,generation,[1])

@pytest.mark.parametrize('attack',['foreign','checkpoint','skipped','generation','future','duplicate','unbound'])
def test_private_pipe_token_attacks_have_no_forward_body(tmp_path,evidence,attack):
    s=FixtureSession(ROOT,tmp_path/'worker',3,LEDGER)
    try:
        event=s.start(); token=certify_fixture(s,event,1)
        if attack=='duplicate':s.resume(token)
        with pytest.raises(ValueError) as refused:
            if attack=='foreign':token=replace(token,session_id='f'*64)
            elif attack=='checkpoint':token=replace(token,checkpoint_id='f'*64)
            elif attack=='skipped':token=replace(token,barrier_seq=3)
            elif attack=='generation':token=replace(token,predecessor_generation=2)
            elif attack=='future':token=replace(token,candidate_generation=3)
            elif attack=='unbound':s._binding=None
            s.resume(token)
        phase='TOKEN_CONSTRUCTION' if attack in ('skipped','generation','future') else 'SESSION_RESUME'
        if phase=='TOKEN_CONSTRUCTION':assert str(refused.value)=='token generation/sequence mismatch'
        forbidden=3 if attack=='duplicate' else 2
        assert not (s.run_root/f'body{forbidden}').exists()
        evidence.append({'attack':'token_'+attack,'scope':'REAL_MARKER_PROCESS_ONLY','verdict':'REFUSED','refusal_phase':phase,'reason':str(refused.value),'forbidden_body':forbidden,'forbidden_body_exists':False})
    finally:s.terminate('Task7 marker attack complete')

@pytest.fixture(scope='module')
def saved_edge(tmp_path_factory):
    base=tmp_path_factory.mktemp('task7-saved'); pred=chain_genesis(ROOT,3)
    cp,_,_=checkpoint(base/'cp',pred,1); out=base/'edge'
    build_edge(cp,pred,out,ROOT); report=check_edge(cp,out,pred,ROOT)
    assert report['verdict']=='CHECKER_PASS' and report['evidence_role']=='TEST_ONLY'
    return pred,cp,out,(out/'edge.json').read_bytes(),(out/'completion.json').read_bytes()

@pytest.mark.parametrize('attack',['q','full_v','latent','coefficient','box_reset','box_increase','form_reset','early_body','tdt_swap','gradient_omit','terminal_successor'])
def test_rehashed_saved_numeric_mutants_are_independently_refused(saved_edge,evidence,attack):
    pred,cp,out,original,completion=saved_edge; edge=json.loads(original); c=edge['candidate']
    if attack in ('q','full_v','latent'):c[attack+'_bits'][0]=OTHER
    elif attack=='coefficient':c['forms'][0]['coefficients'][0]='0x1.0000000000000p-52'
    elif attack=='box_reset':c['forms'][0]['box']='0x0.0p+0'
    elif attack=='box_increase':c['forms'][0]['box']='0x1.0000000000000p+0'
    elif attack=='form_reset':
        for form in c['forms']:form['coefficients']=['0x0.0p+0']*4; form['box']='0x0.0p+0'
    elif attack=='early_body':edge['native']['next_body_executed']=True
    elif attack=='tdt_swap':c['next_t_bits'],c['dt_bits']=c['dt_bits'],c['next_t_bits']
    elif attack=='gradient_omit':c.pop('gradient_bits')
    else:c['barrier_kind']='FINAL_TERMINAL';c['next_t_bits']=ZERO
    try:
        (out/'edge.json').write_bytes(canonical_bytes(edge));rehash_derived(out)
        report=check_edge(cp,out,pred,ROOT)
        evidence.append({'attack':'saved_'+attack,'scope':'TEST_ONLY_SAVED_NUMERICAL_EDGE','verdict':report['verdict'],'failure_stage':report.get('failure_stage'),'reason':report.get('reason')})
        assert report['verdict']=='REFUSED' and report['failure_stage']=='SEMANTIC',report
    finally:
        (out/'edge.json').write_bytes(original);(out/'completion.json').write_bytes(completion)

@pytest.mark.parametrize('attack',['latent','coefficient','box','t','dt','source','step'])
def test_equal_public_replay_cannot_hide_wrong_continuation(tmp_path,evidence,attack):
    d=prepared(tmp_path); before=inventory(d.store); fresh=replay_driver(d)
    class Changed(ReplayMarkerGate):
        def observe(self,*args):
            report=copy.deepcopy(super().observe(*args));c=report['candidate']
            if attack=='latent':
                c['latent_bits']=[OTHER,OTHER]
                for f in c['forms']:
                    if f['component']=='latent':f['center_bits']=OTHER
            elif attack=='coefficient':c['forms'][0]['coefficients'][0]='0x1.0000000000000p-52'
            elif attack=='box':c['forms'][0]['box']='0x1.0000000000000p-50'
            elif attack=='t':c['next_t_bits']=OTHER
            elif attack=='dt':c['dt_bits']=OTHER
            elif attack=='source':c['source_binding']='f'*64
            else:c['step_index']=2
            return report
    fresh._gate=Changed(); result=ReplayEngine(lambda:fresh,d.store).recover(4,'replay-mutation')
    stopped(evidence,'replay_'+attack,fresh,result,2,[1])
    assert inventory(d.store)==before

def test_replay_has_no_generation_or_acceptance_publication(tmp_path,evidence):
    d=prepared(tmp_path);before=inventory(d.store);fresh=replay_driver(d)
    fresh.store.publish=lambda *a,**k:pytest.fail('replay attempted to publish')
    result=ReplayEngine(lambda:fresh,d.store).recover(4,'replay-only',continue_live=False)
    assert result.verdict=='REPLAYED' and result.generation==2 and inventory(d.store)==before
    assert fresh.session.markers==[1,2]
    evidence.append({'attack':'replay_only_publication_trap','scope':'TEST_ONLY_REPLAY','verdict':'PASS','generation':2,'markers':[1,2],'store_byte_unchanged':True})

def test_replay_candidate_cannot_claim_acceptance(tmp_path,evidence):
    d=prepared(tmp_path);before=inventory(d.store);fresh=replay_driver(d)
    class Claimed(ReplayMarkerGate):
        def observe(self,*args):
            report=copy.deepcopy(super().observe(*args));report['candidate']['acceptance_id']='f'*64
            return report
    fresh._gate=Claimed();result=ReplayEngine(lambda:fresh,d.store).recover(4,'claimed')
    stopped(evidence,'replay_acceptance_claim',fresh,result,2,[1]);assert inventory(d.store)==before

def test_altered_stored_certificate_refuses_before_fresh_process(tmp_path,evidence):
    d=prepared(tmp_path);identity=d.store.current()[0];pointer=(d.store.root/'CURRENT').read_bytes()
    p=d.store.root/'objects'/(identity+'.json');p.chmod(0o600);p.write_bytes(b'{}')
    fresh=replay_driver(d);fresh._make_session=lambda *a:pytest.fail('corrupt history started replay')
    with pytest.raises(ValueError):ReplayEngine(lambda:fresh,d.store).recover(4,'corrupt')
    assert (d.store.root/'CURRENT').read_bytes()==pointer and fresh.session is None
    evidence.append({'attack':'altered_stored_certificate','scope':'TEST_ONLY_STORE','verdict':'REFUSED','raw_CURRENT_pointer_unchanged':True,'fresh_process_started':False})

def test_cross_process_live_publication_without_transition_refuses(tmp_path,evidence):
    d=prepared(tmp_path);parent=d.store.current()[1];before=inventory(d.store)
    child,receipt=successor(parent,session='f'*64)
    with pytest.raises(ValueError):d.store.publish(parent.content_hash,child,receipt)
    assert inventory(d.store)==before and d.store.current()[1].generation==2 and d.session.markers==[1,2,3]
    evidence.append({'attack':'cross_process_without_transition','scope':'TEST_ONLY_STORE','verdict':'REFUSED','generation':2,'markers':[1,2,3],'body4_exists':False})
