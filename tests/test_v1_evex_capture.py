"""Complete raw state acquisition contracts; no actual numerical execution."""
import copy
import importlib.util
import pytest
from types import SimpleNamespace


def capture():
    assert importlib.util.find_spec('verified_driver.v1.native_evex_capture'), 'full-state recorder missing'
    from verified_driver.v1 import native_evex_capture
    return native_evex_capture


class Raw:
    def __init__(self, value=0, data=b''):
        self.value = value
        self.bytes = data if data else (value.to_bytes(4,'little',signed=value<0)
            if -2**31<=value<2**32 else b'')
        self.type=SimpleNamespace(code=8,sizeof=4,strip_typedefs=lambda:'int')
        self.is_optimized_out=False
    def __int__(self):
        return self.value


class Frame:
    def __init__(self):
        self.values = {name:Raw(0) for name in (
            'rax rbx rcx rdx rsi rdi rbp rsp r8 r9 r10 r11 r12 r13 r14 r15 rip '
            'eflags mxcsr fs_base gs_base k0 k1 k2 k3 k4 k5 k6 k7 '
            'fctrl fstat ftag fiseg fioff foseg fooff fop').split()}
        self.values['eflags']=Raw(0x202)
        self.values['mxcsr']=Raw(0x1f80)
        self.values.update({name: Raw(value=value) for name, value in
            dict(cs=0x33, ss=0x2b, ds=0, es=0, fs=0, gs=0).items()})
        for i in range(32):self.values['zmm'+str(i)]=Raw(data=bytes([i])*64)
        for i in range(8):self.values['st'+str(i)]=Raw(data=bytes([i+1])*10)
    def architecture(self):return SimpleNamespace(name=lambda:'i386:x86-64')
    def read_register(self,name):
        return self.values[name]


def test_complete_state_preserves_raw_x87_and_all_upper_vector_lanes():
    state=capture().collect_state(Frame(),dict(cet_ibt=False,cet_shstk=False))
    assert state['vectors']['zmm31']=='1f'*64
    assert state['fpu']['st7']=='08'*10
    assert state['registers']['mxcsr']==0x1f80
    assert state['unavailable']==[]
    assert set(state['vectors'])=={'zmm'+str(i) for i in range(32)}
    assert all('k'+str(i) in state['registers'] for i in range(8))


@pytest.mark.parametrize('field',['zmm31','k7','st7','fctrl','fop'])
def test_missing_required_state_refuses_instead_of_zero_fill(field):
    frame=Frame();del frame.values[field]
    with pytest.raises(ValueError):capture().collect_state(frame,dict(cet_ibt=False,cet_shstk=False))


@pytest.mark.parametrize('field,size',[('zmm16',32),('st0',8)])
def test_truncated_vector_or_float_raw_bits_refuses(field,size):
    frame=Frame();frame.values[field]=Raw(data=bytes(size))
    with pytest.raises(ValueError):capture().collect_state(frame,dict(cet_ibt=False,cet_shstk=False))


def test_cet_enabled_or_unknown_contract_refuses():
    for control in ({},{'cet_ibt':True,'cet_shstk':False},{'cet_ibt':False,'cet_shstk':None}):
        with pytest.raises(ValueError):capture().collect_state(Frame(),control)


def test_cpuid_cet_capability_not_kernel_feature_name_drives_refusal():
    mod=capture()
    assert mod.control_from_cpuid(0,0)==dict(cet_ibt=False,cet_shstk=False)
    with pytest.raises(ValueError):mod.control_from_cpuid(1<<7,0)
    with pytest.raises(ValueError):mod.control_from_cpuid(0,1<<20)
    with pytest.raises(ValueError):mod.control_from_cpuid(False,0)


def test_cpuid_unimplemented_leaf_cannot_prove_cet_absence():
    mod=capture()
    witness=dict(max_basic_leaf=6,leaf=7,subleaf=0,eax=0,ebx=0,ecx=0,edx=0,
        acquisition_code_hex='534989d089f889f10fa241890041895804418948084189500c5bc3')
    with pytest.raises(ValueError):mod.control_from_witness(witness)
    witness['max_basic_leaf']=7
    assert mod.control_from_witness(witness)==dict(cet_ibt=False,cet_shstk=False)
    witness['acquisition_code_hex']='c3'
    with pytest.raises(ValueError):mod.control_from_witness(witness)


