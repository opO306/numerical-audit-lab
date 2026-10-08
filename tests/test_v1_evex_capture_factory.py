"""Literal native/caller states through a fake reviewed collector and GDB."""
import ast
import copy
import hashlib
import importlib
import json
import os
from pathlib import Path
import sys
import types

import pytest
from tests.test_v1_evex_graph_producer import fixture, BASE, LIBC

ROOT=Path(__file__).parents[1]
GALA='a6ac98736304bb9f6a92e473bba45da10d9b5b99f8019e2ca15eb6a7f86234fc'
GBASE=0x600000000000
BINDING=dict(profile_id='libc-memset-avx512-evex-16zero-v1',manifest_sha256='a'*64,source_binding='b'*64)


@pytest.fixture(autouse=True)
def guarded_quota(tmp_path,monkeypatch):
    """Fake Parent's trace allocation; real receipt quota arithmetic/file IO.

    Each fixture owns an exclusive single-process counter. Windows replaces
    only the unavailable POSIX lock primitive; WSL exercises actual flock.
    """
    path=tmp_path/'writer_quota.txt';path.write_text(str(512*1024*1024))
    monkeypatch.setenv('RTN_QUOTA_FILE',str(path))
    monkeypatch.setenv('RTN_QUOTA_BYTES',str(671088640))
    if os.name=='nt':
        monkeypatch.setitem(sys.modules,'fcntl',types.SimpleNamespace(LOCK_EX=2,flock=lambda *_:None))
    return path


def api():
    return importlib.import_module('verified_driver.v1.native_evex_collector')


class Register:
    def __init__(self,value,width=8):
        self.value,self.width=value,width
        self.type=types.SimpleNamespace(code=8,sizeof=width,strip_typedefs=lambda:'int')
        self.is_optimized_out=False
    def __int__(self):return self.value
    @property
    def bytes(self):
        return bytes.fromhex(self.value) if type(self.value) is str else self.value.to_bytes(self.width,'little',signed=self.value<0)


class FakeGDB:
    class SignalEvent:
        stop_signal='SIGSEGV'
    def __init__(self):
        capture,rows,region=fixture();self.capture,self.region=capture,region
        ret=GBASE+0x3568e
        rows[-1]['native_evex']['after']['registers']['rip']=ret
        rows[-1]['native_evex']['reads'][0]['bytes_hex']=ret.to_bytes(8,'little').hex()
        initial=copy.deepcopy(rows[0]['native_evex']['before'])
        call_before=copy.deepcopy(initial);call_before['registers'].update(rip=GBASE+0x35689,rsp=0x900008)
        call_after=copy.deepcopy(initial);call_after['registers']['rip']=GBASE+0x6350
        prefix=[dict(pc=0x35689,code='e8c20cfdff',assembly=f'call {GBASE+0x6350:x}',before=call_before,after=call_after,module='gala'),
                dict(pc=0x6350,code='ff253aae0300',assembly='jmp *0x3ae3a(%rip)',before=call_after,after=initial,module='gala')]
        self.instructions=prefix+[dict(pc=r['elf_address'],code=r['bytes'],assembly=r['opcode'],
            before=r['native_evex']['before'],after=r['native_evex']['after'],module='libc') for r in rows]
        self.index=0;self.state=copy.deepcopy(call_before);self.owner=(17,17,0);self.pid=17
        self.memory={0x20000+i:0 for i in range(16)}
        self.got=GBASE+0x41190
        self.memory.update({self.got+i:b for i,b in enumerate((BASE+0x1996c0).to_bytes(8,'little'))})
        self.memory.update({0x900000+i:b for i,b in enumerate(ret.to_bytes(8,'little'))})
        self.reads=[];self.step_count=0;self.on_step=None
    def newest_frame(self):return self
    def selected_thread(self):return types.SimpleNamespace(ptid=self.owner)
    def selected_inferior(self):return self
    def read_register(self,name):
        for part in ('registers','vectors','fpu'):
            if name in self.state[part]:return Register(self.state[part][name],4 if part=='fpu' and type(self.state[part][name]) is int else 8)
        raise ValueError(name)
    def architecture(self):return types.SimpleNamespace(name=lambda:'i386:x86-64',disassemble=self.disassemble)
    def disassemble(self,pc,count):
        ins=self.instructions[self.index];return [dict(length=len(bytes.fromhex(ins['code'])),asm=ins['assembly'])]
    def name(self):return 'memset'
    def read_memory(self,address,size):
        ins=self.instructions[self.index]
        if address==ins['before']['registers']['rip']:
            return bytes.fromhex(ins['code'])[:size]
        self.reads.append((address,size));return bytes(self.memory[address+i] for i in range(size))
    def execute(self,command,to_string=True):
        assert command=='stepi'
        ins=self.instructions[self.index]
        if ins['pc']==0x35689:
            value=(ins['before']['registers']['rip']+5).to_bytes(8,'little')
            self.memory.update({0x900000+i:b for i,b in enumerate(value)})
        if ins['pc']==0x199720:
            self.memory.update({0x20000+i:0 for i in range(16)})
        self.state=copy.deepcopy(ins['after']);self.index+=1;self.step_count+=1
        if self.on_step:self.on_step()
        return ''


