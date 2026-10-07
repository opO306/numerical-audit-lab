"""Real filesystem/process tests for the single upper campaign allowance."""
import json
import multiprocessing
import os
from pathlib import Path
import stat

import pytest


def test_wave2_prepared_alias_restoration_preserves_source_stop(api, tmp_path, monkeypatch, capsys):
    path, digest, config = cli_config(tmp_path, monkeypatch)
    prior = api.CampaignLedger.open(Path(config['ledger_path']), CampaignLimits())
    prior.begin_attempt('TEST_ONLY-preflight', 'prior', '2c', 'guard-preflight', 0)
    prior.finish_attempt('prior', 9.25, 1, 7, 3, 'GUARD_COMPLETE')
    assert api.main(['init', '--config', str(path), '--config-sha256', digest]) == 0
    seen = install_admitted_guard(api, tmp_path, monkeypatch, config)
    ledger = Path(config['ledger_path'])
    before = api.CampaignLedger.read_snapshot(ledger)
    wrapper = Path(config['identities']['compute_metabolism/v0/run_v1.py']['path'])
    original = wrapper.read_bytes()
    alias = tmp_path/'TEST_ONLY-unreadable-alias-target'
    alias.write_bytes(b'TEST_ONLY alias bytes must never be followed')
    wrapper.unlink()
    wrapper.symlink_to(alias)
    original_read = Path.read_bytes
    def no_alias_read(target):
        if target == wrapper or target == alias:
            raise AssertionError('prepared alias bytes were followed')
        return original_read(target)
    args = ['run-next', '--config', str(path), '--config-sha256', digest, '--run-id', 'never']
    with monkeypatch.context() as isolated:
        isolated.setattr(Path, 'read_bytes', no_alias_read)
        assert api.main(args) == 2
    refusal = json.loads(capsys.readouterr().out.splitlines()[-1])
    wrapper.unlink()
    wrapper.write_bytes(original)
    marker = ledger.parent/'gcp-test/host-source-stop.json'
    assert marker.is_file(), refusal
    saved = marker.read_bytes()
    assert api.main(args) == 2
    assert seen == [] and marker.read_bytes() == saved
    after = api.CampaignLedger.read_snapshot(ledger)
    assert after['attempts'] == before['attempts'] and after['total_wall_seconds'] == before['total_wall_seconds']
    assert after['total_wall_seconds'] == 9.25
    assert after['retained_total_bytes'] >= before['retained_total_bytes']


@pytest.mark.parametrize('fault', ['prepared-alias', 'unsafe-namespace', 'wrong-origin'])
def test_wave2_invalid_preinit_never_creates_source_stop(api, tmp_path, monkeypatch, fault):
    import hashlib
    path, digest, config = cli_config(tmp_path, monkeypatch)
    wrapper = Path(config['identities']['compute_metabolism/v0/run_v1.py']['path'])
    if fault == 'prepared-alias':
        wrapper.unlink()
        wrapper.symlink_to(tmp_path/'TEST_ONLY-missing-target')
    elif fault == 'unsafe-namespace':
        config['ledger_path'] = str(tmp_path/'outside/budget.json')
    else:
        config['identities']['compute_metabolism/v0/run_v1.py']['path'] = str(tmp_path/'foreign.py')
    raw = json.dumps(config).encode()
    path.write_bytes(raw)
    assert api.main(['init', '--config', str(path), '--config-sha256', hashlib.sha256(raw).hexdigest()]) == 2
    assert not list(tmp_path.rglob('host-source-stop.json'))
    assert not Path(config['ledger_path']).exists()


@pytest.mark.parametrize('kind', ['timeout', 'oom'])
def test_finalfix_retained_real_serializer_cycle_finishes_exactly(api, tmp_path, monkeypatch, capsys, kind):
    import copy
    path, digest, config = cli_config(tmp_path, monkeypatch)
    assert api.main(['init', '--config', str(path), '--config-sha256', digest]) == 0
    seen = install_admitted_guard(api, tmp_path, monkeypatch, config,
        wall=lambda row: 10 if row['role']=='warm-up' else 180.123456789)
    prefix = ['run-next','--config',str(path),'--config-sha256',digest,'--run-id']
    assert api.main(prefix+['warm']) == 0
    capsys.readouterr()
    original = api._encode
    sizes = []
    target = Path(config['ledger_path']).parent/'gcp-test/round-01/r1'
    def boundary_encode(doc):
        if doc.get('schema') != 'COMPUTE_METABOLISM_EXECUTION_V0':
            return original(doc)
        sizes.append(doc['retained_bytes'])
        if len(sizes) == 1:
            probe = copy.deepcopy(doc)
            probe['retained_bytes'] = 100663295
            probe['classification'] = api.classify_attempt(probe['admission_report'], probe['guard_receipt'],100663295)
            length = len(original(probe))
            sparse = target/'TEST_ONLY-sparse.bin'
            with sparse.open('xb') as stream:
                stream.truncate(100663297 - length - api.logical_tree_bytes(target))
        if len(sizes) > 12:
            raise ValueError('TEST_ONLY watchdog caught retained sizing cycle: '+repr(sizes))
        return original(doc)
    if kind=='oom':
        from compute_metabolism.v0 import system_guard as guard
        original_guard = guard.run_system_guard
        def oom_guard(*args, **kwargs):
            receipt = original_guard(*args, **kwargs)
            receipt['outer_timeout_proved'] = False
            receipt['after']['memory_events'].update(oom=1,oom_kill=1)
            (kwargs['artifact_dir']/'guard-outer.json').write_text(json.dumps(receipt))
            return receipt
        monkeypatch.setattr(guard,'run_system_guard',oom_guard)
    monkeypatch.setattr(api,'_encode',boundary_encode)
    assert api.main(prefix+['r1']) == 2
    result=json.loads(capsys.readouterr().out)
    print('ACTUAL_SERIALIZER_RETAINED_SEQUENCE', sizes)
    assert (target/'execution.json').exists(), result
    execution=json.loads((target/'execution.json').read_bytes())
    assert execution['retained_bytes']==api.logical_tree_bytes(target)
    assert execution['classification']['resource_reason']=='EVIDENCE_GROWTH'
    assert execution['classification']['resource_proof']['observed']==execution['retained_bytes']
    state=api.CampaignLedger.read_snapshot(Path(config['ledger_path']))
    assert state['running'] is None and state['total_wall_seconds']==190.123456789
    assert state['attempts'][-1]['status']=='FINISHED'
    assert json.loads((target/'guard-outer.json').read_bytes())['wall_seconds']==180.123456789
    assert api.main(prefix+['r2'])==2 and len(seen)==2


def test_finalfix_prepared_drift_restoration_cannot_resume(api,tmp_path,monkeypatch,capsys):
    path,digest,config=cli_config(tmp_path,monkeypatch)
    assert api.main(['init','--config',str(path),'--config-sha256',digest])==0
    seen=install_admitted_guard(api,tmp_path,monkeypatch,config)
    wrapper=Path(config['identities']['compute_metabolism/v0/run_v1.py']['path'])
    original=wrapper.read_bytes()
    wrapper.write_bytes(b'TEST_ONLY prepared source drift')
    args=['run-next','--config',str(path),'--config-sha256',digest,'--run-id','r1']
    assert api.main(args)==2
    wrapper.write_bytes(original)
    assert api.main(args)==2
    assert seen==[]
    assert (Path(config['ledger_path']).parent/'gcp-test/host-source-stop.json').exists()


@pytest.mark.parametrize('profile',['2c','1c','0p5c','variability'])
def test_finalfix_terminal_policy_cli_stops(api,tmp_path,monkeypatch,capsys,profile):
    path,digest,config=cli_config(tmp_path,monkeypatch)
    assert api.main(['init','--config',str(path),'--config-sha256',digest])==0
    ledger=api.CampaignLedger.open(Path(config['ledger_path']),CampaignLimits())
    history=[dict(role='warm-up',profile='2c',outcome='ACCEPT',eligible=True,status='FINISHED')]
    for i in range(1,8 if profile=='variability' else 4):
        for p in ('2c','1c','0p5c'):
            row=policy_attempt(p,'REFUSED_RESOURCE' if p==profile else 'ACCEPT',
                wall=1 if i==1 and profile=='variability' else 20,round_index=i)
            if profile=='0p5c' and p==profile and i==2: row['resource_reason']='CGROUP_OOM'
            history.append(row)
    # Policy history is TEST_ONLY; real CLI/resource/status paths still run.
    state=api.CampaignLedger.read_snapshot(ledger.path)
    monkeypatch.setattr(api,'_campaign_view',lambda config,raw:(state,history))
    capsys.readouterr()
    assert api.main(['status','--config',str(path),'--config-sha256',digest])==2
    result=json.loads(capsys.readouterr().out)
    assert result['campaign_stop'] and result['next_attempt'] is None
    assert result['campaign_outcome']==('UNRESOLVED_VARIABILITY' if profile=='variability' else 'STOP_INCOMPLETE')
    assert api.main(['run-next','--config',str(path),'--config-sha256',digest,'--run-id','never'])==2


def test_finalfix_unbound_conflict_dominates_valid_resource(api,tmp_path):
    report,receipt=classification_fixture(tmp_path)
    report['verification_conflict']=True
    got=api.classify_attempt(report,receipt,10)
    assert got['wrapper_outcome']=='UNRESOLVED_FAILURE' and got['campaign_stop']


def test_finalfix_run_next_last_resource_slot_returns_policy_stop(api,tmp_path,monkeypatch,capsys):
    path,digest,config=cli_config(tmp_path,monkeypatch)
    assert api.main(['init','--config',str(path),'--config-sha256',digest])==0
    ledger=api.CampaignLedger.open(Path(config['ledger_path']),CampaignLimits())
    history=[dict(role='warm-up',profile='2c',outcome='ACCEPT',eligible=True,status='FINISHED',round_index=0)]
    for i,order in enumerate((('2c','1c','0p5c'),('1c','0p5c','2c'),('0p5c',)),1):
        history.extend(policy_attempt(p,'REFUSED_RESOURCE' if p=='2c' else 'ACCEPT',round_index=i) for p in order)
    for i,row in enumerate(history):
        run_id=f'prior-{i}'
        ledger.begin_attempt('gcp-test',run_id,row['profile'],row['role'],row['round_index'])
        finish(ledger,run_id,wall=row.get('outer_wall_seconds',1),cpu=row.get('cpu_seconds',.5),outcome=row['outcome'])
        with ledger._authority():
            state=api._read(ledger.path)
            state['attempts'][-1].update(row)
            ledger._write(state)
    seen=install_admitted_guard(api,tmp_path,monkeypatch,config,wall=lambda row:180.123456789)
    capsys.readouterr()
    args=['run-next','--config',str(path),'--config-sha256',digest,'--run-id','last']
    assert api.main(args)==2
    result=json.loads(capsys.readouterr().out)
    assert result['classification']['campaign_stop'] is False
    assert result['campaign_outcome']=='STOP_INCOMPLETE' and result['campaign_stop']
    saved=json.loads(Path(result['campaign_finalization']['finalization_locator']).read_bytes())
    assert saved['campaign_outcome']=='STOP_INCOMPLETE'
    assert api.main(['status','--config',str(path),'--config-sha256',digest])==2
    assert api.main(args[:-1]+['never'])==2 and len(seen)==1


