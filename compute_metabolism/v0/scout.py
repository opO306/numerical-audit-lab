"""Finite TEST_ONLY CPU scout orchestration; never issues run authority."""
from copy import deepcopy
import hashlib,json,os,resource,stat,struct,platform
from pathlib import Path
from .adaptive import canonical,digest,detect_environment,elf_build_id
from . import campaign,source_epoch
from .observer import _run

LIMIT=2*1024*1024
BASE=0x7fa08aef6000
NOP_PC=BASE+0xc90
XGETBV_CODE='31c90f01d048c1e2204809d0c3'

def sha(raw):return hashlib.sha256(raw).hexdigest()

def canonical_path(path):
    p=Path(path).absolute()
    if '..' in p.parts or any(x.is_symlink() for x in (p,*p.parents)) or p.resolve(strict=False)!=p:
        raise ValueError('canonical unaliased scout path required')
    return p

def scout_output(policy,path):
    p=canonical_path(path);directory=canonical_path(policy['execution_directory'])
    if directory.resolve(strict=True) not in p.parents:
        raise ValueError('scout output outside approved execution directory')
    return p

def save(path,value):
    raw=canonical(value)
    if len(raw)>LIMIT:raise ValueError('bounded scout artifact required')
    path=canonical_path(path)
    with path.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())

def fixture():
    """Deterministic isolated FXRSTOR64/FXSAVE64, NOP2, exit; no Gala."""
    raw=bytearray(8192);raw[:16]=b'\x7fELF\x02\x01\x01'+bytes(9)
    struct.pack_into('<HHIQQQIHHHHHH',raw,16,2,62,1,BASE+0xc80,64,0,0,64,56,2,0,0,0)
    struct.pack_into('<IIQQQQQQ',raw,64,1,7,0,BASE,BASE,len(raw),len(raw),4096)
    struct.pack_into('<IIQQQQQQ',raw,120,4,4,0x200,BASE+0x200,BASE+0x200,36,36,4)
    struct.pack_into('<III',raw,0x200,4,20,3);raw[0x20c:0x210]=b'GNU\0'
    code=bytes.fromhex('480fae0d78030000480fae05700100009090b83c00000031ff0f05')
    raw[0xc80:0xc80+len(code)]=code
    fx=bytearray(512)
    struct.pack_into('<HHBBHQQII',fx,0,0x37f,0,0xff,0,0x456,0x7fa08aef6c93,0x1234fedcba98,0x1f80,0xffff)
    for i in range(8):fx[32+16*i:42+16*i]=(0x8000000000000000+i).to_bytes(8,'little')+b'\xff\x3f'
    for i in range(16):fx[160+16*i:176+16*i]=bytes((i*17+j)%256 for j in range(16))
    raw[0x1000:0x1200]=fx
    raw[0x210:0x224]=hashlib.sha256(code+fx).digest()[:20]
    return bytes(raw)

def policy(root,epoch,binaries,directory,*,uid,gid,cpus,expected_entry=None,historical_candidates=()):
    root=Path(root);sources,binding=source_epoch.validate_epoch(epoch,root)
    bins=deepcopy(binaries)
    ds=Path(directory).stat();directory_identity=[ds.st_dev,ds.st_ino,ds.st_uid,ds.st_gid,stat.S_IMODE(ds.st_mode)]
    for item in bins.values():
        p=Path(item['path']).resolve(strict=True);s=p.stat()
        item.update(resolved_path=str(p),file_identity=[s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns])
    return dict(schema='CPU_SCOUT_POLICY_V1',scope='TEST_ONLY',source_epoch=deepcopy(epoch),
        source_binding=binding,gate_source_snapshot=campaign.gate_source_snapshot(root,epoch),
        binaries=bins,execution_directory=str(Path(directory).absolute()),uid=uid,gid=gid,
        directory_identity=directory_identity,cpus=list(cpus),memory_bytes=4294967296,max_wall_seconds=30,max_path_steps=128,
        max_output_bytes=LIMIT,expected_entry=expected_entry,gdb_version='15.1',
        registry_sha256=sha((root/'compute_metabolism/v0/execution_profiles/registry.json').read_bytes()),
        historical_candidates=deepcopy(list(historical_candidates)))

