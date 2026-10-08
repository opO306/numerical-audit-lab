"""TEST_ONLY filesystem evidence; no Gala, GDB, cgroup or numerical launches."""
import copy
import hashlib
import json
from pathlib import Path

import pytest

from tests import test_compute_metabolism_v0_v1 as v1
from tests.test_compute_metabolism_v0_campaign import api, cli_config
from tests.test_compute_metabolism_v0_v1 import evidence
from compute_metabolism.v0.profiles import CampaignLimits


def environment_case():
    env = v1.environment()
    prepared = copy.deepcopy(env['runtime'])
    campaign = dict(schema='COMPUTE_METABOLISM_ENVIRONMENT_V0',
        instance_id='123456', boot_id=env['boot_id'], topology=env['topology'],
        platform=env['runtime']['platform'])
    return env, prepared, campaign


def test_amendment_prepared_platform_is_provenance_campaign_platform_is_authority():
    env, prepared, campaign = environment_case()
    original = v1.PREP.read_bytes()
    env['runtime']['platform'] = campaign['platform'] = 'TEST_ONLY current campaign platform'
    assert env['runtime']['platform'] != prepared['platform']
    v1.api()._validate_environment(env, prepared, campaign, 'TEST_ONLY')
    assert v1.PREP.read_bytes() == original


@pytest.mark.parametrize('platform', ['TEST_ONLY foreign platform', '', None])
def test_amendment_campaign_platform_mismatch_or_missing_refuses(platform):
    env, prepared, campaign = environment_case()
    campaign['platform'] = platform
    with pytest.raises(v1.api().AdmissionFailure):
        v1.api()._validate_environment(env, prepared, campaign, 'TEST_ONLY')


def test_amendment_before_after_platform_drift_refuses(evidence):
    root, _ = evidence(1)
    manifest = v1.get(root/'attempt.json')
    campaign = v1.get(root/'campaign-environment.json')
    campaign['platform'] = v1.get(root/'environment-before.json')['runtime']['platform']
    v1.put(root/'campaign-environment.json', campaign)
    manifest['inputs']['campaign-environment.json'] = v1.digest_bytes((root/'campaign-environment.json').read_bytes())
    after = v1.get(root/'environment-after.json')
    after['runtime']['platform'] = 'TEST_ONLY changed after platform'
    v1.put(root/'environment-after.json', after)
    with pytest.raises(v1.api().AdmissionFailure):
        v1.api()._environment_evidence(root, manifest)


@pytest.mark.parametrize('field', ['python', 'executable', 'packages', 'files', 'source_count',
    'source_binding', 'source_matches', 'source_snapshot', 'instance', 'boot', 'topology'])
def test_amendment_userspace_source_and_vm_drift_still_refuses(field):
    env, prepared, campaign = environment_case()
    if field in ('packages', 'files'):
        env['runtime'][field][next(iter(env['runtime'][field]))] = 'TEST_ONLY drift'
    elif field == 'source_count': env['runtime'][field] = 39
    elif field == 'source_matches': env['runtime'][field] = False
    elif field in ('python', 'executable', 'source_binding'): env['runtime'][field] = 'TEST_ONLY drift'
    elif field == 'source_snapshot': env[field][next(iter(env[field]))] = 'f'*64
    elif field == 'instance': env['instance_observation']['instance_id'] = '999'
    elif field == 'boot': env['boot_id'] = 'TEST_ONLY foreign boot'
    elif field == 'topology': env['topology'] = {'TEST_ONLY': 'foreign'}
    with pytest.raises(v1.api().AdmissionFailure):
        v1.api()._validate_environment(env, prepared, campaign, 'TEST_ONLY')


def stopped_campaign(api, tmp_path, monkeypatch, outcome='ENVIRONMENT_INVALID'):
    path, digest, config = cli_config(tmp_path, monkeypatch)
    assert api.main(['init', '--config', str(path), '--config-sha256', digest]) == 0
    ledger = api.CampaignLedger.open(Path(config['ledger_path']), CampaignLimits())
    ledger.begin_attempt(config['campaign_id'], 'old-warmup', '2c', 'warm-up', 0)
    ledger.finish_attempt('old-warmup', 1.0627413820002403,
        None if outcome == 'ENVIRONMENT_INVALID' else 0.5, 29958, 95, outcome)
    final = api._finalize_upper(ledger, config, 'old-warmup', False, 'POST_FINISH')
    return ledger, config, final


