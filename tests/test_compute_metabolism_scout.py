"""Scout departure is separate from profile/numerical authority."""
from copy import deepcopy
import importlib
import json
from pathlib import Path
import os
import pytest

def api():
    return importlib.import_module('compute_metabolism.v0.scout'), importlib.import_module('compute_metabolism.v0.scout_check')

def test_adaptive_has_scout_entry_without_execution_authority():
    from compute_metabolism.v0 import adaptive
    assert callable(getattr(adaptive, 'scout', None))

@pytest.fixture
def case(tmp_path):
    scout, check = api()
    from compute_metabolism.v0.adaptive import elf_build_id
    from compute_metabolism.v0.evex_profile import _executable_elf
    import struct,hashlib
    def elf(kind,tool=False):
        raw=bytearray(1024);raw[:16]=b'\x7fELF\x02\x01\x01'+bytes(9)
        struct.pack_into('<HHIQQQIHHHHHH',raw,16,kind,62,1,0x400180,64,0,0,64,56,3 if tool else 2,0,0,0)
        struct.pack_into('<IIQQQQQQ',raw,64,1,5,0,0x400000,0x400000,1024,1024,4096)
        struct.pack_into('<IIQQQQQQ',raw,120,4,4,0x200,0x400200,0x400200,36,36,4)
        struct.pack_into('<III',raw,0x200,4,20,3);raw[0x20c:0x210]=b'GNU\0';raw[0x210:0x224]=bytes(range(20));raw[0x180]=0xc3
        if tool:
            interp=b'/lib64/ld-linux-x86-64.so.2\0'
            struct.pack_into('<IIQQQQQQ',raw,176,3,4,0x280,0x400280,0x400280,len(interp),len(interp),1)
            raw[0x280:0x280+len(interp)]=interp
        return bytes(raw)
    folder=tmp_path/'launch';folder.mkdir(mode=0o700)
    binaries={}
    for name,kind in [('runtime',2),('libc',3),('gala',3),('gdb',2)]:
        p=tmp_path/name;p.write_bytes(elf(kind,tool=name=='gdb'));p.chmod(0o755)
        binaries[name]=dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),build_id=elf_build_id(p.read_bytes()),role='EXECUTABLE' if name=='runtime' else 'TOOL' if name=='gdb' else 'SHARED_LIBRARY')
    root=Path(__file__).parents[1]
    epoch=json.loads((Path(__file__).with_name('fixtures')/'scout-epoch-final-connection.json').read_bytes())
    policy=scout.policy(root,epoch,binaries,folder,uid=os.getuid(),gid=os.getgid(),cpus=[0,1])
    raw=json.loads((Path(__file__).with_name('fixtures')/'scout-raw83.json').read_bytes())
    probe=dict(raw);probe['schema']='CPU_SCOUT_GDB_RAW_V1';probe['Gala']=False;probe['test_only']=True;probe['cwd']=str(folder);probe['kernel_roundtrip']['nop_code_hex']='9090';probe['gdb_version']='15.1';probe['architecture']='i386:x86-64';probe['fixture_sha256']=scout.sha(scout.fixture())
    probe['cpu_samples']=[dict(cpu=i,leaves={'0':dict(eax=13,ebx=0,ecx=0,edx=0),'1':dict(eax=0,ebx=0,ecx=(1<<26)|(1<<27)|(1<<28),edx=(1<<26)),'7':dict(eax=0,ebx=(1<<5)|(1<<8)|(1<<9)|(1<<16)|(1<<30)|(1<<31),ecx=0,edx=0),'13':dict(eax=0xe7,ebx=0,ecx=0,edx=0)},xcr0=0xe7) for i in [0,1]]
    probe['cpuid_code_hex']='534989d089f889f10fa241890041895804418948084189500c5bc3'
    probe['xgetbv_code_hex']='31c90f01d048c1e2204809d0c3'
    probe['uid']=os.getuid();probe['gid']=os.getgid()
    probe['affinity']=[0,1];probe['rlimit_as']=[4294967296,4294967296]
    fp=dict(schema='COMPUTE_METABOLISM_FINGERPRINT_V1',cpu_arch='x86_64',cpu_features=['avx2','avx512f','avx512bw','avx512vl','bmi2','erms'],v1_source_binding=policy['source_binding'])
    fp.update({n:{k:binaries[n][k] for k in ['path','sha256','build_id']} for n in ['runtime','libc','gala']});fp['libc']['memset_elf_entry']=0x1996c0
    env=dict(fingerprint=fp,kernel={'release':'test-kernel','boot_id':'test-boot','cpu_flags':fp['cpu_features']},cgroup={'raw':'0::/fixture\n','ancestors':[{'path':'/sys/fs/cgroup/fixture','cpu.max':'max 100000\n','memory.max':'max\n','memory.swap.max':'max\n','cpuset.cpus.effective':'0-1\n'},{'path':'/sys/fs/cgroup','cpu.max':None,'memory.max':None,'memory.swap.max':None,'cpuset.cpus.effective':'0-11\n'}]},gdb_version='15.1')
    bundle=scout.bundle(policy,env,probe,path_observation=None)
    return scout,check,root,policy,bundle

