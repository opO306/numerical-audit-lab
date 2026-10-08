"""Explicit independent authority admission for the finite fresh N1 profile."""
import os
from pathlib import Path
from verified_driver.v1.model import digest_bytes, content_id

PROFILE_ID='libc-memset-avx512-evex-16zero-v1'

def _need(ok,why):
    if not ok:raise ValueError('REFUSED: native profile '+why)

def _registered(binding,root):
    from compute_metabolism.v0 import adaptive,evex_profile
    from verified_driver.v1.live_chain.session import live_source_snapshot
    _need(type(binding) is dict and set(binding)=={'profile_id','manifest_sha256','source_binding'},'explicit binding keys')
    _need(binding['profile_id']==PROFILE_ID,'finite profile ID')
    folder=Path(root)/'compute_metabolism/v0/execution_profiles'
    index=adaptive._read(folder/'registry.json')
    _need(index.get('schema')=='COMPUTE_METABOLISM_PROFILE_REGISTRY_V1','registry schema')
    rows=[x for x in index['profiles'] if x.get('path')==PROFILE_ID+'.json']
    _need(len(rows)==1 and rows[0]['manifest_sha256']==binding['manifest_sha256'],'registered manifest binding')
    profile=adaptive.validate_profile(adaptive._read(folder/(PROFILE_ID+'.json')))
    _need(profile['status']=='VERIFIED' and adaptive.digest(profile)==binding['manifest_sha256'],'no candidate authority')
    _need(profile['v1_source_binding']==binding['source_binding']==content_id(live_source_snapshot(Path(root))),'current complete source binding')
    verified=evex_profile.verify_registered_profile(profile,Path(root))
    _need(adaptive.canonical(verified)==adaptive.canonical(profile),'independent exact registered replay')
    return profile

def admit_capture(capture,root):
    if 'native_profile_binding' not in capture:return None
    profile=_registered(capture['native_profile_binding'],root)
    _need(capture.get('requested_steps')==1 and type(capture.get('requested_steps')) is int,'finite N1 capture')
    _need(capture.get('source_pinset_sha256')==profile['v1_source_binding'],'capture source binding')
    _need(set(profile['entry_points'])=={0x1996c0},'finite entry')
    return dict(profile_id=PROFILE_ID,libc_sha256=profile['libraries']['libc']['sha256'],
        libc_build_id=profile['libraries']['libc']['build_id'],entry_elf_pc=0x1996c0,
        caller_module_sha256=profile['libraries']['gala']['sha256'],
        caller_build_id=profile['libraries']['gala']['build_id'],source_sha256=profile['v1_source_binding'],
        library_path=profile['verification']['library_paths']['libc'],caller_path=profile['verification']['library_paths']['gala'])

def admit_environment(root,requested_steps):
    """Hash-bound campaign input; a raw row or environment label grants nothing."""
    path=os.environ.get('CM_NATIVE_PROFILE_CONFIG');sha=os.environ.get('CM_NATIVE_PROFILE_SHA256')
    if path is None and sha is None:return None
    _need(path is not None and sha is not None and requested_steps==1,'explicit N1 input')
    from compute_metabolism.v0 import adaptive,run_v1,source_epoch
    raw=run_v1._read(Path(path));_need(digest_bytes(raw)==sha,'campaign input hash')
    campaign=adaptive._read(Path(path));binding=campaign['execution_profile']
    _need(binding['profile_id']==PROFILE_ID,'finite campaign profile')
    snapshot,current=source_epoch.validate_epoch(campaign['source_epoch'],Path(root))
    profile=_registered(dict(profile_id=PROFILE_ID,manifest_sha256=binding['manifest_sha256'],source_binding=current),root)
    adaptive.validate_campaign_binding(binding,binding['fingerprint'],[profile])
    registry=Path(root)/'compute_metabolism/v0/execution_profiles/registry.json'
    _need(digest_bytes(run_v1._read(registry))==campaign['execution_registry_sha256'],'campaign registry hash')
    return dict(profile_id=PROFILE_ID,manifest_sha256=binding['manifest_sha256'],source_binding=current)
