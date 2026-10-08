"""TEST_ONLY STOP-linked one-observation authority, never numerical execution."""
import copy
import hashlib
import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from tests.test_compute_metabolism_v0_campaign import cli_config, api
from compute_metabolism.v0 import observation_run


def successors(api, tmp_path, monkeypatch):
    path, _, old = cli_config(tmp_path, monkeypatch)
    files = {n:Path(x['path']).read_bytes() for g in ('inputs', 'identities') for n,x in old[g].items()}
    api.initialize_campaign(old, path.read_bytes(), files)
    ledger = api.CampaignLedger.open(Path(old['ledger_path']), api.CampaignLimits())
    ledger.begin_attempt(old['campaign_id'], 'prior-stop', '2c', 'warm-up', 0)
    ledger.finish_attempt('prior-stop', 16.948194404001697, None, 0, 0, 'ENVIRONMENT_INVALID')
    final = api._finalize_upper(ledger, old, 'prior-stop', False, 'POST_FINISH')
    before = ledger.snapshot()
    fingerprint = {'TEST_ONLY':'fixture-fingerprint'}
    epoch = {'TEST_ONLY':'fixture-epoch'}
    digest = lambda value: hashlib.sha256((json.dumps(value,sort_keys=True,separators=(',',':'))+'\n').encode()).hexdigest()
    cfg = copy.deepcopy(old)
    cfg.update(campaign_id='observation-successor', execution_mode='OBSERVATION_ONLY',
        restart_from_campaign_id=old['campaign_id'],
        restart_from_finalization_sha256=final['finalization_sha256'],
        observation_authorization=dict(run_id='actual-gala-once', profile='2c',
            maximum_attempts=1, certified_state_progress=False,
            fingerprint_sha256=digest(fingerprint), source_epoch_sha256=digest(epoch),
            registry_sha256='c'*64, gdb_sha256='d'*64))
    raw = json.dumps(cfg).encode()
    return ledger, cfg, raw, files, before


def begin(ledger, cfg, *, launch=True, mutation=None):
    doc=dict(schema='COMPUTE_METABOLISM_GALA_OBSERVATION_CONFIG_V1', mode='OBSERVATION',
        certified_state_progress=False, campaign_id=cfg['campaign_id'], run_id='actual-gala-once', profile='2c',
        fingerprint={'TEST_ONLY':'fixture-fingerprint'}, source_epoch={'TEST_ONLY':'fixture-epoch'},
        fingerprint_sha256=cfg['observation_authorization']['fingerprint_sha256'],
        source_epoch_sha256=cfg['observation_authorization']['source_epoch_sha256'],
        source_manifest=cfg.get('gate_source_snapshot',{}),
        execution_registry_sha256='c'*64, gdb_sha256='d'*64)
    if mutation is not None:
        mutation(doc)
    parent=ledger.root/cfg['campaign_id']/'observations'
    parent.mkdir(exist_ok=True)
    path=parent/'config-actual-gala-once.json'
    raw=(json.dumps(doc,sort_keys=True,separators=(',',':'))+'\n').encode()
    path.write_bytes(raw)
    digest=hashlib.sha256(raw).hexdigest()
    if launch:
        observation_run._begin_observation(ledger, 'actual-gala-once', digest)
    return digest


def test_new_successor_allows_only_bound_observation_and_preserves_history(api, tmp_path, monkeypatch):
    ledger, cfg, raw, files, before = successors(api, tmp_path, monkeypatch)
    api.initialize_campaign(cfg, raw, files)
    initialized = ledger.snapshot()
    begin(ledger, cfg)
    after = ledger.snapshot()
    assert after['attempts'][:-1] == before['attempts']
    assert after['total_wall_seconds'] == 16.948194404001697
    assert after['limits'] == before['limits']
    assert after['attempts'][-1]['campaign_id'] == 'observation-successor'
    assert after['attempts'][-1]['certified_state_progress'] is False
    assert after['campaign_finalizations'] == initialized['campaign_finalizations']