def test_full_raw83_handoff_scout_ready_is_not_accept(case):
    scout,check,root,policy,b=case
    verdict=check.verify(b,policy,root,require_path=False)
    assert verdict['status']=='STATE_TEST_PASS',verdict['reasons']
    assert verdict['body_allowed'] is False
    assert verdict['numerical_certification'] is False
    assert verdict['profile_promotion'] is False
    assert verdict['certified_state_progress'] is False
    assert verdict['checked_fields']==83

@pytest.mark.parametrize('mutation', ['source','ownership','library_role','elf_kind','hash','build_id','entry','type','width','raw','missing','register','nop','xcr0','cpuid','gdb','self_pass'])
def test_past_failures_and_tampering_block_before_gala(case,mutation):
    scout,check,root,policy,b=case
    p=deepcopy(policy);d=deepcopy(b)
    if mutation=='source':p['source_binding']='0'*64
    elif mutation=='ownership':p['uid']+=1
    elif mutation=='library_role':p['binaries']['libc']['role']='EXECUTABLE'
    elif mutation=='elf_kind':p['binaries']['runtime']=deepcopy(p['binaries']['libc']);p['binaries']['runtime']['role']='EXECUTABLE'
    elif mutation=='hash':p['binaries']['libc']['sha256']='0'*64
    elif mutation=='build_id':p['binaries']['libc']['build_id']='00'
    elif mutation=='entry':p['expected_entry']=1
    elif mutation=='type':d['probe']['fields']['fioff']['type_name']='unsigned int'
    elif mutation=='width':d['probe']['fields']['fioff']['width_bytes']=8
    elif mutation=='raw':d['probe']['fields']['fioff']['raw_hex']='00000000'
    elif mutation=='missing':d['probe']['fields'].pop('fooff')
    elif mutation=='register':d['probe']['seeded_state']['registers']['rbx']^=1
    elif mutation=='nop':d['probe']['kernel_roundtrip']['nop_instructions']=3
    elif mutation=='xcr0':d['probe']['cpu_samples'][0]['xcr0']=7
    elif mutation=='cpuid':d['probe']['cpu_samples'][0]['leaves']['7']['ebx']=0
    elif mutation=='gdb':d['probe']['gdb_version']='unexpected'
    else:d['status']='SCOUT_READY';d['profile_promotion']=True
    d['policy_sha256']=scout.digest(p)
    verdict=check.verify(d,p,root,require_path=False)
    assert verdict['status'] in ['SCOUT_REFUSED','SCOUT_UNKNOWN']
    assert verdict['body_allowed'] is False
    assert verdict['profile_promotion'] is False

