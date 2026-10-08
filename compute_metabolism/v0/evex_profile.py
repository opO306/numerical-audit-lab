"""Read-only independent admission of the finite actual-Gala EVEX profile.

Public APIs never acquire an inferior, mutate an allowance, or register a file.
``build_candidate`` is a pending contract, not execution evidence. Promotion
requires ``proof-bundle.json`` with exact PROOF_KEYS and FILE_ROLES below.
Every file locator is a repo-relative {path, sha256}; primary observation and
guard evidence lives in the original operational campaign's observations/run.

The sealed outer observation config has CONFIG_KEYS. Its source epoch and
gate_source_snapshot are frozen before the attempt. V1 source identity keeps
the old prepared 40-source identity separately; no historical PASS is relabelled.
Review receipts contain REVIEW_OBLIGATIONS, source-bound supporting files, and
no unresolved findings. Regression receipts bind the same two source maps and
complete exact pytest test inventory/output. Neither labels nor counts alone
grant authority: actual origin and native effects plus fresh negatives replay.
"""
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
import struct

from verified_driver.v1.native_evex_checker import PATH, _typed_equal, _elf
from verified_driver.v1.model import content_id
from .gala_origin_check import verify_observation, CALLER_SHA, LIBC_SHA, LIBC_BUILD_ID
from . import source_epoch, system_guard, campaign
from .campaign import CampaignLedger, logical_tree_bytes, measured_guard_cost, _read as _ledger_read
from .profiles import CampaignLimits, get_profile, parse_cpu_list, parse_cpu_max

PROFILE_ID = 'libc-memset-avx512-evex-16zero-v1'
FEATURES = ('avx512f','avx512bw','avx512vl','bmi2')
PREPARED_SHA = '4901a28b9e4e829b154970ca48077209275b3312aee0be17e53e64670515e7ec'
HARNESS_SHA = '4928f88e4c6255cfbc3f68798648b543146fb5b13327490d331814f778a9fc26'
NEGATIVE_CLASSES = ('resultbit','outsidebyte','preservedreg','codebyte','samevaluewriteomission',
    'caller','entry','mask','length','nonzerofill','differentlibc')
SKELETON_CLASSES = ('library_hash','build_id','caller','entry','result','out_of_range_write',
    'unmodelled_instruction','forbidden_register_change','self_issued_pass')
FILE_ROLES = frozenset(('observation','launch','parent_birth','enabled_writes','observer_config',
    'observation_config','environment_before','environment_after','source_epoch','source_review',
    'source_regression','guard_before','guard_final','guard_outer','execution','upper_before','upper_after',
    'prepared','campaign_environment','campaign_config','negative_skeleton','negative_tests','old_candidate',
    'pre_registry','writer_quota','gdb_raw','candidate_birth','state_acquisitions'))
PROOF_KEYS = frozenset(('schema','evidence_role','campaign_id','run_id','files','gate_source_snapshot',
    'required_negative_classes'))
CONFIG_KEYS = frozenset(('schema','mode','certified_state_progress','campaign_id','run_id','profile',
    'inner_output','fingerprint','fingerprint_sha256','source_epoch','source_epoch_sha256','source_manifest',
    'prepared','prepared_sha256','campaign_environment','upper_before_sha256','gdb_sha256',
    'execution_registry_sha256','harness_sha256'))
REVIEW_OBLIGATIONS = frozenset(('independent_four_forms','complete_thirteen_effects','call_plt_got_origin',
    'cpuid_full_raw_state','same_value_store_footprint','owned_birth_and_containment',
    'finite_profile_admission','immutable_historical_source_authority'))
REQUIRED_TEST_FILES = frozenset(('tests/test_v1_evex_producer.py','tests/test_v1_evex_checker.py',
    'tests/test_v1_evex_capture.py','tests/test_v1_evex_collector.py',
    'tests/test_compute_metabolism_gala_origin.py','tests/test_compute_metabolism_gala_observer.py',
    'tests/test_compute_metabolism_source_epoch.py','tests/test_compute_metabolism_evex_profile.py'))
SPEC_PATHS = frozenset(('docs/superpowers/specs/2026-10-07-compute-metabolism-adaptive-design.md',
    'docs/superpowers/plans/2026-10-07-compute-metabolism-evex-promotion.md'))


def _need(condition,reason):
    if not condition:raise ValueError('REFUSED: EVEX profile '+reason)


def _keys(value,names,label):
    _need(type(value) is dict and set(value)==set(names),label+' exact keys')


def _hash(value):
    _need(type(value) is str and re.fullmatch('[0-9a-f]{64}',value) is not None,'strict SHA256')
    return value


def _canonical(value):
    return (json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False)+'\n').encode('ascii')


def _sha(raw):return hashlib.sha256(raw).hexdigest()


def _relative(name):
    _need(type(name) is str and name and '\\' not in name and ':' not in name,'POSIX relative locator')
    path=PurePosixPath(name)
    _need(not path.is_absolute() and path.as_posix()==name and
        all(p not in ('','.','..') for p in name.split('/')),'canonical relative locator')
    return name


def _safe(path):
    path=Path(os.path.abspath(path))
    for p in (path,*path.parents):
        info=p.lstat()
        _need(not stat.S_ISLNK(info.st_mode) and not getattr(info,'st_file_attributes',0)&0x400,'aliased path')
    return path


def _bytes(path,maximum=16*1024*1024):
    path=_safe(path)
    descriptor=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0))
    try:
        before=os.fstat(descriptor)
        _need(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and 0<=before.st_size<=maximum,
            'bounded single-link regular proof')
        with os.fdopen(descriptor,'rb',closefd=False) as stream:raw=stream.read(maximum+1)
        after=os.fstat(descriptor)
        _need(len(raw)<=maximum and (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)==
            (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns),'proof changed during read')
        return raw
    finally:os.close(descriptor)


def _json(raw):
    def pairs(items):
        value={}
        for key,item in items:
            _need(key not in value,'duplicate JSON key');value[key]=item
        return value
    return json.loads(raw,object_pairs_hook=pairs,
        parse_constant=lambda _:(_ for _ in ()).throw(ValueError('nonfinite JSON')))


def _read_ref(root,reference,maximum=16*1024*1024):
    _keys(reference,('path','sha256'),'file locator');name=_relative(reference['path']);_hash(reference['sha256'])
    raw=_bytes(Path(root)/name,maximum)
    _need(_sha(raw)==reference['sha256'],'proof SHA mismatch: '+name)
    return raw


def _number(value,label):
    _need(type(value) in (int,float) and math.isfinite(value) and value>=0,label+' finite nonnegative')
    return value


def _uint(value,label):
    _need(type(value) is int and value>=0,label+' strict nonnegative integer')
    return value


def _namespaces(campaign_id,run_id):
    for value in (campaign_id,run_id):
        _need(type(value) is str and re.fullmatch('[a-z0-9][a-z0-9-]{0,63}',value),'fixed operational namespace identity')
    base='compute_metabolism/v0/artifacts/operational/'+campaign_id+'/observations/'
    return dict(attempt=base+run_id+'/',proof=base+'proofs/'+run_id+'/',
        upper_before=base+'upper-before-'+run_id+'.raw.json')


