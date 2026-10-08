"""Read-only independent scout departure checker; no profile/run authority."""
import hashlib,os,stat,re,struct
from pathlib import Path
from .adaptive import digest
from .source_epoch import validate_epoch
from .campaign import gate_source_snapshot
from .evex_profile import _executable_elf
from verified_driver.v1.native_evex_checker import _elf

NAMES=tuple('rax rbx rcx rdx rsi rdi rbp rsp r8 r9 r10 r11 r12 r13 r14 r15 rip eflags mxcsr fs_base gs_base'.split())+tuple('k'+str(i) for i in range(8))+tuple('cs ss ds es fs gs'.split())+tuple('fctrl fstat ftag fiseg fioff foseg fooff fop'.split())+tuple('st'+str(i) for i in range(8))+tuple('zmm'+str(i) for i in range(32))
SCALARS=set('fctrl fstat ftag fiseg fioff foseg fooff fop'.split())
GPRS=set('rax rbx rcx rdx rsi rdi rbp rsp r8 r9 r10 r11 r12 r13 r14 r15 rip'.split())
SELECTORS=set('cs ss ds es fs gs'.split())
CPUID='534989d089f889f10fa241890041895804418948084189500c5bc3'
XGETBV='31c90f01d048c1e2204809d0c3'
class Unknown(ValueError):pass
def need(value,reason):
    if not value:raise ValueError(reason)

def tool_elf(raw):
    # Prepared GDB is the separately pinned ET_EXEC executable.
    loads,bid=_executable_elf(raw)
    entry,phoff=struct.unpack_from('<QQ',raw,24)
    phsize,phnum=struct.unpack_from('<HH',raw,54)
    need(sum(bool(flags&1 and v<=entry<v+size) for _,v,size,flags in loads)==1,'GDB executable entry')
    interps=[]
    for i in range(phnum):
        kind,_,off,_,_,size,_,_=struct.unpack_from('<IIQQQQQQ',raw,phoff+i*phsize)
        if kind==3:
            need(2<=size<=256 and off+size<=len(raw),'GDB interpreter bounds')
            value=raw[off:off+size]
            need(value.endswith(b'\0') and b'\0' not in value[:-1],'GDB interpreter string')
            interps.append(value[:-1].decode('ascii'))
    need(interps==['/lib64/ld-linux-x86-64.so.2'],'GDB executable interpreter; DSO masquerade refused')
    return loads,bid

def literal_fxrestore():
    # Independently owned stimulus; no producer output defines checker truth.
    raw=bytearray(512)
    raw[:32]=bytes.fromhex('7f030000ff005604936cef8aa07f000098badcfe34120000801f0000ffff0000')
    for i in range(8):raw[32+i*16:42+i*16]=(0x8000000000000000+i).to_bytes(8,'little')+bytes.fromhex('ff3f')
    for i in range(16):raw[160+i*16:176+i*16]=bytes((i*17+j)%256 for j in range(16))
    return bytes(raw)

