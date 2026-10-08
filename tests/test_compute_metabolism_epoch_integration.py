"""Explicit source amendment preserves old preparation and numerical authority."""
import copy
import json
from pathlib import Path

import pytest
from compute_metabolism.v0 import run_v1 as runner, campaign
from verified_driver.v1.live_chain.session import live_source_snapshot
from verified_driver.v1.model import content_id
from tests import test_compute_metabolism_v0_v1 as legacy

ROOT=Path(__file__).parents[1]
OLD='f75980706aefbbd68cddce09549695c2f633905e01185f92f96660db81a9e2cd'
evidence=legacy.evidence


@pytest.fixture
def epoch():
    archive=f'compute_metabolism/v0/source_epochs/{OLD}/source'
    manifest=json.loads((ROOT/Path(archive).parent/'manifest.json').read_bytes())
    snapshot=live_source_snapshot(ROOT)
    return dict(schema='COMPUTE_METABOLISM_SOURCE_EPOCH_V1',predecessor_binding=OLD,
        predecessor_snapshot=manifest['source_snapshot'],source_snapshot=snapshot,
        source_binding=content_id(snapshot),source_count=len(snapshot),
        source_amendment='2026-10-07-native-evex-semantics',historical_source_archive=archive,
        review_sha256='a'*64,regression_sha256='b'*64)


@pytest.fixture
def case(epoch):
    env=legacy.environment();prepared=copy.deepcopy(env['runtime'])
    env['runtime'].update(source_count=epoch['source_count'],source_binding=epoch['source_binding'],source_matches=True)
    env['source_snapshot']=copy.deepcopy(epoch['source_snapshot'])
    env['source_epoch']=copy.deepcopy(epoch)
    campaign_env=dict(schema='COMPUTE_METABOLISM_ENVIRONMENT_V0',instance_id='123456',
        boot_id=env['boot_id'],topology=env['topology'],platform=env['runtime']['platform'],source_epoch=copy.deepcopy(epoch))
    return env,prepared,campaign_env


def test_new_current_epoch_environment_admitted_with_immutable_old_preparation(case):
    env,prepared,campaign_env=case;frozen=copy.deepcopy(prepared)
    assert env['runtime']['source_count']>40
    runner._validate_environment(env,prepared,campaign_env,'TEST_ONLY',repo_root=ROOT)
    assert prepared==frozen and prepared['source_count']==40 and prepared['source_binding']==OLD
    assert runner._environment_source_binding(env,ROOT)==env['runtime']['source_binding']


@pytest.mark.parametrize('drift',['epoch','snapshot','count','binding','matches','packages','files','missing_env_epoch'])
def test_current_epoch_or_userspace_drift_refused(case,drift):
    env,prepared,campaign_env=case
    if drift=='epoch':campaign_env['source_epoch']['source_binding']='0'*64
    elif drift=='snapshot':env['source_snapshot'][next(iter(env['source_snapshot']))]='0'*64
    elif drift=='count':env['runtime']['source_count']=40
    elif drift=='binding':env['runtime']['source_binding']=OLD
    elif drift=='matches':env['runtime']['source_matches']=False
    elif drift in ('packages','files'):env['runtime'][drift][next(iter(env['runtime'][drift]))]='changed'
    else:env.pop('source_epoch')
    with pytest.raises(runner.AdmissionFailure):
        runner._validate_environment(env,prepared,campaign_env,'TEST_ONLY',repo_root=ROOT)


def test_current_binding_cannot_bypass_missing_explicit_amendment(case):
    env,prepared,campaign_env=case
    campaign_env.pop('source_epoch');env.pop('source_epoch')
    with pytest.raises(runner.AdmissionFailure):
        runner._validate_environment(env,prepared,campaign_env,'TEST_ONLY',repo_root=ROOT)


def test_context_source_binding_recomputed_from_physical_epoch(case):
    env,_,_=case
    context=dict(source_binding=env['runtime']['source_binding'],source_epoch=env['source_epoch'])
    assert campaign.context_source_binding(context,ROOT)==env['runtime']['source_binding']
    context['source_binding']=OLD
    with pytest.raises(ValueError):campaign.context_source_binding(context,ROOT)


