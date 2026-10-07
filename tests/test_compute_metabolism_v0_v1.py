"""TEST_ONLY marker evidence; never executes Gala, GDB, systemd or metadata."""
import copy
from dataclasses import asdict
import importlib
import importlib.util
import json
import os
from pathlib import Path

import pytest


@pytest.mark.parametrize('mutation,expected', [('body','REFUSED_VERIFICATION'),('checker','UNRESOLVED_FAILURE'),('bound-checker','REFUSED_VERIFICATION'),('barrier','REFUSED_VERIFICATION'),('foreign-body','UNRESOLVED_FAILURE'),('clean','UNRESOLVED_FAILURE'),('partial','UNRESOLVED_FAILURE')])
def test_finalfix_raw_stop_checks_existing_anomalies(evidence,mutation,expected):
    root,reference=evidence()
    run=root/'runs/test-run'
    result=get(run/'result.json'); result['verdict']='STOP'; put(run/'result.json',result)
    if mutation=='body':
        body=get(run/'live/body-start-3.json'); body.update(step=4,predecessor_id=result['state_id'])
        put(run/'live/body-start-4.json',body)
    if mutation=='checker':
        put(run/'edge-4.checker.json',dict(schema='LIVE_EDGE_CHECK_V1',verdict='REFUSED',failure_stage='check',reason='TEST_ONLY'))
    if mutation=='bound-checker':
        put(run/'edge-2.checker.json',dict(schema='LIVE_EDGE_CHECK_V1',verdict='REFUSED',failure_stage='check',reason='TEST_ONLY'))
    if mutation=='barrier':
        doc=get(root/'publication-2.json'); doc['next_body_absent']=False; put(root/'publication-2.json',doc)
    if mutation=='foreign-body': put(run/'live/body-start-4.json',{'TEST_ONLY':'no identity'})
    if mutation=='partial':
        first=get(root/'publication-1.json')['state_id']
        (root/'store/CURRENT').write_text(first+'\n')
        result.update(state_id=first,generation=1,step_index=1); put(run/'result.json',result)
    report=api().evaluate_v1_evidence(root,3,reference)
    assert report['outcome']==expected
    assert bool(report.get('verification_conflict'))==(mutation not in ('clean','partial'))
    if mutation not in ('clean','partial'):
        assert report['verification_anomalies'][0]['raw_sha256']
        assert report['verification_anomalies'][0]['manifest_sha256']==digest_bytes((root/'attempt.json').read_bytes())
    from tests.test_compute_metabolism_v0_campaign import classification_fixture
    from compute_metabolism.v0.campaign import classify_attempt
    resource_report,receipt=classification_fixture(root)
    resource_report.update(outcome=report['outcome'],verification_conflict=report.get('verification_conflict',False),
        verification_anomalies=report.get('verification_anomalies',[]))
    classified=classify_attempt(resource_report,receipt,1000)
    assert classified['wrapper_outcome']==('REFUSED_RESOURCE' if mutation in ('clean','partial') else expected)
    assert classified['campaign_stop']==(mutation not in ('clean','partial'))


@pytest.mark.parametrize('raises',[False,True])
def test_finalfix_partial_driver_metrics_preserved(runner_fixture,monkeypatch,raises):
    mod,config,_=runner_data(runner_fixture)
    metrics=[{'initial_acquisition_seconds':.125},{'next_body':2,'acquisition_seconds':.375}]
    original_metrics=[{'TEST_ONLY':'original immutable metrics'}]
    def fail(self,n,run_id):
        self.metrics=copy.deepcopy(metrics)
        put(self.run_root/run_id/'metrics.json',original_metrics)
        put(self.run_root/run_id/'result.json',{'verdict':'STOP','run_id':run_id,'reason':'TEST_ONLY'})
        if raises: raise RuntimeError('TEST_ONLY partial failure')
    monkeypatch.setattr(mod.VerifiedChainDriver,'run',fail)
    mod.run_fresh_v1(config)
    root=config.attempt_root/'v1'
    saved=get(root/'driver-metrics-snapshot.json')
    assert saved['metrics']==metrics and saved['status']=='PARTIAL'
    assert saved['run_id']=='test-run' and saved['requested_steps']==3
    assert saved['manifest_sha256']==digest_bytes((root/'attempt.json').read_bytes())
    assert json.loads((root/'runs/test-run/metrics.json').read_bytes())==original_metrics
    assert get(root/'runs/test-run/result.json')['verdict']=='STOP'

from compute_metabolism.v0.profiles import APPROVED_N3_FINAL_PUBLIC_BITS, APPROVED_V1_SOURCE_BINDING, CampaignLimits
from compute_metabolism.v0.campaign import CampaignLedger
from verified_driver.v1.model import (BASIS, DT, ZERO, ChainState, FormLane,
    canonical_bytes, chain_genesis, content_id, digest_bytes, strict_json)
from verified_driver.v1.live_chain.checkpoint import chain_hash
from verified_driver.v1.live_chain.session import live_source_snapshot

ROOT = Path(__file__).resolve().parents[1]
PREP = Path('C:/Users/zun24/.codex/visualizations/2026/10/06/01a10fe0-8e9a-7033-913a-5fe8f4eb351f/compute-metabolism-v0-environment-preparation/execution-environment.json')
if os.name != 'nt':
    PREP = Path('/mnt/c/Users/zun24/.codex/visualizations/2026/10/06/01a10fe0-8e9a-7033-913a-5fe8f4eb351f/compute-metabolism-v0-environment-preparation/execution-environment.json')


def api():
    assert importlib.util.find_spec('compute_metabolism.v0.run_v1') is not None, 'fresh V1 runner API is missing'
    return importlib.import_module('compute_metabolism.v0.run_v1')