def test_rf_cannot_be_captured_as_preserved_instruction_state():
    frame=Frame();frame.values['eflags']=Raw(0x202|(1<<16))
    with pytest.raises(ValueError,match='RF'):capture().collect_state(frame,dict(cet_ibt=False,cet_shstk=False))


@pytest.mark.parametrize('maximum,ecx,edx',[(6,0,0),(7,1<<7,0),(7,0,1<<20)])
def test_refused_cpuid_keeps_actual_sampled_words(maximum,ecx,edx):
    mod=capture();calls=[]
    def query(leaf,subleaf,data):
        calls.append((leaf,subleaf))
        words=(maximum,0x12345678,0x90abcdef,0x76543210) if leaf==0 else (0x1357,0xc0010100,ecx,edx)
        for i,value in enumerate(words):data[i]=value
    with pytest.raises(ValueError) as caught:mod.sample_control(query)
    receipt=caught.value.diagnostic_receipt
    assert receipt['leaf0']==dict(leaf=0,subleaf=0,eax=maximum,ebx=0x12345678,ecx=0x90abcdef,edx=0x76543210)
    if maximum==6:
        assert receipt['leaf7'] is None and calls==[(0,0)]
    else:
        assert receipt['leaf7']['ecx']==ecx and receipt['leaf7']['edx']==edx
    assert receipt['measurement_accepted'] is False


@pytest.mark.parametrize('field,stage,counts',[
    ('k7','registers',(28,0,0)),
    ('zmm31','vectors',(35,31,0)),
    ('fop','fpu_scalars',(35,32,7)),
    ('st7','fpu_stack',(35,32,15)),
])
def test_late_missing_register_keeps_all_actual_prior_context(field,stage,counts):
    # Dropping the receipt, clearing a partial bank, or inventing the missing
    # field must fail this check. The frame is a literal GDB boundary double.
    frame=Frame();del frame.values[field]
    control=dict(cet_ibt=False,cet_shstk=False)
    with pytest.raises(ValueError) as caught:capture().collect_state(frame,control)
    receipt=getattr(caught.value,'diagnostic_receipt',None)
    assert receipt is not None, 'late state acquisition lost actual partial context'
    assert isinstance(caught.value,capture().StateAcquisitionFailure)
    assert receipt['stage']==stage and receipt['failed_register']==field
    assert receipt['measurement_accepted'] is False
    assert receipt['exception_type']=='KeyError'
    partial=receipt['partial_context']
    assert set(partial)=={'registers','vectors','fpu','control','unavailable'}
    assert tuple(len(partial[k]) for k in ('registers','vectors','fpu'))==counts
    assert partial['registers']['eflags']==0x202
    assert partial['registers']['mxcsr']==0x1f80
    assert partial['control']==dict(cet_ibt=False,cet_shstk=False)
    assert field not in {**partial['registers'],**partial['vectors'],**partial['fpu']}
    assert receipt['unavailable']==partial['unavailable'] and field in receipt['unavailable']
    if stage!='registers':assert partial['vectors']['zmm30']=='1e'*64
    if stage=='fpu_stack':assert partial['fpu']['st6']=='07'*10
    if field=='st7':assert receipt['unavailable']==['st7']
    if field=='fop':assert receipt['unavailable']==['fop',*('st'+str(i) for i in range(8))]
    control['cet_ibt']=True
    assert partial['control']['cet_ibt'] is False


@pytest.mark.parametrize('field,value,stage',[
    ('k7',Raw(value=2**64),'registers'),
    ('zmm31',Raw(data=b'\xab'*32),'vectors'),
    ('fop',Raw(value=2**16),'fpu_scalars'),
    ('st7',Raw(data=b'\xcd'*8),'fpu_stack'),
])
def test_late_invalid_width_keeps_actual_sample_without_accepting_it(field,value,stage):
    frame=Frame();frame.values[field]=value
    with pytest.raises(ValueError) as caught:
        capture().collect_state(frame,dict(cet_ibt=False,cet_shstk=False))
    receipt=getattr(caught.value,'diagnostic_receipt',None)
    assert receipt is not None, 'invalid sampled width erased prior acquisition'
    assert receipt['stage']==stage and receipt['failed_register']==field
    assert receipt['measurement_accepted'] is False and receipt['exception_type']=='ValueError'
    partial=receipt['partial_context']
    bank='registers' if field=='k7' else 'vectors' if field=='zmm31' else 'fpu'
    expected=2**64 if field=='k7' else 'ab'*32 if field=='zmm31' else 2**16 if field=='fop' else 'cd'*8
    assert partial[bank][field]==expected
    assert partial['registers']['eflags']==0x202 and partial['registers']['mxcsr']==0x1f80
    assert field not in receipt['unavailable']
    if field=='st7':assert receipt['unavailable']==[]