def test_finalfix_variability_keeps_remaining_round7_authority(api,tmp_path,monkeypatch,capsys):
    path,digest,config=cli_config(tmp_path,monkeypatch)
    assert api.main(['init','--config',str(path),'--config-sha256',digest])==0
    state=api.CampaignLedger.read_snapshot(Path(config['ledger_path']))
    history=[dict(role='warm-up',profile='2c',outcome='ACCEPT',eligible=True,status='FINISHED')]
    for i in range(1,8):
        for p in ('2c','1c','0p5c') if i<7 else ('2c',):
            history.append(policy_attempt(p,wall=1 if i==1 else 20,round_index=i))
    monkeypatch.setattr(api,'_campaign_view',lambda config,raw:(state,history))
    capsys.readouterr()
    assert api.main(['status','--config',str(path),'--config-sha256',digest])==0
    result=json.loads(capsys.readouterr().out)
    assert result['profiles']['2c']['decision']=='UNRESOLVED_VARIABILITY'
    assert result['next_attempt']['profile']=='1c' and result['next_attempt']['round_index']==7
    assert result['campaign_stop'] is False

from compute_metabolism.v0.profiles import CampaignLimits


@pytest.fixture
def api():
    from compute_metabolism.v0 import campaign
    return campaign


def opened(api, tmp_path):
    return api.CampaignLedger.open(tmp_path / 'artifacts' / 'upper.json', CampaignLimits())


def finish(ledger, run_id, wall=1, cpu=0.5, outcome='ACCEPT'):
    return ledger.finish_attempt(run_id, wall, cpu, 7, 3, outcome)


def test_fresh_only_once_and_new_campaign_never_resets(api, tmp_path):
    ledger = opened(api, tmp_path)
    assert ledger.snapshot()['total_wall_seconds'] == 0

    assert ledger.snapshot()['limits']['total_wall_seconds'] == 4200
    assert ledger.snapshot()['limits']['retained_total_bytes'] == 3221225472
    ledger.begin_attempt('a', 'r1', '2c', 'measured', 1)
    finish(ledger, 'r1', wall=180.25)
    ledger = api.CampaignLedger.open(ledger.path, CampaignLimits())
    ledger.begin_attempt('b', 'r2', '1c', 'warm-up', 0)
    finish(ledger, 'r2', wall=2, outcome='REFUSED_RESOURCE')
    state = ledger.snapshot()
    assert state['total_wall_seconds'] == 182.25
    assert [x['campaign_id'] for x in state['attempts']] == ['a', 'b']
    assert state['attempts'][0]['writer_reserved_bytes'] == 7
    assert state['attempts'][0]['retained_bytes'] == 3


def test_running_survives_reopen_crash_and_unresolved_receipt(api, tmp_path):
    ledger = opened(api, tmp_path)
    ledger.begin_attempt('gcp-a', 'r1', '2c', 'measured', 1)
    ledger.record_unresolved('r1', {'terminal_reaped': False, 'partial_wall_seconds': 181.1})
    reopened = api.CampaignLedger.open(ledger.path, CampaignLimits())
    with pytest.raises(api.UnresolvedPriorAttempt):
        reopened.begin_attempt('gcp-b', 'r2', '1c', 'measured', 1)
    assert reopened.can_start_attempt() == (False, 'UNRESOLVED_PRIOR_ATTEMPT')
    assert reopened.snapshot()['running']['run_id'] == 'r1'
    assert reopened.snapshot()['attempts'][0]['partial_receipts'][0]['terminal_reaped'] is False
    with pytest.raises(api.UnresolvedPriorAttempt):
        finish(reopened, 'r1', wall=182, cpu=None, outcome='UNRESOLVED_FAILURE')
    assert reopened.snapshot()['total_wall_seconds'] == 0


def test_wall_precheck_actual_cleanup_and_failed_charge(api, tmp_path):
    ledger = opened(api, tmp_path)
    ledger.begin_attempt('a', 'r1', '2c', 'measured', 1)
    finish(ledger, 'r1', wall=4020, outcome='REFUSED_RESOURCE')
    assert ledger.can_start_attempt() == (True, None)
    ledger.begin_attempt('b', 'r2', '2c', 'measured', 1)
    finish(ledger, 'r2', wall=180.75, outcome='ENVIRONMENT_INVALID', cpu=None)
    assert ledger.snapshot()['total_wall_seconds'] == 4200.75
    assert ledger.can_start_attempt() == (False, 'CAMPAIGN_WALL_EXHAUSTED')
    with pytest.raises(api.CampaignResourceExhausted):
        ledger.begin_attempt('c', 'r3', '1c', 'measured', 1)


def test_actual_root_metadata_namespaces_sparse_lengths_no_deletion(api, tmp_path):
    ledger = opened(api, tmp_path)
    root = ledger.path.parent
    for rel, size in [('a/failed.bin', 19), ('b/warmup.bin', 23), ('report.json', 29)]:
        target = root / rel
        target.parent.mkdir(exist_ok=True)
        target.write_bytes(b'x' * size)
    outside = tmp_path / 'rootfs'
    outside.mkdir()
    (outside / 'prepared').write_bytes(b'x' * 1000)
    state = ledger.snapshot()
    expected = sum(p.stat().st_size for p in root.rglob('*') if p.is_file())
    assert state['retained_total_bytes'] == expected
    assert api.logical_tree_bytes(root) == expected
    huge = root / 'a' / 'sparse.bin'
    with huge.open('wb') as stream:
        stream.truncate(3221225472 - 100663296)
    assert ledger.can_start_attempt() == (False, 'CAMPAIGN_RETAINED_EXHAUSTED')
    assert huge.exists() and (root / 'a/failed.bin').read_bytes() == b'x' * 19


def test_hardlinks_count_per_entry_and_symlink_escape_refused(api, tmp_path):
    root = tmp_path / 'tree'
    root.mkdir()
    (root / 'a').write_bytes(b'12345')
    os.link(root / 'a', root / 'b')
    assert api.logical_tree_bytes(root) == 10
    try:
        (root / 'alias').symlink_to(tmp_path, target_is_directory=True)
    except OSError:
        pytest.skip('symlink privilege unavailable; Linux run covers this')
    with pytest.raises(api.UnsafeArtifactTree):
        api.logical_tree_bytes(root)
    assert (root / 'alias').is_symlink()
    with pytest.raises(api.UnsafeArtifactTree):
        api.CampaignLedger.open(root / 'alias' / 'ledger.json', CampaignLimits())


def test_duplicates_wrong_identity_finish_twice_and_missing_ledger_refuse(api, tmp_path):
    ledger = opened(api, tmp_path)
    ledger.begin_attempt('a', 'r1', '2c', 'measured', 1)
    with pytest.raises(api.AttemptIdentityError):
        finish(ledger, 'other')
    finish(ledger, 'r1')
    with pytest.raises(api.AttemptIdentityError):
        finish(ledger, 'r1')
    with pytest.raises(api.AttemptIdentityError):
        ledger.begin_attempt('b', 'r1', '1c', 'measured', 1)
    ledger.path.unlink()
    with pytest.raises(api.LedgerIntegrityError):
        api.CampaignLedger.open(ledger.path, CampaignLimits())


@pytest.mark.parametrize('field,value', [('wall', float('inf')), ('wall', -1),
    ('wall', float('nan')), ('cpu', -1), ('cpu', float('nan')), ('cpu', None),
    ('reserved', -1), ('retained', 1.5), ('outcome', 'MADE_UP')])
def test_invalid_metrics_preserve_running(api, tmp_path, field, value):
    ledger = opened(api, tmp_path)
    ledger.begin_attempt('a', 'r1', '2c', 'measured', 1)
    args = dict(run_id='r1', outer_wall_seconds=1, cpu_seconds=0.5,
                writer_reserved_bytes=7, retained_bytes=3, outcome='ACCEPT')
    args[{'wall': 'outer_wall_seconds', 'cpu': 'cpu_seconds', 'reserved':
          'writer_reserved_bytes', 'retained': 'retained_bytes'}.get(field, field)] = value
    with pytest.raises(ValueError):
        ledger.finish_attempt(**args)
    assert ledger.snapshot()['running']['run_id'] == 'r1'
    assert ledger.snapshot()['total_wall_seconds'] == 0


@pytest.mark.parametrize('outcome', ['ENVIRONMENT_INVALID', 'UNRESOLVED_FAILURE', 'REFUSED_VERIFICATION'])
def test_unknown_cpu_explicit_for_invalid_terminal_attempt(api, tmp_path, outcome):
    ledger = opened(api, tmp_path)
    ledger.begin_attempt('a', 'r1', '1c', 'measured', 1)
    finish(ledger, 'r1', cpu=None, outcome=outcome)
    record = ledger.snapshot()['attempts'][0]
    assert record['cpu_seconds'] is None
    assert record['cpu_measurement_status'] == 'UNAVAILABLE'
    assert ledger.snapshot()['total_wall_seconds'] == 1


def test_guard_preflight_same_allowance_and_guard_outcome_restricted(api, tmp_path):
    ledger = opened(api, tmp_path)
    ledger.begin_attempt('preflight', 'g1', '2c', 'guard-preflight', 0)
    finish(ledger, 'g1', wall=5, outcome='GUARD_COMPLETE')
    ledger.begin_attempt('gcp-a', 'r1', '2c', 'measured', 1)
    with pytest.raises(ValueError):
        finish(ledger, 'r1', outcome='GUARD_COMPLETE')
    finish(ledger, 'r1', wall=2)
    assert ledger.snapshot()['total_wall_seconds'] == 7


def test_incompatible_existing_ledger_untouched(api, tmp_path):
    root = tmp_path / 'history'
    root.mkdir()
    path = root / 'ledger.json'
    raw = b'{"historic": true}\n'
    path.write_bytes(raw)
    with pytest.raises(api.LedgerIntegrityError):
        api.CampaignLedger.open(path, CampaignLimits())
    assert path.read_bytes() == raw
    assert list(root.iterdir()) == [path]


def _race_begin(path, event, result):
    from compute_metabolism.v0.campaign import CampaignLedger, UnresolvedPriorAttempt
    ledger = CampaignLedger.open(Path(path), CampaignLimits())
    event.wait(10)
    try:
        ledger.begin_attempt('a', str(os.getpid()), '1c', 'measured', 1)
        result.put('begun')
    except UnresolvedPriorAttempt:
        result.put('blocked')


