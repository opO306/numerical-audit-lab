"""Raw complete architectural state acquisition, without checker semantics.

The finite successful path requires CET capabilities absent. Missing state is
an acquisition refusal, never an implicit zero or a historical evidence repair.
"""
import ctypes
import mmap
import platform
from copy import deepcopy

GPRS=tuple('rax rbx rcx rdx rsi rdi rbp rsp r8 r9 r10 r11 r12 r13 r14 r15 rip'.split())
SELECTORS=('cs','ss','ds','es','fs','gs')
FP_SCALARS=tuple('fctrl fstat ftag fiseg fioff foseg fooff fop'.split())
CPUID_CODE='534989d089f889f10fa241890041895804418948084189500c5bc3'


class ControlAcquisitionFailure(ValueError):
    def __init__(self,message,receipt):
        super().__init__(message);self.diagnostic_receipt=deepcopy(receipt)


class StateAcquisitionFailure(ValueError):
    def __init__(self,message,receipt):
        super().__init__(message);self.diagnostic_receipt=deepcopy(receipt)


def sample_control(call):
    """Sample raw words before validation; refused capabilities stay evidence."""
    receipt=dict(stage='CPUID-leaf0',acquisition_code_hex=CPUID_CODE,
        leaf0=None,leaf7=None,measurement_accepted=False)
    data=(ctypes.c_uint32*4)()
    try:
        call(0,0,data)
        receipt['leaf0']=dict(leaf=0,subleaf=0,**dict(zip(('eax','ebx','ecx','edx'),map(int,data))))
        maximum=int(data[0])
        if maximum<7:raise ValueError('CPUID leaf7 unavailable')
        receipt['stage']='CPUID-leaf7'
        call(7,0,data)
        receipt['leaf7']=dict(leaf=7,subleaf=0,**dict(zip(('eax','ebx','ecx','edx'),map(int,data))))
        result=dict(max_basic_leaf=maximum,acquisition_code_hex=CPUID_CODE,**receipt['leaf7'])
        receipt['stage']='CPUID-capability-validation'
        return control_from_witness(result),result
    except Exception as exc:
        receipt.update(exception_type=type(exc).__name__,exception_message=str(exc))
        raise ControlAcquisitionFailure(str(exc),receipt) from exc


def control_from_cpuid(ecx,edx):
    for value in (ecx,edx):
        if type(value) is not int or not 0<=value<2**32:
            raise ValueError('raw CPUID leaf7 subleaf0 32-bit fields required')
    # Intel CPUID.7.0:ECX[7] CET shadow stack; EDX[20] CET IBT.
    if ecx&(1<<7) or edx&(1<<20):
        raise ValueError('CET-capable environment outside finite non-CET contract')
    return dict(cet_ibt=False,cet_shstk=False)


def control_from_witness(witness):
    if type(witness) is not dict or set(witness)!={
        'max_basic_leaf','leaf','subleaf','eax','ebx','ecx','edx','acquisition_code_hex'}:
        raise ValueError('complete CPUID witness required')
    for name in ('max_basic_leaf','leaf','subleaf','eax','ebx','ecx','edx'):
        if type(witness[name]) is not int or not 0<=witness[name]<2**32:
            raise ValueError('CPUID witness unsigned fields required')
    if (witness['max_basic_leaf']<7 or witness['leaf']!=7 or witness['subleaf']!=0
        or witness['acquisition_code_hex']!=CPUID_CODE):
        raise ValueError('implemented leaf7 and exact acquisition code required')
    return control_from_cpuid(witness['ecx'],witness['edx'])


def observe_control():
    """Read actual guest CPUID in the collector, preserving SysV RBX.

    The read-only environment query never calls code in the Gala inferior.
    Its exact code bytes and returned words are part of the source-bound proof.
    """
    if platform.system()!='Linux' or platform.machine()!='x86_64':
        raise ValueError('Linux x86-64 CPUID acquisition required')
    code=bytes.fromhex(CPUID_CODE)
    with mmap.mmap(-1,len(code),prot=mmap.PROT_READ|mmap.PROT_WRITE|mmap.PROT_EXEC) as page:
        page.write(code)
        address=ctypes.addressof(ctypes.c_char.from_buffer(page))
        call=ctypes.CFUNCTYPE(None,ctypes.c_uint32,ctypes.c_uint32,ctypes.POINTER(ctypes.c_uint32))(address)
        try:control,result=sample_control(call)
        finally:del call
    return control,result



def _x87_scalar(observed,name,evidence):
    """Decode the complete approved GDB AMD64 signed int32 representation.

    GDB 15.1 features/i386/64bit-core.xml describes all eight words as
    bitsize=32,type=int. amd64_supply_{f,x}save maps fiseg/foseg to the
    high words at offsets 12/20; fioff/fooff are the low words at 8/16.
    GDB Value.bytes supplies full value contents; on this approved little
    endian architecture no byte reversal, integer masking, or truncation
    is permitted. Coherence with signed conversion must hold before use.
    """
    row={};evidence[name]=row
    raw=observed.bytes
    row['raw_hex']=raw.hex() if type(raw) is bytes else None
    typ=observed.type.strip_typedefs()
    row.update(type_name=str(typ),type_code=observed.type.code,
        width_bits=observed.type.sizeof*8,byte_order='little')
    if (type(observed.type.code) is not int or observed.type.code!=8
        or type(observed.type.sizeof) is not int or observed.type.sizeof!=4
        or str(typ)!='int' or observed.is_optimized_out is not False
        or getattr(observed,'is_unavailable',False) is not False):
        raise ValueError('approved GDB signed int32 x87 type required: '+name)
    if type(raw) is not bytes or len(raw)!=4:
        raise ValueError('complete four raw x87 bytes required: '+name)
    signed=int(observed);row['signed_value']=signed
    if signed!=int.from_bytes(raw,'little',signed=True):
        raise ValueError('x87 signed value/raw bits disagreement: '+name)
    unsigned=int.from_bytes(raw,'little',signed=False)
    row['unsigned_value']=unsigned
    return unsigned


