"""Linux subreaper terminates its owned subtree on controller pipe EOF."""
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

def process_table():
    table={}
    for p in Path('/proc').iterdir():
        if not p.name.isdigit(): continue
        try:
            fields=(p/'stat').read_text().rsplit(')',1)[1].split()
            table[int(p.name)]=(int(fields[1]),int(fields[2]),int(fields[19]))
        except (OSError,ValueError,IndexError): pass
    return table

def owned(table):
    # This dedicated subreaper launches exactly one target. Its descendants,
    # including adopted children in different sessions/groups, are owned.
    parents={os.getpid()};found={}
    while True:
        added={pid:info for pid,info in table.items() if info[0] in parents and pid not in parents}
        if not added: return found
        found.update(added);parents.update(added)

def signal_identity(pid,info,sig):
    # A pidfd and the recorded start time prevent PID reuse from redirecting
    # a signal to an unrelated process.
    try:
        fd=os.pidfd_open(pid)
    except ProcessLookupError: return
    try:
        current=process_table().get(pid)
        if current is not None and current[2]==info[2]:signal.pidfd_send_signal(fd,sig)
    except ProcessLookupError: pass
    finally:os.close(fd)

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
    reason='TARGET_EXIT'; status=None;tracked={}
    try:
        while True:
            tracked.update(owned(process_table()))
            ready,_,_=select.select([args.watchdog],[],[],.01)
            if ready:
                if os.read(args.watchdog,1)==b'': reason='CONTROLLER_PIPE_EOF'; break
                reason='INVALID_WATCHDOG_DATA'; break
            status=os.waitid(os.P_PID,process.pid,os.WEXITED|os.WNOHANG|os.WNOWAIT)
            if status is not None: break
    finally:
        before=members(process.pid)
        # Freeze the entire owned tree before killing its debugger. A separate
        # inferior group must not run while GDB termination is in progress.
        frozen=set();descendants=set();deadline=time.monotonic()+5
        while True:
            live=owned(process_table());tracked.update(live);descendants.update(live)
            additions=[(pid,info) for pid,info in live.items() if (pid,info[2]) not in frozen]
            for pid,info in additions:
                signal_identity(pid,info,signal.SIGSTOP);frozen.add((pid,info[2]))
            if not additions:break
            if time.monotonic()>=deadline:raise TimeoutError('owned subtree freeze incomplete')
        # Re-scan adopted descendants during cleanup; group membership alone
        # is insufficient because GDB creates its inferior in a distinct PGID.
        deadline=time.monotonic()+5
        while True:
            live=owned(process_table());tracked.update(live);descendants.update(live)
            for pid,info in live.items():signal_identity(pid,info,signal.SIGSTOP)
            for pid,info in reversed(list(live.items())):signal_identity(pid,info,signal.SIGKILL)
            try:
                while os.waitpid(-1,os.WNOHANG)[0]: pass
            except ChildProcessError: pass
            remaining=members(process.pid)
            table=process_table()
            descendant_remaining=sorted(pid for pid,info in tracked.items() if pid in table and table[pid][2]==info[2])
            untracked=owned(table)
            if not remaining and not descendant_remaining and not untracked:break
            if time.monotonic()>=deadline:break
            time.sleep(.01)
        process.returncode=(status.si_status if status.si_code==os.CLD_EXITED else -status.si_status) if status else -signal.SIGKILL
        cgroup=Path('/proc/self/cgroup').read_text()
        receipt={'schema':'V1_PROCESS_GROUP_CONTAINMENT_V1','controller_pid':args.controller,
                 'supervisor_pid':os.getpid(),'target_pid':process.pid,'target_pgid':process.pid,
                 'command_sha256':digest_bytes(canonical_bytes(command)),
                 'cgroup':cgroup,'reason':reason,'target_return_code':process.returncode,
                 'group_pids_before_stop':before,'group_remaining_pids':remaining,
                 'descendant_pids_before_stop':sorted(descendants),
                 'tracked_process_identities':{str(pid):{'ppid':info[0],'pgid':info[1],'start_time_ticks':info[2]} for pid,info in tracked.items()},
                 'descendant_remaining_pids':descendant_remaining,
                 'owned_subtree_verified':not remaining and not descendant_remaining and not untracked,
                 'body_start_markers':sorted(p.name for p in args.receipt.parent.glob('body-start-*.json')),
                 'test_only_next_body_marker_present':(args.receipt.parent/'next-body').exists(),
                 'watchdog_inherited_by_target':False,'subreaper':True}
        sealed_write(args.receipt,canonical_bytes(receipt))
        os.close(args.watchdog)
    if remaining or descendant_remaining or untracked: return 125
    return process.returncode if process.returncode>=0 else 128-process.returncode

if __name__=='__main__': raise SystemExit(main())
