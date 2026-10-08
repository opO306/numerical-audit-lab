"""TEST_ONLY raw83 authority linkage; fixture data grants no LIVE authority."""
import copy,hashlib,json,pytest
from pathlib import Path
from types import SimpleNamespace
from compute_metabolism.v0 import evex_profile as gate
from compute_metabolism.v0.scout_check import type_contract
from tests.test_compute_metabolism_gala_origin import fixture
from verified_driver.v1 import native_evex_capture as cap

def canonical(v):
    return (json.dumps(v,sort_keys=True,separators=(',',':'))+'\n').encode()
def sha(v):return hashlib.sha256(canonical(v)).hexdigest()
def contexts(doc):
    return [doc['caller'][n] for n in ['before','after_call','entry']]+[
        c for row in doc['native']['steps'] for c in [row['before'],row['after']]]+[doc['native']['exit']]
def field_map(context):
    fields={}
    for bank in ['registers','vectors','fpu']:
        for name,value in context[bank].items():
            width,code,typ=type_contract(name)
            raw=value if type(value) is str else value.to_bytes(width,'little').hex()
            fields[name]=dict(type_name=typ,type_code=code,width_bytes=width,raw_hex=raw,
                byte_order='little',is_optimized_out=False,is_unavailable=False)
    return fields
def acquisition(context):
    fields=field_map(context);scalars={}
    for name in cap.FP_SCALARS:
        raw=bytes.fromhex(fields[name]['raw_hex'])
        scalars[name]=dict(raw_hex=raw.hex(),type_name='int',type_code=8,width_bits=32,
            byte_order='little',signed_value=int.from_bytes(raw,'little',signed=True),
            unsigned_value=int.from_bytes(raw,'little'))
    ptr={}
    for label,lo,hi in [('instruction','fioff','fiseg'),('operand','fooff','foseg')]:
        raw=bytes.fromhex(fields[lo]['raw_hex']+fields[hi]['raw_hex'])
        ptr[label]=dict(low_register=lo,high_register=hi,raw_hex=raw.hex(),unsigned_value=int.from_bytes(raw,'little'))
    order=[*cap.GPRS,'eflags','mxcsr','fs_base','gs_base',*('k'+str(i) for i in range(8)),*cap.SELECTORS,*('zmm'+str(i) for i in range(32)),*cap.FP_SCALARS,*('st'+str(i) for i in range(8))]
    return dict(schema='gdb-amd64-x87-raw-v1',architecture='i386:x86-64',
        measurement_accepted=True,scalars=scalars,pointer_words=ptr,fields=fields,read_order=order)
def sample(tmp_path):
    doc,*_=fixture(tmp_path);cfg=dict(source_snapshot=doc['source_snapshot'],gdb_sha256='a'*64,result='/private/run1/raw')
    samples=[dict(sample_index=i,context_rip=c['registers']['rip'],context_sha256=sha(c),evidence=acquisition(c)) for i,c in enumerate(contexts(doc))]
    side=dict(schema='gala-state-acquisitions-v2',observation_sha256=sha(doc),observer_config_sha256=sha(cfg),
        source_binding=doc['source_binding'],process_identity=doc['process_identity'],thread_ptid=doc['thread_ptid'],
        gdb_sha256=cfg['gdb_sha256'],samples=samples)
    return side,doc,cfg
def test_raw83_becomes_mandatory_original_proof_role():
    assert 'state_acquisitions' in gate.FILE_ROLES
def test_all30_raw83_join_reaches_independent_state_checker(tmp_path):
    side,doc,cfg=sample(tmp_path)
    v=gate.verify_state_acquisitions(side,doc,cfg)
    assert v['sample_count']==30 and v['checked_fields_per_sample']==83 and v['verdict']=='PASS'
    assert v['numerical_certification'] is False
@pytest.mark.parametrize('attack',[
    'missing_field','damaged_raw','wrong_width','wrong_type','wrong_endian','unavailable','optimized',
    'context_value','context_hash','missing_sample','extra_sample','order','read_order','index_bool',
    'observation_hash','config_hash','source','different_pid','different_thread','different_gdb',
    'missing_proof','x87_signed','x87_unsigned','x87_raw','pointer_words'])