def test_unknown_data_is_never_filled(case):
    scout,check,root,p,d=case;d['probe']=None;d['unknown']=['fooff']
    v=check.verify(d,p,root,require_path=False)
    assert v['status']=='SCOUT_UNKNOWN'
    assert v['checked_fields']==0
    assert 'fooff' in v['unknown']

def test_file_replacement_is_refused(case):
    scout,check,root,p,d=case;Path(p['binaries']['runtime']['path']).write_bytes(b'corrupt')
    assert check.verify(d,p,root,require_path=False)['status']=='SCOUT_REFUSED'

def test_model_name_alone_cannot_reuse(case):
    scout,check,root,p,d=case
    assert scout.reuse_plan(d,p,d['environment'],root,require_path=False,live_probe=d['probe'])['reuse_probe'] is True
    e=deepcopy(d['environment']);e['kernel']['boot_id']='new'
    assert scout.reuse_plan(d,p,e,root,require_path=False,live_probe=d['probe'])['reuse_probe'] is False
    changed=deepcopy(d);changed['probe']['seeded_fields']['k7']['raw_hex']='00'*8
    assert scout.reuse_plan(changed,p,d['environment'],root,require_path=False,live_probe=d['probe'])['reuse_probe'] is False

def test_unsigned_interpretation_uses_actual_raw_bits(case):
    scout,check,root,p,d=case
    assert d['probe']['raw_evidence']['scalars']['fioff']['signed_value']==-1964020589
    assert check.verify(d,p,root,require_path=False)['status']=='STATE_TEST_PASS'

def test_missing_path_blocks_complete_scout(case):
    scout,check,root,p,d=case
    assert check.verify(d,p,root)['status']=='SCOUT_UNKNOWN'

def test_exclusive_bounded_machine_readable_artifact(case,tmp_path):
    scout,check,root,p,d=case;out=tmp_path/'proof'
    scout.save(out,d)
    with pytest.raises((FileExistsError,ValueError)):scout.save(out,d)
    assert json.loads(out.read_bytes())['schema']=='CPU_SCOUT_BUNDLE_V1'

def test_reuse_requires_fresh_header(case):
    scout,check,root,p,d=case
    assert scout.reuse_plan(d,p,d['environment'],root,require_path=False)['reuse_probe'] is False

def test_actual_output_directory_contract_precedes_probe(case,tmp_path):
    scout,check,root,p,d=case
    with pytest.raises(ValueError,match='outside approved execution directory'):
        scout.run(p,root,{},tmp_path/'outside')
    assert not (tmp_path/'outside').exists()

def full_path(case):
    scout,check,root,p,d=case
    fp=d['environment']['fingerprint'];fp['libc']['memset_elf_entry']=0x400180
    destination=0x900020;initial='a5'*80;final='a5'*32+'00'*16+'a5'*32
    path=dict(schema='COMPUTE_METABOLISM_OBSERVATION_V1',mode='OBSERVATION',
        certified_state_progress=False,promotion_allowed=False,fingerprint=deepcopy(fp),
        fingerprint_sha256=scout.digest(fp),library=deepcopy(p['binaries']['libc']),
        call_origin=dict(kind='SYNTHETIC_PYTHON_CTYPES',authorized_gala_call=False),
        entry=0x400180,input=dict(length=16,value=0,destination=destination,window_address=destination-32,
            window_size=80,initial_window_hex=initial),
        observed_result=dict(return_value=destination,destination_hex='00'*16,final_window_hex=final),
        terminal=dict(status='OBSERVED_RETURN',complete=True),trace=[
            dict(seq=0,pc=0x400180,absolute_pc=0x400180,instruction_bytes='c3',bytes='c3',
                assembly='ret',reads=[],writes=[],before={},after={})])
    path['library']['load_base']=0x70000000
    absolute=0x70000000+0x400180;ret=0x80000000
    path['call_origin']['native_caller']={'return_pc':ret}
    path['trace'][0].update(absolute_pc=absolute,next_pc=ret-0x70000000,absolute_next_pc=ret,
        before={'registers':{'rip':absolute,'rax':0}},
        after={'registers':{'rip':ret,'rax':destination}})
    path['start_state']=deepcopy(path['trace'][0]['before'])
    path['end_state']=deepcopy(path['trace'][0]['after'])
    d['path_observation']=path
    return path

