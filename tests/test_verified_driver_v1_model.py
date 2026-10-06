from dataclasses import replace
import pytest
from verified_driver.v1.model import ChainState, FormLane, chain_genesis
from tests.verified_driver_v1_support import ROOT, ZERO, HX, successor

def test_genesis_requires_original_harness(tmp_path):
    p=tmp_path/'runtime_trace/harness.py'; p.parent.mkdir(); p.write_text('different program')
    with pytest.raises(ValueError): chain_genesis(tmp_path,3)
    g=chain_genesis(ROOT,3)
    assert (g.generation,g.step_index,g.barrier_kind)==(0,0,'GENESIS')
    assert g.public_bits==(ZERO,ZERO,'0x3fd0000000000000','0x3fc0000000000000')

@pytest.mark.parametrize('field,value',[
 ('q_bits',(ZERO,)),('full_v_bits',(ZERO,)*3),('latent_bits',(ZERO,)),
 ('public_bits',('0x7ff0000000000000',)*4),('q_bits',('0X0000000000000000',ZERO)),
 ('gradient_bits',('0x8000000000000000',ZERO)),('dt_bits','0x7ff8000000000000'),
 ('generation',2),('step_index',0),('barrier_seq',3),('requested_steps',True),
 ('barrier_kind','GENESIS'),('next_t_bits',None),('forms',()),
 ('basis_contract',{'k':5,'meaning':'computed-minus-true','reseeded':False}),
 ('trace_prefix_bytes',0),('verified_frontier',-1),('source_binding','bad'),
])
def test_malformed_continuation_refuses(field,value):
    state,_=successor(chain_genesis(ROOT,3))
    with pytest.raises(ValueError): replace(state,**{field:value})

@pytest.mark.parametrize('coefficients,box',[(('0x0.0p+0',)*3,HX),((HX,)*4,'-0x1.0000000000000p+0'),
 ((HX,HX,HX,'inf'),HX),((HX,)*4,'nan')])
def test_invalid_forms_refuse(coefficients,box):
    with pytest.raises(ValueError): FormLane(ZERO,coefficients,box,'sid','q',0)

def test_form_lane_centers_and_roles_must_match_state():
    state,_=successor(chain_genesis(ROOT,3))
    with pytest.raises(ValueError): replace(state,forms=(replace(state.forms[0],center_bits=ZERO),)+state.forms[1:])
    with pytest.raises(ValueError): replace(state,forms=(state.forms[0],)*6)

def test_final_terminal_requires_requested_last_step():
    with pytest.raises(ValueError): successor(chain_genesis(ROOT,3),final=True)
    state,_=successor(chain_genesis(ROOT,1),final=True)
    assert state.next_t_bits is None
    with pytest.raises(ValueError): replace(state,barrier_kind='NEXT_STEP_ENTRY')

def test_frozen_state_cannot_be_mutated_through_basis():
    state,_=successor(chain_genesis(ROOT,3))
    with pytest.raises(TypeError): state.basis_contract['k']=5

@pytest.mark.parametrize('n',[0,-1,101,True,3.0])
def test_unsupported_request_is_rejected(n):
    with pytest.raises(ValueError): chain_genesis(ROOT,n)
