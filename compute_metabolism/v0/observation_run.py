"""Guarded, non-certified observation charged to the existing upper allowance.

A stopped numerical campaign cannot resume through this interface. The only
child command is a bounded synthetic libc sample, with no V1 store or Gala.
All old attempt and finalization records remain unchanged.
"""
from __future__ import annotations
import argparse,hashlib,json,os,re
from pathlib import Path
from . import adaptive,campaign,system_guard as guard
from .profiles import CampaignLimits,get_profile


def _sources(repo):
    names=['compute_metabolism/v0/'+n for n in ('adaptive.py','profile_verify.py','observer.py',
        'gdb_observer.py','observation_run.py','campaign.py','run_v1.py','analyze.py','profiles.py','system_guard.py')]
    names.extend(p.relative_to(repo).as_posix() for p in (repo/'compute_metabolism/v0/execution_profiles').glob('*.json'))
    return {n:hashlib.sha256(campaign._frozen_read(repo/n,hashlib.sha256((repo/n).read_bytes()).hexdigest())).hexdigest() for n in names}


def _begin_observation(ledger,run_id,config_sha256):
    """Grant only OBSERVATION after a durable STOP; no generic resume API."""
    campaign._hash(config_sha256)
    if re.fullmatch('[a-z0-9][a-z0-9-]{0,63}',run_id) is None:
        raise ValueError('bounded observation identity required')
    with ledger._authority():
        state=campaign._read(ledger.path)
        if state['running'] is not None:
            raise campaign.UnresolvedPriorAttempt('prior RUNNING blocks observation')
        prior=state.get('formal_campaign')
        pointers=[p for p in state.get('campaign_finalizations',[]) if prior and p['campaign_id']==prior['campaign_id']]
        config = json.loads(campaign._frozen_read(ledger.root/prior['campaign_id']/'campaign.json', prior['config_sha256'])) if prior else {}
        scope = campaign.observation_authorization(config)
        if scope is not None:
            if scope['run_id'] != run_id:
                raise ValueError('OBSERVATION_ONLY run identity outside frozen authorization')
            actual_path = ledger.root/prior['campaign_id']/'observations'/('config-'+run_id+'.json')
            actual = json.loads(campaign._frozen_read(actual_path, config_sha256))
            if (type(actual) is not dict or actual.get('schema') != 'COMPUTE_METABOLISM_GALA_OBSERVATION_CONFIG_V1'
                    or actual.get('mode') != 'OBSERVATION' or actual.get('profile') != '2c'
                    or actual.get('certified_state_progress') is not False
                    or actual.get('campaign_id') != prior['campaign_id'] or actual.get('run_id') != run_id
                    or actual.get('fingerprint_sha256') != scope['fingerprint_sha256']
                    or adaptive.digest(actual.get('fingerprint')) != scope['fingerprint_sha256']
                    or actual.get('source_epoch_sha256') != scope['source_epoch_sha256']
                    or adaptive.digest(actual.get('source_epoch')) != scope['source_epoch_sha256']
                    or actual.get('source_manifest') != config.get('gate_source_snapshot', {})
                    or actual.get('execution_registry_sha256') != scope['registry_sha256']
                    or actual.get('gdb_sha256') != scope['gdb_sha256']):
                raise ValueError('OBSERVATION_ONLY requires frozen actual-Gala scope/config')
            own = [row for row in state['attempts'] if row['campaign_id'] == prior['campaign_id']]
            links = [link for link in state.get('campaign_restarts', []) if
                link.get('successor_campaign_id') == prior['campaign_id']
                and link.get('successor_config_sha256') == prior['config_sha256']]
            if scope['run_id'] != run_id or own or pointers or len(links) != 1:
                raise ValueError('OBSERVATION_ONLY single successor authorization refused')
            link = links[0]
            predecessor = dict(campaign_id=link['campaign_id'], config_sha256=link['config_sha256'])
            if (not state.get('formal_campaign_history') or state['formal_campaign_history'][-1] != predecessor
                    or config['restart_from_campaign_id'] != predecessor['campaign_id']
                    or config['restart_from_finalization_sha256'] != link['finalization_sha256']):
                raise ValueError('OBSERVATION_ONLY recorded predecessor identity mismatch')
            # Read-only view reuses every original STOP proof/history check.
            view = dict(state, formal_campaign=predecessor)
            checked = campaign._restart_predecessor(view, config, ledger.root)
            if (any(checked[key] != link[key] for key in checked if key != 'retained_total_bytes')
                    or checked['retained_total_bytes'] < link['retained_total_bytes']):
                raise ValueError('OBSERVATION_ONLY predecessor usage/history mismatch')
        else:
            if not pointers:
                raise ValueError('durable prior STOP required for isolated observation')
            campaign._restart_predecessor(state,dict(campaign_id='observation-'+run_id,
                restart_from_campaign_id=prior['campaign_id'],restart_from_finalization_sha256=pointers[-1]['sha256']),ledger.root)
        if any(row['run_id']==run_id for row in state['attempts']):
            raise campaign.AttemptIdentityError('observation identity already used')
        allowed,reason=ledger._funds(state)
        if not allowed:raise campaign.CampaignResourceExhausted(reason)
        identity=dict(campaign_id=prior['campaign_id'],run_id=run_id,profile='2c',role='guard-preflight',round_index=0)
        state['running']=identity
        state['attempts'].append(dict(identity,status='RUNNING',partial_receipts=[],kind='OBSERVATION',
            certified_state_progress=False,observation_config_sha256=config_sha256))
        ledger._prepare_payload(state)
        allowed,reason=ledger._funds(state)
        if not allowed:raise campaign.CampaignResourceExhausted(reason)
        ledger._write(state);ledger._owned_run=(run_id,os.getpid())
        return identity