def put(path, doc):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_bytes(doc))


def get(path):
    return strict_json(path.read_bytes())


def topo():
    return {'0': {'physical_package_id': '0', 'core_id': '0'},
            '1': {'physical_package_id': '0', 'core_id': '1'}}


def snapshot(t=1):
    return {'epoch': {'path': '/sys/fs/cgroup/system.slice/compute-metabolism-test.service',
            'device': 1, 'inode': 2, 'boot_id': 'test-boot'}, 'monotonic_seconds': t,
        'cpus': [0, 1], 'cpu_max': {'unlimited': True, 'quota_usec': None, 'period_usec': 100000, 'finite_ancestors': []},
        'raw': {'memory.max': '4294967296', 'memory.swap.max': '0'},
        'memory': {'effective_bytes': 4294967296}, 'swap': {'effective_bytes': 0},
        'cpu_stat': {k: t for k in ('usage_usec', 'user_usec', 'system_usec', 'nr_periods', 'nr_throttled', 'throttled_usec')},
        'memory_events': {'oom': 0, 'oom_kill': 0}, 'memory_peak': 10,
        'pids': [os.getpid()], 'process_identities': {str(os.getpid()): {'pid': os.getpid(), 'start_ticks': '42'}}}


def environment():
    return {'evidence_scope': 'TEST_ONLY', 'runtime': get(PREP)['identity'],
        'source_snapshot': live_source_snapshot(ROOT), 'boot_id': 'test-boot', 'topology': topo(),
        'instance_observation': {'instance_id': '123456', 'raw': '123456', 'observed_utc': '2026-10-06T00:00:00+00:00'},
        'proc': {'loadavg': 'TEST_ONLY', 'cpu_pressure': 'TEST_ONLY', 'stat': 'cpu 1 2 3 4 5 6 7 8', 'steal_ticks': {'cpu': 8}},
        'wrapper_identity': {'pid': os.getpid(), 'start_ticks': '42'},
        'thread_environment': {'OMP_NUM_THREADS': '1', 'OPENBLAS_NUM_THREADS': '1'}}


def running_ledger(campaign_id='test-campaign', run_id='test-run', profile='2c', role='measured', round_index=1):
    identity = dict(campaign_id=campaign_id, run_id=run_id, profile=profile, role=role, round_index=round_index)
    return {'schema': 'compute-metabolism-v0-upper-ledger-v1', 'limits': asdict(CampaignLimits()),
        'attempts': [{**identity, 'status': 'RUNNING', 'partial_receipts': []}], 'running': identity,
        'total_wall_seconds': 0, 'retained_total_bytes': 0, 'start_refusals': []}


def save_upper_proof(root, ledger_path, doc):
    raw = canonical_bytes(doc)
    (root / 'upper-ledger-before.raw.json').write_bytes(raw)
    (root / 'upper-authority-before.bin').write_bytes(b'1')
    proof = {'schema': 'COMPUTE_METABOLISM_UPPER_BEFORE_V0', 'ledger_path': str(ledger_path),
        'artifact_root': str(ledger_path.parent), 'ledger_schema': doc['schema'], 'running': doc['running'],
        'ledger_raw_sha256': digest_bytes(raw), 'authority_path': str(ledger_path.with_name('.'+ledger_path.name+'.authority')),
        'authority_sha256': digest_bytes(b'1')}
    put(root / 'upper-ledger-before.json', proof)
    return proof


