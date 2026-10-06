"""Edge serialization and explicit carry inputs; no numerical evaluator."""
from dataclasses import asdict
from pathlib import Path
from verified_driver.v1.model import ChainState, FormLane, BASIS, content_id, canonical_bytes
from runtime_trace.regular_nstep.schema import boundary, namespaced
from runtime_trace.regular_nstep.acquire import write

def prior_endpoint(pred):
    if pred.generation==0: return None
    return [{'component':f.component,'byte_offset':f.byte_offset,'center_bits':f.center_bits,
      'form':{'coef':list(f.coefficients),'box':f.box},'state_id':f.source_state_id,
      'occurrence':f'step{pred.step_index}','acquisition_id':pred.live_session_id} for f in pred.forms]

def candidate(event,metadata,endpoint,pred):
    snap=event.checkpoint_state
    forms=tuple(FormLane(e['center_bits'],tuple(e['form']['coef']),e['form']['box'],e['state_id'],e['component'],e['byte_offset'])
      for e in endpoint if e['component']!='gradient')
    state=ChainState(event.completed_step,event.completed_step,event.requested_steps,event.barrier_kind,
      tuple(snap['q'])+tuple(snap['full_v']),tuple(snap['q']),tuple(snap['full_v']),tuple(snap['latent']),
      tuple(snap['gradient']),snap['t_bits'],snap['dt_bits'],forms,BASIS,event.session_id+'/global-error-basis',
      metadata['source_binding'],event.trace_prefix_sha256,event.trace_prefix_bytes,snap['frontier'],pred.content_hash,
      '0'*64,event.session_id,content_id(event.process_identity),event.barrier_seq)
    return state.candidate_document()

def edge_document(checkpoint_id,event,blocks,native,metadata,pred):
    return {'schema':'LIVE_EDGE_V1','checkpoint_id':checkpoint_id,'predecessor_id':pred.content_hash,
      'blocks':blocks,'native':native,'candidate':candidate(event,metadata,blocks[-1]['endpoint'],pred)}

def completion(edge,edge_sha):
    c=edge['candidate']
    doc={'schema':'EDGE_COMPLETION_V1','checkpoint_id':edge['checkpoint_id'],'predecessor_id':edge['predecessor_id'],
      'edge_sha256':edge_sha,'checked_edge':c['step_index'],'requested_steps':c['requested_steps'],
      'requested_complete':c['barrier_kind']=='FINAL_TERMINAL','verified_frontier':c['verified_frontier'],
      'operation_count':sum(len(b['ir']['operations']) for b in edge['blocks']),
      'init_to_step1':'UNTRACED','post_terminal_frontier':'UNTRACED','formal_certification':False}
    doc['completion_sha256']=content_id(doc)
    return doc
