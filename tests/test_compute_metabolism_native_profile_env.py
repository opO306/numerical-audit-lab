"""Campaign input authority is installed only for the explicit N1 profile."""
import os
from pathlib import Path
import pytest
from compute_metabolism.v0 import run_v1
from verified_driver.v1 import native_evex_profile as admission

def test_hash_bound_campaign_environment_reaches_session_and_is_restored(monkeypatch):
    monkeypatch.setenv('CM_NATIVE_PROFILE_CONFIG','prior')
    monkeypatch.setenv('CM_NATIVE_PROFILE_SHA256','priorhash')
    calls=[]
    def check(root,n):
        calls.append((root,n,os.environ['CM_NATIVE_PROFILE_CONFIG'],os.environ['CM_NATIVE_PROFILE_SHA256']))
        return {'TEST_ONLY':'external gate called'}
    monkeypatch.setattr(admission,'admit_environment',check)
    with run_v1._native_execution_environment({'profile_id':admission.PROFILE_ID},Path('/workspace'),Path('/run/campaign-environment.json'),'a'*64,1):
        assert os.environ['CM_NATIVE_PROFILE_CONFIG']=='/run/campaign-environment.json'
    assert calls==[(Path('/workspace'),1,'/run/campaign-environment.json','a'*64)]
    assert os.environ['CM_NATIVE_PROFILE_CONFIG']=='prior' and os.environ['CM_NATIVE_PROFILE_SHA256']=='priorhash'

def test_failed_profile_gate_does_not_start_session_and_restores_environment(monkeypatch):
    monkeypatch.delenv('CM_NATIVE_PROFILE_CONFIG',raising=False);monkeypatch.delenv('CM_NATIVE_PROFILE_SHA256',raising=False)
    monkeypatch.setattr(admission,'admit_environment',lambda *a:(_ for _ in ()).throw(ValueError('REFUSED')))
    with pytest.raises(ValueError,match='REFUSED'):
        with run_v1._native_execution_environment({'profile_id':admission.PROFILE_ID},Path('/workspace'),Path('/input'),'a'*64,1):
            pytest.fail('must refuse before session')
    assert 'CM_NATIVE_PROFILE_CONFIG' not in os.environ and 'CM_NATIVE_PROFILE_SHA256' not in os.environ

def test_legacy_campaign_refuses_stray_native_authority(monkeypatch):
    monkeypatch.setenv('CM_NATIVE_PROFILE_CONFIG','unbound')
    with pytest.raises(run_v1.AdmissionFailure):
        with run_v1._native_execution_environment({'profile_id':'old'},Path('/workspace'),Path('/input'),'a'*64,1):
            pytest.fail('foreign profile authority')