def bundle(policy,environment,probe,*,path_observation=None,unknown=()):
    return dict(schema='CPU_SCOUT_BUNDLE_V1',scope='TEST_ONLY',policy_sha256=digest(policy),
        environment=deepcopy(environment),probe=deepcopy(probe),path_observation=deepcopy(path_observation),
        unknown=list(unknown),certified_state_progress=False,numerical_certification=False,
        profile_promotion=False,body_allowed=False)

def environment(root,prepared,gdb):
    """Fresh file/resolver/kernel inspection; no Gala import or calculation."""
    fp=detect_environment(root,prepared)
    process=_run([str(gdb),'--version'],{'PATH':'/usr/bin:/bin','LC_ALL':'C.UTF-8'},3,65536)
    if process['returncode']!=0 or process['stop_reason']:raise ValueError('GDB version unavailable')
    cgroup_raw=Path('/proc/self/cgroup').read_text()
    rows=[v[3:] for v in cgroup_raw.splitlines() if v.startswith('0::')]
    if len(rows)!=1 or not rows[0].startswith('/') or '..' in Path(rows[0]).parts:raise ValueError('cgroup location unavailable')
    cgroup=Path('/sys/fs/cgroup')/rows[0].lstrip('/')
    records={'raw':cgroup_raw}
    # Retain all visible ancestor limits; inherited unlimited is not a future
    # formal cgroup PASS. Probe hard limit is separately sampled by GDB.
    records['ancestors']=[]
    for parent in (cgroup,*[x for x in cgroup.parents if x==Path('/sys/fs/cgroup') or Path('/sys/fs/cgroup') in x.parents]):
        row={'path':str(parent)}
        for name in ['cpu.max','memory.max','memory.swap.max','cpuset.cpus.effective']:
            file=parent/name;row[name]=file.read_text() if file.exists() else None
        records['ancestors'].append(row)
    return dict(fingerprint=fp,kernel=dict(release=platform.release(),
        boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
        cpu_flags=fp['cpu_features']),cgroup=records,gdb_version=process['stdout'])

def cache_key(policy,env,probe):
    """No CPU-model-name-only key; bind complete observed CPU/OS envelope."""
    return digest(dict(policy=policy,environment=env,cpu_samples=probe.get('cpu_samples'),
        architecture=probe.get('architecture'),gdb_version=probe.get('gdb_version'),
        cpuid_code_hex=probe.get('cpuid_code_hex'),xgetbv_code_hex=probe.get('xgetbv_code_hex'),
        register_types={n:{k:v for k,v in row.items() if k!='raw_hex'} for n,row in probe.get('fields',{}).items()},
        affinity=probe.get('affinity'),rlimit_as=probe.get('rlimit_as'),uid=probe.get('uid'),gid=probe.get('gid')))

def reuse_plan(old,policy,env,root,*,require_path=True,live_probe=None):
    from .scout_check import verify
    verdict=verify(old,policy,root,require_path=require_path)
    prior=old.get('probe') or {}
    if live_probe is None:return dict(reuse_probe=False,recheck=['fresh CPU/OS/type/envelope header required'],body_allowed=False,status='SCOUT_UNKNOWN')
    current=live_probe
    from .scout_check import state,cpu
    try:
        if current.get('schema')!='CPU_SCOUT_GDB_RAW_V1' or current.get('Gala') is not False or current.get('test_only') is not True or current.get('cwd')!=policy['execution_directory']:raise ValueError('live header envelope')
        if type(current.get('uid')) is not int or type(current.get('gid')) is not int or current['uid']!=policy['uid'] or current['gid']!=policy['gid']:raise ValueError('live header identity')
        state(current['fields'],current['state']);cpu(current['cpu_samples'],policy)
        if current.get('unknown'):raise ValueError('live header UNKNOWN')
    except (KeyError,ValueError,TypeError):
        return dict(reuse_probe=False,recheck=['fresh full probe required'],body_allowed=False,status='SCOUT_UNKNOWN')
    same=bool(prior) and cache_key(policy,env,current)==cache_key(policy,old.get('environment'),prior)
    return dict(reuse_probe=verdict['status']==('SCOUT_READY' if require_path else 'STATE_TEST_PASS') and same,
        recheck=['files','source','directory_identity','CPU_per_target','XCR0','kernel','resources','checker','cached_raw_evidence'],
        body_allowed=False,status=verdict['status'])

