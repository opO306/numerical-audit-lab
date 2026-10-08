"""Independent pinned Gala CALL/PLT/GOT and finite native observation checker.

Inputs named ``expected_*`` are separately frozen caller authority inputs,
not copies chosen from the observation being checked. The caller obtains the
process birth from its owned acquisition/containment evidence. This checker
does not acquire a process, modify a registry, or grant numerical authority.
No producer/recorder imports or computed observation claims are trusted.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path, PurePosixPath
import re

from verified_driver.v1.native_evex_checker import (
    Refused, _address, _context, _elf, _hex, _typed_equal, _uint, verify_trace,
)


CALLER_SHA = 'a6ac98736304bb9f6a92e473bba45da10d9b5b99f8019e2ca15eb6a7f86234fc'
LIBC_SHA = '3a15d66867d83762c7f2f1e37359cb8f6c5743edb369c65285cb0b1c4f7498bf'
LIBC_BUILD_ID = 'a4a7992a8e66555c8141ab2a08a8465ff6e0ea65'
CALL_PC, CALL_CODE = 0x35689, 'e8c20cfdff'
PLT_PC, PLT_CODE, GOT_PC = 0x6350, 'ff253aae0300', 0x41190
NATIVE_PC = 0x1996c0
CPUID_CODE = '534989d089f889f10fa241890041895804418948084189500c5bc3'
FEATURE_BITS = {'avx512f':16,'avx512bw':30,'avx512vl':31,'bmi2':8}


def _need(ok,reason):
    if not ok:
        raise Refused('Gala origin: '+reason)


def _mode64(state):
    """Actual high instruction pointer excludes every 32-bit execution mode.

    Hidden CS.L/EFER bits are not claimed as direct observations. A completed
    userspace instruction at RIP above 32 bits witnesses 64-bit execution;
    the independently decoded finite near CALL/JMP/RET/ISA sequence contains
    no segment, descriptor, control-register or execution-mode write.
    """
    regs=state['registers']
    _uint(regs['rip'],64,'mode witness RIP')
    _uint(regs['cs'],16,'mode witness CS')
    _need(regs['rip']>0xffffffff and regs['cs']&3==3,
        'actual 64-bit userspace instruction pointer/CS witness')


def _canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode('ascii')


def _content(value):
    return hashlib.sha256(_canonical(value)).hexdigest()


def _keys(value,names,label):
    _need(type(value) is dict and set(value)==set(names),label+' exact keys')


def _file(path,label):
    _need(isinstance(path,(str,Path)),label+' path type')
    path=Path(path).resolve(strict=True)
    _need(path.is_file() and path.stat().st_size<=32*1024*1024,label+' bounded file')
    raw=path.read_bytes()
    return path,raw,hashlib.sha256(raw).hexdigest()


def _elf_bytes(raw,loads,address,size,executable):
    matches=[offset+address-vaddr for offset,vaddr,filesz,flags in loads
        if (not executable or flags&1) and vaddr<=address and address+size<=vaddr+filesz]
    _need(len(matches)==1,'unique file-backed ELF span')
    return raw[matches[0]:matches[0]+size]


def _sources(repo_root,observed,expected,binding):
    _need(type(expected) is dict and bool(expected) and _typed_equal(observed,expected),
        'separately frozen source snapshot')
    root=Path(repo_root).resolve(strict=True)
    _need(root.is_dir(),'source root directory')
    for name,want in expected.items():
        _need(type(name) is str and '\\' not in name,'POSIX source name')
        relative=PurePosixPath(name)
        _need(not relative.is_absolute() and '..' not in relative.parts and str(relative)==name,
            'unaliased relative source name')
        _hex(want,32,'source file hash')
        path=root.joinpath(*relative.parts)
        _need(not any(p.is_symlink() for p in (path,*path.parents)),'source alias')
        actual,raw,got=_file(path,'source')
        _need(actual.is_relative_to(root) and got==want,'current source bytes')
    _need(type(binding) is str and binding==_content(expected),'canonical source content ID')


def _process(observed,thread,expected):
    fields=('pid','linux_boot_id','proc_stat_start_time_ticks')
    _keys(observed,fields,'observed process identity')
    _keys(expected,fields,'frozen process identity')
    _need(_typed_equal(observed,expected),'independent owned process birth')
    for name in ('pid','proc_stat_start_time_ticks'):
        _uint(observed[name],64,name)
        _need(observed[name]>0,'positive process identity')
    _need(type(observed['linux_boot_id']) is str and re.fullmatch(
        '[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}',observed['linux_boot_id']) is not None,'Linux boot UUID')
    _need(type(thread) is list and len(thread)==3,'thread PTID')
    for value in thread:
        _uint(value,64,'PTID field')
    _need(thread[0]==observed['pid'] and thread[1]>0 and thread[2]==0,'same inferior owned thread')


def _control(witness,features):
    _keys(witness,('acquisition_code_hex','max_basic_leaf','leaf','subleaf','eax','ebx','ecx','edx'),
        'raw CPUID witness')
    _need(witness['acquisition_code_hex']==CPUID_CODE,'source-bound CPUID acquisition code')
    for name in ('max_basic_leaf','leaf','subleaf','eax','ebx','ecx','edx'):
        _uint(witness[name],32,'CPUID '+name)
    _need(witness['max_basic_leaf']>=7 and witness['leaf']==7 and witness['subleaf']==0,
        'positive CPUID leaf7 support')
    _need(not witness['ecx']&(1<<7) and not witness['edx']&(1<<20),'CET capability absent')
    _need(type(features) is list and all(type(name) is str for name in features) and
        len(features)==len(set(features)),'CPU feature set')
    _need(not {'ibt','user_shstk','shstk'}.intersection(features),'CET fingerprint contradicts absence witness')
    for name,bit in FEATURE_BITS.items():
        _need(witness['ebx']&(1<<bit) and name in features,'usable required CPU feature '+name)


def _state(state,label):
    _context(state)
    _need(state['registers']['eflags']&(1<<16)==0,label+' RF outside supported contract')


def verify_observation(document,repo_root,expected_fingerprint,expected_source_snapshot,
        library_path,caller_path,expected_process_identity):
    """Return a receipt only after deriving CALL, PLT, and all native effects.

    There is no SHA override or TEST_ONLY promotion path. Tests use hand states
    and the same pinned actual ELFs; such tests do not establish live execution.
    The receipt cannot register a profile or advance certified state by itself.
    """
    try:
        return _verify(document,repo_root,expected_fingerprint,expected_source_snapshot,
            library_path,caller_path,expected_process_identity)
    except Refused:
        raise
    except (KeyError,TypeError,ValueError,OSError,OverflowError) as exc:
        raise Refused('Gala origin: malformed or unavailable evidence: '+str(exc)) from exc


def _verify(doc,root,expected_fp,expected_sources,library_path,caller_path,expected_birth):
    _keys(doc,('schema','source_snapshot','source_binding','fingerprint','process_identity',
        'thread_ptid','control_witness','caller','native','termination'),'observation')
    _need(doc['schema']=='gala-native-observation-v1','observation schema')
    _need(len(_canonical(doc))<=2*1024*1024,'bounded raw observation')
    _need(type(expected_fp) is dict and _typed_equal(doc['fingerprint'],expected_fp),'frozen environment fingerprint')
    fp=expected_fp
    _need(fp['schema']=='COMPUTE_METABOLISM_FINGERPRINT_V1' and fp['cpu_arch']=='x86_64','native environment')
    _sources(root,doc['source_snapshot'],expected_sources,doc['source_binding'])
    _need(fp['v1_source_binding']==doc['source_binding'],'fingerprint/source authority seam')
    _process(doc['process_identity'],doc['thread_ptid'],expected_birth)
    _control(doc['control_witness'],fp['cpu_features'])
    libc_path,libc_raw,libc_sha=_file(library_path,'pinned libc')
    gala_path,gala_raw,gala_sha=_file(caller_path,'pinned Gala caller')
    _need(libc_sha==LIBC_SHA and gala_sha==CALLER_SHA,'fixed libc/Gala SHA authority')
    libc_loads,libc_id=_elf(libc_raw)
    gala_loads,gala_id=_elf(gala_raw)
    _need(libc_id==LIBC_BUILD_ID,'fixed libc GNU Build ID')
    for name,sha,bid in (('libc',libc_sha,libc_id),('gala',gala_sha,gala_id)):
        _need(fp[name]['sha256']==sha and fp[name]['build_id']==bid,'fingerprint pinned '+name)
    _need(fp['libc']['memset_elf_entry']==NATIVE_PC,'resolved IFUNC entry')
    caller=doc['caller']
    _keys(caller,('path','sha256','build_id','load_base','elf_pc','instruction_bytes','return_pc',
        'plt_elf_pc','plt_instruction_bytes','got_elf_address','got_address','got_bytes_hex',
        'before','after_call','entry','stack_write'),'actual caller')
    _need(type(caller['path']) is str and Path(caller['path']).resolve(strict=True)==gala_path,
        'actual caller ELF path')
    _need(caller['sha256']==gala_sha and caller['build_id']==gala_id,'actual caller identity')
    for key in ('load_base','elf_pc','return_pc','plt_elf_pc','got_elf_address','got_address'):
        _uint(caller[key],64,'caller '+key)
    base=caller['load_base']
    _need(caller['elf_pc']==CALL_PC and caller['instruction_bytes']==CALL_CODE,'fixed authorized Gala CALL site')
    _need(_elf_bytes(gala_raw,gala_loads,CALL_PC,5,True).hex()==CALL_CODE,'actual ELF CALL bytes')
    return_pc=base+CALL_PC+5
    _address(return_pc,1)
    target=return_pc+int.from_bytes(bytes.fromhex(CALL_CODE)[1:],'little',signed=True)
    _need(caller['return_pc']==return_pc and caller['plt_elf_pc']==PLT_PC and target==base+PLT_PC,
        'independently computed CALL rel32/return target')
    _need(caller['plt_instruction_bytes']==PLT_CODE and
        _elf_bytes(gala_raw,gala_loads,PLT_PC,6,True).hex()==PLT_CODE,'fixed actual ELF indirect PLT jump')
    got_address=base+PLT_PC+6+int.from_bytes(bytes.fromhex(PLT_CODE)[2:],'little',signed=True)
    _need(caller['got_elf_address']==GOT_PC and got_address==base+GOT_PC and caller['got_address']==got_address,
        'independently computed RIP-relative GOT address')
    _address(got_address,8)
    _elf_bytes(gala_raw,gala_loads,GOT_PC,8,False)
    native=doc['native']
    _uint(native['load_base'],64,'native libc load base')
    native_entry=native['load_base']+NATIVE_PC
    _address(native_entry,1)
    _need(int.from_bytes(_hex(caller['got_bytes_hex'],8,'GOT PRE pointer'),'little')==native_entry,
        'actual GOT read resolves only the finite pinned libc entry')
    before,after_call,entry=caller['before'],caller['after_call'],caller['entry']
    for value,label in ((before,'CALL pre'),(after_call,'CALL post'),(entry,'PLT post')):
        _state(value,label)
        _mode64(value)
    regs=before['registers']
    _need(regs['rip']==base+CALL_PC and regs['rsi']==0 and regs['rdx']==16,'actual Gala CALL PC/zero16 inputs')
    destination=regs['rdi'];_address(destination,16)
    _need(destination&0xfff<=0xfe0,'finite non-cross-page masked-store route')
    _need(regs['rsp']>=8,'CALL push underflow')
    push_address=regs['rsp']-8;_address(push_address,8)
    _need(not (destination<push_address+8 and push_address<destination+16),'destination aliases CALL/RET stack')
    _need(not (destination<got_address+8 and got_address<destination+16),'destination aliases GOT')
    stack=caller['stack_write']
    _keys(stack,('address','size','before_hex','after_hex'),'CALL stack write')
    _uint(stack['address'],64,'CALL push address')
    _need(type(stack['size']) is int and stack['size']==8 and stack['address']==push_address,'one exact CALL stack push')
    _hex(stack['before_hex'],8,'CALL stack before')
    _need(_hex(stack['after_hex'],8,'CALL stack after')==return_pc.to_bytes(8,'little'),'derived pushed return bytes')
    derived=deepcopy(before)
    derived['registers'].update(rsp=push_address,rip=target)
    _need(_typed_equal(derived,after_call),'CALL changes only complete RIP/RSP state')
    derived['registers']['rip']=native_entry
    _need(_typed_equal(derived,entry) and _typed_equal(native['entry'],entry),'PLT changes only RIP/full native entry seam')
    expected_domain=dict(provenance_kind='ACTUAL_GALA_CALL',source_sha256=doc['source_binding'],
        caller_module_sha256=gala_sha,caller_elf_pc=CALL_PC,caller_instruction_bytes=CALL_CODE,
        caller_return_pc=return_pc,caller_load_base=base,caller_path=caller['path'],caller_build_id=gala_id,
        destination=destination,length=16,fill=0,libc_sha256=libc_sha,libc_build_id=libc_id)
    result=verify_trace(native,libc_path,expected_domain)
    for step in native['steps']:
        _mode64(step['before'])
        _mode64(step['after'])
    _need(native['steps'][-1]['reads']==[dict(address=push_address,size=8,bytes_hex=stack['after_hex'])],
        'RET reads the actual CALL-produced stack bytes')
    _need(native['exit']['registers']['rsp']==regs['rsp'],'CALL/RET complete stack seam')
    termination=doc['termination']
    _keys(termination,('inferior_killed','remaining_owned_pids','certified_state_progress'),'termination')
    _need(termination['inferior_killed'] is True and type(termination['remaining_owned_pids']) is list and
        termination['remaining_owned_pids']==[] and termination['certified_state_progress'] is False,
        'noncertified owned inferior terminated')
    return dict(schema='gala-native-observation-check-v1',verdict='PASS',
        scope='ACTUAL_GALA_ORIGIN_AND_FINITE_NATIVE_EFFECTS',promotion_allowed=False,
        numerical_certification=False,formal_certification=False,certified_state_progress=False,
        canonical_encoding='SORTED_JSON_ASCII_NO_NEWLINE',
        checker_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        observation_sha256=_content(doc),source_binding=doc['source_binding'],
        fingerprint_sha256=_content(fp),process_identity=deepcopy(doc['process_identity']),
        thread_ptid=list(doc['thread_ptid']),caller_sha256=gala_sha,caller_build_id=gala_id,
        caller_elf_pc=CALL_PC,plt_elf_pc=PLT_PC,got_elf_address=GOT_PC,
        caller_return_pc=return_pc,libc_sha256=libc_sha,libc_build_id=libc_id,native=result,
        required_features=sorted(FEATURE_BITS),termination=deepcopy(termination))
