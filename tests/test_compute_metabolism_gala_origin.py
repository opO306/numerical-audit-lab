"""Hand-authored origin/ISA fixtures using the unchanged actual pinned ELFs.

No Gala invocation occurs here. Literal synthetic process/state fixtures check
the independent verifier; they cannot authorize a live profile or campaign.
"""
import copy
import hashlib
import importlib
import json
from pathlib import Path

import pytest

from verified_driver.v1.native_evex_checker import _elf
from test_v1_evex_checker import context, PATH


ROOT = Path(__file__).resolve().parents[1]
LIBC = ROOT/'runtime_trace/frozen_binaries/libc.so.6'
GALA = ROOT/'audit/gate2c1/vendor/gala/integrate/cyintegrators/leapfrog.cpython-312-x86_64-linux-gnu.so'
GALA_BASE = 0x5000000000
LIBC_BASE = 0x7000000000
DEST = 0x20002040
RETURN = GALA_BASE+0x3568e
STACK = 0x30000000
CONTROL_CODE = '534989d089f889f10fa241890041895804418948084189500c5bc3'


def checker():
    try:
        return importlib.import_module('compute_metabolism.v0.gala_origin_check')
    except ModuleNotFoundError:
        pytest.fail('independent actual Gala origin gate has not been implemented')


def content(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),
        ensure_ascii=True,allow_nan=False).encode('ascii')).hexdigest()


def fixture(tmp_path):
    libraw, callerraw = LIBC.read_bytes(), GALA.read_bytes()
    libsha, callsha = hashlib.sha256(libraw).hexdigest(),hashlib.sha256(callerraw).hexdigest()
    assert libsha == '3a15d66867d83762c7f2f1e37359cb8f6c5743edb369c65285cb0b1c4f7498bf'
    assert callsha == 'a6ac98736304bb9f6a92e473bba45da10d9b5b99f8019e2ca15eb6a7f86234fc'
    libid, callerid = _elf(libraw)[1],_elf(callerraw)[1]
    repo = tmp_path/'independent-source';repo.mkdir()
    (repo/'binding-proof.py').write_bytes(b'# independently frozen source fixture\n')
    sources = {'binding-proof.py':hashlib.sha256((repo/'binding-proof.py').read_bytes()).hexdigest()}
    binding = content(sources)
    fp = dict(schema='COMPUTE_METABOLISM_FINGERPRINT_V1',cpu_arch='x86_64',
        cpu_features=['avx512f','avx512bw','avx512vl','bmi2'],v1_source_binding=binding,
        libc=dict(path=str(LIBC),sha256=libsha,build_id=libid,memset_elf_entry=0x1996c0),
        gala=dict(path=str(GALA),sha256=callsha,build_id=callerid))
    birth = dict(pid=4321,linux_boot_id='11111111-2222-3333-4444-555555555555',proc_stat_start_time_ticks=1234)
    before = context()
    before['registers'].update(rip=GALA_BASE+0x35689,rsp=STACK+8,rdi=DEST,rsi=0,rdx=16)
    after = copy.deepcopy(before);after['registers'].update(rip=GALA_BASE+0x6350,rsp=STACK)
    entry = copy.deepcopy(after);entry['registers']['rip']=LIBC_BASE+0x1996c0
    caller = dict(path=str(GALA),sha256=callsha,build_id=callerid,load_base=GALA_BASE,
        elf_pc=0x35689,instruction_bytes='e8c20cfdff',return_pc=RETURN,
        plt_elf_pc=0x6350,plt_instruction_bytes='ff253aae0300',got_elf_address=0x41190,
        got_address=GALA_BASE+0x41190,got_bytes_hex=(LIBC_BASE+0x1996c0).to_bytes(8,'little').hex(),
        before=before,after_call=after,entry=entry,
        stack_write=dict(address=STACK,size=8,before_hex='00'*8,after_hex=RETURN.to_bytes(8,'little').hex()))
    domain=dict(provenance_kind='ACTUAL_GALA_CALL',source_sha256=binding,
        caller_module_sha256=callsha,caller_elf_pc=0x35689,caller_instruction_bytes='e8c20cfdff',
        caller_return_pc=RETURN,caller_load_base=GALA_BASE,caller_path=str(GALA),caller_build_id=callerid,
        destination=DEST,length=16,fill=0,libc_sha256=libsha,libc_build_id=libid)
    changes = [{},{},{'rax':DEST},{'eflags':0x287},{},
        {'rdi':0x40,'eflags':0x202},{'eflags':0x287},{},
        {'rcx':0xffffffff},{'rcx':0xffff,'eflags':0x206},{'k1':0xffff},{},{'rsp':STACK+8}]
    nexts=[pc for pc,_ in PATH[1:]]+[RETURN-LIBC_BASE]
    current=copy.deepcopy(entry);steps=[]
    for index,(pc,code) in enumerate(PATH):
        pre=copy.deepcopy(current)
        current['registers'].update(changes[index],rip=LIBC_BASE+nexts[index])
        if index==1:current['vectors']['zmm16']='00'*64
        reads=[dict(address=STACK,size=8,bytes_hex=RETURN.to_bytes(8,'little').hex())] if index==12 else []
        writes=[dict(address=DEST+i,size=1,after_hex='00') for i in range(16)] if index==11 else []
        steps.append(dict(elf_pc=pc,instruction_bytes=code,before=pre,after=copy.deepcopy(current),reads=reads,writes=writes))
    native=dict(schema='native-evex-trace-v1',library=dict(sha256=libsha,build_id=libid),
        load_base=LIBC_BASE,domain=domain,entry=copy.deepcopy(entry),exit=copy.deepcopy(current),steps=steps)
    observation=dict(schema='gala-native-observation-v1',source_snapshot=sources,source_binding=binding,
        fingerprint=fp,process_identity=birth,thread_ptid=[4321,4322,0],
        control_witness=dict(acquisition_code_hex=CONTROL_CODE,max_basic_leaf=7,leaf=7,subleaf=0,
            eax=0,ebx=(1<<16)|(1<<30)|(1<<31)|(1<<8),ecx=0,edx=0),
        caller=caller,native=native,termination=dict(inferior_killed=True,remaining_owned_pids=[],certified_state_progress=False))
    return observation,repo,copy.deepcopy(fp),copy.deepcopy(sources),copy.deepcopy(birth)