def _library_identity(path,expected):
    """Prepared binary links are resolved, separately from evidence locators."""
    concrete=Path(path).resolve(strict=True);raw=_bytes(concrete,64*1024*1024)
    sha,bid=_sha(raw),_elf(raw)[1]
    _need(sha==expected['sha256'] and bid==expected['build_id'],'resolved prepared ELF SHA/BuildID')
    return dict(resolved_path=str(concrete),sha256=sha,build_id=bid)



def _executable_elf(raw):
    """Independent ET_EXEC-only ELF64 parser; shared-library rules stay fixed."""
    _need(len(raw)>=64 and raw[:7]==b"\x7fELF\x02\x01\x01",'ELF64 little endian executable')
    kind,machine,version,entry,phoff,_,_,ehsize,phsize,phnum,_,_,_=struct.unpack_from('<HHIQQQIHHHHHH',raw,16)
    _need(kind==2 and machine==62 and version==1 and ehsize==64 and
        phsize==56 and 0<phnum<=4096,'ELF x86-64 ET_EXEC executable header')
    _need(phoff>=64 and phoff+phsize*phnum<=len(raw),'ELF executable program headers bounds')
    loads=[];build_ids=[]
    for i in range(phnum):
        ptype,flags,offset,vaddr,_,filesz,memsz,_=struct.unpack_from('<IIQQQQQQ',raw,phoff+i*phsize)
        _need(offset+filesz<=len(raw),'ELF executable segment file bounds')
        if ptype==1:
            _need(filesz<=memsz and vaddr+memsz<=1<<64,'ELF executable load segment bounds')
            loads.append((offset,vaddr,filesz,flags))
        elif ptype==4:
            end=offset+filesz;cursor=offset
            while cursor<end:
                _need(cursor+12<=end,'ELF executable note header bounds')
                namesz,descsz,note_type=struct.unpack_from('<III',raw,cursor)
                name_at=cursor+12;desc_at=name_at+((namesz+3)&~3)
                next_at=desc_at+((descsz+3)&~3)
                _need(next_at<=end,'ELF executable note body bounds')
                if raw[name_at:name_at+namesz]==b'GNU\0' and note_type==3:
                    _need(0<descsz<=64,'ELF executable GNU Build ID length')
                    build_ids.append(raw[desc_at:desc_at+descsz].hex())
                cursor=next_at
    _need(len(set(build_ids))==1,'ELF executable missing or ambiguous GNU Build ID')
    _need(len([1 for _,vaddr,filesz,flags in loads if flags&1 and vaddr<=entry<vaddr+filesz])==1,
        'ELF executable entry in one file-backed executable load')
    return loads,build_ids[0]


def _executable_identity(path,expected,*,approved_paths=()):
    """Only the frozen runtime path and explicit prepared venv link are allowed."""
    name=os.fspath(path);recorded=expected['path']
    for value in (name,recorded,*approved_paths):
        _need(type(value) is str and PurePosixPath(value).is_absolute() and
            PurePosixPath(value).as_posix()==value and '..' not in PurePosixPath(value).parts,
            'canonical approved executable path')
    _need(name in (recorded,*approved_paths),'approved executable path')
    concrete=Path(name).resolve(strict=True)
    _need(concrete==Path(recorded).resolve(strict=True),'approved executable resolved target')
    before=concrete.stat();raw=_bytes(concrete,64*1024*1024);after=concrete.stat()
    identity=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
    _need(identity(before)==identity(after) and Path(name).resolve(strict=True)==concrete and
        Path(recorded).resolve(strict=True)==concrete,'executable replaced during read')
    sha,bid=_sha(raw),_executable_elf(raw)[1]
    _need(sha==expected['sha256'] and bid==expected['build_id'],'resolved prepared executable ELF SHA/BuildID')
    return dict(resolved_path=str(concrete),sha256=sha,build_id=bid)


def build_candidate(observation,old_candidate_sha256):
    """Return only the exact pending zero16 contract; observation grants nothing."""
    try:
        _hash(old_candidate_sha256)
        _need(observation['schema']=='gala-native-observation-v1','actual-origin candidate schema')
        fp=observation['fingerprint'];native=observation['native'];domain=native['domain']
        _need(fp['cpu_arch']=='x86_64' and set(FEATURES)<=set(fp['cpu_features']),'finite required CPU features')
        _need(fp['libc']['sha256']==LIBC_SHA and fp['libc']['build_id']==LIBC_BUILD_ID and
            fp['libc']['memset_elf_entry']==0x1996c0 and fp['gala']['sha256']==CALLER_SHA,'fixed libraries/entry')
        _need(observation['source_binding']==fp['v1_source_binding']==domain['source_sha256'] and
            observation['source_binding']==content_id(observation['source_snapshot']),'candidate source seam')
        _need(domain['provenance_kind']=='ACTUAL_GALA_CALL' and domain['length']==16 and
            type(domain['length']) is int and domain['fill']==0 and type(domain['fill']) is int,'finite zero16 domain')
        _need(observation['caller']['elf_pc']==0x35689 and observation['caller']['instruction_bytes']=='e8c20cfdff'
            and observation['caller']['plt_elf_pc']==0x6350,'finite actual CALL/PLT candidate')
        _need([(s['elf_pc'],s['instruction_bytes']) for s in native['steps']]==list(PATH),'exact thirteen byte-bound path')
        libraries={name:{key:fp[name][key] for key in ('sha256','build_id')} for name in ('libc','gala','runtime')}
        for library in libraries.values():
            _hash(library['sha256']);_need(type(library['build_id']) is str and
                re.fullmatch('[0-9a-f]+',library['build_id']) is not None,'library Build ID')
        return dict(schema='COMPUTE_METABOLISM_EXECUTION_PROFILE_V1',profile_id=PROFILE_ID,status='CANDIDATE',
            required_cpu_features=list(FEATURES),environment=dict(cpu_arch='x86_64'),libraries=libraries,
            v1_source_binding=fp['v1_source_binding'],allowed_call_origins=[dict(sha256=CALLER_SHA,elf_address=0x6350)],
            entry_points=[0x1996c0],allowed_path=[pc for pc,_ in PATH],
            expected_inputs=dict(destination='approved_gala_gradient',lengths=[16],fill_values=[0],
                domain_status='EXACT_FINITE_GALA_ZERO16',destination_page_offset_max=0xfe0),
            memory_contract=dict(reads=['return_address[0:8]'],writes=['destination[0:16]'],
                coverage='INDEPENDENT_FULL_NATIVE_EVEX_EFFECTS'),
            expected_result=dict(return_value='destination',bytes='exact_fill_byte'),
            allowed_state_changes=['registers.eflags','registers.k1','registers.rax','registers.rcx',
                'registers.rdi','registers.rip','registers.rsp','vectors.zmm16'],
            forbidden_state_changes=['outside_destination','unmodelled_registers','callee_saved_registers'],
            verified_capability_rank=0,derived_from=dict(candidate_sha256=old_candidate_sha256),
            verification=dict(authority=None,independent_verification='PENDING',tests=[],evidence_sha256=[]))
    except (KeyError,TypeError) as exc:raise ValueError('REFUSED: incomplete EVEX candidate: '+str(exc)) from exc


