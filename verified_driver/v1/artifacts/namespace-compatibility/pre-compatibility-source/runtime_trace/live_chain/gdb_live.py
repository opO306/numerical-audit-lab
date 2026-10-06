"""Persistent original inferior; IPC barrier precedes every next body."""
def drive_barriers(backend,n):
    backend.prepare()
    for k in range(1,n+1):
        backend.body(k)
        if k<n: backend.handoff(k)
        else: backend.terminal()
        kind='NEXT_STEP_ENTRY' if k<n else 'FINAL_TERMINAL'
        event=backend.barrier(k,kind)
        backend.wait(event,kind)
    backend.finish()

def main():
    import ast, fcntl, hashlib, os, sys, time
    from pathlib import Path
    import gdb
    root=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(root))
    from dataclasses import asdict
    from verified_driver.v1.model import canonical_bytes, content_id, digest_bytes, strict_json
    from runtime_trace.regular_nstep.acquire import harness_source, write, validate_n
    from runtime_trace.live_chain.session import live_source_snapshot
    from runtime_trace.live_chain.protocol import BarrierEvent, ResumeToken, read_frame, write_frame
    from runtime_trace.live_chain.checkpoint import chain_hash, verify_checkpoint
    out=Path(os.environ['RT_OUTPUT']); n=validate_n(int(os.environ['RTN_STEPS']))
    command_fd=int(os.environ['V1_COMMAND_FD']); event_fd=int(os.environ['V1_EVENT_FD'])
    # These authority FDs must never be inherited by the inferior itself.
    for fd in (command_fd,event_fd): fcntl.fcntl(fd,fcntl.F_SETFD,fcntl.FD_CLOEXEC)
    path=root/'runtime_trace/regular_nstep/gdb_acquire.py'; nodes=[]
    for node in ast.parse(path.read_text()).body:
        if isinstance(node,ast.For) and isinstance(node.target,ast.Name) and node.target.id=='command': break
        nodes.append(node)
    ns={'__file__':str(path),'__name__':'runtime_trace.live_chain._reviewed_collector_definitions'}
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path),'exec'),ns)
    Capture=ns['Capture']; base=ns['base']; Refused=ns['Refused']
    for command in ('set pagination off','set confirm off','set breakpoint pending on','set disassembly-flavor att',
        'set print symbol-filename on','set debuginfod enabled off','set non-stop off','set startup-with-shell off'):
        gdb.execute(command)
    class Backend:
        def __init__(self):
            self.capture=Capture(); self.pred=os.environ['V1_PREDECESSOR']; self.binding=None; self.used=set()
            self.sources=live_source_snapshot(root); self.capture.started=time.perf_counter()
        def prepare(self):
            self.init=gdb.Breakpoint(base['INIT_SYMBOL'],internal=True); self.step=gdb.Breakpoint(base['STEP_SYMBOL'],internal=True)
            gdb.execute('run',to_string=True); self.init.enabled=False
            self.capture.region('init',base['INIT_SYMBOL']); gdb.execute('continue',to_string=True)
        def body(self,k):
            write(out/f'body-start-{k}.json',{'step':k,'pid':gdb.selected_inferior().pid,'predecessor_id':self.pred,
              'session_id':os.environ['V1_SESSION'],'trace_start_seq':self.capture.count})
            self.capture.region(f'step{k}',base['STEP_SYMBOL'])
        def handoff(self,k):
            c=self.capture; c.corridor_label=f'caller{k}-{k+1}'
            c.caller_corridor(c.regions[-1]['entry_pc']); c.corridor['occurrence']=c.corridor_label; c.corridors.append(c.corridor)
        def terminal(self): self.capture.terminal_corridor()
        def entry(self):
            c=self.capture; context=c.context(); rsp=int(context['gpr']['rsp'],16)
            mem=lambda p: bytes(gdb.selected_inferior().read_memory(p,8))
            pointers={'q':int(context['gpr']['rcx'],16),'full_v':int(context['gpr']['r8'],16),
              'latent':int(context['gpr']['r9'],16),'gradient':int.from_bytes(mem(rsp+8),'little')}
            hx=base['hx']; state=c.component_state(pointers)
            return {'entry_pc':int(context['gpr']['rip'],16),'return_pc':int.from_bytes(mem(rsp),'little'),
              'pointers':pointers,'start_state':state,'t_bits':hx(c.register_bytes(context,'xmm0',8)),
              'dt_bits':hx(c.register_bytes(context,'xmm1',8)),'mxcsr':context['mxcsr'],'ptid':list(c.owner),
              'entry_stack_observations':{'return_pc':{'address':rsp,'size':8,'bytes_hex':mem(rsp).hex(),'status':'OK','timing':'FUNCTION_ENTRY'},
               'gradient_pointer':{'address':rsp+8,'size':8,'bytes_hex':mem(rsp+8).hex(),'status':'OK','timing':'FUNCTION_ENTRY'}},
              'context':context}
        def barrier(self,k,kind):
            c=self.capture; c.stream.flush(); os.fsync(c.stream.raw.raw.fileno())
            raw=(out/'trace.jsonl').read_bytes(); self.pc=int(gdb.newest_frame().read_register('rip'))
            entry=self.entry() if kind=='NEXT_STEP_ENTRY' else None
            state=entry['start_state'] if entry else {**c.regions[-1]['end_state'],'gradient':c.regions[-1]['start_state']['gradient']}
            snapshot={'q':state['q'],'full_v':state['full_v'],'latent':state['latent'],'gradient':state['gradient'],
              't_bits':entry['t_bits'] if entry else None,'dt_bits':entry['dt_bits'] if entry else c.regions[-1]['dt_bits'],
              'paused_pc':self.pc,'next_entry':entry,'body_count':k,'frontier':c.count-1}
            event=BarrierEvent(os.environ['V1_SESSION'],k,k,kind,n,c.process_identity,len(raw),digest_bytes(raw),chain_hash(raw),self.pred,snapshot)
            capture={'schema':'gala-live-prefix-v1','verdict':'PAUSED','case':'known','requested_steps':n,
              'record_count':c.count,'scalar_fp_count':c.fp_count,'opcode_histogram':c.histogram,'regions':c.regions,
              'modules':{p:{a:b for a,b in v.items() if a!='_raw'} for p,v in c.modules.items()},
              'trace_sha256':digest_bytes(raw),'final_chain':c.augmented_chain,'wheel_sha256':base['BASE']['EXPECTED_WHEEL'],
              'process_identity':c.process_identity,'caller_corridors':c.corridors,'terminal_corridor':c.terminal,
              'acquisition_id':event.session_id,'source_pinset_sha256':content_id(self.sources),
              'harness_source_proof':harness_source(root)[1],'guard_source_transformations':ns['guard_proofs'],
              'machine_mapping_read_by_tracer':False,'harness_completed_normally':False,'gdb_exit_event':None}
            metadata={'source_snapshot':self.sources,'source_binding':content_id(self.sources),'capture':capture,'evidence_role':'LIVE',
              'retained_gaps':['init-return -> step1-entry','terminal frontier -> wrapper tail']}
            name=f'metadata-{k}.json'; write(out/name,metadata)
            write_frame(event_fd,{'type':'BARRIER','event':asdict(event),'metadata_path':name,'metadata_sha256':digest_bytes((out/name).read_bytes())})
            self.event=event; self.binding=None; return event
        def paused(self):
            if int(gdb.newest_frame().read_register('rip'))!=self.pc or gdb.selected_inferior().pid!=self.event.process_identity['pid']:
                raise Refused('live pause identity changed')
            if self.event.barrier_kind=='NEXT_STEP_ENTRY' and canonical_bytes(self.entry())!=canonical_bytes(self.event.checkpoint_state['next_entry']):
                raise Refused('live entry changed while paused')
        def wait(self,event,kind):
            while True:
                command=read_frame(command_fd,590); self.paused()
                action=command.get('type')
                if action=='PING': write_frame(event_fd,{'type':'PAUSED','event_id':content_id(event)}); continue
                if action=='BIND':
                    if self.binding is not None: raise Refused('duplicate checkpoint bind')
                    doc=verify_checkpoint(Path(command['checkpoint_dir']),command['checkpoint_id'],expected_event=event)
                    if doc['metadata']['source_binding']!=content_id(self.sources): raise Refused('source binding changed')
                    self.binding={k:command[k] for k in ('checkpoint_id','state_id')}
                    write_frame(event_fd,{'type':'BOUND','checkpoint_id':command['checkpoint_id']}); continue
                if action=='FINISH' and kind=='FINAL_TERMINAL': return
                if action!='RESUME' or kind!='NEXT_STEP_ENTRY' or self.binding is None: raise Refused('no accepted body resume')
                token=ResumeToken(**command['token'])
                expected={'session_id':event.session_id,'barrier_seq':event.barrier_seq,
                  'predecessor_generation':event.completed_step-1,'candidate_generation':event.completed_step,**self.binding}
                document=asdict(token); nonce=document.pop('nonce')
                if document!=expected or nonce in self.used: raise Refused('strict live token binding/reuse')
                self.used.add(nonce); self.pred=token.state_id; return
        def finish(self):
            self.init.delete(); gdb.execute('set scheduler-locking off')
            exit_event={'observed':False,'exit_code':None}
            def exited(e): exit_event.update(observed=True,exit_code=getattr(e,'exit_code',None))
            gdb.events.exited.connect(exited)
            try: gdb.execute('continue',to_string=True)
            finally: gdb.events.exited.disconnect(exited)
            if not exit_event['observed'] or exit_event['exit_code']!=0 or gdb.selected_inferior().pid!=0 or not (out/'harness_output.json').is_file():
                raise Refused('extra native body or incomplete original exit')
            self.capture.stream.close(); self.step.delete()
            write_frame(event_fd,{'type':'FINISHED','normal_exit':True,'exit_event':exit_event,'post_frontier':'UNTRACED'})
    backend=None
    try:
        backend=Backend(); drive_barriers(backend,n)
    except BaseException as exc:
        try:
            if gdb.selected_inferior().pid: gdb.execute('kill',to_string=True)
        except Exception: pass
        try: write_frame(event_fd,{'type':'STOP','reason':f'{type(exc).__name__}: {exc}'})
        except Exception: pass
        raise

if __name__=='__main__': main()