def parent_for(gdb,out):
    # Execute the exact reviewed stream definition, with only fake GDB inputs.
    source=ROOT/'runtime_trace/regular_2step/gdb_acquire.py'
    node=next(n for n in ast.parse(source.read_text()).body if isinstance(n,ast.ClassDef) and n.name=='EnrichingStream')
    ns=dict(json=json,hashlib=hashlib,gdb=gdb)
    exec(compile(ast.Module(body=[node],type_ignores=[]),str(source),'exec'),ns)
    class Bounded:
        def __init__(self,raw):self.raw=raw;self.count=0
        def write(self,text):self.count+=len(text.encode());return self.raw.write(text)
        def flush(self):self.raw.flush()
        def close(self):self.raw.close()
        @property
        def closed(self):return self.raw.closed
    class Parent:
        def __init__(self):
            self.stream=ns['EnrichingStream'](self,Bounded((out/'trace.jsonl').open('x')))
            self.augmented_chain=self.chain='0'*64;self.row_extras=None;self.count=0
            self.histogram={};self.fp_count=0;self.known={};self.owner=gdb.owner
            self.process_identity=dict(pid=17);self.pre_memory_observation_count=0
            self.possible_memory_write_count=0;self.last_event=None;self.pending=None
            self.parent_steps=0
        def context(self,extras=()):return api().project_state(gdb.state)
        def module_at(self,pc):
            gala=GBASE<=pc<GBASE+0x100000
            module=dict(path='/gala/step.so' if gala else '/lib/libc.so.6',sha256=GALA if gala else LIBC,
                load_base=GBASE if gala else BASE,wheel_member='gala/step.so' if gala else None)
            return module,dict(start=module['load_base'],end=module['load_base']+0x300000,perms='r-xp')
        def file_slice(self,module,pc,size):return bytes.fromhex(gdb.instructions[gdb.index]['code']),pc-module['load_base']
        def keys(self,op):
            if op['kind']=='memory':return [('mem',op['address']+i) for i in range(op['width'])]
            name=op['register'];base='vector'+name[3:] if name.startswith('ymm') else name
            return [('reg',base,i) for i in range(op['width'])]
        def put(self,op,raw,origin,numeric=False):
            origins=origin if isinstance(origin,list) else [origin]*len(raw)
            for key,b,item in zip(self.keys(op),raw,origins):self.known[key]=(b,item,numeric)
        def origins(self,op,raw):
            return [self.known.get(k,(0,None,False))[1] for k in self.keys(op)]
        def forget_changed_gprs(self,before,after,exempt=()):
            for name in before['gpr']:
                if name=='rip' or name in exempt or before['gpr'][name]==after['gpr'][name]:continue
                keys=[('reg',name,i) for i in range(8)]
                if any(self.known.get(k,(0,None,False))[2] for k in keys):raise ValueError('numerical payload')
                for key in keys:self.known.pop(key,None)
        def one(self,phase):
            self.parent_steps+=1;ins=gdb.instructions[gdb.index];pre=self.context()
            module,mapping=self.module_at(pre['gpr']['rip'] and gdb.state['registers']['rip'])
            obs=[];writes=[]
            if ins['pc']==0x35689:writes=[dict(address=0x900000,size=8,kind='CALL_STACK',before_hex=gdb.read_memory(0x900000,8).hex())]
            if ins['pc']==0x6350:obs=[dict(address=gdb.got,size=8,kind='EXPLICIT',operand='0x3ae3a(%rip)',
                bytes_hex=gdb.read_memory(gdb.got,8).hex(),status='OK',timing='PRE_INSTRUCTION')]
            self.pre_memory_observation_count+=len(obs);self.possible_memory_write_count+=len(writes)
            self.row_extras=dict(occurrence=phase,pre_memory_observations=obs,possible_memory_writes=writes)
            gdb.execute('stepi');post=self.context()
            row=dict(seq=self.count,pid=17,ptid=list(self.owner),phase=phase,step=0,elf_address=ins['pc'],
                bytes=ins['code'],instruction=ins['assembly'],opcode=ins['assembly'].split()[0],kind='CONTROL',
                pre=pre,post=post,post_pc=gdb.state['registers']['rip'],runtime_pc=ins['before']['registers']['rip'],
                module_sha256=module['sha256'],module_path=module['path'],module_load_base=module['load_base'],
                elf_file_offset=ins['pc'],mapping=mapping,operands=[])
            self.stream.write(json.dumps(row)+'\n');self.stream.flush();self.row_extras=None
            self.count+=1;op=row['opcode'];self.histogram[op]=self.histogram.get(op,0)+1
    return Parent


