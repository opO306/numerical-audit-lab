"""Raw x87 bits, actual signed GDB15.1 boundary; no Gala execution."""
from types import SimpleNamespace
import copy
import pytest
from verified_driver.v1 import native_evex_capture as capture

CONTROL = dict(cet_ibt=False, cet_shstk=False)

class Sample:
    def __init__(self, value=0, raw=None, kind=8, size=4, typename='int'):
        self.value=value
        self.bytes=(value.to_bytes(size,'little',signed=value<0) if raw is None else raw)
        self.type=SimpleNamespace(code=kind,sizeof=size)
        self.type.strip_typedefs=lambda: typename
        self.is_optimized_out=False
    def __int__(self): return self.value

class Frame:
    def __init__(self):
        self.values={n:0 for n in (*capture.GPRS,'eflags','mxcsr','fs_base','gs_base',
            *('k'+str(i) for i in range(8)),*capture.SELECTORS)}
        self.values.update(eflags=0x202,mxcsr=0x1f80,cs=0x33,ss=0x2b)
        self.values.update({n:Sample() for n in capture.FP_SCALARS})
        self.values.update({'zmm'+str(i):Sample(raw=bytes([i])*64) for i in range(32)})
        self.values.update({'st'+str(i):Sample(raw=bytes([i+1])*10) for i in range(8)})
    def architecture(self): return SimpleNamespace(name=lambda:'i386:x86-64')
    def read_register(self,n):
        v=self.values[n]
        if type(v) is int:
            return Sample(v,size=8 if n in capture.GPRS or n in ('fs_base','gs_base') or n.startswith('k') else 4)
        return v

def test_actual_negative_fioff_bits_are_unsigned_word_without_masking():
    f=Frame()
    f.values['fioff']=Sample(-1964020589,bytes.fromhex('936cef8a'))
    f.values['fiseg']=Sample(32672,bytes.fromhex('a07f0000'))
    s=capture.collect_state(f,CONTROL)
    assert s['fpu']['fioff']==0x8aef6c93
    assert s['fpu']['fiseg']==0x7fa0
    assert s['unavailable']==[]

@pytest.mark.parametrize('name',['fioff','fooff'])
@pytest.mark.parametrize('raw,signed,unsigned',[
    ('00000000',0,0),('ffffff7f',0x7fffffff,0x7fffffff),
    ('00000080',-0x80000000,0x80000000),('ffffffff',-1,0xffffffff),
    ('936cef8a',-1964020589,0x8aef6c93)])
def test_exact_all_32_bits_and_original_interpretation_are_recorded(name,raw,signed,unsigned):
    f=Frame();f.values[name]=Sample(signed,bytes.fromhex(raw));evidence={}
    s=capture.collect_state(f,CONTROL,raw_evidence=evidence)
    assert s['fpu'][name]==unsigned
    row=evidence['scalars'][name]
    assert row['raw_hex']==raw and row['signed_value']==signed and row['unsigned_value']==unsigned
    assert row['width_bits']==32 and row['byte_order']=='little'
    assert evidence['measurement_accepted'] is True
    assert set(evidence['scalars'])==set(capture.FP_SCALARS)

@pytest.mark.parametrize('field',capture.FP_SCALARS)
@pytest.mark.parametrize('attack',['truncated','oversized','type','width','signedness','raw_type','corrupt','missing'])
def test_invalid_metadata_missing_or_disagreeing_raw_bits_refuse(field,attack):
    f=Frame();sample=f.values[field]
    if attack=='truncated':sample.bytes=b'\x00'*3
    elif attack=='oversized':sample.bytes=b'\x00'*5
    elif attack=='type':sample.type.code=9
    elif attack=='width':sample.type.sizeof=8
    elif attack=='signedness':sample.type.strip_typedefs=lambda:'unsigned int'
    elif attack=='raw_type':sample.bytes=[0,0,0,0]
    elif attack=='corrupt':sample.bytes=b'\x01\x00\x00\x00'
    elif attack=='missing':del f.values[field]
    evidence={}
    with pytest.raises(ValueError):
        capture.collect_state(f,CONTROL,raw_evidence=evidence)
    assert evidence['measurement_accepted'] is False

@pytest.mark.parametrize('field',['fctrl','fstat','ftag','fiseg','foseg','fop'])
def test_existing_16_bit_finite_contract_is_not_widened(field):
    f=Frame();f.values[field]=Sample(0x10000)
    with pytest.raises(ValueError):capture.collect_state(f,CONTROL)