def _inner(config_path,expected):
    from . import observer,run_v1
    from runtime_trace.regular_nstep.resources import reserve_writer
    config=json.loads(campaign._frozen_read(config_path,expected))
    repo=Path('/workspace');out=Path(config['inner_output'])
    if (config.get('mode')!='OBSERVATION' or config.get('certified_state_progress') is not False
        or out.name!='observations' or out.parent.parent.name!='observations' or config['source_manifest']!=_sources(repo)):
        raise ValueError('isolated observation source/namespace binding invalid')
    out.mkdir(exist_ok=False)
    reserve_writer(16*1024*1024)
    prepared=run_v1._prepared(config['prepared'],config['prepared_sha256'])
    stage='environment-before';result=None;error=None
    try:
        before=run_v1._capture_environment(repo,prepared)
        campaign._exclusive_raw(out/'environment-before.json',adaptive.canonical(before))
        run_v1._validate_environment(before,prepared,config['campaign_environment'])
        if adaptive.digest(before['execution_fingerprint'])!=config['fingerprint_sha256']:
            raise ValueError('live observation fingerprint drift')
        stage='profile-selection'
        registry=repo/'compute_metabolism/v0/execution_profiles'
        profiles=adaptive.load_registry(registry,repo_root=repo)
        decision=adaptive.plan_execution(profiles,before['execution_fingerprint'])
        campaign._exclusive_raw(out/'selection.json',adaptive.canonical(decision))
        if decision['mode']!='OBSERVATION':
            raise ValueError('compatible VERIFIED profile exists; no unknown-route observation')
        stage='bounded-memset-observation'
        if hashlib.sha256(Path('/usr/bin/gdb').read_bytes()).hexdigest()!=config['gdb_sha256']:
            raise ValueError('prepared GDB identity drift')
        result=observer.observe_memset(before['execution_fingerprint'],out/'observation.raw.json',
            python_path=guard.INNER_PYTHON,gdb_path='/usr/bin/gdb',length=16,value=0,max_steps=2048,timeout_seconds=30)
        stage='candidate-generation'
        if result['terminal']['status']!='OBSERVED_RETURN':
            raise ValueError('observation terminal: '+result['terminal']['status'])
        adaptive.generate_candidate(result,adaptive.nearest_profile(profiles,before['execution_fingerprint']),out/'candidate')
    except Exception as exc:
        error=dict(stage=stage,exception_type=type(exc).__name__,exception_message=str(exc),
            certified_state_progress=False,mode='OBSERVATION')
        campaign._exclusive_raw(out/'diagnostic.json',adaptive.canonical(error))
    finally:
        try:
            after=run_v1._capture_environment(repo,prepared)
            campaign._exclusive_raw(out/'environment-after.json',adaptive.canonical(after))
            run_v1._validate_environment(after,prepared,config['campaign_environment'])
            if (adaptive.digest(after['execution_fingerprint'])!=config['fingerprint_sha256']
                or _sources(repo)!=config['source_manifest']):
                raise ValueError('observation after environment/source drift')
        except Exception as exc:
            campaign._exclusive_raw(out/'after-diagnostic.json',adaptive.canonical(dict(
                stage='environment-after',exception_type=type(exc).__name__,exception_message=str(exc))))
            error=error or dict(stage='environment-after',exception_message=str(exc))
    return 2 if error else 0