def test_old_context_and_reference_keep_fixed_historical_authority():
    assert campaign.context_source_binding(dict(source_binding=OLD),ROOT)==OLD
    with pytest.raises(ValueError):campaign.context_source_binding(dict(source_binding='a'*64),ROOT)
    reference=dict(schema='COMPUTE_METABOLISM_REFERENCE_V0',requested_steps=3,source_binding='a'*64,
        final_public_bits=list(runner.APPROVED_N3_FINAL_PUBLIC_BITS),
        provenance=[dict(locator='historical',sha256='a'*64,role='HISTORICAL_REFERENCE')])
    with pytest.raises(runner.AdmissionFailure):runner._reference(reference)


def test_gate_source_snapshot_exact_physical_union(epoch):
    snapshot=campaign.gate_source_snapshot(ROOT,epoch)
    assert set(epoch['source_snapshot'])<=set(snapshot)
    assert 'compute_metabolism/v0/source_epoch.py' in snapshot
    assert 'compute_metabolism/v0/historical_profile.py' in snapshot
    assert 'compute_metabolism/v0/evex_profile.py' in snapshot
    assert 'verified_driver/v0/model.py' in snapshot
    assert 'runtime_trace/numeric_ir/checker.py' in snapshot
    assert not any('/execution_profiles/' in p for p in snapshot)
    assert campaign.validate_gate_source_snapshot(snapshot,ROOT,epoch)==snapshot


@pytest.mark.parametrize('drift',['missing','extra','changed'])
def test_gate_map_cannot_override_authority_sources(epoch,drift):
    snapshot=campaign.gate_source_snapshot(ROOT,epoch)
    if drift=='missing':snapshot.pop('compute_metabolism/v0/source_epoch.py')
    elif drift=='extra':snapshot['unreviewed/injected.py']='a'*64
    else:snapshot['compute_metabolism/v0/source_epoch.py']='a'*64
    with pytest.raises(ValueError):campaign.validate_gate_source_snapshot(snapshot,ROOT,epoch)


def test_capture_environment_copies_epoch_and_matches_new_source_without_network(case,monkeypatch):
    import types
    from compute_metabolism.v0 import adaptive
    env,prepared,_=case
    raw_stat='cpu 1 2 3 4 5 6 7 8'
    original=Path.read_text
    def read(path,*args,**kwargs):
        texts={'/proc/stat':raw_stat,'/proc/sys/kernel/random/boot_id':env['boot_id'],
               '/proc/loadavg':'TEST_ONLY load','/proc/pressure/cpu':'TEST_ONLY pressure'}
        name=path.as_posix()
        return texts[name] if name in texts else original(path,*args,**kwargs)
    monkeypatch.setattr(Path,'read_text',read)
    monkeypatch.setattr(runner.sys,'version',prepared['python'])
    monkeypatch.setattr(runner.sys,'executable',prepared['executable'])
    monkeypatch.setattr(runner.importlib.metadata,'version',lambda name:prepared['packages'][name])
    monkeypatch.setattr(runner.importlib.metadata,'distributions',lambda:[
        types.SimpleNamespace(metadata={'Name':name},version=value) for name,value in prepared['packages'].items()])
    monkeypatch.setattr(runner,'_runtime_file_hashes',lambda _:copy.deepcopy(prepared['files']))
    monkeypatch.setattr(runner,'_instance_identity',lambda:copy.deepcopy(env['instance_observation']))
    monkeypatch.setattr(runner,'_optional_dmi',lambda:dict(status='UNAVAILABLE',value=None))
    monkeypatch.setattr(runner.guard,'read_cpu_topology',lambda:env['topology'])
    monkeypatch.setattr(runner.guard,'_process_identity',lambda _:env['wrapper_identity'])
    monkeypatch.setattr(adaptive,'detect_environment',lambda *_:dict(status='TEST_ONLY'))
    actual=runner._capture_environment(ROOT,prepared,env['source_epoch'])
    assert actual['source_epoch']==env['source_epoch'] and actual['source_epoch'] is not env['source_epoch']
    assert actual['runtime']['source_matches'] is True
    assert actual['runtime']['source_count']>40 and prepared['source_count']==40
    assert actual['runtime']['source_binding']!=prepared['source_binding']