def _raw_field(observed,name,evidence):
    # Metadata and interpreted value come from the SAME register-read object.
    raw=observed.bytes
    if type(raw) is not bytes or observed.is_optimized_out is not False or getattr(observed,'is_unavailable',False) is not False:
        raise ValueError('complete original raw register required: '+name)
    evidence['fields'][name]=dict(type_name=str(observed.type),type_code=observed.type.code,
        width_bytes=observed.type.sizeof,raw_hex=raw.hex(),byte_order='little',
        is_optimized_out=False,is_unavailable=False)
    evidence['read_order'].append(name)


def collect_state(frame,control,*,raw_evidence=None):
    if (type(control) is not dict or set(control)!={'cet_ibt','cet_shstk'}
        or control['cet_ibt'] is not False or control['cet_shstk'] is not False):
        raise ValueError('positively established non-CET architectural contract required')
    if raw_evidence is not None and (type(raw_evidence) is not dict or raw_evidence):
        raise ValueError('exclusive empty acquisition evidence dictionary required')
    evidence={} if raw_evidence is None else raw_evidence
    evidence.update(schema='gdb-amd64-x87-raw-v1',measurement_accepted=False,
        scalars={},pointer_words={},fields={},read_order=[])
    registers={};vectors={};fpu={}
    register_names=(*GPRS,'eflags','mxcsr','fs_base','gs_base',*('k'+str(i) for i in range(8)),*SELECTORS)
    vector_names=tuple('zmm'+str(i) for i in range(32))
    stack_names=tuple('st'+str(i) for i in range(8))
    stage='registers';failed_register=None
    try:
        evidence['architecture']=frame.architecture().name()
        if evidence['architecture']!='i386:x86-64':
            raise ValueError('approved AMD64 register representation required')
        for name in register_names:
            failed_register=name
            observed=frame.read_register(name)
            if raw_evidence is not None:_raw_field(observed,name,evidence)
            if type(observed) is bool:
                registers[name]=observed
                raise ValueError('boolean architectural register sample: '+name)
            value=int(observed)
            registers[name]=value
            width=16 if name in SELECTORS else 32 if name in ('eflags','mxcsr') else 64
            if not 0<=value<(1<<width):
                raise ValueError('architectural register width: '+name)
        stage='register-domain-validation';failed_register='eflags'
        if registers['eflags']&(1<<16):
            raise ValueError('RF=1 outside supported finite instruction domain')
        stage='vectors'
        for name in vector_names:
            failed_register=name
            observed=frame.read_register(name)
            if raw_evidence is not None:_raw_field(observed,name,evidence)
            raw=bytes(observed.bytes)
            vectors[name]=raw.hex()
            if len(raw)!=64:raise ValueError('full raw ZMM required: '+name)
        stage='fpu_scalars'
        for name in FP_SCALARS:
            failed_register=name
            observed=frame.read_register(name)
            if raw_evidence is not None:_raw_field(observed,name,evidence)
            try:
                value=_x87_scalar(observed,name,evidence['scalars'])
            except Exception:
                row=evidence['scalars'].get(name,{})
                if 'signed_value' in row:fpu[name]=row['signed_value']
                raise
            fpu[name]=evidence['scalars'][name]['signed_value']
            if not 0<=value<(1<<(64 if name in ('fioff','fooff') else 16)):
                raise ValueError('raw x87 field width: '+name)
            fpu[name]=value
        for label,low,high in [('instruction','fioff','fiseg'),('operand','fooff','foseg')]:
            raw=bytes.fromhex(evidence['scalars'][low]['raw_hex']+
                evidence['scalars'][high]['raw_hex'])
            evidence['pointer_words'][label]=dict(low_register=low,high_register=high,
                raw_hex=raw.hex(),unsigned_value=int.from_bytes(raw,'little'))
        stage='fpu_stack'
        for name in stack_names:
            failed_register=name
            observed=frame.read_register(name)
            if raw_evidence is not None:_raw_field(observed,name,evidence)
            raw=bytes(observed.bytes)
            fpu[name]=raw.hex()
            if len(raw)!=10:raise ValueError('raw x87 80-bit state required: '+name)
    except Exception as exc:
        unavailable=[name for name in register_names if name not in registers]
        unavailable += [name for name in vector_names if name not in vectors]
        unavailable += [name for name in (*FP_SCALARS,*stack_names) if name not in fpu]
        # Diagnostics retain actual samples, including rejected widths. They
        # never fill unread fields or qualify as a complete accepted context.
        partial=dict(registers=registers,vectors=vectors,fpu=fpu,
            control=dict(control),unavailable=unavailable)
        receipt=dict(stage=stage,failed_register=failed_register,
            partial_context=partial,unavailable=unavailable,measurement_accepted=False,
            exception_type=type(exc).__name__,exception_message=str(exc),
            raw_x87_evidence=deepcopy(evidence))
        raise StateAcquisitionFailure('complete architectural state unavailable: '+str(exc),receipt) from exc
    evidence['measurement_accepted']=True
    return dict(registers=registers,vectors=vectors,fpu=fpu,control=dict(control),unavailable=[])
