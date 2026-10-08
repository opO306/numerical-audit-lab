"""One persistent inferior, authenticated-by-ownership anonymous-pipe control."""
from dataclasses import asdict
import hashlib, os, signal, subprocess, sys, time
from pathlib import Path
from verified_driver.v1.model import canonical_bytes, content_id, digest_bytes, chain_genesis, check_hash
from runtime_trace.regular_nstep.acquire import source_pinset, harness_source, validate_n
from .protocol import BarrierEvent, ResumeToken, read_frame, write_frame
from .checkpoint import no_alias, verify_checkpoint, sealed_write

def live_source_snapshot(root):
    root=Path(root); result=source_pinset(root)
    for base in ('verified_driver/v1/live_chain','verified_driver/v1'):
        for p in (root/base).glob('*.py'): result[p.relative_to(root).as_posix()]=digest_bytes(p.read_bytes())
    for relative in ('lab/v2_bound.py','independent_checker/oracle.py','runtime_trace/regular_nstep/raw_check.py',
      'runtime_trace/regular_nstep/machine_check.py','runtime_trace/regular_2step/checker.py','runtime_trace/regular_2step/form_oracle.py'):
        result[relative]=digest_bytes((root/relative).read_bytes())
    return result

class LiveGalaSession:
    def __init__(self,repo_root:Path,run_root:Path,requested_steps:int,ledger:Path):
        self.repo_root=no_alias(repo_root); self.run_root=no_alias(run_root)
        self.requested_steps=validate_n(requested_steps); self.ledger=Path(ledger)
        self.genesis=chain_genesis(self.repo_root,self.requested_steps)
        if not self.ledger.is_file(): raise ValueError('existing shared ledger required')
        self.session_id=os.urandom(32).hex(); self.process=None; self.event=None; self.metadata=None
        self.master_trace=self.run_root/'trace.jsonl'; self._binding=None; self._used=set(); self._phase='NEW'
        self._timeout=120.; self._fds=[]; self._log=None
    def _command(self):
        return ['gdb','-q','-nx','-batch','-x',str(self.repo_root/'verified_driver/v1/live_chain/gdb_live.py'),
          '--args',sys.executable,str(self.repo_root/'verified_driver/v1/live_chain/harness.py')]
    def _launch(self,command,env,fds):
        from verified_driver.v1.containment import ContainedLiveProcess
        return ContainedLiveProcess(command,cwd=self.repo_root,env=env,pass_fds=fds,
          stdout=self._log,stderr=subprocess.STDOUT,receipt=self.run_root/'containment.json')
    def start(self):
        if self._phase!='NEW': raise ValueError('live session already started')
        self.run_root.mkdir(parents=True,exist_ok=False)
        self.sources=live_source_snapshot(self.repo_root)
        event_r,event_w=os.pipe(); command_r,command_w=os.pipe()
        self._event_fd=event_r; self._command_fd=command_w; self._fds=[event_r,command_w]
        self._log=(self.run_root/'gdb.log').open('xb')
        env=dict(os.environ,LD_BIND_NOW='1',RT_OUTPUT=str(self.run_root),RTN_STEPS=str(self.requested_steps),
          RT2_CASE='known',CT_ANTECEDENT_LABEL='known',V1_SESSION=self.session_id,
          V1_PREDECESSOR=self.genesis.content_hash,V1_EVENT_FD=str(event_w),V1_COMMAND_FD=str(command_r),
          PYTHONPATH=str(self.repo_root))
        try:
            self.process=self._launch(self._command(),env,(event_w,command_r))
        finally: os.close(event_w); os.close(command_r)
        self._phase='RUNNING'
        try: return self._receive(1,self.genesis.content_hash)
        except Exception: self.terminate('initial live event failed'); raise
    def _receive(self,sequence,pred):
        record=read_frame(self._event_fd,self._timeout)
        if record.get('type')!='BARRIER': raise ValueError('expected certification barrier: '+str(record.get('reason')))
        event=BarrierEvent(**record['event'])
        if event.session_id!=self.session_id or event.barrier_seq!=sequence or event.predecessor_id!=pred or event.requested_steps!=self.requested_steps:
            raise ValueError('stale/foreign/skipped live event')
        if self.event is not None and event.process_identity!=self.event.process_identity: raise ValueError('inferior process changed')
        if 'metadata_path' in record:
            p=no_alias(self.run_root/record['metadata_path'])
            if not p.is_relative_to(self.run_root): raise ValueError('metadata path escape')
            raw=p.read_bytes()
            if digest_bytes(raw)!=record['metadata_sha256']: raise ValueError('metadata bytes differ from private event')
            from verified_driver.v1.model import strict_json
            metadata=strict_json(raw)
        else: metadata=record['metadata']
        self.event=event; self.metadata=metadata; self._binding=None; self._phase='PAUSED'
        return event
    def is_paused_at(self,event):
        if self._phase!='PAUSED' or self.event!=event or self.process is None or self.process.poll() is not None: return False
        try:
            write_frame(self._command_fd,{'type':'PING'})
            response=read_frame(self._event_fd,self._timeout)
            return response=={'type':'PAUSED','event_id':content_id(event)}
        except Exception: self.terminate('pause proof unavailable'); return False
    def bind_checkpoint(self,checkpoint_id,checkpoint_dir,published_state_id,predecessor_generation):
        if self._phase!='PAUSED' or self._binding is not None or not self.is_paused_at(self.event): raise ValueError('unique proven paused barrier required')
        check_hash(published_state_id)
        if predecessor_generation!=self.event.completed_step-1: raise ValueError('generation bind mismatch')
        verify_checkpoint(checkpoint_dir,checkpoint_id,expected_event=self.event)
        binding=dict(session_id=self.session_id,barrier_seq=self.event.barrier_seq,
          predecessor_generation=predecessor_generation,candidate_generation=self.event.completed_step,
          checkpoint_id=checkpoint_id,state_id=published_state_id)
        write_frame(self._command_fd,{'type':'BIND','checkpoint_id':checkpoint_id,'checkpoint_dir':str(checkpoint_dir),'state_id':published_state_id})
        response=read_frame(self._event_fd,self._timeout)
        if response!={'type':'BOUND','checkpoint_id':checkpoint_id}: self.terminate('checkpoint bind failed'); raise ValueError('GDB checkpoint binding mismatch')
        self._binding=binding
    def resume(self,token:ResumeToken):
        if self._phase!='PAUSED' or self.event.barrier_kind!='NEXT_STEP_ENTRY' or self._binding is None: raise ValueError('no numerical resume authority')
        if not isinstance(token,ResumeToken): raise ValueError('resume token required')
        actual=asdict(token); nonce=actual.pop('nonce')
        if actual!=self._binding or nonce in self._used: raise ValueError('stale/duplicate/foreign token')
        if not self.is_paused_at(self.event): self.terminate('inferior not provably paused'); raise ValueError('inferior pause lost')
        self._used.add(nonce); sequence=self.event.barrier_seq+1
        write_frame(self._command_fd,{'type':'RESUME','token':asdict(token)})
        self._phase='RUNNING'
        try: return self._receive(sequence,token.state_id)
        except Exception: self.terminate('resumed acquisition failed'); raise
    def finish(self,token:ResumeToken|None=None):
        if token is not None or self._phase!='PAUSED' or self.event.barrier_kind!='FINAL_TERMINAL': raise ValueError('final terminal finish only; no body token')
        if not self.is_paused_at(self.event): self.terminate('terminal pause lost'); raise ValueError('terminal pause unavailable')
        write_frame(self._command_fd,{'type':'FINISH'})
        try:
            result=read_frame(self._event_fd,self._timeout)
            if result.get('type')!='FINISHED' or result.get('normal_exit') is not True: raise ValueError('normal original exit unavailable')
            if self.process.wait(timeout=10)!=0: raise ValueError('live collector exit failed')
            self._phase='FINISHED'; return result
        except Exception: self.terminate('terminal finish failed'); raise
    def terminate(self,reason):
        if self.process is not None and hasattr(self.process,'terminate_group'):
            self.process.terminate_group(reason)
        elif self.process is not None and self.process.poll() is None:
            try: os.killpg(self.process.pid,signal.SIGKILL)
            except ProcessLookupError: pass
            self.process.wait(timeout=10)
        for fd in self._fds:
            try: os.close(fd)
            except OSError: pass
        self._fds=[]
        if self._log is not None: self._log.close()
        if self._phase!='FINISHED': self._phase='STOPPED'
        if self.run_root.is_dir() and not (self.run_root/'session-stop.json').exists():
            sealed_write(self.run_root/'session-stop.json',canonical_bytes({'phase':self._phase,'reason':reason,'session_id':self.session_id}))
