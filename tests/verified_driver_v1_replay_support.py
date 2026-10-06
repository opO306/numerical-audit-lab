"""TEST_ONLY marker replay reports; no Gala evidence or real certificate."""
from dataclasses import replace
from verified_driver.v1.model import ChainState, canonical_bytes, content_id, digest_bytes
from tests.verified_driver_v1_control_support import MarkerSession, MarkerGate, marker_driver
from tests.verified_driver_v1_support import successor

def prepared(tmp_path,steps=4,target=2):
    driver=marker_driver(tmp_path,steps,gate=MarkerGate(refuse=target+1))
    driver.run(steps,'original')
    assert driver.store.current()[1].generation==target
    return driver

def proof_document(driver):
    from verified_driver.v1.replay import ReplayTransition
    chain=driver.store.chain(); fresh=chain[0]; proofs=[]
    for stored in chain[1:]:
        state,_=successor(fresh,final=stored.barrier_kind=='FINAL_TERMINAL',session='f'*64)
        state=replace(state,source_binding=stored.source_binding,process_identity_digest='d'*64,
                      trace_prefix_bytes=stored.step_index*111,verified_frontier=stored.step_index*12)
        candidate=state.candidate_document()
        candidate['predecessor_id']=stored.predecessor_id
        report={'schema':'LIVE_EDGE_CHECK_V1','verdict':'CHECKER_PASS','candidate':candidate,
                'checkpoint_id':str(stored.step_index)*64,'completion_sha256':'e'*64,
                'checked_step':stored.step_index,'requested_complete':False,
                'evidence_role':'LIVE','formal_certification':False,
                'init_to_step1':'UNTRACED','post_terminal_frontier':'UNTRACED'}
        proofs.append({'checkpoint_id':report['checkpoint_id'],'checker_report':report,
                       'checker_report_sha256':content_id(report)})
        fresh=state
    return ReplayTransition.document(chain,proofs,driver.session.sources)

def transitioned_child(driver,document):
    from verified_driver.v1.replay import ReplayCarry
    parent=driver.store.current()[1]
    carry=ReplayCarry(parent,document['fresh_anchor'])
    child,receipt=successor(parent,final=parent.generation+1==parent.requested_steps,session=carry.live_session_id)
    child=replace(child,process_identity_digest=carry.process_identity_digest,
                  source_binding=carry.source_binding,trace_prefix_bytes=carry.trace_prefix_bytes+101,
                  verified_frontier=carry.verified_frontier+10)
    receipt=canonical_bytes({'schema':'VERIFIED_CHAIN_ACCEPTANCE_V1','verdict':'ACCEPT',
             'candidate':child.candidate_document(),'predecessor_id':parent.content_hash,
             'checkpoint_id':'4'*64,'edge_completion_sha256':'e'*64,
             'replay_transition_id':content_id(document)})
    return replace(child,acceptance_id=digest_bytes(receipt)),receipt

class ReplayMarkerSession(MarkerSession):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs); self.session_id='f'*64
        self.identity={**self.identity,'pid':456,'proc_stat_start_time_ticks':10}
    def bind_checkpoint(self,cid,cp,sid,pred_gen):
        from verified_driver.v1.live_chain.checkpoint import verify_checkpoint
        assert any(state.content_hash==sid for state in self.store.chain())
        verify_checkpoint(cp,cid,expected_event=self.event); self.bound=(cid,sid,pred_gen)
    def resume(self,token):
        assert self.bound==(token.checkpoint_id,token.state_id,token.predecessor_generation)
        pred=next(s for s in self.store.chain() if s.content_hash==token.state_id)
        return self.emit(pred)

class ReplayMarkerGate(MarkerGate):
    def observe(self,cid,cp,pred,out,root):
        from verified_driver.v1.live_chain.checkpoint import verify_checkpoint
        doc=verify_checkpoint(cp,cid)
        return {'schema':'LIVE_EDGE_CHECK_V1','verdict':'CHECKER_PASS','candidate':doc['metadata']['candidate'],
                'checkpoint_id':cid,'completion_sha256':'e'*64,'checked_step':doc['event']['completed_step'],
                'requested_complete':doc['event']['barrier_kind']=='FINAL_TERMINAL',
                'evidence_role':'LIVE','formal_certification':False,
                'init_to_step1':'UNTRACED','post_terminal_frontier':'UNTRACED'}

def replay_driver(driver):
    from verified_driver.v1.controller import VerifiedChainDriver
    fresh=VerifiedChainDriver(driver.repo_root,driver.store,driver.run_root,driver.ledger)
    fresh._gate=ReplayMarkerGate()
    fresh._make_session=lambda root,out,n,ledger:ReplayMarkerSession(root,out,n,ledger,driver.store)
    return fresh