def _observation_status(receipt,directory,source_matches):
    """CPU measurement availability grants cost recording, never success."""
    if not source_matches or (directory/'after-diagnostic.json').exists():
        return 'ENVIRONMENT_INVALID','OBSERVATION_FAILED'
    original=receipt.get('outcome')
    if original!='GUARD_COMPLETE':
        return original if original in ('ENVIRONMENT_INVALID','REFUSED_RESOURCE','UNRESOLVED_FAILURE','REFUSED_VERIFICATION') else 'UNRESOLVED_FAILURE','OBSERVATION_FAILED'
    if receipt.get('measurement_valid') is not True or (directory/'diagnostic.json').exists():
        return 'UNRESOLVED_FAILURE','OBSERVATION_FAILED'
    try:
        raw=json.loads((directory/'observation.raw.json').read_bytes())
        if raw['terminal']['status']!='OBSERVED_RETURN' or not (directory/'candidate/candidate-profile.json').is_file():
            raise ValueError('complete observation/candidate unavailable')
    except (OSError,ValueError,KeyError,TypeError):
        return 'UNRESOLVED_FAILURE','OBSERVATION_FAILED'
    return 'GUARD_COMPLETE','OBSERVED_UNCERTIFIED'


def _final_status(outcome,status,cpu_available,retained):
    if outcome in ('ENVIRONMENT_INVALID','REFUSED_VERIFICATION','UNRESOLVED_FAILURE'):
        return outcome,'OBSERVATION_FAILED'
    if not cpu_available:
        # A resource refusal without a valid measurement cannot satisfy the
        # ledger's resource-proof contract. Preserve the original guard claim
        # in the raw receipt and initial_observation_outcome below.
        return 'ENVIRONMENT_INVALID','OBSERVATION_FAILED'
    if retained>CampaignLimits().retained_run_bytes:
        return 'REFUSED_RESOURCE','OBSERVATION_FAILED'
    return outcome,status


def _execution_payload(record,directory):
    """Bind the final classification to actual bytes, including this receipt."""
    base=campaign.logical_tree_bytes(directory);retained=base
    original=record['wrapper_outcome'];status=record['observation_outcome']
    record['initial_observation_outcome']=original
    for _ in range(64):
        record['wrapper_outcome'],record['observation_outcome']=_final_status(
            original,status,record['cpu_accounting']['cpu_seconds'] is not None,retained)
        record['retained_bytes']=retained
        payload=adaptive.canonical(record);actual=base+len(payload)
        if actual==retained:return payload,retained
        retained=actual
    raise campaign.LedgerIntegrityError('observation execution sizing did not converge')