def preflight(policy,root):
    need(policy['schema']=='CPU_SCOUT_POLICY_V1' and policy['scope']=='TEST_ONLY','TEST_ONLY frozen policy')
    sources,binding=validate_epoch(policy['source_epoch'],root)
    need(binding==policy['source_binding'],'runner/checker V1 source mismatch')
    need(gate_source_snapshot(root,policy['source_epoch'])==policy['gate_source_snapshot'],'runner/checker gate source mismatch')
    registry=Path(root)/'compute_metabolism/v0/execution_profiles/registry.json'
    need(hashlib.sha256(registry.read_bytes()).hexdigest()==policy['registry_sha256'],'registry authority drift')
    need(type(policy['historical_candidates']) is list and len(policy['historical_candidates'])<=16,'bounded historical candidates')
    for ref in policy['historical_candidates']:
        f=Path(ref['path']);need(f.is_absolute() and all(not q.is_symlink() for q in (f,*f.parents)),'candidate path alias')
        info=f.stat();need(stat.S_ISREG(info.st_mode) and info.st_nlink==1 and info.st_size<=2097152,'bounded candidate history')
        need(hashlib.sha256(f.read_bytes()).hexdigest()==ref['sha256'],'historical candidate drift')
    need(type(policy['uid']) is int and type(policy['gid']) is int,'execution identity integers')
    need(type(policy['cpus']) is list and policy['cpus'] and policy['cpus']==sorted(set(policy['cpus']))
        and all(type(x) is int and 0<=x<4096 for x in policy['cpus']),'bounded exact CPU set')
    need(policy['memory_bytes']==4294967296 and policy['max_wall_seconds']==30 and policy['max_path_steps']==128
        and policy['max_output_bytes']==2097152,'fixed scout limits')
    directory=Path(policy['execution_directory'])
    need(directory.is_absolute() and all(not p.is_symlink() for p in (directory,*directory.parents)),'execution path alias')
    info=directory.lstat()
    need(stat.S_ISDIR(info.st_mode) and (info.st_uid,info.st_gid)==(policy['uid'],policy['gid'])
        and stat.S_IMODE(info.st_mode)==0o700,'execution folder ownership/private permissions mismatch')
    need([info.st_dev,info.st_ino,info.st_uid,info.st_gid,stat.S_IMODE(info.st_mode)]==policy['directory_identity'],'execution directory replacement')
    need(set(policy['binaries'])=={'runtime','libc','gala','gdb'},'exact actual binary roles')
    for name,item in policy['binaries'].items():
        role='EXECUTABLE' if name=='runtime' else 'TOOL' if name=='gdb' else 'SHARED_LIBRARY'
        need(item['role']==role,'executable/shared-library role confusion')
        p=Path(item['path']);concrete=p.resolve(strict=True)
        need(str(concrete)==item['resolved_path'],'binary resolved target replaced')
        before=concrete.stat();need(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and before.st_size<=64*1024*1024,'bounded unaliased ELF file')
        need(before.st_mode&0o111,'actual ELF execute permissions')
        raw=concrete.read_bytes();after=concrete.stat()
        identity=lambda s:[s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]
        need(type(item['file_identity']) is list and len(item['file_identity'])==5 and all(type(x) is int for x in item['file_identity']),'strict binary file identity')
        need(identity(before)==identity(after)==item['file_identity'] and p.resolve(strict=True)==concrete,'binary file replacement')
        need(hashlib.sha256(raw).hexdigest()==item['sha256'],'actual file hash drift')
        loads,bid=(_executable_elf(raw) if role=='EXECUTABLE' else tool_elf(raw) if role=='TOOL' else _elf(raw))
        need(bid==item['build_id'],'actual Build-ID drift')

def resource_map(env,policy):
    cg=env.get('cgroup') or {};rows=cg.get('ancestors')
    if not rows:raise Unknown('effective cgroup resource map unavailable')
    need(type(rows) is list and len(rows)<=64,'bounded resource ancestry')
    origin=[v[3:] for v in cg.get('raw','').splitlines() if v.startswith('0::')]
    need(len(origin)==1 and origin[0].startswith('/') and '..' not in Path(origin[0]).parts,'cgroup origin')
    first=Path('/sys/fs/cgroup')/origin[0].lstrip('/')
    expected=[str(first),*[str(p) for p in first.parents if p==Path('/sys/fs/cgroup') or Path('/sys/fs/cgroup') in p.parents]]
    need([r['path'] for r in rows]==expected,'complete cgroup ancestor map')
    result={}
    for name in ['cpu.max','memory.max','memory.swap.max','cpuset.cpus.effective']:
        values=[r.get(name) for r in rows if r.get(name) is not None]
        if not values:raise Unknown('effective cgroup '+name+' unavailable')
        need(all(type(v) is str and 0<len(v)<=65536 for v in values),'bounded resource values')
        result[name]=values
        for value in values:
            value=value.strip()
            if name=='cpu.max':
                parts=value.split()
                need(len(parts)==2 and parts[1].isdigit() and int(parts[1])>0
                    and (parts[0]=='max' or parts[0].isdigit() and int(parts[0])>0),'CPU quota syntax')
                if parts[0]!='max':need(int(parts[0])>=len(policy['cpus'])*int(parts[1]),'insufficient effective CPU quota')
            elif name in ['memory.max','memory.swap.max']:
                need(value=='max' or value.isdigit(),'memory controller syntax')
                if name=='memory.max' and value!='max':need(int(value)>=policy['memory_bytes'],'insufficient effective memory')
            else:
                available=set()
                for part in value.split(','):
                    bounds=part.split('-')
                    need(1<=len(bounds)<=2 and all(x.isdigit() for x in bounds),'cpuset syntax')
                    lo=int(bounds[0]);hi=int(bounds[-1])
                    need(0<=lo<=hi<4096,'bounded cpuset')
                    available.update(range(lo,hi+1))
                need(set(policy['cpus'])<=available,'effective cpuset excludes required CPU')
    return dict(observed_controls=result,formal_campaign_resource_certification=False)

