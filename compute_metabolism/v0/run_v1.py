"""Fresh production V1 runner and read-only, hash-bound wrapper admission.

Only N=1 warm-up and N=3 measured attempts are supported. Numerical proof
remains the original LIVE checker result; this wrapper never reruns it.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import importlib.metadata
import os
from pathlib import Path
import platform
import re
import stat
import sys
from urllib.request import Request, urlopen

from . import system_guard as guard
from .campaign import CampaignLedger
from .profiles import (APPROVED_N3_FINAL_PUBLIC_BITS, APPROVED_V1_SOURCE_BINDING,
                       CampaignLimits, get_profile)
from runtime_trace.regular_nstep.resources import reserve_writer
from verified_driver.v1.controller import VerifiedChainDriver
from verified_driver.v1.model import (ChainState, canonical_bytes,
                                    content_id, digest_bytes, strict_json, check_hash)
from verified_driver.v1.store import ChainStore
from verified_driver.v1.live_chain.checkpoint import no_alias, verify_checkpoint
from verified_driver.v1.live_chain.session import live_source_snapshot


APPROVED_PREPARATION_SHA256 = '4901a28b9e4e829b154970ca48077209275b3312aee0be17e53e64670515e7ec'
RUNTIME_FIELDS = ('python', 'executable', 'packages', 'files', 'source_count', 'source_binding', 'source_matches', 'platform')
INPUT_NAMES = ('execution-environment.json', 'campaign-environment.json', 'reference.json')


@dataclass(frozen=True)
class AttemptConfig:
    repo_root: Path
    attempt_root: Path
    ledger_path: Path
    run_id: str
    profile: str
    role: str
    requested_steps: int
    execution_environment_path: Path
    execution_environment_sha256: str
    campaign_environment_path: Path
    campaign_environment_sha256: str
    reference_path: Path
    reference_sha256: str
    campaign_id: str
    round_index: int


class AdmissionFailure(ValueError):
    def __init__(self, reason, outcome='REFUSED_VERIFICATION'):
        super().__init__(reason)
        self.outcome = outcome


def _require(condition, reason, outcome='REFUSED_VERIFICATION'):
    if not condition:
        raise AdmissionFailure(reason, outcome)


def _read(path: Path) -> bytes:
    path = no_alias(path)
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > 32 * 1024 * 1024:
        raise ValueError('bounded unaliased regular evidence required: ' + str(path))
    if any(getattr(p, 'is_junction', lambda: False)() for p in (path, *path.parents)):
        raise ValueError('junction evidence alias')
    return path.read_bytes()


def _json(path: Path):
    return strict_json(_read(path))


def _write(path: Path, value) -> None:
    _write_bytes(path, canonical_bytes(value))


def _write_bytes(path, raw):
    reserve_writer(len(raw))
    with path.open('xb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def _scope(n, role, profile):
    _require(type(n) is int and (n, role) in ((1, 'warm-up'), (3, 'measured')),
             'only N1 warm-up and N3 measured attempts', 'ENVIRONMENT_INVALID')
    _require(role != 'warm-up' or profile == '2c', 'warm-up requires profile 2c', 'ENVIRONMENT_INVALID')


def _upper_identity(manifest):
    _require(isinstance(manifest['campaign_id'], str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', manifest['campaign_id']) is not None,
             'simple campaign identity required', 'ENVIRONMENT_INVALID')
    round_index = manifest['round_index']
    _require(type(round_index) is int and ((manifest['role'] == 'warm-up' and round_index == 0)
        or (manifest['role'] == 'measured' and 1 <= round_index <= 7)), 'campaign round scope invalid', 'ENVIRONMENT_INVALID')
    return {key: manifest[key] for key in ('campaign_id', 'run_id', 'profile', 'role', 'round_index')}


def _upper_namespace(ledger_path, parent, manifest):
    _upper_identity(manifest)
    path = Path(ledger_path)
    _require(path.is_absolute() and '..' not in path.parts, 'absolute lexical upper path required', 'ENVIRONMENT_INVALID')
    branch = 'warmup' if manifest['role'] == 'warm-up' else f"round-{manifest['round_index']:02d}"
    _require(path.parent / manifest['campaign_id'] / branch / manifest['run_id'] == parent,
             'upper campaign/round/run namespace mismatch', 'ENVIRONMENT_INVALID')


def _validate_upper_state(state, manifest):
    identity = _upper_identity(manifest)
    _require(state['schema'] == 'compute-metabolism-v0-upper-ledger-v1'
        and canonical_bytes(state['limits']) == canonical_bytes(asdict(CampaignLimits()))
        and state['running'] == identity, 'Compute upper schema/limits/RUNNING identity mismatch', 'ENVIRONMENT_INVALID')
    records = [record for record in state['attempts'] if record['run_id'] == identity['run_id']]
    _require(len(records) == 1 and records[0]['status'] == 'RUNNING'
        and all(records[0][key] == value for key, value in identity.items())
        and not records[0].get('containment_unresolved') and not records[0].get('partial_receipts'),
        'unresolved or missing matching RUNNING record', 'ENVIRONMENT_INVALID')


def _capture_upper_before(root, ledger_path, manifest):
    path = no_alias(ledger_path)
    _upper_namespace(path, root.parent, manifest)
    raw = _read(path)
    state = CampaignLedger.read_snapshot(path)
    _require(raw == _read(path), 'upper changed during prelaunch observation', 'ENVIRONMENT_INVALID')
    observed = state.pop('observed_retained_total_bytes')
    _require(state == strict_json(raw), 'upper raw/snapshot observation mismatch', 'ENVIRONMENT_INVALID')
    _validate_upper_state(state, manifest)
    authority_path = path.with_name('.' + path.name + '.authority')
    authority = _read(authority_path)
    _require(authority == b'1', 'upper persistent authority marker unavailable', 'ENVIRONMENT_INVALID')
    _write_bytes(root / 'upper-ledger-before.raw.json', raw)
    _write_bytes(root / 'upper-authority-before.bin', authority)
    proof = {'schema': 'COMPUTE_METABOLISM_UPPER_BEFORE_V0', 'ledger_path': str(path),
        'artifact_root': str(path.parent), 'ledger_schema': state['schema'], 'running': state['running'],
        'ledger_raw_sha256': digest_bytes(raw), 'authority_path': str(authority_path),
        'authority_sha256': digest_bytes(authority), 'observed_retained_total_bytes': observed}
    _write(root / 'upper-ledger-before.json', proof)
    for name in ('upper-ledger-before.raw.json', 'upper-authority-before.bin', 'upper-ledger-before.json'):
        (root / name).chmod(0o444)
    return proof


def _saved_upper_before(root, manifest):
    try:
        raw_proof = _read(root / 'upper-ledger-before.json')
        _require(digest_bytes(raw_proof) == manifest['upper_before_sha256'], 'saved upper proof hash mismatch', 'ENVIRONMENT_INVALID')
        proof = strict_json(raw_proof)
        path = Path(proof['ledger_path'])
        _upper_namespace(path, root.parent, manifest)
        _require(proof['schema'] == 'COMPUTE_METABOLISM_UPPER_BEFORE_V0'
            and str(path) == manifest['ledger_path'] and proof['artifact_root'] == str(path.parent)
            and proof['authority_path'] == str(path.with_name('.' + path.name + '.authority')),
            'saved upper origin/schema binding mismatch', 'ENVIRONMENT_INVALID')
        raw = _read(root / 'upper-ledger-before.raw.json')
        authority = _read(root / 'upper-authority-before.bin')
        _require(digest_bytes(raw) == proof['ledger_raw_sha256'] and authority == b'1'
            and digest_bytes(authority) == proof['authority_sha256'], 'saved upper raw/authority hash mismatch', 'ENVIRONMENT_INVALID')
        # Validate the preserved file, not a mutable external ledger after finish.
        state = CampaignLedger.read_snapshot(root / 'upper-ledger-before.raw.json')
        state.pop('observed_retained_total_bytes')
        _require(state == strict_json(raw), 'saved upper raw/snapshot mismatch', 'ENVIRONMENT_INVALID')
        _validate_upper_state(state, manifest)
        _require(proof['ledger_schema'] == state['schema'] and proof['running'] == state['running'] == manifest['upper_running_identity'],
                 'saved upper RUNNING identity binding mismatch', 'ENVIRONMENT_INVALID')
        return proof
    except AdmissionFailure:
        raise
    except Exception as exc:
        raise AdmissionFailure('upper before evidence: ' + str(exc), 'ENVIRONMENT_INVALID') from exc


def _reference(reference):
    _require(reference['schema'] == 'COMPUTE_METABOLISM_REFERENCE_V0'
        and reference['requested_steps'] == 3
        and reference['source_binding'] == APPROVED_V1_SOURCE_BINDING
        and tuple(reference['final_public_bits']) == APPROVED_N3_FINAL_PUBLIC_BITS,
        'reference cannot redefine approved V1 binding/bits')
    _require(isinstance(reference['provenance'], list) and bool(reference['provenance']), 'reference provenance missing')
    for item in reference['provenance']:
        check_hash(item['sha256'])
        _require(isinstance(item['locator'], str) and bool(item['locator']) and item['role'] == 'HISTORICAL_REFERENCE',
                 'reference locator/hash/role required')


def _prepared(document, raw_hash):
    _require(raw_hash == APPROVED_PREPARATION_SHA256, 'unapproved prepared runtime identity', 'ENVIRONMENT_INVALID')
    identity = document['identity']
    _require(identity['source_binding'] == APPROVED_V1_SOURCE_BINDING and identity['source_count'] == 40,
             'prepared source identity invalid', 'ENVIRONMENT_INVALID')
    return identity


def _instance_identity():
    request = Request('http://169.254.169.254/computeMetadata/v1/instance/id', headers={'Metadata-Flavor': 'Google'})
    with urlopen(request, timeout=2) as response:
        raw = response.read(1025)
    if len(raw) > 1024:
        raise ValueError('metadata instance identity exceeds bound')
    decoded = raw.decode('ascii')
    if not re.fullmatch(r'[0-9]+\s*', decoded):
        raise ValueError('numeric GCP instance identity unavailable')
    return {'instance_id': decoded.strip(), 'raw': decoded,
            'observed_utc': datetime.now(timezone.utc).isoformat()}


def _steal_ticks(raw):
    result = {}
    for row in raw.splitlines():
        fields = row.split()
        if fields and re.fullmatch(r'cpu[0-9]*', fields[0]):
            if len(fields) < 9 or not all(v.isdigit() for v in fields[1:]):
                raise ValueError('CPU steal counters unavailable')
            result[fields[0]] = int(fields[8])
    if 'cpu' not in result:
        raise ValueError('aggregate CPU counters unavailable')
    return result


def _runtime_file_hashes(expected):
    # Approved system binaries can live under /lib -> /usr/lib or venv links.
    # Their resolved bytes are compared with the frozen prepared identity;
    # this does not relax the separate no-alias rule for run evidence.
    result = {}
    for name in expected:
        resolved = Path(name).resolve(strict=True)
        if not resolved.is_file():
            raise ValueError('prepared runtime binary unavailable: ' + name)
        result[name] = digest_bytes(resolved.read_bytes())
    return result


def _optional_dmi():
    try:
        return {'status': 'OBSERVED', 'value': Path('/sys/class/dmi/id/product_uuid').read_text().strip()}
    except OSError as exc:
        return {'status': 'UNAVAILABLE', 'value': None, 'reason': f'{type(exc).__name__}: {exc}'}


def _capture_environment(repo_root, prepared):
    sources = live_source_snapshot(repo_root)
    raw_stat = Path('/proc/stat').read_text()
    runtime = {'python': sys.version, 'executable': sys.executable,
        'packages': {name: importlib.metadata.version(name) for name in prepared['packages']},
        'files': _runtime_file_hashes(prepared['files']),
        'source_count': len(sources), 'source_binding': content_id(sources),
        'source_matches': content_id(sources) == APPROVED_V1_SOURCE_BINDING,
        'platform': platform.platform()}
    # Read the complete installed package set, so added distributions drift too.
    installed = {dist.metadata['Name']: dist.version for dist in importlib.metadata.distributions()}
    if {k.lower().replace('_', '-'): v for k, v in installed.items()} != {
            k.lower().replace('_', '-'): v for k, v in prepared['packages'].items()}:
        raise ValueError('installed package set differs from prepared runtime')
    result = {'evidence_scope': 'LIVE', 'runtime': runtime, 'source_snapshot': sources,
        'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
        'topology': guard.read_cpu_topology(), 'instance_observation': _instance_identity(),
        'proc': {'loadavg': Path('/proc/loadavg').read_text(),
                 'cpu_pressure': Path('/proc/pressure/cpu').read_text(), 'stat': raw_stat,
                 'steal_ticks': _steal_ticks(raw_stat)},
        'wrapper_identity': guard._process_identity(os.getpid()),
        'thread_environment': {name: os.environ.get(name) for name in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS')}}
    result['dmi_observation'] = _optional_dmi()
    if result['dmi_observation']['status'] == 'OBSERVED':
        result['dmi_identity'] = result['dmi_observation']['value']
    return result


def _validate_environment(env, prepared, campaign, scope='LIVE'):
    invalid = 'ENVIRONMENT_INVALID'
    _require(env['evidence_scope'] == scope, 'environment observation role mismatch', invalid)
    _require(all(env['runtime'][key] == prepared[key] for key in RUNTIME_FIELDS), 'runtime identity drift', invalid)
    sources = env['source_snapshot']
    _require(len(sources) == 40 and content_id(sources) == APPROVED_V1_SOURCE_BINDING, 'V1 source drift', invalid)
    _require(campaign['schema'] == 'COMPUTE_METABOLISM_ENVIRONMENT_V0'
        and re.fullmatch(r'[0-9]+', campaign['instance_id']) is not None
        and bool(campaign['boot_id']) and bool(campaign['topology']), 'campaign identity invalid', invalid)
    observed = env['instance_observation']
    _require(observed['instance_id'] == observed['raw'].strip() == campaign['instance_id']
        and bool(observed['observed_utc']), 'instance identity mismatch', invalid)
    _require(env['boot_id'] == campaign['boot_id'] and env['topology'] == campaign['topology'], 'VM boot/topology drift', invalid)
    if 'dmi_identity' in campaign:
        _require(env.get('dmi_identity') == campaign['dmi_identity'], 'DMI identity mismatch', invalid)
    _require(all(isinstance(env['proc'][key], str) and bool(env['proc'][key])
        for key in ('loadavg', 'cpu_pressure', 'stat')) and env['proc']['steal_ticks'] == _steal_ticks(env['proc']['stat']),
        'live process load/pressure/steal observation missing', invalid)
    _require(env['thread_environment'] == {'OMP_NUM_THREADS': '1', 'OPENBLAS_NUM_THREADS': '1'}, 'thread policy drift', invalid)
    _require(type(env['wrapper_identity']['pid']) is int and bool(env['wrapper_identity']['start_ticks']), 'wrapper identity unavailable', invalid)


def _observe_inferior(identity, cgroup_path):
    pid = identity['pid']
    observed = guard._process_identity(pid)
    relative = str(cgroup_path.relative_to(guard.CGROUP_ROOT))
    membership = Path(f'/proc/{pid}/cgroup').read_text().splitlines()
    _require('0::/' + relative in membership, 'inferior is outside owned unit')
    second = guard._process_identity(pid)
    _require(observed['start_ticks'] == second['start_ticks'], 'inferior PID reused during observation')
    return {'pid': pid, 'linux_boot_id': guard._boot_id(), 'proc_stat_start_time_ticks': int(second['start_ticks'])}


def _publication_observer(root, store, driver, run_id, cgroup_path):
    def observe(point):
        if point != 'after_current_replace':
            return
        identity = _read(store.root / 'CURRENT').decode('ascii').strip()
        check_hash(identity)
        state = ChainState(**_json(store.root / 'objects' / (identity + '.json')))
        _require(state.content_hash == identity, 'observed CURRENT object mismatch')
        live = root / 'runs' / run_id / 'live'
        markers = sorted(int(p.stem.removeprefix('body-start-')) for p in live.glob('body-start-*.json'))
        doc = {'run_id': run_id, 'step': state.step_index, 'state_id': identity,
            'body_markers': markers, 'next_body_absent': not (live / f'body-start-{state.step_index+1}.json').exists()}
        if state.generation:
            event = driver.session.event
            cp = root / 'runs' / run_id / f'checkpoint-{state.step_index}'
            doc.update(event_id=content_id(event), checkpoint_id=_read(cp / 'CHECKPOINT').decode('ascii').strip(),
                process_identity=dict(event.process_identity), session_id=event.session_id,
                observed_process_identity=_observe_inferior(event.process_identity, cgroup_path),
                cgroup_path=str(cgroup_path), body_sha256={str(k): digest_bytes(_read(live / f'body-start-{k}.json')) for k in markers})
        _write(root / f'publication-{state.step_index}.json', doc)
    return observe


def _validate_guard_before(document, manifest, snapshot, topology, parent):
    invalid = 'ENVIRONMENT_INVALID'
    path = Path(snapshot['epoch']['path'])
    _require(parent.name == manifest['run_id'] == document['run_id']
        and document['profile'] == manifest['profile'] and document['unit'] == path.name
        and path.parent.name == 'system.slice' and re.fullmatch(guard.UNIT_PATTERN, path.name) is not None,
        'guard parent/run/profile/unit binding mismatch', invalid)
    _require(document['before']['epoch'] == snapshot['epoch'] and document['topology_before'] == topology,
             'guard cgroup epoch/topology mismatch', invalid)
    pid = str(document['wrapper_identity']['pid'])
    _require(int(pid) in snapshot['pids'] and pid in snapshot['process_identities']
        and snapshot['process_identities'][pid]['start_ticks'] == document['wrapper_identity']['start_ticks'],
        'guard wrapper live PID/start ticks mismatch', invalid)
    guard.validate_enforcement(get_profile(manifest['profile']), document['before'], document['topology_before'])
    guard.validate_snapshot_pair(document['before'], snapshot)


def _environment_evidence(root, manifest):
    try:
        inputs = {}
        for name in INPUT_NAMES:
            raw = _read(root / name)
            _require(digest_bytes(raw) == manifest['inputs'][name], 'immutable input drift', 'ENVIRONMENT_INVALID')
            inputs[name] = strict_json(raw)
        prepared = _prepared(inputs['execution-environment.json'], manifest['inputs']['execution-environment.json'])
        before, after = (_json(root / f'environment-{which}.json') for which in ('before', 'after'))
        for env in (before, after):
            _validate_environment(env, prepared, inputs['campaign-environment.json'], manifest['evidence_scope'])
        _require(before['wrapper_identity'] == after['wrapper_identity'], 'wrapper process changed', 'ENVIRONMENT_INVALID')
        pair = [_json(root / f'cgroup-{which}.json') for which in ('before', 'after')]
        guard_raw = _read(root / 'guard-before.json')
        _require(digest_bytes(guard_raw) == manifest['guard_before_sha256']
            and guard_raw == _read(root.parent / 'guard-cgroup-before.json')
            and no_alias(manifest['attempt_root']) == root.parent, 'guard receipt hash/parent binding mismatch', 'ENVIRONMENT_INVALID')
        _validate_guard_before(strict_json(guard_raw), manifest, pair[0]['snapshot'], pair[0]['topology'], root.parent)
        profile = get_profile(manifest['profile'])
        for item in pair:
            guard.validate_enforcement(profile, item['snapshot'], item['topology'])
            path = Path(item['snapshot']['epoch']['path'])
            _require(path.name.startswith('compute-metabolism-') and path.name.endswith('.service')
                and path.parent.name == 'system.slice', 'system unit identity unavailable', 'ENVIRONMENT_INVALID')
            _require(item['topology'] == before['topology'] and item['snapshot']['epoch']['boot_id'] == before['boot_id']
                and item['wrapper_identity'] == before['wrapper_identity'], 'cgroup/environment identity mismatch', 'ENVIRONMENT_INVALID')
            pid = str(before['wrapper_identity']['pid'])
            _require(int(pid) in item['snapshot']['pids'] and item['snapshot']['process_identities'][pid]['start_ticks'] == before['wrapper_identity']['start_ticks'],
                'wrapper cgroup membership mismatch', 'ENVIRONMENT_INVALID')
        delta = guard.validate_snapshot_pair(pair[0]['snapshot'], pair[1]['snapshot'])
        return before, pair, delta, inputs['reference.json']
    except AdmissionFailure:
        raise
    except Exception as exc:
        raise AdmissionFailure('environment evidence: ' + str(exc), 'ENVIRONMENT_INVALID') from exc


def _states(root, n, *, complete=True):
    pointer = _read(root / 'store/CURRENT')
    _require(len(pointer) == 65 and pointer[-1:] == b'\n', 'CURRENT malformed')
    identity = pointer[:-1].decode('ascii')
    check_hash(identity)
    chain = []
    for _ in range(n + 1):
        raw = _read(root / 'store/objects' / (identity + '.json'))
        state = ChainState(**strict_json(raw))
        _require(state.content_hash == identity and canonical_bytes(state) == raw, 'state hash/canonical bytes mismatch')
        chain.append(state)
        if state.generation == 0:
            break
        identity = state.predecessor_id
    chain.reverse()
    _require((not complete or len(chain) == n+1) and [s.generation for s in chain] == list(range(len(chain)))
        and all(s.requested_steps == n for s in chain), 'fresh S0 through requested terminal chain required')
    if complete:
        _require(chain[-1].barrier_kind == 'FINAL_TERMINAL', 'final terminal required')
    _require(chain[0].predecessor_id is None, 'fresh genesis predecessor required')
    return chain


def _edge_evidence(root, run, pred, state, n, env, cgroup_path):
    k = state.step_index
    receipt_raw = _read(root / 'store/receipts' / (state.acceptance_id + '.json'))
    receipt = strict_json(receipt_raw)
    _require(canonical_bytes(receipt) == receipt_raw and digest_bytes(receipt_raw) == state.acceptance_id,
             'receipt hash/canonical bytes mismatch')
    _require(receipt['schema'] == 'VERIFIED_CHAIN_ACCEPTANCE_V1' and receipt['verdict'] == 'ACCEPT'
        and receipt['candidate'] == strict_json(canonical_bytes(state.candidate_document()))
        and receipt['predecessor_id'] == pred.content_hash and 'replay_transition_id' not in receipt,
        'receipt candidate/predecessor mismatch or replay')
    _require(state.predecessor_id == pred.content_hash and state.source_binding == APPROVED_V1_SOURCE_BINDING,
        'state predecessor/source mismatch')
    cp = verify_checkpoint(run / f'checkpoint-{k}', receipt['checkpoint_id'])
    event, meta = cp['event'], cp['metadata']
    process = event['process_identity']
    _require(meta['evidence_role'] == 'LIVE' and meta['source_snapshot'] == env['source_snapshot']
        and meta['source_binding'] == APPROVED_V1_SOURCE_BINDING, 'LIVE checkpoint source binding required')
    _require(process['linux_boot_id'] == env['boot_id'] and type(process['pid']) is int
        and type(process['proc_stat_start_time_ticks']) is int and process['proc_stat_start_time_ticks'] > 0,
        'live inferior identity unavailable')
    _require(content_id(process) == state.process_identity_digest and event['session_id'] == state.live_session_id
        and event['predecessor_id'] == pred.content_hash and event['completed_step'] == k and event['requested_steps'] == n
        and event['barrier_seq'] == k and event['barrier_kind'] == state.barrier_kind
        and event['trace_prefix_sha256'] == state.trace_prefix_sha256 and event['trace_prefix_bytes'] == state.trace_prefix_bytes,
        'event state/process/session/prefix binding mismatch')
    snap = event['checkpoint_state']
    _require(all(tuple(snap[name]) == getattr(state, name + '_bits') for name in ('q', 'full_v', 'latent', 'gradient'))
        and snap['frontier'] == state.verified_frontier and snap['t_bits'] == state.next_t_bits
        and snap['dt_bits'] == state.dt_bits and snap['body_count'] == k, 'checkpoint state mismatch')
    if pred.generation:
        _require(state.live_session_id == pred.live_session_id and state.process_identity_digest == pred.process_identity_digest
            and state.trace_prefix_bytes > pred.trace_prefix_bytes and state.verified_frontier > pred.verified_frontier,
            'persistent session/process or forward frontier mismatch')
    checker = _json(run / f'edge-{k}.checker.json')
    _require(content_id(checker) == receipt['checker_report_sha256'] and checker['schema'] == 'LIVE_EDGE_CHECK_V1'
        and checker['verdict'] == 'CHECKER_PASS' and checker['evidence_role'] == 'LIVE'
        and checker['checkpoint_id'] == receipt['checkpoint_id'] and checker['candidate'] == receipt['candidate']
        and checker['checked_step'] == k and checker['requested_complete'] is (k == n), 'hash-bound LIVE checker required')
    edge_raw = _read(run / f'edge-{k}/edge.json')
    edge = strict_json(edge_raw)
    completion = _json(run / f'edge-{k}/completion.json')
    _require(edge['schema'] == 'LIVE_EDGE_V1' and edge['candidate'] == receipt['candidate']
        and edge['checkpoint_id'] == receipt['checkpoint_id'] and edge['predecessor_id'] == pred.content_hash, 'edge binding mismatch')
    completion_hash = content_id({key: value for key, value in completion.items() if key != 'completion_sha256'})
    _require(completion['schema'] == 'EDGE_COMPLETION_V1'
        and completion_hash == completion['completion_sha256'] == checker['completion_sha256'] == receipt['edge_completion_sha256']
        and completion['edge_sha256'] == digest_bytes(edge_raw) and completion['checkpoint_id'] == receipt['checkpoint_id']
        and completion['predecessor_id'] == pred.content_hash and completion['checked_edge'] == k
        and completion['requested_steps'] == n and completion['requested_complete'] is (k == n)
        and completion['verified_frontier'] == state.verified_frontier, 'edge/completion hash binding mismatch')
    body = _json(run / 'live' / f'body-start-{k}.json')
    regions = [r for r in meta['capture']['regions'] if r['occurrence'] == f'step{k}']
    _require(len(regions) == 1 and body['step'] == k and body['pid'] == process['pid']
        and body['session_id'] == state.live_session_id and body['predecessor_id'] == pred.content_hash
        and body['trace_start_seq'] == regions[0]['start_seq'] and meta['capture']['process_identity'] == process
        and meta['capture']['acquisition_id'] == state.live_session_id and meta['capture']['requested_steps'] == n,
        'body checkpoint/process/predecessor lineage mismatch')
    barrier = _json(run / f'barrier-{k}.json')
    publication = _json(root / f'publication-{k}.json')
    _require(barrier['order'] == ['PAUSE', 'SEAL', 'CHECK', 'CURRENT', 'BIND']
        and barrier['event_id'] == publication['event_id'] == content_id(event)
        and barrier['checkpoint_id'] == publication['checkpoint_id'] == receipt['checkpoint_id']
        and barrier['state_id'] == publication['state_id'] == state.content_hash and barrier['predecessor_id'] == pred.content_hash,
        'publication barrier/checkpoint/state mismatch')
    _require(publication['run_id'] == run.name and publication['step'] == k
        and publication['session_id'] == state.live_session_id and publication['process_identity'] == process
        and publication['observed_process_identity'] == process and publication['cgroup_path'] == cgroup_path
        and publication['body_markers'] == list(range(1, k+1)) and publication['next_body_absent'] is True
        and publication['body_sha256'] == {str(i): digest_bytes(_read(run / 'live' / f'body-start-{i}.json')) for i in range(1, k+1)},
        'actual publication-before-next-body observation missing')
    return {'step': k, 'state_id': state.content_hash, 'receipt_sha256': state.acceptance_id,
        'checkpoint_id': receipt['checkpoint_id'], 'checker_report_sha256': receipt['checker_report_sha256'],
        'completion_sha256': completion_hash, 'event_id': content_id(event), 'process_identity': process,
        'body_sha256': digest_bytes(_read(run / 'live' / f'body-start-{k}.json')),
        'publication_sha256': digest_bytes(_read(root / f'publication-{k}.json'))}


def _failure_anomalies(root, run, manifest, env, cgroup_path):
    """Inspect existing bound observations only; a partial chain is not a fault.

    Refusal reports without binding fields remain unresolved conflicts. A
    committed receipt/checkpoint or a matching live marker can prove a fault;
    neither STOP prose nor a missing next generation proves one.
    """
    anomalies = []
    n = manifest['requested_steps']
    manifest_hash = digest_bytes(_read(root/'attempt.json'))
    def record(path, reason, bound=False, checkpoint=None):
        anomalies.append(dict(locator=str(path),raw_sha256=digest_bytes(_read(path)),
            reason=reason,bound=bound,checkpoint_id=checkpoint,run_id=manifest['run_id'],
            manifest_sha256=manifest_hash,source_binding=env['runtime']['source_binding']))
    states = []
    if (root/'store/CURRENT').exists():
        try:
            states = _states(root,n,complete=False)
        except (ValueError,KeyError,TypeError,OSError) as exc:
            record(root/'store/CURRENT','conflicting current/lineage: '+str(exc))
    checkpoints = {}
    for pred,state in zip(states,states[1:]):
        k = state.step_index
        cp_path = run/f'checkpoint-{k}'
        if not all((cp_path/name).is_file() for name in ('CHECKPOINT','checkpoint.json','trace.jsonl')):
            continue
        try:
            cp = verify_checkpoint(cp_path)
            event,meta = cp['event'],cp['metadata']
            cid = _read(cp_path/'CHECKPOINT').decode('ascii').strip()
            _require(meta['source_binding']==APPROVED_V1_SOURCE_BINDING and meta['source_snapshot']==env['source_snapshot']
                and meta['evidence_role']=='LIVE' and event['predecessor_id']==pred.content_hash
                and event['completed_step']==k and event['requested_steps']==n
                and event['session_id']==state.live_session_id
                and content_id(event['process_identity'])==state.process_identity_digest
                and event['process_identity']['linux_boot_id']==env['boot_id'], 'checkpoint attempt binding mismatch')
            checkpoints[k] = (cid,event,state)
        except (ValueError,KeyError,TypeError,OSError) as exc:
            record(cp_path/'checkpoint.json','conflicting checkpoint: '+str(exc))
            continue
        required = [root/'store/receipts'/(state.acceptance_id+'.json'),run/f'edge-{k}.checker.json',
            run/f'edge-{k}/edge.json',run/f'edge-{k}/completion.json',run/f'barrier-{k}.json',
            root/f'publication-{k}.json',*[run/f'live/body-start-{i}.json' for i in range(1,k+1)]]
        if all(path.is_file() for path in required):
            try:
                _edge_evidence(root,run,pred,state,n,env,cgroup_path)
            except (ValueError,KeyError,TypeError,OSError) as exc:
                record(required[0],'published edge integrity: '+str(exc),True,cid)
    for path in sorted((run/'live').glob('body-start-*.json')):
        try:
            k = int(path.stem.removeprefix('body-start-'))
        except ValueError:
            record(path,'unbound body marker name')
            continue
        if 1 <= k <= n:
            continue
        bound, cid = False, None
        try:
            body = _json(path)
            cid,event,state = checkpoints[n]
            bound = (body['step']==k and body['pid']==event['process_identity']['pid']
                and body['session_id']==event['session_id'] and body['predecessor_id']==state.content_hash)
        except (ValueError,KeyError,TypeError,OSError):
            pass
        record(path,'unrequested body marker',bound,cid if bound else None)
    for path in sorted(run.glob('edge-*.checker.json')):
        try:
            checker = _json(path)
            conflict = checker.get('verdict') != 'CHECKER_PASS'
        except (ValueError,KeyError,TypeError,OSError):
            conflict = True
        if conflict:
            # Original REFUSED schema has no run/checkpoint/source binding.
            # A published receipt mismatch above is separate bound evidence.
            record(path,'unbound checker refusal/conflict')
    if n==3 and states and states[-1].generation==n and n in checkpoints:
        if states[-1].public_bits != APPROVED_N3_FINAL_PUBLIC_BITS:
            record(root/'store/objects'/(states[-1].content_hash+'.json'),
                'bound final public bits mismatch',True,checkpoints[n][0])
    return anomalies


def evaluate_v1_evidence(attempt_root: Path, requested_steps: int, reference: dict) -> dict:
    """Read existing evidence without creating locks, recovering or checking numerics."""
    report = {'schema': 'COMPUTE_METABOLISM_ADMISSION_V0', 'admitted': False,
        'outcome': 'REFUSED_VERIFICATION', 'evidence_scope': 'UNKNOWN', 'formal_certification': False,
        'requested_steps': requested_steps, 'raw_v1_result': None}
    root = no_alias(attempt_root)
    try:
        manifest = _json(root / 'attempt.json')
        report.update(evidence_scope=manifest['evidence_scope'], run_id=manifest['run_id'])
        _require(manifest['schema'] == 'COMPUTE_METABOLISM_ATTEMPT_V0' and manifest['evidence_scope'] in ('LIVE', 'TEST_ONLY'), 'attempt identity invalid')
        _scope(requested_steps, manifest['role'], manifest['profile'])
        _require(manifest['requested_steps'] == requested_steps and re.fullmatch(r'[a-z0-9][a-z0-9-]{0,63}', manifest['run_id']) is not None,
                 'requested run identity mismatch')
        run = root / 'runs' / manifest['run_id']
        try:
            result_raw = _read(run / 'result.json')
            report.update(raw_v1_result=strict_json(result_raw), raw_v1_result_sha256=digest_bytes(result_raw))
        except Exception as exc:
            report['raw_v1_result_error'] = f'{type(exc).__name__}: {exc}'
        env, pair, delta, frozen_reference = _environment_evidence(root, manifest)
        upper = _saved_upper_before(root, manifest)
        _reference(reference)
        _require(reference == frozen_reference, 'reference differs from immutable campaign reference')
        result = report['raw_v1_result']
        if result is None or result.get('verdict') != 'ACCEPT':
            anomalies = _failure_anomalies(root,run,manifest,env,pair[0]['snapshot']['epoch']['path'])
            if anomalies:
                report.update(verification_conflict=True,verification_anomalies=anomalies)
                bound = any(item['bound'] for item in anomalies)
                raise AdmissionFailure('existing verification evidence conflicts with failed attempt',
                    'REFUSED_VERIFICATION' if bound else 'UNRESOLVED_FAILURE')
        _require(result is not None, 'raw V1 outcome unavailable', 'UNRESOLVED_FAILURE')
        _require(result['verdict'] == 'ACCEPT', 'raw V1 did not ACCEPT', 'UNRESOLVED_FAILURE')
        metrics_raw = _read(run / 'metrics.json')
        _require(isinstance(strict_json(b'{"metrics":' + metrics_raw + b'}')['metrics'], list), 'raw V1 metrics unavailable')
        report['raw_v1_metrics_sha256'] = digest_bytes(metrics_raw)
        states = _states(root, requested_steps)
        final = states[-1]
        _require((result['run_id'], result['state_id'], result['generation'], result['step_index']) ==
            (manifest['run_id'], final.content_hash, requested_steps, requested_steps), 'raw V1 result/current scope mismatch')
        genesis = _json(root / 'publication-0.json')
        _require(genesis['state_id'] == states[0].content_hash and genesis['step'] == 0 and genesis['run_id'] == manifest['run_id']
            and genesis['body_markers'] == [] and genesis['next_body_absent'] is True, 'fresh genesis publication observation required')
        bodies = sorted(int(p.stem.removeprefix('body-start-')) for p in (run / 'live').glob('body-start-*.json'))
        _require(bodies == list(range(1, requested_steps+1)), 'exact requested bodies only; unrequested body exists')
        edges = [_edge_evidence(root, run, pred, state, requested_steps, env, pair[0]['snapshot']['epoch']['path'])
                 for pred, state in zip(states, states[1:])]
        stopped = _json(run / 'live/session-stop.json')
        _require(stopped['phase'] == 'FINISHED' and stopped['session_id'] == final.live_session_id, 'original session did not finish')
        if requested_steps == 3:
            _require(final.public_bits == APPROVED_N3_FINAL_PUBLIC_BITS, 'N3 final public bits mismatch')
        report.update(admitted=True, outcome='ACCEPT', chain_ids=[s.content_hash for s in states],
            edges=edges, final_public_bits=list(final.public_bits), cgroup_delta=delta,
            input_sha256=manifest['inputs'], guard_before_sha256=manifest['guard_before_sha256'], reference_provenance=reference['provenance'],
            upper_before_sha256=manifest['upper_before_sha256'], upper_running_identity=upper['running'], upper_ledger_path=upper['ledger_path'],
            correctness_authority='TEST_ONLY' if manifest['evidence_scope'] == 'TEST_ONLY' else 'EXISTING_HASH_BOUND_LIVE_CHECKER')
    except AdmissionFailure as exc:
        report.update(outcome=exc.outcome, reason=str(exc))
    except Exception as exc:
        report.update(reason=f'{type(exc).__name__}: {exc}')
    return report


def run_fresh_v1(config: AttemptConfig) -> dict:
    _scope(config.requested_steps, config.role, config.profile)
    get_profile(config.profile)
    _require(re.fullmatch(r'[a-z0-9][a-z0-9-]{0,63}', config.run_id) is not None, 'bounded run identity required')
    parent = no_alias(config.attempt_root)
    _require(parent.is_dir() and no_alias(config.ledger_path).is_file(), 'guard parent/shared ledger required', 'ENVIRONMENT_INVALID')
    quota = no_alias(Path(os.environ.get('RTN_QUOTA_FILE', '')))
    _require(quota == parent / 'writer_quota.txt' and quota.is_file()
        and os.environ.get('RTN_QUOTA_BYTES') == str(CampaignLimits().writer_bytes), 'guard-owned writer allocation required', 'ENVIRONMENT_INVALID')
    repo = no_alias(config.repo_root)
    root = parent / 'v1'
    root.mkdir(exist_ok=False)
    errors = []
    cgroup_path = None
    reference = {}
    numerical_started = False
    driver = None
    try:
        inputs = {}
        for name, path, expected in zip(INPUT_NAMES,
                (config.execution_environment_path, config.campaign_environment_path, config.reference_path),
                (config.execution_environment_sha256, config.campaign_environment_sha256, config.reference_sha256)):
            check_hash(expected)
            raw = _read(path)
            _require(digest_bytes(raw) == expected, 'immutable input hash mismatch', 'ENVIRONMENT_INVALID')
            inputs[name] = strict_json(raw)
            _write_bytes(root / name, raw)
        prepared = _prepared(inputs['execution-environment.json'], config.execution_environment_sha256)
        reference = inputs['reference.json']
        _reference(reference)
        guard_raw = _read(parent / 'guard-cgroup-before.json')
        _write_bytes(root / 'guard-before.json', guard_raw)
        manifest = {'schema': 'COMPUTE_METABOLISM_ATTEMPT_V0', 'evidence_scope': 'LIVE',
            'run_id': config.run_id, 'requested_steps': config.requested_steps, 'role': config.role,
            'profile': config.profile, 'attempt_root': str(parent),
            'campaign_id': config.campaign_id, 'round_index': config.round_index, 'ledger_path': str(no_alias(config.ledger_path)),
            'guard_before_sha256': digest_bytes(guard_raw),
            'inputs': {name: digest_bytes(_read(root / name)) for name in INPUT_NAMES}}
        upper = _capture_upper_before(root, config.ledger_path, manifest)
        manifest.update(upper_before_sha256=content_id(upper), upper_running_identity=upper['running'])
        _write(root / 'attempt.json', manifest)
        cgroup_path = guard.current_cgroup_path()
        env = _capture_environment(repo, prepared)
        _write(root / 'environment-before.json', env)
        _validate_environment(env, prepared, inputs['campaign-environment.json'])
        before = guard.read_cgroup_snapshot(cgroup_path)
        topology = guard.read_cpu_topology()
        guard.validate_enforcement(get_profile(config.profile), before, topology)
        _write(root / 'cgroup-before.json', {'snapshot': before, 'topology': topology, 'wrapper_identity': env['wrapper_identity']})
        _validate_guard_before(strict_json(guard_raw), manifest, before, topology, parent)
        store = ChainStore(root / 'store')
        driver = VerifiedChainDriver(repo, store, root / 'runs', config.ledger_path)
        store._crash_hook = _publication_observer(root, store, driver, config.run_id, cgroup_path)
        # Production driver installs its own V1Gate and LiveGalaSession.
        numerical_started = True
        driver.run(config.requested_steps, config.run_id)
    except Exception as exc:
        errors.append({'stage': 'run', 'error': f'{type(exc).__name__}: {exc}',
                       'outcome': exc.outcome if isinstance(exc, AdmissionFailure) else
                       ('UNRESOLVED_FAILURE' if numerical_started else 'ENVIRONMENT_INVALID')})
    finally:
        if driver is not None and hasattr(driver, 'metrics'):
            try:
                result_path = root/'runs'/config.run_id/'result.json'
                result_raw = _read(result_path) if result_path.exists() else None
                result = strict_json(result_raw) if result_raw is not None else {}
                _write(root/'driver-metrics-snapshot.json', dict(
                    schema='COMPUTE_METABOLISM_DRIVER_METRICS_V0', provenance='VerifiedChainDriver.metrics',
                    run_id=config.run_id, requested_steps=config.requested_steps,
                    manifest_sha256=digest_bytes(_read(root/'attempt.json')),
                    raw_result_sha256=digest_bytes(result_raw) if result_raw is not None else None,
                    status='COMPLETE' if result.get('verdict')=='ACCEPT' and not errors else 'PARTIAL',
                    metrics=driver.metrics))
            except Exception as exc:
                errors.append(dict(stage='driver-metrics-snapshot',error=f'{type(exc).__name__}: {exc}',outcome='UNRESOLVED_FAILURE'))
        # Independent collectors preserve one receipt even if the other fails.
        try:
            after = guard.read_cgroup_snapshot(cgroup_path or guard.current_cgroup_path())
            topology = guard.read_cpu_topology()
            _write(root / 'cgroup-after.json', {'snapshot': after, 'topology': topology,
                    'wrapper_identity': guard._process_identity(os.getpid())})
        except Exception as exc:
            errors.append({'stage': 'cgroup-after', 'error': f'{type(exc).__name__}: {exc}', 'outcome': 'ENVIRONMENT_INVALID'})
        try:
            prepared = _prepared(_json(root / 'execution-environment.json'), digest_bytes(_read(root / 'execution-environment.json')))
            _write(root / 'environment-after.json', _capture_environment(repo, prepared))
        except Exception as exc:
            errors.append({'stage': 'environment-after', 'error': f'{type(exc).__name__}: {exc}', 'outcome': 'ENVIRONMENT_INVALID'})
    report = evaluate_v1_evidence(root, config.requested_steps, reference)
    if errors:
        report.update(admitted=False, runner_errors=errors)
        if any(e['outcome'] == 'ENVIRONMENT_INVALID' for e in errors):
            report['outcome'] = 'ENVIRONMENT_INVALID'
        elif report['outcome'] == 'ACCEPT':
            report['outcome'] = 'UNRESOLVED_FAILURE'
    _write(root / 'admission.json', report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--config-sha256', required=True)
    args = parser.parse_args(argv)
    raw = _read(args.config)
    check_hash(args.config_sha256)
    _require(digest_bytes(raw) == args.config_sha256, 'CLI immutable config mismatch', 'ENVIRONMENT_INVALID')
    document = strict_json(raw)
    for name in ('repo_root', 'attempt_root', 'ledger_path', 'execution_environment_path', 'campaign_environment_path', 'reference_path'):
        document[name] = Path(document[name])
    report = run_fresh_v1(AttemptConfig(**document))
    return 0 if report['admitted'] and report['evidence_scope'] == 'LIVE' else 2


if __name__ == '__main__':
    raise SystemExit(main())
