from dataclasses import replace
import hashlib, json, os
import pytest
from runtime_trace.live_chain.protocol import BarrierEvent
from runtime_trace.live_chain.checkpoint import CheckpointSealer, verify_checkpoint

PREFIX=b'{"seq":0}\n'
CHAIN=hashlib.sha256(bytes(32)+PREFIX).hexdigest()
META={'source_snapshot':{'runtime_trace/harness.py':'d'*64},'source_binding':'e'*64,'capture':{'TEST_ONLY':True}}
def event(prefix=PREFIX):
    return BarrierEvent('a'*64,1,1,'NEXT_STEP_ENTRY',3,{'pid':123},len(prefix),
      hashlib.sha256(prefix).hexdigest(),CHAIN,'b'*64,{'q':['0x0000000000000000']*2})

def test_checkpoint_is_exact_prefix_and_later_appends_are_harmless(tmp_path):
    master=tmp_path/'master.jsonl'; master.write_bytes(PREFIX+b'{"seq":1}\n')
    out=tmp_path/'checkpoint'; identity=CheckpointSealer(tmp_path).seal(master,event(),META,out)
    assert (out/'trace.jsonl').read_bytes()==PREFIX
    master.open('ab').write(b'{"seq":2}\n')
    doc=verify_checkpoint(out,identity)
    assert doc['event']['session_id']=='a'*64 and doc['event']['predecessor_id']=='b'*64
    assert doc['metadata']['source_snapshot']==META['source_snapshot']
    assert (out/'trace.jsonl').stat().st_mode&0o222==0
    with pytest.raises(FileExistsError): CheckpointSealer(tmp_path).seal(master,event(),META,out)

def test_verified_master_prefix_mutation_is_fatal(tmp_path):
    master=tmp_path/'master.jsonl'; master.write_bytes(PREFIX); sealer=CheckpointSealer(tmp_path)
    sealer.seal(master,event(),META,tmp_path/'one'); master.write_bytes(b'{"seq":9}\n')
    with pytest.raises(ValueError): sealer.assert_prefixes(master)
    with pytest.raises(ValueError): sealer.seal(master,event(),META,tmp_path/'two')

@pytest.mark.parametrize('mutation',['trace','metadata','chain','truncation'])
def test_checkpoint_tamper_or_incomplete_prefix_refuses(tmp_path,mutation):
    master=tmp_path/'master.jsonl'; master.write_bytes(PREFIX)
    if mutation in ('chain','truncation'):
        bad=replace(event(),trace_chain_hash='f'*64) if mutation=='chain' else replace(event(),trace_prefix_bytes=100)
        with pytest.raises(ValueError): CheckpointSealer(tmp_path).seal(master,bad,META,tmp_path/'one')
        return
    out=tmp_path/'one'; identity=CheckpointSealer(tmp_path).seal(master,event(),META,out)
    target=out/('trace.jsonl' if mutation=='trace' else 'checkpoint.json'); target.chmod(0o600)
    target.write_bytes(target.read_bytes()+b' ')
    with pytest.raises(ValueError): verify_checkpoint(out,identity)

def test_alias_and_destination_escape_refuse(tmp_path):
    master=tmp_path/'master.jsonl'; master.write_bytes(PREFIX)
    alias=tmp_path/'alias'; alias.symlink_to(master)
    with pytest.raises(ValueError): CheckpointSealer(tmp_path).seal(alias,event(),META,tmp_path/'one')
    with pytest.raises(ValueError): CheckpointSealer(tmp_path).seal(master,event(),META,tmp_path.parent/'escape')

def test_sealed_descriptor_cannot_splice_another_barrier_even_rehashing(tmp_path):
    master=tmp_path/'master.jsonl'; master.write_bytes(PREFIX)
    out=tmp_path/'one'; identity=CheckpointSealer(tmp_path).seal(master,event(),META,out)
    with pytest.raises(ValueError): verify_checkpoint(out,identity,expected_event=replace(event(),session_id='f'*64))