def type_contract(name):
    if name.startswith('zmm'):return 64,4,'union builtin_type_vec512i'
    if name.startswith('st'):return 10,9,'builtin_type_i387_ext'
    if name in SCALARS:return 4,8,'int'
    if name in SELECTORS:return 4,8,'int32_t'
    if name in ['rbp','rsp']:return 8,1,'void *'
    if name=='rip':return 8,1,'void (*)()'
    if name in GPRS:return 8,8,'int64_t'
    if name.startswith('k'):return 8,8,'uint64_t'
    if name in ['fs_base','gs_base']:return 8,8,'long'
    return 4,6,'i386_'+name

def cpu(samples,policy):
    if not samples:raise Unknown('CPU/OS raw samples unavailable')
    need([x['cpu'] for x in samples]==policy['cpus'],'CPU sample coverage mismatch')
    findings=[]
    for sample in samples:
        leaves=sample['leaves'];need(set(leaves)=={'0','1','7','13'},'exact CPUID leaf coverage')
        for word in leaves.values():
            need(set(word)=={'eax','ebx','ecx','edx'} and all(type(x) is int and 0<=x<2**32 for x in word.values()),'raw CPUID word/type')
        if leaves['0']['eax']<13:raise Unknown('required CPUID leaf unavailable')
        a=leaves['1']['ecx'];b=leaves['7']['ebx'];c=leaves['7']['ecx'];d=leaves['7']['edx']
        hardware=dict(xsave=bool(a&(1<<26)),avx=bool(a&(1<<28)),avx2=bool(b&(1<<5)),
            bmi2=bool(b&(1<<8)),erms=bool(b&(1<<9)),avx512f=bool(b&(1<<16)),
            avx512bw=bool(b&(1<<30)),avx512vl=bool(b&(1<<31)),cet_shstk=bool(c&(1<<7)),cet_ibt=bool(d&(1<<20)))
        x=sample['xcr0'];osxsave=bool(a&(1<<27))
        if not osxsave or x is None:raise Unknown('OS XCR0 unavailable; not inferred from model name')
        need(type(x) is int and 0<=x<2**64,'XCR0 raw width/type')
        supported=leaves['13']['eax']+(leaves['13']['edx']<<32)
        need(x & ~supported==0,'XCR0 unsupported bits')
        usable=hardware['xsave'] and hardware['avx'] and all(hardware[k] for k in ['avx512f','avx512bw','avx512vl','bmi2']) and x&0xe7==0xe7
        if not usable:raise Unknown('finite AVX512 state/path not CPU+OS usable')
        need(not hardware['cet_ibt'] and not hardware['cet_shstk'],'CET outside unchanged finite capture domain')
        findings.append(dict(cpu=sample['cpu'],hardware=hardware,os=dict(osxsave=osxsave,xcr0=x,avx512_state_enabled=x&0xe7==0xe7,unscouted_enabled_bits=x&~0xe7)))
    return findings

