"""One original Gala call, under the unchanged operational upper and guard.

No store, CURRENT, checkpoint, session authority or certified state is created.
The separately frozen observation environment amends source identity while
preserving the previous campaign and all its failed attempt/finalization bytes.
"""
import argparse,copy,hashlib,json,re
from pathlib import Path
from . import adaptive,campaign,system_guard as guard,observation_run as history
from .profiles import CampaignLimits,get_profile
from verified_driver.v1.model import HARNESS_SHA

def observation_environment(prior,epoch):
    environment=copy.deepcopy(prior)
    environment.pop('execution_profile',None);environment.pop('execution_registry_sha256',None)
    environment['source_epoch']=copy.deepcopy(epoch)
    return environment

def _check_sources(config,repo):
    campaign.validate_gate_source_snapshot(config['source_manifest'],repo,config['source_epoch'])

def _inner(path,expected):
    from . import run_v1,gala_observer
    from runtime_trace.regular_nstep.resources import reserve_writer
    config=json.loads(campaign._frozen_read(path,expected));repo=Path('/workspace')
    out=Path(config['inner_output']);epoch=config['source_epoch']
    if (config.get('schema')!='COMPUTE_METABOLISM_GALA_OBSERVATION_CONFIG_V1'
        or config.get('mode')!='OBSERVATION' or config.get('certified_state_progress') is not False
        or config.get('profile')!='2c' or config.get('harness_sha256')!=HARNESS_SHA
        or adaptive.digest(epoch)!=config['source_epoch_sha256']
        or out!=repo/'compute_metabolism/v0/artifacts/operational'/config['campaign_id']/'observations'/config['run_id']/'observations'):
        raise ValueError('finite actual Gala observation config/namespace required')
    _check_sources(config,repo);out.mkdir(exist_ok=False)
    # Environment/selection diagnostics only. Recorder reserves its own bounded
    # scratch + retained allocation from the same counter before creating files.
    reserve_writer(4*1024*1024)
    prepared=run_v1._prepared(config['prepared'],config['prepared_sha256'])
    stage='environment-before';error=None
    try:
        before=run_v1._capture_environment(repo,prepared,epoch)
        campaign._exclusive_raw(out/'environment-before.json',adaptive.canonical(before))
        run_v1._validate_environment(before,prepared,config['campaign_environment'],repo_root=repo)
        if before['execution_fingerprint']!=config['fingerprint'] or adaptive.digest(before['execution_fingerprint'])!=config['fingerprint_sha256']:
            raise ValueError('frozen actual Gala fingerprint drift')
        registry=repo/'compute_metabolism/v0/execution_profiles'
        if hashlib.sha256((registry/'registry.json').read_bytes()).hexdigest()!=config['execution_registry_sha256']:
            raise ValueError('pre-observation registry drift')
        profiles=adaptive.load_registry(registry,repo_root=repo)
        decision=adaptive.plan_execution(profiles,before['execution_fingerprint'])
        campaign._exclusive_raw(out/'selection.json',adaptive.canonical(decision))
        if decision['mode']!='OBSERVATION':raise ValueError('unknown route observation requires no compatible VERIFIED profile')
        stage='actual-Gala-call-observation'
        result=gala_observer.observe_gala(before['execution_fingerprint'],out/'gala-observation.raw.json',repo,
            gdb_sha256=config['gdb_sha256'],source_snapshot=epoch['source_snapshot'])
        if result.get('schema')!='gala-native-observation-v1' or 'diagnostic' in result:
            raise ValueError('actual Gala observation incomplete/refused')
    except Exception as exc:
        error=dict(stage=stage,exception_type=type(exc).__name__,exception_message=str(exc),
            certified_state_progress=False,mode='OBSERVATION')
        campaign._exclusive_raw(out/'diagnostic.json',adaptive.canonical(error))
    finally:
        try:
            after=run_v1._capture_environment(repo,prepared,epoch)
            campaign._exclusive_raw(out/'environment-after.json',adaptive.canonical(after))
            run_v1._validate_environment(after,prepared,config['campaign_environment'],repo_root=repo)
            _check_sources(config,repo)
            if after['execution_fingerprint']!=config['fingerprint']:
                raise ValueError('after actual Gala environment/fingerprint drift')
        except Exception as exc:
            campaign._exclusive_raw(out/'after-diagnostic.json',adaptive.canonical(dict(
                stage='environment-after',exception_type=type(exc).__name__,exception_message=str(exc))))
            error=error or dict(stage='environment-after',exception_message=str(exc))
    return 2 if error else 0