def verify(rows):
    doc,repo,fp,sources,birth=rows
    return checker().verify_observation(doc,repo,fp,sources,LIBC,GALA,birth)


def test_fixed_actual_elf_hand_literal_origin_call_plt_got_and_native_replay(tmp_path):
    result=verify(fixture(tmp_path))
    assert result['verdict']=='PASS'
    assert result['scope']=='ACTUAL_GALA_ORIGIN_AND_FINITE_NATIVE_EFFECTS'
    assert result['native']['instruction_count']==13
    assert result['native']['write_count']==16
    assert result['promotion_allowed'] is False
    assert result['numerical_certification'] is False


@pytest.mark.parametrize('attack',['resultbit','outsidewrite','preservedreg','codebyte','samevaluewriteomission',
    'caller','entry','mask','length','nonzerofill','otherlibc'])
def test_eleven_required_adversarial_classes_refuse(tmp_path,attack):
    rows=fixture(tmp_path);doc=rows[0];native=doc['native']
    if attack=='resultbit':native['steps'][9]['after']['registers']['rcx']^=1
    elif attack=='outsidewrite':native['steps'][11]['writes'].append(dict(address=DEST+16,size=1,after_hex='00'))
    elif attack=='preservedreg':doc['caller']['after_call']['registers']['rbx']^=1
    elif attack=='codebyte':native['steps'][1]['instruction_bytes']='62e27d287ac7'
    elif attack=='samevaluewriteomission':native['steps'][11]['writes'].pop()
    elif attack=='caller':doc['caller']['sha256']='03'*32
    elif attack=='entry':doc['caller']['entry']['registers']['rip']+=1
    elif attack=='mask':native['steps'][10]['after']['registers']['k1']=0x7fff
    elif attack=='length':doc['caller']['before']['registers']['rdx']=15
    elif attack=='nonzerofill':doc['caller']['before']['registers']['rsi']=0x100
    elif attack=='otherlibc':doc['fingerprint']['libc']['sha256']='04'*32
    with pytest.raises(ValueError):verify(rows)


@pytest.mark.parametrize('attack',['call_pc','call_bytes','return','plt_bytes','got_address','got_target',
    'stack_address','stack_size','stack_bytes','stack_alias_destination','call_fp','plt_k','missing_fp',
    'pid','thread','source_binding','source_snapshot','fingerprint','cet_shstk','cet_ibt',
    'no_leaf7','missing_bmi2','missing_avx512f','missing_avx512bw','missing_avx512vl','cpuid_code','termination','bool_pid'])