def test_concurrent_processes_never_both_obtain_allowance(api, tmp_path):
    ledger = opened(api, tmp_path)
    ctx = multiprocessing.get_context('spawn')
    event, result = ctx.Event(), ctx.Queue()
    children = [ctx.Process(target=_race_begin, args=(str(ledger.path), event, result)) for _ in range(2)]
    for child in children:
        child.start()
    event.set()
    responses = sorted([result.get(timeout=20), result.get(timeout=20)])
    for child in children:
        child.join(20)
        assert child.exitcode == 0
    assert responses == ['begun', 'blocked']


def test_replace_failure_preserves_prior_running_record(api, tmp_path, monkeypatch):
    ledger = opened(api, tmp_path)
    ledger.begin_attempt('a', 'r1', '2c', 'measured', 1)
    before = ledger.path.read_bytes()
    def failed_replace(*args):
        raise OSError('controlled replace failure')
    monkeypatch.setattr(api.os, 'replace', failed_replace)
    with pytest.raises(OSError):
        finish(ledger, 'r1')
    assert ledger.path.read_bytes() == before
    assert json.loads(before)['running']['run_id'] == 'r1'


def test_running_metadata_must_leave_full_run_allowance_or_durable_refusal(api, tmp_path):
    ledger = opened(api, tmp_path)
    root = ledger.path.parent
    sparse = root / 'retained.bin'
    sparse.touch()
    with sparse.open('r+b') as stream:
        stream.truncate(3221225472 - 100663296 - 1000)
    ledger.snapshot()  # stabilize the metadata's decimal length first
    other = sum(p.stat().st_size for p in root.iterdir() if p != sparse)
    with sparse.open('r+b') as stream:
        stream.truncate(3221225472 - 100663296 - other)
    assert ledger.can_start_attempt() == (True, None)
    with pytest.raises(api.CampaignResourceExhausted):
        ledger.begin_attempt('a', 'r1', '1c', 'measured', 1)
    state = ledger.snapshot()
    assert state['running'] is None and state['attempts'] == []
    assert state['start_refusals'][0]['run_id'] == 'r1'
    assert state['start_refusals'][0]['reason'] == 'CAMPAIGN_RETAINED_EXHAUSTED'
    assert state['retained_total_bytes'] == sum(p.stat().st_size for p in root.iterdir())


def test_per_run_evidence_growth_preserved_and_blocks_next(api, tmp_path):
    ledger = opened(api, tmp_path)
    ledger.begin_attempt('a', 'r1', '1c', 'measured', 1)
    ledger.finish_attempt('r1', 1, 0.5, 671088640, 100663297, 'REFUSED_RESOURCE')
    assert ledger.snapshot()['attempts'][0]['retained_bytes'] == 100663297
    assert ledger.can_start_attempt() == (False, 'EVIDENCE_GROWTH')
    with pytest.raises(api.CampaignResourceExhausted):
        ledger.begin_attempt('a', 'r2', '2c', 'measured', 1)


def test_explicit_new_campaign_after_growth_preserves_upper_usage(api, tmp_path):
    ledger = opened(api, tmp_path)
    ledger.begin_attempt('a', 'r1', '1c', 'measured', 1)
    ledger.finish_attempt('r1', 181, 0.5, 671088640, 100663297, 'REFUSED_RESOURCE')
    prior_bytes = ledger.snapshot()['retained_total_bytes']
    ledger.begin_attempt('b', 'r2', '1c', 'measured', 1)
    finish(ledger, 'r2', wall=1)
    assert ledger.snapshot()['total_wall_seconds'] == 182
    assert ledger.snapshot()['retained_total_bytes'] > prior_bytes
    assert ledger.can_start_attempt('a') == (False, 'EVIDENCE_GROWTH')
    assert ledger.can_start_attempt('b') == (True, None)


@pytest.mark.parametrize('mutation', ['limits', 'sum', 'running', 'duplicate'])
def test_corrupt_existing_ledger_rejected_without_writes(api, tmp_path, mutation):
    ledger = opened(api, tmp_path)
    ledger.begin_attempt('a', 'r1', '1c', 'measured', 1)
    state = json.loads(ledger.path.read_bytes())
    if mutation == 'limits':
        state['limits']['total_wall_seconds'] = 999999
    elif mutation == 'sum':
        state['total_wall_seconds'] = 1
    elif mutation == 'running':
        state['running']['run_id'] = 'other'
    else:
        state['attempts'].append(dict(state['attempts'][0]))
    raw = json.dumps(state).encode()
    ledger.path.write_bytes(raw)
    with pytest.raises(api.LedgerIntegrityError):
        api.CampaignLedger.open(ledger.path, CampaignLimits())
    assert ledger.path.read_bytes() == raw


@pytest.mark.skipif(os.name != 'posix', reason='FIFO is a Linux artifact-tree case')
def test_fifo_artifact_is_rejected_without_read_or_delete(api, tmp_path):
    os.mkfifo(tmp_path / 'fifo')
    with pytest.raises(api.UnsafeArtifactTree):
        api.logical_tree_bytes(tmp_path)
    assert (tmp_path / 'fifo').exists()


def test_reopened_object_cannot_finish_known_running_id(api, tmp_path):
    owner = opened(api, tmp_path)
    owner.begin_attempt('a', 'r1', '1c', 'measured', 1)
    reopened = api.CampaignLedger.open(owner.path, CampaignLimits())
    with pytest.raises(api.UnresolvedPriorAttempt):
        finish(reopened, 'r1')
    assert owner.snapshot()['running']['run_id'] == 'r1'
    finish(owner, 'r1')
    assert owner.snapshot()['total_wall_seconds'] == 1


def _foreign_finish(path_or_ledger, result):
    from compute_metabolism.v0.campaign import CampaignLedger, UnresolvedPriorAttempt
    ledger = (CampaignLedger.open(Path(path_or_ledger), CampaignLimits())
              if isinstance(path_or_ledger, str) else path_or_ledger)
    try:
        finish(ledger, 'r1')
        result.put('finished')
    except UnresolvedPriorAttempt:
        result.put('blocked')


@pytest.mark.parametrize('method', ['spawn', 'fork'])
def test_new_process_or_fork_cannot_release_known_running_id(api, tmp_path, method):
    if method not in multiprocessing.get_all_start_methods():
        pytest.skip('fork is unavailable on this OS; Linux run covers it')
    owner = opened(api, tmp_path)
    owner.begin_attempt('a', 'r1', '1c', 'measured', 1)
    ctx = multiprocessing.get_context(method)
    result = ctx.Queue()
    target = str(owner.path) if method == 'spawn' else owner
    child = ctx.Process(target=_foreign_finish, args=(target, result))
    child.start()
    response = result.get(timeout=20)
    child.join(20)
    assert child.exitcode == 0
    assert response == 'blocked'
    assert owner.snapshot()['running']['run_id'] == 'r1'
    finish(owner, 'r1')


def test_read_snapshot_observes_new_metadata_without_file_lock_or_mtime_change(api, tmp_path):
    ledger = opened(api, tmp_path)
    stored = json.loads(ledger.path.read_bytes())['retained_total_bytes']
    ledger.authority_path.unlink()  # read-only status cannot re-create even absent lock
    (ledger.path.parent / 'late-report.txt').write_bytes(b'x' * 20)
    root = ledger.path.parent
    before = {str(p): (p.stat().st_size, p.stat().st_mtime_ns)
              for p in [root, *root.rglob('*')]}
    view = api.CampaignLedger.read_snapshot(ledger.path)
    after = {str(p): (p.stat().st_size, p.stat().st_mtime_ns)
             for p in [root, *root.rglob('*')]}
    assert before == after
    assert view['retained_total_bytes'] == stored
    assert view['observed_retained_total_bytes'] == stored + 19
    assert not ledger.authority_path.exists()
    assert view['total_wall_seconds'] == 0 and view['running'] is None


def test_read_snapshot_historical_incompatible_refuses_without_writes(api, tmp_path):
    path = tmp_path / 'historic.json'
    path.write_bytes(b'{"historic":true}')
    before = {str(p): (p.stat().st_size, p.stat().st_mtime_ns)
              for p in [tmp_path, path]}
    with pytest.raises(api.LedgerIntegrityError):
        api.CampaignLedger.read_snapshot(path)
    after = {str(p): (p.stat().st_size, p.stat().st_mtime_ns)
             for p in [tmp_path, *tmp_path.iterdir()]}
    assert before == after


@pytest.mark.skipif(os.name != 'posix', reason='Linux directory fsync durability boundary')
def test_new_artifact_ancestor_entries_fsynced_before_allowance_creation(api, tmp_path, monkeypatch):
    path = tmp_path / 'new-parent' / 'new-child' / 'artifacts' / 'upper.json'
    synced = []
    original_fsync = api.os.fsync
    def observe_fsync(fd):
        original_fsync(fd)
        if stat.S_ISDIR(os.fstat(fd).st_mode):
            directory = Path(os.readlink(f'/proc/self/fd/{fd}'))
            synced.append((directory, path.exists(), path.with_name('.upper.json.authority').exists()))
    monkeypatch.setattr(api.os, 'fsync', observe_fsync)
    ledger = api.CampaignLedger.open(path, CampaignLimits())
    # Real fsync succeeds on every child/parent entry before any allowance files.
    required = [path.parent, *path.parent.parents]
    prior = [directory for directory, ledger_exists, lock_exists in synced
             if not ledger_exists and not lock_exists]
    assert prior == required
    assert ledger.snapshot()['total_wall_seconds'] == 0


@pytest.mark.skipif(os.name != 'posix', reason='Linux directory fsync durability boundary')
def test_ancestor_fsync_failure_refuses_allowance_and_retry_still_syncs_ancestors(api, tmp_path, monkeypatch):
    path = tmp_path / 'new-parent' / 'new-child' / 'artifacts' / 'upper.json'
    authority = path.with_name('.upper.json.authority')
    original_fsync = api.os.fsync
    failures = []
    def parent_fsync_fails(fd):
        if stat.S_ISDIR(os.fstat(fd).st_mode):
            directory = Path(os.readlink(f'/proc/self/fd/{fd}'))
            if directory == tmp_path:
                failures.append(directory)
                raise OSError('controlled ancestor fsync failure')
        original_fsync(fd)
    monkeypatch.setattr(api.os, 'fsync', parent_fsync_fails)
    for _ in range(2):
        # Second invocation sees already-created empty directories but must not
        # skip the failed parent durability boundary or grant a zero allowance.
        with pytest.raises(OSError, match='controlled ancestor fsync failure'):
            api.CampaignLedger.open(path, CampaignLimits())
        assert path.parent.exists() and not path.exists() and not authority.exists()
    assert failures == [tmp_path, tmp_path]
    monkeypatch.setattr(api.os, 'fsync', original_fsync)
    ledger = api.CampaignLedger.open(path, CampaignLimits())
    assert ledger.snapshot()['total_wall_seconds'] == 0


