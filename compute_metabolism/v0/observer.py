"""Isolated, bounded libc samples. This module grants no numerical authority.

The only inferior is a synthetic ctypes harness. It never imports Gala or V1,
and its memory window is an observation, not proof of absence of side effects.
The caller supplies a hash-bound fingerprint and an exclusive artifact path.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import selectors
import shutil
import signal
import subprocess
import sys
import tempfile
import time

from .adaptive import canonical, elf_build_id


HARNESS = r'''
import ctypes,json,os,signal
from pathlib import Path
config=json.loads(Path(os.environ['CM_OBSERVER_CONFIG']).read_bytes())
lib=ctypes.CDLL(config['fingerprint']['libc']['path'])
fn=lib.memset
fn.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_size_t]
fn.restype=ctypes.c_void_p
buf=ctypes.create_string_buffer(b'\xa5'*(config['length']+64),config['length']+64)
destination=ctypes.addressof(buf)+32
marker=dict(entry=ctypes.cast(fn,ctypes.c_void_p).value,destination=destination,
    window_address=ctypes.addressof(buf),window_size=config['length']+64,pid=os.getpid())
with Path(config['marker']).open('xb') as stream:
    stream.write((json.dumps(marker,sort_keys=True,separators=(',',':'))+'\n').encode())
os.kill(os.getpid(),signal.SIGSTOP)
result=fn(destination,config['value'],config['length'])
assert result==destination
'''


def _safe_path(path):
    path = Path(path).absolute()
    if '..' in path.parts or any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('observer path alias forbidden')
    return path


def _json_read(path, limit=16*1024*1024):
    path = _safe_path(path)
    stat = path.stat()
    if not path.is_file() or stat.st_nlink != 1 or stat.st_size > limit:
        raise ValueError('bounded single-link observation document required')
    def pairs(items):
        out = {}
        for key, value in items:
            if key in out:
                raise ValueError('duplicate observation key')
            out[key] = value
        return out
    return json.loads(path.read_bytes(), object_pairs_hook=pairs,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite observation value')))


def _identity(path, expected, kind):
    path = Path(path).resolve(strict=True)
    if not path.is_file() or path.stat().st_size > 32*1024*1024:
        raise ValueError('bounded '+kind+' ELF required')
    raw = path.read_bytes()
    got = dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest(), build_id=elf_build_id(raw))
    if got['sha256'] != expected.get('sha256') or got['build_id'] != expected.get('build_id'):
        raise ValueError(kind+' SHA-256/Build-ID differs from fingerprint')
    return got


def _bounds(length, value, max_steps, timeout_seconds, max_output_bytes):
    for name, number, low, high in (
        ('length',length,0,4096),('value',value,0,255),('max_steps',max_steps,1,4096),
        ('timeout_seconds',timeout_seconds,1,60),('max_output_bytes',max_output_bytes,65536,16*1024*1024)):
        if type(number) is not int or not low <= number <= high:
            raise ValueError('bounded integer '+name+' required')


def _run(argv, env, timeout, output_cap):
    """Drain bounded pipes and kill the whole isolated process group on stop."""
    process = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, env=env, start_new_session=True)
    streams = selectors.DefaultSelector()
    for stream, name in ((process.stdout,'stdout'),(process.stderr,'stderr')):
        os.set_blocking(stream.fileno(), False)
        streams.register(stream, selectors.EVENT_READ, name)
    chunks = {'stdout':bytearray(), 'stderr':bytearray()}
    reason = None
    deadline = time.monotonic()+timeout
    try:
        while streams.get_map():
            if time.monotonic() >= deadline:
                reason = 'STOP_TIMEOUT'
                break
            for key, _ in streams.select(min(.1, max(0,deadline-time.monotonic()))):
                part = os.read(key.fileobj.fileno(), 65536)
                if not part:
                    streams.unregister(key.fileobj)
                elif sum(map(len,chunks.values()))+len(part) > output_cap:
                    reason = 'STOP_OUTPUT_LIMIT'
                    break
                else:
                    chunks[key.data].extend(part)
            if reason:
                break
        if reason:
            os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=5)
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=5)
        streams.close()
        process.stdout.close()
        process.stderr.close()
    return dict(returncode=process.returncode, stop_reason=reason,
        **{name:bytes(raw).decode('utf-8',errors='replace') for name,raw in chunks.items()})


def observe_memset(fingerprint, output_path, *, python_path=None, gdb_path=None,
        length=64, value=0, max_steps=2048, timeout_seconds=30,
        max_output_bytes=8*1024*1024):
    """Observe one real pinned libc invocation; return only OBSERVATION data.

    Run this command under system_guard to apply the campaign's cgroup budget.
    This function itself adds process isolation and finite trace/output limits.
    It neither reads nor writes a V1 certified store, ledger, CURRENT or session.
    """
    _bounds(length,value,max_steps,timeout_seconds,max_output_bytes)
    out = _safe_path(output_path)
    if out.name != 'observation.raw.json':
        raise ValueError('exclusive observation.raw.json artifact required')
    if out.exists():
        raise FileExistsError(str(out))
    if not out.parent.is_dir():
        raise ValueError('existing isolated observation artifact directory required')
    if fingerprint.get('schema') != 'COMPUTE_METABOLISM_FINGERPRINT_V1':
        raise ValueError('live fingerprint schema required')
    fp_raw = canonical(fingerprint)
    if len(fp_raw) > 32768:
        raise ValueError('bounded fingerprint document required')
    fingerprint = json.loads(fp_raw)
    libc = _identity(fingerprint['libc']['path'],fingerprint['libc'],'libc')
    executable = Path(python_path or fingerprint['runtime']['path']).resolve(strict=True)
    runtime = _identity(executable,fingerprint['runtime'],'runtime')
    debugger = Path(gdb_path or shutil.which('gdb') or '/usr/bin/gdb').resolve(strict=True)
    if not debugger.is_file():
        raise ValueError('prepared GDB executable required')
    gdb_script = Path(__file__).with_name('gdb_observer.py')
    base = dict(schema='COMPUTE_METABOLISM_OBSERVATION_V1',mode='OBSERVATION',
        certified_state_progress=False,promotion_allowed=False,fingerprint=fingerprint,
        fingerprint_sha256=hashlib.sha256(canonical(fingerprint)).hexdigest(),
        library=libc,runtime=runtime,trace=[],entry=None,
        call_origin=dict(kind='SYNTHETIC_PYTHON_CTYPES',authorized_gala_call=False,
            harness_sha256=hashlib.sha256(HARNESS.encode()).hexdigest()),
        input=dict(length=length,value=value),observed_result={},
        effect_coverage=dict(complete=False,outside_window='UNKNOWN',
            reads='UNKNOWN_EXCEPT_EXPLICIT_DECODED_OPERANDS',
            same_value_writes='UNKNOWN_EXCEPT_EXPLICIT_DECODED_OPERANDS',
            state='UNTRACED_SYSTEM_AND_MICROARCHITECTURAL_STATE'),
        terminal=dict(status='STOP_ERROR',complete=False,inferior_exit_code=None),
        limits=dict(max_steps=max_steps,max_output_bytes=max_output_bytes,
            timeout_seconds=timeout_seconds,max_length=4096))
    with tempfile.TemporaryDirectory(prefix='.memset-observation-',dir=out.parent) as scratch:
        scratch = Path(scratch)
        config = dict(fingerprint=fingerprint,length=length,value=value,max_steps=max_steps,
            timeout_seconds=timeout_seconds,max_output_bytes=max_output_bytes,
            marker=str(scratch/'marker.json'),result=str(scratch/'result.json'),base=base)
        config_path = scratch/'config.json'
        config_path.write_bytes(canonical(config))
        # Environment excludes loader injection and all inherited V1/store paths.
        env = {key:os.environ[key] for key in ('PATH','LANG','LC_ALL','HOME') if key in os.environ}
        env.update(CM_OBSERVER_CONFIG=str(config_path),PYTHONDONTWRITEBYTECODE='1',
            OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
        argv = [str(debugger),'-q','-nx','-batch','-iex','set auto-load off',
            '-iex','set debuginfod enabled off','-x',str(gdb_script),
            '--args',str(executable),'-B','-c',HARNESS]
        process = _run(argv,env,timeout_seconds+2, min(max_output_bytes,1024*1024))
        result = _json_read(scratch/'result.json',max_output_bytes) if (scratch/'result.json').exists() else base
        result['process'] = process
        if process['stop_reason'] or process['returncode'] != 0:
            result['terminal'].update(status=process['stop_reason'] or 'STOP_GDB_ERROR',complete=False)
        if 'memset_elf_entry' in fingerprint['libc'] and result['entry'] != fingerprint['libc']['memset_elf_entry']:
            result['terminal'].update(status='STOP_ENTRY_DRIFT',complete=False)
        raw = canonical(result)
        if len(raw) > max_output_bytes:
            result['trace'] = []
            result['terminal'].update(status='STOP_OUTPUT_LIMIT',complete=False)
            result['process'] = {k:v for k,v in process.items() if k not in ('stdout','stderr')}
            raw = canonical(result)
        with out.open('xb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fingerprint',required=True,type=Path)
    parser.add_argument('--fingerprint-sha256',required=True)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--python',type=Path)
    parser.add_argument('--gdb',type=Path)
    parser.add_argument('--length',type=int,default=64)
    parser.add_argument('--value',type=int,default=0)
    parser.add_argument('--max-steps',type=int,default=2048)
    parser.add_argument('--timeout-seconds',type=int,default=30)
    parser.add_argument('--max-output-bytes',type=int,default=8*1024*1024)
    args = parser.parse_args(argv)
    fp = _json_read(args.fingerprint)
    if hashlib.sha256(canonical(fp)).hexdigest() != args.fingerprint_sha256:
        raise ValueError('fingerprint canonical hash binding invalid')
    result = observe_memset(fp,args.output,python_path=args.python,gdb_path=args.gdb,
        length=args.length,value=args.value,max_steps=args.max_steps,
        timeout_seconds=args.timeout_seconds,max_output_bytes=args.max_output_bytes)
    print(json.dumps(dict(mode='OBSERVATION',status=result['terminal']['status'],
        certified_state_progress=False,output=str(args.output)),sort_keys=True))
    return 0 if result['terminal']['status']=='OBSERVED_RETURN' else 2


if __name__ == '__main__':
    raise SystemExit(main())