def restart_config(tmp_path, config, final):
    new = copy.deepcopy(config)
    new.update(campaign_id='gcp-restart', restart_from_campaign_id=config['campaign_id'],
        restart_from_finalization_sha256=final['finalization_sha256'])
    path = tmp_path/'restart-config.json'
    raw = json.dumps(new).encode()
    path.write_bytes(raw)
    return path, hashlib.sha256(raw).hexdigest(), new


def test_amendment_durable_stop_restart_preserves_single_upper_history(api, tmp_path, monkeypatch):
    ledger, config, final = stopped_campaign(api, tmp_path, monkeypatch)
    before = ledger.snapshot()
    old_root = ledger.root/config['campaign_id']
    old_files = {str(p): (p.read_bytes(), p.stat().st_mtime_ns) for p in old_root.rglob('*') if p.is_file()}
    path, digest, new = restart_config(tmp_path, config, final)
    assert api.main(['init', '--config', str(path), '--config-sha256', digest]) == 0
    after = ledger.snapshot()
    assert after['total_wall_seconds'] == before['total_wall_seconds'] == 1.0627413820002403
    assert after['limits'] == before['limits'] and after['limits']['total_wall_seconds'] == 4200
    assert after['attempts'] == before['attempts'] and after['campaign_finalizations'] == before['campaign_finalizations']
    assert after['retained_total_bytes'] >= before['retained_total_bytes']
    assert before['formal_campaign'] in after['formal_campaign_history']
    assert after['formal_campaign'] == dict(campaign_id=new['campaign_id'], config_sha256=digest)
    assert old_files == {str(p): (p.read_bytes(), p.stat().st_mtime_ns) for p in old_root.rglob('*') if p.is_file()}
    assert (ledger.root/new['campaign_id']/'campaign.json').read_bytes() == path.read_bytes()
    old_raw = (old_root/'campaign.json').read_bytes()
    old_view, old_rows = api._campaign_view(config, old_raw)
    assert old_rows == before['attempts']  # historical read remains possible
    assert old_view['formal_campaign'] == after['formal_campaign']
    from compute_metabolism.v0 import analyze
    receipts, issues = analyze._finalizations(config, after, old_rows, old_root)
    assert issues == [] and len(receipts) == 1
    with pytest.raises(ValueError): api.run_next(config, old_raw, 'old-retry-never')
    _, new_rows = api._campaign_view(new, path.read_bytes())
    assert new_rows == [] and api.next_attempt(new_rows)['requested_steps'] == 1


@pytest.mark.parametrize('fault', ['missing-finalization', 'wrong-hash', 'tampered-finalization',
    'not-stop', 'running', 'same-id', 'existing-namespace', 'no-predecessor', 'wrong-predecessor'])
def test_amendment_restart_refuses_without_exact_stopped_predecessor(api, tmp_path, monkeypatch, fault):
    ledger, config, final = stopped_campaign(api, tmp_path, monkeypatch,
        'ACCEPT' if fault == 'not-stop' else 'ENVIRONMENT_INVALID')
    path, digest, new = restart_config(tmp_path, config, final)
    if fault == 'missing-finalization':
        p = Path(final['finalization_locator']); p.chmod(0o600); p.unlink()
    elif fault == 'wrong-hash': new['restart_from_finalization_sha256'] = '0'*64
    elif fault == 'tampered-finalization':
        p = Path(final['finalization_locator']); p.chmod(0o600); p.write_bytes(p.read_bytes()+b' ')
    elif fault == 'running': ledger.begin_attempt(config['campaign_id'], 'pending', '2c', 'warm-up', 0)
    elif fault == 'same-id': new['campaign_id'] = config['campaign_id']
    elif fault == 'existing-namespace': (ledger.root/new['campaign_id']).mkdir()
    elif fault == 'no-predecessor':
        new.pop('restart_from_campaign_id'); new.pop('restart_from_finalization_sha256')
    elif fault == 'wrong-predecessor': new['restart_from_campaign_id'] = 'foreign'
    raw = json.dumps(new).encode(); path.write_bytes(raw); digest = hashlib.sha256(raw).hexdigest()
    before = ledger.snapshot()
    assert api.main(['init', '--config', str(path), '--config-sha256', digest]) == 2
    after = api.CampaignLedger.read_snapshot(ledger.path)
    for key in ('total_wall_seconds', 'attempts', 'campaign_finalizations', 'formal_campaign', 'limits'):
        assert after[key] == before[key]
    if fault != 'same-id': assert not (ledger.root/new['campaign_id']/'campaign.json').exists()
