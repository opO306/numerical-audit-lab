"""TEST_ONLY literal continuation fixtures; never numerical evidence."""
from dataclasses import replace
from pathlib import Path
import os
ROOT=Path(__file__).resolve().parents[1]
LEDGER=Path(os.environ.get('GIT_WORK_TREE',str(ROOT)))/'runtime_trace/regular_nstep/artifacts/budget.json'
ZERO='0x0000000000000000'
DT='0x3f90000000000000'
HX='0x0.0p+0'
def successor(parent, *, final=False, session='a'*64):
    from verified_driver.v1.model import FormLane, canonical_bytes, digest_bytes
    k=parent.generation+1
    q=('0x3f70000000000000','0x3f60000000000000')
    v=('0x3fd0000000000000','0x3fc0000000000000')
    forms=tuple(FormLane(bits,(HX,)*4,'0x1.0000000000000p-54',f'{session}/step{k}/{name}/{offset}',name,offset)
      for name,lanes in [('q',q),('full_v',v),('latent',v)] for offset,bits in zip((0,8),lanes))
    state=replace(parent,generation=k,step_index=k,barrier_seq=k,
      barrier_kind='FINAL_TERMINAL' if final else 'NEXT_STEP_ENTRY',public_bits=q+v,
      q_bits=q,full_v_bits=v,latent_bits=v,gradient_bits=(ZERO,ZERO),next_t_bits=None if final else DT,
      forms=forms,live_basis_namespace=session+'/global-error-basis',live_session_id=session,
      process_identity_digest='b'*64,trace_prefix_sha256=str(k)*64,trace_prefix_bytes=k*100,
      verified_frontier=k*10,predecessor_id=parent.content_hash,acceptance_id='c'*64)
    receipt=canonical_bytes({'schema':'VERIFIED_CHAIN_ACCEPTANCE_V1','verdict':'ACCEPT',
      'candidate':state.candidate_document(),'predecessor_id':parent.content_hash,'checkpoint_id':'d'*64,
      'edge_completion_sha256':'e'*64})
    return replace(state,acceptance_id=digest_bytes(receipt)),receipt