# Task 5 synthetic policy fixtures; these never launch a numerical/system guard.
def policy_attempt(profile='2c', outcome='ACCEPT', wall=10, cpu=5, **extra):
    return dict(profile=profile, role='measured', status='FINISHED',
                wrapper_outcome=outcome, outcome=outcome, outer_wall_seconds=wall,
                cpu_seconds=cpu, eligible=True, resource_reason='OUTER_WALL_TIMEOUT',
                resource_proven=True, invariants_valid=True, campaign_stop=False,
                **extra)


def test_sample_cv_uses_sample_sd_and_rejects_undefined(api):
    assert hasattr(api, 'sample_cv'), 'Task 5 sample CV API missing'
    assert api.sample_cv([1, 2, 3]) == pytest.approx(0.5)
    for values in ([], [1], [0, 0], [1, None], [1, float('nan')]):
        with pytest.raises(ValueError):
            api.sample_cv(values)


@pytest.mark.parametrize('n,outcomes,expected', [
    (3, ['ACCEPT'], 'STABLE_ACCEPT'), (5, ['ACCEPT'], 'STABLE_ACCEPT'),
    (7, ['ACCEPT'], 'STABLE_ACCEPT'),
    (3, ['ACCEPT', 'REFUSED_RESOURCE'], 'EXPAND_TO_5'),
    (5, ['ACCEPT', 'REFUSED_RESOURCE'], 'EXPAND_TO_7'),
    (7, ['ACCEPT', 'REFUSED_RESOURCE'], 'UNRESOLVED_VARIABILITY'),
    (3, ['REFUSED_RESOURCE'], 'STOP_INCOMPLETE'),
    (3, ['UNRESOLVED_FAILURE'], 'STOP'),
])
def test_profile_outcome_consistency_before_cv(api, n, outcomes, expected):
    assert hasattr(api, 'profile_decision'), 'Task 5 profile API missing'
    attempts = [policy_attempt(outcome=outcomes[i % len(outcomes)]) for i in range(n)]
    assert api.profile_decision('2c', attempts)['decision'] == expected


@pytest.mark.parametrize('n,expected', [(3, 'EXPAND_TO_5'), (5, 'EXPAND_TO_7'), (7, 'UNRESOLVED_VARIABILITY')])
def test_unstable_cpu_alone_expands_without_dropping_outlier(api, n, expected):
    assert hasattr(api, 'profile_decision'), 'Task 5 profile API missing'
    attempts = [policy_attempt(cpu=1 if i == 0 else 20) for i in range(n)]
    decision = api.profile_decision('2c', attempts)
    assert decision['decision'] == expected and decision['n'] == n


@pytest.mark.parametrize('mutation', [None, 'reason', 'proof', 'fault', 'global', 'late'])
def test_half_core_first_three_stable_resource_only(api, mutation):
    assert hasattr(api, 'profile_decision'), 'Task 5 profile API missing'
    attempts = [policy_attempt('0p5c', 'REFUSED_RESOURCE') for _ in range(3)]
    if mutation == 'reason': attempts[1]['resource_reason'] = 'CGROUP_OOM'
    if mutation == 'proof': attempts[1]['resource_proven'] = False
    if mutation == 'fault': attempts[1]['invariants_valid'] = False
    if mutation == 'global': attempts[1].update(resource_reason='EVIDENCE_GROWTH', campaign_stop=True)
    if mutation == 'late': attempts = [policy_attempt('0p5c')] + attempts
    got = api.profile_decision('0p5c', attempts)['decision']
    assert (got == 'STABLE_RESOURCE_REFUSAL') == (mutation is None)


def test_exact_schedule_and_stable_profile_skips(api):
    assert hasattr(api, 'next_attempt'), 'Task 5 schedule API missing'
    history = [dict(role='warm-up', profile='2c', outcome='ACCEPT', eligible=True, status='FINISHED')]
    expected = [('2c','1c','0p5c'), ('1c','0p5c','2c'), ('0p5c','2c','1c'),
                ('2c','0p5c','1c'), ('0p5c','1c','2c'), ('1c','2c','0p5c'), ('2c','1c','0p5c')]
    for round_index, profiles in enumerate(expected, 1):
        for profile in profiles:
            got = api.next_attempt(history)
            assert (got['round_index'], got['profile'], got['requested_steps']) == (round_index, profile, 3)
            history.append(policy_attempt(profile, 'REFUSED_RESOURCE' if profile == '0p5c' and round_index == 1 else 'ACCEPT',
                                          wall=1 if round_index == 1 else 20,
                                          round_index=round_index))
    assert api.next_attempt(history) is None
    history = history[:10]
    for item in history[1:]:
        if item['profile'] == '1c': item['outer_wall_seconds'] = 10
    assert api.next_attempt(history)['profile'] == '2c'
    history.append(policy_attempt('2c', round_index=4))
    assert api.next_attempt(history)['profile'] == '0p5c'
    history.append(policy_attempt('0p5c', round_index=4))
    assert api.next_attempt(history)['round_index'] == 5


@pytest.mark.parametrize('outcome', ['REFUSED_RESOURCE', 'REFUSED_VERIFICATION', 'ENVIRONMENT_INVALID', 'UNRESOLVED_FAILURE'])
def test_any_warmup_failure_and_running_stop_schedule(api, outcome):
    assert hasattr(api, 'next_attempt'), 'Task 5 schedule API missing'
    assert api.next_attempt([]) == dict(profile='2c', role='warm-up', round_index=0, requested_steps=1)
    assert api.next_attempt([dict(role='warm-up', outcome=outcome, status='FINISHED')]) is None
    assert api.next_attempt([dict(role='warm-up', outcome='ACCEPT', status='RUNNING')]) is None


@pytest.mark.parametrize('reason', ['resource refusal', 'producer timeout 60', 'frame timeout 120'])
def test_strings_and_writer_counter_never_prove_resource(api, reason):
    assert hasattr(api, 'classify_attempt'), 'Task 5 classification API missing'
    got = api.classify_attempt({'outcome':'UNRESOLVED_FAILURE', 'raw_v1_result':{'verdict':'STOP', 'reason':reason}},
                               {'writer_bytes':671088640}, 1)
    assert got['wrapper_outcome'] == 'UNRESOLVED_FAILURE' and got['campaign_stop']
    assert got['v1_outcome'] == 'STOP'


def classification_fixture(tmp_path, outcome='UNRESOLVED_FAILURE', resource=True):
    """Synthetic LIVE-shaped contract data only; no acquired runtime authority."""
    import copy
    import hashlib
    from compute_metabolism.v0.profiles import APPROVED_V1_SOURCE_BINDING
    epoch = dict(path='/sys/fs/cgroup/system.slice/compute-metabolism-test.service',
                 device=1, inode=2, boot_id='test-boot')
    topology = {'0':dict(physical_package_id='0', core_id='0'), '1':dict(physical_package_id='0', core_id='1')}
    before = dict(epoch=epoch, cpus=[0,1], monotonic_seconds=1,
                  cpu_max=dict(unlimited=True, finite_ancestors=[]),
                  raw={'memory.max':'4294967296', 'memory.swap.max':'0'},
                  memory={'effective_bytes':4294967296}, swap={'effective_bytes':0},
                  cpu_stat=dict(usage_usec=10, user_usec=7, system_usec=3, nr_periods=1, nr_throttled=0, throttled_usec=0),
                  memory_events={'oom':0, 'oom_kill':0}, memory_peak=50,
                  pids=[42], process_identities={'42':{'start_ticks':'55'}})
    after = copy.deepcopy(before)
    after['monotonic_seconds'] = 181
    after['cpu_stat']['usage_usec'] = 5000010
    receipt = dict(run_id='r1', profile='2c', unit=epoch['path'].split('/')[-1],
                   test_only=False, deadline_seconds=180, writer_bytes=671088640,
                   before=before, after=after, wall_seconds=180.25,
                   terminal=True, launcher_reaped=True, measurement_valid=True,
                   outer_timeout_proved=resource, outcome='REFUSED_RESOURCE' if resource else 'GUARD_COMPLETE',
                   resource_reason='OUTER_WALL_TIMEOUT' if resource else None,
                   inner=dict(topology_before=topology, topology_after=topology,
                              containment={'remaining_pids':[]}, wrapper_identity={'pid':42, 'start_ticks':'55'},
                              cleanup_errors=[], final_errors=[]), cleanup_attempts=[])
    if not resource: receipt['wall_seconds'] = 10
    path = tmp_path / 'guard-outer.json'
    raw = json.dumps(receipt).encode()
    path.write_bytes(raw)
    receipt.update(proof_locator=str(path), proof_sha256=hashlib.sha256(raw).hexdigest())
    context = dict(run_id='r1', profile='2c', unit=receipt['unit'], epoch=epoch,
                   evidence_scope='LIVE', source_binding=APPROVED_V1_SOURCE_BINDING,
                   input_sha256={key:'a'*64 for key in ('execution-environment.json','campaign-environment.json','reference.json')},
                   environment_before_sha256='b'*64, environment_after_sha256='c'*64,
                   upper_before_sha256='d'*64, manifest_sha256='e'*64)
    report = dict(outcome=outcome, run_id='r1', raw_v1_result={'verdict':'ACCEPT' if outcome == 'ACCEPT' else 'STOP'},
                  admitted=outcome == 'ACCEPT', evidence_scope='LIVE',
                  correctness_authority='EXISTING_HASH_BOUND_LIVE_CHECKER', classification_context=context)
    return report, receipt


def test_structurally_bound_outer_timeout_can_explain_generic_stop(api, tmp_path):
    report, receipt = classification_fixture(tmp_path)
    got = api.classify_attempt(report, receipt, 10)
    assert got['wrapper_outcome'] == 'REFUSED_RESOURCE' and not got['campaign_stop']
    assert got['resource_proof']['epoch'] == receipt['before']['epoch']
    assert got['resource_proof']['ceiling'] == 180
    assert got['resource_proof']['sha256'] == receipt['proof_sha256']
    assert got['v1_outcome'] == 'STOP'


@pytest.mark.parametrize('mutation', ['hash', 'run', 'unit', 'profile', 'epoch', 'test', 'counter', 'cpu', 'fault'])
def test_resource_proof_cannot_hide_identity_or_measurement_fault(api, tmp_path, mutation):
    report, receipt = classification_fixture(tmp_path)
    if mutation == 'hash': receipt['proof_sha256'] = '0'*64
    if mutation == 'run': report['classification_context']['run_id'] = 'foreign'
    if mutation == 'unit': report['classification_context']['unit'] = 'foreign'
    if mutation == 'profile': report['classification_context']['profile'] = '1c'
    if mutation == 'epoch': report['classification_context']['epoch']['inode'] = 99
    if mutation == 'test': report['classification_context']['evidence_scope'] = 'TEST_ONLY'
    if mutation == 'counter': receipt['after']['cpu_stat']['usage_usec'] = 0
    if mutation == 'cpu': receipt.pop('after')
    if mutation == 'fault': report.update(outcome='REFUSED_VERIFICATION', reason='explicit checker refusal')
    got = api.classify_attempt(report, receipt, 10)
    assert got['campaign_stop'] and got['wrapper_outcome'] != 'REFUSED_RESOURCE'