def test_epoch_campaign_requires_frozen_gate_map(epoch,tmp_path,monkeypatch):
    import hashlib
    from tests.test_compute_metabolism_v0_campaign import cli_config
    path,_,config=cli_config(tmp_path,monkeypatch)
    campaign_path=Path(config['inputs']['campaign-environment.json']['path'])
    campaign_path.write_text(json.dumps(dict(source_epoch=epoch)))
    config['inputs']['campaign-environment.json']['sha256']=hashlib.sha256(campaign_path.read_bytes()).hexdigest()
    path.write_text(json.dumps(config));digest=hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(ValueError,match='requires frozen gate source snapshot'):
        campaign._configuration(path,digest)


def test_epoch_configuration_binds_union_and_fixed_extra_dependencies(epoch,tmp_path,monkeypatch):
    import hashlib
    import shutil
    from tests.test_compute_metabolism_v0_campaign import cli_config
    path,_,config=cli_config(tmp_path,monkeypatch);repo=Path(config['repo_root'])
    snapshot=campaign.gate_source_snapshot(ROOT,epoch)
    for relative in snapshot:
        target=repo/relative;target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes((ROOT/relative).read_bytes())
    archive=Path(epoch['historical_source_archive'])
    shutil.copytree(ROOT/archive,repo/archive)
    for relative in campaign._EPOCH_IDENTITY_FILES:
        config['identities'][relative]=dict(path=str(repo/relative),sha256=snapshot[relative])
    config['gate_source_snapshot']=snapshot
    campaign_path=Path(config['inputs']['campaign-environment.json']['path'])
    campaign_path.write_text(json.dumps(dict(source_epoch=epoch)))
    config['inputs']['campaign-environment.json']['sha256']=hashlib.sha256(campaign_path.read_bytes()).hexdigest()
    path.write_text(json.dumps(config));digest=hashlib.sha256(path.read_bytes()).hexdigest()
    validated,_,_=campaign._configuration(path,digest)
    assert validated['gate_source_snapshot']==snapshot
    bound=campaign._bind_host_dependencies(config)
    assert {'source_epoch','historical_profile','evex_profile','gala_origin_check'}<=set(bound['modules'])
    assert set(campaign.identity_names(config))==set(config['identities'])
    assert campaign.identity_names({})==campaign._IDENTITY_FILES


@pytest.mark.parametrize('use_current_edge',[True,False])
def test_complete_test_only_edge_requires_current_epoch_authority(case,evidence,monkeypatch,use_current_edge):
    """All edge hashes are rebuilt; a coherent historical edge still refuses."""
    env,_,campaign_env=case
    binding=env['runtime']['source_binding'] if use_current_edge else OLD
    monkeypatch.setattr(legacy,'environment',lambda:copy.deepcopy(env))
    monkeypatch.setattr(legacy,'APPROVED_V1_SOURCE_BINDING',binding)
    root,reference=evidence(1)
    reference['source_binding']=OLD
    legacy.put(root/'reference.json',reference)
    legacy.put(root/'campaign-environment.json',campaign_env)
    manifest=legacy.get(root/'attempt.json')
    manifest['inputs']={name:runner.digest_bytes((root/name).read_bytes()) for name in manifest['inputs']}
    legacy.put(root/'attempt.json',manifest)
    admission=runner.evaluate_v1_evidence(root,1,reference)
    assert admission['admitted'] is use_current_edge
    assert admission['evidence_scope']=='TEST_ONLY'
    if use_current_edge:
        context=campaign._saved_classification_context(root)
        assert context['source_epoch']==env['source_epoch']
        assert campaign.context_source_binding(context,ROOT)==binding
    else:
        assert admission['outcome']=='REFUSED_VERIFICATION'
        assert admission['reason']=='state predecessor/source mismatch'
