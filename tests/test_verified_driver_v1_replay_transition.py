"""Narrow transition attachment authority and durable crash recovery."""
from dataclasses import replace
import copy
import pytest
from verified_driver.v1.model import canonical_bytes, content_id, digest_bytes
from tests.verified_driver_v1_support import successor
from tests.verified_driver_v1_replay_support import prepared,proof_document,transitioned_child,replay_driver

def inventory(store):
    return {str(p.relative_to(store.root)):p.read_bytes() for p in store.root.rglob('*') if p.is_file() and p.name!='.lock'}

def receipt_for(state,tid):
    r=canonical_bytes({'schema':'VERIFIED_CHAIN_ACCEPTANCE_V1','verdict':'ACCEPT',
       'candidate':state.candidate_document(),'predecessor_id':state.predecessor_id,
       'checkpoint_id':'4'*64,'edge_completion_sha256':'e'*64,'replay_transition_id':tid})
    return replace(state,acceptance_id=digest_bytes(r)),r

def test_complete_replay_only_creates_no_store_generation_objects_or_acceptance(tmp_path):
    from verified_driver.v1.replay import ReplayEngine
    driver=prepared(tmp_path); before=inventory(driver.store); fresh=replay_driver(driver)
    result=ReplayEngine(lambda:fresh,driver.store).recover(4,'replay-only',continue_live=False)
    assert result.verdict=='REPLAYED' and result.generation==2
    assert inventory(driver.store)==before and fresh.session.markers==[1,2]

def test_valid_transition_publishes_exactly_one_new_generation_and_recovers(tmp_path):
    driver=prepared(tmp_path); parent=driver.store.current()[1]; doc=proof_document(driver)
    tid=driver.store.add_replay_transition(doc); child,receipt=transitioned_child(driver,doc)
    before=len(list((driver.store.root/'objects').glob('*.json')))
    driver.store.publish(parent.content_hash,child,receipt)
    assert driver.store.recover()[1]==child
    assert len(list((driver.store.root/'objects').glob('*.json')))==before+1
    assert driver.store.publish(parent.content_hash,child,receipt)==child.content_hash

@pytest.mark.parametrize('field,value',[
 ('latent_bits',['0x3fc0000000000000']*2),('next_t_bits','0x3fa0000000000000'),
 ('dt_bits','0x3fa0000000000000'),('source_binding','f'*64),('step_index',1),
 ('form_box','0x1.0000000000000p-53'),('form_coefficient','0x1.0000000000000p-54')])
def test_repaired_attachment_hashes_cannot_hide_semantic_mutation(tmp_path,field,value):
    driver=prepared(tmp_path); doc=copy.deepcopy(proof_document(driver)); fresh=doc['fresh_anchor']
    if field=='form_box': fresh['forms'][0]['box']=value
    elif field=='form_coefficient': fresh['forms'][0]['coefficients'][0]=value
    else: fresh[field]=value
    doc['replay_proofs'][-1]['checker_report']['candidate']=copy.deepcopy(fresh)
    doc['replay_proofs'][-1]['checker_report_sha256']=content_id(doc['replay_proofs'][-1]['checker_report'])
    with pytest.raises(ValueError): driver.store.add_replay_transition(doc)

@pytest.mark.parametrize('attack',['absent','partial','wrong_parent','wrong_session','wrong_process','prefix','frontier'])
def test_transition_refuses_missing_partial_foreign_or_nonforward_child(tmp_path,attack):
    driver=prepared(tmp_path); parent=driver.store.current()[1]; doc=proof_document(driver)
    if attack=='partial':
        doc['replay_proofs'].pop(0)
        with pytest.raises(ValueError): driver.store.add_replay_transition(doc)
        return
    if attack!='absent': driver.store.add_replay_transition(doc)
    child,receipt=transitioned_child(driver,doc)
    if attack=='wrong_parent':
        parent=driver.store.chain()[1]; child,_=successor(parent,session='f'*64)
    if attack=='wrong_session':
        child=replace(child,live_session_id='8'*64,live_basis_namespace='8'*64+'/global-error-basis')
    if attack=='wrong_process': child=replace(child,process_identity_digest='8'*64)
    if attack=='prefix': child=replace(child,trace_prefix_bytes=doc['fresh_anchor']['trace_prefix_bytes'])
    if attack=='frontier': child=replace(child,verified_frontier=doc['fresh_anchor']['verified_frontier'])
    child,receipt=receipt_for(child,content_id(doc))
    with pytest.raises(ValueError): driver.store.publish(parent.content_hash,child,receipt)
    assert driver.store.current()[1].generation==2