def test_unapproved_architecture_refuses():
    f=Frame();f.architecture=lambda:SimpleNamespace(name=lambda:'i386')
    with pytest.raises(ValueError):capture.collect_state(f,CONTROL)

@pytest.mark.parametrize('field',['zmm31','st7','k7','gs'])
def test_complete_state_still_required_after_signed_conversion(field):
    f=Frame();f.values['fioff']=Sample(-1964020589,bytes.fromhex('936cef8a'))
    del f.values[field]
    with pytest.raises(ValueError):capture.collect_state(f,CONTROL)

def test_raw_receipt_is_detached_from_state_and_preserves_pointer_words():
    f=Frame();f.values['fioff']=Sample(-1964020589,bytes.fromhex('936cef8a'))
    f.values['fiseg']=Sample(32672);e={}
    s=capture.collect_state(f,CONTROL,raw_evidence=e);frozen=copy.deepcopy(e)
    s['fpu']['fioff']=0
    assert e==frozen
    assert e['pointer_words']['instruction']==dict(low_register='fioff',high_register='fiseg',
        raw_hex='936cef8aa07f0000',unsigned_value=0x7fa08aef6c93)

def test_integer_conversion_failure_still_retains_original_bytes_and_type():
    class Unconvertible(Sample):
        def __int__(self): raise ValueError('integer unavailable')
    f=Frame();f.values['fioff']=Unconvertible(-1964020589,bytes.fromhex('936cef8a'));e={}
    with pytest.raises(capture.StateAcquisitionFailure) as caught:
        capture.collect_state(f,CONTROL,raw_evidence=e)
    row=caught.value.diagnostic_receipt['raw_x87_evidence']['scalars']['fioff']
    assert row['raw_hex']=='936cef8a' and row['type_name']=='int' and row['width_bits']==32
    assert 'signed_value' not in row
    assert e['measurement_accepted'] is False

def test_optimized_out_raw_sample_refuses():
    f=Frame();f.values['fioff'].is_optimized_out=True
    with pytest.raises(ValueError):capture.collect_state(f,CONTROL)

def test_unavailable_raw_sample_refuses():
    f=Frame();f.values['fooff'].is_unavailable=True
    with pytest.raises(ValueError):capture.collect_state(f,CONTROL)

def test_actual_success_sealer_retains_raw_sidecar_and_reaches_unchanged_origin_checker(tmp_path):
    import ast,json
    from pathlib import Path
    from compute_metabolism.v0.gala_observer import write_bounded,STATE_LIMIT
    from compute_metabolism.v0.adaptive import canonical
    from verified_driver.v1.model import content_id
    from tests.test_compute_metabolism_gala_origin import fixture,verify
    source=Path(__file__).parents[1]/'compute_metabolism/v0/gdb_gala_observer.py'
    node=next(n for n in ast.parse(source.read_text()).body
              if isinstance(n,ast.FunctionDef) and n.name=='seal_observation')
    ns=dict(hashlib=__import__('hashlib'),Path=Path,deepcopy=copy.deepcopy,write_bounded=write_bounded,canonical=canonical,content_id=content_id,STATE_LIMIT=STATE_LIMIT)
    exec(compile(ast.Module(body=[node],type_ignores=[]),str(source),'exec'),ns)
    rows=fixture(tmp_path);doc=copy.deepcopy(rows[0]);result={'old':True}
    evidence={};capture.collect_state(Frame(),CONTROL,raw_evidence=evidence)
    samples=[dict(sample_index=0,context_rip=doc['native']['entry']['registers']['rip'],evidence=evidence)]
    config=dict(result=str(tmp_path/'gala-result.json'),source_snapshot=doc['source_snapshot'],gdb_sha256='a'*64)
    ns['seal_observation'](result,config,doc['fingerprint'],doc['process_identity'],doc['thread_ptid'],
                          doc['control_witness'],doc['caller'],doc['native'],samples)
    assert result==doc
    rows=(result,*rows[1:])
    assert verify(rows)['native']['instruction_count']==13
    recorded=json.loads((tmp_path/'state-acquisitions.json').read_text())
    assert recorded['samples']==samples
    samples[0]['evidence']['scalars'].clear()
    assert recorded['samples'][0]['evidence']['scalars']

