"""Execution-profile discovery and draft generation, never numerical authority.

Normal execution consumes a hash-bound VERIFIED registry entry. Unknown routes
produce OBSERVATION artifacts. Candidate construction never calls promotion.
The independent gate lives in profile_verify.py and imports no observer logic.
"""
from __future__ import annotations

import ctypes
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import struct


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n').encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def _read(path):
    path = Path(path)
    if '..' in path.parts or any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('unaliased profile/evidence path required')
    if not path.is_file() or path.stat().st_nlink != 1 or path.stat().st_size > 16*1024*1024:
        raise ValueError('bounded single-link profile/evidence required')
    def pairs(rows):
        result = {}
        for key, value in rows:
            if key in result:
                raise ValueError('duplicate profile key')
            result[key] = value
        return result
    return json.loads(path.read_bytes(), object_pairs_hook=pairs,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite profile value')))


def elf_build_id(raw):
    """Read GNU Build-ID from bounded ELF64 little-endian PT_NOTE records."""
    if len(raw) < 64 or raw[:6] != b'\x7fELF\x02\x01':
        raise ValueError('ELF64 little endian required')
    offset = struct.unpack_from('<Q', raw, 32)[0]
    stride, count = struct.unpack_from('<HH', raw, 54)
    if stride < 56 or count > 1024 or offset+stride*count > len(raw):
        raise ValueError('ELF program headers invalid')
    found = []
    for index in range(count):
        kind, _, start, _, _, length, _, _ = struct.unpack_from('<IIQQQQQQ', raw, offset+index*stride)
        if kind != 4:
            continue
        end = start+length
        if end > len(raw):
            raise ValueError('ELF note outside file')
        cursor = start
        while cursor+12 <= end:
            namesz, descsz, note_type = struct.unpack_from('<III', raw, cursor)
            cursor += 12
            name = raw[cursor:cursor+namesz]
            cursor += (namesz+3)&~3
            desc = raw[cursor:cursor+descsz]
            cursor += (descsz+3)&~3
            if cursor > end:
                raise ValueError('truncated ELF note')
            if name == b'GNU\0' and note_type == 3 and desc:
                found.append(desc.hex())
    if len(set(found)) != 1:
        raise ValueError('unique GNU Build-ID required')
    return found[0]


def detect_environment(repo_root, prepared_identity, cpuinfo_text=None):
    """Live stdlib/file inspection only. Does not call memset or run Gala."""
    from verified_driver.v1.live_chain.session import live_source_snapshot
    from verified_driver.v1.model import content_id
    repo_root = Path(repo_root)
    text = Path('/proc/cpuinfo').read_text() if cpuinfo_text is None else cpuinfo_text
    blocks = [dict(line.split(':', 1) for line in block.splitlines() if ':' in line)
        for block in text.strip().split('\n\n')]
    blocks = [{k.strip():v.strip() for k,v in b.items()} for b in blocks]
    if not blocks or any('flags' not in b for b in blocks):
        raise ValueError('live CPU flags unavailable')
    flags = sorted(set.intersection(*(set(b['flags'].split()) for b in blocks)))
    pinned = prepared_identity['files']
    libc_name = next(n for n in pinned if n.endswith('/libc.so.6'))
    gala_name = next(n for n in pinned if '/gala/' in n and n.endswith('.so'))
    python_name = next(n for n in pinned if n.endswith('/python3.12'))
    observed = {}
    for name in (libc_name, gala_name, python_name):
        raw = Path(name).resolve(strict=True).read_bytes()
        sha = hashlib.sha256(raw).hexdigest()
        if sha != pinned[name]:
            raise ValueError('adaptive binary drift: '+name)
        observed[name] = dict(sha256=sha, build_id=elf_build_id(raw), path=name)
    class DlInfo(ctypes.Structure):
        _fields_ = [('filename',ctypes.c_char_p),('base',ctypes.c_void_p),
                   ('symbol',ctypes.c_char_p),('symbol_address',ctypes.c_void_p)]
    lib = ctypes.CDLL(libc_name)
    address = ctypes.cast(lib.memset, ctypes.c_void_p).value
    dladdr = ctypes.CDLL(None).dladdr
    dladdr.argtypes = [ctypes.c_void_p,ctypes.POINTER(DlInfo)]
    dladdr.restype = ctypes.c_int
    info = DlInfo()
    if not dladdr(address, ctypes.byref(info)) or not info.base or not info.filename:
        raise ValueError('live memset resolver identity unavailable')
    if hashlib.sha256(Path(os.fsdecode(info.filename)).resolve(strict=True).read_bytes()).hexdigest() != pinned[libc_name]:
        raise ValueError('resolved memset belongs to unpinned library')
    sources = live_source_snapshot(repo_root)
    return dict(schema='COMPUTE_METABOLISM_FINGERPRINT_V1', cpu_arch=platform.machine(),
        cpu_vendor=blocks[0].get('vendor_id','UNAVAILABLE'), cpu_model=blocks[0].get('model name','UNAVAILABLE'),
        cpu_family=blocks[0].get('cpu family','UNAVAILABLE'), cpu_model_number=blocks[0].get('model','UNAVAILABLE'),
        cpu_stepping=blocks[0].get('stepping','UNAVAILABLE'), cpu_features=flags, platform=platform.platform(),
        libc=dict(observed[libc_name],memset_elf_entry=address-info.base),
        gala=observed[gala_name], runtime=observed[python_name],
        v1_source_binding=content_id(sources), v1_source_count=len(sources))


def validate_profile(p):
    required = {'profile_id','status','required_cpu_features','environment','libraries','v1_source_binding',
        'allowed_call_origins','entry_points','allowed_path','expected_inputs','memory_contract','expected_result',
        'allowed_state_changes','forbidden_state_changes','verification','derived_from','verified_capability_rank'}
    if p.get('schema') != 'COMPUTE_METABOLISM_EXECUTION_PROFILE_V1' or not required <= set(p):
        raise ValueError('complete execution profile required')
    if not re.fullmatch('[a-z0-9][a-z0-9-]{0,95}',p['profile_id']) or p['status'] not in ('CANDIDATE','VERIFIED','REFUSED'):
        raise ValueError('bounded profile ID/status required')
    if type(p['verified_capability_rank']) is not int or p['verified_capability_rank'] < 0:
        raise ValueError('nonnegative capability rank required')
    if set(p['libraries']) != {'libc','gala','runtime'} or not p['allowed_call_origins']:
        raise ValueError('pinned libraries and call origins required')
    for item in p['libraries'].values():
        if not re.fullmatch('[0-9a-f]{64}',item['sha256']) or not re.fullmatch('[0-9a-f]+',item['build_id']):
            raise ValueError('library SHA-256/Build-ID required')
    if not re.fullmatch('[0-9a-f]{64}',p['v1_source_binding']):
        raise ValueError('profile source binding required')
    if not p['entry_points'] or not p['allowed_path'] or any(type(n) is not int or n < 0 for n in p['entry_points']+p['allowed_path']):
        raise ValueError('explicit ELF entries/path required; whole libc is forbidden')
    if not set(p['entry_points']) <= set(p['allowed_path']):
        raise ValueError('profile entries outside allowed path')
    flags=p['required_cpu_features']
    if (not isinstance(flags,list) or len(flags)!=len(set(flags))
        or any(not isinstance(flag,str) or not re.fullmatch('[a-z0-9_]+',flag) for flag in flags)):
        raise ValueError('explicit unique CPU features required')
    if len(p['allowed_path'])>16384 or len(p['entry_points'])>32:
        raise ValueError('bounded execution paths required')
    for origin in p['allowed_call_origins']:
        if not isinstance(origin,dict) or not origin:
            raise ValueError('observed caller provenance required')
        if p['status']=='VERIFIED' and (set(origin)!={'sha256','elf_address'}
            or not re.fullmatch('[0-9a-f]{64}',origin['sha256'])
            or type(origin['elf_address']) is not int or origin['elf_address']<0):
            raise ValueError('explicit pinned caller origin required')
    if p['status']=='VERIFIED':
        for key,limit in (('lengths',1048576),('fill_values',255)):
            values=p['expected_inputs'].get(key)
            if not isinstance(values,list) or not values or any(type(v) is not int or not 0<=v<=limit for v in values):
                raise ValueError('bounded verified input domain required')
    canonical(p)
    return p


def load_registry(directory, *, repo_root=None):
    directory = Path(directory)
    index = _read(directory/'registry.json')
    if index.get('schema') != 'COMPUTE_METABOLISM_PROFILE_REGISTRY_V1':
        raise ValueError('registry authority schema invalid')
    profiles = []
    for item in index['profiles']:
        name = item['path']
        if Path(name).name != name or not name.endswith('.json'):
            raise ValueError('registry profile namespace invalid')
        p = validate_profile(_read(directory/name))
        if digest(p) != item['manifest_sha256'] or any(x['profile_id']==p['profile_id'] for x in profiles):
            raise ValueError('registry manifest binding/duplicate invalid')
        if p['status']=='VERIFIED' and p['verification'].get('authority') not in (
            'IMPORTED_EXISTING_LIVE_V1','INDEPENDENT_PROFILE_GATE_V1'):
            raise ValueError('independent profile authority required')
        if p['status']=='VERIFIED':
            from .profile_verify import verify_registered_profile
            verify_registered_profile(p,Path(repo_root) if repo_root is not None else Path(__file__).parents[2])
        profiles.append(p)
    return profiles


def compatible(p, fp):
    validate_profile(p)
    return (set(p['required_cpu_features']) <= set(fp['cpu_features'])
        and p['environment'].get('cpu_arch','x86_64') == fp.get('cpu_arch','x86_64')
        and all(p['libraries'][name]['sha256']==fp[name]['sha256']
            and p['libraries'][name]['build_id']==fp[name].get('build_id')
            for name in ('libc','gala','runtime'))
        and fp['libc']['memset_elf_entry'] in p['entry_points']
        and p['v1_source_binding']==fp['v1_source_binding'])


def select_profile(profiles, fingerprint):
    available = [p for p in profiles if p['status']=='VERIFIED' and compatible(p,fingerprint)]
    return min(available,key=lambda p:(-p['verified_capability_rank'],p['profile_id'])) if available else None


def plan_execution(profiles, fingerprint):
    selected = select_profile(profiles,fingerprint)
    return dict(mode='NORMAL' if selected else 'OBSERVATION', certified_state_progress=selected is not None,
        profile_id=selected['profile_id'] if selected else None,
        profile_manifest_sha256=digest(selected) if selected else None, fingerprint_sha256=digest(fingerprint))


def bind_campaign(profile, fingerprint):
    if profile['status']!='VERIFIED' or not compatible(profile,fingerprint):
        raise ValueError('compatible VERIFIED profile required for campaign binding')
    return dict(profile_id=profile['profile_id'],manifest_sha256=digest(profile),
        fingerprint_sha256=digest(fingerprint),fingerprint=fingerprint)


def validate_native_domain(profile, rows):
    """Additional profile constraint before the unchanged V1 independent gate."""
    validate_profile(profile)
    libc=profile['libraries']['libc']['sha256']
    allowed=set(profile['allowed_path']); entries=set(profile['entry_points'])
    for index,row in enumerate(rows):
        if row.get('module_sha256') != libc:
            continue
        if row['elf_address'] not in allowed:
            raise ValueError('execution profile native path outside verified domain')
        if row['elf_address'] in entries:
            origin = None if index==0 else dict(sha256=rows[index-1].get('module_sha256'),
                elf_address=rows[index-1].get('elf_address'))
            if origin not in profile['allowed_call_origins']:
                raise ValueError('execution profile caller outside verified domain')
            registers=row['pre']['gpr']
            if (int(registers['rdx'],16) not in profile['expected_inputs']['lengths']
                or int(registers['rsi'],16)&255 not in profile['expected_inputs']['fill_values']):
                raise ValueError('execution profile input outside verified domain')


def validate_campaign_binding(binding, fingerprint, profiles):
    matches = [p for p in profiles if p['profile_id']==binding['profile_id']]
    if (len(matches)!=1 or matches[0]['status']!='VERIFIED' or digest(matches[0])!=binding['manifest_sha256']
        or digest(binding['fingerprint'])!=binding['fingerprint_sha256']
        or digest(fingerprint)!=binding['fingerprint_sha256'] or not compatible(matches[0],fingerprint)):
        raise ValueError('campaign execution profile/environment drift')
    return matches[0]


def nearest_profile(profiles, fp):
    if not profiles:
        return None
    def score(p):
        same_lib=sum(p['libraries'][n]['sha256']==fp[n]['sha256'] for n in ('libc','gala','runtime'))
        features=len(set(p['required_cpu_features']) & set(fp['cpu_features']))
        return (-same_lib,-features,p['profile_id'])
    return min(profiles,key=score)


def generate_candidate(observation, nearest, directory):
    if (observation.get('mode')!='OBSERVATION' or observation.get('certified_state_progress') is not False
        or observation.get('schema')!='COMPUTE_METABOLISM_OBSERVATION_V1'):
        raise ValueError('non-certified observation required')
    from .profile_verify import inspect_observation
    findings = inspect_observation(observation)
    fp=observation['fingerprint']; entry=observation['entry']
    p = dict(schema='COMPUTE_METABOLISM_EXECUTION_PROFILE_V1',profile_id='candidate-'+digest(observation)[:24],
        status='CANDIDATE',required_cpu_features=fp['cpu_features'],environment=dict(cpu_arch=fp.get('cpu_arch','x86_64')),
        libraries={n:{k:fp[n][k] for k in ('sha256','build_id')} for n in ('libc','gala','runtime')},
        v1_source_binding=fp['v1_source_binding'],allowed_call_origins=[observation['call_origin']],
        entry_points=[entry],allowed_path=sorted({entry,*[row['pc'] for row in observation['trace']]}),
        expected_inputs=dict(observed=observation['input'],domain_status='UNPROVED'),
        memory_contract=dict(reads=findings['reads'],writes=findings['writes'],coverage=findings['effect_coverage']),
        expected_result=observation['observed_result'],allowed_state_changes=findings['changed_registers'],
        forbidden_state_changes=['outside_destination','unmodelled_registers','callee_saved_registers'],
        verified_capability_rank=0,derived_from=None if nearest is None else
            dict(profile_id=nearest['profile_id'],manifest_sha256=digest(nearest)),
        verification=dict(authority=None,tests=[],evidence_sha256=[digest(observation)],independent_verification='PENDING'))
    validate_profile(p)
    difference=dict(nearest_profile=p['derived_from'],new_entry=entry,
        added_path=sorted(set(p['allowed_path'])-set(nearest['allowed_path'] if nearest else [])),
        removed_path=sorted(set(nearest['allowed_path'] if nearest else [])-set(p['allowed_path'])),
        instruction_counts=findings['instruction_counts'],unknown_instructions=findings['unknown_instructions'])
    obligations=dict(schema='COMPUTE_METABOLISM_PROOF_OBLIGATIONS_V1',promotion_allowed=False,
        unknown_instructions=findings['unknown_instructions'],required_proofs=findings['required_proofs'],
        numeric_certification=False,observation_sha256=digest(observation))
    directory=Path(directory)
    if any(parent.is_symlink() for parent in (directory,*directory.parents)):
        raise ValueError('candidate alias forbidden')
    directory.mkdir(parents=True,exist_ok=False)
    output={'observation.raw.json':observation,'candidate-profile.json':p,'difference-report.json':difference,
        'proof-obligations.json':obligations,'generated-positive-fixture.json':dict(
            evidence_role='OBSERVATION',observation=observation,expected='INDEPENDENT_PROOF_REQUIRED'),
        'generated-negative-fixtures.json':dict(mutations=['library_hash','build_id','caller','entry','result',
            'out_of_range_write','unmodelled_instruction','forbidden_register_change','self_issued_pass'])}
    for name,value in output.items():
        with (directory/name).open('xb') as stream:
            stream.write(canonical(value));stream.flush();os.fsync(stream.fileno())
    tests = """# Generated observation cases: no ACCEPT/certification expectation.
import copy,json
from pathlib import Path
import pytest
from compute_metabolism.v0.profile_verify import inspect_observation
@pytest.mark.parametrize('mutation',['result','unmodelled_instruction','out_of_range_write'])
def test_generated_observation_refuses_promotion(mutation):
    raw=json.loads((Path(__file__).with_name('observation.raw.json')).read_bytes())
    changed=copy.deepcopy(raw)
    if mutation=='result': changed['observed_result']['return_value']=-1
    elif mutation=='unmodelled_instruction': changed['trace'][0]['assembly']='UNKNOWN_OBSERVATION_OPCODE'
    else:
        changed['trace'][0]['writes'].append({'address':-1,'size':8})
        with pytest.raises(ValueError,match='bounded actual memory range required'):
            inspect_observation(changed)
        return
    assert not inspect_observation(changed)['promotion_allowed']
"""
    with (directory/'generated-negative-tests.py').open('x',encoding='utf-8',newline='\n') as stream:
        stream.write(tests)
    return p


def promote_candidate(candidate_directory, registry_directory):
    """Explicit separate gate invocation; no candidate self-issued status/PASS."""
    from .profile_verify import verify_promotion
    verdict=verify_promotion(Path(candidate_directory))
    if verdict['promotion_allowed'] is not True:
        raise ValueError('independent promotion refused: '+', '.join(verdict['required_proofs']))
    # The gate must return a fully proved manifest, never the generator's claim.
    promoted=validate_profile(verdict['verified_manifest'])
    registry_directory=Path(registry_directory)
    existing=load_registry(registry_directory)
    if any(p['profile_id']==promoted['profile_id'] for p in existing):
        raise ValueError('profile authority already registered')
    # An explicit promotion is a source-authority transaction, never invoked by
    # discovery. Preserve each old index and fail closed on partial registration.
    from .campaign import _safe_path,_exclusive_raw,_fsync_directory
    import tempfile
    registry_directory=_safe_path(registry_directory)
    lock=registry_directory/'.promotion.authority'
    fd=os.open(lock,os.O_RDWR|os.O_CREAT|getattr(os,'O_NOFOLLOW',0),0o600)
    try:
        if os.name!='posix':
            raise ValueError('durable profile promotion requires POSIX lock/fsync')
        import fcntl
        fcntl.flock(fd,fcntl.LOCK_EX)
        current=load_registry(registry_directory)
        if any(p['profile_id']==promoted['profile_id'] for p in current):
            raise ValueError('profile authority already registered')
        old_raw=(registry_directory/'registry.json').read_bytes()
        index=_read(registry_directory/'registry.json')
        name=promoted['profile_id']+'.json'
        history=registry_directory/'history';history.mkdir(exist_ok=True)
        _fsync_directory(registry_directory)
        old_name=history/(hashlib.sha256(old_raw).hexdigest()+'.raw')
        if not old_name.exists():_exclusive_raw(old_name,old_raw)
        _exclusive_raw(registry_directory/name,canonical(promoted))
        _exclusive_raw(registry_directory/(promoted['profile_id']+'.verification.json'),canonical(verdict))
        index['profiles'].append(dict(path=name,manifest_sha256=digest(promoted)))
        tempfd,tmp=tempfile.mkstemp(prefix='.registry.',suffix='.pending',dir=registry_directory)
        with os.fdopen(tempfd,'wb') as out:
            out.write(canonical(index));out.flush();os.fsync(out.fileno())
        os.replace(tmp,registry_directory/'registry.json');_fsync_directory(registry_directory)
        return promoted
    finally:
        os.close(fd)


def main(argv=None):
    """Discover/select or explicitly register independently rechecked authority."""
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='operation',required=True)
    discover=sub.add_parser('discover')
    discover.add_argument('--repo-root',type=Path,required=True)
    discover.add_argument('--prepared',type=Path,required=True)
    discover.add_argument('--prepared-sha256',required=True)
    discover.add_argument('--output',type=Path,required=True)
    promote=sub.add_parser('promote')
    promote.add_argument('--candidate-directory',type=Path,required=True)
    promote.add_argument('--registry-directory',type=Path,required=True)
    args=parser.parse_args(argv)
    if args.operation=='promote':
        result=promote_candidate(args.candidate_directory,args.registry_directory)
    else:
        from . import run_v1
        from .campaign import _frozen_read,_exclusive_raw
        prepared=run_v1._prepared(_read(args.prepared),args.prepared_sha256)
        _frozen_read(args.prepared,args.prepared_sha256)
        fp=detect_environment(args.repo_root,prepared)
        registry=args.repo_root/'compute_metabolism/v0/execution_profiles'
        profiles=load_registry(registry,repo_root=args.repo_root)
        result=dict(fingerprint=fp,decision=plan_execution(profiles,fp),
            registry_sha256=hashlib.sha256((registry/'registry.json').read_bytes()).hexdigest())
        _exclusive_raw(args.output,canonical(result))
    print(canonical(result).decode(),end='')
    return 0


if __name__=='__main__':raise SystemExit(main())