def state(fields,context):
    if set(fields)!=set(NAMES):raise Unknown('missing complete raw83 register coverage')
    need(set(context['registers'])==set(NAMES[:35]) and set(context['fpu'])==set(NAMES[35:51])
        and set(context['vectors'])==set(NAMES[51:]),'exact per-group context83 field set')
    need(context['unavailable']==[] and context['control']==dict(cet_ibt=False,cet_shstk=False),'complete finite control/state')
    for name in NAMES:
        meta=fields[name];width,code,typename=type_contract(name)
        need(type(meta['width_bytes']) is int and meta['width_bytes']==width and type(meta['type_code']) is int
            and meta['type_code']==code and meta['type_name']==typename,'GDB register width/type: '+name)
        raw=meta['raw_hex'];need(type(raw) is str and re.fullmatch('[0-9a-f]{'+str(width*2)+'}',raw) is not None,'complete register raw bytes: '+name)
        group=next(g for g in ['registers','fpu','vectors'] if name in context[g])
        value=context[group][name];expected=raw if name.startswith('zmm') or name.startswith('st') else int.from_bytes(bytes.fromhex(raw),'little')
        need(type(value) is type(expected) and value==expected,'raw/state register mismatch: '+name)
        if name in SELECTORS or name in SCALARS-{'fioff','fooff'}:need(value<2**16,'original finite16 range: '+name)
    need(not context['registers']['eflags']&(1<<16),'RF outside finite state')

