"""TEST_ONLY logical replay comparison; no numerical or publication evidence."""
from dataclasses import replace
import pytest
from verified_driver.v1.replay import ReplayObservation, ReplayComparator
from verified_driver.v1.model import chain_genesis
from tests.verified_driver_v1_support import ROOT, successor

def pair(final=False):
    stored,_=successor(chain_genesis(ROOT,1 if final else 3),final=final)
    fresh,_=successor(chain_genesis(ROOT,1 if final else 3),final=final,session='f'*64)
    fresh=replace(fresh,process_identity_digest='d'*64,trace_prefix_sha256='e'*64,
                  trace_prefix_bytes=211,verified_frontier=19)
    observed=ReplayObservation.from_candidate(fresh.candidate_document(),
       stored_position_id=stored.content_hash,stored_predecessor_id=stored.predecessor_id,
       checkpoint_id='8'*64,checker_report_id='9'*64)
    return stored,observed

def test_replay_allows_only_new_process_namespace_and_prefix_provenance():
    stored,observed=pair()
    ReplayComparator.compare(stored,observed)
    assert observed.live_session_id!=stored.live_session_id
    assert not hasattr(observed,'generation')
    assert not hasattr(observed,'acceptance_id')
    assert not hasattr(observed,'publish')

@pytest.mark.parametrize('field,value',[
 ('latent_bits',('0x3fc0000000000000',)*2),
 ('next_t_bits','0x3fa0000000000000'),
 ('source_binding','f'*64),('requested_steps',4),
 ('stored_position_id','f'*64),('stored_predecessor_id','f'*64),
 ('gradient_bits',('0x3ff0000000000000',)*2),('step_index',2)])
def test_replay_same_public_qv_cannot_hide_wrong_continuation(field,value):
    stored,observed=pair()
    with pytest.raises(ValueError): ReplayComparator.compare(stored,replace(observed,**{field:value}))

@pytest.mark.parametrize('field,value',[
 ('coefficients',('0x1.0000000000000p+0',)+('0x0.0p+0',)*3),
 ('box','0x1.0000000000000p-53'),('byte_offset',8)])
def test_replay_wrong_form_refuses(field,value):
    stored,observed=pair(); forms=list(observed.forms)
    forms[0]=replace(forms[0],**{field:value})
    with pytest.raises(ValueError): ReplayComparator.compare(stored,replace(observed,forms=tuple(forms)))

def test_terminal_replay_observation_has_no_live_successor_authority():
    stored,observed=pair(final=True)
    ReplayComparator.compare(stored,observed)
    assert observed.barrier_kind=='FINAL_TERMINAL' and observed.next_t_bits is None
    assert observed.may_transition_to_live is False

def test_cross_process_nonzero_basis_is_outside_supported_replay_scope():
    stored,observed=pair()
    coef=('0x1.0000000000000p-54',)+('0x0.0p+0',)*3
    stored=replace(stored,forms=(replace(stored.forms[0],coefficients=coef),)+stored.forms[1:])
    observed=replace(observed,forms=(replace(observed.forms[0],coefficients=coef),)+observed.forms[1:],
                     stored_position_id=stored.content_hash)
    with pytest.raises(ValueError,match='nonzero'): ReplayComparator.compare(stored,observed)