@pytest.fixture
def evidence(tmp_path):
    def build(n=3, final_bits=APPROVED_N3_FINAL_PUBLIC_BITS):
        root = tmp_path / 'upper/test-campaign' / ('warmup' if n == 1 else 'round-01') / 'test-run/v1'
        root.mkdir(parents=True)
        env = environment()
        reference = {'schema': 'COMPUTE_METABOLISM_REFERENCE_V0', 'requested_steps': 3,
            'source_binding': APPROVED_V1_SOURCE_BINDING, 'final_public_bits': list(APPROVED_N3_FINAL_PUBLIC_BITS),
            'provenance': [{'locator': 'immutable/historical/TEST_ONLY.json', 'sha256': 'a'*64, 'role': 'HISTORICAL_REFERENCE'}]}
        campaign = {'schema': 'COMPUTE_METABOLISM_ENVIRONMENT_V0', 'instance_id': '123456', 'boot_id': 'test-boot', 'topology': topo()}
        (root / 'execution-environment.json').write_bytes(PREP.read_bytes())
        put(root / 'campaign-environment.json', campaign)
        put(root / 'reference.json', reference)
        guard_before = {'run_id': 'test-run', 'profile': '2c', 'unit': 'compute-metabolism-test.service',
            'before': snapshot(), 'topology_before': topo(), 'wrapper_identity': env['wrapper_identity']}
        put(root.parent / 'guard-cgroup-before.json', guard_before)
        put(root / 'guard-before.json', guard_before)
        ledger_path = tmp_path / 'upper/upper-ledger.json'
        ledger = running_ledger(role='measured' if n == 3 else 'warm-up', round_index=1 if n == 3 else 0)
        put(ledger_path, ledger)
        (ledger_path.with_name('.upper-ledger.json.authority')).write_bytes(b'1')
        upper_proof = save_upper_proof(root, ledger_path, ledger)
        manifest = {'schema': 'COMPUTE_METABOLISM_ATTEMPT_V0', 'evidence_scope': 'TEST_ONLY', 'run_id': 'test-run',
            'requested_steps': n, 'role': 'measured' if n == 3 else 'warm-up', 'profile': '2c', 'attempt_root': str(root.parent),
            'guard_before_sha256': content_id(guard_before),
            'campaign_id': 'test-campaign', 'round_index': 1 if n == 3 else 0, 'ledger_path': str(ledger_path),
            'upper_before_sha256': content_id(upper_proof),
            'upper_running_identity': ledger['running'],
            'inputs': {name: digest_bytes((root / name).read_bytes()) for name in ('execution-environment.json', 'campaign-environment.json', 'reference.json')}}
        put(root / 'attempt.json', manifest)
        put(root / 'environment-before.json', env)
        put(root / 'environment-after.json', env)
        put(root / 'cgroup-before.json', {'snapshot': snapshot(), 'topology': topo(), 'wrapper_identity': env['wrapper_identity']})
        put(root / 'cgroup-after.json', {'snapshot': snapshot(2), 'topology': topo(), 'wrapper_identity': env['wrapper_identity']})
        run = root / 'runs' / 'test-run'
        (run / 'live').mkdir(parents=True)
        store = root / 'store'
        (store / 'objects').mkdir(parents=True)
        (store / 'receipts').mkdir()
        pred = chain_genesis(ROOT, n)
        put(store / 'objects' / (pred.content_hash + '.json'), pred)
        put(root / 'publication-0.json', {'run_id': 'test-run', 'step': 0, 'state_id': pred.content_hash, 'body_markers': [], 'next_body_absent': True})
        process = {'pid': 177, 'linux_boot_id': 'test-boot', 'proc_stat_start_time_ticks': 52}
        for k in range(1, n + 1):
            raw = b'{}\n' * k
            bits = final_bits if n == 3 and k == 3 else pred.public_bits
            snap = {'q': list(bits[:2]), 'full_v': list(bits[2:]), 'latent': list(bits[2:]), 'gradient': [ZERO, ZERO],
                't_bits': None if k == n else ZERO, 'dt_bits': DT, 'body_count': k, 'frontier': k - 1}
            event = {'session_id': 'b'*64, 'barrier_seq': k, 'completed_step': k, 'barrier_kind': 'FINAL_TERMINAL' if k == n else 'NEXT_STEP_ENTRY',
                'requested_steps': n, 'process_identity': process, 'trace_prefix_bytes': len(raw), 'trace_prefix_sha256': digest_bytes(raw),
                'trace_chain_hash': chain_hash(raw), 'predecessor_id': pred.content_hash, 'checkpoint_state': snap}
            metadata = {'evidence_role': 'LIVE', 'source_snapshot': env['source_snapshot'], 'source_binding': APPROVED_V1_SOURCE_BINDING,
                'capture': {'process_identity': process, 'acquisition_id': 'b'*64, 'requested_steps': n,
                    'regions': [{'occurrence': f'step{i}', 'start_seq': i - 1} for i in range(1, k + 1)]}}
            cp = {'schema': 'LIVE_CHECKPOINT_V1', 'event': event, 'metadata': metadata}
            cid = content_id(cp)
            folder = run / f'checkpoint-{k}'
            put(folder / 'checkpoint.json', cp)
            (folder / 'CHECKPOINT').write_bytes((cid + '\n').encode('ascii'))
            (folder / 'trace.jsonl').write_bytes(raw)
            forms = tuple(FormLane(snap[name][offset//8], ('0x0.0p+0',)*4, '0x0.0p+0', f'TEST_ONLY:{k}', name, offset)
                for name in ('q', 'full_v', 'latent') for offset in (0, 8))
            candidate = ChainState(k, k, n, event['barrier_kind'], bits, tuple(snap['q']), tuple(snap['full_v']), tuple(snap['latent']),
                (ZERO, ZERO), snap['t_bits'], DT, forms, BASIS, 'b'*64+'/global-error-basis', APPROVED_V1_SOURCE_BINDING,
                digest_bytes(raw), len(raw), k-1, pred.content_hash, '0'*64, 'b'*64, content_id(process), k).candidate_document()
            edge = {'schema': 'LIVE_EDGE_V1', 'checkpoint_id': cid, 'predecessor_id': pred.content_hash, 'candidate': candidate}
            put(run / f'edge-{k}' / 'edge.json', edge)
            completion = {'schema': 'EDGE_COMPLETION_V1', 'checkpoint_id': cid, 'predecessor_id': pred.content_hash,
                'edge_sha256': content_id(edge), 'checked_edge': k, 'requested_steps': n, 'requested_complete': k == n, 'verified_frontier': k-1}
            completion['completion_sha256'] = content_id(completion)
            put(run / f'edge-{k}' / 'completion.json', completion)
            checker = {'schema': 'LIVE_EDGE_CHECK_V1', 'verdict': 'CHECKER_PASS', 'evidence_role': 'LIVE', 'checkpoint_id': cid,
                'candidate': candidate, 'completion_sha256': completion['completion_sha256'], 'checked_step': k, 'requested_complete': k == n}
            put(run / f'edge-{k}.checker.json', checker)
            receipt = {'schema': 'VERIFIED_CHAIN_ACCEPTANCE_V1', 'verdict': 'ACCEPT', 'candidate': candidate, 'predecessor_id': pred.content_hash,
                'checkpoint_id': cid, 'edge_completion_sha256': completion['completion_sha256'], 'checker_report_sha256': content_id(checker)}
            state = ChainState(**candidate, acceptance_id=content_id(receipt))
            put(store / 'receipts' / (state.acceptance_id + '.json'), receipt)
            put(store / 'objects' / (state.content_hash + '.json'), state)
            body = {'step': k, 'pid': 177, 'session_id': 'b'*64, 'predecessor_id': pred.content_hash, 'trace_start_seq': k-1}
            put(run / 'live' / f'body-start-{k}.json', body)
            put(run / f'barrier-{k}.json', {'event_id': content_id(event), 'checkpoint_id': cid, 'state_id': state.content_hash,
                'predecessor_id': pred.content_hash, 'order': ['PAUSE', 'SEAL', 'CHECK', 'CURRENT', 'BIND']})
            put(root / f'publication-{k}.json', {'run_id': 'test-run', 'step': k, 'state_id': state.content_hash, 'event_id': content_id(event),
                'checkpoint_id': cid, 'process_identity': process, 'observed_process_identity': process, 'session_id': 'b'*64,
                'cgroup_path': snapshot()['epoch']['path'], 'body_markers': list(range(1, k+1)), 'body_sha256': {str(i): digest_bytes((run / 'live' / f'body-start-{i}.json').read_bytes()) for i in range(1, k+1)}, 'next_body_absent': True})
            pred = state
        (store / 'CURRENT').write_bytes((pred.content_hash + '\n').encode('ascii'))
        put(run / 'result.json', {'verdict': 'ACCEPT', 'run_id': 'test-run', 'state_id': pred.content_hash, 'generation': n, 'step_index': n, 'reason': 'TEST_ONLY'})
        put(run / 'metrics.json', [{'TEST_ONLY': True, 'step': i} for i in range(1, n+1)])
        put(run / 'live' / 'session-stop.json', {'phase': 'FINISHED', 'reason': 'TEST_ONLY', 'session_id': 'b'*64})
        return root, reference
    return build


@pytest.mark.parametrize('n', [1, 3])
def test_complete_synthetic_admission_is_explicitly_test_only_and_read_only(evidence, n):
    root, reference = evidence(n)
    before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in root.rglob('*') if p.is_file()}
    report = api().evaluate_v1_evidence(root, n, reference)
    assert report['admitted'] is True, json.dumps(report)
    assert report['evidence_scope'] == 'TEST_ONLY'
    assert report['formal_certification'] is False
    assert before == {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in root.rglob('*') if p.is_file()}


@pytest.mark.parametrize('file', ['attempt.json', 'environment-before.json', 'environment-after.json', 'cgroup-before.json',
    'cgroup-after.json', 'publication-0.json', 'publication-1.json', 'publication-2.json', 'publication-3.json',
    'runs/test-run/result.json', 'runs/test-run/metrics.json', 'runs/test-run/edge-1.checker.json',
    'runs/test-run/edge-2.checker.json', 'runs/test-run/edge-3.checker.json', 'runs/test-run/checkpoint-1/CHECKPOINT',
    'runs/test-run/checkpoint-2/trace.jsonl', 'runs/test-run/checkpoint-3/checkpoint.json', 'runs/test-run/barrier-2.json',
    'runs/test-run/live/body-start-1.json', 'runs/test-run/live/body-start-2.json', 'runs/test-run/live/body-start-3.json',
    'runs/test-run/live/session-stop.json', 'runs/test-run/edge-3/completion.json', 'store/CURRENT'])
def test_each_missing_required_artifact_refuses(evidence, file):
    root, reference = evidence()
    (root / file).unlink()
    assert api().evaluate_v1_evidence(root, 3, reference)['admitted'] is False


@pytest.mark.parametrize('file,key,value', [
    ('runs/test-run/result.json', 'verdict', 'STOP'), ('runs/test-run/result.json', 'generation', 2),
    ('runs/test-run/result.json', 'step_index', 2), ('runs/test-run/result.json', 'run_id', 'foreign'),
    ('runs/test-run/edge-2.checker.json', 'verdict', 'REFUSED'), ('runs/test-run/edge-3.checker.json', 'evidence_role', 'TEST_ONLY'),
    ('runs/test-run/live/body-start-2.json', 'pid', 999), ('runs/test-run/live/body-start-2.json', 'session_id', 'c'*64),
    ('runs/test-run/live/body-start-3.json', 'predecessor_id', 'd'*64), ('runs/test-run/live/body-start-3.json', 'trace_start_seq', 99),
    ('publication-2.json', 'next_body_absent', False), ('publication-1.json', 'state_id', 'e'*64),
    ('publication-2.json', 'event_id', 'e'*64), ('publication-3.json', 'observed_process_identity', {'pid': 177}),
    ('runs/test-run/barrier-1.json', 'order', ['CURRENT', 'CHECK']), ('runs/test-run/live/session-stop.json', 'phase', 'STOPPED')])
def test_changed_admission_item_refuses(evidence, file, key, value):
    root, reference = evidence()
    doc = get(root / file)
    doc[key] = value
    put(root / file, doc)
    assert api().evaluate_v1_evidence(root, 3, reference)['admitted'] is False


@pytest.mark.parametrize('n', [1, 3])
def test_unrequested_body_and_replay_receipt_refuse(evidence, n):
    root, reference = evidence(n)
    put(root / 'runs/test-run/live' / f'body-start-{n+1}.json', {'TEST_ONLY': True})
    assert api().evaluate_v1_evidence(root, n, reference)['admitted'] is False


def test_warmup_does_not_compare_n3_public_bits(evidence):
    root, reference = evidence(1)
    final = get(root / 'store/objects' / (root / 'store/CURRENT').read_text().strip().__add__('.json'))
    assert final['public_bits'] != reference['final_public_bits']
    assert api().evaluate_v1_evidence(root, 1, reference)['admitted']


def test_arbitrary_reference_bits_cannot_redefine_approved_gate(evidence):
    root, reference = evidence()
    reference['final_public_bits'][0] = ZERO
    assert not api().evaluate_v1_evidence(root, 3, reference)['admitted']


@pytest.mark.parametrize('lane', [0, 1, 2, 3])
def test_each_hash_consistent_wrong_final_public_bit_refuses(evidence, lane):
    changed = list(APPROVED_N3_FINAL_PUBLIC_BITS)
    changed[lane] = ZERO
    root, reference = evidence(3, tuple(changed))
    report = api().evaluate_v1_evidence(root, 3, reference)
    assert report['admitted'] is False
    assert report['reason'] == 'N3 final public bits mismatch'


@pytest.mark.parametrize('field', ['runtime', 'source_snapshot', 'boot_id', 'topology', 'instance_observation', 'proc', 'thread_environment'])
def test_environment_missing_or_drift_refuses(evidence, field):
    root, reference = evidence()
    env = get(root / 'environment-after.json')
    del env[field]
    put(root / 'environment-after.json', env)
    assert not api().evaluate_v1_evidence(root, 3, reference)['admitted']


def test_cgroup_after_wrong_enforcement_or_epoch_refuses(evidence):
    root, reference = evidence()
    doc = get(root / 'cgroup-after.json')
    doc['snapshot']['cpus'] = [0]
    put(root / 'cgroup-after.json', doc)
    assert not api().evaluate_v1_evidence(root, 3, reference)['admitted']


def test_source_binding_remains_approved_40_file_snapshot():
    sources = live_source_snapshot(ROOT)
    assert len(sources) == 40
    assert content_id(sources) == APPROVED_V1_SOURCE_BINDING


@pytest.fixture
def runner_fixture(tmp_path, monkeypatch):
    if importlib.util.find_spec('compute_metabolism.v0.run_v1') is None:
        return None
    mod = api()
    ledger = tmp_path / 'upper/upper-ledger.json'
    owner = CampaignLedger.open(ledger, CampaignLimits())
    owner.begin_attempt('test-campaign', 'test-run', '2c', 'measured', 1)
    parent = ledger.parent / 'test-campaign/round-01/test-run'
    parent.mkdir(parents=True)
    (parent / 'writer_quota.txt').write_text('0')
    put(parent / 'guard-cgroup-before.json', {'run_id': 'test-run', 'profile': '2c', 'unit': 'compute-metabolism-test.service',
        'before': snapshot(), 'topology_before': topo(), 'wrapper_identity': environment()['wrapper_identity']})
    monkeypatch.setenv('RTN_QUOTA_FILE', str(parent / 'writer_quota.txt'))
    monkeypatch.setenv('RTN_QUOTA_BYTES', '671088640')
    config_inputs = tmp_path / 'inputs'
    config_inputs.mkdir()
    (config_inputs / 'execution-environment.json').write_bytes(PREP.read_bytes())
    put(config_inputs / 'campaign-environment.json', {'schema': 'COMPUTE_METABOLISM_ENVIRONMENT_V0', 'instance_id': '123456', 'boot_id': 'test-boot', 'topology': topo()})
    put(config_inputs / 'reference.json', {'schema': 'COMPUTE_METABOLISM_REFERENCE_V0', 'requested_steps': 3, 'source_binding': APPROVED_V1_SOURCE_BINDING,
        'final_public_bits': list(APPROVED_N3_FINAL_PUBLIC_BITS), 'provenance': [{'locator': 'TEST_ONLY', 'sha256': 'a'*64, 'role': 'HISTORICAL_REFERENCE'}]})
    config = mod.AttemptConfig(repo_root=ROOT, attempt_root=parent, ledger_path=ledger, run_id='test-run', profile='2c', role='measured', requested_steps=3,
        execution_environment_path=config_inputs / 'execution-environment.json', execution_environment_sha256=digest_bytes(PREP.read_bytes()),
        campaign_environment_path=config_inputs / 'campaign-environment.json', campaign_environment_sha256=digest_bytes((config_inputs / 'campaign-environment.json').read_bytes()),
        reference_path=config_inputs / 'reference.json', reference_sha256=digest_bytes((config_inputs / 'reference.json').read_bytes()),
        **({'campaign_id': 'test-campaign', 'round_index': 1} if 'campaign_id' in mod.AttemptConfig.__dataclass_fields__ else {}))
    monkeypatch.setattr(mod, '_capture_environment', lambda root, prepared: environment())
    monkeypatch.setattr(mod, '_validate_environment', lambda *args, **kwargs: None)
    monkeypatch.setattr(mod, 'reserve_writer', lambda count: None)
    monkeypatch.setattr(mod.guard, '_process_identity', lambda pid: {'pid': pid, 'start_ticks': '42'})
    monkeypatch.setattr(mod.guard, 'current_cgroup_path', lambda: Path(snapshot()['epoch']['path']))
    samples = iter([snapshot(), snapshot(2)])
    monkeypatch.setattr(mod.guard, 'read_cgroup_snapshot', lambda path: next(samples))
    monkeypatch.setattr(mod.guard, 'read_cpu_topology', topo)
    calls = []
    class TEST_ONLYDriver:
        def __init__(self, repo_root, store, run_root, ledger):
            calls.append((store, run_root))
            self.store, self.run_root = store, run_root
        def run(self, n, run_id):
            root = self.run_root.parent
            assert (root / 'environment-before.json').is_file()
            assert (root / 'cgroup-before.json').is_file()
            assert not (self.store.root / 'CURRENT').exists()
            assert not list((self.store.root / 'objects').iterdir())
            put(self.store.root / 'objects/genesis-TEST_ONLY.json', {'TEST_ONLY': True})
            put(self.run_root / run_id / 'result.json', {'verdict': 'STOP', 'run_id': run_id, 'generation': 0, 'step_index': 0, 'state_id': None, 'reason': 'TEST_ONLY'})
            put(self.run_root / run_id / 'metrics.json', [{'TEST_ONLY': True}])
            return get(self.run_root / run_id / 'result.json')
    monkeypatch.setattr(mod, 'VerifiedChainDriver', TEST_ONLYDriver)
    return mod, config, calls


def runner_data(fixture):
    assert fixture is not None, 'fresh V1 runner API is missing'
    return fixture


def test_runner_exclusive_child_fresh_store_and_raw_stop_unchanged(runner_fixture):
    mod, config, calls = runner_data(runner_fixture)
    report = mod.run_fresh_v1(config)
    root = config.attempt_root / 'v1'
    assert report['admitted'] is False
    assert get(root / 'runs/test-run/result.json')['verdict'] == 'STOP'
    assert json.loads((root / 'runs/test-run/metrics.json').read_bytes()) == [{'TEST_ONLY': True}]
    assert (root / 'environment-after.json').is_file()
    assert (root / 'cgroup-after.json').is_file()
    assert calls[0][0].root == root / 'store'
    with pytest.raises(FileExistsError):
        mod.run_fresh_v1(config)
    assert len(calls) == 1


def test_driver_exception_still_writes_final_snapshot(runner_fixture, monkeypatch):
    mod, config, calls = runner_data(runner_fixture)
    def fail(self, n, run_id):
        raise RuntimeError('TEST_ONLY failure')
    monkeypatch.setattr(mod.VerifiedChainDriver, 'run', fail)
    report = mod.run_fresh_v1(config)
    assert not report['admitted']
    assert (config.attempt_root / 'v1/cgroup-after.json').is_file()
    assert (config.attempt_root / 'v1/environment-after.json').is_file()
    assert not (config.attempt_root / 'v1/runs/test-run/result.json').exists()


def test_final_snapshot_failure_never_accepts(runner_fixture, monkeypatch):
    mod, config, calls = runner_data(runner_fixture)
    count = [0]
    def read(path):
        count[0] += 1
        if count[0] == 2:
            raise OSError('TEST_ONLY missing final')
        return snapshot()
    monkeypatch.setattr(mod.guard, 'read_cgroup_snapshot', read)
    report = mod.run_fresh_v1(config)
    assert report['outcome'] == 'ENVIRONMENT_INVALID'
    assert not (config.attempt_root / 'v1/cgroup-after.json').exists()


@pytest.mark.parametrize('n,role', [(2, 'measured'), (1, 'measured'), (3, 'warm-up')])
def test_only_n1_warmup_n3_measured(runner_fixture, n, role):
    mod, config, calls = runner_data(runner_fixture)
    from dataclasses import replace
    with pytest.raises(ValueError):
        mod.run_fresh_v1(replace(config, requested_steps=n, role=role))
    assert not calls


def test_metadata_request_is_fixed_bounded_and_no_fallback(monkeypatch):
    mod = api()
    requests = []
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, size): return b'123456\n'
    def open_url(request, timeout):
        requests.append((request, timeout))
        return Response()
    monkeypatch.setattr(mod, 'urlopen', open_url)
    observed = mod._instance_identity()
    assert observed['instance_id'] == '123456'
    assert requests[0][0].full_url == 'http://169.254.169.254/computeMetadata/v1/instance/id'
    assert requests[0][0].get_header('Metadata-flavor') == 'Google'
    assert 0 < requests[0][1] <= 2
    monkeypatch.setattr(mod, 'urlopen', lambda *args, **kwargs: (_ for _ in ()).throw(TimeoutError('TEST_ONLY')))
    with pytest.raises(TimeoutError): mod._instance_identity()