def test_cross_session_without_transition_and_second_child_reuse_refuse(tmp_path):
    driver=prepared(tmp_path); parent=driver.store.current()[1]; doc=proof_document(driver)
    tid=driver.store.add_replay_transition(doc); child,receipt=transitioned_child(driver,doc)
    without=__import__('json').loads(receipt); without.pop('replay_transition_id')
    with pytest.raises(ValueError): driver.store.publish(parent.content_hash,replace(child,acceptance_id=digest_bytes(canonical_bytes(without))),canonical_bytes(without))
    driver.store.publish(parent.content_hash,child,receipt)
    second,_=successor(child,final=True,session=child.live_session_id)
    second,receipt2=receipt_for(second,tid)
    with pytest.raises(ValueError): driver.store.publish(child.content_hash,second,receipt2)
    assert driver.store.current()[1]==child

@pytest.mark.parametrize('point,generation',[('before_current_replace',2),('after_current_replace',3)])
def test_transition_pre_and_post_current_crash_recovery(tmp_path,point,generation):
    driver=prepared(tmp_path); parent=driver.store.current()[1]; doc=proof_document(driver)
    driver.store.add_replay_transition(doc); child,receipt=transitioned_child(driver,doc)
    def crash(where):
        if where==point: raise RuntimeError('controlled crash')
    driver.store._crash_hook=crash
    with pytest.raises(RuntimeError): driver.store.publish(parent.content_hash,child,receipt)
    assert driver.store.recover()[1].generation==generation
    if generation==3:
        p=driver.store.root/'replay_transitions'/(content_id(doc)+'.json')
        p.chmod(0o600); p.write_bytes(b'{}')
        with pytest.raises(ValueError): driver.store.recover()

def test_terminal_replay_never_creates_transition_or_successor(tmp_path):
    from verified_driver.v1.replay import ReplayEngine
    from tests.verified_driver_v1_control_support import marker_driver
    driver=marker_driver(tmp_path,3); assert driver.run(3,'original').verdict=='ACCEPT'
    before=inventory(driver.store); fresh=replay_driver(driver)
    result=ReplayEngine(lambda:fresh,driver.store).recover(3,'terminal-replay')
    assert result.verdict=='ACCEPT' and result.generation==3
    assert inventory(driver.store)==before and fresh.session.markers==[1,2,3]
    with pytest.raises(ValueError): driver.store.add_replay_transition(proof_document(driver))

def test_replay_to_live_preserves_historical_parent_then_normal_links(tmp_path):
    from verified_driver.v1.replay import ReplayEngine
    driver=prepared(tmp_path); old=driver.store.current()[0]; fresh=replay_driver(driver)
    result=ReplayEngine(lambda:fresh,driver.store).recover(4,'recover-live')
    assert result.verdict=='ACCEPT' and result.generation==4
    chain=driver.store.chain(); assert chain[3].predecessor_id==old
    import json
    first=json.loads((driver.store.root/'receipts'/(chain[3].acceptance_id+'.json')).read_bytes())
    following=json.loads((driver.store.root/'receipts'/(chain[4].acceptance_id+'.json')).read_bytes())
    assert 'replay_transition_id' in first and 'replay_transition_id' not in following

def test_transition_from_another_historical_store_parent_is_refused(tmp_path):
    driver=prepared(tmp_path/'one'); document=proof_document(driver)
    other=prepared(tmp_path/'two',target=1)
    before=inventory(other.store)
    with pytest.raises(ValueError): other.store.add_replay_transition(document)
    assert inventory(other.store)==before

def test_substituted_transition_bytes_refuse_even_after_valid_publication(tmp_path):
    driver=prepared(tmp_path); parent=driver.store.current()[1]; document=proof_document(driver)
    tid=driver.store.add_replay_transition(document); child,receipt=transitioned_child(driver,document)
    driver.store.publish(parent.content_hash,child,receipt)
    path=driver.store.root/'replay_transitions'/(tid+'.json')
    path.chmod(0o600); mutated=copy.deepcopy(document)
    mutated['fresh_anchor']['process_identity_digest']='9'*64
    path.write_bytes(canonical_bytes(mutated))
    with pytest.raises(ValueError): driver.store.recover()