def test_raw83_mutations_refuse(tmp_path,attack):
    side,doc,cfg=sample(tmp_path);s=side['samples'][3];f=s['evidence']['fields']
    if attack=='missing_field':del f['zmm31']
    elif attack=='damaged_raw':f['rax']['raw_hex']='ff'
    elif attack=='wrong_width':f['rax']['width_bytes']=4
    elif attack=='wrong_type':f['rax']['type_name']='int'
    elif attack=='wrong_endian':f['rax']['byte_order']='big'
    elif attack=='unavailable':f['rax']['is_unavailable']=True
    elif attack=='optimized':f['rax']['is_optimized_out']=True
    elif attack=='context_value':doc['native']['steps'][0]['before']['registers']['rax']^=1
    elif attack=='context_hash':s['context_sha256']='b'*64
    elif attack=='missing_sample':side['samples'].pop()
    elif attack=='extra_sample':side['samples'].append(copy.deepcopy(s))
    elif attack=='order':side['samples'][0],side['samples'][1]=side['samples'][1],side['samples'][0]
    elif attack=='read_order':s['evidence']['read_order'].reverse()
    elif attack=='index_bool':s['sample_index']=True
    elif attack=='observation_hash':side['observation_sha256']='b'*64
    elif attack=='config_hash':side['observer_config_sha256']='b'*64
    elif attack=='source':side['source_binding']='b'*64
    elif attack=='different_pid':side['process_identity']=dict(side['process_identity'],pid=99)
    elif attack=='different_thread':side['thread_ptid']=[99,99,0]
    elif attack=='different_gdb':side['gdb_sha256']='b'*64
    elif attack=='missing_proof':del s['evidence']['scalars']
    elif attack=='x87_signed':s['evidence']['scalars']['fioff']['signed_value']+=1
    elif attack=='x87_unsigned':s['evidence']['scalars']['fooff']['unsigned_value']+=1
    elif attack=='x87_raw':s['evidence']['scalars']['fioff']['raw_hex']='93abcdef'
    elif attack=='pointer_words':s['evidence']['pointer_words']['instruction']['unsigned_value']+=1
    with pytest.raises((ValueError,KeyError,TypeError)):
        gate.verify_state_acquisitions(side,doc,cfg)
def test_same_read_records_metadata_for_all83(tmp_path):
    side,doc,cfg=sample(tmp_path);context=contexts(doc)[0];fields=field_map(context);calls=[]
    class Value:
        def __init__(self,n):
            row=fields[n];self.bytes=bytes.fromhex(row['raw_hex'])
            class Type:
                code=row['type_code'];sizeof=row['width_bytes']
                def __str__(self):return row['type_name']
                def strip_typedefs(self):return row['type_name']
            self.type=Type()
            self.is_optimized_out=False;self.is_unavailable=False
            self.name=n
        def __int__(self):
            raw=self.bytes
            return int.from_bytes(raw,'little',signed=self.name in cap.FP_SCALARS)
    class Frame:
        def architecture(self):return SimpleNamespace(name=lambda:'i386:x86-64')
        def read_register(self,n):calls.append(n);return Value(n)
    proof={};state=cap.collect_state(Frame(),dict(cet_ibt=False,cet_shstk=False),raw_evidence=proof)
    assert proof['fields']==fields and proof['read_order']==calls
    assert len(calls)==len(set(calls))==83 and state==context
def test_full30_evidence_fits_original_reservation(tmp_path):
    from compute_metabolism.v0 import gala_observer as observer
    side,*_=sample(tmp_path)
    assert len(canonical(side))<=observer.STATE_LIMIT
    worst=2*observer.CONFIG_LIMIT+3*1048576+2*observer.WRITES_LIMIT+4*observer.BIRTH_LIMIT+2*observer.STATE_LIMIT+observer.LAUNCH_LIMIT
    assert worst<=observer.RESERVATION_BYTES==16777216
