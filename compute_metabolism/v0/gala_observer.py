"""One original Gala CALL observation, terminated before certified progress.

Launch is guarded by the caller's system unit and single upper-ledger attempt.
This function does not create a store, a campaign, a profile or acceptance.
"""
import hashlib
import json
import os
from pathlib import Path
import selectors
import signal
import subprocess
import struct
import tempfile
import time
from .adaptive import canonical
from .observer import _json_read,_safe_path
from .system_guard import INNER_PYTHON

# Fixed worst-case allocation covers scratch AND retained copies: config2*512KiB,
# raw3*1MiB, writes2*512KiB, births4*64KiB, states2*1MiB, launch7MiB =14.25MiB.
# Launch includes JSON escaping of the1MiB pipe cap. Harness output
# keeps its existing separate1MiB reservation. No shared ceiling is increased.
RESERVATION_BYTES=16*1024*1024
WRITER_CEILING=671088640
CONFIG_LIMIT=524288
BIRTH_LIMIT=65536
WRITES_LIMIT=524288
STATE_LIMIT=1048576
LAUNCH_LIMIT=7*1024*1024


def validate_reservation(reservation):
    if (type(reservation) is not dict or set(reservation)!={'path','maximum_bytes','reserved_bytes'}
        or type(reservation['path']) is not str or not Path(reservation['path']).is_absolute()
        or reservation['path']!=os.environ.get('RTN_QUOTA_FILE')
        or type(reservation['maximum_bytes']) is not int
        or not RESERVATION_BYTES<=reservation['maximum_bytes']<=WRITER_CEILING
        or str(reservation['maximum_bytes'])!=os.environ.get('RTN_QUOTA_BYTES')
        or type(reservation['reserved_bytes']) is not int or reservation['reserved_bytes']!=RESERVATION_BYTES):
        raise ValueError('fixed actual shared writer reservation required')
    _safe_path(reservation['path'])
    return reservation


def writer_binding():
    raw=os.environ.get('RTN_QUOTA_BYTES','')
    if not raw.isascii() or not raw.isdecimal() or str(int(raw))!=raw:
        raise ValueError('strict actual shared writer maximum required')
    return validate_reservation(dict(path=os.environ.get('RTN_QUOTA_FILE',''),
        maximum_bytes=int(raw),reserved_bytes=RESERVATION_BYTES))


def write_bounded(path,raw,maximum):
    if type(raw) is not bytes or len(raw)>maximum:
        raise ValueError('bounded reserved observer artifact required')
    path=_safe_path(path)
    with path.open('xb') as stream:
        stream.write(raw);stream.flush();os.fsync(stream.fileno())


def retain_raw(source,target,maximum):
    """Retain actual bytes before parsing; oversized evidence is explicit prefix."""
    source=_safe_path(source)
    if not source.exists():return dict(present=False,actual_size=None,retained_size=0,truncated=False)
    info=source.stat()
    if not source.is_file() or info.st_nlink!=1:
        raise ValueError('unaliased single-link raw input required')
    with source.open('rb') as stream:raw=stream.read(maximum)
    write_bounded(target,raw,maximum)
    return dict(present=True,actual_size=info.st_size,retained_size=len(raw),
        truncated=info.st_size>maximum,retained_sha256=hashlib.sha256(raw).hexdigest(),
        original_path=str(source),retained_path=str(target))


def _identity(path,expected,kind):
    path=Path(path).resolve(strict=True)
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=expected['sha256']:
        raise ValueError('pinned '+kind+' identity drift')


def build_config(root,scratch,fingerprint,gdb_sha256,source_snapshot):
    root=Path(root);scratch=Path(scratch)
    return dict(mode='OBSERVATION',certified_state_progress=False,
        fingerprint=fingerprint,source_snapshot=source_snapshot,gdb_sha256=gdb_sha256,
        python_executable=INNER_PYTHON,
        result=str(scratch/'raw.json'),birth=str(scratch/'owned-birth.json'),
        candidate_birth=str(scratch/'candidate-birth.json'),
        harness_output=str(scratch/'harness-output'),max_native_steps=13,
        stop_at='FIRST_APPROVED_MEMSET_RETURN',timeout_seconds=100,
        max_output_bytes=1024*1024,writer_reservation=writer_binding())