def verify(document,policy,root,*,require_path=True):
    verdict=dict(schema='CPU_SCOUT_VERDICT_V1',status='SCOUT_REFUSED',scope='TEST_ONLY',
        body_allowed=False,numerical_certification=False,profile_promotion=False,certified_state_progress=False,
        checked_fields=0,unknown=[],reasons=[],cpu=[],actual_path=None)
    try:
        preflight(policy,root)
        need(document['schema']=='CPU_SCOUT_BUNDLE_V1' and document['scope']=='TEST_ONLY'
            and document['policy_sha256']==digest(policy),'frozen scout request binding')
        for key in ['body_allowed','numerical_certification','profile_promotion','certified_state_progress']:
            need(document[key] is False,'self-issued run/profile authority')
        need('status' not in document,'producer may not self-issue departure verdict')
        if document.get('failure'):raise ValueError(document['failure']['reason'])
        if document.get('unknown'):raise Unknown('; '.join(document['unknown']))
        raw=document.get('probe')
        if raw is None:raise Unknown('CPU state acquisition unavailable')
        env=document.get('environment')
        if env is None:raise Unknown('environment map unavailable')
        need(raw['schema']=='CPU_SCOUT_GDB_RAW_V1' and raw['Gala'] is False and raw['test_only'] is True,'current TEST_ONLY raw schema; no Gala relabeling')
        need(raw['gdb_version']==policy['gdb_version'] and raw['architecture']=='i386:x86-64','approved GDB architecture/version')
        need(raw['cpuid_code_hex']==CPUID and raw['xgetbv_code_hex']==XGETBV,'exact CPU/OS acquisition code')
        need(type(raw['uid']) is int and type(raw['gid']) is int and raw['uid']==policy['uid'] and raw['gid']==policy['gid'],'GDB user mismatch')
        need(type(raw['affinity']) is list and all(type(x) is int for x in raw['affinity']) and raw['affinity']==policy['cpus'] and raw['rlimit_as']==[policy['memory_bytes']]*2,'GDB CPU/memory envelope')
        need(raw['cwd']==policy['execution_directory'],'GDB execution directory mismatch')
        verdict['cpu']=cpu(raw['cpu_samples'],policy)
        if raw.get('unknown'):raise Unknown('; '.join(raw['unknown']))
        verdict['resources']=resource_map(env,policy)
        fp=env['fingerprint'];need(fp['cpu_arch']=='x86_64' and fp['v1_source_binding']==policy['source_binding'],'environment/source seam')
        for name in ['libc','gala','runtime']:
            need(all(fp[name][k]==policy['binaries'][name][k] for k in ['path','sha256','build_id']),'environment binary identity seam')
        if policy['expected_entry'] is not None:need(fp['libc']['memset_elf_entry']==policy['expected_entry'],'CPU resolved execution path mismatch')
        need(type(env['kernel']['release']) is str and env['kernel']['release'] and env['kernel']['boot_id'],'kernel/boot identity')
        need(type(env['cgroup']) is dict and env['cgroup'],'resource map unavailable')
        for feature in ['avx512f','avx512bw','avx512vl','bmi2']:
            need(feature in env['kernel']['cpu_flags'],'kernel feature exposure contradiction')
        state(raw['fields'],raw['state']);state(raw['seeded_fields'],raw['seeded_state'])
        need(raw['fixture_sha256']=='0bc06d472e38b2e5adab0d1fc7e120211a393bdcd7ad767b8d70c82ce7fa5785','independent literal fixture identity')
        fx=bytes.fromhex(raw['fxsave_hex']);initial=bytes.fromhex(raw['input_fxrestore_hex'])
        need(len(fx)==len(initial)==512 and initial==literal_fxrestore(),'literal FXRESTORE input')
        for name,off,size in [('fctrl',0,2),('fstat',2,2),('fop',6,2),('fioff',8,4),('fiseg',12,4),('fooff',16,4),('foseg',20,4)]:
            need(raw['state']['fpu'][name]==int.from_bytes(fx[off:off+size],'little')
                and fx[off:off+size]==initial[off:off+size],'hardware x87 offset: '+name)
        need(raw['state']['fpu']['ftag']==0 and fx[4]==initial[4]==0xff,'literal full/abridged x87 tag')
        need(raw['state']['registers']['mxcsr']==int.from_bytes(fx[24:28],'little')
            and fx[24:28]==initial[24:28],'hardware MXCSR raw/literal coherence')
        for i in range(8):
            need(raw['state']['fpu']['st'+str(i)]==fx[32+16*i:42+16*i].hex()
                and fx[32+16*i:42+16*i]==initial[32+16*i:42+16*i],'hardware x87 raw80')
        for i in range(16):need(raw['state']['vectors']['zmm'+str(i)][:32]==fx[160+16*i:176+16*i].hex()
            and fx[160+16*i:176+16*i]==initial[160+16*i:176+16*i],'hardware XMM bits')
        for receipt in [raw['raw_evidence'],raw['seeded_raw_evidence']]:
            need(receipt['measurement_accepted'] is True and receipt['architecture']=='i386:x86-64','accepted x87 acquisition receipt')
            need(set(receipt['scalars'])==SCALARS,'complete eight x87 words')
            for name,row in receipt['scalars'].items():
                need(row['type_name']=='int' and row['type_code']==8 and row['width_bits']==32 and row['byte_order']=='little','x87 interpretation basis')
                bits=bytes.fromhex(row['raw_hex']);need(len(bits)==4,'x87 raw4')
                need(row['signed_value']==int.from_bytes(bits,'little',signed=True) and row['unsigned_value']==int.from_bytes(bits,'little'),'x87 signed/raw coherence')
                need(row['raw_hex']==raw['fields'][name]['raw_hex'],'x87 raw receipt/field seam')
            for label,offset in [('instruction',8),('operand',16)]:
                row=receipt['pointer_words'][label];need(row['raw_hex']==fx[offset:offset+8].hex() and row['unsigned_value']==int.from_bytes(fx[offset:offset+8],'little'),'full FIP/FDP raw8')
        pc=0x7fa08aef6c90;k=raw['kernel_roundtrip']
        need(k['nop_instructions']==2 and k['pc_before']==pc and k['pc_after']==pc+2
            and k['register_cache_invalidated_by_inferior_resume'] is True,'exact two-NOP kernel refetch')
        need(raw['state']['registers']['rip']==pc and raw['seeded_state']['registers']['rip']==pc+2,'raw two-NOP PC')
        need(k['nop_code_hex']=='9090','literal NOP opcode bytes')
        need(set(raw['disposable_register_stimuli'])=={*('zmm'+str(i) for i in range(32)),*('k'+str(i) for i in range(8))},'complete finite literal stimulus')
        for name in NAMES:
            if name.startswith('zmm'):
                i=int(name[3:]);expected=bytes((i*7+j*13+1)%256 for j in range(64)).hex()
            elif name.startswith('k'):
                i=int(name[1:]);expected=(0x8000000000000001+i*0x1000100010001).to_bytes(8,'little').hex()
            elif name=='rip':continue
            else:need(raw['fields'][name]['raw_hex']==raw['seeded_fields'][name]['raw_hex'],'forbidden NOP side effect: '+name);continue
            need(raw['disposable_register_stimuli'][name]==expected and raw['seeded_fields'][name]['raw_hex']==expected,'literal all-bit roundtrip: '+name)
        verdict['checked_fields']=83
        path=document.get('path_observation')
        if require_path and path is None:raise Unknown('synthetic actual memset path unavailable')
        if path is not None:
            need(path['certified_state_progress'] is False and path['promotion_allowed'] is False
                and path['call_origin']['kind']=='SYNTHETIC_PYTHON_CTYPES'
                and path['call_origin']['authorized_gala_call'] is False,'synthetic path cannot impersonate Gala')
            need(path['fingerprint']==fp and path['fingerprint_sha256']==digest(fp),'path/environment fingerprint seam')
            need(path['terminal']['status']=='OBSERVED_RETURN' and path['terminal']['complete'] is True,'bounded path observation incomplete')
            need(path['entry']==fp['libc']['memset_elf_entry'],'actual resolver/path entry mismatch')
            need(0<len(path['trace'])<=policy['max_path_steps'],'bounded actual path')
            need(path['trace'][0]['pc']==path['entry'],'actual entry/first path instruction')
            inp=path['input'];res=path['observed_result']
            need(type(inp['length']) is int and inp['length']==16 and type(inp['value']) is int and inp['value']==0,'finite synthetic zero16 input')
            need(type(inp['destination']) is int and type(inp['window_address']) is int and 0<=inp['window_address']<inp['destination']<2**64
                and inp['destination']==inp['window_address']+32 and inp['window_size']==80,'bounded synthetic destination window')
            initial=bytes.fromhex(inp['initial_window_hex']);final=bytes.fromhex(res['final_window_hex'])
            need(initial==bytes([0xa5])*80 and final==initial[:32]+bytes(16)+initial[48:],'independent synthetic window/guard result')
            need(type(res['return_value']) is int and res['return_value']==inp['destination'] and res['destination_hex']=='00'*16,'synthetic returned pointer/bytes')
            observed_lib=path['library'];pinned_lib=policy['binaries']['libc']
            need(observed_lib['sha256']==pinned_lib['sha256'] and observed_lib['build_id']==pinned_lib['build_id'],'actual path library identity')
            base=observed_lib['load_base']
            need(type(base) is int and 0<=base<2**64,'actual library load base')
            need(path['start_state']==path['trace'][0]['before'] and path['end_state']==path['trace'][-1]['after'],'actual start/end state seam')
            for index,row in enumerate(path['trace']):
                need(type(row['pc']) is int and type(row['next_pc']) is int and type(row['absolute_pc']) is int and type(row['absolute_next_pc']) is int,'actual PC types')
                need(row['seq']==index and row['absolute_pc']==base+row['pc']==row['before']['registers']['rip']
                    and row['absolute_next_pc']==base+row['next_pc']==row['after']['registers']['rip'],'actual relative/absolute/state PC coherence')
                if index:
                    need(path['trace'][index-1]['after']==row['before'],'dense actual state transitions')
            need(path['trace'][-1]['absolute_next_pc']==path['call_origin']['native_caller']['return_pc']==path['end_state']['registers']['rip'],'actual caller return target')
            library=Path(policy['binaries']['libc']['resolved_path']).read_bytes();loads,_=_elf(library)
            for row in path['trace']:
                at=row['pc'];code=bytes.fromhex(row['instruction_bytes'])
                found=[off+at-vaddr for off,vaddr,size,flags in loads if flags&1 and vaddr<=at and at+len(code)<=vaddr+size]
                need(len(found)==1 and code and library[found[0]:found[0]+len(code)]==code,'actual path code bytes/ELF mapping')
            from .profile_verify import inspect_observation
            effects=inspect_observation(path)
            need(effects['promotion_allowed'] is False,'path survey never promotes')
            verdict['actual_path']=dict(entry=path['entry'],instructions=len(path['trace']),
                unknown_instructions=effects['unknown_instructions'],effect_coverage=effects['effect_coverage'])
        verdict['status']='SCOUT_READY' if require_path else 'STATE_TEST_PASS'
        if not require_path:verdict['scope']='STATE_ONLY_TEST'
    except Unknown as exc:verdict.update(status='SCOUT_UNKNOWN',unknown=str(exc).split('; '))
    except (ValueError,KeyError,TypeError,OSError,OverflowError,StopIteration) as exc:verdict['reasons'].append(str(exc))
    verdict['evidence_sha256']=digest(document);verdict['policy_sha256']=digest(policy)
    return verdict