def _negative_controls(document,root,fp,sources,libc,gala,birth,classes=NEGATIVE_CLASSES,*,same_value_address=None):
    results=[]
    for name in classes:
        doc=deepcopy(document);native=doc['native'];steps=native['steps'];caller=doc['caller']
        if name in ('resultbit','result'):steps[9]['after']['registers']['rcx']^=1
        elif name in ('outsidebyte','out_of_range_write'):
            steps[11]['writes'].append(dict(address=native['domain']['destination']+16,size=1,after_hex='00'))
        elif name in ('preservedreg','forbidden_register_change'):steps[0]['after']['registers']['rbx']^=1
        elif name in ('codebyte','unmodelled_instruction'):steps[1]['instruction_bytes']='62e27d287ac7'
        elif name=='samevaluewriteomission':
            _need(type(same_value_address) is int,'authenticated actual same-value omission address')
            matching=[i for i,w in enumerate(steps[11]['writes']) if w['address']==same_value_address and w['size']==1]
            _need(len(matching)==1,'one independently checked enabled same-value lane')
            steps[11]['writes'].pop(matching[0])
        elif name=='caller':caller['sha256']='aa'*32
        elif name=='entry':caller['entry']['registers']['rip']+=1
        elif name=='mask':steps[10]['after']['registers']['k1']^=1
        elif name=='length':caller['before']['registers']['rdx']=15
        elif name=='nonzerofill':caller['before']['registers']['rsi']=1
        elif name in ('differentlibc','library_hash'):native['library']['sha256']='bb'*32
        elif name=='build_id':native['library']['build_id']='cc'*20
        elif name=='self_issued_pass':doc['verification']=dict(verdict='PASS',promotion_allowed=True)
        else:raise ValueError('unimplemented skeleton mutation '+name)
        try:verify_observation(doc,root,fp,sources,libc,gala,birth)
        except ValueError as exc:
            receipt=dict(mutation=name,verdict='REFUSED',mutant_sha256=_sha(_canonical(doc)),reason=str(exc))
            if name=='samevaluewriteomission':receipt['removed_write_address']=same_value_address
            results.append(receipt)
        else:raise ValueError('independent negative did not refuse: '+name)
    return results


def _validate_writes(samples,document):
    expected=[w for step in document['native']['steps'] for w in step['writes']]
    _need(type(samples) is list and len(samples)==len(expected)==16,'all sixteen actual enabled-store samples')
    same_value=False;first_unchanged=None
    for sample,write in zip(samples,expected):
        _keys(sample,('address','size','after_hex','before_hex','actual_after_hex','value_changed','basis'),'enabled write')
        _need({k:sample[k] for k in ('address','size','after_hex')}==write and type(sample['size']) is int and
            sample['size']==1 and type(sample['address']) is int,'actual sample/derived footprint seam')
        _need(sample['actual_after_hex']==sample['after_hex']=='00' and
            type(sample['before_hex']) is str and re.fullmatch('[0-9a-f]{2}',sample['before_hex']) is not None,
            'exact actual pre/post bytes')
        _need(type(sample['value_changed']) is bool and
            sample['value_changed']==(sample['before_hex']!=sample['actual_after_hex']) and
            sample['basis']=='DERIVED_ENABLED_STORE_WITH_ACTUAL_PRE_POST_BYTES','truthful same-value store evidence')
        same_value |= not sample['value_changed']
        if not sample['value_changed'] and first_unchanged is None:first_unchanged=sample['address']
    _need(same_value,'actual same-value store witness required for omission control')
    return first_unchanged


def _raw_snapshot(snapshot):
    """Reparse raw CPU/memory/PID files before using claimed parsed counters."""
    raw=snapshot['raw']
    _need(list(parse_cpu_list(raw['cpuset.cpus.effective'].strip()))==snapshot['cpus'],'raw CPU set')
    def counters(name):
        result={}
        for line in raw[name].splitlines():
            fields=line.split();_need(len(fields)==2 and fields[0] not in result and fields[1].isdigit(),'raw counter syntax')
            result[fields[0]]=int(fields[1])
        return result
    _need(_typed_equal(counters('cpu.stat'),snapshot['cpu_stat']) and
        _typed_equal(counters('memory.events'),snapshot['memory_events']),'raw counters/parsed seam')
    for rawname,key in (('memory.current','memory_current'),('memory.peak','memory_peak')):
        _need(raw[rawname].strip().isdigit() and int(raw[rawname])==snapshot[key],'raw memory value')
    _need(raw['cpu.max']==snapshot['cpu_max']['raw'],'raw bandwidth value')
    mount=PurePosixPath('/sys/fs/cgroup');leaf=PurePosixPath(snapshot['epoch']['path'])
    _need(mount in leaf.parents,'controller mount ancestry')
    folders=[leaf,*[p for p in leaf.parents if p==mount or mount in p.parents]]
    cpu=snapshot['cpu_max'];entries=cpu['ancestors']
    _need(cpu['scan_root']==str(mount) and [item['path'] for item in entries]==
        [str(p/'cpu.max') for p in folders],'complete original CPU ancestor raw scan')
    known=[];finite=[]
    for i,(folder,item) in enumerate(zip(folders,entries)):
        if item['raw'] is None:
            _need((i==0 or folder==mount) and item.get('missing_at_root')==(folder==mount),
                'unknown CPU ancestor refused')
        else:
            quota,period=parse_cpu_max(item['raw'])
            _need(_typed_equal(item['quota_usec'],quota) and _typed_equal(item['period_usec'],period),'raw ancestor bandwidth parse')
            known.append(item)
            if quota is not None:finite.append(item)
    _need(known and cpu['source']==known[0]['path'] and cpu['raw']==known[0]['raw'] and
        _typed_equal(cpu['quota_usec'],known[0]['quota_usec']) and _typed_equal(cpu['period_usec'],known[0]['period_usec']) and
        type(cpu['unlimited']) is bool and cpu['unlimited']==(not finite) and cpu['finite_ancestors']==finite,
        'derived effective raw bandwidth')
    for group,filename in (('memory','memory.max'),('swap','memory.swap.max')):
        scan=snapshot[group];items=scan['ancestors'];limits=[]
        _need(scan['scan_root']==str(mount) and [item['path'] for item in items]==
            [str(p/filename) for p in folders] and items[0]['raw']==raw[filename],'complete raw effective memory/swap ancestry')
        for folder,item in zip(folders,items):
            if item['raw'] is None:
                _need(folder==mount and item.get('missing_at_root') is True,'unknown memory/swap ancestor')
            else:
                text=item['raw'].strip();_need(text=='max' or re.fullmatch('[0-9]+',text),'raw memory/swap integer')
                limit=None if text=='max' else int(text)
                _need(_typed_equal(item['bytes'],limit),'raw memory/swap parsed seam')
                if limit is not None:limits.append(limit)
        _need(_typed_equal(scan['effective_bytes'],min(limits) if limits else None),'derived effective raw memory/swap ceiling')
    _need(snapshot['enumerated_pids']==sorted(int(p) for p in raw['cgroup.procs'].split()),'raw PID inventory')
    _need(type(snapshot['epoch']['boot_id']) is str and bool(snapshot['epoch']['boot_id']),'actual cgroup boot')