@pytest.mark.parametrize('kind,index', [('objects', 0), ('objects', 1), ('objects', 2), ('objects', 3), ('receipts', 1), ('receipts', 2), ('receipts', 3)])
def test_missing_linked_state_or_receipt_refuses(evidence, kind, index):
    root, reference = evidence()
    chain = api()._states(root, 3)
    identity = chain[index].content_hash if kind == 'objects' else chain[index].acceptance_id
    (root / 'store' / kind / (identity + '.json')).unlink()
    assert not api().evaluate_v1_evidence(root, 3, reference)['admitted']


def test_two_invocations_never_reuse_prior_current_checkpoint_or_store(runner_fixture, monkeypatch):
    from dataclasses import replace
    mod, config, calls = runner_data(runner_fixture)
    mod.run_fresh_v1(config)
    first = config.attempt_root / 'v1'
    (first / 'store/CURRENT').write_bytes(b'TEST_ONLY prior pointer\n')
    put(first / 'runs/test-run/checkpoint-1/checkpoint.json', {'TEST_ONLY': True})
    put(first / 'runs/test-run/token.json', {'TEST_ONLY': True})
    second = config.attempt_root.parent / 'second-attempt'
    second.mkdir()
    put(config.ledger_path, running_ledger(run_id='second-attempt'))
    (second / 'writer_quota.txt').write_text('0')
    guard_before = get(config.attempt_root / 'guard-cgroup-before.json')
    guard_before['run_id'] = 'second-attempt'
    put(second / 'guard-cgroup-before.json', guard_before)
    monkeypatch.setenv('RTN_QUOTA_FILE', str(second / 'writer_quota.txt'))
    samples = iter([snapshot(), snapshot(2)])
    monkeypatch.setattr(mod.guard, 'read_cgroup_snapshot', lambda path: next(samples))
    mod.run_fresh_v1(replace(config, attempt_root=second, run_id='second-attempt'))
    assert len(calls) == 2
    assert calls[0][0].root != calls[1][0].root
    assert calls[0][1] != calls[1][1]
    assert not (second / 'v1/store/CURRENT').exists()
    assert not (second / 'v1/runs/second-attempt/checkpoint-1').exists()


