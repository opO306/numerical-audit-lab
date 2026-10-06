"""Authority attacks exercise the real Driver/gate/store, saved runner only."""
from dataclasses import replace
import os
import subprocess
import sys
import pytest
from verified_driver.v0 import driver as implementation,gate
from verified_driver.v0.fallback import FallbackRegistry
from verified_driver.v0.gate import candidate_from_evidence
from verified_driver_v0_support import ROOT,BITS,load,dump,control,copy_control,rehash_completion,sha,test_runner as saved_runner
from test_verified_driver_v0_driver import make_driver

MUTANTS=('one_ulp','repaired_hashes','stale_pass','candidate_a_on_b','checker_skipped',
    'refused_forced_accept','malformed_report','resource_refusal','predecessor_swap')

def mutate(out,kind):
    if kind in ('one_ulp','repaired_hashes'):
        h=load(out/'capture/harness_output.json'); h['output_bits'][0]='0x3fa3eaff7788ac23'; dump(out/'capture/harness_output.json',h)
        if kind=='repaired_hashes':
            c=load(out/'derived/completion.json')
            next(x for x in c['final_endpoint'] if x['component']=='q' and x['byte_offset']==0)['center_bits']=h['output_bits'][0]
            dump(out/'derived/completion.json',c); rehash_completion(out)
            for name in ('fresh_checker_report.json','run_result.json'):
                v=load(out/name); v['completion_sha256']=load(out/'derived/completion.json')['completion_sha256']; dump(out/name,v)
    elif kind in ('stale_pass','candidate_a_on_b'):
        v=load(out/'fresh_checker_report.json'); v['completion_sha256']='f'*64; dump(out/'fresh_checker_report.json',v)
    elif kind=='checker_skipped': (out/'independent_check/execution.json').unlink()
    elif kind=='refused_forced_accept':
        v=load(out/'run_result.json'); v.update(verdict='REFUSED',requested_complete=False); dump(out/'run_result.json',v)
    elif kind=='malformed_report': (out/'fresh_checker_report.json').write_bytes(b'{"verdict":')
    elif kind=='resource_refusal':
        v=load(out/'independent_check/execution.json'); v['verdict']='REFUSED_RESOURCE'; dump(out/'independent_check/execution.json',v)
        v=load(out/'run_result.json'); v['stage_receipts'][2]=sha(out/'independent_check/execution.json'); dump(out/'run_result.json',v)
    elif kind=='predecessor_swap':
        # Extraction cannot overwrite the controller-owned binding.
        dump(out/'driver_binding.json',{'transaction_id':'foreign','predecessor_id':'a'*64})

@pytest.mark.parametrize('kind',MUTANTS)
def test_full_transaction_mutants_never_change_current(tmp_path,kind):
    driver=saved_runner(make_driver(tmp_path),lambda out:mutate(out,kind)); before=driver.store.current()
    result=driver.transact(10,'attack')
    assert result.verdict=='STOP' and driver.store.current()==before
    assert not list((driver.store.root/'receipts').iterdir())

@pytest.mark.parametrize('error',[TimeoutError('timeout'),RuntimeError('checker exception')])
def test_checker_exception_and_timeout_do_not_publish(tmp_path,error):
    driver=make_driver(tmp_path); before=driver.store.current()
    def run(*args): raise error
    driver._run_segment=run
    assert driver.transact(10,'exception').verdict=='STOP' and driver.store.current()==before

def test_publish_before_controller_check_is_denied(tmp_path):
    driver=make_driver(tmp_path); before,pred=driver.store.current()
    def run(n,out):
        foreign=control(tmp_path/'foreign','foreign',pred)
        candidate=candidate_from_evidence('foreign',before,foreign)
        with pytest.raises(ValueError,match='private controller'):
            driver._publish_candidate(candidate,pred)
        assert driver.store.current()==(before,pred)
        return copy_control(out)
    driver._run_segment=run
    assert driver.transact(10,'normal').verdict=='ACCEPT'

def test_fallback_without_controller_revalidation_cannot_publish(tmp_path):
    driver=make_driver(tmp_path); before,pred=driver.store.current()
    foreign=control(tmp_path/'foreign','bad-fallback',pred)
    stale=candidate_from_evidence('bad-fallback',before,foreign)
    class TestOnly(FallbackRegistry):
        def resolve(self,*args): return stale
    driver.fallback=TestOnly(); driver._run_segment=lambda *x:{'verdict':'REFUSED'}
    assert driver.transact(10,'bad-fallback').verdict=='STOP' and driver.store.current()==(before,pred)

def test_previous_transaction_acceptance_receipt_is_not_reusable(tmp_path):
    a=saved_runner(make_driver(tmp_path/'a')); assert a.transact(10,'a').verdict=='ACCEPT'
    _,state=a.store.current(); data=(a.store.root/'receipts'/(state.acceptance_id+'.json')).read_bytes()
    b=saved_runner(make_driver(tmp_path/'b')); before=b.store.current()
    original=implementation.evaluate_candidate
    from verified_driver.v0.model import GateDecision
    implementation.evaluate_candidate=lambda *args:GateDecision('ACCEPT','stale',data)
    try: assert b.transact(10,'b').verdict=='STOP' and b.store.current()==before
    finally: implementation.evaluate_candidate=original

