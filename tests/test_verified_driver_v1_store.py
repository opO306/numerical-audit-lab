from dataclasses import replace
import pytest
from verified_driver.v1.model import chain_genesis
from verified_driver.v1.store import ChainStore
from tests.verified_driver_v1_support import ROOT, ZERO, successor

def test_append_only_receipt_object_and_idempotent_retry(tmp_path):
    g=chain_genesis(ROOT,3); store=ChainStore(tmp_path); store.initialize(g)
    old=(tmp_path/'objects'/f'{g.content_hash}.json').read_bytes()
    s,r=successor(g); assert store.publish(g.content_hash,s,r)==s.content_hash
    assert store.publish(g.content_hash,s,r)==s.content_hash
    assert (tmp_path/'objects'/f'{g.content_hash}.json').read_bytes()==old
    assert (tmp_path/'receipts'/f'{s.acceptance_id}.json').read_bytes()==r
    assert ChainStore(tmp_path).recover()==(s.content_hash,s)

@pytest.mark.parametrize('point,want',[('after_objects',0),('before_current_replace',0),('after_current_replace',1)])
def test_durable_current_defines_recovery(tmp_path,point,want):
    g=chain_genesis(ROOT,3); store=ChainStore(tmp_path); store.initialize(g); s,r=successor(g)
    def crash(name):
        if name==point: raise OSError('publication uncertainty')
    broken=ChainStore(tmp_path,_crash_hook=crash)
    with pytest.raises(OSError): broken.publish(g.content_hash,s,r)
    assert ChainStore(tmp_path).recover()[1].generation==want

@pytest.mark.parametrize('data',[b'',b'f'*64+b'\n',b'../object\n',b'a'*64])
def test_unknown_or_corrupt_current_never_guesses(tmp_path,data):
    store=ChainStore(tmp_path); store.initialize(chain_genesis(ROOT,3)); (tmp_path/'CURRENT').write_bytes(data)
    with pytest.raises(ValueError): store.recover()

def test_predecessor_and_receipt_substitution_fail_without_publication(tmp_path):
    g=chain_genesis(ROOT,3); store=ChainStore(tmp_path); store.initialize(g); s,r=successor(g)
    for pred,state,receipt in [('f'*64,s,r),(g.content_hash,replace(s,latent_bits=(ZERO,ZERO),forms=tuple(
        replace(f,center_bits=ZERO) if f.component=='latent' else f for i,f in enumerate(s.forms))),r),
        (g.content_hash,s,r+b' ' )]:
        with pytest.raises(ValueError): store.publish(pred,state,receipt)
        assert store.current()[1].generation==0

def test_terminal_cannot_publish_a_successor(tmp_path):
    g=chain_genesis(ROOT,1); store=ChainStore(tmp_path); store.initialize(g); s,r=successor(g,final=True)
    store.publish(g.content_hash,s,r)
    with pytest.raises(ValueError): successor(s,final=True)

def test_existing_objects_cannot_be_overwritten(tmp_path):
    g=chain_genesis(ROOT,3); store=ChainStore(tmp_path); store.initialize(g); s,r=successor(g)
    (tmp_path/'objects'/f'{s.content_hash}.json').write_bytes(b'corrupt')
    with pytest.raises(ValueError): store.publish(g.content_hash,s,r)
    assert store.current()[1].generation==0

def test_initialize_different_request_refuses(tmp_path):
    store=ChainStore(tmp_path); store.initialize(chain_genesis(ROOT,3))
    with pytest.raises(ValueError): store.initialize(chain_genesis(ROOT,4))