def observation_status(receipt,directory,source_matches):
    if not source_matches or (directory/'after-diagnostic.json').exists():return 'ENVIRONMENT_INVALID','OBSERVATION_FAILED'
    original=receipt.get('outcome')
    if original!='GUARD_COMPLETE':
        return original if original in ('ENVIRONMENT_INVALID','REFUSED_RESOURCE','UNRESOLVED_FAILURE','REFUSED_VERIFICATION') else 'UNRESOLVED_FAILURE','OBSERVATION_FAILED'
    if receipt.get('measurement_valid') is not True or (directory/'diagnostic.json').exists():
        return 'UNRESOLVED_FAILURE','OBSERVATION_FAILED'
    try:
        doc=adaptive._read(directory/'gala-observation.raw.json')
        launch=adaptive._read(directory/'gala-launch.json')
        if (doc['schema']!='gala-native-observation-v1' or 'diagnostic' in doc
            or doc['termination']!=dict(inferior_killed=True,remaining_owned_pids=[],certified_state_progress=False)
            or launch['outcome']!='OBSERVED_UNCERTIFIED' or launch['process']['returncode']!=0
            or launch['process']['stop_reason'] is not None):raise ValueError('incomplete raw observation')
    except (OSError,ValueError,KeyError,TypeError):return 'UNRESOLVED_FAILURE','OBSERVATION_FAILED'
    return 'GUARD_COMPLETE','OBSERVED_UNCERTIFIED'

