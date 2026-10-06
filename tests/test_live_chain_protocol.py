from dataclasses import replace
import pytest
from verified_driver.v1.live_chain.protocol import BarrierEvent, ResumeToken, TokenLedger, encode_record, decode_record

EXPECTED=dict(session_id='a'*64,barrier_seq=1,predecessor_generation=0,candidate_generation=1,
 checkpoint_id='b'*64,state_id='c'*64)

def test_single_use_token_bound_to_exact_live_transaction():
    ledger=TokenLedger(); token=ledger.issue(**EXPECTED,current_state_id='c'*64)
    assert isinstance(token,ResumeToken)
    ledger.consume(token,**EXPECTED)
    with pytest.raises(ValueError): ledger.consume(token,**EXPECTED)

@pytest.mark.parametrize('key,value',[
 ('session_id','f'*64),('barrier_seq',0),('barrier_seq',2),('predecessor_generation',1),
 ('candidate_generation',2),('checkpoint_id','e'*64),('state_id','e'*64),('nonce','f'*64)])
def test_token_substitution_refuses_and_does_not_consume_real_token(key,value):
    ledger=TokenLedger(); token=ledger.issue(**EXPECTED,current_state_id='c'*64)
    with pytest.raises(ValueError): ledger.consume(replace(token,**{key:value}),**EXPECTED)
    ledger.consume(token,**EXPECTED)

def test_issue_requires_current_and_monotonic_barrier():
    ledger=TokenLedger()
    with pytest.raises(ValueError): ledger.issue(**EXPECTED,current_state_id='d'*64)
    ledger.issue(**EXPECTED,current_state_id='c'*64)
    with pytest.raises(ValueError): ledger.issue(**EXPECTED,current_state_id='c'*64)
    with pytest.raises(ValueError): ledger.issue(**{**EXPECTED,'barrier_seq':3},current_state_id='c'*64)

def test_bounded_canonical_frame_rejects_duplicate_keys_and_extra_frames():
    wire=encode_record({'type':'STOP','reason':'checker refused'})
    assert decode_record(wire)=={'type':'STOP','reason':'checker refused'}
    for bad in (b'{"x":1,"x":2}\n',b'{"x":NaN}\n',wire+wire,b'[]\n',b'{}',b'{ "x": 1 }\n'):
        with pytest.raises(ValueError): decode_record(bad)
    with pytest.raises(ValueError): encode_record({'x':'a'*65536})