@pytest.mark.parametrize('pointer',[b'abc',b'f'*64+b'\n'])
def test_corrupt_pointer_fails_closed(tmp_path,pointer):
    driver=make_driver(tmp_path); before=driver.store.current()
    (driver.store.root/'CURRENT').write_bytes(pointer)
    with pytest.raises(ValueError): driver.transact(10,'bad-current')
    assert (driver.store.root/'objects'/(before[0]+'.json')).exists()

@pytest.mark.parametrize('point',['after_objects','before_replace','after_replace'])
def test_actual_process_exit_recovers_only_complete_generation(tmp_path,point):
    driver=make_driver(tmp_path); before=driver.store.current()
    # Same real Driver path, terminated by os._exit: no Python cleanup/catch.
    code='''import os,sys
sys.path.insert(0,str(__import__('pathlib').Path.cwd()/'tests'))
from test_verified_driver_v0_driver import make_driver
from verified_driver_v0_support import test_runner
from pathlib import Path
d=test_runner(make_driver(Path(sys.argv[1])))
d.store._crash_hook=lambda p:os._exit(73) if p==sys.argv[2] else None
d.transact(10,'crash')
'''
    process=subprocess.run([sys.executable,'-c',code,str(tmp_path),point],cwd=ROOT,timeout=15)
    assert process.returncode==73
    recovered=driver.store.recover()
    if point=='after_replace':
        assert recovered[1].generation==1 and recovered[1].state_bits==BITS
        assert driver.transact(10,'crash').verdict=='ACCEPT'
    else: assert recovered==before

def test_source_change_during_transaction_refuses(tmp_path,monkeypatch):
    driver=make_driver(tmp_path); before=driver.store.current(); original=implementation.source_snapshot
    changed=False
    def snapshot(root):
        value=original(root)
        if changed: value['driver']['verified_driver/v0/driver.py']='a'*64
        return value
    monkeypatch.setattr(implementation,'source_snapshot',snapshot); monkeypatch.setattr(gate,'source_snapshot',snapshot)
    def run(n,out):
        nonlocal changed
        observed=copy_control(out); changed=True; return observed
    driver._run_segment=run
    assert driver.transact(10,'changed').verdict=='STOP' and driver.store.current()==before

def test_fallback_cannot_reset_pretransaction_source_binding(tmp_path,monkeypatch):
    driver=make_driver(tmp_path); before=driver.store.current(); original=implementation.source_snapshot
    changed=False
    def snapshot(root):
        value=original(root)
        if changed: value['driver']['verified_driver/v0/driver.py']='a'*64
        return value
    monkeypatch.setattr(implementation,'source_snapshot',snapshot); monkeypatch.setattr(gate,'source_snapshot',snapshot)
    def run(n,out):
        nonlocal changed
        if out.name!='fallback': changed=True; return {'verdict':'REFUSED'}
        return copy_control(out)
    class TestOnly(FallbackRegistry):
        def resolve(self,reason,context): return context['validate_segment'](context['fallback_dir'])
    driver._run_segment=run; driver.fallback=TestOnly()
    assert driver.transact(10,'changed-fallback').verdict=='STOP' and driver.store.current()==before

def test_production_adapter_cannot_start_with_new_budget_ledger(tmp_path,monkeypatch):
    driver=make_driver(tmp_path); out=tmp_path/'raw'; out.mkdir()
    import runtime_trace.regular_nstep.resources as resources
    monkeypatch.setattr(resources,'run_guarded',lambda *a,**k:pytest.fail('unapproved ledger reached execution'))
    with pytest.raises(ValueError,match='existing approved ledger'): driver._run_segment(1,out)

def test_fallback_cannot_publish_a_different_controller_transaction(tmp_path):
    driver=make_driver(tmp_path); before,pred=driver.store.current()
    def run(n,out):
        return copy_control(out) if out.name=='foreign' else {'verdict':'REFUSED'}
    class TestOnly(FallbackRegistry):
        def resolve(self,reason,context):
            return driver._collect(10,'foreign',pred,tmp_path/'foreign')
    driver._run_segment=run; driver.fallback=TestOnly()
    result=driver.transact(10,'expected')
    assert result.verdict=='STOP' and driver.store.current()==(before,pred)

def test_dangling_current_alias_is_refused_without_reset(tmp_path):
    driver=make_driver(tmp_path); pointer=driver.store.root/'CURRENT'
    pointer.unlink(); pointer.symlink_to(tmp_path/'unknown-pointer-target')
    with pytest.raises(ValueError): make_driver(tmp_path)
    assert pointer.is_symlink() and not (tmp_path/'unknown-pointer-target').exists()

def test_production_evidence_must_remain_in_accounted_driver_namespace(tmp_path,monkeypatch):
    # A toy ledger is only to exercise path validation; subprocess execution is intercepted.
    import runtime_trace.regular_nstep.resources as resources
    d=object.__new__(implementation.VerifiedDriver); d.repo_root=tmp_path/'root'
    d.ledger=d.repo_root/'runtime_trace/regular_nstep/artifacts/budget.json'
    dump(d.ledger,{'used_seconds':0,'jobs':[],'TEST_ONLY':True})
    (tmp_path/'outside').mkdir()
    monkeypatch.setattr(implementation,'source_snapshot',lambda *a:{'runtime':{}})
    monkeypatch.setattr(resources,'run_guarded',lambda *a,**k:pytest.fail('unaccounted output reached execution'))
    with pytest.raises(ValueError,match='accounted Driver evidence'): d._run_segment(1,tmp_path/'outside')
