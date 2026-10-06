"""Transactional controls with saved evidence; no fresh numerical claim."""
from pathlib import Path
import pytest
from verified_driver.v0.driver import VerifiedDriver
from verified_driver.v0.fallback import FallbackRegistry
from verified_driver.v0.model import regular_genesis
from verified_driver.v0.store import CertifiedStore
from verified_driver_v0_support import ROOT,BITS,test_runner as saved_runner,load,dump,control

def make_driver(tmp_path):
    store=CertifiedStore(tmp_path/'certified')
    store.initialize(regular_genesis(ROOT))
    driver=VerifiedDriver(ROOT,store,tmp_path/'pending',tmp_path/'unused-ledger.json')
    # TEST_ONLY: controlled runner metadata allocation, not a new execution ledger.
    driver._admit_segment=lambda out:{'remaining':8*1048576}
    return driver

def test_candidate_has_no_authority_before_check_and_accept_commits_once(tmp_path):
    driver=make_driver(tmp_path); before=driver.store.current()
    def inspect():
        assert driver.store.current()==before
        assert load(driver.pending_root/'normal'/'transaction.json')['predecessor_id']==before[0]
    saved_runner(driver,inspect=inspect)
    result=driver.transact(10,'normal')
    assert result.verdict=='ACCEPT',result.reason
    identity,state=driver.store.current()
    assert state.generation==1 and state.state_bits==BITS and identity==result.state_id
    assert (driver.store.root/'receipts'/(state.acceptance_id+'.json')).exists()
    restarted=make_driver(tmp_path)
    restarted._run_segment=lambda *args: pytest.fail('completed transaction reran external calculation')
    retry=restarted.transact(10,'normal')
    assert retry.verdict=='ACCEPT' and retry.state_id==identity and retry.generation==1

@pytest.mark.parametrize('failure',['refused','exception','resource'])
def test_failure_preserves_authority_and_defaults_stop(tmp_path,failure):
    driver=make_driver(tmp_path); before=driver.store.current()
    def run(n,out):
        if failure=='exception': raise TimeoutError('checker timeout')
        return {'verdict':'REFUSED_RESOURCE' if failure=='resource' else 'REFUSED'}
    driver._run_segment=run
    result=driver.transact(10,'bad')
    assert result.verdict=='STOP' and driver.store.current()==before
    assert list((driver.store.root/'receipts').iterdir())==[]

def test_audit_only_does_not_change_result_or_current(tmp_path):
    driver=saved_runner(make_driver(tmp_path)); before=driver.store.current()
    candidate=driver.audit_only(10,tmp_path/'audit')
    assert candidate.state_bits==BITS and driver.store.current()==before

def test_empty_production_fallback(tmp_path):
    assert FallbackRegistry().resolve('invalid',{}) is None

@pytest.mark.parametrize('good',[True,False])
def test_test_only_fallback_requires_same_gate(tmp_path,good):
    driver=make_driver(tmp_path); before=driver.store.current()
    def run(n,out):
        from verified_driver_v0_support import copy_control
        observed=copy_control(out)
        if out.name=='fallback' and not good:
            h=load(out/'capture/harness_output.json'); h['output_bits'][0]='0x3fa3eaff7788ac23'; dump(out/'capture/harness_output.json',h)
        if out.name!='fallback': return {'verdict':'REFUSED','reason':'controlled'}
        return observed
    driver._run_segment=run
    class TestOnly(FallbackRegistry):
        def resolve(self,reason,context):
            # A controller-run fallback, not a copied PASS or production solver.
            return context['validate_segment'](context['fallback_dir'])
    driver.fallback=TestOnly()
    result=driver.transact(10,'fallback-tx')
    assert result.verdict==('ACCEPT' if good else 'STOP')
    if not good: assert driver.store.current()==before

@pytest.mark.parametrize('steps',[True,0,101,1.0])
def test_invalid_request_never_starts_runner(tmp_path,steps):
    driver=make_driver(tmp_path); driver._run_segment=lambda *x: pytest.fail('invalid request ran')
    with pytest.raises(ValueError): driver.transact(steps,'invalid')

def test_pending_cannot_alias_certified_namespace(tmp_path):
    driver=make_driver(tmp_path)
    with pytest.raises(ValueError): VerifiedDriver(ROOT,driver.store,driver.store.root,driver.ledger)

def test_recovery_does_not_claim_arbitrary_gala_continuation(tmp_path):
    driver=saved_runner(make_driver(tmp_path)); assert driver.transact(10,'first').verdict=='ACCEPT'
    before=driver.store.current(); driver._run_segment=lambda *x: pytest.fail('arbitrary restart')
    assert driver.transact(10,'next').verdict=='STOP' and driver.store.current()==before