def run_observation(root_directory,run_id,fingerprint):
    root=campaign._safe_path(root_directory)
    if root!=guard.PREPARED_ROOT:
        raise ValueError('fixed prepared observation root required')
    repo=root/'workspace';ledger_path=repo/'compute_metabolism/v0/artifacts/operational/budget.json'
    state=campaign.CampaignLedger.read_snapshot(ledger_path)
    prior=state['formal_campaign'];parent=ledger_path.parent/prior['campaign_id']
    old_config=json.loads(campaign._frozen_read(parent/'campaign.json',prior['config_sha256']))
    if campaign.observation_authorization(old_config) is not None:
        raise ValueError('OBSERVATION_ONLY authorization is exclusively for actual Gala')
    prepared_raw=campaign._frozen_read(parent/'execution-environment.json',old_config['inputs']['execution-environment.json']['sha256'])
    environment_raw=campaign._frozen_read(parent/'campaign-environment.json',old_config['inputs']['campaign-environment.json']['sha256'])
    if re.fullmatch('[a-z0-9][a-z0-9-]{0,63}',run_id) is None:
        raise ValueError('bounded observation identity required')
    namespace=parent/'observations';campaign._create_durable_artifact_root(namespace)
    attempt=namespace/run_id
    if attempt.exists():raise ValueError('exclusive observation attempt required')
    source=_sources(repo)
    config=dict(schema='COMPUTE_METABOLISM_ISOLATED_OBSERVATION_V1',mode='OBSERVATION',
        certified_state_progress=False,run_id=run_id,source_manifest=source,
        inner_output='/'+(attempt/'observations').relative_to(root).as_posix(),
        fingerprint_sha256=adaptive.digest(fingerprint),prepared=json.loads(prepared_raw),
        prepared_sha256=hashlib.sha256(prepared_raw).hexdigest(),campaign_environment=json.loads(environment_raw),
        gdb_sha256=hashlib.sha256((root/'usr/bin/gdb').read_bytes()).hexdigest())
    raw=adaptive.canonical(config);path=namespace/('config-'+run_id+'.json')
    campaign._exclusive_raw(path,raw)
    ledger=campaign.CampaignLedger.open(ledger_path,CampaignLimits())
    _begin_observation(ledger,run_id,hashlib.sha256(raw).hexdigest())
    command=[guard.INNER_PYTHON,'-B','-m','compute_metabolism.v0.observation_run','--inner-config',
        '/'+path.relative_to(root).as_posix(),'--config-sha256',hashlib.sha256(raw).hexdigest()]
    try:
        receipt=guard.run_system_guard(get_profile('2c'),run_id=run_id,artifact_dir=attempt,command=command,
            topology=config['campaign_environment']['topology'],root_directory=root,limits=CampaignLimits())
    except Exception as exc:
        partial=dict(mode='OBSERVATION',exception_type=type(exc).__name__,exception_message=str(exc),campaign_stop=True)
        ledger.record_unresolved(run_id,partial);return partial
    if receipt.get('terminal') is not True or receipt.get('launcher_reaped') is not True:
        ledger.record_unresolved(run_id,receipt);return dict(mode='OBSERVATION',campaign_stop=True,guard=receipt)
    proof=dict(receipt,proof_locator=str(attempt/'guard-outer.json'),
        proof_sha256=hashlib.sha256((attempt/'guard-outer.json').read_bytes()).hexdigest())
    try:
        cost=campaign.measured_guard_cost(proof)
    except (ValueError,OSError,KeyError,TypeError) as exc:
        cost=dict(cpu_seconds=None,cpu_measurement_status='UNAVAILABLE',error=str(exc))
    observation_dir=attempt/'observations'
    outcome,observation_status=_observation_status(receipt,observation_dir,_sources(repo)==source)
    quota=(attempt/'writer_quota.txt').read_bytes()
    if re.fullmatch(b'[0-9]+',quota) is None:
        ledger.record_unresolved(run_id,dict(stage='writer-accounting',guard=proof));return dict(campaign_stop=True,mode='OBSERVATION')
    record=dict(schema='COMPUTE_METABOLISM_OBSERVATION_EXECUTION_V1',mode='OBSERVATION',certified_state_progress=False,
        config_sha256=hashlib.sha256(raw).hexdigest(),guard=proof,cpu_accounting=cost,source_manifest=source,
        wrapper_outcome=outcome,writer_used_bytes=int(quota),writer_reservation_bytes=CampaignLimits().writer_bytes)
    record['observation_outcome']=observation_status
    record['observation_evidence']={p.relative_to(observation_dir).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
        for p in observation_dir.rglob('*') if p.is_file()}
    payload,retained=_execution_payload(record,attempt)
    campaign._exclusive_raw(attempt/'observation-execution.json',payload)
    if campaign.logical_tree_bytes(attempt)!=retained:
        raise campaign.LedgerIntegrityError('observation execution retained bytes changed')
    ledger.finish_attempt(run_id,receipt['wall_seconds'],cost['cpu_seconds'],int(quota),retained,record['wrapper_outcome'])
    final=campaign._finalize_upper(ledger,old_config,run_id,False,'POST_FINISH')
    return dict(record,retained_bytes=retained,campaign_finalization=final,upper=campaign.CampaignLedger.read_snapshot(ledger_path))


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inner-config',type=Path,required=True);parser.add_argument('--config-sha256',required=True)
    args=parser.parse_args(argv)
    return _inner(args.inner_config,args.config_sha256)

if __name__=='__main__':raise SystemExit(main())
