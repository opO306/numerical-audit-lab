"""Truthful acquisition and write preservation, without a Gala execution."""
import copy
import importlib
import pytest
from tests.test_v1_evex_producer import state,BASE,CODES

def api():
    return importlib.import_module('verified_driver.v1.native_evex_collector')

def test_masked_store_keeps_all_sixteen_same_value_writes_and_no_cpu_reads():
    before=state(0x199720);before['registers'].update(rax=0x4000,k1=0xffff)
    before['vectors']['zmm16']='00'*64
    after=copy.deepcopy(before);after['registers']['rip']=BASE+0x199726
    reads=[];executions=[]
    def read(address,size):
        reads.append((address,size));return bytes(size)
    row=api().record_step(0x199720,CODES[0x199720],before,read,
        lambda:executions.append(1),lambda:after,BASE)
    assert executions==[1]
    assert row['reads']==[]
    assert reads==[(0x4000+i,1) for i in range(16)]*2
    assert row['writes']==[dict(address=0x4000+i,size=1,after_hex='00') for i in range(16)]
    assert all(w['before_hex']=='00' and w['after_hex']=='00' and w['value_changed'] is False
        for w in row['write_observations'])

def test_ret_records_only_architectural_stack_read():
    before=state(0x199726);before['registers']['rsp']=0x8000
    after=copy.deepcopy(before);after['registers'].update(rip=0x9000,rsp=0x8008)
    calls=[]
    def read(address,size):calls.append((address,size));return (0x9000).to_bytes(8,'little')
    row=api().record_step(0x199726,'c3',before,read,lambda:None,lambda:after,BASE)
    assert calls==[(0x8000,8)]
    assert row['reads']==[dict(address=0x8000,size=8,bytes_hex='0090000000000000')]
    assert row['writes']==[]

@pytest.mark.parametrize('mutation',['gpr','upper_vector','memory','code'])
def test_observed_wrong_effect_is_never_replaced_by_derived_result(mutation):
    before=state(0x199720);before['registers'].update(rax=0x4000,k1=0xffff)
    before['vectors']['zmm16']='00'*64
    after=copy.deepcopy(before);after['registers']['rip']=BASE+0x199726
    if mutation=='gpr':after['registers']['rbx']^=1
    if mutation=='upper_vector':after['vectors']['zmm31']='ff'*64
    executed=[]
    def read(address,size):return b'\x01' if mutation=='memory' and executed else bytes(size)
    with pytest.raises(ValueError):api().record_step(0x199720,
        '62e17f297f01' if mutation=='code' else CODES[0x199720],before,read,
        lambda:executed.append(1),lambda:after,BASE)
    assert after['registers']['rbx']==(before['registers']['rbx']^(mutation=='gpr'))

def test_undefined_flags_remain_actual_raw_bits():
    before=state(0x199717);before['registers'].update(rcx=0xffffffff,rdx=16)
    after=copy.deepcopy(before);after['registers'].update(rcx=0xffff,rip=BASE+0x19971c,
        eflags=(before['registers']['eflags']&~(1|64|128|2048|4|16))|4|16)
    row=api().record_step(0x199717,CODES[0x199717],before,
        lambda *args:pytest.fail('unexpected read'),lambda:None,lambda:after,BASE)
    assert row['after']['registers']['eflags']==after['registers']['eflags']
    assert row['defined_flags_mask']==0xffffffeb


def test_failed_state_comparison_preserves_actual_failed_row():
    before=state(0x1996c4);before['registers']['rsi']=0
    actual=copy.deepcopy(before);actual['registers']['rip']=BASE+0x1996ca
    actual['vectors']['zmm16']='ff'*64
    with pytest.raises(ValueError) as caught:
        api().record_step(0x1996c4,CODES[0x1996c4],before,
            lambda *args:pytest.fail('unexpected read'),lambda:None,lambda:actual,BASE)
    receipt=caught.value.diagnostic_receipt
    assert receipt['before']==before and receipt['after']==actual
    assert receipt['stage']=='compare-post-state'
    assert receipt['measurement_accepted'] is False


@pytest.mark.parametrize('where',['post-memory','post-state'])
def test_acquisition_exception_keeps_current_instruction_and_known_state(where):
    before=state(0x199720);before['registers'].update(rax=0x4000,k1=0xffff)
    before['vectors']['zmm16']='00'*64
    actual=copy.deepcopy(before);actual['registers']['rip']=BASE+0x199726
    ran=[]
    def read(*args):
        if ran and where=='post-memory':raise OSError('inaccessible written page')
        return b'\x00'
    def after():
        if where=='post-state':raise ValueError('raw x87 unavailable')
        return actual
    with pytest.raises(ValueError) as caught:
        api().record_step(0x199720,CODES[0x199720],before,read,lambda:ran.append(1),after,BASE)
    receipt=caught.value.diagnostic_receipt
    assert receipt['elf_pc']==0x199720 and receipt['before']==before
    assert len(receipt['attempted_writes'])==16
    assert receipt['after']==(actual if where=='post-memory' else None)
    assert receipt['measurement_accepted'] is False


def test_full_native_framing_is_consumed_by_both_graph_bridges(tmp_path,monkeypatch):
    from tests.test_v1_evex_graph_checker import graph_fixture
    from verified_driver.v1.native_evex_graph_producer import NativeEvexDataflow
    from verified_driver.v1.native_evex_graph_checker import graph
    capture,rows,regions,spans=graph_fixture(tmp_path,monkeypatch)
    region=regions[0]
    framed=[]
    for original in rows:
        native=original['native_evex']
        raw=dict(elf_pc=original['elf_address'],instruction_bytes=original['bytes'],**native,
            write_observations=original['possible_memory_writes'])
        row=api().frame_native(original['seq'],'init',
            dict(path=original['module_path'],sha256=original['module_sha256'],load_base=original['module_load_base']),
            {},0,original.get('instruction','actual byte-bound native form'),raw,owner=[123,123,0])
        assert row['pre']['extra_vectors']==row['post']['extra_vectors']=={}
        framed.append(row)
    # The two implementations consume the same raw sidecar. Framing grants no profile authority.
    flow=NativeEvexDataflow(framed,capture,__import__('pathlib').Path(__file__).resolve().parents[1],
        verified_spans=[dict(start_seq=0,end_seq=13)])
    assert flow.native_receipts[0]['write_count']==16
    # Independent bridge admission is exercised without pretending this is live Gala.
    from verified_driver.v1.native_evex_graph_checker import _native_spans
    assert len(_native_spans(framed,[region],[dict(start_seq=0,end_seq=13)]))==13
    # Consume the collector's actual framing through the entire independent
    # numerical/provenance graph, including implicit RET stack operands.
    ops, values, _ = graph(capture, framed, [region], tmp_path,
        [dict(start_seq=0, end_seq=13)])
    assert ops == []
    assert next(v for v in values if v['value_id']=='v:r1:zero')['width']==32
    assert next(v for v in values if v['value_id']=='v:r11:copy')['width']==16
    stack=framed[-1]['native_evex']['reads'][0]
    assert framed[-1]['operands']==[dict(kind='memory',address=stack['address'],width=8,
        raw_bits='0x'+bytes.fromhex(stack['bytes_hex'])[::-1].hex(),access='read')]