def test_publication_observer_reads_current_without_recover_under_lock(evidence, monkeypatch):
    from types import SimpleNamespace
    from verified_driver.v1.live_chain.protocol import BarrierEvent
    root, reference = evidence()
    mod = api()
    state = mod._states(root, 3)[1]
    cp = get(root / 'runs/test-run/checkpoint-1/checkpoint.json')
    for k in (2, 3): (root / f'runs/test-run/live/body-start-{k}.json').unlink()
    (root / 'publication-1.json').unlink()
    (root / 'store/CURRENT').write_bytes((state.content_hash + '\n').encode('ascii'))
    store = SimpleNamespace(root=root / 'store', recover=lambda: pytest.fail('recover called inside publication hook'))
    driver = SimpleNamespace(session=SimpleNamespace(event=BarrierEvent(**cp['event'])))
    monkeypatch.setattr(mod, '_observe_inferior', lambda identity, path: dict(identity))
    monkeypatch.setattr(mod, 'reserve_writer', lambda count: None)
    observer = mod._publication_observer(root, store, driver, 'test-run', Path(snapshot()['epoch']['path']))
    observer('before_current_replace')
    assert not (root / 'publication-1.json').exists()
    observer('after_current_replace')
    observed = get(root / 'publication-1.json')
    assert observed['state_id'] == state.content_hash
    assert observed['event_id'] == content_id(cp['event'])
    assert observed['body_markers'] == [1]
    assert observed['next_body_absent'] is True
    assert observed['observed_process_identity'] == cp['event']['process_identity']