def test_full_environment_raw83_path_independent_departure(case):
    scout,check,root,p,d=case;full_path(case)
    result=check.verify(d,p,root)
    assert result['status']=='SCOUT_READY',result
    assert result['actual_path']['instructions']==1
    assert result['checked_fields']==83 and result['body_allowed'] is False

@pytest.mark.parametrize('mutation',['origin','code','pc','entry','result','guard','length','schema','nop_bytes','cwd','Gala','authority','mxcsr','ftw'])
def test_complete_handoff_mutants_are_recomputed(case,mutation):
    scout,check,root,p,d=case;path=full_path(case)
    if mutation=='origin':path['call_origin']['authorized_gala_call']=True
    elif mutation=='code':path['trace'][0]['instruction_bytes']='90'
    elif mutation=='pc':path['trace'][0]['pc']+=1
    elif mutation=='entry':path['entry']+=1
    elif mutation=='result':path['observed_result']['return_value']+=1
    elif mutation=='guard':path['observed_result']['final_window_hex']='00'+path['observed_result']['final_window_hex'][2:]
    elif mutation=='length':path['input']['length']=17
    elif mutation=='schema':d['probe']['schema']='HISTORICAL_PROBE'
    elif mutation=='nop_bytes':d['probe']['kernel_roundtrip']['nop_code_hex']='9091'
    elif mutation=='cwd':d['probe']['cwd']='/wrong'
    elif mutation=='Gala':d['probe']['Gala']=True
    elif mutation=='authority':d['numerical_certification']=True
    elif mutation=='mxcsr':
        for fk,sk in [('fields','state'),('seeded_fields','seeded_state')]:
            d['probe'][fk]['mxcsr']['raw_hex']='811f0000'
            d['probe'][sk]['registers']['mxcsr']=0x1f81
    elif mutation=='ftw':d['probe']['fxsave_hex']=d['probe']['fxsave_hex'][:8]+'00'+d['probe']['fxsave_hex'][10:]
    result=check.verify(d,p,root)
    assert result['status']=='SCOUT_REFUSED',result
    assert result['body_allowed'] is False

def test_dso_cannot_masquerade_as_GDB(case):
    scout,check,root,p,d=case
    p['binaries']['gdb']=deepcopy(p['binaries']['libc']);p['binaries']['gdb']['role']='TOOL'
    d['policy_sha256']=scout.digest(p)
    result=check.verify(d,p,root,require_path=False)
    assert result['status']=='SCOUT_REFUSED'
    assert 'header' in str(result['reasons']) or 'interpreter' in str(result['reasons'])

def test_producer_to_checker_and_candidate_without_Gala(case,monkeypatch):
    scout,check,root,p,d=case;full_path(case)
    monkeypatch.chdir(p['execution_directory'])
    monkeypatch.setattr(scout,'environment',lambda *args:deepcopy(d['environment']))
    monkeypatch.setattr(scout,'probe',lambda *args,**kwargs:(deepcopy(d['probe']),None))
    from compute_metabolism.v0 import observer,adaptive
    monkeypatch.setattr(observer,'observe_memset',lambda fp,out,**kw:deepcopy(d['path_observation']) if out.name=='observation.raw.json' else (_ for _ in ()).throw(ValueError('filename contract')))
    monkeypatch.setattr(adaptive,'load_registry',lambda *args,**kw:[])
    out=Path(p['execution_directory'])/'handoff'
    result=adaptive.scout(p,root,{},out)
    assert result['status']=='SCOUT_READY' and result['body_allowed'] is False
    manifest=json.loads((out/'candidate/candidate-profile.json').read_bytes())
    assert manifest['status']=='CANDIDATE' and manifest['verification']['authority'] is None
    assert json.loads((out/'independent-verdict.json').read_bytes())['checked_fields']==83

