"""Old authority must be replayed from isolated old bytes, never relabelled."""
import copy
import importlib
import json
from pathlib import Path
import shutil

import pytest

ROOT = Path(__file__).parents[1]
OLD = 'f75980706aefbbd68cddce09549695c2f633905e01185f92f96660db81a9e2cd'
ARCHIVE = Path('compute_metabolism/v0/source_epochs') / OLD


def api():
    return importlib.import_module('compute_metabolism.v0.historical_profile')


@pytest.fixture
def profile():
    return json.loads((ROOT / 'compute_metabolism/v0/execution_profiles/libc-memset-avx2-unaligned-erms-v1.json').read_bytes())


@pytest.fixture
def early_root(tmp_path):
    shutil.copytree(ROOT / ARCHIVE, tmp_path / ARCHIVE)
    return tmp_path


@pytest.mark.parametrize('field,value', [
    ('status', 'CANDIDATE'), ('profile_id', 'unreviewed-profile'),
    ('v1_source_binding', 'f'*64), ('entry_points', [1]),
    ('required_cpu_features', ['avx512f']), ('verified_capability_rank', 999),
])
def test_changed_prior_profile_refused_before_replay(profile, field, value):
    profile[field] = value
    with pytest.raises(ValueError):
        api().verify_historical_profile(profile, ROOT)


@pytest.mark.parametrize('field,value', [
    ('source_count', 41), ('source_count', True), ('source_binding', 'f'*64),
    ('profile_gate_sha256', '0'*64), ('negative_controls', []),
    ('authority', 'SELF_ISSUED_PASS'),
])
def test_changed_old_receipt_refused(profile, field, value):
    profile['verification'][field] = value
    with pytest.raises(ValueError):
        api().verify_historical_profile(profile, ROOT)


@pytest.mark.parametrize('relative', ['source/verified_driver/v1/live_chain/raw.py',
    'authority/profile_verify.py', 'authority/adaptive.py'])
def test_archive_or_gate_tamper_refused(profile, early_root, relative):
    path = early_root / ARCHIVE / relative
    path.write_bytes(path.read_bytes() + b'\n# tamper\n')
    with pytest.raises(ValueError):
        api().verify_historical_profile(profile, early_root)


def test_extra_archived_source_refused(profile, early_root):
    (early_root / ARCHIVE / 'source/verified_driver/v1/native_evex_backdoor.py').write_text('pass\n')
    with pytest.raises(ValueError):
        api().verify_historical_profile(profile, early_root)


def test_manifest_rehash_cannot_authorize_archive_mutation(profile, early_root):
    import hashlib
    file = early_root / ARCHIVE / 'source/verified_driver/v1/model.py'
    file.write_bytes(file.read_bytes() + b'\n# tamper\n')
    manifest_path = early_root / ARCHIVE / 'manifest.json'
    manifest = json.loads(manifest_path.read_bytes())
    manifest['source_snapshot']['verified_driver/v1/model.py'] = hashlib.sha256(file.read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        api().verify_historical_profile(profile, early_root)


def test_runtime_drift_refused(profile, early_root):
    # All protected sources are needed, with no current V1 code in this fixture.
    for path in (ROOT / 'runtime_trace').rglob('*.py'):
        if 'artifacts' in path.parts or '__pycache__' in path.parts:
            continue
        target = early_root / path.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(path.read_bytes())
    for relative in ('lab/v2_bound.py', 'independent_checker/oracle.py'):
        target = early_root / relative; target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / relative).read_bytes())
    path = early_root / 'runtime_trace/semantics.py'
    path.write_bytes(path.read_bytes() + b'\n# altered runtime\n')
    with pytest.raises(ValueError, match='Runtime'):
        api().verify_historical_profile(profile, early_root)


@pytest.fixture(scope='module')
def pinned_payload():
    return api()._payload(ROOT)


@pytest.mark.parametrize('relative', [
    'verified_driver/v0/model.py',
    'runtime_trace/frozen_binaries/libc.so.6',
    'current/numeric_ir_v2_independent_audit_evidence_2026-10-03.zip',
    'compute_metabolism/v0/execution_profiles/proofs/task8-positive-03-edge-1/edge/edge.json',
])
def test_extra_helper_binary_or_proof_tamper_refused(profile, early_root, pinned_payload, relative):
    for name, raw in pinned_payload.items():
        target = early_root / name; target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    path = early_root / relative
    path.write_bytes(path.read_bytes() + b'tamper')
    with pytest.raises(ValueError, match='byte identity'):
        api().verify_historical_profile(profile, early_root)


def test_no_current_native_module_in_replay_payload(pinned_payload):
    assert not any('native_evex' in path for path in pinned_payload)
    assert not any('historical_profile' in path for path in pinned_payload)


def test_subprocess_failed_or_changed_receipt_cannot_authorize(profile, monkeypatch):
    monkeypatch.setattr(api(), '_payload', lambda _: {})
    changed = copy.deepcopy(profile)
    changed['verification']['source_count'] = 50
    monkeypatch.setattr(api(), '_execute', lambda *_: changed)
    with pytest.raises(ValueError, match='result/receipt drift'):
        api().verify_historical_profile(profile, ROOT)


def test_actual_old_full_gate_and_eight_negatives_with_new_current_v1(profile):
    from verified_driver.v1.live_chain.session import live_source_snapshot
    assert len(live_source_snapshot(ROOT)) > 40
    before = copy.deepcopy(profile)
    result = api().verify_historical_profile(profile, ROOT)
    assert result == before == profile
    assert result['verification']['source_count'] == 40
    assert result['verification']['source_binding'] == OLD
    controls = result['verification']['negative_controls']
    assert len(controls) == 8
    assert all(c['verdict'] == 'REFUSED' for c in controls)
    assert controls[-1]['failure_stage'] == 'SEMANTIC'
    assert result['verification']['numerical_certification'] is False
