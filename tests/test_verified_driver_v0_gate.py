from dataclasses import replace
from pathlib import Path
import pytest
from verified_driver.v0.model import regular_genesis
from verified_driver.v0.gate import candidate_from_evidence, evaluate_candidate
from verified_driver_v0_support import ROOT,BITS,bind_control,control,dump,load,rehash_completion,sha

def fixture(tmp_path):
    pred=regular_genesis(ROOT); out=control(tmp_path/'evidence','tx-a',pred)
    return pred,out,candidate_from_evidence('tx-a',pred.content_hash,out)

def test_passing_saved_control_binds_exact_checked_four_bits(tmp_path):
    pred,out,c=fixture(tmp_path)
    decision=evaluate_candidate(c,pred,ROOT)
    assert decision.verdict=='ACCEPT' and c.state_bits==BITS
    assert load_bytes(decision.acceptance_bytes)['candidate_id']==c.content_hash

def load_bytes(data):
    import json
    return json.loads(data)

def test_stale_checker_reuse_from_other_transaction_refuses(tmp_path):
    pred,out,c=fixture(tmp_path)
    stale=replace(c,transaction_id='tx-b')
    assert evaluate_candidate(stale,pred,ROOT).verdict=='REFUSE'

def test_one_ulp_candidate_and_repaired_content_id_refuses(tmp_path):
    pred,out,c=fixture(tmp_path)
    bad=replace(c,state_bits=('0x3fa3eaff7788ac23',*c.state_bits[1:]))
    assert bad.content_hash!=c.content_hash
    decision=evaluate_candidate(bad,pred,ROOT)
    assert decision.verdict=='REFUSE' and 'terminal output' in decision.reason

def test_wrong_predecessor_refuses(tmp_path):
    pred,out,c=fixture(tmp_path)
    assert evaluate_candidate(replace(c,predecessor_id='f'*64),pred,ROOT).verdict=='REFUSE'

@pytest.mark.parametrize('mutation',['harness','prefix','false-complete','resource','completion-digest','old-pass'])
def test_wrong_binding_or_incomplete_evidence_refuses(tmp_path,mutation):
    pred,out,c=fixture(tmp_path)
    if mutation=='harness':
        p=out/'integration_source_pinset.json'; d=load(p); d['runtime_trace/harness.py']='f'*64; dump(p,d)
    elif mutation in ('prefix','false-complete','old-pass'):
        p=out/'fresh_checker_report.json'; d=load(p)
        d['checked_steps']=1 if mutation=='prefix' else 10
        if mutation=='false-complete': d['requested_complete']=False
        if mutation=='old-pass': d['completion_sha256']='f'*64
        dump(p,d)
    elif mutation=='resource':
        p=out/'independent_check/execution.json'; d=load(p); d['verdict']='REFUSED'; d['resource_failure']='wall ceiling'; dump(p,d)
    else:
        p=out/'derived/completion.json'; d=load(p); d['final_endpoint'][0]['center_bits']='0x3fa3eaff7788ac23'; dump(p,d)
    assert evaluate_candidate(c,pred,ROOT).verdict=='REFUSE'

@pytest.mark.parametrize('bad',[b'{"verdict":"CHECKER_PASS","verdict":"REFUSED"}',b'{"x":NaN}',b'{"x":1e999}',b'{bad'])
def test_duplicate_nonfinite_or_malformed_json_refuses(tmp_path,bad):
    pred,out,c=fixture(tmp_path)
    (out/'fresh_checker_report.json').write_bytes(bad)
    assert evaluate_candidate(c,pred,ROOT).verdict=='REFUSE'

def test_mutated_terminal_and_repaired_hashes_cannot_reuse_old_pass(tmp_path):
    pred,out,c=fixture(tmp_path)
    h=load(out/'capture/harness_output.json'); h['output_bits'][0]='0x3fa3eaff7788ac23'; dump(out/'capture/harness_output.json',h)
    d=load(out/'derived/completion.json'); d['final_endpoint'][0]['center_bits']=h['output_bits'][0]; dump(out/'derived/completion.json',d)
    rehash_completion(out)
    bad=replace(c,state_bits=tuple(h['output_bits']))
    assert evaluate_candidate(bad,pred,ROOT).verdict=='REFUSE'