def test_accept_evidence_growth_preserves_raw_accept_and_blocks(api, tmp_path):
    report, receipt = classification_fixture(tmp_path, 'ACCEPT', False)
    got = api.classify_attempt(report, receipt, 100663297)
    assert got['v1_outcome'] == 'ACCEPT' and got['wrapper_outcome'] == 'REFUSED_RESOURCE'
    assert got['resource_reason'] == 'EVIDENCE_GROWTH' and got['campaign_stop']
    assert api.classify_attempt(report, receipt, 100663296)['wrapper_outcome'] == 'ACCEPT'


@pytest.mark.parametrize('fault', ['ENVIRONMENT_INVALID', 'REFUSED_VERIFICATION'])
def test_explicit_fault_wins_over_structural_resource(api, tmp_path, fault):
    report, receipt = classification_fixture(tmp_path, fault)
    got = api.classify_attempt(report, receipt, 100663297)
    assert got['wrapper_outcome'] == fault and got['campaign_stop']


def cli_config(tmp_path, monkeypatch):
    import hashlib
    from compute_metabolism.v0 import system_guard as guard
    root = tmp_path / 'prepared'
    repo = root / 'workspace'
    repo.mkdir(parents=True)
    monkeypatch.setattr(guard, 'PREPARED_ROOT', root)
    identities = {}
    for relative in ('compute_metabolism/v0/profiles.py', 'compute_metabolism/v0/system_guard.py',
                     'compute_metabolism/v0/run_v1.py', 'compute_metabolism/v0/campaign.py',
                     'docs/superpowers/specs/2026-10-06-compute-metabolism-v0-design.md',
                     'docs/superpowers/plans/2026-10-06-compute-metabolism-v0.md'):
        target = repo / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        raw = (Path(__file__).parents[1]/relative).read_bytes()
        target.write_bytes(raw)
        identities[relative] = dict(path=str(target), sha256=hashlib.sha256(raw).hexdigest())
    inputs = {}
    for name in ('execution-environment.json', 'campaign-environment.json', 'reference.json'):
        target = tmp_path / name
        raw = json.dumps({'evidence_scope':'TEST_ONLY', 'topology':{'0':dict(core_id='0',physical_package_id='0'),'1':dict(core_id='1',physical_package_id='0')}}).encode()
        target.write_bytes(raw)
        inputs[name] = dict(path=str(target), sha256=hashlib.sha256(raw).hexdigest())
    config = dict(schema='COMPUTE_METABOLISM_CAMPAIGN_V0', campaign_id='gcp-test',
                  root_directory=str(root), repo_root=str(repo),
                  ledger_path=str(repo/'compute_metabolism/v0/artifacts/budget.json'),
                  inputs=inputs, identities=identities)
    path = tmp_path / 'launch-config.json'
    raw = json.dumps(config).encode()
    path.write_bytes(raw)
    return path, hashlib.sha256(raw).hexdigest(), config


def test_cli_init_freezes_raw_files_and_status_writes_nothing(api, tmp_path, monkeypatch, capsys):
    assert hasattr(api, 'main'), 'Task 5 campaign CLI missing'
    path, digest, config = cli_config(tmp_path, monkeypatch)
    assert api.main(['init','--config',str(path),'--config-sha256',digest]) == 0
    root = Path(config['ledger_path']).parent
    campaign = root/'gcp-test'
    assert (campaign/'campaign.json').read_bytes() == path.read_bytes()
    for name, item in config['inputs'].items():
        assert (campaign/name).read_bytes() == Path(item['path']).read_bytes()
    before = {str(p):(p.stat().st_size,p.stat().st_mtime_ns) for p in [root,*root.rglob('*')]}
    assert api.main(['status','--config',str(path),'--config-sha256',digest]) == 0
    after = {str(p):(p.stat().st_size,p.stat().st_mtime_ns) for p in [root,*root.rglob('*')]}
    assert before == after
    assert api.main(['init','--config',str(path),'--config-sha256',digest]) == 2
    assert Path(config['ledger_path']).exists()


def test_first_formal_init_after_preflight_never_resets_upper(api, tmp_path, monkeypatch, capsys):
    assert hasattr(api, 'main'), 'Task 5 campaign CLI missing'
    path, digest, config = cli_config(tmp_path, monkeypatch)
    ledger = api.CampaignLedger.open(Path(config['ledger_path']), CampaignLimits())
    ledger.begin_attempt('preflight','probe','2c','guard-preflight',0)
    finish(ledger,'probe',wall=9,outcome='GUARD_COMPLETE')
    assert api.main(['init','--config',str(path),'--config-sha256',digest]) == 0
    assert api.CampaignLedger.read_snapshot(ledger.path)['total_wall_seconds'] == 9
    config['campaign_id'] = 'gcp-another'
    import hashlib
    raw = json.dumps(config).encode()
    other = tmp_path/'new-config.json'
    other.write_bytes(raw)
    assert api.main(['init','--config',str(other),'--config-sha256',hashlib.sha256(raw).hexdigest()]) == 2


@pytest.mark.parametrize('terminal', [True, False])
def test_run_next_exactly_one_guard_same_owner_and_durable_stop(api, tmp_path, monkeypatch, terminal):
    assert hasattr(api, 'main'), 'Task 5 campaign CLI missing'
    path, digest, config = cli_config(tmp_path, monkeypatch)
    assert api.main(['init','--config',str(path),'--config-sha256',digest]) == 0
    from compute_metabolism.v0 import system_guard as guard
    seen = []
    def fake_guard(profile, **kwargs):
        state = api.CampaignLedger.read_snapshot(Path(config['ledger_path']))
        assert state['running'] == dict(campaign_id='gcp-test',run_id='r1',profile='2c',role='warm-up',round_index=0)
        target = kwargs['artifact_dir']
        assert target == Path(config['ledger_path']).parent/'gcp-test/warmup/r1'
        assert '--config-sha256' in kwargs['command']
        assert kwargs['command'][0] == guard.INNER_PYTHON
        target.mkdir()
        (target/'writer_quota.txt').write_bytes(b'17')
        result = dict(run_id='r1',profile='2c',outcome='ENVIRONMENT_INVALID',wall_seconds=2,
                      terminal=terminal,launcher_reaped=terminal,measurement_valid=False)
        (target/'guard-outer.json').write_text(json.dumps(result))
        seen.append(kwargs)
        return result
    monkeypatch.setattr(guard,'run_system_guard',fake_guard)
    argv = ['run-next','--config',str(path),'--config-sha256',digest,'--run-id','r1']
    assert api.main(argv) == 2
    state = api.CampaignLedger.read_snapshot(Path(config['ledger_path']))
    assert len(seen) == 1 and len(state['attempts']) == 1
    assert state['attempts'][0]['status'] == ('FINISHED' if terminal else 'RUNNING')
    if terminal:
        assert state['total_wall_seconds'] == 2
        assert state['attempts'][0]['writer_reserved_bytes'] == 17
    else:
        assert state['attempts'][0]['partial_receipts'] and state['running']['run_id'] == 'r1'
    argv[-1] = 'r2'
    assert api.main(argv) == 2 and len(seen) == 1


def test_config_or_wrapper_drift_blocks_guard_before_launch(api, tmp_path, monkeypatch):
    assert hasattr(api, 'main'), 'Task 5 campaign CLI missing'
    path, digest, config = cli_config(tmp_path, monkeypatch)
    assert api.main(['init','--config',str(path),'--config-sha256',digest]) == 0
    Path(config['identities']['compute_metabolism/v0/run_v1.py']['path']).write_bytes(b'drift')
    assert api.main(['run-next','--config',str(path),'--config-sha256',digest,'--run-id','r1']) == 2
    assert api.CampaignLedger.read_snapshot(Path(config['ledger_path']))['attempts'] == []


def test_saved_helper_checks_inner_hashes_and_never_mutates_evidence(api, tmp_path, monkeypatch, capsys):
    assert hasattr(api, '_classification_helper'), 'read-only prepared helper missing'
    import hashlib
    import io
    root = tmp_path/'v1'
    root.mkdir()
    for name in api._CONTEXT_FILES:
        (root/name).write_bytes(b'{"evidence_scope":"TEST_ONLY"}')
    target = root/'attempt.json'
    request = dict(root=str(root), evidence_sha256={name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in api._CONTEXT_FILES})
    monkeypatch.setattr(api, '_saved_classification_context', lambda path:dict(run_id='r1', evidence_scope='TEST_ONLY'))
    monkeypatch.setattr(api, '_helper_root', lambda path: Path(path))
    monkeypatch.setattr(api.sys,'stdin',io.StringIO(json.dumps(request)))
    before = target.stat().st_mtime_ns
    api._classification_helper()
    output = json.loads(capsys.readouterr().out)
    assert output['context']['run_id'] == 'r1' and output['evidence_sha256'] == request['evidence_sha256']
    assert before == target.stat().st_mtime_ns and set(p.name for p in root.iterdir()) == set(api._CONTEXT_FILES)
    request['evidence_sha256']['attempt.json'] = '0'*64
    monkeypatch.setattr(api.sys,'stdin',io.StringIO(json.dumps(request)))
    with pytest.raises(ValueError): api._classification_helper()


def test_post_helper_fixed_prepared_command_hash_binding_and_admin_timing(api, tmp_path, monkeypatch):
    assert hasattr(api, '_post_context'), 'prepared namespace integration missing'
    path, digest, config = cli_config(tmp_path, monkeypatch)
    root = Path(config['ledger_path']).parent/'gcp-test/warmup/r1/v1'
    root.mkdir(parents=True)
    for name in api._CONTEXT_FILES:
        (root/name).write_bytes(b'{"evidence_scope":"TEST_ONLY"}')
    report, receipt = classification_fixture(tmp_path)
    context = report['classification_context']
    def fake_subprocess(argv, **kwargs):
        from types import SimpleNamespace
        assert argv[:4] == ['sudo','-n','chroot',config['root_directory']]
        assert '-B' in argv and 'PYTHONDONTWRITEBYTECODE=1' in argv
        assert '--chdir=/workspace' in argv
        request = json.loads(kwargs['input'])
        assert request['root'] == '/workspace/compute_metabolism/v0/artifacts/gcp-test/warmup/r1/v1'
        context.update(manifest_sha256=request['evidence_sha256']['attempt.json'],
                       environment_before_sha256=request['evidence_sha256']['environment-before.json'],
                       environment_after_sha256=request['evidence_sha256']['environment-after.json'],
                       input_sha256={name:request['evidence_sha256'][name] for name in api._INPUT_FILES},
                       upper_before_sha256=request['evidence_sha256']['upper-ledger-before.json'])
        return SimpleNamespace(stdout=json.dumps(dict(context=context,evidence_sha256=request['evidence_sha256'])).encode(),stderr=b'',returncode=0)
    monkeypatch.setattr(api.subprocess,'run',fake_subprocess)
    got, administration = api._post_context(root, config, receipt)
    assert got == context and administration['wall_seconds'] >= 0
    assert administration['measurement_role'] == 'ADMINISTRATION_ONLY'
    context['run_id'] = 'foreign'
    with pytest.raises(ValueError): api._post_context(root, config, receipt)