def _validate_guard_launch(outer,reference,attempt_prefix):
    """Bind actual systemd argv to the sealed one-observation config bytes."""
    _keys(reference,('path','sha256'),'outer observation config locator')
    name=_relative(reference['path']);_hash(reference['sha256'])
    attempt=PurePosixPath(attempt_prefix.rstrip('/'))
    expected_name=(attempt.parent/('config-'+attempt.name+'.json')).as_posix()
    _need(name==expected_name,'original prelaunch observation config namespace')
    command=[system_guard.INNER_PYTHON,'-B','-m','compute_metabolism.v0.gala_observation_run',
        '--inner-config','/workspace/'+name,'--config-sha256',reference['sha256']]
    expected=system_guard.build_systemd_run_argv(get_profile('2c'),unit_name=outer['unit'],
        artifact_dir=PurePosixPath('/workspace/'+attempt.as_posix()),command=command,
        root_directory=system_guard.PREPARED_ROOT,limits=CampaignLimits())
    _need(_typed_equal(outer['argv'],expected),'actual guarded Gala observation argv/config SHA')


def _validate_cpu_accounting(claimed,outer,root,reference):
    """Recheck guest proof bytes; retain the one approved host locator spelling."""
    _read_ref(root,reference)
    cost=measured_guard_cost(dict(outer,proof_locator=str(Path(root)/reference['path']),
        proof_sha256=reference['sha256']))
    cost['cpu_measurement_proof']['locator']=str(system_guard.PREPARED_ROOT/'workspace'/reference['path'])
    _need(_typed_equal(claimed,cost),'actual CPU cost and fixed host/guest proof mapping')
    return cost


def _validate_guard(outer,final,before,config,run_id):
    try:
        _need(outer['test_only'] is False and outer['terminal'] is True and outer['launcher_reaped'] is True
            and outer['measurement_valid'] is True and outer['outcome']=='GUARD_COMPLETE' and
            outer['outer_timeout_proved'] is False and outer['returncode']==0,'terminal LIVE guard required')
        _need(outer['deadline_seconds']==180 and outer['writer_bytes']==671088640 and
            _number(outer['wall_seconds'],'wall')<=180,'fixed guard caps')
        _need(outer['run_id']==final['run_id']==before['run_id']==run_id and
            outer['profile']==final['profile']==before['profile']=='2c' and
            outer['unit']==final['unit']==before['unit'] and re.fullmatch(system_guard.UNIT_PATTERN,outer['unit']),
            'same actual system unit/run/profile')
        _need(outer['inner']==final and before['before']==final['before'] and
            outer['before']==final['before'] and outer['after']==final['after'],'raw guard receipt seams')
        _need(final['outcome']=='GUARD_COMPLETE' and final['measurement_valid'] is True and
            final['child_returncode']==0 and final['interrupted'] is False and final['cleanup_errors']==[] and
            final['final_errors']==[] and final['containment']['remaining_pids']==[],'inner terminal containment')
        for item in (outer,final,before):_need('error' not in item and 'diagnostic' not in item,'guard error retained; admission forbidden')
        _need(not any(attempt.get('errors') for attempt in outer['cleanup_attempts']) and
            'cleanup_error' not in outer and 'terminal_error' not in outer,'outer cleanup errors')
        for which in ('before','after'):
            snap=outer[which];_raw_snapshot(snap)
            cg=PurePosixPath(snap['epoch']['path'])
            _need(cg.parent==PurePosixPath('/sys/fs/cgroup/system.slice') and cg.name==outer['unit'],'system.slice cgroup')
            _need(final['topology_'+which]==config['campaign_environment']['topology'],'frozen guest topology')
            system_guard.validate_enforcement(get_profile('2c'),snap,final['topology_'+which])
        delta=system_guard.validate_snapshot_pair(outer['before'],outer['after'])
        _need(outer['delta']==final['delta']==delta,'actual raw CPU delta')
        _need(outer['after']['pids']==[final['wrapper_identity']['pid']],'only wrapper present before final collection')
        _need(all(outer['after']['memory_events'][k]==outer['before']['memory_events'][k] for k in ('oom','oom_kill')),'no OOM')
        states=outer['unit_states']+[state for attempt in outer['cleanup_attempts'] for state in attempt.get('unit_states',[])]
        terminal=[]
        for state in states:
            if state.get('returncode')==0 and state.get('unit')==outer['unit']:
                props=dict(line.split('=',1) for line in state['stdout'].splitlines() if '=' in line)
                _need(props.get('ControlGroup','') in ('','/system.slice/'+outer['unit']), 'terminal raw unit ControlGroup identity')
                if props.get('LoadState')=='not-found' or props.get('ActiveState') in ('inactive','failed'):
                    terminal.append(state)
        _need(terminal and all(s['monotonic_seconds']>=final['after']['monotonic_seconds'] for s in terminal),
            'raw terminal unit observation after final counter collection')
        return delta
    except (KeyError,TypeError,OSError) as exc:raise ValueError('REFUSED: incomplete raw guard proof '+str(exc)) from exc


def _gate_sources(root,epoch,supplied):
    _need(type(supplied) is dict and supplied,'complete gate source snapshot')
    # Shared physical inventory rules have no native instruction semantics.
    # Rehash each source independently with this gate's bounded file reader.
    validated=campaign.validate_gate_source_snapshot(supplied,root,epoch)
    _need(_typed_equal(validated,supplied),'exact physical gate inventory')
    for name,want in supplied.items():
        _relative(name);_hash(want);_need(_sha(_bytes(root/name))==want,'current gate source drift: '+name)
    _need(supplied['compute_metabolism/v0/evex_profile.py']==_sha(_bytes(Path(__file__))), 'verifier self-source bound')
    return deepcopy(supplied)