@pytest.fixture
def setup(tmp_path,monkeypatch):
    from verified_driver.v1 import native_evex_capture as capture
    witness=dict(max_basic_leaf=7,leaf=7,subleaf=0,eax=0,ebx=0,ecx=0,edx=0,acquisition_code_hex=capture.CPUID_CODE)
    monkeypatch.setattr(capture,'observe_control',lambda:(dict(cet_ibt=False,cet_shstk=False),copy.deepcopy(witness)))
    gdb=FakeGDB();Parent=parent_for(gdb,tmp_path)
    cls=api().make_capture(Parent,gdb,BINDING);collector=cls()
    return collector,gdb,tmp_path,witness


def load_rows(out):return [json.loads(line) for line in (out/'trace.jsonl').read_text().splitlines()]


def test_actual_fifteen_rows_full_sidecars_zero32_copy16_and_chain(setup):
    c,gdb,out,witness=setup
    for _ in range(15):c.one('init')
    rows=load_rows(out)
    assert c.parent_steps==2 and c.count==15 and gdb.step_count==15
    assert c.native_spans==[dict(start_seq=2,end_seq=15)]
    assert c.native_evex_control_witness==witness and c.native_profile_binding==BINDING
    assert rows[0]['native_evex_caller']['writes']==[dict(address=0x900000,size=8,after_hex=(GBASE+0x3568e).to_bytes(8,'little').hex())]
    assert rows[1]['native_evex_caller']['reads']==[dict(address=gdb.got,size=8,bytes_hex=(BASE+0x1996c0).to_bytes(8,'little').hex())]
    assert rows[3]['result_bits']=='0x'+'00'*32
    assert rows[13]['result_bits']=='0x'+'00'*16
    assert len(rows[13]['possible_memory_writes'])==16
    assert all(w['value_changed'] is False for w in rows[13]['possible_memory_writes'])
    assert len(rows[-1]['pre_memory_observations'])==1
    assert c.pre_memory_observation_count==2 and c.possible_memory_write_count==17
    assert [c.known[('reg','vector16',i)][0] for i in range(32)]==[0]*32
    assert [c.known[('mem',0x20000+i)][0] for i in range(16)]==[0]*16
    assert all(c.known[('mem',0x20000+i)][1]=='record:13' for i in range(16))
    chain='0'*64
    for seq,row in enumerate(rows):
        assert row['seq']==seq
        assert row['pre']['extra_vectors']==row['post']['extra_vectors']=={}
        receipts=row['native_evex_state_acquisitions']
        assert receipts
        assert [r['sample_index'] for r in receipts]==list(range(len(receipts)))
        for receipt in receipts:
            assert receipt['trace_sequence']==seq and receipt['context_rip']>0
            assert receipt['evidence']['measurement_accepted'] is True
            assert set(receipt['evidence']['scalars'])==set('fctrl fstat ftag fiseg fioff foseg fooff fop'.split())
            assert all(len(r['raw_hex'])==8 for r in receipt['evidence']['scalars'].values())
        unsigned={k:v for k,v in row.items() if k!='chain'}
        chain=hashlib.sha256(bytes.fromhex(chain)+json.dumps(unsigned,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        assert row['chain']==chain
    assert c.augmented_chain==c.chain==chain
    assert c.stream.raw.raw.fileno()>=0
    assert sum(c.histogram.values())==15 and c.fp_count==0


@pytest.mark.parametrize('change',['escape','code','module','duplicate','signal','thread','post'])
def test_active_failure_preserves_current_diagnostic_before_refusal(setup,change):
    c,gdb,out,_=setup
    for _ in range(3):c.one('init')
    if change=='escape':gdb.state['registers']['rip']+=100
    if change=='code':gdb.instructions[gdb.index]['code']='62e27d287ac7'
    if change=='module':c.module_at=lambda _: (dict(path='/bad',sha256='f'*64,load_base=BASE),{})
    if change=='duplicate':gdb.state['registers']['rip']=BASE+0x1996c0
    if change=='signal':gdb.on_step=lambda:setattr(c,'last_event',gdb.SignalEvent())
    if change=='thread':gdb.on_step=lambda:setattr(gdb,'owner',(17,18,0))
    if change=='post':gdb.on_step=lambda:gdb.state['registers'].__setitem__('rbx',1)
    with pytest.raises(ValueError):c.one('init')
    receipt=json.loads((out/'native-diagnostic.json').read_text())
    assert receipt['measurement_accepted'] is False
    assert receipt['seq']==3 and receipt['before'] is not None
    assert len(load_rows(out))==3 and c.native_spans==[]


def test_numerical_gpr_payload_cannot_be_forgotten(setup):
    c,gdb,out,_=setup
    for _ in range(4):c.one('init')
    c.known[('reg','rax',0)]=(0,'numeric',True)
    with pytest.raises(ValueError,match='numerical payload'):c.one('init')
    assert (out/'native-diagnostic.json').is_file()
    assert len(load_rows(out))==4


@pytest.mark.parametrize('bad',[{},dict(BINDING,authority='VERIFIED'),dict(BINDING,profile_id='other'),
    dict(BINDING,manifest_sha256='A'*64),dict(BINDING,source_binding=True)])
def test_explicit_finite_profile_binding_required(tmp_path,bad):
    gdb=FakeGDB()
    with pytest.raises(ValueError):api().make_capture(parent_for(gdb,tmp_path),gdb,bad)


def test_caller_wrong_preserved_full_vector_refuses_before_row_hash(setup):
    c,gdb,out,_=setup
    gdb.on_step=lambda:gdb.state['vectors'].__setitem__('zmm31','ff'*64)
    with pytest.raises(ValueError):c.one('init')
    assert load_rows(out)==[]
    assert json.loads((out/'native-diagnostic.json').read_text())['after']['vectors']['zmm31']=='ff'*64


def test_native_entry_without_actual_caller_pair_refuses(setup):
    c,gdb,out,_=setup
    gdb.index=2;gdb.state=copy.deepcopy(gdb.instructions[2]['before'])
    with pytest.raises(ValueError):c.one('init')
    assert load_rows(out)==[] and (out/'native-diagnostic.json').is_file()


def test_collected_truth_consumed_by_independent_producer_storage_bridge(setup):
    from verified_driver.v1.native_evex_graph_producer import build_ir
    c,gdb,out,_=setup
    for _ in range(15):c.one('init')
    rows=load_rows(out)
    region=copy.deepcopy(gdb.region);region['end_seq']=15
    operations,values,terminal=build_ir(gdb.capture,rows,region,ROOT,verified_spans=c.native_spans)
    assert operations==[]
    zero=next(v for v in values if v['value_id']=='v:r3:zero')
    copyvalue=next(v for v in values if v['value_id']=='v:r13:copy')
    assert zero['width']==32 and zero['raw_bits']=='0x'+'00'*32
    assert copyvalue['width']==16 and copyvalue['raw_bits']=='0x'+'00'*16
    assert copyvalue['source_slices'][0]['value_id']=='v:r3:zero'
    assert copyvalue['source_slices'][0]['trace_sequence']==13
    assert [ref.value_id for ref in terminal['gradient']]==['v:r13:copy']*16


def test_ordinary_parent_row_passes_through_without_full_state_acquisition(setup,monkeypatch):
    c,gdb,out,_=setup
    for _ in range(15):c.one('init')
    before=copy.deepcopy(gdb.state);after=copy.deepcopy(before)
    after['registers']['rip']+=1
    gdb.instructions.append(dict(pc=0x3568e,code='90',assembly='nop',before=before,after=after,module='gala'))
    monkeypatch.setattr(c,'_full_state',lambda:pytest.fail('ordinary row requested full native state'))
    c.one('init')
    row=load_rows(out)[-1]
    assert row['seq']==15 and row['bytes']=='90' and row['instruction']=='nop'
    assert 'native_evex' not in row and 'native_evex_caller' not in row
    assert c.parent_steps==3 and c.count==16


def test_cpuid_refusal_follows_parent_stream_allocation_and_preserves_receipt(tmp_path,monkeypatch):
    from verified_driver.v1 import native_evex_capture as capture
    gdb=FakeGDB();Parent=parent_for(gdb,tmp_path)
    def fail():
        assert (tmp_path/'trace.jsonl').is_file()
        raise ValueError('unsupported CET CPU')
    monkeypatch.setattr(capture,'observe_control',fail)
    with pytest.raises(ValueError,match='unsupported CET CPU'):
        api().make_capture(Parent,gdb,BINDING)()
    receipt=json.loads((tmp_path/'native-diagnostic.json').read_text())
    assert receipt['stage']=='observe-control' and receipt['measurement_accepted'] is False
    assert (tmp_path/'trace.jsonl').read_bytes()==b''


def test_return_target_must_be_actual_gala_call_successor(setup):
    c,gdb,out,_=setup
    for _ in range(14):c.one('init')
    # Produce a semantically self-consistent RET to the wrong stack value.
    raw=(GBASE+0x3568f).to_bytes(8,'little')
    gdb.memory.update({0x900000+i:b for i,b in enumerate(raw)})
    gdb.instructions[-1]['after']['registers']['rip']=GBASE+0x3568f
    with pytest.raises(ValueError,match='CALL successor'):c.one('init')
    assert len(load_rows(out))==14 and c.native_spans==[]
    receipt=json.loads((out/'native-diagnostic.json').read_text())
    assert receipt['after']['registers']['rip']==GBASE+0x3568f


@pytest.mark.parametrize('stage',['frame','provenance','stream'])
def test_executed_store_evidence_survives_later_publication_failure(setup,monkeypatch,stage):
    c,gdb,out,_=setup
    for _ in range(13):c.one('init')
    gdb.memory.update({0x20000+i:0 if i==0 else 1 for i in range(16)})
    def fail(*_args,**_kwargs):raise ValueError('injected '+stage+' failure after actual store')
    if stage=='frame':monkeypatch.setattr(api(),'frame_native',fail)
    elif stage=='provenance':monkeypatch.setattr(c,'origins',fail)
    else:monkeypatch.setattr(c.stream.stream,'write',fail)
    with pytest.raises(api().AcquisitionFailure) as failed:c.one('init')
    receipt=json.loads((out/'native-diagnostic.json').read_bytes())
    assert len(load_rows(out))==13 and gdb.step_count==14
    samples=receipt['completed_native_step']['write_observations']
    assert samples==failed.value.diagnostic_receipt['completed_native_step']['write_observations']
    assert len(samples)==16 and [w['address'] for w in samples]==list(range(0x20000,0x20010))
    assert all(w['actual_after_hex']=='00' and w['after_hex']=='00' for w in samples)
    assert samples[0]['before_hex']=='00' and samples[0]['value_changed'] is False
    assert all(w['before_hex']=='01' and w['value_changed'] is True for w in samples[1:])
    assert receipt['acquired_memory'][-1]['write_observations']==samples


def test_failed_caller_full_post_keeps_actual_stack_pre_and_post_bytes(setup):
    c,gdb,out,_=setup
    gdb.memory.update({0x900000+i:0x11 for i in range(8)})
    gdb.on_step=lambda:gdb.state['vectors'].__setitem__('zmm31','ff'*64)
    with pytest.raises(api().AcquisitionFailure):c.one('init')
    receipt=json.loads((out/'native-diagnostic.json').read_bytes())
    caller=receipt['caller_acquisition']
    assert caller['pre_stack_hex']=='11'*8
    assert caller['write_observations']==[dict(address=0x900000,size=8,before_hex='11'*8,
        after_hex=(GBASE+0x3568e).to_bytes(8,'little').hex(),
        actual_after_hex=(GBASE+0x3568e).to_bytes(8,'little').hex(),value_changed=True,
        basis='DERIVED_ENABLED_STORE_WITH_ACTUAL_PRE_POST_BYTES')]
    assert receipt['acquired_memory'][0]['write_observations']==caller['write_observations']
    assert receipt['after']['vectors']['zmm31']=='ff'*64 and load_rows(out)==[]


def test_failed_got_resolution_keeps_actual_pre_read_before_caller_rejection(setup):
    c,gdb,out,_=setup;c.one('init')
    raw=(1).to_bytes(8,'little');gdb.memory.update({gdb.got+i:b for i,b in enumerate(raw)})
    with pytest.raises(api().AcquisitionFailure):c.one('init')
    receipt=json.loads((out/'native-diagnostic.json').read_bytes())
    assert receipt['caller_acquisition']['reads']==[dict(address=gdb.got,size=8,bytes_hex=raw.hex())]
    assert receipt['acquired_memory'][-1]['reads']==receipt['caller_acquisition']['reads']
    assert len(load_rows(out))==1 and gdb.step_count==1


def test_failure_diagnostic_charges_exact_canonical_receipt_bytes(setup,guarded_quota):
    c,_,out,_=setup;before=int(guarded_quota.read_text())
    with pytest.raises(api().AcquisitionFailure):c._save_failure(ValueError('실제 관측 실패'),dict(stage='literal'))
    raw=(out/'native-diagnostic.json').read_bytes()
    assert int(guarded_quota.read_text())-before==len(raw)
    assert raw==(json.dumps(json.loads(raw),sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()


def test_exhausted_shared_quota_denies_diagnostic_file_but_preserves_memory_receipt(setup,guarded_quota):
    c,gdb,out,_=setup
    for _ in range(13):c.one('init')
    guarded_quota.write_text(str(671088640))
    gdb.on_step=lambda:gdb.state['registers'].__setitem__('rbx',1)
    with pytest.raises(api().AcquisitionFailure) as failed:c.one('init')
    assert not (out/'native-diagnostic.json').exists()
    receipt=failed.value.diagnostic_receipt
    assert receipt['after']['registers']['rbx']==1
    assert len(receipt['attempted_writes'])==16
    assert 'exhausted' in receipt['diagnostic_write_error']
    assert int(guarded_quota.read_text())==671088640


def test_oversized_diagnostic_refuses_before_quota_or_file_write(setup,guarded_quota):
    c,_,out,_=setup;before=guarded_quota.read_bytes()
    with pytest.raises(api().AcquisitionFailure) as failed:c._save_failure(ValueError('x'*1048576))
    assert not (out/'native-diagnostic.json').exists() and guarded_quota.read_bytes()==before
    assert 'ceiling' in failed.value.diagnostic_receipt['diagnostic_write_error']


def test_trace_flush_failure_still_writes_quota_charged_actual_diagnostic(setup,monkeypatch,guarded_quota):
    c,gdb,out,_=setup
    for _ in range(13):c.one('init')
    def fail(*_args,**_kwargs):raise ValueError('injected trace flush failure')
    monkeypatch.setattr(c.stream,'flush',fail)
    before=int(guarded_quota.read_text())
    with pytest.raises(api().AcquisitionFailure) as failed:c.one('init')
    raw=(out/'native-diagnostic.json').read_bytes();receipt=json.loads(raw)
    assert receipt['trace_flush_error']=='injected trace flush failure'
    assert len(receipt['completed_native_step']['write_observations'])==16
    assert failed.value.diagnostic_receipt==receipt
    assert int(guarded_quota.read_text())-before==len(raw)


def test_late_post_state_acquisition_preserves_nested_partial_context_without_overwriting_instruction(setup):
    c,gdb,_,_=setup
    for _ in range(13):c.one('init')
    before=copy.deepcopy(gdb.state)
    nested=dict(stage='read-register',failed_register='zmm31',
        partial_context=dict(registers=dict(rax=0x20000,rip=BASE+0x199726),
            vectors=dict(zmm0='ab'*64),fpu={}),
        unavailable=['zmm31'],measurement_accepted=False)
    class LateStateFailure(ValueError):
        def __init__(self):
            super().__init__('late actual register unavailable')
            self.diagnostic_receipt=nested
    def collect_after():raise LateStateFailure()
    with pytest.raises(api().AcquisitionFailure) as failed:
        api().record_step(0x199720,'62e17f297f00',before,c._read,c._step,collect_after,BASE)
    receipt=failed.value.diagnostic_receipt
    assert receipt['acquisition_diagnostic']==nested
    assert receipt['stage']=='collect-post-state' and receipt['before']==before
    assert receipt['after'] is None and len(receipt['attempted_writes'])==16
    assert receipt['measurement_accepted'] is False
    nested['partial_context']['vectors']['zmm0']='ff'*64
    assert receipt['acquisition_diagnostic']['partial_context']['vectors']['zmm0']=='ab'*64