def test_helper_failure_preserves_raw_result_and_administration_time(api,tmp_path,monkeypatch):
    assert hasattr(api,'HelperFailure'), 'helper failure evidence API missing'
    from types import SimpleNamespace
    path,digest,config = cli_config(tmp_path,monkeypatch)
    root = Path(config['ledger_path']).parent/'gcp-test/warmup/r1/v1'
    root.mkdir(parents=True)
    for name in api._CONTEXT_FILES: (root/name).write_bytes(b'{}')
    report,receipt = classification_fixture(tmp_path)
    monkeypatch.setattr(api.subprocess,'run',lambda *args,**kwargs:SimpleNamespace(stdout=b'partial helper',stderr=b'failure',returncode=2))
    with pytest.raises(api.HelperFailure) as failed: api._post_context(root,config,receipt)
    assert failed.value.administration['stdout_hex'] == b'partial helper'.hex()
    assert failed.value.administration['stderr_hex'] == b'failure'.hex()
    assert failed.value.administration['wall_seconds'] >= 0


def test_saved_context_uses_task4_pure_validator_api_and_actual_runtime_source(api, tmp_path, monkeypatch):
    from compute_metabolism.v0 import run_v1 as runner
    from compute_metabolism.v0.profiles import APPROVED_V1_SOURCE_BINDING
    root = tmp_path/'v1'
    root.mkdir()
    manifest = dict(run_id='r1',profile='2c',campaign_id='gcp-test',round_index=0,role='warm-up',evidence_scope='TEST_ONLY',
                    inputs={name:'a'*64 for name in api._INPUT_FILES},upper_before_sha256='b'*64)
    (root/'attempt.json').write_text(json.dumps(manifest))
    for name in ('environment-before.json','environment-after.json'): (root/name).write_bytes(b'{}')
    calls = []
    def environment(path, saved):
        calls.append(('environment',path,saved))
        return {'runtime':{'source_binding':APPROVED_V1_SOURCE_BINDING}}, [{'snapshot':{'epoch':{'path':'/sys/fs/cgroup/system.slice/compute-metabolism-test.service'}}}], {}, {}
    def upper(path, saved):
        calls.append(('upper',path,saved))
        return {'running':{}}
    monkeypatch.setattr(runner,'_environment_evidence',environment)
    monkeypatch.setattr(runner,'_saved_upper_before',upper)
    context = api._saved_classification_context(root)
    assert context['source_binding'] == APPROVED_V1_SOURCE_BINDING
    assert [name for name,_,_ in calls] == ['environment','upper']
    assert all(saved == manifest for _,_,saved in calls)


def test_structural_resource_cannot_hide_explicit_runner_error(api, tmp_path):
    report, receipt = classification_fixture(tmp_path)
    report['runner_errors'] = [{'stage':'run','outcome':'REFUSED_VERIFICATION','error':'bound checker violation'}]
    got = api.classify_attempt(report,receipt,10)
    assert got['wrapper_outcome'] == 'REFUSED_VERIFICATION' and got['campaign_stop']


@pytest.mark.parametrize('path', ['/tmp/v1','/workspace/compute_metabolism/v0/artifacts/../bad/v1',
                                '/workspace/compute_metabolism/v0/artifacts/gcp-test/round-08/r1/v1'])
def test_helper_namespace_refuses_escape_or_attempt8(api, path):
    with pytest.raises(ValueError): api._helper_root(path)


def test_half_core_resource_only_different_reasons_stops_incomplete(api):
    attempts = [policy_attempt('0p5c','REFUSED_RESOURCE') for _ in range(3)]
    attempts[1]['resource_reason'] = 'CGROUP_OOM'
    assert api.profile_decision('0p5c',attempts)['decision'] == 'STOP_INCOMPLETE'


def test_completed_resource_only_two_core_stops_before_remaining_round_slot(api):
    history = [dict(role='warm-up',profile='2c',outcome='ACCEPT',eligible=True,status='FINISHED')]
    for round_index, order in enumerate((('2c','1c','0p5c'),('1c','0p5c','2c'),('0p5c','2c')),1):
        for profile in order:
            history.append(policy_attempt(profile,'REFUSED_RESOURCE' if profile == '2c' else 'ACCEPT',round_index=round_index))
    assert api.next_attempt(history) is None


def test_config_cannot_pin_different_executing_campaign_wrapper(api, tmp_path, monkeypatch):
    import hashlib
    path, digest, config = cli_config(tmp_path,monkeypatch)
    identity = config['identities']['compute_metabolism/v0/campaign.py']
    Path(identity['path']).write_bytes(b'foreign campaign implementation')
    identity['sha256'] = hashlib.sha256(b'foreign campaign implementation').hexdigest()
    raw = json.dumps(config).encode()
    path.write_bytes(raw)
    assert api.main(['init','--config',str(path),'--config-sha256',hashlib.sha256(raw).hexdigest()]) == 2
    assert not Path(config['ledger_path']).exists()


def test_success_run_next_advances_only_on_next_explicit_call(api,tmp_path,monkeypatch):
    path,digest,config = cli_config(tmp_path,monkeypatch)
    assert api.main(['init','--config',str(path),'--config-sha256',digest]) == 0
    from compute_metabolism.v0 import system_guard as guard
    seen = []
    contexts = {}
    def fake_guard(profile, **kwargs):
        parent = kwargs['artifact_dir']
        parent.mkdir()
        (parent/'writer_quota.txt').write_bytes(b'17')
        report,receipt = classification_fixture(tmp_path,'ACCEPT',False)
        receipt = {k:v for k,v in receipt.items() if k not in ('proof_locator','proof_sha256')}
        receipt['run_id'] = report['run_id'] = kwargs['run_id']
        context = report.pop('classification_context')
        running = api.CampaignLedger.read_snapshot(Path(config['ledger_path']))['running']
        context.update(running)
        contexts[parent/'v1'] = context
        (parent/'guard-outer.json').write_text(json.dumps(receipt))
        (parent/'v1').mkdir()
        (parent/'v1/admission.json').write_text(json.dumps(report))
        seen.append(running)
        return receipt
    monkeypatch.setattr(guard,'run_system_guard',fake_guard)
    monkeypatch.setattr(api,'_post_context',lambda root,config,receipt:(contexts[root],dict(measurement_role='ADMINISTRATION_ONLY',wall_seconds=.01)))
    # Host administrative orchestration must not import the numerical runner;
    # only the already-authorized prepared readonly helper imports Task 4.
    monkeypatch.setitem(api.sys.modules,'compute_metabolism.v0.run_v1',None)
    import compute_metabolism.v0 as package
    monkeypatch.delattr(package,'run_v1',raising=False)
    prefix = ['run-next','--config',str(path),'--config-sha256',digest,'--run-id']
    assert api.main(prefix+['r1']) == 0
    first = api.CampaignLedger.read_snapshot(Path(config['ledger_path']))
    assert first['running'] is None and len(first['attempts']) == 1
    assert first['attempts'][0]['outcome'] == 'ACCEPT'
    assert api.main(prefix+['r2']) == 0
    second = api.CampaignLedger.read_snapshot(Path(config['ledger_path']))
    assert second['total_wall_seconds'] == 20 and len(second['attempts']) == 2
    assert [row['role'] for row in seen] == ['warm-up','measured']
    assert seen[1]['profile'] == '2c' and seen[1]['round_index'] == 1


def install_admitted_guard(api,tmp_path,monkeypatch,config,wall=lambda row:10,after=None):
    """Synthetic acquisition boundary; keep real campaign writes/accounting."""
    from compute_metabolism.v0 import system_guard as guard
    contexts, seen = {}, []
    def fake_guard(profile, **kwargs):
        parent = kwargs['artifact_dir']
        parent.mkdir()
        (parent/'writer_quota.txt').write_bytes(b'17')
        running = api.CampaignLedger.read_snapshot(Path(config['ledger_path']))['running']
        amount = wall(running)
        report,receipt = classification_fixture(tmp_path,'ACCEPT',amount >= 180)
        receipt = {key:value for key,value in receipt.items() if key not in ('proof_locator','proof_sha256')}
        receipt.update(run_id=running['run_id'],wall_seconds=amount)
        report['run_id'] = running['run_id']
        context = report.pop('classification_context')
        context.update(running)
        contexts[parent/'v1'] = context
        (parent/'guard-outer.json').write_bytes(json.dumps(receipt).encode())
        (parent/'v1').mkdir()
        (parent/'v1/admission.json').write_bytes(json.dumps(report).encode())
        seen.append(running)
        if after: after(running,parent)
        return receipt
    monkeypatch.setattr(guard,'run_system_guard',fake_guard)
    monkeypatch.setattr(api,'_post_context',lambda root,config,receipt:(contexts[root],dict(measurement_role='ADMINISTRATION_ONLY',wall_seconds=.01)))
    return seen


@pytest.mark.parametrize('dependency',['profiles','system_guard'])
def test_imported_host_shadow_source_mismatch_refuses_before_launch(api,tmp_path,monkeypatch,capsys,dependency):
    import copy
    import importlib
    path,digest,config = cli_config(tmp_path,monkeypatch)
    assert api.main(['init','--config',str(path),'--config-sha256',digest]) == 0
    capsys.readouterr()
    seen = install_admitted_guard(api,tmp_path,monkeypatch,config)
    module = importlib.import_module('compute_metabolism.v0.'+dependency)
    original_file,original_spec = module.__file__,module.__spec__
    shadow = tmp_path/'shadow'/f'{dependency}.py'
    shadow.parent.mkdir()
    shadow.write_bytes(b'TEST_ONLY different host dependency')
    spec = copy.copy(module.__spec__)
    spec.origin = str(shadow)
    monkeypatch.setattr(module,'__file__',str(shadow))
    monkeypatch.setattr(module,'__spec__',spec)
    assert api.main(['run-next','--config',str(path),'--config-sha256',digest,'--run-id','r1']) == 2
    output = json.loads(capsys.readouterr().out)
    assert output['wrapper_outcome'] == 'ENVIRONMENT_INVALID' and output['campaign_stop']
    assert not seen and api.CampaignLedger.read_snapshot(Path(config['ledger_path']))['attempts'] == []
    marker = Path(config['ledger_path']).parent/'gcp-test/host-source-stop.json'
    assert marker.exists(), 'prelaunch source STOP must remain durable without issuing RUNNING'
    monkeypatch.setattr(module,'__file__',original_file)
    monkeypatch.setattr(module,'__spec__',original_spec)
    assert api.main(['run-next','--config',str(path),'--config-sha256',digest,'--run-id','r2']) == 2
    assert not seen


