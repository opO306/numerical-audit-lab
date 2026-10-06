"""Linux subreaper kills the full GDB/inferior group on controller pipe EOF."""
import argparse, ctypes, os, select, signal, subprocess, time
from pathlib import Path
from verified_driver.v1.model import canonical_bytes, digest_bytes
from .checkpoint import sealed_write

def members(pgid):
    found=[]
    for p in Path('/proc').iterdir():
        if not p.name.isdigit(): continue
        try:
            fields=(p/'stat').read_text().rsplit(')',1)[1].split()
            if int(fields[2])==pgid: found.append(int(p.name))
        except (OSError,ValueError,IndexError): pass
    return sorted(found)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--watchdog',type=int,required=True)
    parser.add_argument('--controller',type=int,required=True)
    parser.add_argument('--receipt',type=Path,required=True)
    parser.add_argument('--pass-fd',type=int,action='append',default=[])
    args,command=parser.parse_known_args()
    if command and command[0]=='--': command.pop(0)
    if not command: raise ValueError('target command required')
    libc=ctypes.CDLL(None,use_errno=True)
    if libc.prctl(36,1,0,0,0)!=0: raise OSError(ctypes.get_errno(),'subreaper unavailable')
    # Authority FD belongs only to the supervisor, never to the target.
    os.set_inheritable(args.watchdog,False)
    process=subprocess.Popen(command,pass_fds=tuple(args.pass_fd),start_new_session=True)
    for fd in args.pass_fd: os.close(fd)
    reason='TARGET_EXIT'; status=None
    try:
        while True:
            ready,_,_=select.select([args.watchdog],[],[],.01)
            if ready:
                if os.read(args.watchdog,1)==b'': reason='CONTROLLER_PIPE_EOF'; break
                reason='INVALID_WATCHDOG_DATA'; break
            status=os.waitid(os.P_PID,process.pid,os.WEXITED|os.WNOHANG|os.WNOWAIT)
            if status is not None: break
    finally:
        before=members(process.pid)
        try: os.killpg(process.pid,signal.SIGKILL)
        except ProcessLookupError: pass
        # The unreaped root holds its PID until group termination; adopted
        # descendants are reaped here, so group receipts include no zombies.
        deadline=time.monotonic()+5
        while True:
            try:
                while os.waitpid(-1,os.WNOHANG)[0]: pass
            except ChildProcessError: pass
            remaining=members(process.pid)
            if not remaining or time.monotonic()>=deadline: break
            time.sleep(.01)
        process.returncode=(status.si_status if status.si_code==os.CLD_EXITED else -status.si_status) if status else -signal.SIGKILL
        cgroup=Path('/proc/self/cgroup').read_text()
        receipt={'schema':'V1_PROCESS_GROUP_CONTAINMENT_V1','controller_pid':args.controller,
                 'supervisor_pid':os.getpid(),'target_pid':process.pid,'target_pgid':process.pid,
                 'command_sha256':digest_bytes(canonical_bytes(command)),
                 'cgroup':cgroup,'reason':reason,'target_return_code':process.returncode,
                 'group_pids_before_stop':before,'group_remaining_pids':remaining,
                 'body_start_markers':sorted(p.name for p in args.receipt.parent.glob('body-start-*.json')),
                 'test_only_next_body_marker_present':(args.receipt.parent/'next-body').exists(),
                 'watchdog_inherited_by_target':False,'subreaper':True}
        sealed_write(args.receipt,canonical_bytes(receipt))
        os.close(args.watchdog)
    if remaining: return 125
    return process.returncode if process.returncode>=0 else 128-process.returncode

if __name__=='__main__': raise SystemExit(main())