def test_rf_domain_refusal_retains_actual_register_bank_and_unread_fields():
    frame=Frame();frame.values['eflags']=Raw(0x10202)
    with pytest.raises(ValueError) as caught:
        capture().collect_state(frame,dict(cet_ibt=False,cet_shstk=False))
    receipt=getattr(caught.value,'diagnostic_receipt',None)
    assert receipt is not None, 'RF refusal lost the actual acquired register bank'
    assert receipt['stage']=='register-domain-validation' and receipt['failed_register']=='eflags'
    assert receipt['partial_context']['registers']['eflags']==0x10202
    assert len(receipt['partial_context']['registers'])==35
    assert receipt['partial_context']['vectors']=={} and receipt['partial_context']['fpu']=={}
    assert 'eflags' not in receipt['unavailable'] and 'zmm0' in receipt['unavailable']
    assert receipt['measurement_accepted'] is False


SELECTOR_NAMES = ('cs', 'ss', 'ds', 'es', 'fs', 'gs')
SELECTOR_VALUES = dict(zip(SELECTOR_NAMES, (0x33, 0x2b, 0, 1, 0xfffe, 0xffff)))


def selector_frame():
    frame = Frame()
    frame.values.update({name: Raw(value=value) for name, value in SELECTOR_VALUES.items()})
    return frame


def test_acquisition_reads_actual_six_selectors_without_filling_defaults():
    frame = selector_frame()
    collected = capture().collect_state(frame, dict(cet_ibt=False, cet_shstk=False))
    assert {name: collected['registers'][name] for name in SELECTOR_NAMES} == SELECTOR_VALUES
    assert all(type(collected['registers'][name]) is int for name in SELECTOR_NAMES)
    assert collected['unavailable'] == []


@pytest.mark.parametrize('missing', SELECTOR_NAMES)
def test_missing_selector_keeps_prior_actual_selectors_and_unavailable_receipt(missing):
    frame = selector_frame()
    del frame.values[missing]
    with pytest.raises(ValueError) as caught:
        capture().collect_state(frame, dict(cet_ibt=False, cet_shstk=False))
    receipt = caught.value.diagnostic_receipt
    assert receipt['failed_register'] == missing
    assert receipt['measurement_accepted'] is False
    partial = receipt['partial_context']
    prior = SELECTOR_NAMES[:SELECTOR_NAMES.index(missing)]
    assert {name: partial['registers'][name] for name in prior} == {name: SELECTOR_VALUES[name] for name in prior}
    assert partial['registers']['eflags'] == 0x202
    assert partial['registers']['mxcsr'] == 0x1f80
    assert missing not in partial['registers']
    assert missing in receipt['unavailable']
    assert receipt['unavailable'] == partial['unavailable']
    assert set(SELECTOR_NAMES[SELECTOR_NAMES.index(missing):]) <= set(receipt['unavailable'])


@pytest.mark.parametrize('name', SELECTOR_NAMES)
@pytest.mark.parametrize('value', [-1, 1 << 16, True, False])
def test_selector_acquisition_refuses_out_of_width_or_boolean_actual_value(name, value):
    frame = selector_frame()
    # Boolean doubles are returned as booleans, so int(False) cannot silently
    # turn unavailable/invalid typed evidence into a valid selector zero.
    frame.values[name] = value if type(value) is bool else Raw(value=value)
    with pytest.raises(ValueError) as caught:
        capture().collect_state(frame, dict(cet_ibt=False, cet_shstk=False))
    receipt = caught.value.diagnostic_receipt
    assert receipt['failed_register'] == name
    assert receipt['measurement_accepted'] is False
    partial = receipt['partial_context']
    prior = SELECTOR_NAMES[:SELECTOR_NAMES.index(name)]
    assert {field: partial['registers'][field] for field in prior} == {field: SELECTOR_VALUES[field] for field in prior}
    assert partial['registers']['eflags'] == 0x202
    assert receipt['unavailable'] == partial['unavailable']