@pytest.mark.parametrize('dependency',['profiles','system_guard'])
def test_imported_host_source_drift_after_execution_stops_and_preserves_cost(api,tmp_path,monkeypatch,capsys,dependency):
    import copy,importlib
    path,digest,config = cli_config(tmp_path,monkeypatch)
    assert api.main(['init','--config',str(path),'--config-sha256',digest]) == 0
    capsys.readouterr()
    def shadow_after(row,parent):
        module = importlib.import_module('compute_metabolism.v0.'+dependency)
        shadow = tmp_path/f'after-{dependency}.py'
        shadow.write_bytes(b'TEST_ONLY drift after actual guard boundary')
        spec = copy.copy(module.__spec__)
        spec.origin = str(shadow)
        monkeypatch.setattr(module,'__file__',str(shadow))
        monkeypatch.setattr(module,'__spec__',spec)
    seen = install_admitted_guard(api,tmp_path,monkeypatch,config,after=shadow_after)
    assert api.main(['run-next','--config',str(path),'--config-sha256',digest,'--run-id','r1']) == 2
    output = json.loads(capsys.readouterr().out)
    assert output['classification']['wrapper_outcome'] == 'ENVIRONMENT_INVALID'
    state = api.CampaignLedger.read_snapshot(Path(config['ledger_path']))
    assert len(seen) == 1 and state['running'] is None and state['total_wall_seconds'] == 10
    assert output['classification']['v1_outcome'] == 'ACCEPT'
    assert output['host_dependencies_after']['status'] == 'ENVIRONMENT_INVALID'


def test_uncapped_cleanup_over_upper_wall_additive_global_stop(api,tmp_path,monkeypatch,capsys):
    path,digest,config = cli_config(tmp_path,monkeypatch)
    ledger = api.CampaignLedger.open(Path(config['ledger_path']),CampaignLimits())
    ledger.begin_attempt('preflight','p1','2c','guard-preflight',0)
    finish(ledger,'p1',wall=4000,outcome='GUARD_COMPLETE')
    assert api.main(['init','--config',str(path),'--config-sha256',digest]) == 0
    seen = install_admitted_guard(api,tmp_path,monkeypatch,config,wall=lambda row:10 if row['role']=='warm-up' else 191)
    prefix = ['run-next','--config',str(path),'--config-sha256',digest,'--run-id']
    assert api.main(prefix+['r1']) == 0
    capsys.readouterr()
    assert api.main(prefix+['r2']) == 2
    result = json.loads(capsys.readouterr().out)
    assert result['campaign_outcome'] == 'CAMPAIGN_RESOURCE_EXHAUSTED' and result['campaign_stop']
    assert result['campaign_finalization']['resource_reason'] == 'CAMPAIGN_WALL_CEILING'
    assert result['campaign_finalization']['resource_proof']['observed'] == 4201
    local = Path(config['ledger_path']).parent/'gcp-test/round-01/r2/execution.json'
    saved = json.loads(local.read_bytes())
    assert saved['classification']['v1_outcome'] == 'ACCEPT'
    assert saved['classification']['campaign_outcome'] == 'CONTINUE'
    state = api.CampaignLedger.read_snapshot(Path(config['ledger_path']))
    assert state['total_wall_seconds'] == 4201 and state['running'] is None
    assert state['campaign_resource_stop']['campaign_outcome'] == 'CAMPAIGN_RESOURCE_EXHAUSTED'
    assert len(seen) == 2


@pytest.mark.parametrize('resource',['wall','retained'])
def test_insufficient_full_next_allowance_status_readonly_run_next_structured_stop(api,tmp_path,monkeypatch,capsys,resource):
    path,digest,config = cli_config(tmp_path,monkeypatch)
    assert api.main(['init','--config',str(path),'--config-sha256',digest]) == 0
    ledger = api.CampaignLedger.open(Path(config['ledger_path']),CampaignLimits())
    if resource == 'wall':
        ledger.begin_attempt('preflight','p1','2c','guard-preflight',0)
        finish(ledger,'p1',wall=4100,outcome='GUARD_COMPLETE')
    else:
        sparse = ledger.root/'global-sparse.bin'
        sparse.touch()
        with sparse.open('r+b') as stream: stream.truncate(3221225472-100663296)
    capsys.readouterr()
    before = {str(p):(p.stat().st_size,p.stat().st_mtime_ns) for p in [ledger.root,*ledger.root.rglob('*')]}
    assert api.main(['status','--config',str(path),'--config-sha256',digest]) == 2
    output = json.loads(capsys.readouterr().out)
    assert output['campaign_outcome'] == 'CAMPAIGN_RESOURCE_EXHAUSTED' and output['next_attempt'] is None
    assert output['resource_proof']['ceiling'] == (4200 if resource=='wall' else 3221225472)
    after = {str(p):(p.stat().st_size,p.stat().st_mtime_ns) for p in [ledger.root,*ledger.root.rglob('*')]}
    assert before == after
    seen = install_admitted_guard(api,tmp_path,monkeypatch,config)
    assert api.main(['run-next','--config',str(path),'--config-sha256',digest,'--run-id','r1']) == 2
    output = json.loads(capsys.readouterr().out)
    assert output['campaign_outcome'] == 'CAMPAIGN_RESOURCE_EXHAUSTED' and not seen
    assert api.CampaignLedger.read_snapshot(ledger.path)['running'] is None


def test_upper_retained_growth_after_guard_stops_without_rewriting_attempt(api,tmp_path,monkeypatch,capsys):
    path,digest,config = cli_config(tmp_path,monkeypatch)
    assert api.main(['init','--config',str(path),'--config-sha256',digest]) == 0
    root = Path(config['ledger_path']).parent
    def grow(row,parent):
        sparse = root/'global-sparse.bin'
        sparse.touch()
        other = api.logical_tree_bytes(root)
        with sparse.open('r+b') as stream: stream.truncate(3221225472-other-1)
    seen = install_admitted_guard(api,tmp_path,monkeypatch,config,after=grow)
    capsys.readouterr()
    assert api.main(['run-next','--config',str(path),'--config-sha256',digest,'--run-id','r1']) == 2
    output = json.loads(capsys.readouterr().out)
    assert output['campaign_finalization']['resource_reason'] == 'CAMPAIGN_EVIDENCE_CEILING'
    state = api.CampaignLedger.read_snapshot(Path(config['ledger_path']))
    assert state['observed_retained_total_bytes'] >= 3221225472 and len(seen)==1
    assert output['classification']['v1_outcome'] == 'ACCEPT'
    assert output['classification']['wrapper_outcome'] == 'ACCEPT'


