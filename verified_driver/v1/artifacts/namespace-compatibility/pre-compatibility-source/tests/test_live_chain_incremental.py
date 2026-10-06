from dataclasses import replace
import json
import pytest
from runtime_trace.live_chain.producer import build_edge
from runtime_trace.live_chain.checker import check_edge
from verified_driver.v1.model import chain_genesis, canonical_bytes
from tests.verified_driver_v1_support import ROOT, ZERO
from tests.live_chain_fixture import checkpoint, observed_state, rehash_derived, rehash_checkpoint, CASE

def first(tmp_path):
    pred=chain_genesis(ROOT,3); capture,identity,event=checkpoint(tmp_path/'cp1',pred,1)
    out=tmp_path/'derived1'; report=build_edge(capture,pred,out,ROOT)
    return pred,capture,out,report

def test_saved_original_three_edges_preserve_hidden_state_and_final_boundary(tmp_path):
    pred=chain_genesis(ROOT,3); states=[]
    original=json.loads((CASE/'capture.json').read_bytes())
    for k in (1,2,3):
        cp,identity,event=checkpoint(tmp_path/f'cp{k}',pred,k); out=tmp_path/f'edge{k}'
        build_edge(cp,pred,out,ROOT); report=check_edge(cp,out,pred,ROOT)
        assert report['verdict']=='CHECKER_PASS',report
        state=observed_state(report)
        assert state.q_bits==tuple(original['regions'][k]['end_state']['q'])
        assert state.full_v_bits==tuple(original['regions'][k]['end_state']['full_v'])
        assert state.latent_bits==tuple(original['regions'][k]['end_state']['latent'])
        assert state.predecessor_id==pred.content_hash and state.barrier_seq==k
        assert len(state.forms)==6
        assert report['evidence_role']=='TEST_ONLY'
        states.append(state); pred=state
    assert pred.barrier_kind=='FINAL_TERMINAL' and pred.next_t_bits is None
    assert states[0].full_v_bits!=states[0].latent_bits

@pytest.mark.parametrize('attack',['latent','coefficient','box_reset','form_reset','early_body','tdt','gradient','final_successor'])
def test_rehashed_candidate_mutations_fail_semantically(tmp_path,attack):
    pred,cp,out,report=first(tmp_path)
    edge=json.loads((out/'edge.json').read_bytes())
    if attack=='latent': edge['candidate']['latent_bits'][0]=ZERO
    elif attack=='coefficient': edge['candidate']['forms'][0]['coefficients'][0]='0x1.0000000000000p-52'
    elif attack=='box_reset': edge['candidate']['forms'][0]['box']='0x0.0p+0'
    elif attack=='form_reset':
        for f in edge['candidate']['forms']: f['coefficients']=['0x0.0p+0']*4; f['box']='0x0.0p+0'
    elif attack=='early_body': edge['native']['next_body_executed']=True
    elif attack=='tdt': edge['candidate']['next_t_bits']=edge['candidate']['dt_bits']
    elif attack=='gradient': edge['candidate']['gradient_bits'][0]='0x3ff0000000000000'
    else: edge['candidate']['barrier_kind']='FINAL_TERMINAL'; edge['candidate']['next_t_bits']=ZERO
    (out/'edge.json').write_bytes(canonical_bytes(edge)); rehash_derived(out)
    rejected=check_edge(cp,out,pred,ROOT)
    assert rejected['verdict']=='REFUSED' and rejected['failure_stage']=='SEMANTIC',rejected

@pytest.mark.parametrize('attack',['foreign_session','wrong_predecessor','wrong_latent_predecessor','prefix_mismatch','next_entry_t','gradient_omit'])
def test_live_checkpoint_substitution_and_hidden_handoff_refuse(tmp_path,attack):
    _,_,_,first_report=first(tmp_path); pred=observed_state(first_report)
    cp,identity,event=checkpoint(tmp_path/'cp2',pred,2)
    doc=json.loads((cp/'checkpoint.json').read_bytes())
    if attack=='foreign_session': doc['event']['session_id']='e'*64; doc['metadata']['capture']['acquisition_id']='e'*64
    elif attack=='wrong_predecessor': doc['event']['predecessor_id']='e'*64
    elif attack=='wrong_latent_predecessor':
        pred=replace(pred,latent_bits=(ZERO,ZERO),forms=tuple(replace(f,center_bits=ZERO) if f.component=='latent' else f for f in pred.forms))
        doc['event']['predecessor_id']=pred.content_hash
    elif attack=='prefix_mismatch': doc['event']['trace_prefix_sha256']='e'*64
    elif attack=='next_entry_t': doc['event']['checkpoint_state']['t_bits']=ZERO
    else: doc['event']['checkpoint_state'].pop('gradient')
    p=cp/'checkpoint.json'; p.chmod(0o600); p.write_bytes(canonical_bytes(doc)); rehash_checkpoint(cp)
    report=check_edge(cp,tmp_path/'absent',pred,ROOT)
    assert report['verdict']=='REFUSED',report

@pytest.mark.parametrize('counter',['scalar_fp_count','opcode_histogram'])
def test_rehashed_acquisition_counters_refuse(tmp_path,counter):
    pred,cp,out,report=first(tmp_path)
    doc=json.loads((cp/'checkpoint.json').read_bytes())
    doc['metadata']['capture'][counter]=0 if counter=='scalar_fp_count' else {}
    p=cp/'checkpoint.json'; p.chmod(0o600); p.write_bytes(canonical_bytes(doc)); rehash_checkpoint(cp)
    edge=json.loads((out/'edge.json').read_bytes()); edge['checkpoint_id']=(cp/'CHECKPOINT').read_text().strip()
    (out/'edge.json').write_bytes(canonical_bytes(edge)); rehash_derived(out)
    rejected=check_edge(cp,out,pred,ROOT)
    assert rejected['verdict']=='REFUSED' and rejected['failure_stage']=='RAW',rejected
