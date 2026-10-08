"""Source epochs keep historical authority separate from new finite replay."""
import copy,json
from pathlib import Path
import pytest
from compute_metabolism.v0 import profile_verify as gate,historical_profile as old

ROOT=Path(__file__).parents[1]
def test_old_registered_manifest_uses_archived_authority(monkeypatch):
    profile=json.loads((ROOT/'compute_metabolism/v0/execution_profiles/libc-memset-avx2-unaligned-erms-v1.json').read_bytes())
    called=[]
    def check(p,r):called.append((p,r));return p
    monkeypatch.setattr(old,'verify_historical_profile',check)
    assert gate.verify_registered_profile(profile,ROOT)==profile
    assert called==[(profile,ROOT)]

def test_new_candidate_cannot_use_old_gate_schema(tmp_path):
    p=tmp_path/'candidate';p.mkdir()
    (p/'candidate-profile.json').write_text(json.dumps({'profile_id':'libc-memset-avx512-evex-16zero-v1','status':'CANDIDATE'}))
    (p/'proof-bundle.json').write_text(json.dumps({'schema':'COMPUTE_METABOLISM_INDEPENDENT_PROOF_V1'}))
    assert gate.verify_promotion(p)['promotion_allowed'] is False

def test_registered_evex_authority_always_calls_independent_replay(tmp_path,monkeypatch):
    from compute_metabolism.v0 import adaptive,evex_profile
    from tests.test_compute_metabolism_evex_profile import sample
    observation,*_=sample(tmp_path)
    profile=evex_profile.build_candidate(observation,'a'*64)
    profile['status']='VERIFIED';profile['verification']['authority']='INDEPENDENT_GALA_EVEX_PROFILE_V1'
    registry=tmp_path/'registry';registry.mkdir()
    (registry/(profile['profile_id']+'.json')).write_bytes(adaptive.canonical(profile))
    (registry/'registry.json').write_bytes(adaptive.canonical(dict(schema='COMPUTE_METABOLISM_PROFILE_REGISTRY_V1',
        profiles=[dict(path=profile['profile_id']+'.json',manifest_sha256=adaptive.digest(profile))])))
    def refuse(*a):raise ValueError('INDEPENDENT_REPLAY_REFUSED')
    monkeypatch.setattr(evex_profile,'verify_registered_profile',refuse)
    with pytest.raises(ValueError,match='INDEPENDENT_REPLAY_REFUSED'):
        adaptive.load_registry(registry,repo_root=tmp_path)