def regression_test_files(repo_root):
    """Exact related Runtime/V0/V1/EVEX/Compute test arguments, no execution."""
    prefixes=('test_compute_metabolism_','test_v1_evex_','test_verified_driver_','test_live_chain_','test_numeric_ir',
        'test_regular_','test_caller_transition','test_runtime_trace','test_gate2c1',
        'test_machine_check','test_write_effect','test_read_effect','test_v2')
    original=('test_gate0.py','test_gate0_closure.py','test_gate1.py','test_gate2a.py',
        'test_gate2a_sealed.py','test_gate2b.py','test_gate2b_adapter.py','test_gate2c.py',
        'test_gate2c_sealed.py','test_independence.py','test_provenance.py',
        'test_post_seal_audit.py','test_ported_hard_cases.py')
    root=Path(repo_root)
    paths={p.relative_to(root).as_posix() for p in (root/'tests').glob('test_*.py')
        if p.name.startswith(prefixes) or p.name in original}
    for directory in ('runtime_trace/tests','runtime_trace/caller_transition/tests',
        'runtime_trace/numeric_ir/tests','runtime_trace/numeric_ir/v2/tests','runtime_trace/regular_2step/tests'):
        paths.update(p.relative_to(root).as_posix() for p in (root/directory).glob('test*.py') if p.is_file())
    return sorted(paths)


def _review_regression(root,review,regression,epoch,gate):
    _keys(review,('schema','evidence_role','source_binding','gate_source_snapshot','obligations','unresolved_findings'),'review receipt')
    _need(review['schema']=='COMPUTE_METABOLISM_EVEX_SOURCE_REVIEW_V1' and review['evidence_role']=='SOURCE_REVIEW'
        and review['source_binding']==epoch['source_binding'] and _typed_equal(review['gate_source_snapshot'],gate)
        and review['unresolved_findings']==[],'source-bound substantive review')
    _need(type(review['obligations']) is dict and set(review['obligations'])==REVIEW_OBLIGATIONS,'all source/effect review obligations')
    for name,item in review['obligations'].items():
        _keys(item,('source_sha256','supporting_file'),'review obligation')
        _need(type(item['source_sha256']) is dict and item['source_sha256'] and
            all(gate.get(path)==want for path,want in item['source_sha256'].items()),'reviewed current actual files')
        required={
            'independent_four_forms':{'verified_driver/v1/native_evex_producer.py','verified_driver/v1/native_evex_checker.py'},
            'complete_thirteen_effects':{'verified_driver/v1/native_evex_checker.py','verified_driver/v1/native_evex_collector.py'},
            'call_plt_got_origin':{'compute_metabolism/v0/gala_origin_check.py','compute_metabolism/v0/gdb_gala_observer.py'},
            'cpuid_full_raw_state':{'verified_driver/v1/native_evex_capture.py'},
            'same_value_store_footprint':{'verified_driver/v1/native_evex_checker.py','verified_driver/v1/native_evex_collector.py'},
            'owned_birth_and_containment':{'compute_metabolism/v0/gala_observer.py','compute_metabolism/v0/system_guard.py'},
            'finite_profile_admission':{'compute_metabolism/v0/evex_profile.py','verified_driver/v1/native_evex_profile.py'},
            'immutable_historical_source_authority':{'compute_metabolism/v0/source_epoch.py','compute_metabolism/v0/historical_profile.py'},
        }[name]
        _need(required<=set(item['source_sha256']),'source-effect obligation binds its actual implementation files')
        supporting=_read_ref(root,item['supporting_file'])
        _need(len(supporting)>=32 and name.encode() in supporting and
            all(want.encode() in supporting for want in item['source_sha256'].values()),'substantive source-bound review evidence')
    _keys(regression,('schema','source_binding','gate_source_snapshot','test_files','command','returncode','output'),'regression receipt')
    _need(regression['schema']=='COMPUTE_METABOLISM_EVEX_SOURCE_REGRESSION_V1' and
        regression['source_binding']==epoch['source_binding'] and _typed_equal(regression['gate_source_snapshot'],gate),
        'same actual regression source maps')
    inventory=regression_test_files(root)
    _need(type(regression['test_files']) is dict and set(regression['test_files'])==set(inventory) and
        REQUIRED_TEST_FILES<=set(inventory),'exact complete related regression test inventory')
    for path,want in regression['test_files'].items():
        _need(path in inventory and path.endswith('.py'),'exact related test source inventory')
        _read_ref(root,dict(path=path,sha256=want))
    command=regression['command']
    _need(type(command) is list and len(command)==len(inventory)+5 and type(command[0]) is str and
        re.fullmatch(r'python(?:3(?:\.12)?)?',PurePosixPath(command[0]).name) is not None and
        command[1:4]==['-B','-m','pytest'] and command[4:-1]==inventory and command[-1]=='-q' and
        type(regression['returncode']) is int and regression['returncode']==0,'exact complete merged-tree regression')
    output=_read_ref(root,regression['output']).decode('utf-8')
    _need(re.search(r'\b[1-9][0-9]* passed\b',output) is not None and
        re.search(r'\b[1-9][0-9]* (?:failed|error|errors)\b',output) is None,'actual passing regression output')


def _environment(environment,prepared,epoch,root,frozen,fp):
    source_epoch.validate_environment_identity(environment,prepared['identity'],epoch,root)
    _need(environment['evidence_scope']=='LIVE' and environment['execution_fingerprint']==fp,'external actual environment/fingerprint')
    observation=environment['instance_observation']
    _need(frozen['schema']=='COMPUTE_METABOLISM_ENVIRONMENT_V0' and
        type(frozen['instance_id']) is str and re.fullmatch('[0-9]+',frozen['instance_id']) and
        observation['instance_id']==observation['raw'].strip()==frozen['instance_id'] and observation['observed_utc'],
        'raw frozen GCP instance identity')
    _need(environment['boot_id']==frozen['boot_id'] and environment['topology']==frozen['topology'] and
        environment['runtime']['platform']==frozen['platform'],'same boot/topology/platform')
    _need(environment['thread_environment']=={'OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1'},'thread policy')
    if 'dmi_identity' in frozen:_need(environment.get('dmi_identity')==frozen['dmi_identity'],'same DMI identity')
    for name in ('loadavg','cpu_pressure','stat'):_need(type(environment['proc'][name]) is str and environment['proc'][name],'raw environment '+name)
    steal={}
    for line in environment['proc']['stat'].splitlines():
        fields=line.split()
        if fields and re.fullmatch(r'cpu[0-9]*',fields[0]):
            _need(len(fields)>=9 and fields[0] not in steal and all(v.isascii() and v.isdigit() for v in fields[1:]),
                'raw per-CPU steal counters')
            steal[fields[0]]=int(fields[8])
    _need('cpu' in steal and _typed_equal(environment['proc']['steal_ticks'],steal),'all actual CPU steal counters')