def test_origin_state_cpu_identity_and_termination_boundaries_refuse(tmp_path,attack):
    rows=fixture(tmp_path);doc=rows[0];caller=doc['caller'];control=doc['control_witness']
    if attack=='call_pc':caller['elf_pc']+=1
    elif attack=='call_bytes':caller['instruction_bytes']='e8c30cfdff'
    elif attack=='return':caller['return_pc']+=1
    elif attack=='plt_bytes':caller['plt_instruction_bytes']='ff253bae0300'
    elif attack=='got_address':caller['got_address']+=8
    elif attack=='got_target':caller['got_bytes_hex']='00'*8
    elif attack=='stack_address':caller['stack_write']['address']+=8
    elif attack=='stack_size':caller['stack_write']['size']=True
    elif attack=='stack_bytes':caller['stack_write']['after_hex']='00'*8
    elif attack=='stack_alias_destination':caller['before']['registers']['rdi']=STACK
    elif attack=='call_fp':caller['after_call']['fpu']['st7']='00'*10
    elif attack=='plt_k':caller['entry']['registers']['k7']^=1
    elif attack=='missing_fp':caller['before'].pop('fpu')
    elif attack=='pid':doc['process_identity']['pid']+=1
    elif attack=='thread':doc['thread_ptid'][0]+=1
    elif attack=='source_binding':doc['source_binding']='00'*32
    elif attack=='source_snapshot':doc['source_snapshot']={}
    elif attack=='fingerprint':doc['fingerprint']={}
    elif attack=='cet_shstk':control['ecx']|=1<<7
    elif attack=='cet_ibt':control['edx']|=1<<20
    elif attack=='no_leaf7':control['max_basic_leaf']=6
    elif attack.startswith('missing_'):
        bit={'missing_bmi2':8,'missing_avx512f':16,'missing_avx512bw':30,'missing_avx512vl':31}[attack]
        control['ebx']&=~(1<<bit)
    elif attack=='cpuid_code':control['acquisition_code_hex']='90'
    elif attack=='termination':doc['termination']['remaining_owned_pids']=[4321]
    elif attack=='bool_pid':doc['process_identity']['pid']=True
    with pytest.raises(ValueError):verify(rows)


def test_current_source_bytes_are_checked_without_importing_sources(tmp_path):
    rows=fixture(tmp_path)
    (rows[1]/'binding-proof.py').write_bytes(b'# drifted independently frozen source\n')
    with pytest.raises(ValueError):verify(rows)


def test_expected_inputs_are_never_mutated_or_promoted(tmp_path):
    rows=fixture(tmp_path);before=copy.deepcopy(rows[:1]+rows[2:])
    verify(rows)
    assert rows[:1]+rows[2:]==before


@pytest.mark.parametrize('label',['ibt','user_shstk','shstk'])
def test_contradictory_frozen_cet_label_is_refused(tmp_path,label):
    witness=dict(acquisition_code_hex=CONTROL_CODE,max_basic_leaf=7,leaf=7,subleaf=0,
        eax=0,ebx=sum(1<<bit for bit in (8,16,30,31)),ecx=0,edx=0)
    with pytest.raises(ValueError,match='CET'):
        checker()._control(witness,['avx512f','avx512bw','avx512vl','bmi2',label])


@pytest.mark.parametrize('module',['libc','gala'])
def test_new_elf_and_rebound_fingerprint_cannot_override_fixed_production_sha(tmp_path,module):
    doc,repo,fp,sources,birth=fixture(tmp_path)
    source=LIBC if module=='libc' else GALA
    image=bytearray(source.read_bytes());image[-1]^=1
    replacement=tmp_path/('replacement-'+module+'.so');replacement.write_bytes(image)
    rebinding=hashlib.sha256(image).hexdigest()
    fp[module]['sha256']=rebinding;doc['fingerprint']=copy.deepcopy(fp)
    if module=='gala':doc['caller'].update(path=str(replacement),sha256=rebinding)
    with pytest.raises(ValueError,match='fixed libc/Gala SHA'):
        checker().verify_observation(doc,repo,fp,sources,
            replacement if module=='libc' else LIBC,replacement if module=='gala' else GALA,birth)


@pytest.mark.parametrize('rip,cs',[(0xffffffff,0x33),(0x100000000,0x30),
    (0x100000000,True),(True,0x33)])
def test_actual_execution_mode_requires_high_rip_and_observed_user_selector(rip,cs):
    with pytest.raises(ValueError):
        checker()._mode64(dict(registers=dict(rip=rip,cs=cs)))


def test_actual_execution_mode_witness_uses_observed_values():
    assert checker()._mode64(dict(registers=dict(rip=0x100000000,cs=0x33))) is None
