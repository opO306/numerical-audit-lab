from dataclasses import replace
from pathlib import Path
import pytest
from verified_driver.v0.model import CertifiedState, canonical_bytes, digest_bytes, regular_genesis
from verified_driver.v0.store import CertifiedStore

ROOT=Path(__file__).resolve().parents[1]
BITS=('0x3fa3eaff7788ac22','0x3f93eacc1b020e3a','0x3fcf9999a5c32ae6','0x3fbf984cad4b103f')
def successor(genesis):
    receipt=canonical_bytes({'schema':'DRIVER_V0_ACCEPTANCE_V1','verdict':'ACCEPT','transaction_id':'tx-a',
        'predecessor_id':genesis.content_hash,'candidate_id':'a'*64,'source_pinset_sha256':'b'*64,
        'completion_sha256':'c'*64,'acquisition_id':'d'*64,'requested_steps':10,'checked_steps':10,
        'requested_complete':True,'output_bits':BITS})
    state=CertifiedState(1,BITS,'b'*64,genesis.content_hash,digest_bytes(receipt),'tx-a','d'*64)
    return state,receipt

def test_same_genesis_idempotent_and_restart(tmp_path):
    g=regular_genesis(ROOT); store=CertifiedStore(tmp_path)
    assert store.initialize(g)==g.content_hash
    assert store.initialize(g)==g.content_hash
    assert CertifiedStore(tmp_path).recover()==(g.content_hash,g)

def test_predecessor_mismatch_refuses_without_publication(tmp_path):
    g=regular_genesis(ROOT); store=CertifiedStore(tmp_path); store.initialize(g)
    state,receipt=successor(g)
    with pytest.raises(ValueError): store.publish('f'*64,state,receipt)
    assert store.current()==(g.content_hash,g)

def test_append_only_objects_and_receipts_precede_pointer(tmp_path):
    g=regular_genesis(ROOT); store=CertifiedStore(tmp_path); store.initialize(g)
    state,receipt=successor(g); before=(tmp_path/f'objects/{g.content_hash}.json').read_bytes()
    assert store.publish(g.content_hash,state,receipt)==state.content_hash
    assert (tmp_path/f'objects/{g.content_hash}.json').read_bytes()==before
    assert (tmp_path/f'receipts/{state.acceptance_id}.json').read_bytes()==receipt
    assert CertifiedStore(tmp_path).current()==(state.content_hash,state)

def test_retry_does_not_double_generation(tmp_path):
    g=regular_genesis(ROOT); store=CertifiedStore(tmp_path); store.initialize(g)
    state,receipt=successor(g)
    store.publish(g.content_hash,state,receipt)
    assert store.publish(g.content_hash,state,receipt)==state.content_hash
    assert store.current()[1].generation==1

@pytest.mark.parametrize('point,want_new',[('after_objects',False),('before_replace',False),('after_replace',True)])
def test_crash_recovers_only_old_or_complete_new(tmp_path,point,want_new):
    g=regular_genesis(ROOT); store=CertifiedStore(tmp_path); store.initialize(g)
    state,receipt=successor(g)
    def crash(name):
        if name==point: raise OSError('injected publication crash')
    broken=CertifiedStore(tmp_path,_crash_hook=crash)
    with pytest.raises(OSError): broken.publish(g.content_hash,state,receipt)
    assert CertifiedStore(tmp_path).recover()==((state.content_hash,state) if want_new else (g.content_hash,g))

@pytest.mark.parametrize('bad',[b'0'*12,b'f'*64+b'\n',b'',b'../escape\n'])
def test_truncated_or_unknown_current_refuses(tmp_path,bad):
    g=regular_genesis(ROOT); store=CertifiedStore(tmp_path); store.initialize(g)
    (tmp_path/'CURRENT').write_bytes(bad)
    with pytest.raises(ValueError): store.recover()

def test_existing_content_address_bytes_cannot_be_overwritten(tmp_path):
    g=regular_genesis(ROOT); store=CertifiedStore(tmp_path); store.initialize(g)
    state,receipt=successor(g)
    (tmp_path/f'objects/{state.content_hash}.json').write_bytes(b'wrong')
    with pytest.raises(ValueError): store.publish(g.content_hash,state,receipt)
    assert store.current()==(g.content_hash,g)

def test_unaccepted_receipt_or_wrong_output_cannot_publish(tmp_path):
    g=regular_genesis(ROOT); store=CertifiedStore(tmp_path); store.initialize(g)
    state,receipt=successor(g)
    bad=replace(state,state_bits=g.state_bits)
    with pytest.raises(ValueError): store.publish(g.content_hash,bad,receipt)
    assert store.current()==(g.content_hash,g)