@pytest.mark.parametrize('failed',[False,True])
def test_observer_retains_raw_state_sidecar_after_scratch_cleanup(tmp_path,monkeypatch,failed):
    import hashlib,json,os
    from pathlib import Path
    from compute_metabolism.v0 import gala_observer as mod
    from runtime_trace.regular_nstep import resources
    monkeypatch.setattr(resources,'reserve_writer',lambda n:None)
    quota=tmp_path/'quota';quota.write_text('0')
    monkeypatch.setenv('RTN_QUOTA_FILE',str(quota))
    monkeypatch.setenv('RTN_QUOTA_BYTES',str(mod.WRITER_CEILING))
    monkeypatch.setattr(mod,'_identity',lambda *args:None)
    captured={};evidence={};capture.collect_state(Frame(),CONTROL,raw_evidence=evidence)
    raw=json.dumps(dict(schema='gala-state-acquisitions-v1',samples=[
        dict(sample_index=0,context_rip=0x1234,evidence=evidence)])).encode()
    def fake_run(args,env,timeout,cap):
        cfg=json.loads(Path(env['CM_GALA_OBSERVER_CONFIG']).read_bytes())
        scratch=Path(cfg['result']).parent;captured['scratch']=scratch
        Path(cfg['result']).write_text('{"diagnostic":{"stage":"TEST_ONLY"}}' if failed else '{}')
        (scratch/'state-acquisitions.json').write_bytes(raw)
        (scratch/'enabled-write-observations.json').write_text('[]')
        return dict(returncode=2 if failed else 0,stop_reason=None,stdout='',stderr='',diagnostic=None)
    monkeypatch.setattr(mod,'_run',fake_run)
    fp={n:dict(path='/prepared/'+n) for n in ('runtime','libc','gala')}
    mod.observe_gala(fp,tmp_path/'gala-observation.raw.json',Path(__file__).parents[1],
        gdb_sha256='a'*64,source_snapshot={})
    assert not captured['scratch'].exists()
    assert (tmp_path/'state-acquisitions.json').read_bytes()==raw
    launch=json.loads((tmp_path/'gala-launch.json').read_text())
    meta=launch['state_acquisition_evidence']
    assert meta['present'] is True and meta['truncated'] is False
    assert meta['retained_sha256']==hashlib.sha256(raw).hexdigest()
    assert launch['outcome']==('OBSERVATION_FAILED' if failed else 'OBSERVED_UNCERTIFIED')

@pytest.mark.parametrize('artifact',['absent','oversized'])
def test_missing_or_oversized_state_sidecar_cannot_report_success(tmp_path,monkeypatch,artifact):
    import json
    from pathlib import Path
    from compute_metabolism.v0 import gala_observer as mod
    from runtime_trace.regular_nstep import resources
    monkeypatch.setattr(resources,'reserve_writer',lambda n:None)
    quota=tmp_path/'quota';quota.write_text('0')
    monkeypatch.setenv('RTN_QUOTA_FILE',str(quota))
    monkeypatch.setenv('RTN_QUOTA_BYTES',str(mod.WRITER_CEILING))
    monkeypatch.setattr(mod,'_identity',lambda *args:None)
    def fake_run(args,env,timeout,cap):
        cfg=json.loads(Path(env['CM_GALA_OBSERVER_CONFIG']).read_bytes())
        Path(cfg['result']).write_text('{}')
        scratch=Path(cfg['result']).parent
        if artifact=='oversized':(scratch/'state-acquisitions.json').write_bytes(b'x'*(mod.STATE_LIMIT+1))
        return dict(returncode=0,stop_reason=None,stdout='',stderr='',diagnostic=None)
    monkeypatch.setattr(mod,'_run',fake_run)
    fp={n:dict(path='/prepared/'+n) for n in ('runtime','libc','gala')}
    mod.observe_gala(fp,tmp_path/'gala-observation.raw.json',Path(__file__).parents[1],gdb_sha256='a'*64,source_snapshot={})
    launch=json.loads((tmp_path/'gala-launch.json').read_text())
    assert launch['outcome']=='OBSERVATION_FAILED'
    if artifact=='oversized':
        assert (tmp_path/'state-acquisitions.json').stat().st_size==mod.STATE_LIMIT
        assert launch['state_acquisition_evidence']['truncated'] is True

def test_additional_raw_evidence_fits_original_writer_reservation():
    from compute_metabolism.v0 import gala_observer as mod
    worst=(2*mod.CONFIG_LIMIT+3*1024*1024+2*mod.WRITES_LIMIT+
        4*mod.BIRTH_LIMIT+2*mod.STATE_LIMIT+mod.LAUNCH_LIMIT)
    assert worst==int(14.25*1024*1024)
    assert worst<=mod.RESERVATION_BYTES==16*1024*1024