def probe(policy,root,out,*,mode='full'):
    """One bounded GDB invocation; no automatic retry."""
    from .scout_check import preflight
    out=scout_output(policy,out)
    preflight(policy,root)
    if os.getuid()!=policy['uid'] or os.getgid()!=policy['gid']:raise ValueError('scout execution user mismatch')
    if sorted(os.sched_getaffinity(0))!=policy['cpus'] or list(resource.getrlimit(resource.RLIMIT_AS))!=[policy['memory_bytes']]*2:
        raise ValueError('scout actual CPU/memory envelope mismatch')
    if Path.cwd()!=Path(policy['execution_directory']):raise ValueError('actual scout working directory mismatch')
    out=Path(out);out.mkdir(mode=0o700,exist_ok=False)
    exe=out/'fixture';exe.write_bytes(fixture());exe.chmod(0o700)
    config={'policy':policy,'root':str(root),'fixture':str(exe),'output':str(out/'raw.json'),'mode':mode}
    save(out/'config.json',config)
    env={'PATH':'/usr/bin:/bin','LC_ALL':'C.UTF-8','HOME':str(out),'PYTHONDONTWRITEBYTECODE':'1',
        'CPU_SCOUT_CONFIG':str(out/'config.json'),'OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1'}
    worker=Path(__file__).with_name('scout_gdb.py')
    run=_run([policy['binaries']['gdb']['path'],'-q','-nx','-batch','-iex','set auto-load off',
        '-iex','set debuginfod enabled off','-x',str(worker)],env,policy['max_wall_seconds'],LIMIT)
    save(out/'launch.json',run)
    if run['returncode'] or run['stop_reason'] or not (out/'raw.json').exists():
        return None,dict(stage='GDB',reason=run['stop_reason'] or 'probe incomplete')
    raw=(out/'raw.json').read_bytes()
    if len(raw)>LIMIT:raise ValueError('scout raw output limit')
    result=json.loads(raw)
    preflight(policy,root) # file/source substitution after launch remains refusal
    return result,None