def test_completed_below_ceilings_does_not_require_unused_next_allowance(api,tmp_path,monkeypatch,capsys):
    path,digest,config = cli_config(tmp_path,monkeypatch)
    assert api.main(['init','--config',str(path),'--config-sha256',digest]) == 0
    ledger = api.CampaignLedger.open(Path(config['ledger_path']),CampaignLimits())
    rows = [(0,'2c','warm-up')]+[(n,p,'measured') for n,order in enumerate((('2c','1c','0p5c'),('1c','0p5c','2c'),('0p5c','2c','1c')),1) for p in order]
    for index,(round_index,profile,role) in enumerate(rows):
        run_id=f'completed-{index}'
        ledger.begin_attempt('gcp-test',run_id,profile,role,round_index)
        finish(ledger,run_id)
    with ledger._authority():
        state = api._read(ledger.path)
        for row in state['attempts']: row.update(eligible=True,invariants_valid=True,campaign_stop=False)
        ledger._write(state)
    ledger.begin_attempt('preflight','p1','2c','guard-preflight',0)
    finish(ledger,'p1',wall=4090,outcome='GUARD_COMPLETE')
    capsys.readouterr()
    assert api.main(['status','--config',str(path),'--config-sha256',digest]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output['next_attempt'] is None and output.get('campaign_stop') is False
    assert output['upper']['total_wall_seconds'] == 4100


def test_finalization_files_alone_cross_upper_retained_ceiling_and_are_counted(api,tmp_path,monkeypatch,capsys):
    import hashlib
    assert hasattr(api,'_finalize_upper'), 'additive upper finalization API missing'
    path,digest,config = cli_config(tmp_path,monkeypatch)
    assert api.main(['init','--config',str(path),'--config-sha256',digest]) == 0
    install_admitted_guard(api,tmp_path,monkeypatch,config)
    original = api._finalize_upper
    def place_at_boundary(ledger,config,run_id,needs_next,phase):
        assert phase=='POST_FINISH'
        sparse = ledger.root/'finalization-boundary.bin'
        sparse.touch()
        with sparse.open('r+b') as stream: stream.truncate(3221225472-100000)
        ledger.snapshot()  # stabilize ledger metadata at a ten-digit length
        other = api.logical_tree_bytes(ledger.root)-sparse.stat().st_size
        with sparse.open('r+b') as stream: stream.truncate(3221225472-other-1)
        assert api.CampaignLedger.read_snapshot(ledger.path)['observed_retained_total_bytes'] == 3221225471
        return original(ledger,config,run_id,needs_next,phase)
    monkeypatch.setattr(api,'_finalize_upper',place_at_boundary)
    capsys.readouterr()
    assert api.main(['run-next','--config',str(path),'--config-sha256',digest,'--run-id','r1']) == 2
    result = json.loads(capsys.readouterr().out)
    receipt = result['campaign_finalization']
    proof = json.loads(Path(receipt['upper_proof_locator']).read_bytes())
    assert proof['retained_total_bytes']==3221225471
    assert receipt['resource_reason']=='CAMPAIGN_EVIDENCE_CEILING'
    assert receipt['observed_retained_total_bytes']>3221225472
    state = api.CampaignLedger.read_snapshot(Path(config['ledger_path']))
    assert state['retained_total_bytes']==state['observed_retained_total_bytes']==receipt['observed_retained_total_bytes']
    raw = Path(receipt['finalization_locator']).read_bytes()
    assert hashlib.sha256(raw).hexdigest()==receipt['finalization_sha256']
    saved = json.loads(raw)
    assert saved['observed_retained_total_bytes']==receipt['observed_retained_total_bytes']


def test_new_config_metadata_exhausts_full_allowance_before_begin_without_launch(api,tmp_path,monkeypatch,capsys):
    path,digest,config = cli_config(tmp_path,monkeypatch)
    assert api.main(['init','--config',str(path),'--config-sha256',digest]) == 0
    ledger = api.CampaignLedger.open(Path(config['ledger_path']),CampaignLimits())
    sparse = ledger.root/'exact-allowance.bin'
    sparse.touch()
    with sparse.open('r+b') as stream: stream.truncate(3221225472-100663296-100000)
    ledger.snapshot()
    other = api.logical_tree_bytes(ledger.root)-sparse.stat().st_size
    with sparse.open('r+b') as stream: stream.truncate(3221225472-100663296-other)
    assert api.CampaignLedger.read_snapshot(ledger.path)['observed_retained_total_bytes']==3221225472-100663296
    seen = install_admitted_guard(api,tmp_path,monkeypatch,config)
    capsys.readouterr()
    assert api.main(['run-next','--config',str(path),'--config-sha256',digest,'--run-id','r1']) == 2
    result = json.loads(capsys.readouterr().out)
    assert result['campaign_outcome']=='CAMPAIGN_RESOURCE_EXHAUSTED'
    assert result['campaign_finalization']['phase']=='PRELAUNCH' and not seen
    state = api.CampaignLedger.read_snapshot(ledger.path)
    assert state['running'] is None and state['attempts']==[]
    assert state['start_refusals'][0]['reason']=='CAMPAIGN_RETAINED_EXHAUSTED'


def test_failed_finalization_preserves_finished_cost_and_blocks_next_without_running_release(api,tmp_path,monkeypatch,capsys):
    path,digest,config = cli_config(tmp_path,monkeypatch)
    assert api.main(['init','--config',str(path),'--config-sha256',digest]) == 0
    seen = install_admitted_guard(api,tmp_path,monkeypatch,config)
    original = api._exclusive_raw
    def fail_final(path,raw):
        if path.name.startswith('campaign-finalization-'): raise OSError('TEST_ONLY finalization write failure')
        return original(path,raw)
    monkeypatch.setattr(api,'_exclusive_raw',fail_final)
    capsys.readouterr()
    prefix = ['run-next','--config',str(path),'--config-sha256',digest,'--run-id']
    assert api.main(prefix+['r1']) == 2
    state = api.CampaignLedger.read_snapshot(Path(config['ledger_path']))
    assert state['running'] is None and state['total_wall_seconds']==10
    assert state['attempts'][0]['status']=='FINISHED' and state['attempts'][0]['outcome']=='ACCEPT'
    assert state['campaign_finalization_unresolved']['campaign_stop'] is True
    assert api.main(prefix+['r2']) == 2 and len(seen)==1


def test_failed_stop_ledger_write_preserves_pending_and_readonly_view_blocks_finished_gap(api,tmp_path,monkeypatch,capsys):
    path,digest,config = cli_config(tmp_path,monkeypatch)
    assert api.main(['init','--config',str(path),'--config-sha256',digest]) == 0
    seen = install_admitted_guard(api,tmp_path,monkeypatch,config)
    original_raw,original_replace = api._exclusive_raw,api.os.replace
    fail_replace = [False]
    def fail_final(path,raw):
        if path.name.startswith('campaign-finalization-'):
            fail_replace[0]=True
            raise OSError('TEST_ONLY finalization followed by STOP-write failure')
        return original_raw(path,raw)
    def replace_unavailable(source,target):
        if fail_replace[0]: raise OSError('TEST_ONLY STOP ledger replacement failed')
        return original_replace(source,target)
    monkeypatch.setattr(api,'_exclusive_raw',fail_final)
    monkeypatch.setattr(api.os,'replace',replace_unavailable)
    prefix=['run-next','--config',str(path),'--config-sha256',digest,'--run-id']
    assert api.main(prefix+['r1'])==2
    ledger_path=Path(config['ledger_path'])
    state=api.CampaignLedger.read_snapshot(ledger_path)
    assert state['running'] is None and state['total_wall_seconds']==10
    assert state['attempts'][0]['outcome']=='ACCEPT' and 'campaign_finalization_unresolved' not in state
    assert list(ledger_path.parent.glob('.budget.json.*.pending'))
    fail_replace[0]=False
    capsys.readouterr()
    before={str(p):(p.stat().st_size,p.stat().st_mtime_ns) for p in [ledger_path.parent,*ledger_path.parent.rglob('*')]}
    assert api.main(['status','--config',str(path),'--config-sha256',digest])==2
    result=json.loads(capsys.readouterr().out)
    assert result['upper']['campaign_finalization_unresolved']['reason']=='MISSING_DURABLE_POST_FINISH_FINALIZATION'
    after={str(p):(p.stat().st_size,p.stat().st_mtime_ns) for p in [ledger_path.parent,*ledger_path.parent.rglob('*')]}
    assert before==after
    assert api.main(prefix+['r2'])==2 and len(seen)==1


def test_finalization_decimal_remaining_cycle_finishes_with_exact_actual_metadata(api,tmp_path,monkeypatch):
    """An owned bounded serializer probe finds the real filesystem 10000-byte boundary."""
    import hashlib
    boundary = 3221215472  # actual ceiling minus 10000, not a new budget
    original_raw,original_encode = api._exclusive_raw,api._encode
    class ProbeComplete(Exception): pass
    class TestSizingBudgetExpired(Exception): pass

    def fixture(name):
        ledger = api.CampaignLedger.open(tmp_path/name/'upper.json',CampaignLimits())
        ledger.begin_attempt('a','r1','2c','warm-up',0)
        finish(ledger,'r1',wall=10)
        (ledger.root/'a').mkdir()
        sparse = ledger.root/'TEST_ONLY_decimal_boundary.bin'
        with sparse.open('wb') as stream: stream.truncate(boundary-100000)
        ledger.snapshot()  # stabilize real retained metadata at ten decimal digits
        return ledger,sparse

    probe,probe_sparse = fixture('p0')
    probe_data = {}
    def place_probe(path,raw):
        original_raw(path,raw)
        if path.name.startswith('upper-finalization-'):
            other = api.logical_tree_bytes(probe.root)-probe_sparse.stat().st_size
            with probe_sparse.open('r+b') as stream: stream.truncate(boundary+1-other)
    def bounded_probe(value):
        raw = original_encode(value)
        if value.get('schema')=='COMPUTE_METABOLISM_CAMPAIGN_FINALIZATION_V0':
            probe_data['receipt_bytes']=len(raw)
        if value.get('campaign_finalizations'):
            other = api.logical_tree_bytes(probe.root)-probe.path.stat().st_size
            probe_data['total']=other+probe_data['receipt_bytes']+len(raw)
            raise ProbeComplete
        return raw
    monkeypatch.setattr(api,'_exclusive_raw',place_probe)
    monkeypatch.setattr(api,'_encode',bounded_probe)
    with pytest.raises(ProbeComplete): api._finalize_upper(probe,{'campaign_id':'a'},'r1',True,'POST_FINISH')
    # Calibrate only preserved sparse fixture bytes from the actual serialized
    # product candidate; do not duplicate its sizing or classification logic.
    adjustment = boundary-1-probe_data['total']
    monkeypatch.setattr(api,'_encode',original_encode)
    trial,sparse = fixture('p1')
    observed,calls = [],[0]
    def place_trial(path,raw):
        original_raw(path,raw)
        if path.name.startswith('upper-finalization-'):
            other = api.logical_tree_bytes(trial.root)-sparse.stat().st_size
            with sparse.open('r+b') as stream: stream.truncate(boundary+1+adjustment-other)
    def bounded_trial(value):
        calls[0]+=1
        if calls[0]>512: raise TestSizingBudgetExpired('TEST_ONLY product sizing exceeded 512 serializations')
        if value.get('schema')=='COMPUTE_METABOLISM_CAMPAIGN_FINALIZATION_V0':
            observed.append(value['observed_retained_total_bytes'])
        return original_encode(value)
    monkeypatch.setattr(api,'_exclusive_raw',place_trial)
    monkeypatch.setattr(api,'_encode',bounded_trial)
    receipt = None
    try: receipt=api._finalize_upper(trial,{'campaign_id':'a'},'r1',True,'POST_FINISH')
    except TestSizingBudgetExpired: pass
    assert receipt is not None, f'bounded product path did not publish STOP; observed cycle tail={observed[-6:]}'
    assert boundary+1 in observed and boundary-1 in observed
    assert receipt['campaign_stop'] is True and receipt['resource_reason']=='CAMPAIGN_EVIDENCE_CEILING'
    state=api.CampaignLedger.read_snapshot(trial.path)
    assert state['total_wall_seconds']==10 and state['attempts'][0]['status']=='FINISHED'
    assert receipt['observed_retained_total_bytes']==api.logical_tree_bytes(trial.root)==state['retained_total_bytes']
    assert receipt['resource_proof']['remaining']==3221225472-receipt['observed_retained_total_bytes']
    assert receipt['resource_proof']['observed']==receipt['observed_retained_total_bytes']
    raw=Path(receipt['finalization_locator']).read_bytes()
    assert hashlib.sha256(raw).hexdigest()==receipt['finalization_sha256']
    assert json.loads(raw)['resource_proof']==receipt['resource_proof']
    assert sparse.exists() and (probe.root/'a'/'upper-finalization-0001.raw.json').exists()


def test_finalization_nonconvergence_stops_finitely_preserves_finished_cost_and_blocks_next(api,tmp_path,monkeypatch,capsys):
    path,digest,config=cli_config(tmp_path,monkeypatch)
    assert api.main(['init','--config',str(path),'--config-sha256',digest])==0
    seen=install_admitted_guard(api,tmp_path,monkeypatch,config)
    original_encode=api._encode
    calls=[0]
    def growing_candidate(value):
        raw=original_encode(value)
        if value.get('campaign_finalizations'):
            calls[0]+=1
            if calls[0]>256: raise OSError('TEST_ONLY bounded serializer terminated unbounded sizing')
            return raw+b' '*calls[0]  # valid JSON administration fault; no raw execution edits
        return raw
    monkeypatch.setattr(api,'_encode',growing_candidate)
    prefix=['run-next','--config',str(path),'--config-sha256',digest,'--run-id']
    assert api.main(prefix+['r1'])==2
    state=api.CampaignLedger.read_snapshot(Path(config['ledger_path']))
    assert state['running'] is None and state['total_wall_seconds']==10
    assert state['attempts'][0]['status']=='FINISHED' and state['attempts'][0]['outcome']=='ACCEPT'
    assert 'FINALIZATION_SIZING_NONCONVERGENCE' in state['campaign_finalization_unresolved']['partial_error']
    assert calls[0]<=128 and not list(Path(config['ledger_path']).parent.rglob('campaign-finalization-*.json'))
    assert list(Path(config['ledger_path']).parent.rglob('upper-finalization-*.raw.json'))
    monkeypatch.setattr(api,'_encode',original_encode)
    assert api.main(prefix+['r2'])==2 and len(seen)==1
