"""Only CURRENT-authorized numerical progression; no production fallback."""
from dataclasses import asdict, replace
from pathlib import Path
import re, time
from .model import ChainState, ChainResult, chain_genesis, canonical_bytes, content_id, strict_json, digest_bytes
from .gate import V1Gate
from verified_driver.v1.live_chain.protocol import TokenLedger
from verified_driver.v1.live_chain.session import LiveGalaSession, live_source_snapshot
from verified_driver.v1.live_chain.checkpoint import CheckpointSealer, sealed_write, no_alias, verify_checkpoint
from runtime_trace.regular_nstep.acquire import validate_n

class VerifiedChainDriver:
    def __init__(self,repo_root,store,run_root,ledger):
        self.repo_root=no_alias(repo_root); self.store=store; self.run_root=no_alias(run_root); self.ledger=Path(ledger)
        if self.run_root.is_relative_to(store.root) or store.root.is_relative_to(self.run_root): raise ValueError('run/store namespaces overlap')
        if not self.ledger.is_file(): raise ValueError('existing shared ledger required')
        self._make_session=LiveGalaSession; self._gate=V1Gate(); self._crash_hook=None; self.session=None; self.metrics=[]
    def _hook(self,point):
        if self._crash_hook: self._crash_hook(point)
    def _paused(self,event):
        if self.session.sources!=live_source_snapshot(self.repo_root): raise ValueError('source changed while live')
        if not self.session.is_paused_at(event): raise ValueError('live pause cannot be proved')
    def _event(self,event,pred):
        if event.predecessor_id!=pred.content_hash or event.completed_step!=pred.step_index+1 or event.requested_steps!=pred.requested_steps:
            raise ValueError('stale/skipped/foreign predecessor event')
        if event.session_id!=self.session.session_id: raise ValueError('foreign live session')
        self._paused(event)
    def _accepted(self,state,event,pred,cid,receipt):
        doc=strict_json(receipt)
        if state.predecessor_id!=pred.content_hash or state.step_index!=event.completed_step or state.barrier_kind!=event.barrier_kind or state.live_session_id!=event.session_id:
            raise ValueError('acceptance barrier/predecessor mismatch')
        if state.process_identity_digest!=content_id(event.process_identity) or state.source_binding!=self.session.metadata['source_binding'] or state.trace_prefix_sha256!=event.trace_prefix_sha256 or state.trace_prefix_bytes!=event.trace_prefix_bytes or state.verified_frontier!=event.checkpoint_state['frontier']:
            raise ValueError('acceptance live process/source/prefix mismatch')
        for name in ('q','full_v','latent','gradient'):
            if getattr(state,name+'_bits')!=tuple(event.checkpoint_state[name]): raise ValueError('acceptance logical snapshot mismatch')
        if state.next_t_bits!=event.checkpoint_state['t_bits'] or state.dt_bits!=event.checkpoint_state['dt_bits'] or doc['checkpoint_id']!=cid:
            raise ValueError('acceptance entry/checkpoint substitution')
        self.store._receipt(state,receipt)
    def _stop(self,run_id,reason):
        if self.session is not None:
            try: self.session.terminate(reason)
            except Exception as exc: reason+='; containment termination: '+str(exc)
        try: identity,state=self.store.recover()
        except Exception as exc: return ChainResult('STOP',run_id,None,None,None,reason+'; CURRENT unresolved: '+str(exc))
        return ChainResult('STOP',run_id,identity,state.generation,state.step_index,reason)
    def _advance(self,event,pred,out,sealer,tokens,*,transition_id=None):
        self._event(event,pred); k=event.completed_step; paused=time.perf_counter(); measurement={'step':k}
        start=time.perf_counter(); cp=out/f'checkpoint-{k}'
        cid=sealer.seal(self.session.master_trace,event,self.session.metadata,cp)
        measurement['seal_seconds']=time.perf_counter()-start
        state,receipt=self._gate.evaluate(cid,cp,pred,out/f'edge-{k}',self.repo_root)
        if transition_id is not None:
            document=strict_json(receipt); document['replay_transition_id']=transition_id
            receipt=canonical_bytes(document); state=replace(state,acceptance_id=digest_bytes(receipt))
        measurement.update(getattr(self._gate,'metrics',{})); self._accepted(state,event,pred,cid,receipt); self._paused(event)
        start=time.perf_counter(); identity=self.store.publish(pred.content_hash,state,receipt)
        measurement['publication_seconds']=time.perf_counter()-start
        self._hook('after_current_replace_before_token')
        sealer.assert_prefixes(self.session.master_trace)
        current,current_state=self.store.recover()
        if current!=identity or current_state!=state: raise ValueError('publication authority uncertain')
        self._paused(event); self.session.bind_checkpoint(cid,cp,identity,pred.generation)
        measurement['paused_seconds']=time.perf_counter()-paused; self.metrics.append(measurement)
        sealed_write(out/f'barrier-{k}.json',canonical_bytes({'event_id':content_id(event),'checkpoint_id':cid,
          'state_id':identity,'predecessor_id':pred.content_hash,'order':['PAUSE','SEAL','CHECK','CURRENT','BIND'],**measurement}))
        if state.barrier_kind=='FINAL_TERMINAL':
            self.session.finish(); return None,state
        binding=dict(session_id=event.session_id,barrier_seq=event.barrier_seq,predecessor_generation=pred.generation,
          candidate_generation=state.generation,checkpoint_id=cid,state_id=identity)
        token=tokens.issue(current_state_id=current,**binding)
        self._hook('after_token_before_resume'); self._paused(event)
        # Recheck complete CURRENT immediately before consuming the exact token.
        if self.store.recover()[0]!=identity: raise ValueError('CURRENT changed before resume')
        sealer.assert_prefixes(self.session.master_trace)
        tokens.consume(token,**binding)
        started=time.perf_counter(); following=self.session.resume(token)
        self.metrics.append({'next_body':following.completed_step,'acquisition_seconds':time.perf_counter()-started})
        return following,state
    def run(self,requested_steps,run_id):
        n=validate_n(requested_steps)
        if type(run_id) is not str or re.fullmatch(r'[a-z0-9][a-z0-9-]{0,63}',run_id) is None: raise ValueError('bounded run identity required')
        out=self.run_root/run_id
        try:
            self.store.initialize(chain_genesis(self.repo_root,n)); identity,pred=self.store.recover()
            if pred.generation:
                result_path=out/'result.json'
                if pred.barrier_kind=='FINAL_TERMINAL' and result_path.is_file():
                    prior=ChainResult(**strict_json(result_path.read_bytes()))
                    if prior.verdict=='ACCEPT' and prior.state_id==identity: return prior
                return self._stop(run_id,'lost live session requires genesis replay; no arbitrary continuation')
            out.mkdir(parents=True,exist_ok=False); sealer=CheckpointSealer(out); tokens=TokenLedger()
            self.session=self._make_session(self.repo_root,out/'live',n,self.ledger)
            start=time.perf_counter(); event=self.session.start()
            self.metrics.append({'initial_acquisition_seconds':time.perf_counter()-start})
            while event is not None: event,pred=self._advance(event,pred,out,sealer,tokens)
            result=ChainResult('ACCEPT',run_id,pred.content_hash,pred.generation,pred.step_index,'requested numerical chain complete; wrapper tail UNTRACED')
            self.session.terminate('completed'); sealed_write(out/'result.json',canonical_bytes(result))
            sealed_write(out/'metrics.json',canonical_bytes(self.metrics)); return result
        except Exception as exc:
            result=self._stop(run_id,type(exc).__name__+': '+str(exc))
            if out.is_dir() and not (out/'result.json').exists(): sealed_write(out/'result.json',canonical_bytes(result))
            return result