def test_observation_only_mode_refuses_numerical_entry_before_unit(api, tmp_path, monkeypatch):
    ledger, cfg, raw, files, before = successors(api, tmp_path, monkeypatch)
    api.initialize_campaign(cfg, raw, files)
    launch = Mock(side_effect=AssertionError('no numerical unit'))
    monkeypatch.setattr(api, '_bind_host_dependencies', launch)
    with pytest.raises(ValueError, match='OBSERVATION_ONLY'):
        api.run_next(cfg, raw, 'forbidden-warmup')
    assert not launch.called
    assert ledger.snapshot()['attempts'] == before['attempts']


def test_finished_observation_gets_genuine_stop_and_can_link_verified_successor(api, tmp_path, monkeypatch):
    ledger, cfg, raw, files, before = successors(api, tmp_path, monkeypatch)
    api.initialize_campaign(cfg, raw, files)
    begin(ledger, cfg)
    ledger.finish_attempt('actual-gala-once', 2.0, 1.0, 7, 0, 'GUARD_COMPLETE')
    final = api._finalize_upper(ledger, cfg, 'actual-gala-once', False, 'POST_FINISH')
    assert final['campaign_stop'] is True and final['campaign_outcome'] == 'STOP'
    assert final['needs_next_attempt'] is False
    assert ledger.snapshot()['attempts'][-1]['outcome'] == 'GUARD_COMPLETE'
    second = copy.deepcopy(cfg)
    second.pop('execution_mode'); second.pop('observation_authorization')
    second.update(campaign_id='verified-successor', restart_from_campaign_id=cfg['campaign_id'],
                  restart_from_finalization_sha256=final['finalization_sha256'])
    api.initialize_campaign(second, json.dumps(second).encode(), files)
    assert ledger.snapshot()['total_wall_seconds'] == 18.948194404001697
    assert ledger.snapshot()['attempts'][:1] == before['attempts']
    assert len(ledger.snapshot()['attempts']) == 2


@pytest.mark.parametrize('fault', ['wrong-run', 'wrong-final-hash', 'missing-restart-record', 'wrong-mode'])
def test_successor_observation_refuses_wrong_authority_without_ledger_mutation(api, tmp_path, monkeypatch, fault):
    ledger, cfg, raw, files, before = successors(api, tmp_path, monkeypatch)
    if fault == 'wrong-mode':
        cfg.pop('execution_mode'); cfg.pop('observation_authorization'); raw=json.dumps(cfg).encode()
    api.initialize_campaign(cfg, raw, files)
    run = 'wrong-run' if fault == 'wrong-run' else 'actual-gala-once'
    if fault == 'wrong-final-hash':
        target = ledger.root/cfg['restart_from_campaign_id']/'campaign-finalization-0001.json'
        target.chmod(0o644); target.write_bytes(b'{}')
    elif fault == 'missing-restart-record':
        state = api._read(ledger.path); state['campaign_restarts'] = []; ledger._write(state)
    digest = begin(ledger,cfg,launch=False) if fault != 'wrong-mode' else 'e'*64
    saved = ledger.path.read_bytes()
    with pytest.raises((ValueError, api.LedgerIntegrityError)):
        observation_run._begin_observation(ledger, run, digest)
    assert ledger.path.read_bytes() == saved


def test_finished_once_cannot_start_second_observation(api, tmp_path, monkeypatch):
    ledger, cfg, raw, files, before = successors(api, tmp_path, monkeypatch)
    api.initialize_campaign(cfg, raw, files)
    begin(ledger, cfg)
    ledger.finish_attempt('actual-gala-once', 2.0, 1.0, 7, 0, 'GUARD_COMPLETE')
    api._finalize_upper(ledger, cfg, 'actual-gala-once', False, 'POST_FINISH')
    saved=ledger.path.read_bytes()
    with pytest.raises(ValueError):observation_run._begin_observation(ledger, 'second-observation', 'f'*64)
    assert ledger.path.read_bytes() == saved