@pytest.mark.parametrize('key,value',[('schema','wrong'),('Gala',True),('test_only',False),('cwd','/wrong'),('uid',True),('gid',True)])
def test_live_reuse_header_envelope_is_required(case,key,value):
    scout,check,root,p,d=case
    live=deepcopy(d['probe']);live[key]=value
    assert scout.reuse_plan(d,p,d['environment'],root,require_path=False,live_probe=live)['reuse_probe'] is False

@pytest.mark.parametrize('mutation',['library_sha','library_build','load_base','absolute_pc','absolute_next','next_pc','start','end','return_target'])
def test_actual_path_identity_and_pc_seams(case,mutation):
    scout,check,root,p,d=case;path=full_path(case)
    if mutation=='library_sha':path['library']['sha256']='0'*64
    elif mutation=='library_build':path['library']['build_id']='00'
    elif mutation=='load_base':path['library']['load_base']+=1
    elif mutation=='absolute_pc':path['trace'][0]['absolute_pc']+=1
    elif mutation=='absolute_next':path['trace'][0]['absolute_next_pc']+=1
    elif mutation=='next_pc':path['trace'][0]['next_pc']+=1
    elif mutation=='start':path['start_state']['registers']['rip']+=1
    elif mutation=='end':path['end_state']['registers']['rip']+=1
    else:path['call_origin']['native_caller']['return_pc']+=1
    assert check.verify(d,p,root)['status']=='SCOUT_REFUSED'

@pytest.mark.parametrize('missing',['all','cpu.max','memory.max','memory.swap.max','cpuset.cpus.effective','ancestors'])
def test_missing_resource_map_is_unknown(case,missing):
    scout,check,root,p,d=case
    if missing=='ancestors':d['environment']['cgroup'].pop('ancestors')
    else:
        for row in d['environment']['cgroup']['ancestors']:
            for name in ['cpu.max','memory.max','memory.swap.max','cpuset.cpus.effective']:
                if missing in ['all',name]:row[name]=None
    assert check.verify(d,p,root,require_path=False)['status']=='SCOUT_UNKNOWN'

@pytest.mark.parametrize('field,value',[('cpu.max','bad'),('memory.max','-1'),('cpuset.cpus.effective','0'),('memory.max','1024'),('cpu.max','100000 100000')])
def test_invalid_or_insufficient_resource_map_refused(case,field,value):
    scout,check,root,p,d=case;d['environment']['cgroup']['ancestors'][0][field]=value
    assert check.verify(d,p,root,require_path=False)['status']=='SCOUT_REFUSED'

@pytest.mark.parametrize('mutation',['traversal','symlink'])
def test_output_uses_real_containment_before_probe(case,monkeypatch,tmp_path,mutation):
    scout,check,root,p,d=case
    monkeypatch.chdir(p['execution_directory'])
    outside=tmp_path/'escaped';outside.mkdir()
    if mutation=='traversal':output=Path(p['execution_directory'])/'..'/'escaped'/'out'
    else:
        alias=Path(p['execution_directory'])/'alias';alias.symlink_to(outside,target_is_directory=True)
        output=alias/'out'
    called=[]
    monkeypatch.setattr(scout,'probe',lambda *args,**kw:called.append('native'))
    with pytest.raises(ValueError):scout.run(p,root,{},output)
    assert not called and not (outside/'out').exists()

def test_direct_probe_cannot_write_outside_approved_directory(case,monkeypatch,tmp_path):
    scout,check,root,p,d=case
    monkeypatch.chdir(p['execution_directory'])
    monkeypatch.setattr(scout,'_run',lambda *args,**kwargs:dict(returncode=1,stdout='',stderr='',stop_reason=None))
    with pytest.raises(ValueError,match='outside approved execution directory'):scout.probe(p,root,tmp_path/'outside-probe')
    assert not (tmp_path/'outside-probe').exists()