def _verify(directory,root):
    root=_safe(root);directory=_safe(directory)
    candidate=_json(_bytes(directory/'candidate-profile.json'))
    proof_raw=_bytes(directory/'proof-bundle.json');proof=_json(proof_raw)
    _keys(proof,PROOF_KEYS,'proof bundle')
    _need(proof['schema']=='COMPUTE_METABOLISM_GALA_EVEX_PROOF_V1' and proof['evidence_role']=='LIVE','explicit actual LIVE proof bundle')
    for key in ('campaign_id','run_id'):
        _need(type(proof[key]) is str and re.fullmatch('[a-z0-9][a-z0-9-]{0,63}',proof[key]),'fixed operational '+key)
    _need(set(proof['files'])==FILE_ROLES and proof['required_negative_classes']==list(NEGATIVE_CLASSES),'complete bounded proof inventory')
    namespaces=_namespaces(proof['campaign_id'],proof['run_id']);prefix=namespaces['attempt'];proof_prefix=namespaces['proof']
    _need(directory.is_relative_to(root) and directory.relative_to(root).as_posix()==proof_prefix+'candidate',
        'exact separate operational proof candidate namespace')
    files=proof['files'];raw={name:_read_ref(root,ref) for name,ref in files.items()}
    docs={name:_json(data) for name,data in raw.items() if name not in ('negative_tests','writer_quota')}
    _need(len({ref['path'] for ref in files.values()})==len(files),'independent proof files cannot alias each other')
    for role in ('observation','launch','parent_birth','enabled_writes','observer_config','environment_before',
        'environment_after','guard_before','guard_final','guard_outer','execution','writer_quota',
        'gdb_raw','candidate_birth','state_acquisitions'):
        _need(files[role]['path'].startswith(prefix),'same original operational observation attempt: '+role)
    _need(files['upper_before']['path']==namespaces['upper_before'] and
        files['upper_after']['path']==proof_prefix+'upper-after.raw.json','prelaunch/final immutable allowance snapshot namespaces')
    _need(files['state_acquisitions']['path']==prefix+'observations/state-acquisitions.json','exact original raw83 file locator')
    config=docs['observation_config'];_keys(config,CONFIG_KEYS,'sealed observation config')
    _need(config['schema']=='COMPUTE_METABOLISM_GALA_OBSERVATION_CONFIG_V1' and config['mode']=='OBSERVATION'
        and config['certified_state_progress'] is False and config['campaign_id']==proof['campaign_id'] and
        config['run_id']==proof['run_id'] and config['profile']=='2c' and
        config['inner_output']=='/workspace/'+prefix+'observations','fixed actual observation config')
    _need(config['source_epoch_sha256']==files['source_epoch']['sha256'] and
        config['upper_before_sha256']==files['upper_before']['sha256'] and
        config['execution_registry_sha256']==files['pre_registry']['sha256'] and config['harness_sha256']==HARNESS_SHA,
        'pre-attempt authority anchors')
    epoch=docs['source_epoch'];sources,binding=source_epoch.validate_epoch(epoch,root)
    _need(config['source_epoch']==epoch and _sha(_canonical(epoch))==files['source_epoch']['sha256'],
        'exact pre-attempt inline source epoch')
    gate=_gate_sources(root,epoch,proof['gate_source_snapshot'])
    _need(_typed_equal(config['source_manifest'],gate),'pre-attempt gate self-source binding')
    _need(epoch['review_sha256']==files['source_review']['sha256'] and
        epoch['regression_sha256']==files['source_regression']['sha256'],'actual epoch review/regression anchors')
    _review_regression(root,docs['source_review'],docs['source_regression'],epoch,gate)
    _need(files['prepared']['sha256']==PREPARED_SHA,'immutable old prepared identity')
    prepared=docs['prepared'];frozen=docs['campaign_environment'];fp=config['fingerprint']
    _need(config['prepared']==prepared and config['prepared_sha256']==PREPARED_SHA and
        config['fingerprint_sha256']==_sha(_canonical(fp)),'externally frozen runtime/fingerprint')
    expected_environment={key:value for key,value in frozen.items() if key not in ('execution_profile','execution_registry_sha256')}
    expected_environment['source_epoch']=epoch
    _need(config['campaign_environment']==expected_environment,'separate derived observation environment preserves old VM identity')
    for environment in (docs['environment_before'],docs['environment_after']):
        _environment(environment,prepared,epoch,root,frozen,fp)
    _need(fp['v1_source_binding']==binding,'new current epoch fingerprint')
    _need(_sha(_bytes(root/'runtime_trace/harness.py'))==HARNESS_SHA,'unchanged original parameter-only harness')
    _validate_guard_launch(docs['guard_outer'],files['observation_config'],prefix)
    delta=_validate_guard(docs['guard_outer'],docs['guard_final'],docs['guard_before'],
        {'campaign_environment':frozen},proof['run_id'])
    outer=docs['guard_outer'];final=docs['guard_final']
    for environment in (docs['environment_before'],docs['environment_after']):
        _need(environment['boot_id']==outer['before']['epoch']['boot_id'] and
            all(environment['wrapper_identity'][key]==final['child_identity'][key] for key in ('pid','start_ticks')),
            'guard/environment wrapper birth ownership')
    launch=docs['launch'];observer_config=docs['observer_config'];birth=docs['parent_birth']
    _need(launch['config']==observer_config and launch['config_sha256']==files['observer_config']['sha256'] and
        launch['owned_process_identity']==birth and launch['outcome']=='OBSERVED_UNCERTIFIED','independent parent launch/config/birth')
    _need(launch['process']['returncode']==0 and launch['process']['stop_reason'] is None and
        launch['process'].get('diagnostic') is None,'single clean acquisition')
    _need(observer_config['mode']=='OBSERVATION' and observer_config['certified_state_progress'] is False and
        observer_config['fingerprint']==fp and observer_config['source_snapshot']==sources and
        observer_config['max_native_steps']==13 and observer_config['stop_at']=='FIRST_APPROVED_MEMSET_RETURN' and
        observer_config['gdb_sha256']==config['gdb_sha256'],'exact one CALL recorder config')
    executable=prepared['identity']['executable']
    _need(executable==system_guard.INNER_PYTHON and observer_config['python_executable']==executable,
        'original prepared venv executable, distinct from resolved Python ELF provenance')
    args=['/usr/bin/gdb','-q','-nx','-batch','-iex','set auto-load off','-iex','set debuginfod enabled off',
        '-x','/workspace/compute_metabolism/v0/gdb_gala_observer.py','--args',executable,'-B',
        '/workspace/verified_driver/v1/live_chain/harness.py']
    _need(launch['command']==args and launch['recorder_source_sha256']==gate['compute_metabolism/v0/gdb_gala_observer.py'],
        'actual original V1 harness launch')
    env=launch['environment']
    required_env=dict(CM_GALA_OBSERVER_CONFIG=launch['original_config_path'],
        PYTHONDONTWRITEBYTECODE='1',PYTHONPATH='/workspace',RT_OUTPUT=observer_config['harness_output'],RTN_STEPS='1',
        RT2_CASE='known',CT_ANTECEDENT_LABEL='known',LD_BIND_NOW='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',
        RTN_QUOTA_FILE='/workspace/'+prefix+'writer_quota.txt',RTN_QUOTA_BYTES='671088640')
    _need(type(env) is dict and set(required_env)<=set(env) and set(env)<=set(required_env)|{'PATH','LANG','LC_ALL','HOME'}
        and all(env[key]==want for key,want in required_env.items()),'actual N1/no-store/same-allocation launch environment')
    _need(launch['retained_config_path']=='/workspace/'+files['observer_config']['path'], 'retained exact launched config namespace')
    for name,role in (('owned_birth','parent_birth'),('enabled_write_evidence','enabled_writes'),
        ('raw_result','gdb_raw'),('candidate_birth','candidate_birth'),
        ('state_acquisition_evidence','state_acquisitions')):
        meta=launch[name]
        _need(meta['present'] is True and meta['truncated'] is False and meta['actual_size']==meta['retained_size']==len(raw[role])
            and meta['retained_sha256']==files[role]['sha256'] and meta['retained_path']=='/workspace/'+files[role]['path'],
            'untruncated original private acquisition evidence: '+name)
    _need(docs['gdb_raw']==docs['observation'] and docs['candidate_birth']=={'pid':birth['pid']},
        'actual complete GDB raw bytes and independent candidate PID seam')
    _need(observer_config['birth']==launch['owned_birth']['original_path'] and
        observer_config['result']==launch['raw_result']['original_path'],'actual scratch/raw/birth config seam')
    reservation=launch['writer_reservation']
    _need(reservation==dict(path='/workspace/'+prefix+'writer_quota.txt',maximum_bytes=671088640,reserved_bytes=16777216),
        'original shared writer reservation; no new allowance')
    _need(_sha(_bytes('/usr/bin/gdb',64*1024*1024))==config['gdb_sha256'],'actual prepared GDB SHA')
    _executable_identity(fp['runtime']['path'],fp['runtime'])
    _executable_identity(executable,fp['runtime'],approved_paths=(executable,))
    for name in ('libc','gala'):
        _library_identity(fp[name]['path'],fp[name])
    observation=docs['observation'];same_value_address=_validate_writes(docs['enabled_writes'],observation)
    raw_states=verify_state_acquisitions(docs['state_acquisitions'],observation,observer_config)
    _need(launch['state_acquisition_evidence']['original_path']==str(PurePosixPath(observer_config['result']).with_name('state-acquisitions.json')),'original private raw83 namespace')
    normal=verify_observation(observation,root,fp,sources,fp['libc']['path'],fp['gala']['path'],birth)
    _need(birth['linux_boot_id']==frozen['boot_id'],'actual owned inferior same boot')
    contract=build_candidate(observation,files['old_candidate']['sha256'])
    _need(_typed_equal(candidate,contract),'exact candidate contract; no self-issued authority')
    skeleton=docs['negative_skeleton']
    _need(type(skeleton) is dict and skeleton.get('mutations')==list(SKELETON_CLASSES),
        'preserved original generated negative names')
    _need(b'INDEPENDENT_PROOF_REQUIRED' in raw['negative_tests'] or
        b'test_generated_observation_refuses_promotion' in raw['negative_tests'],'actual preserved generated negative skeleton')
    negatives=_negative_controls(observation,root,fp,sources,fp['libc']['path'],fp['gala']['path'],birth,
        same_value_address=same_value_address)
    skeleton_receipts=_negative_controls(observation,root,fp,sources,fp['libc']['path'],fp['gala']['path'],birth,SKELETON_CLASSES)
    execution=docs['execution'];cpu=_validate_cpu_accounting(execution['cpu_accounting'],outer,root,files['guard_outer'])
    _need(execution['mode']=='OBSERVATION' and execution['certified_state_progress'] is False and
        execution['config_sha256']==files['observation_config']['sha256'] and execution['wrapper_outcome']=='GUARD_COMPLETE'
        and execution['observation_outcome']=='OBSERVED_UNCERTIFIED' and execution['cpu_accounting']==cpu,
        'actual observation execution and raw CPU cost')
    retained=_uint(execution['retained_bytes'],'retained bytes');writer=_uint(execution['writer_used_bytes'],'writer use')
    _need(retained<=100663296 and writer<=671088640 and execution['writer_reservation_bytes']==671088640,'resource caps')
    _need(re.fullmatch(b'[0-9]+',raw['writer_quota']) is not None and int(raw['writer_quota'])==writer,'actual writer reservation counter')
    before,after=docs['upper_before'],docs['upper_after']
    _need(_ledger_read(root/files['upper_before']['path'])==before and
        _ledger_read(root/files['upper_after']['path'])==after,'validated before/after upper snapshots')
    _need(before['limits']==after['limits']==asdict(CampaignLimits()) and before['running'] is None and after['running'] is None,
        'same existing completed upper allowance')
    _need(before['formal_campaign']==after['formal_campaign'] and
        before['formal_campaign']['campaign_id']==proof['campaign_id'] and
        before['formal_campaign']['config_sha256']==files['campaign_config']['sha256'],'old campaign authority preserved')
    old_config=docs['campaign_config']
    _need(old_config['inputs']['execution-environment.json']['sha256']==files['prepared']['sha256'] and
        old_config['inputs']['campaign-environment.json']['sha256']==files['campaign_environment']['sha256'],
        'old immutable prepared/campaign input anchors')
    _need(len(after['attempts'])==len(before['attempts'])+1 and after['attempts'][:-1]==before['attempts'],'append one existing allowance attempt')
    record=after['attempts'][-1]
    _need(record['campaign_id']==proof['campaign_id'] and record['run_id']==proof['run_id'] and
        record['status']=='FINISHED' and record['kind']=='OBSERVATION' and record['role']=='guard-preflight' and
        record['profile']=='2c' and record['round_index']==0 and record['certified_state_progress'] is False and
        record['observation_config_sha256']==files['observation_config']['sha256'] and record['outcome']=='GUARD_COMPLETE'
        and record['cpu_seconds']==delta['cpu_seconds'] and record['outer_wall_seconds']==outer['wall_seconds'] and
        record['writer_reserved_bytes']==writer and record['retained_bytes']==retained,'exact charged one-attempt identity')
    _need(after['total_wall_seconds']==math.fsum(r['outer_wall_seconds'] for r in after['attempts']), 'upper cumulative actual wall')
    _need(after['total_wall_seconds']<=4200 and before['total_wall_seconds']+180<=4200,'existing wall allowance; no new grant')
    live=CampaignLedger.read_snapshot(root/'compute_metabolism/v0/artifacts/operational/budget.json')
    live.pop('observed_retained_total_bytes',None)
    _need(live==after or (live['attempts'][:len(after['attempts'])]==after['attempts'] and live['limits']==after['limits']),
        'actual existing operational ledger still contains immutable attempt prefix')
    _need(logical_tree_bytes(root/prefix)==retained and retained<=100663296,'exact charged original attempt tree retained bytes')
    _need(logical_tree_bytes(root/proof_prefix)<=100663296,'bounded separate authority proof metadata')
    _need(logical_tree_bytes(root/'compute_metabolism/v0/artifacts/operational')<=3221225472,'actual total retained upper allowance')
    verified=deepcopy(contract);verified['status']='VERIFIED';verified['verified_capability_rank']=20
    verified['verification']=dict(authority='INDEPENDENT_GALA_EVEX_PROFILE_V1',
        independent_verification='ACTUAL_CALL_FULL_NATIVE_GUARD_SOURCE_AND_NEGATIVE_REPLAY',
        proof_bundle=dict(path=(directory/'proof-bundle.json').relative_to(root).as_posix(),sha256=_sha(proof_raw)),
        source_binding=binding,source_count=len(sources),gate_source_snapshot=gate,profile_gate_sha256=gate['compute_metabolism/v0/evex_profile.py'],
        actual_gala_observation_sha256=files['observation']['sha256'],proof_files_sha256={k:v['sha256'] for k,v in files.items()},
        library_paths={name:fp[name]['path'] for name in ('libc','gala','runtime')},
        normal_receipt=normal,raw_state_receipt=raw_states,negative_controls=negatives,skeleton_negative_controls=skeleton_receipts,
        required_features=list(FEATURES),authorized_call_elf_pc=0x35689,plt_elf_pc=0x6350,native_entry=0x1996c0,
        native_source_sha256={k:sources[k] for k in sources if k.startswith('verified_driver/v1/native_evex_')},
        raw_effects_rechecked=True,numerical_certification=False,formal_certification=False,certified_state_progress=False)
    return verified


