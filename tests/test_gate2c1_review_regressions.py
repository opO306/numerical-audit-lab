import copy
import json
import sys
from pathlib import Path
import pytest
from test_gate2c1_independent import ind
from test_gate2c1_package import pkg

ROOT=Path(__file__).resolve().parents[1]

def test_local_missing_extra_and_changed_bounds_rejected():
    p=json.loads((ROOT/'reports/gate2c1-development-20-2026-10-02/evidence/exact/regular_0_8step.json').read_bytes())
    st=dict(zip(ind.STATE,[int(x,16) for x in p['start_latent']]))
    d=ind.local_check(st)
    ind.compare_local(p,d,st,'regular',0)
    for mutation in ('empty','short','extra','bound','input'):
        bad=copy.deepcopy(p)
        if mutation=='empty':bad['records']=[]
        elif mutation=='short':bad['records'].pop()
        elif mutation=='extra':bad['records'].append(bad['records'][0])
        elif mutation=='bound':bad['records'][0]['output_bounds']=['0x0.0p+0']*4
        else:bad['records'][0]['represented_input_latent'][0]='3ff0000000000000'
        with pytest.raises(ValueError):ind.compare_local(bad,d,st,'regular',0)

def test_trace_address_occurrence_ordinal_and_forms_mutants(tmp_path):
    from benchmarks.gate2c1.binary_replay import BinaryReplay
    t=BinaryReplay();regs=t.init(*(ind.bits(v) for v in (0.,0.,.25,.125)))
    d={'phase':'init','operations':t.trace('init',regs),'v2_input_forms':ind.bf(ind.zero_forms())}
    p=tmp_path/'trace.json'
    p.write_text(json.dumps(d));ind.compare_trace(p,ind.INIT,regs)
    for field,value in [('machine_address','ffff'),('instruction_occurrence','wrong'),('ordinal',99)]:
        bad=copy.deepcopy(d);bad['operations'][3][field]=value;p.write_text(json.dumps(bad))
        with pytest.raises(ValueError):ind.compare_trace(p,ind.INIT,regs)
    d['v2_input_forms']=[];p.write_text(json.dumps(d))
    with pytest.raises(ValueError):ind.compare_trace(p,ind.INIT,regs)

def valid_orbit(n=20):
    return {'steps_recomputed':n,'certified_prefix':n,'first_refused':None,'cross_first_refused':None,
            'raw_violation_count':0,'replay_mismatch_count':0,
            'connections':[{'coverage':[1,n],'recomputed_endpoint_equal':True,'decision_digest_equal':True}],
            'exact_local_windows':{'0':{'violations':0,'steps':8}}}

def test_violation_or_incomplete_coverage_cannot_succeed():
    good={k:valid_orbit() for k in ('regular','chaotic')}
    assert ind.verification_verdict(good,20,None)=='PASS'
    for key in ('raw_violation_count','replay_mismatch_count'):
        bad=copy.deepcopy(good);bad['chaotic'][key]=1
        assert ind.verification_verdict(bad,20,None)=='FAIL'
    bad=copy.deepcopy(good);bad['regular']['exact_local_windows']['0']['violations']=1
    assert ind.verification_verdict(bad,20,None)=='FAIL'
    bad=copy.deepcopy(good);bad['regular']['steps_recomputed']=19
    assert ind.verification_verdict(bad,20,None)!='PASS'
    bad=copy.deepcopy(good);bad['regular']['certified_prefix']=19
    assert ind.verification_verdict(bad,20,None)!='PASS'

def test_pre_and_post_seal_failure_report_preserves_results(tmp_path,monkeypatch):
    for stage in ('before','after'):
        out=tmp_path/stage
        monkeypatch.setattr(sys,'argv',['checker','--n','20','--producer',str(tmp_path),'--out',str(out)])
        def seal_check(n,s=stage):
            seal_check.calls+=1
            if (s=='before' and seal_check.calls==1) or (s=='after' and seal_check.calls==2):raise ValueError('injected seal failure')
        seal_check.calls=0
        monkeypatch.setattr(ind,'validate_seals',seal_check)
        monkeypatch.setattr(ind,'budget_deadline',lambda *args:float('inf'))
        monkeypatch.setattr(ind,'verify_orbit',lambda *args:valid_orbit())
        assert ind.main()==1
        d=json.loads((out/'independent_report.json').read_bytes())
        assert d['verification_verdict']=='FAIL' and d['seal_failures'][0]['stage']==stage
        assert bool(d['orbits'])==(stage=='after')

def test_combined_budget_uses_producer_time(tmp_path):
    (tmp_path/'gate2c1_report.json').write_text(json.dumps({'total_wall_seconds':317.}))
    assert ind.budget_deadline(tmp_path,10.)==3293.
    (tmp_path/'gate2c1_report.json').write_text(json.dumps({'total_wall_seconds':float('nan')}))
    with pytest.raises(ValueError):ind.budget_deadline(tmp_path,10.)

def test_all_full_coverage_segments_are_required():
    segment_paths=[p for p in pkg.REQUIRED if '/segments/' in p]
    assert len(segment_paths)==400
    assert pkg.P+'/evidence/segments/regular/100000.json' in segment_paths
    assert pkg.I+'/segments/chaotic/100000.json' in segment_paths