def run_observation(root_directory,run_id,fingerprint,epoch,gate_sources):
    root=campaign._safe_path(root_directory)
    if root!=guard.PREPARED_ROOT:raise ValueError('fixed prepared actual Gala observation root required')
    repo=root/'workspace';ledger_path=repo/'compute_metabolism/v0/artifacts/operational/budget.json'
    campaign.validate_gate_source_snapshot(gate_sources,repo,epoch)
    before_raw=ledger_path.read_bytes();state=campaign.CampaignLedger.read_snapshot(ledger_path)
    prior=state['formal_campaign'];parent=ledger_path.parent/prior['campaign_id']
    old_config=json.loads(campaign._frozen_read(parent/'campaign.json',prior['config_sha256']))
    prepared_raw=campaign._frozen_read(parent/'execution-environment.json',old_config['inputs']['execution-environment.json']['sha256'])
    old_env_raw=campaign._frozen_read(parent/'campaign-environment.json',old_config['inputs']['campaign-environment.json']['sha256'])
    scope=campaign.observation_authorization(old_config)
    if scope is not None and (scope['run_id']!=run_id or scope['fingerprint_sha256']!=adaptive.digest(fingerprint)
            or scope['source_epoch_sha256']!=adaptive.digest(epoch)
            or scope['registry_sha256']!=hashlib.sha256((repo/'compute_metabolism/v0/execution_profiles/registry.json').read_bytes()).hexdigest()
            or scope['gdb_sha256']!=hashlib.sha256((root/'usr/bin/gdb').read_bytes()).hexdigest()):
        raise ValueError('frozen OBSERVATION_ONLY live fingerprint/source/registry/GDB mismatch')
    if re.fullmatch('[a-z0-9][a-z0-9-]{0,63}',run_id) is None:raise ValueError('bounded observation identity')
    namespace=parent/'observations';campaign._create_durable_artifact_root(namespace)
    attempt=namespace/run_id
    if attempt.exists():raise ValueError('exclusive actual Gala observation attempt required')
    before_path=namespace/('upper-before-'+run_id+'.raw.json');campaign._exclusive_raw(before_path,before_raw)
    config=dict(schema='COMPUTE_METABOLISM_GALA_OBSERVATION_CONFIG_V1',mode='OBSERVATION',
        certified_state_progress=False,campaign_id=prior['campaign_id'],run_id=run_id,profile='2c',
        inner_output='/'+(attempt/'observations').relative_to(root).as_posix(),
        fingerprint=fingerprint,fingerprint_sha256=adaptive.digest(fingerprint),source_epoch=epoch,
        source_epoch_sha256=adaptive.digest(epoch),source_manifest=gate_sources,
        prepared=json.loads(prepared_raw),prepared_sha256=hashlib.sha256(prepared_raw).hexdigest(),
        campaign_environment=observation_environment(json.loads(old_env_raw),epoch),
        upper_before_sha256=hashlib.sha256(before_raw).hexdigest(),
        gdb_sha256=hashlib.sha256((root/'usr/bin/gdb').read_bytes()).hexdigest(),
        execution_registry_sha256=hashlib.sha256((repo/'compute_metabolism/v0/execution_profiles/registry.json').read_bytes()).hexdigest(),
        harness_sha256=HARNESS_SHA)
    raw=adaptive.canonical(config);path=namespace/('config-'+run_id+'.json');campaign._exclusive_raw(path,raw)
    ledger=campaign.CampaignLedger.open(ledger_path,CampaignLimits())
    history._begin_observation(ledger,run_id,hashlib.sha256(raw).hexdigest())
    command=[guard.INNER_PYTHON,'-B','-m','compute_metabolism.v0.gala_observation_run','--inner-config',
        '/'+path.relative_to(root).as_posix(),'--config-sha256',hashlib.sha256(raw).hexdigest()]
    try:
        receipt=guard.run_system_guard(get_profile('2c'),run_id=run_id,artifact_dir=attempt,command=command,
            topology=config['campaign_environment']['topology'],root_directory=root,limits=CampaignLimits())
    except Exception as exc:
        partial=dict(mode='OBSERVATION',exception_type=type(exc).__name__,exception_message=str(exc),campaign_stop=True)
        ledger.record_unresolved(run_id,partial);return partial
    if receipt.get('terminal') is not True or receipt.get('launcher_reaped') is not True:
        ledger.record_unresolved(run_id,receipt);return dict(mode='OBSERVATION',campaign_stop=True,guard=receipt)
    proof=dict(receipt,proof_locator=str(attempt/'guard-outer.json'),proof_sha256=hashlib.sha256((attempt/'guard-outer.json').read_bytes()).hexdigest())
    try:cost=campaign.measured_guard_cost(proof)
    except (ValueError,OSError,KeyError,TypeError) as exc:cost=dict(cpu_seconds=None,cpu_measurement_status='UNAVAILABLE',error=str(exc))
    source_matches=True
    try:_check_sources(config,repo)
    except Exception:source_matches=False
    outcome,status=observation_status(receipt,attempt/'observations',source_matches)
    quota=(attempt/'writer_quota.txt').read_bytes()
    if re.fullmatch(b'[0-9]+',quota) is None:
        ledger.record_unresolved(run_id,dict(stage='writer-accounting',guard=proof));return dict(campaign_stop=True,mode='OBSERVATION')
    record=dict(schema='COMPUTE_METABOLISM_OBSERVATION_EXECUTION_V1',kind='ACTUAL_GALA',mode='OBSERVATION',
        certified_state_progress=False,config_sha256=hashlib.sha256(raw).hexdigest(),guard=proof,cpu_accounting=cost,
        source_manifest=gate_sources,wrapper_outcome=outcome,observation_outcome=status,
        writer_used_bytes=int(quota),writer_reservation_bytes=CampaignLimits().writer_bytes)
    record['observation_evidence']={p.relative_to(attempt/'observations').as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (attempt/'observations').rglob('*') if p.is_file()}
    payload,retained=history._execution_payload(record,attempt)
    campaign._exclusive_raw(attempt/'observation-execution.json',payload)
    if campaign.logical_tree_bytes(attempt)!=retained:raise campaign.LedgerIntegrityError('actual Gala retained sizing changed')
    ledger.finish_attempt(run_id,receipt['wall_seconds'],cost['cpu_seconds'],int(quota),retained,record['wrapper_outcome'])
    proof_root=namespace/'proofs'/run_id
    campaign._create_durable_artifact_root(proof_root)
    campaign._exclusive_raw(proof_root/'upper-after.raw.json',ledger.path.read_bytes())
    final=campaign._finalize_upper(ledger,old_config,run_id,False,'POST_FINISH')
    return dict(record,retained_bytes=retained,campaign_finalization=final,upper=campaign.CampaignLedger.read_snapshot(ledger_path),
        attempt_directory=str(attempt),proof_directory=str(proof_root),upper_before_path=str(before_path),observation_config_path=str(path))

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inner-config',type=Path,required=True);parser.add_argument('--config-sha256',required=True)
    args=parser.parse_args(argv);return _inner(args.inner_config,args.config_sha256)

if __name__=='__main__':raise SystemExit(main())
