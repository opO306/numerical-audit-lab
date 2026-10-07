"""Read-only saved-evidence analysis; no numerical execution or ledger mutation.

Use -B for administrative CLI/helper imports. The only prepared-rootfs helper
re-evaluates immutable Task4 evidence with its existing pure semantic evaluator.
It never launches a driver/checker, recovers a store, or captures live evidence.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
import math
import os
from pathlib import Path
import re
import statistics
import subprocess
import sys
import threading
import time

from . import campaign
from .profiles import CampaignLimits, APPROVED_V1_SOURCE_BINDING, APPROVED_N3_FINAL_PUBLIC_BITS


class AnalysisInvalid(ValueError):
    """Saved evidence cannot authorize a comparison/completion claim."""


class SemanticFailure(AnalysisInvalid):
    def __init__(self, reason, administration):
        super().__init__(reason)
        self.administration = administration


def _require(condition, reason):
    if not condition:
        raise AnalysisInvalid(reason)


def _digest(path):
    path = campaign._safe_path(Path(path))
    info = path.stat()
    _require(path.is_file() and info.st_nlink == 1, 'single-link regular raw evidence required')
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _tree(root, exclude=None):
    campaign.logical_tree_bytes(root)  # existing alias/nonregular safety contract
    files = {}
    for path in sorted(root.rglob('*')):
        if path.is_file() and (exclude is None or not path.is_relative_to(exclude)):
            files[path.relative_to(root).as_posix()] = dict(sha256=_digest(path), bytes=path.stat().st_size)
    raw = campaign._encode(files)
    return dict(sha256=hashlib.sha256(raw).hexdigest(), files=files,
                bytes=sum(item['bytes'] for item in files.values()))


def _contained(path, parent):
    path = campaign._safe_path(Path(path))
    _require(path.is_relative_to(parent), 'raw locator outside validated namespace')
    return path


def _document(path, expected=None):
    digest = expected or _digest(path)
    raw = campaign._frozen_read(Path(path), digest)
    return json.loads(raw)


def _raw_metric(path):
    if not path.exists():
        return dict(locator=str(path), sha256=None, value=None, status='UNAVAILABLE')
    digest = _digest(path)
    try:
        value = _document(path, digest)
        return dict(locator=str(path), sha256=digest, value=value, status='AVAILABLE')
    except (ValueError, OSError) as exc:
        return dict(locator=str(path), sha256=digest, value=None, status='INVALID', reason=str(exc))


def _statistics(values):
    n = len(values)
    mean = statistics.mean(values) if n else None
    sd = statistics.stdev(values) if n >= 2 else None
    return dict(n=n, mean=mean, sample_sd=sd, cv=sd/mean if sd is not None and mean > 0 else None,
                unit='seconds')


def _identity_observations(config):
    observations, issues = {}, []
    repo = campaign._safe_path(Path(config['repo_root']))
    for name in campaign._IDENTITY_FILES:
        item = config['identities'][name]
        try:
            target = campaign._safe_path(Path(item['path']))
            _require(target == repo/name, 'current source origin mismatch')
            observations[name] = dict(locator=str(target), expected_sha256=item['sha256'], sha256=_digest(target))
            _require(observations[name]['sha256'] == item['sha256'], 'current source differs from frozen bytes')
        except (ValueError, OSError, KeyError) as exc:
            issues.append(f'{name}: {exc}')
    return observations, issues


def _actual_host_binding(config):
    """Bind the validators actually imported here to the frozen source bytes."""
    from . import profiles
    observations=dict(status='VALID',campaign={},dependencies=None,analyzer_aliases_valid=False)
    expected_origin=Path(__file__).parent/'campaign.py'
    expected_hash=config['identities']['compute_metabolism/v0/campaign.py']['sha256']
    observed=observations['campaign']
    observed.update(origin=getattr(campaign,'__file__',None),spec_origin=getattr(campaign.__spec__,'origin',None),
        expected_origin=str(expected_origin),expected_sha256=expected_hash)
    try:
        origin=campaign._safe_path(Path(observed['origin']))
        if origin.is_file(): observed['sha256']=_digest(origin)
        _require(origin==expected_origin and Path(observed['spec_origin'])==expected_origin
            and sys.modules.get('compute_metabolism.v0.campaign') is campaign, 'actual imported campaign origin invalid')
        campaign._frozen_read(origin,expected_hash)
        observations['dependencies']=campaign._bind_host_dependencies(config)
        _require(CampaignLimits is profiles.CampaignLimits and CampaignLimits is campaign.CampaignLimits
            and APPROVED_V1_SOURCE_BINDING is profiles.APPROVED_V1_SOURCE_BINDING
            and APPROVED_N3_FINAL_PUBLIC_BITS is profiles.APPROVED_N3_FINAL_PUBLIC_BITS,
            'actual analyzer profile API aliases invalid')
        observations['analyzer_aliases_valid']=True
    except (ValueError,OSError,TypeError,KeyError) as exc:
        observations['status']='ENVIRONMENT_INVALID'
        observations['reason']=f'{type(exc).__name__}: {exc}'
        if isinstance(exc,campaign.HostSourceInvalid): observations['dependencies']=exc.observations
    return observations


def _verify_saved_helper(execution, root, context):
    admin = execution['administration']
    _require(admin['measurement_role'] == 'ADMINISTRATION_ONLY' and admin['returncode'] == 0,
             'saved classification helper unavailable')
    stdout, stderr = bytes.fromhex(admin['stdout_hex']), bytes.fromhex(admin['stderr_hex'])
    _require(len(stdout) <= 65536 and len(stderr) <= 65536, 'saved helper output unbounded')
    _require(hashlib.sha256(stdout).hexdigest() == admin['stdout_sha256']
             and hashlib.sha256(stderr).hexdigest() == admin['stderr_sha256'], 'saved helper stream hash mismatch')
    response = json.loads(stdout)
    hashes = admin['evidence_sha256']
    _require(set(hashes) == set(campaign._CONTEXT_FILES) and response['evidence_sha256'] == hashes
             and response['context'] == context, 'saved helper context/hash-set mismatch')
    for name, expected in hashes.items():
        campaign._frozen_read(root/name, expected)
    _require(context['manifest_sha256'] == hashes['attempt.json']
             and context['environment_before_sha256'] == hashes['environment-before.json']
             and context['environment_after_sha256'] == hashes['environment-after.json']
             and context['upper_before_sha256'] == hashes['upper-ledger-before.json']
             and context['input_sha256'] == {name:hashes[name] for name in campaign._INPUT_FILES},
             'saved helper evidence bindings invalid')


def _bounded_process(argv, request, cwd):
    """Cap both retained streams while enforcing the fixed helper deadline."""
    process = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, cwd=cwd)
    outputs, overflow = {}, threading.Event()
    def collect(name, stream, limit):
        chunks, length = [], 0
        try:
            while True:
                chunk = stream.read(4096)
                if not chunk:
                    break
                length += len(chunk)
                if length > limit:
                    overflow.set()
                    process.kill()
                    break
                chunks.append(chunk)
        finally:
            outputs[name] = b''.join(chunks)
            stream.close()
    threads = [threading.Thread(target=collect,args=('stdout',process.stdout,1024*1024)),
               threading.Thread(target=collect,args=('stderr',process.stderr,65536))]
    delivery_errors=[]
    def deliver():
        try:
            process.stdin.write(request)
        except (OSError,ValueError) as exc:
            delivery_errors.append(str(exc))
        finally:
            process.stdin.close()
    threads.append(threading.Thread(target=deliver))
    for thread in threads:
        thread.start()
    timed_out = False
    try:
        process.wait(timeout=30)
    except subprocess.TimeoutExpired:
        timed_out = True
        process.kill()
        process.wait()
    except Exception:
        process.kill()
        process.wait()
        raise
    finally:
        for thread in threads:
            thread.join(timeout=5)
    _require(not any(thread.is_alive() for thread in threads), 'helper stream closure unavailable')
    return dict(returncode=process.returncode, stdout=outputs['stdout'], stderr=outputs['stderr'],
                timed_out=timed_out, overflow=overflow.is_set(), delivery_errors=delivery_errors)


def _evaluation_helper():
    """Fixed inner entry: existing saved semantic evaluator only, zero writes."""
    request_raw = sys.stdin.buffer.read(1024*1024+1)
    _require(len(request_raw) <= 1024*1024, 'bounded helper request required')
    request = json.loads(request_raw)
    root = campaign._helper_root(request['root'])
    n = request['requested_steps']
    _require(type(n) is int and n in (1,3), 'N1/N3 saved evaluation only')
    before = _tree(root.parent)
    _require(before['sha256'] == request['attempt_tree_sha256'], 'helper raw tree differs from host request')
    from . import run_v1
    _require(Path(__file__)==Path('/workspace/compute_metabolism/v0/analyze.py'), 'inner analyzer origin mismatch')
    campaign._frozen_read(Path(__file__),request['analysis_source_sha256'])
    _require(set(request['source_sha256']) == set(campaign._IDENTITY_FILES), 'complete helper source binding required')
    for name, expected in request['source_sha256'].items():
        campaign._frozen_read(Path('/workspace')/name, expected)
    for name, module in (('campaign',campaign),('run_v1',run_v1)):
        expected_origin=Path('/workspace')/f'compute_metabolism/v0/{name}.py'
        _require(Path(module.__file__)==expected_origin and Path(module.__spec__.origin)==expected_origin,
                 'prepared helper imported source shadowing')
    reference = _document(root/'reference.json')
    report = run_v1.evaluate_v1_evidence(root, n, reference)
    context = None
    try:
        context = campaign._saved_classification_context(root)
    except (ValueError, OSError, KeyError) as exc:
        report = dict(report, semantic_context_error=f'{type(exc).__name__}: {exc}')
    after = _tree(root.parent)
    _require(before == after, 'semantic evaluation changed raw evidence')
    response = campaign._encode(dict(report=report, context=context, requested_steps=n,
        attempt_tree_sha256=after['sha256'], raw_preserved=True))
    _require(len(response) <= 1024*1024, 'bounded helper response required')
    sys.stdout.buffer.write(response)


def _semantic_evaluation(root, config, n, receipt):
    from . import system_guard as guard
    prepared = campaign._safe_path(Path(config['root_directory']))
    _require(prepared == guard.PREPARED_ROOT and root.is_relative_to(prepared), 'fixed prepared root required')
    inner = '/' + root.relative_to(prepared).as_posix()
    # Validate lexically without changing the immutable inner manifest.
    campaign._helper_root(inner)
    before = _tree(root.parent)
    request = campaign._encode(dict(root=inner,requested_steps=n,attempt_tree_sha256=before['sha256'],
        analysis_source_sha256=_digest(Path(__file__)),
        source_sha256={name:item['sha256'] for name,item in config['identities'].items()}))
    _require(len(request) <= 1024*1024, 'bounded helper request required')
    argv = ['sudo','-n','chroot',str(prepared),'/usr/bin/env','--chdir=/workspace',
        'PYTHONDONTWRITEBYTECODE=1',guard.INNER_PYTHON,'-B','-c',
        'from compute_metabolism.v0.analyze import _evaluation_helper; _evaluation_helper()']
    started = time.monotonic()
    streams = _bounded_process(argv,request,prepared/'workspace')
    administrative = dict(measurement_role='ADMINISTRATION_ONLY',argv=argv,
        wall_seconds=time.monotonic()-started,**{key:value for key,value in streams.items() if key not in ('stdout','stderr')},
        stdout_hex=streams['stdout'].hex(),stderr_hex=streams['stderr'].hex(),
        stdout_sha256=hashlib.sha256(streams['stdout']).hexdigest(),stderr_sha256=hashlib.sha256(streams['stderr']).hexdigest())
    if before != _tree(root.parent):
        raise SemanticFailure('helper changed raw evidence',administrative)
    if streams['returncode'] != 0 or streams['timed_out'] or streams['overflow']:
        raise SemanticFailure('prepared saved-evidence helper failed',administrative)
    try:
        response = json.loads(streams['stdout'])
    except ValueError as exc:
        raise SemanticFailure('prepared helper response invalid',administrative) from exc
    _require(response['raw_preserved'] is True and response['attempt_tree_sha256'] == before['sha256']
             and response['requested_steps'] == n, 'helper host/raw/N binding mismatch')
    report, context = response['report'], response['context']
    _require(context is not None and report['run_id'] == context['run_id'] == receipt['run_id']
             and context['unit'] == receipt['unit'] and context['epoch'] == receipt['before']['epoch']
             and context['source_binding'] == APPROVED_V1_SOURCE_BINDING, 'helper semantic run/source/unit binding mismatch')
    return report, context, administrative


def _finalizations(config, state, rows, root):
    issues, receipts = [], []
    for pointer in state.get('campaign_finalizations',[]):
        if pointer.get('campaign_id') != config['campaign_id']:
            continue
        try:
            path = _contained(pointer['locator'],root)
            receipt = _document(path,pointer['sha256'])
            proof_path = _contained(receipt['upper_proof_locator'],root)
            proof = campaign._read(proof_path)
            _require(_digest(proof_path) == receipt['upper_proof_sha256'], 'finalization upper proof hash mismatch')
            _require(receipt['schema'] == 'COMPUTE_METABOLISM_CAMPAIGN_FINALIZATION_V0'
                and receipt['campaign_id'] == config['campaign_id'] and receipt['run_id'] == pointer['run_id']
                and receipt['phase'] in ('PRELAUNCH','POST_FINISH')
                and receipt['total_wall_seconds'] == proof['total_wall_seconds']
                and proof.get('formal_campaign') == state.get('formal_campaign'), 'finalization receipt/upper identity mismatch')
            _require(len(proof['attempts']) <= len(state['attempts'])
                and proof['attempts'] == state['attempts'][:len(proof['attempts'])], 'finalization upper history continuity mismatch')
            observed = receipt['observed_retained_total_bytes']
            _require(type(observed) is int and observed >= proof['retained_total_bytes'], 'finalization retained continuity mismatch')
            history = [row for row in proof['attempts'] if row['campaign_id'] == config['campaign_id']]
            needs_next = campaign.next_attempt(history) is not None
            _require(type(receipt['needs_next_attempt']) is bool and receipt['needs_next_attempt'] == needs_next,
                'finalization next-attempt/history mismatch')
            resource = campaign._upper_resource_status(dict(proof,observed_retained_total_bytes=observed),
                needs_next,proof_path,receipt['upper_proof_sha256'])
            policy = campaign._policy_status(history)
            _require(receipt.get('policy_status') == policy, 'finalization policy status/history mismatch')
            if not resource['campaign_stop'] and policy['campaign_stop']:
                resource.update(campaign_stop=True,campaign_outcome=policy['campaign_outcome'])
            _require(all(receipt.get(key)==value for key,value in resource.items()), 'finalization policy/proof mismatch')
            _require(pointer['campaign_outcome']==receipt['campaign_outcome'], 'finalization pointer outcome mismatch')
            if receipt['phase']=='POST_FINISH':
                _require(any(row['run_id']==receipt['run_id'] and row['status']=='FINISHED' for row in proof['attempts']),
                    'POST_FINISH has no bound FINISHED attempt')
            receipts.append(dict(locator=str(path),sha256=pointer['sha256'],receipt=receipt))
        except (ValueError,OSError,KeyError,TypeError) as exc:
            issues.append(f'finalization {pointer.get("run_id")}: {exc}')
    for row in rows:
        if row['status']=='FINISHED' and row.get('execution_locator'):
            if not any(item['receipt']['run_id']==row['run_id'] and item['receipt']['phase']=='POST_FINISH' for item in receipts):
                issues.append(f'{row["run_id"]}: missing valid POST_FINISH receipt')
    return receipts, issues


def _attempt(row,config,root,can_evaluate):
    result = dict(raw_record=row,analysis_eligible=False,performance_eligible=False,issues=[],
                  semantic_evaluation=None,administrative_evaluation=None,raw_metrics={})
    if row['role']=='guard-preflight':
        result['issues'].append('guard-preflight is unscored')
        return result
    branch = 'warmup' if row['role']=='warm-up' else f'round-{row["round_index"]:02d}'
    parent = root/branch/row['run_id']
    v1 = parent/'v1'
    run = v1/'runs'/row['run_id']
    result['raw_metrics'] = dict(v1_metrics=_raw_metric(run/'metrics.json'),
        driver_metrics_snapshot=_raw_metric(v1/'driver-metrics-snapshot.json'),
        barriers=[_raw_metric(path) for path in sorted(run.glob('barrier-*.json'))],
        environment_before=_raw_metric(v1/'environment-before.json'),environment_after=_raw_metric(v1/'environment-after.json'),
        cgroup_before=_raw_metric(v1/'cgroup-before.json'),cgroup_after=_raw_metric(v1/'cgroup-after.json'),
        guard_outer=_raw_metric(parent/'guard-outer.json'))
    if row['status']!='FINISHED':
        result['issues'].append('unfinished/unknown containment; no saved execution authority')
        return result
    try:
        execution_path = _contained(row['execution_locator'],parent)
        _require(execution_path == parent/'execution.json', 'execution origin mismatch')
        execution = _document(execution_path,row['execution_sha256'])
        result['execution'] = dict(locator=str(execution_path),sha256=row['execution_sha256'],value=execution)
        _require(execution['schema']=='COMPUTE_METABOLISM_EXECUTION_V0' and execution['run_id']==row['run_id'], 'execution run/schema mismatch')
        config_path = parent.parent/f'config-{row["run_id"]}.json'
        attempt_config = _document(config_path,execution['config_sha256'])
        n = 1 if row['role']=='warm-up' else 3
        for key in ('run_id','campaign_id','profile','role','round_index'):
            _require(attempt_config[key]==row[key], 'attempt config/ledger binding mismatch')
        _require(attempt_config['requested_steps']==n, 'attempt N scope mismatch')
        prepared=Path(config['root_directory'])
        inner_parent='/'+parent.relative_to(prepared).as_posix()
        inner_upper='/'+Path(config['ledger_path']).relative_to(prepared).as_posix()
        _require(attempt_config['repo_root']=='/workspace' and attempt_config['attempt_root']==inner_parent
            and attempt_config['ledger_path']==inner_upper, 'immutable inner attempt/upper origin invalid')
        for prefix,name in (('execution_environment','execution-environment.json'),
                            ('campaign_environment','campaign-environment.json'),('reference','reference.json')):
            _require(attempt_config[prefix+'_path']=='/'+(root/name).relative_to(prepared).as_posix()
                and attempt_config[prefix+'_sha256']==config['inputs'][name]['sha256'], 'attempt input/config binding invalid')
        receipt = execution['guard_receipt']
        _require(_contained(receipt['proof_locator'],parent)==parent/'guard-outer.json', 'guard proof origin mismatch')
        report = execution['admission_report']
        context = report['classification_context']
        for key in ('run_id','campaign_id','profile','role','round_index'):
            _require(context[key]==row[key], 'helper context/ledger binding mismatch')
        saved = _document(v1/'admission.json')
        for key,value in saved.items():
            _require(report.get(key)==value, 'detached admission differs from raw admission')
        _verify_saved_helper(execution,v1,context)
        _require(execution['identities_before']==config['identities'] and execution['identities_after']==
            {key:value['sha256'] for key,value in config['identities'].items()}, 'execution source identities mismatch')
        for key in ('host_dependencies_before','host_dependencies_after'):
            _require(execution[key]['status']=='VALID', 'execution imported host source invalid')
            modules=execution[key]['modules']
            _require(set(modules)=={'profiles','system_guard'}, 'complete imported host source evidence required')
            for name,module in modules.items():
                expected=config['identities'][f'compute_metabolism/v0/{name}.py']['sha256']
                origin=Path(module['origin'])
                _require(origin.is_absolute() and module['origin']==module['spec_origin']==module['expected_origin']
                    and tuple(origin.parts[-3:])==('compute_metabolism','v0',f'{name}.py')
                    and module['sha256']==module['expected_sha256']==expected,
                    'imported host source origin/hash authority invalid')
        _require(execution['writer_reserved_bytes']==row['writer_reserved_bytes'] and execution['retained_bytes']==row['retained_bytes'],
                 'execution cost/ledger binding mismatch')
        _require(execution['retained_bytes']==campaign.logical_tree_bytes(parent), 'actual retained tree/cost mismatch')
        quota=(parent/'writer_quota.txt').read_bytes()
        _require(re.fullmatch(b'[0-9]+',quota) is not None and int(quota)==row['writer_reserved_bytes'], 'raw writer counter mismatch')
        classified = campaign.classify_attempt(report,receipt,execution['retained_bytes'])
        if row['role']=='warm-up' and classified['wrapper_outcome']!='ACCEPT':
            classified.update(campaign_stop=True,campaign_outcome='STOP')
        _require(classified==execution['classification'], 'classification disagrees with saved bound proof')
        for key,value in classified.items():
            _require(row.get(key)==value, 'ledger classification mismatch')
        _require(row['outcome']==classified['wrapper_outcome'] and row['outer_wall_seconds']==receipt['wall_seconds']
                 and row['cpu_seconds']==classified.get('cpu_seconds'), 'ledger authoritative wall/CPU/outcome mismatch')
        result['verified_classification'] = classified
        _require(can_evaluate, 'source/finalization invariant unavailable; saved bytes are provenance only')
        semantic, new_context, administrative = _semantic_evaluation(v1,config,n,receipt)
        result.update(semantic_evaluation=semantic,administrative_evaluation=administrative)
        _require(new_context==context, 'new semantic context differs from saved classification helper')
        _require(semantic['run_id']==row['run_id'] and semantic['requested_steps']==n
                 and semantic['evidence_scope']=='LIVE' and context['evidence_scope']=='LIVE', 'actual LIVE run/N authority unavailable')
        if classified['wrapper_outcome']=='ACCEPT':
            _require(semantic['admitted'] is True and semantic['outcome']=='ACCEPT'
                and semantic['correctness_authority']=='EXISTING_HASH_BOUND_LIVE_CHECKER', 'saved checker semantic admission failed')
            _require(n==1 or tuple(semantic['final_public_bits'])==APPROVED_N3_FINAL_PUBLIC_BITS, 'approved N3 final bits mismatch')
        elif classified['wrapper_outcome']=='REFUSED_RESOURCE':
            _require(classified['resource_proven'] is True and classified['invariants_valid'] is True
                and semantic['outcome'] not in ('REFUSED_VERIFICATION','ENVIRONMENT_INVALID')
                and not semantic.get('verification_conflict'), 'resource refusal hides semantic fault')
        else:
            raise AnalysisInvalid('fault outcome is not admissible')
        result['analysis_eligible'] = classified['eligible'] and classified['invariants_valid']
        result['performance_eligible'] = result['analysis_eligible'] and row['role']=='measured' and classified['wrapper_outcome']=='ACCEPT'
    except (ValueError,OSError,KeyError,TypeError,OverflowError) as exc:
        if isinstance(exc,SemanticFailure):
            result['administrative_evaluation']=exc.administration
        result['issues'].append(f'{type(exc).__name__}: {exc}')
    return result


def _render(summary):
    lines = ['# Compute Metabolism V0 saved-evidence analysis', '',f'Outcome: **{summary["outcome"]}**', '',
        f'Proposed snapshot outcome: {summary.get("proposed_outcome",summary["outcome"])}. Candidate evidence is nonfinal until hash-bound publication.json; any publication-stop.json overrides it with STOP.', '',
        'Scope: this campaign and its saved V1 N1/N3 evidence only. No fitness, Joule/energy, physical, general CPU/cloud or formal certification claim.', '',
        'Outer guarded wall and cgroup delta usage_usec / 1,000,000 are separate authoritative totals. Paused includes seal/produce/check/publication; these raw components are never summed into total cost.', '',
        'Analysis/helper administration is separate from guarded compute. Source-frozen bytes are provenance, not execution permission.', '',
        '## Completion blockers', '']
    lines.extend('- '+issue for issue in summary['issues'])
    lines += ['', '## Profiles', '', '| Profile | All-outcome decision | Eligible N3 ACCEPT n | Wall mean s | CPU mean s |', '|---|---|---:|---:|---:|']
    for profile,item in summary['profiles'].items():
        lines.append(f'| {profile} | {item["decision"]["decision"]} | {item["outer_wall_seconds"]["n"]} | {item["outer_wall_seconds"]["mean"]} | {item["cpu_seconds"]["mean"]} |')
    lines += ['', 'Both sample SDs use n−1. Missing/undefined statistics remain null. All refusals, partial records, unknown CPU and outliers remain in summary.json; subset statistics do not override all-outcome policy.', '',
        'Derived comparisons use profile ACCEPT mean / 2c ACCEPT mean only for admissible stable profiles; raw measurements are separate.', '',
        '## Attempts', '']
    for item in summary['attempts']:
        row=item['raw_record']
        lines.append(f'- {row["run_id"]}: {row["role"]}, {row["profile"]}, {row["status"]}, {row.get("outcome")}; performance eligible={item["performance_eligible"]}; CPU={row.get("cpu_seconds")}; issues={json.dumps(item["issues"],ensure_ascii=False)}')
    lines += ['', '## Retained output accounting', '', json.dumps(summary.get('output_accounting'),sort_keys=True), '',
        'The upper ledger is read only. Owning orchestration must reconcile retained output bytes before any later authorized action. No continuation permission is granted by this report.', '',
        f'Raw input SHA256 before: {summary["raw_tree"]["before_sha256"]}', f'Raw input SHA256 after: {summary["raw_tree"]["after_sha256"]}', '']
    return '\n'.join(lines).encode('utf-8')


def analyze_campaign(campaign_root: Path) -> dict:
    """Analyze actual immutable receipts with zero raw writes or new allowance."""
    started=time.monotonic()
    root=campaign._safe_path(Path(campaign_root))
    before=_tree(root.parent,root/'analysis')
    config_raw=campaign._frozen_read(root/'campaign.json',_digest(root/'campaign.json'))
    config=json.loads(config_raw)
    _require(config['schema']=='COMPUTE_METABOLISM_CAMPAIGN_V0' and config['campaign_id']==root.name,
             'campaign schema/root identity invalid')
    _require(Path(config['ledger_path'])==root.parent/'budget.json'
             and Path(config['repo_root'])==Path(config['root_directory'])/'workspace'
             and root.parent==Path(config['repo_root'])/'compute_metabolism/v0/artifacts', 'campaign upper/root namespace invalid')
    executing_source=campaign._safe_path(Path(__file__))
    _require(Path(sys.modules[__name__].__spec__.origin if __spec__ else __file__)==executing_source,
        'executing analyzer source origin mismatch')
    analysis_source=dict(origin=str(executing_source),sha256=_digest(executing_source))
    host_before=_actual_host_binding(config)
    view_issues=[]
    try:
        state,rows=campaign._campaign_view(config,config_raw)
    except (ValueError,OSError,KeyError,TypeError) as exc:
        state=campaign.CampaignLedger.read_snapshot(Path(config['ledger_path']))
        rows=[row for row in state['attempts'] if row['campaign_id']==config['campaign_id']]
        view_issues.append('saved campaign binding invalid: '+str(exc))
    observations,source_issues=_identity_observations(config)
    if host_before['status']!='VALID': source_issues.append('actual host source before: '+json.dumps(host_before,sort_keys=True))
    issues=view_issues+source_issues
    receipts,finalization_issues=_finalizations(config,state,rows,root)
    issues.extend(finalization_issues)
    for key in ('campaign_resource_stop','campaign_environment_stop','campaign_finalization_unresolved'):
        if state.get(key): issues.append(key+': '+json.dumps(state[key],sort_keys=True))
    if state['running'] is not None: issues.append('unresolved RUNNING authority')
    if state['start_refusals']: issues.append('upper start refusals remain')
    if any(root.parent.glob('*.pending')) or any(root.parent.glob('.*.pending')): issues.append('retained pending upper write')
    eligible_gate=not issues
    attempts=[_attempt(row,config,root,eligible_gate) if row['campaign_id']==config['campaign_id'] else
        dict(raw_record=row,analysis_eligible=False,performance_eligible=False,issues=['other upper namespace; not this campaign dataset'],raw_metrics={})
        for row in state['attempts']]
    own=[item for item in attempts if item['raw_record']['campaign_id']==config['campaign_id']]
    host_after=_actual_host_binding(config)
    if host_after['status']!='VALID' or host_before!=host_after or _digest(executing_source)!=analysis_source['sha256']:
        issue='actual host source changed/invalid after analysis'
        source_issues.append(issue)
        issues.append(issue)
        for item in own:
            item['analysis_eligible']=item['performance_eligible']=False
            item['issues'].append(issue)
    verified_rows=[]
    for item in own:
        row=dict(item['raw_record'],eligible=item['analysis_eligible'],invariants_valid=item['analysis_eligible'])
        if not item['analysis_eligible'] and row['role']!='guard-preflight':
            row['campaign_stop']=True
            issues.extend(f'{row["run_id"]}: {issue}' for issue in item['issues'])
        verified_rows.append(row)
    warm=[item for item in own if item['raw_record']['role']=='warm-up']
    warm_ok=(len(warm)==1 and warm[0]['analysis_eligible'] and warm[0]['raw_record']['profile']=='2c'
             and warm[0]['raw_record']['round_index']==0 and warm[0]['raw_record']['outcome']=='ACCEPT')
    if not warm_ok: issues.append('exactly one valid unscored 2c N1 warm-up required')
    profiles={}
    for profile in ('2c','1c','0p5c'):
        subset=[item['raw_record'] for item in own if item['performance_eligible'] and item['raw_record']['profile']==profile]
        decision=campaign.profile_decision(profile,verified_rows)
        profiles[profile]=dict(decision=decision,outer_wall_seconds=_statistics([row['outer_wall_seconds'] for row in subset]),
            cpu_seconds=_statistics([row['cpu_seconds'] for row in subset]),
            statistics_role='ELIGIBLE_ACCEPT_SUBSET_DESCRIPTIVE_ONLY',
            outcomes={outcome:sum(row['profile']==profile and row['role']=='measured' and row.get('outcome')==outcome for row in rows)
                      for outcome in sorted({row.get('outcome','RUNNING') for row in rows})})
    stable=profiles['2c']['decision']['decision']=='STABLE_ACCEPT' and profiles['1c']['decision']['decision']=='STABLE_ACCEPT' and profiles['0p5c']['decision']['decision'] in ('STABLE_ACCEPT','STABLE_RESOURCE_REFUSAL')
    next_item=campaign.next_attempt(verified_rows)
    resource=campaign._upper_resource_status(state,next_item is not None,Path(config['ledger_path']),_digest(config['ledger_path']))
    if resource['campaign_stop']: issues.append('upper resource STOP: '+json.dumps(resource,sort_keys=True))
    stopped=bool(view_issues or source_issues or finalization_issues or any(state.get(key) for key in ('campaign_resource_stop','campaign_environment_stop','campaign_finalization_unresolved')) or state['running'] is not None or state['start_refusals'] or observations and any(o['sha256']!=o['expected_sha256'] for o in observations.values())
        or any(item['issues'] for item in own if item['raw_record']['role']!='guard-preflight') or resource['campaign_stop'])
    outcome='COMPLETE' if stable and warm_ok and not issues else 'STOP' if stopped else 'UNRESOLVED_VARIABILITY' if any(item['decision']['decision']=='UNRESOLVED_VARIABILITY' for item in profiles.values()) else 'STOP_INCOMPLETE' if any(item['decision']['decision'] in ('STOP','STOP_INCOMPLETE') for item in profiles.values()) else 'INCOMPLETE'
    ratios={}
    if not stopped and warm_ok and profiles['2c']['decision']['decision']=='STABLE_ACCEPT':
        base=profiles['2c']
        for profile,item in profiles.items():
            if item['decision']['decision']=='STABLE_ACCEPT':
                ratios[profile]=dict(measurement_role='DERIVED_ONLY',formula='profile eligible ACCEPT mean / 2c eligible ACCEPT mean',
                    numerator_n=item['outer_wall_seconds']['n'],denominator_n=base['outer_wall_seconds']['n'],unit='dimensionless',
                    outer_wall_ratio=item['outer_wall_seconds']['mean']/base['outer_wall_seconds']['mean'],
                    cpu_ratio=item['cpu_seconds']['mean']/base['cpu_seconds']['mean'])
    after=_tree(root.parent,root/'analysis')
    _require(before==after,'raw input tree changed during analysis')
    return dict(schema='COMPUTE_METABOLISM_ANALYSIS_V0',campaign_id=config['campaign_id'],outcome=outcome,issues=issues,
        counts=dict(all_attempts=len(state['attempts']),campaign_attempts=len(rows),warm_up=len(warm),
            measured=sum(row['role']=='measured' for row in rows),guard_preflight=sum(row['role']=='guard-preflight' for row in state['attempts'])),
        attempts=attempts,profiles=profiles,derived_ratios=ratios,upper=state,finalization_receipts=receipts,
        current_source_observations=observations,analysis_source=analysis_source,
        actual_host_dependencies_before=host_before,actual_host_dependencies_after=host_after,
        config_sha256=hashlib.sha256(config_raw).hexdigest(),
        raw_tree=dict(before_sha256=before['sha256'],after_sha256=after['sha256'],files=before['files'],raw_bytes=before['bytes']),
        timing_contract=dict(wall_authority='OUTER_GUARD_WALL',cpu_authority='CGROUP_DELTA_USAGE_USEC_DIV_1000000',
            paused_overlaps=['seal','produce','check','publication'],component_sum_is_total=False),
        administration=dict(measurement_role='ADMINISTRATION_ONLY',analysis_wall_seconds=time.monotonic()-started),
        output_accounting=None,formal_certification=False)


_PUBLICATION_BYTES=4096


def _publication_integrity(root,summary):
    """Recheck content, inventories and actual/prepared sources at submission."""
    result=dict(raw_verified=False,source_verified=False,raw_sha256=None,reason=None)
    try:
        campaign.logical_tree_bytes(root.parent)
        sizes={path.relative_to(root.parent).as_posix():path.stat().st_size
            for path in root.parent.rglob('*') if path.is_file() and not path.is_relative_to(root/'analysis')}
        expected={name:item['bytes'] for name,item in summary['raw_tree']['files'].items()}
        if sizes==expected:
            current=_tree(root.parent,root/'analysis')
            result['raw_sha256']=current['sha256']
            result['raw_verified']=current['files']==summary['raw_tree']['files'] and current['sha256']==summary['raw_tree']['after_sha256']
        config=_document(root/'campaign.json',summary['config_sha256'])
        observed,issues=_identity_observations(config)
        host=_actual_host_binding(config)
        result['source_verified']=(not issues and host['status']=='VALID'
            and host==summary['actual_host_dependencies_after']
            and observed==summary['current_source_observations']
            and _digest(summary['analysis_source']['origin'])==summary['analysis_source']['sha256'])
    except (ValueError,OSError,TypeError,KeyError):
        pass
    if not result['raw_verified']: result['reason']='RAW_INTEGRITY_CHANGED'
    elif not result['source_verified']: result['reason']='SOURCE_INTEGRITY_CHANGED'
    return result


def _publication_payload(receipt):
    receipt=dict(receipt,metadata_padding='')
    raw=campaign._encode(receipt)
    _require(len(raw)<=_PUBLICATION_BYTES,'bounded publication receipt required')
    receipt['metadata_padding']=' '*(_PUBLICATION_BYTES-len(raw))
    raw=campaign._encode(receipt)
    _require(len(raw)==_PUBLICATION_BYTES,'publication metadata sizing invalid')
    return raw


def _write_analysis(root,summary):
    base=root/'analysis'
    campaign._safe_path(base)
    try:
        base.mkdir()
        destination=base
    except FileExistsError:
        _require(base.is_dir(),'analysis output namespace invalid')
        for sequence in range(1,10000):
            destination=base/f'version-{sequence:04d}'
            try:
                destination.mkdir()
                break
            except FileExistsError:
                continue
        else:
            raise AnalysisInvalid('exclusive analysis versions exhausted')
    integrity_before=_publication_integrity(root,summary)
    proposed=summary['outcome']
    if integrity_before['reason']:
        proposed='STOP'
        summary['issues'].append('publication precheck: '+integrity_before['reason'])
    summary['proposed_outcome']=proposed
    summary['outcome']='PENDING_PUBLICATION'
    summary['publication_contract']='Candidate only; publication.json is final authority; any publication-stop.json overrides it with STOP.'
    before_bytes=campaign.logical_tree_bytes(root.parent)
    output_bytes=0
    for _ in range(64):
        projected=before_bytes+output_bytes
        if projected>=CampaignLimits().retained_total_bytes:
            summary['proposed_outcome']='STOP'
            reason='analysis/report bytes reach CAMPAIGN_EVIDENCE_CEILING'
            if reason not in summary['issues']: summary['issues'].append(reason)
        summary['output_accounting']=dict(measurement_role='ADMINISTRATION_ONLY',upper_bytes_before_output=before_bytes,
            output_bytes=output_bytes,projected_upper_bytes=projected,ceiling=CampaignLimits().retained_total_bytes,
            ledger_reconciliation='OWNER_REQUIRED_READ_ONLY_ANALYSIS',directory=str(destination))
        payload=campaign._encode(summary)
        report=_render(summary)
        actual=len(payload)+len(report)+_PUBLICATION_BYTES
        if actual==output_bytes:
            break
        output_bytes=actual
    else:
        raise AnalysisInvalid('analysis output sizing nonconvergence; no completion claim')
    campaign._exclusive_raw(destination/'summary.json',payload)
    campaign._exclusive_raw(destination/'report.md',report)
    integrity_after=_publication_integrity(root,summary)
    outcome=summary['proposed_outcome']
    if integrity_before['reason'] or integrity_after['reason']: outcome='STOP'
    summary_hash=_digest(destination/'summary.json')
    report_hash=_digest(destination/'report.md')
    outputs_verified=(summary_hash==hashlib.sha256(payload).hexdigest() and report_hash==hashlib.sha256(report).hexdigest())
    if not outputs_verified: outcome='STOP'
    receipt=dict(schema='COMPUTE_METABOLISM_ANALYSIS_PUBLICATION_V0',outcome=outcome,
        proposed_outcome=summary['proposed_outcome'],raw_before_sha256=summary['raw_tree']['after_sha256'],
        raw_after_sha256=integrity_after['raw_sha256'],raw_verified=integrity_before['raw_verified'] and integrity_after['raw_verified'],
        source_verified=integrity_before['source_verified'] and integrity_after['source_verified'],
        reason=integrity_before['reason'] or integrity_after['reason'] or (None if outputs_verified else 'OUTPUT_INTEGRITY_CHANGED'),
        summary_sha256=summary_hash,report_sha256=report_hash,outputs_verified=outputs_verified,
        output_bytes=output_bytes,observed_retained_total_bytes=summary['output_accounting']['projected_upper_bytes'])
    publication_payload=_publication_payload(receipt)
    publication_expected_sha256=hashlib.sha256(publication_payload).hexdigest()
    campaign._exclusive_raw(destination/'publication.json',publication_payload)
    actual=campaign.logical_tree_bytes(root.parent)
    final_integrity=_publication_integrity(root,summary)
    final_outputs_verified=(_digest(destination/'summary.json')==summary_hash and _digest(destination/'report.md')==report_hash)
    publication_observed_sha256=None
    try:
        publication_observed_sha256=_digest(destination/'publication.json')
        final_publication_verified=(publication_observed_sha256==publication_expected_sha256
            and campaign._frozen_read(destination/'publication.json',publication_expected_sha256)==publication_payload)
    except (ValueError,OSError):
        final_publication_verified=False
    if final_integrity!=integrity_after or not final_outputs_verified or not final_publication_verified or actual!=summary['output_accounting']['projected_upper_bytes']:
        # Append a dominating STOP authority, preserving all candidate/receipt bytes.
        outcome='STOP'
        stop=dict(receipt,outcome='STOP',reason=final_integrity['reason'] or ('PUBLICATION_INTEGRITY_CHANGED' if not final_publication_verified else 'OUTPUT_INTEGRITY_CHANGED' if not final_outputs_verified else 'OUTPUT_ACCOUNTING_CHANGED'),
            outputs_verified=final_outputs_verified,
            raw_after_sha256=final_integrity['raw_sha256'],raw_verified=final_integrity['raw_verified'],
            source_verified=final_integrity['source_verified'],
            publication_sha256=publication_observed_sha256,
            output_bytes=output_bytes+_PUBLICATION_BYTES,observed_retained_total_bytes=actual+_PUBLICATION_BYTES)
        campaign._exclusive_raw(destination/'publication-stop.json',_publication_payload(stop))
        summary['output_accounting']['output_bytes']=stop['output_bytes']
        summary['output_accounting']['projected_upper_bytes']=stop['observed_retained_total_bytes']
    summary['outcome']=outcome
    return destination


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--campaign-root',required=True,type=Path)
    args=parser.parse_args(argv)
    try:
        summary=analyze_campaign(args.campaign_root)
        destination=_write_analysis(campaign._safe_path(args.campaign_root),summary)
        print(json.dumps(dict(outcome=summary['outcome'],analysis_directory=str(destination),output_accounting=summary['output_accounting'])))
        return 0 if summary['outcome']=='COMPLETE' else 2
    except (ValueError,OSError,KeyError,TypeError) as exc:
        print(json.dumps(dict(outcome='STOP',reason=f'{type(exc).__name__}: {exc}')))
        return 2


if __name__=='__main__':
    raise SystemExit(main())