def test_actual_environment_needs_no_fake_verified_profile_in_observation_mode(api, tmp_path, monkeypatch):
    ledger, cfg, raw, files, before = successors(api, tmp_path, monkeypatch)
    environment=json.loads(files['campaign-environment.json'])
    environment.update(schema='COMPUTE_METABOLISM_ENVIRONMENT_V0')
    files['campaign-environment.json']=json.dumps(environment).encode()
    cfg['inputs']['campaign-environment.json']['sha256']=hashlib.sha256(files['campaign-environment.json']).hexdigest()
    api.initialize_campaign(cfg, json.dumps(cfg).encode(), files)
    assert 'execution_profile' not in environment
    assert ledger.snapshot()['total_wall_seconds'] == before['total_wall_seconds']


@pytest.mark.parametrize('finished', [False, True])
def test_status_cannot_advertise_numerical_authority(api, tmp_path, monkeypatch, capsys, finished):
    ledger, cfg, raw, files, before = successors(api, tmp_path, monkeypatch)
    api.initialize_campaign(cfg, raw, files)
    if finished:
        begin(ledger, cfg)
        ledger.finish_attempt('actual-gala-once', 2, 1, 0, 0, 'GUARD_COMPLETE')
        api._finalize_upper(ledger,cfg,'actual-gala-once',False,'POST_FINISH')
    monkeypatch.setattr(api,'_configuration',lambda *args:(cfg,raw,files))
    assert api.main(['status','--config',str(tmp_path/'fixture.json'),'--config-sha256',hashlib.sha256(raw).hexdigest()]) == 2
    result=json.loads(capsys.readouterr().out)
    assert result['campaign_stop'] is True and result['next_attempt'] is None


def test_synthetic_route_cannot_consume_actual_gala_authorization(api,tmp_path,monkeypatch):
    ledger,cfg,raw,files,before=successors(api,tmp_path,monkeypatch)
    api.initialize_campaign(cfg,raw,files)
    saved=ledger.path.read_bytes()
    with pytest.raises(ValueError,match='OBSERVATION_ONLY'):
        observation_run.run_observation(Path(cfg['root_directory']),'actual-gala-once',{})
    assert ledger.path.read_bytes()==saved
    assert not (ledger.root/cfg['campaign_id']/'observations').exists()


def test_analysis_reports_observation_stop_without_requiring_warmup(api,tmp_path,monkeypatch):
    from compute_metabolism.v0 import analyze
    ledger,cfg,raw,files,before=successors(api,tmp_path,monkeypatch)
    api.initialize_campaign(cfg,raw,files)
    begin(ledger,cfg)
    ledger.finish_attempt('actual-gala-once',2,1,0,0,'GUARD_COMPLETE')
    api._finalize_upper(ledger,cfg,'actual-gala-once',False,'POST_FINISH')
    monkeypatch.setattr(analyze,'_actual_host_binding',lambda config:dict(status='VALID'))
    result=analyze.analyze_campaign(ledger.root/cfg['campaign_id'])
    assert result['outcome']=='STOP'
    assert result['derived_ratios'] == {}
    assert 'exactly one valid unscored 2c N1 warm-up required' not in result['issues']


@pytest.mark.parametrize('field', ['schema','fingerprint_sha256','source_epoch_sha256','execution_registry_sha256','gdb_sha256'])
def test_begin_rechecks_actual_gala_config_scope_before_running(api,tmp_path,monkeypatch,field):
    ledger,cfg,raw,files,before=successors(api,tmp_path,monkeypatch)
    api.initialize_campaign(cfg,raw,files)
    sha=begin(ledger,cfg,launch=False,mutation=lambda doc:doc.update({field:'f'*64}))
    saved=ledger.path.read_bytes()
    with pytest.raises(ValueError,match='actual-Gala'):
        observation_run._begin_observation(ledger,'actual-gala-once',sha)
    assert ledger.path.read_bytes()==saved


def test_observation_successor_cannot_create_new_upper_allowance(api,tmp_path,monkeypatch):
    ledger,cfg,raw,files,before=successors(api,tmp_path,monkeypatch)
    missing=tmp_path/'never-created'/'budget.json'
    cfg['ledger_path']=str(missing)
    with pytest.raises((ValueError,OSError)):
        api.initialize_campaign(cfg,json.dumps(cfg).encode(),files)
    assert not missing.exists() and not missing.parent.exists()