def verify_promotion(candidate_dir,repo_root):
    """Read every proof and replay; return refusal without writing or launching."""
    try:
        result=_verify(candidate_dir,repo_root)
        return dict(promotion_allowed=True,verified_manifest=result,required_proofs=[],
            numerical_certification=False,formal_certification=False)
    except (ValueError,KeyError,TypeError,OSError,OverflowError,StopIteration) as exc:
        return dict(promotion_allowed=False,required_proofs=[str(exc)],numerical_certification=False,formal_certification=False)


def verify_registered_profile(profile,repo_root):
    """Registered labels are rederived from immutable actual observation proofs."""
    _need(type(profile) is dict and profile.get('status')=='VERIFIED' and profile.get('profile_id')==PROFILE_ID,
        'finite registered VERIFIED profile')
    verification=profile.get('verification',{})
    _need(verification.get('authority')=='INDEPENDENT_GALA_EVEX_PROFILE_V1','registered independent authority')
    _need(type(verification.get('proof_bundle')) is dict,'registered actual proof locator')
    reference=verification['proof_bundle'];_read_ref(repo_root,reference)
    directory=Path(repo_root)/_relative(reference['path']);result=verify_promotion(directory.parent,repo_root)
    _need(result['promotion_allowed'] is True,'registered proof replay refused: '+str(result['required_proofs']))
    _need(_typed_equal(profile,result['verified_manifest']),'registered manifest/source/receipt drift')
    return result['verified_manifest']