def run(policy,root,prepared,output,*,reuse=None):
    """Produce raw dossier then hand it to a separate checker."""
    from .scout_check import verify,preflight
    from . import adaptive
    root=Path(root);output=scout_output(policy,output)
    if Path.cwd()!=Path(policy['execution_directory']):raise ValueError('scout launch cwd differs from approved directory')
    output.mkdir(mode=0o700,exist_ok=False)
    save(output/'policy.json',policy)
    env=None;raw=None;path=None;unknown=[];failure=None;reused=False
    try:
        preflight(policy,root)
        env=environment(root,prepared,policy['binaries']['gdb']['path'])
        if policy['expected_entry'] is not None and env['fingerprint']['libc']['memset_elf_entry']!=policy['expected_entry']:
            raise ValueError('CPU resolved execution path mismatch before probe')
        if reuse is not None:
            # A fresh limited header-only GDB read checks CPUID/XCR0 and types;
            # any cache discrepancy falls back to a fresh full probe once.
            header,error=probe(policy,root,output/'live-header',mode='header')
            if error:unknown.append(error['reason'])
            elif header.get('unknown'):unknown.extend(header['unknown'])
            else:
                plan=reuse_plan(reuse,policy,env,root,live_probe=header)
                save(output/'reuse-plan.json',plan)
                if plan['reuse_probe']:
                    raw=deepcopy(reuse['probe']);path=deepcopy(reuse['path_observation']);reused=True
        if not reused and not unknown:
            raw,error=probe(policy,root,output/'state-probe')
            if error:unknown.append(error['reason'])
            elif raw.get('unknown'):unknown.extend(raw['unknown'])
            else:
                from .observer import observe_memset
                path=observe_memset(env['fingerprint'],output/'observation.raw.json',
                    python_path=policy['binaries']['runtime']['path'],gdb_path=policy['binaries']['gdb']['path'],
                    length=16,value=0,max_steps=policy['max_path_steps'],timeout_seconds=policy['max_wall_seconds'],
                    max_output_bytes=LIMIT)
        preflight(policy,root)
    except (ValueError,OSError,KeyError,TypeError) as exc:
        failure={'type':type(exc).__name__,'reason':str(exc)}
    document=bundle(policy,env,raw,path_observation=path,unknown=unknown)
    if failure:document['failure']=failure
    document['cache_reused']=reused
    save(output/'scout-bundle.json',document)
    verdict=verify(document,policy,root)
    save(output/'independent-verdict.json',verdict)
    save(output/'scout-proof-obligations.json',dict(schema='CPU_SCOUT_OBLIGATIONS_V1',
        scout_status=verdict['status'],unknown=verdict['unknown'],refusal_reasons=verdict['reasons'],
        unscouted_xstate_bits=[x['os']['unscouted_enabled_bits'] for x in verdict['cpu']],
        required=['ACTUAL_GALA_ORIGIN','INDEPENDENT_PROFILE_VERIFIED','FORMAL_CGROUP_RECHECK','UNCHANGED_CAMPAIGN_AND_V1_GATES'],
        numerical_certification=False,profile_promotion=False,body_allowed=False))
    save(output/'scout-candidate.json',dict(schema='CPU_SCOUT_CANDIDATE_V1',
        status='REFUSED' if verdict['status']=='SCOUT_REFUSED' else 'CANDIDATE',
        evidence_sha256=digest(document),policy_sha256=digest(policy),
        missing=verdict['unknown'],failures=verdict['reasons'],body_allowed=False))
    save(output/'generated-scout-mutation-fixtures.json',dict(schema='CPU_SCOUT_MUTATION_PLAN_V1',
        expected='BLOCK_BODY',mutations=['source_binding','library_hash','ELF_role','owner','memset_entry',
        'x87_type','register_width','raw_byte','missing_register','XCR0','CPUID','GDB','NOP_bytes','self_issued_READY'],
        promotion_allowed=False))
    if verdict['status']=='SCOUT_READY':
        profiles=adaptive.load_registry(root/'compute_metabolism/v0/execution_profiles',repo_root=root)
        nearest=adaptive.nearest_profile(profiles,env['fingerprint'])
        selected=adaptive.select_profile(profiles,env['fingerprint'])
        comparison=dict(verified_profile_match=selected is not None,
            nearest_profile=None if nearest is None else nearest['profile_id'],
            actual_entry=env['fingerprint']['libc']['memset_elf_entry'],
            body_allowed=False,requires_actual_Gala_origin=True,requires_independent_profile_gate=True)
        save(output/'profile-comparison.json',comparison)
        if selected is None:
            candidate=adaptive.generate_candidate(path,nearest,output/'candidate')
            comparison['new_candidate_manifest_sha256']=digest(candidate)
        comparison['profile_differences']=[dict(profile_id=p['profile_id'],status=p['status'],
            source_match=p['v1_source_binding']==env['fingerprint']['v1_source_binding'],
            entry_match=path['entry'] in p['entry_points'],
            added_path=sorted({row['pc'] for row in path['trace']}-set(p['allowed_path'])),
            removed_path=sorted(set(p['allowed_path'])-{row['pc'] for row in path['trace']})) for p in profiles]
        comparison['historical_candidates']=[]
        for ref in policy['historical_candidates']:
            old=adaptive.validate_profile(json.loads(Path(ref['path']).read_bytes()))
            comparison['historical_candidates'].append(dict(path=ref['path'],sha256=ref['sha256'],profile_id=old['profile_id'],
                status=old['status'],source_match=old['v1_source_binding']==env['fingerprint']['v1_source_binding'],
                entry_match=path['entry'] in old['entry_points'],
                added_path=sorted({row['pc'] for row in path['trace']}-set(old['allowed_path']))))
        save(output/'profile-differences.json',comparison)
    return dict(status=verdict['status'],body_allowed=False,certified_state_progress=False,
        numerical_certification=False,profile_promotion=False,output=str(output),cache_reused=reused)