def test_prepared_binary_paths_allow_real_symlink_resolution(tmp_path):
    mod = api()
    target = tmp_path / 'TEST_ONLY-binary'
    target.write_bytes(b'TEST_ONLY')
    link = tmp_path / 'TEST_ONLY-lib-alias'
    try: link.symlink_to(target)
    except OSError: pytest.skip('Windows symlink privilege unavailable; covered on Linux')
    assert hasattr(mod, '_runtime_file_hashes'), 'prepared /lib symlink hashing must not use evidence no_alias'
    assert mod._runtime_file_hashes({str(link): digest_bytes(target.read_bytes())}) == {str(link): digest_bytes(target.read_bytes())}


def test_unapproved_runtime_preparation_hash_refuses_before_v1(runner_fixture):
    from dataclasses import replace
    mod, config, calls = runner_data(runner_fixture)
    path = config.execution_environment_path
    doc = get(path)
    doc['identity']['python'] = 'TEST_ONLY arbitrary Python'
    put(path, doc)
    report = mod.run_fresh_v1(replace(config, execution_environment_sha256=digest_bytes(path.read_bytes())))
    assert report['outcome'] == 'ENVIRONMENT_INVALID'
    assert not calls


def test_cli_config_hash_is_checked_before_attempt(monkeypatch, tmp_path):
    mod = api()
    path = tmp_path / 'config.json'
    put(path, {'TEST_ONLY': True})
    monkeypatch.setattr(mod, 'run_fresh_v1', lambda config: pytest.fail('mutable config reached runner'))
    with pytest.raises(ValueError):
        mod.main(['--config', str(path), '--config-sha256', '0'*64])


