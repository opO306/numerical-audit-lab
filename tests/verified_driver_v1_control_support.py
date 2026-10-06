"""TEST_ONLY marker sessions and explicit controller gate injection."""
from dataclasses import replace
from pathlib import Path
from verified_driver.v1.model import chain_genesis, canonical_bytes, content_id, digest_bytes
from tests.verified_driver_v1_support import ROOT, LEDGER, successor
from verified_driver.v1.live_chain.protocol import BarrierEvent
from verified_driver.v1.live_chain.checkpoint import chain_hash, verify_checkpoint
from verified_driver.v1.live_chain.session import live_source_snapshot

class MarkerSession:
    def __init__(self,root,out,n,ledger,store):
        self.repo_root=root; self.run_root=out; self.n=n; self.store=store; self.session_id='a'*64
        self.sources=live_source_snapshot(root); self.master_trace=out/'trace.jsonl'; self.markers=[]; self.stopped=False; self.finished=False
        self.identity={'pid':123,'linux_boot_id':'00000000-0000-0000-0000-000000000001','proc_stat_start_time_ticks':9}
        self.bound=None
    def emit(self,pred):
        k=len(self.markers)+1; self.markers.append(k)
        with self.master_trace.open('ab') as f: f.write(canonical_bytes({'TEST_ONLY':True,'body':k})+b'\n')
        raw=self.master_trace.read_bytes(); state,_=successor(pred,final=k==self.n,session=self.session_id)
        state=replace(state,source_binding=content_id(self.sources),process_identity_digest=content_id(self.identity),
          trace_prefix_bytes=len(raw),trace_prefix_sha256=digest_bytes(raw),verified_frontier=k-1)
        snap={'q':state.q_bits,'full_v':state.full_v_bits,'latent':state.latent_bits,'gradient':state.gradient_bits,
          't_bits':state.next_t_bits,'dt_bits':state.dt_bits,'frontier':k-1,'body_count':k}
        self.event=BarrierEvent(self.session_id,k,k,state.barrier_kind,self.n,self.identity,len(raw),digest_bytes(raw),chain_hash(raw),pred.content_hash,snap)
        self.metadata={'source_snapshot':self.sources,'source_binding':content_id(self.sources),'evidence_role':'TEST_ONLY','candidate':state.candidate_document()}
        self.bound=None; return self.event
    def start(self):
        self.run_root.mkdir(parents=True,exist_ok=False)
        return self.emit(chain_genesis(self.repo_root,self.n))
    def is_paused_at(self,event): return event==self.event and not self.stopped
    def bind_checkpoint(self,cid,cp,sid,pred_gen):
        assert self.store.current()[0]==sid
        verify_checkpoint(cp,cid,expected_event=self.event); self.bound=(cid,sid,pred_gen)
    def resume(self,token):
        if self.bound is None: raise ValueError('TEST_ONLY resume before publication/binding')
        cid,sid,pred_gen=self.bound
        assert (token.checkpoint_id,token.state_id,token.predecessor_generation)==(cid,sid,pred_gen)
        assert self.store.current()[0]==sid
        return self.emit(self.store.current()[1])
    def finish(self):
        assert self.store.current()[1].generation==self.n
        self.finished=True; return {'normal_exit':True,'TEST_ONLY':True}
    def terminate(self,reason): self.stopped=True

class MarkerGate:
    def __init__(self,refuse=None,exception=None,callback=None): self.refuse=refuse; self.exception=exception; self.callback=callback
    def evaluate(self,cid,cp,pred,out,root):
        from verified_driver.v1.model import ChainState
        doc=verify_checkpoint(cp,cid); k=doc['event']['completed_step']
        if self.callback: self.callback(k)
        if k==self.refuse: raise ValueError('controlled checker refusal')
        if self.exception: raise self.exception
        candidate=doc['metadata']['candidate']
        receipt=canonical_bytes({'schema':'VERIFIED_CHAIN_ACCEPTANCE_V1','verdict':'ACCEPT',
          'candidate':candidate,'predecessor_id':pred.content_hash,'checkpoint_id':cid,'edge_completion_sha256':'e'*64})
        return ChainState(**candidate,acceptance_id=digest_bytes(receipt)),receipt

def marker_driver(tmp_path,n=3,gate=None,hook=None):
    from verified_driver.v1.store import ChainStore
    from verified_driver.v1.controller import VerifiedChainDriver
    store=ChainStore(tmp_path/'store'); store.initialize(chain_genesis(ROOT,n))
    driver=VerifiedChainDriver(ROOT,store,tmp_path/'runs',LEDGER)
    driver._gate=gate or MarkerGate(); driver._crash_hook=hook
    driver._make_session=lambda root,out,steps,ledger: MarkerSession(root,out,steps,ledger,store)
    return driver
