"""Separate Windows checker host: suspended child -> bounded Job Object -> resume."""
import argparse
import ctypes as C
from ctypes import wintypes as W
import json
from pathlib import Path
import platform
import subprocess
import sys
import time


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--receipt', type=Path, required=True)
    p.add_argument('--seconds', type=int, default=600)
    p.add_argument('--memory', type=int, default=4294967296)
    p.add_argument('command', nargs=argparse.REMAINDER)
    a = p.parse_args()
    if not 0 < a.seconds <= 600 or not 0 < a.memory <= 4294967296 or a.receipt.exists():
        raise ValueError('bounded exclusive Windows job contract')
    command = a.command[1:] if a.command[0] == '--' else a.command
    k = C.WinDLL('kernel32', use_last_error=True)
    H, S, D = W.HANDLE, C.c_size_t, W.DWORD
    class Basic(C.Structure):
        _fields_ = [('process_time', C.c_int64), ('job_time', C.c_int64), ('flags', D),
            ('min_working', S), ('max_working', S), ('active', D), ('affinity', S), ('priority', D), ('scheduling', D)]
    class IO(C.Structure):
        _fields_ = [(name, C.c_uint64) for name in ('reads', 'writes', 'others', 'read_bytes', 'write_bytes', 'other_bytes')]
    class Extended(C.Structure):
        _fields_ = [('basic', Basic), ('io', IO), ('process_memory', S), ('job_memory', S),
            ('peak_process', S), ('peak_job', S)]
    class Startup(C.Structure):
        _fields_ = [('cb', D), ('reserved', W.LPWSTR), ('desktop', W.LPWSTR), ('title', W.LPWSTR),
            ('x', D), ('y', D), ('xsize', D), ('ysize', D), ('xcount', D), ('ycount', D),
            ('fill', D), ('flags', D), ('show', W.WORD), ('reserved2_size', W.WORD),
            ('reserved2', C.POINTER(W.BYTE)), ('stdin', H), ('stdout', H), ('stderr', H)]
    class Process(C.Structure):
        _fields_ = [('process', H), ('thread', H), ('pid', D), ('tid', D)]
    def bind(name, result, arguments):
        f = getattr(k, name)
        f.restype, f.argtypes = result, arguments
        return f
    create_job = bind('CreateJobObjectW', H, [C.c_void_p, W.LPCWSTR])
    set_info = bind('SetInformationJobObject', W.BOOL, [H, C.c_int, C.c_void_p, D])
    query = bind('QueryInformationJobObject', W.BOOL, [H, C.c_int, C.c_void_p, D, C.c_void_p])
    assign = bind('AssignProcessToJobObject', W.BOOL, [H, H])
    create_process = bind('CreateProcessW', W.BOOL, [W.LPCWSTR, W.LPWSTR, C.c_void_p, C.c_void_p,
        W.BOOL, D, C.c_void_p, W.LPCWSTR, C.POINTER(Startup), C.POINTER(Process)])
    resume = bind('ResumeThread', D, [H])
    wait = bind('WaitForSingleObject', D, [H, D])
    terminate = bind('TerminateJobObject', W.BOOL, [H, W.UINT])
    terminate_process = bind('TerminateProcess', W.BOOL, [H, W.UINT])
    exit_code = bind('GetExitCodeProcess', W.BOOL, [H, C.POINTER(D)])
    close = bind('CloseHandle', W.BOOL, [H])
    def ensure(ok):
        if not ok:
            raise C.WinError(C.get_last_error())
    limits, start, process = Extended(), Startup(), Process()
    limits.basic.flags = 0x200 | 0x2000  # job committed-memory limit + kill on close
    limits.job_memory = a.memory
    start.cb = C.sizeof(start)
    job = create_job(None, None)
    ensure(job)
    began = time.perf_counter()
    reason, code, observed = None, D(0), Extended()
    try:
        ensure(set_info(job, 9, C.byref(limits), C.sizeof(limits)))
        ensure(query(job, 9, C.byref(observed), C.sizeof(observed), None))
        ensure(observed.job_memory == a.memory and observed.basic.flags & 0x200)
        line = C.create_unicode_buffer(subprocess.list2cmdline(command))
        ensure(create_process(None, line, None, None, False, 4 | 0x08000000,
            None, str(a.receipt.parent), C.byref(start), C.byref(process)))
        if not assign(job, process.process):
            terminate_process(process.process, 125)
            raise C.WinError(C.get_last_error())
        ensure(resume(process.thread) != 0xffffffff)
        waited = wait(process.process, a.seconds * 1000)
        if waited == 0x102:
            reason = 'wall ceiling'
            ensure(terminate(job, 124))
            wait(process.process, 5000)
        else:
            ensure(waited == 0)
        ensure(exit_code(process.process, C.byref(code)))
        ensure(query(job, 9, C.byref(observed), C.sizeof(observed), None))
        if observed.peak_job > a.memory:
            reason = 'API peak counter exceeds configured memory ceiling'
    except Exception as exc:
        reason = str(exc)
        if process.process:
            terminate(job, 125)
        code.value = 125
    finally:
        receipt = {'schema': 'windows-nstep-checker-job-v1', 'host': platform.node(),
            'platform': platform.platform(), 'python': platform.python_version(),
            'command': command, 'pid': process.pid, 'wall_seconds': time.perf_counter() - began,
            'memory_metric': 'Windows Job Object committed memory; distinct from Linux cgroup/RSS',
            'memory_limit': a.memory, 'enforced_job_memory': observed.job_memory,
            'peak_job_committed_bytes': observed.peak_job, 'exit_code': code.value,
            'resource_failure': reason, 'verdict': 'EXECUTED' if code.value == 0 and not reason else 'REFUSED',
            'requested_complete': False}
        a.receipt.write_text(json.dumps(receipt, sort_keys=True) + '\n', encoding='utf-8')
        for handle in (process.thread, process.process, job):
            if handle:
                close(handle)
    print(json.dumps(receipt, sort_keys=True))
    return 0 if receipt['verdict'] == 'EXECUTED' else 2


if __name__ == '__main__':
    raise SystemExit(main())