def test_optional_dmi_permission_failure_is_observed_not_fabricated(monkeypatch):
    mod = api()
    assert hasattr(mod, '_optional_dmi'), 'optional root-owned DMI must preserve unavailable observation'
    original = Path.read_text
    def read(path, *args, **kwargs):
        if str(path) == str(Path('/sys/class/dmi/id/product_uuid')):
            raise PermissionError('TEST_ONLY root-owned DMI')
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'read_text', read)
    result = mod._optional_dmi()
    assert result['status'] == 'UNAVAILABLE'
    assert result['value'] is None
    assert 'PermissionError' in result['reason']


@pytest.mark.parametrize('field,value', [('run_id', 'foreign'), ('profile', '1c'), ('unit', 'compute-metabolism-other.service'),
    ('wrapper_identity', {'pid': 999999, 'start_ticks': '42'})])
def test_guard_before_foreign_identity_refuses_before_numerical(runner_fixture, field, value):
    mod, config, calls = runner_data(runner_fixture)
    path = config.attempt_root / 'guard-cgroup-before.json'
    doc = get(path)
    doc[field] = value
    put(path, doc)
    report = mod.run_fresh_v1(config)
    assert report['outcome'] == 'ENVIRONMENT_INVALID'
    assert not calls


def test_guard_before_receipt_is_required_and_hash_bound(evidence):
    root, reference = evidence()
    (root.parent / 'guard-cgroup-before.json').unlink()
    assert not api().evaluate_v1_evidence(root, 3, reference)['admitted']


def test_missing_guard_receipt_is_environment_invalid_before_numerical(runner_fixture):
    mod, config, calls = runner_data(runner_fixture)
    (config.attempt_root / 'guard-cgroup-before.json').unlink()
    report = mod.run_fresh_v1(config)
    assert report['outcome'] == 'ENVIRONMENT_INVALID'
    assert not calls


def test_generic_raw_stop_stays_unresolved_and_environment_fault_stays_separate(evidence):
    root, reference = evidence()
    raw = get(root / 'runs/test-run/result.json')
    raw['verdict'] = 'STOP'
    raw['reason'] = 'TEST_ONLY timeout/resource/checker arbitrary string'
    put(root / 'runs/test-run/result.json', raw)
    report = api().evaluate_v1_evidence(root, 3, reference)
    assert report['outcome'] == 'UNRESOLVED_FAILURE'
    assert report['raw_v1_result'] == raw
    (root / 'environment-after.json').unlink()
    report = api().evaluate_v1_evidence(root, 3, reference)
    assert report['outcome'] == 'ENVIRONMENT_INVALID'
    assert report['raw_v1_result'] == raw


