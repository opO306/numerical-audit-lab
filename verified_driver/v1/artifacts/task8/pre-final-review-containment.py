"""Controller-owned watchdog pipe; an independent supervisor owns the group."""
from pathlib import Path
import os, subprocess, sys
from .model import canonical_bytes
from .live_chain.checkpoint import no_alias

class ContainedLiveProcess:
    def __init__(self,command,*,cwd,env,pass_fds,stdout,stderr,receipt):
        if not command or any(type(value) is not str for value in command):
            raise ValueError('explicit argument vector required')
        self.receipt=no_alias(receipt)
        read_fd,write_fd=os.pipe()
        self._watchdog=write_fd
        args=[sys.executable,'-m','verified_driver.v1.live_chain.supervisor',
              '--watchdog',str(read_fd),'--controller',str(os.getpid()),
              '--receipt',str(self.receipt)]
        for fd in pass_fds: args.extend(['--pass-fd',str(fd)])
        args.extend(['--',*command])
        try:
            self._process=subprocess.Popen(args,cwd=cwd,env=env,
                 pass_fds=(read_fd,*pass_fds),stdout=stdout,stderr=stderr,start_new_session=True)
        except BaseException:
            os.close(write_fd); self._watchdog=None; raise
        finally: os.close(read_fd)

    @property
    def pid(self): return self._process.pid
    def poll(self): return self._process.poll()
    def wait(self,timeout=None): return self._process.wait(timeout=timeout)
    def terminate_group(self,reason):
        # A live supervisor receives EOF and kills/reaps the entire target group.
        if self._watchdog is not None:
            os.close(self._watchdog); self._watchdog=None
        result=self._process.wait(timeout=10)
        if not self.receipt.is_file(): raise ValueError('group termination receipt unavailable: '+reason)
        from .model import strict_json
        receipt=strict_json(self.receipt.read_bytes())
        if receipt.get('group_remaining_pids')!=[]: raise ValueError('contained group remains alive')
        return result