def launch_spec(root,config,config_path):
    root=Path(root)
    validate_reservation(config['writer_reservation'])
    if config.get('python_executable')!=INNER_PYTHON:
        raise ValueError('fixed prepared Python executable required')
    env={key:os.environ[key] for key in ('PATH','LANG','LC_ALL','HOME','RTN_QUOTA_FILE','RTN_QUOTA_BYTES') if key in os.environ}
    env.update(CM_GALA_OBSERVER_CONFIG=str(config_path),PYTHONDONTWRITEBYTECODE='1',
        PYTHONPATH=str(root),RT_OUTPUT=config['harness_output'],RTN_STEPS='1',
        RT2_CASE='known',CT_ANTECEDENT_LABEL='known',LD_BIND_NOW='1',
        OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
    args=['/usr/bin/gdb','-q','-nx','-batch','-iex','set auto-load off',
        '-iex','set debuginfod enabled off','-x',str(root/'compute_metabolism/v0/gdb_gala_observer.py'),
        '--args',config['python_executable'],'-B',
        str(root/'verified_driver/v1/live_chain/harness.py')]
    if len(canonical(dict(command=args,environment=env)))>262144:
        raise ValueError('bounded actual observer command/environment required')
    return args,env


def elf_load_bias(raw,mappings):
    """Derive the unique bias from PT_LOAD vaddrs, including RELRO splits."""
    if raw[:7]!=b'\x7fELF\x02\x01\x01' or len(raw)<64:raise ValueError('ELF64 little-endian required')
    offset=struct.unpack_from('<Q',raw,32)[0];width,count=struct.unpack_from('<HH',raw,54)
    if width!=56 or not 0<count<=128 or offset+width*count>len(raw):raise ValueError('bounded ELF program headers')
    loads=[]
    for i in range(count):
        kind,flags,file_offset,vaddr,_,filesz,memsz,_=struct.unpack_from('<IIQQQQQQ',raw,offset+i*width)
        if kind==1:
            if filesz>memsz or file_offset+filesz>len(raw) or file_offset%4096!=vaddr%4096:
                raise ValueError('valid file-backed ELF load segment required')
            loads.append((flags,file_offset&~4095,vaddr&~4095,(file_offset+filesz+4095)&~4095))
    if not loads or not mappings:raise ValueError('actual file-backed mappings required')
    common=None
    for m in mappings:
        choices=set()
        if m['end']<=m['start'] or m['offset']%4096:raise ValueError('page-aligned nonempty mapping')
        for flags,file_start,virtual_start,file_end in loads:
            if (file_start<=m['offset'] and m['offset']+m['end']-m['start']<=file_end
                and ('x' not in m['perms'] or flags&1) and ('w' not in m['perms'] or flags&2)):
                choices.add(m['start']-(virtual_start+m['offset']-file_start))
        common=choices if common is None else common&choices
    if len(common)!=1:raise ValueError('mapped-but-invalid ELF load bias')
    return common.pop()


def bind_owned_birth(config,gdb_pid,proc_root=Path('/proc')):
    """Parent reads birth, ancestry and cgroup independently while paused."""
    candidate=Path(config['candidate_birth'])
    if not candidate.is_file():return None
    if Path(config['birth']).exists():return _json_read(config['birth'])
    pid=_json_read(candidate)['pid']
    if type(pid) is not int or pid<=0:raise ValueError('candidate inferior PID invalid')
    def stat(p):
        tail=(proc_root/str(p)/'stat').read_text().rsplit(')',1)[1].split()
        return int(tail[1]),int(tail[19])
    parent,start=stat(pid);walk=parent
    for _ in range(64):
        if walk==gdb_pid:break
        if walk<=1:raise ValueError('candidate inferior is not GDB-owned')
        walk=stat(walk)[0]
    else:raise ValueError('bounded ancestry proof failed')
    if ((proc_root/str(pid)/'cgroup').read_bytes()!=(proc_root/'self/cgroup').read_bytes()
        or hashlib.sha256((proc_root/str(pid)/'exe').resolve(strict=True).read_bytes()).hexdigest()
            !=config['fingerprint']['runtime']['sha256']):
        raise ValueError('independent inferior cgroup/runtime drift')
    if stat(pid)!=(parent,start):raise ValueError('inferior birth changed during parent observation')
    birth=dict(pid=pid,linux_boot_id=(proc_root/'sys/kernel/random/boot_id').read_text().strip(),
        proc_stat_start_time_ticks=start)
    write_bounded(config['birth'],canonical(birth),BIRTH_LIMIT)
    return birth


def _run(argv,env,timeout,output_cap):
    config=_json_read(env['CM_GALA_OBSERVER_CONFIG'])
    process=subprocess.Popen(argv,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,env=env,start_new_session=True)
    streams=selectors.DefaultSelector();chunks={'stdout':bytearray(),'stderr':bytearray()}
    reason=None;diagnostic=None;deadline=time.monotonic()+timeout
    for stream,name in ((process.stdout,'stdout'),(process.stderr,'stderr')):
        os.set_blocking(stream.fileno(),False);streams.register(stream,selectors.EVENT_READ,name)
    try:
        while streams.get_map():
            bind_owned_birth(config,process.pid)
            if time.monotonic()>=deadline:reason='STOP_TIMEOUT';break
            for key,_ in streams.select(min(.05,max(0,deadline-time.monotonic()))):
                part=os.read(key.fileobj.fileno(),65536)
                if not part:streams.unregister(key.fileobj)
                elif sum(map(len,chunks.values()))+len(part)>output_cap:
                    remaining=output_cap-sum(map(len,chunks.values()))
                    chunks[key.data].extend(part[:remaining])
                    reason='STOP_OUTPUT_LIMIT';break
                else:chunks[key.data].extend(part)
            if reason:break
        if reason:os.killpg(process.pid,signal.SIGKILL)
        process.wait(timeout=5)
    except Exception as exc:
        reason='STOP_PARENT_ACQUISITION'
        diagnostic=dict(stage='independent-parent-acquisition',exception_type=type(exc).__name__,exception_message=str(exc)[:4096])
    finally:
        if process.poll() is None:
            os.killpg(process.pid,signal.SIGKILL);process.wait(timeout=5)
        streams.close();process.stdout.close();process.stderr.close()
    return dict(returncode=process.returncode,stop_reason=reason,diagnostic=diagnostic,
        **{name:bytes(raw).decode('utf-8',errors='replace') for name,raw in chunks.items()})


def observe_gala(fingerprint,output_path,repo_root,*,gdb_sha256,source_snapshot):
    out=_safe_path(output_path);root=_safe_path(repo_root)
    if out.exists():raise FileExistsError(str(out))
    if out.name!='gala-observation.raw.json' or not out.parent.is_dir():
        raise ValueError('exclusive Gala observation namespace required')
    reservation=writer_binding()
    from runtime_trace.regular_nstep.resources import reserve_writer
    reserve_writer(RESERVATION_BYTES)
    # Reserve before identity/acquisition. Reject prior attempt artifacts before
    # launch so a collision cannot lose a newly acquired raw observation.
    names=('gala-observer-config.json','gala-gdb-result.raw','gala-owned-birth.raw',
        'gala-candidate-birth.raw','gala-launch.json','enabled-write-observations.json','state-acquisitions.json')
    if any((out.parent/name).exists() for name in names):raise FileExistsError('prior Gala observation artifacts')
    for name in ('runtime','libc','gala'):
        _identity(fingerprint[name]['path'],fingerprint[name],name)
    _identity('/usr/bin/gdb',dict(sha256=gdb_sha256),'GDB')
    with tempfile.TemporaryDirectory(prefix='.gala-observation-',dir=out.parent) as folder:
        scratch=Path(folder)
        config=build_config(root,scratch,fingerprint,gdb_sha256,source_snapshot)
        _identity(config['python_executable'],fingerprint['runtime'],'prepared Python executable')
        Path(config['harness_output']).mkdir()
        path=scratch/'config.json';config_raw=canonical(config)
        write_bounded(path,config_raw,CONFIG_LIMIT)
        write_bounded(out.parent/'gala-observer-config.json',config_raw,CONFIG_LIMIT)
        args,env=launch_spec(root,config,path)
        try:process=_run(args,env,config['timeout_seconds']+5,1024*1024)
        except Exception as exc:
            process=dict(returncode=None,stop_reason='STOP_PARENT_ACQUISITION',stdout='',stderr='',
                diagnostic=dict(stage='GDB-launch',exception_type=type(exc).__name__,exception_message=str(exc)[:4096]))
        # Never parse scratch receipts before retaining bounded actual bytes.
        raw_result=retain_raw(config['result'],out.parent/'gala-gdb-result.raw',config['max_output_bytes'])
        owned=retain_raw(config['birth'],out.parent/'gala-owned-birth.raw',BIRTH_LIMIT)
        candidate=retain_raw(config['candidate_birth'],out.parent/'gala-candidate-birth.raw',BIRTH_LIMIT)
        writes=scratch/'enabled-write-observations.json'
        write_evidence=retain_raw(writes,out.parent/'enabled-write-observations.json',WRITES_LIMIT)
        state_evidence=retain_raw(scratch/'state-acquisitions.json',
            out.parent/'state-acquisitions.json',STATE_LIMIT)
        try:
            if not raw_result['present']:raise ValueError('GDB did not preserve its raw observation')
            if raw_result['truncated']:raise ValueError('raw result exceeded fixed artifact bound')
            result=_json_read(out.parent/'gala-gdb-result.raw',config['max_output_bytes'])
            if type(result) is not dict:raise ValueError('raw observation mapping required')
        except Exception as exc:
            result=dict(diagnostic=dict(stage='raw-result-parse',exception_type=type(exc).__name__,exception_message=str(exc)[:4096]))
        birth=None
        try:
            if owned['present']:
                if owned['truncated']:raise ValueError('birth exceeded fixed bound')
                birth=_json_read(out.parent/'gala-owned-birth.raw',BIRTH_LIMIT)
        except Exception as exc:
            result['birth_diagnostic']=dict(exception_type=type(exc).__name__,exception_message=str(exc)[:4096])
        result_raw=canonical(result)
        if len(result_raw)>config['max_output_bytes']:
            result=dict(diagnostic=dict(stage='raw-result-parse',exception_type='ArtifactBound',
                exception_message='canonical result with diagnostics exceeded fixed bound; actual raw retained'))
            result_raw=canonical(result)
        launch=dict(process=process,owned_process_identity=birth,config=config,
            config_sha256=hashlib.sha256(config_raw).hexdigest(),command=args,environment=env,
            original_config_path=str(path),retained_config_path=str(out.parent/'gala-observer-config.json'),
            writer_reservation=reservation,raw_result=raw_result,owned_birth=owned,candidate_birth=candidate,
            enabled_write_evidence=write_evidence,state_acquisition_evidence=state_evidence,
            recorder_source_sha256=hashlib.sha256((root/'compute_metabolism/v0/gdb_gala_observer.py').read_bytes()).hexdigest())
        if (process['returncode']!=0 or process['stop_reason'] or 'diagnostic' in result
            or 'birth_diagnostic' in result or write_evidence.get('truncated') or candidate.get('truncated')
            or not state_evidence['present'] or state_evidence.get('truncated')):
            launch['outcome']='OBSERVATION_FAILED'
        else:launch['outcome']='OBSERVED_UNCERTIFIED'
        write_bounded(out,result_raw,config['max_output_bytes'])
        write_bounded(out.parent/'gala-launch.json',canonical(launch),LAUNCH_LIMIT)
        return result