@pytest.mark.parametrize('profile', ['1c', '0p5c'])
def test_warmup_rejects_other_profiles_before_numerical(runner_fixture, profile):
    from dataclasses import replace
    mod, config, calls = runner_data(runner_fixture)
    with pytest.raises(ValueError, match='warm-up.*2c'):
        mod.run_fresh_v1(replace(config, requested_steps=1, role='warm-up', profile=profile))
    assert not calls


@pytest.mark.parametrize('profile', ['1c', '0p5c'])
def test_warmup_evaluator_rejects_other_profiles(evidence, profile):
    root, reference = evidence(1)
    manifest = get(root / 'attempt.json')
    manifest['profile'] = profile
    put(root / 'attempt.json', manifest)
    report = api().evaluate_v1_evidence(root, 1, reference)
    assert report['outcome'] == 'ENVIRONMENT_INVALID'
    assert 'warm-up' in report['reason'] and '2c' in report['reason']


@pytest.mark.parametrize('attack', ['historical', 'file-only', 'limits', 'run_id', 'profile', 'role', 'campaign_id',
    'round_index', 'absent-running', 'missing-authority', 'foreign-namespace'])
def test_upper_authority_attack_refuses_before_driver(runner_fixture, attack):
    from dataclasses import replace
    mod, config, calls = runner_data(runner_fixture)
    doc = get(config.ledger_path)
    if attack == 'historical': doc['schema'] = 'HISTORICAL_TASK8_LEDGER'
    elif attack == 'file-only': doc = {'TEST_ONLY': True}
    elif attack == 'limits': doc['limits']['memory_bytes'] = 1
    elif attack == 'absent-running': doc['running'] = None; doc['attempts'] = []
    elif attack == 'missing-authority': config.ledger_path.with_name('.'+config.ledger_path.name+'.authority').unlink()
    elif attack == 'foreign-namespace':
        foreign = config.attempt_root.parents[1] / 'other-root/upper-ledger.json'
        put(foreign, doc)
        foreign.with_name('.'+foreign.name+'.authority').write_bytes(b'1')
        config = replace(config, ledger_path=foreign)
    else:
        replacement = 2 if attack == 'round_index' else {'role': 'warm-up', 'profile': '1c'}.get(attack, 'foreign')
        doc['running'][attack] = replacement
        doc['attempts'][0][attack] = replacement
    put(config.ledger_path, doc)
    before = config.ledger_path.read_bytes(), config.ledger_path.stat().st_mtime_ns
    report = mod.run_fresh_v1(config)
    assert report['outcome'] == 'ENVIRONMENT_INVALID', report
    assert not calls
    assert before == (config.ledger_path.read_bytes(), config.ledger_path.stat().st_mtime_ns)


@pytest.mark.parametrize('attack', ['schema', 'limits', 'running-run', 'running-role', 'namespace', 'round'])
def test_repaired_upper_proof_hash_cannot_hide_semantic_tamper(evidence, attack):
    root, reference = evidence()
    proof = get(root / 'upper-ledger-before.json')
    ledger = get(root / 'upper-ledger-before.raw.json')
    manifest = get(root / 'attempt.json')
    if attack == 'schema': ledger['schema'] = 'HISTORICAL'
    elif attack == 'limits': ledger['limits']['writer_bytes'] = 1
    elif attack in ('running-run', 'running-role', 'round'):
        key = {'running-run': 'run_id', 'running-role': 'role', 'round': 'round_index'}[attack]
        value = 2 if attack == 'round' else 'foreign'
        ledger['running'][key] = value
        ledger['attempts'][0][key] = value
    else: proof['ledger_path'] = str(root.parent / 'foreign-ledger.json')
    raw = canonical_bytes(ledger)
    (root / 'upper-ledger-before.raw.json').write_bytes(raw)
    proof.update(ledger_raw_sha256=digest_bytes(raw), ledger_schema=ledger['schema'], running=ledger['running'])
    put(root / 'upper-ledger-before.json', proof)
    manifest['upper_before_sha256'] = content_id(proof)
    put(root / 'attempt.json', manifest)
    report = api().evaluate_v1_evidence(root, 3, reference)
    assert not report['admitted'], report
    assert report['outcome'] == 'ENVIRONMENT_INVALID'


def test_legitimate_finished_upper_does_not_revoke_offline_admission(evidence):
    root, reference = evidence()
    manifest = get(root / 'attempt.json')
    external = Path(manifest['ledger_path'])
    document = get(external)
    original = document['attempts'][0]
    original.update(status='FINISHED', outer_wall_seconds=1, cpu_seconds=1, cpu_measurement_status='AVAILABLE',
        writer_reserved_bytes=0, retained_bytes=0, outcome='ACCEPT')
    document.update(running=None, total_wall_seconds=1)
    put(external, document)
    assert CampaignLedger.read_snapshot(external)['running'] is None
    before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in root.rglob('*') if p.is_file()}
    report = api().evaluate_v1_evidence(root, 3, reference)
    assert report['admitted'], report
    assert report.get('upper_running_identity') == manifest.get('upper_running_identity'), 'saved RUNNING proof must be exposed and bound'
    assert before == {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in root.rglob('*') if p.is_file()}


def test_captured_upper_proof_is_readonly_and_original_upper_unchanged(runner_fixture):
    import stat
    mod, config, calls = runner_data(runner_fixture)
    before = config.ledger_path.read_bytes(), config.ledger_path.stat().st_mtime_ns
    mod.run_fresh_v1(config)
    assert before == (config.ledger_path.read_bytes(), config.ledger_path.stat().st_mtime_ns)
    for name in ('upper-ledger-before.raw.json', 'upper-authority-before.bin', 'upper-ledger-before.json'):
        assert not stat.S_IMODE((config.attempt_root / 'v1' / name).stat().st_mode) & 0o222
