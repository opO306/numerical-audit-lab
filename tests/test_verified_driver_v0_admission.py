"""Reviewer findings: refuse before any unowned/unreserved evidence write."""
import shutil
import pytest
from verified_driver.v0.driver import VerifiedDriver
from verified_driver.v0.store import CertifiedStore
from verified_driver.v0 import driver as implementation
from verified_driver_v0_support import ROOT,dump,sha

def inventory(root):
    return {str(p.relative_to(root)):sha(p) for p in root.rglob('*') if p.is_file()}

def test_existing_historical_directory_is_never_given_failure_metadata(tmp_path):
    history=tmp_path/'historical'; child=history/'old'; child.mkdir(parents=True)
    (child/'original.json').write_bytes(b'{"sealed":true}')
    store=CertifiedStore(tmp_path/'store')
    driver=VerifiedDriver(ROOT,store,history,tmp_path/'unused-ledger.json')
    before=inventory(history); state=store.current()
    assert driver.transact(1,'old').verdict=='STOP'
    assert inventory(history)==before and store.current()==state

def test_outside_namespace_refusal_creates_no_evidence(tmp_path):
    driver=VerifiedDriver(ROOT,CertifiedStore(tmp_path/'store'),tmp_path/'outside',tmp_path/'unused.json')
    before=driver.store.current()
    assert driver.transact(1,'new').verdict=='STOP'
    assert not (tmp_path/'outside').exists() and driver.store.current()==before

def toy_driver(tmp_path,monkeypatch,used=0):
    root=tmp_path/'repo'; harness=root/'runtime_trace/harness.py'; harness.parent.mkdir(parents=True)
    shutil.copyfile(ROOT/'runtime_trace/harness.py',harness)
    ledger=root/'runtime_trace/regular_nstep/artifacts/budget.json'; dump(ledger,{'used_seconds':used,'jobs':[],'TEST_ONLY':True})
    monkeypatch.setattr(implementation,'source_snapshot',lambda *args:{'runtime':{},'driver':{}})
    return VerifiedDriver(root,CertifiedStore(tmp_path/'store'),root/'verified_driver/v0/artifacts/pending',ledger)

def test_exhausted_storage_cannot_grow_refused_metadata(tmp_path,monkeypatch):
    driver=toy_driver(tmp_path,monkeypatch)
    import runtime_trace.regular_nstep.resources as resources
    original=resources.Limits
    monkeypatch.setattr(resources,'Limits',lambda **k:original(storage_bytes=1))
    monkeypatch.setattr(resources,'run_guarded',lambda *a,**k:pytest.fail('storage refusal started a numerical job'))
    before=driver.store.current(); artifacts=driver.repo_root/'verified_driver/v0/artifacts'
    for i in range(3): assert driver.transact(1,'full-'+str(i)).verdict=='STOP'
    assert not artifacts.exists() and driver.store.current()==before

def test_exhausted_time_cannot_create_metadata(tmp_path,monkeypatch):
    driver=toy_driver(tmp_path,monkeypatch,3600)
    import runtime_trace.regular_nstep.resources as resources
    def refused(*a,**k): raise resources.ResourceRefused('cumulative execution allowance exhausted')
    monkeypatch.setattr(resources,'run_guarded',refused)
    before=driver.store.current()
    for i in range(3): assert driver.transact(1,'time-'+str(i)).verdict=='STOP'
    assert not driver.pending_root.exists() and driver.store.current()==before

def test_audit_only_refuses_before_outside_path_write(tmp_path):
    driver=VerifiedDriver(ROOT,CertifiedStore(tmp_path/'store'),tmp_path/'pending',tmp_path/'unused.json')
    with pytest.raises(ValueError): driver.audit_only(1,tmp_path/'outside-audit')
    assert not (tmp_path/'outside-audit').exists()

def test_existing_admissible_directory_is_not_owned_by_failed_request(tmp_path,monkeypatch):
    driver=toy_driver(tmp_path,monkeypatch)
    old=driver.pending_root/'old'; old.mkdir(parents=True); (old/'sealed.json').write_bytes(b'{}')
    before=inventory(old)
    assert driver.transact(1,'old').verdict=='STOP'
    assert inventory(old)==before