def verify_state_acquisitions(document,observation,observer_config):
    """Independently bind all30 original raw83 contexts; no numerical authority."""
    from .scout_check import state as check_state, NAMES
    _keys(document,('schema','observation_sha256','observer_config_sha256','source_binding',
        'process_identity','thread_ptid','gdb_sha256','samples'),'raw-state binding')
    _need(document['schema']=='gala-state-acquisitions-v2','current raw83 acquisition schema')
    _need(document['observation_sha256']==_sha(_canonical(observation)) and
        document['observer_config_sha256']==_sha(_canonical(observer_config)),'raw-state observation/config SHA')
    _need(document['source_binding']==observation['source_binding'] and
        _typed_equal(document['process_identity'],observation['process_identity']) and
        _typed_equal(document['thread_ptid'],observation['thread_ptid']) and
        document['gdb_sha256']==observer_config['gdb_sha256'],'same original raw-state execution')
    caller=observation['caller'];steps=observation['native']['steps']
    _need(len(steps)==13,'raw-state complete thirteen instruction order')
    contexts=[caller[n] for n in ('before','after_call','entry')]+[
        c for row in steps for c in (row['before'],row['after'])]+[observation['native']['exit']]
    samples=document['samples']
    _need(type(samples) is list and len(samples)==30,'exact thirty raw-state acquisitions')
    order=list(NAMES[:35])+list(NAMES[51:])+list(NAMES[35:51])
    scalars=('fctrl','fstat','ftag','fiseg','fioff','foseg','fooff','fop')
    for index,(sample,context) in enumerate(zip(samples,contexts)):
        _keys(sample,('sample_index','context_rip','context_sha256','evidence'),'raw-state sample')
        _need(type(sample['sample_index']) is int and sample['sample_index']==index and
            type(sample['context_rip']) is int and sample['context_rip']==context['registers']['rip'] and
            sample['context_sha256']==_sha(_canonical(context)),'raw-state exact context/order')
        proof=sample['evidence']
        _keys(proof,('schema','architecture','measurement_accepted','fields','read_order','scalars','pointer_words'),'raw83 receipt')
        _need(proof['schema']=='gdb-amd64-x87-raw-v1' and proof['architecture']=='i386:x86-64'
            and proof['measurement_accepted'] is True and proof['read_order']==order,'raw83 architecture/reading order')
        fields=proof['fields'];_need(type(fields) is dict and set(fields)==set(NAMES),'exact raw83 coverage')
        for name,row in fields.items():
            _keys(row,('type_name','type_code','width_bytes','raw_hex','byte_order',
                'is_optimized_out','is_unavailable'),'raw83 field metadata')
            _need(row['byte_order']=='little' and row['is_optimized_out'] is False
                and row['is_unavailable'] is False,'raw83 complete original bits: '+name)
        check_state(fields,context)  # separate checker derives raw values/type widths
        _keys(proof['scalars'],scalars,'raw x87 words')
        for name,row in proof['scalars'].items():
            _keys(row,('raw_hex','type_name','type_code','width_bits','byte_order',
                'signed_value','unsigned_value'),'raw x87 scalar')
            raw=bytes.fromhex(fields[name]['raw_hex'])
            _need(row['raw_hex']==raw.hex() and row['type_name']=='int'
                and type(row['type_code']) is int and row['type_code']==8
                and type(row['width_bits']) is int and row['width_bits']==32
                and row['byte_order']=='little' and type(row['signed_value']) is int
                and row['signed_value']==int.from_bytes(raw,'little',signed=True)
                and type(row['unsigned_value']) is int and row['unsigned_value']==int.from_bytes(raw,'little'),
                'raw x87 signed/unsigned coherence: '+name)
        _keys(proof['pointer_words'],('instruction','operand'),'raw x87 pointer words')
        for label,lo,hi in [('instruction','fioff','fiseg'),('operand','fooff','foseg')]:
            row=proof['pointer_words'][label]
            _keys(row,('low_register','high_register','raw_hex','unsigned_value'),'raw pointer word')
            raw=bytes.fromhex(fields[lo]['raw_hex']+fields[hi]['raw_hex'])
            _need(row['low_register']==lo and row['high_register']==hi and row['raw_hex']==raw.hex()
                and type(row['unsigned_value']) is int and row['unsigned_value']==int.from_bytes(raw,'little'),
                'original composed raw pointer: '+label)
    return dict(verdict='PASS',sample_count=30,checked_fields_per_sample=83,
        state_acquisitions_sha256=_sha(_canonical(document)),numerical_certification=False)
