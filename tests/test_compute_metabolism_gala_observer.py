"""Bounded original Gala observer launch; no numerical run in these tests."""
import importlib
import os
from pathlib import Path
import pytest
from compute_metabolism.v0 import adaptive
from compute_metabolism.v0.system_guard import INNER_PYTHON
from runtime_trace.regular_nstep.resources import reserve_writer as REAL_RESERVE_WRITER

ROOT=Path(__file__).resolve().parents[1]

def api():return importlib.import_module('compute_metabolism.v0.gala_observer')

@pytest.fixture(autouse=True)
def guarded_fixture(tmp_path,monkeypatch):
    from runtime_trace.regular_nstep import resources
    quota=tmp_path/'writer_quota.txt';quota.write_text('0')
    monkeypatch.setenv('RTN_QUOTA_FILE',str(quota))
    monkeypatch.setenv('RTN_QUOTA_BYTES','671088640')
    monkeypatch.setattr(resources,'reserve_writer',lambda count:None)


@pytest.mark.parametrize('raw',[b'{"interrupted":',b'x'*(2*1024*1024+1)],ids=['interrupted','oversize'])
def test_unparseable_actual_bytes_and_launch_logs_survive_scratch_cleanup(tmp_path,monkeypatch,raw):
    import json
    mod=api();monkeypatch.setattr(mod,'_identity',lambda *args:None)
    def run(args,env,timeout,cap):
        config=json.loads(Path(env['CM_GALA_OBSERVER_CONFIG']).read_bytes())
        Path(config['result']).write_bytes(raw)
        return dict(returncode=-9,stop_reason='STOP_TIMEOUT',diagnostic=None,stdout='actual stdout',stderr='actual stderr')
    monkeypatch.setattr(mod,'_run',run)
    fp={name:{'path':'/prepared/'+name} for name in ('runtime','libc','gala')}
    result=mod.observe_gala(fp,tmp_path/'gala-observation.raw.json',ROOT,gdb_sha256='a'*64,source_snapshot={'one.py':'b'*64})
    assert result['diagnostic']['stage']=='raw-result-parse'
    assert (tmp_path/'gala-gdb-result.raw').read_bytes()==raw[:1024*1024]
    launch=json.loads((tmp_path/'gala-launch.json').read_bytes())
    assert launch['process']['stdout']=='actual stdout'
    assert launch['outcome']=='OBSERVATION_FAILED'
    assert launch['raw_result']['actual_size']==len(raw)
    assert launch['raw_result']['truncated']==(len(raw)>2*1024*1024)


def test_quota_exhaustion_refuses_before_any_launch_or_identity(tmp_path,monkeypatch):
    from runtime_trace.regular_nstep import resources
    def exhausted(count):raise resources.ResourceRefused('exhausted')
    monkeypatch.setattr(resources,'reserve_writer',exhausted)
    monkeypatch.setattr(api(),'_run',lambda *args:pytest.fail('launch after exhausted quota'))
    monkeypatch.setattr(api(),'_identity',lambda *args:pytest.fail('identity after exhausted quota'))
    with pytest.raises(resources.ResourceRefused):
        api().observe_gala({},tmp_path/'gala-observation.raw.json',ROOT,gdb_sha256='a'*64,source_snapshot={})


def test_actual_shared_quota_binding_and_reservation_precedes_launch(tmp_path,monkeypatch):
    import json
    from runtime_trace.regular_nstep import resources
    calls=[];monkeypatch.setattr(resources,'reserve_writer',lambda n:calls.append(n))
    monkeypatch.setattr(api(),'_identity',lambda *args:None)
    def run(args,env,timeout,cap):
        assert calls==[16*1024*1024]
        config=json.loads(Path(env['CM_GALA_OBSERVER_CONFIG']).read_bytes())
        assert config['writer_reservation']==dict(path=env['RTN_QUOTA_FILE'],maximum_bytes=671088640,reserved_bytes=16*1024*1024)
        Path(config['result']).write_bytes(b'{"diagnostic":{"stage":"fixture"}}')
        return dict(returncode=2,stop_reason=None,diagnostic=None,stdout='',stderr='')
    monkeypatch.setattr(api(),'_run',run)
    fp={name:{'path':'/prepared/'+name} for name in ('runtime','libc','gala')}
    api().observe_gala(fp,tmp_path/'gala-observation.raw.json',ROOT,gdb_sha256='a'*64,source_snapshot={})


@pytest.mark.skipif(os.name=='nt',reason='original quota helper uses Linux flock')
@pytest.mark.parametrize('initial,allowed',[(0,True),(630*1024*1024,False)])
def test_original_shared_quota_really_debits_or_refuses_before_acquisition(tmp_path,monkeypatch,initial,allowed):
    import json
    from runtime_trace.regular_nstep import resources
    quota=Path(os.environ['RTN_QUOTA_FILE']);quota.write_text(str(initial))
    monkeypatch.setattr(resources,'reserve_writer',REAL_RESERVE_WRITER)
    def identity(*args):
        assert allowed
        assert int(quota.read_text())==initial+16*1024*1024
    monkeypatch.setattr(api(),'_identity',identity)
    def run(args,env,timeout,cap):
        config=json.loads(Path(env['CM_GALA_OBSERVER_CONFIG']).read_bytes())
        Path(config['result']).write_bytes(b'{"diagnostic":{"stage":"literal"}}')
        return dict(returncode=2,stop_reason=None,diagnostic=None,stdout='',stderr='')
    monkeypatch.setattr(api(),'_run',run)
    fp={name:{'path':'/prepared/'+name} for name in ('runtime','libc','gala')}
    if allowed:
        api().observe_gala(fp,tmp_path/'gala-observation.raw.json',ROOT,gdb_sha256='a'*64,source_snapshot={})
        assert int(quota.read_text())==16*1024*1024
    else:
        with pytest.raises(resources.ResourceRefused):
            api().observe_gala(fp,tmp_path/'gala-observation.raw.json',ROOT,gdb_sha256='a'*64,source_snapshot={})
        assert int(quota.read_text())==initial


def test_private_parent_birth_and_original_config_environment_are_retained(tmp_path,monkeypatch):
    import json
    mod=api();monkeypatch.setattr(mod,'_identity',lambda *args:None)
    birth=b'{"actual_private_parent_birth":1234}'
    captured={}
    def run(args,env,timeout,cap):
        config=json.loads(Path(env['CM_GALA_OBSERVER_CONFIG']).read_bytes())
        captured.update(config=config,env=env,path=env['CM_GALA_OBSERVER_CONFIG'],args=args)
        Path(config['birth']).write_bytes(birth)
        Path(config['candidate_birth']).write_bytes(b'{"pid":4321}')
        Path(config['result']).write_bytes(b'{"process_identity":{"fake":true},"diagnostic":{"stage":"fixture"}}')
        return dict(returncode=2,stop_reason=None,diagnostic=None,stdout='',stderr='')
    monkeypatch.setattr(mod,'_run',run)
    fp={name:{'path':'/prepared/'+name} for name in ('runtime','libc','gala')}
    mod.observe_gala(fp,tmp_path/'gala-observation.raw.json',ROOT,gdb_sha256='a'*64,source_snapshot={})
    launch=json.loads((tmp_path/'gala-launch.json').read_bytes())
    assert (tmp_path/'gala-owned-birth.raw').read_bytes()==birth
    assert launch['owned_process_identity']=={'actual_private_parent_birth':1234}
    assert launch['environment']==captured['env'] and launch['command']==captured['args']
    assert launch['original_config_path']==captured['path']
    assert json.loads((tmp_path/'gala-observer-config.json').read_bytes())==captured['config']
    assert launch['owned_birth']['original_path']==captured['config']['birth']
    assert launch['raw_result']['original_path']==captured['config']['result']


def test_malformed_parent_birth_is_kept_and_classified_failed(tmp_path,monkeypatch):
    import json
    mod=api();monkeypatch.setattr(mod,'_identity',lambda *args:None)
    def run(args,env,timeout,cap):
        config=json.loads(Path(env['CM_GALA_OBSERVER_CONFIG']).read_bytes())
        Path(config['birth']).write_bytes(b'{partial-private-birth')
        Path(config['result']).write_bytes(b'{}')
        return dict(returncode=0,stop_reason=None,diagnostic=None,stdout='',stderr='')
    monkeypatch.setattr(mod,'_run',run)
    fp={name:{'path':'/prepared/'+name} for name in ('runtime','libc','gala')}
    result=mod.observe_gala(fp,tmp_path/'gala-observation.raw.json',ROOT,gdb_sha256='a'*64,source_snapshot={})
    assert 'birth_diagnostic' in result
    assert (tmp_path/'gala-owned-birth.raw').read_bytes()==b'{partial-private-birth'
    assert json.loads((tmp_path/'gala-launch.json').read_bytes())['outcome']=='OBSERVATION_FAILED'


def test_artifact_write_and_command_environment_have_hard_bounds(tmp_path,monkeypatch):
    with pytest.raises(ValueError):api().write_bounded(tmp_path/'oversize',b'x'*65,64)
    assert not (tmp_path/'oversize').exists()
    monkeypatch.setenv('PATH','x'*262145)
    config=api().build_config(ROOT,tmp_path,{'runtime':{'path':'/prepared/python'}},'a'*64,{})
    with pytest.raises(ValueError,match='command/environment'):
        api().launch_spec(ROOT,config,tmp_path/'config.json')


@pytest.mark.parametrize('maximum',['671088641','0','-1','640MiB'])
def test_invalid_or_increased_quota_refuses_before_launch(tmp_path,monkeypatch,maximum):
    monkeypatch.setenv('RTN_QUOTA_BYTES',maximum)
    monkeypatch.setattr(api(),'_run',lambda *args:pytest.fail('invalid quota launch'))
    with pytest.raises(ValueError):api().observe_gala({},tmp_path/'gala-observation.raw.json',ROOT,gdb_sha256='a'*64,source_snapshot={})

def test_launch_uses_original_parameter_only_harness_one_step_and_no_store(tmp_path,monkeypatch):
    monkeypatch.setenv('RTN_QUOTA_FILE','/owned/writer_quota.txt')
    monkeypatch.setenv('RTN_QUOTA_BYTES','671088640')
    fp={'runtime':{'path':'/prepared/python'},'libc':{'path':'/prepared/libc'},'gala':{'path':'/prepared/gala'}}
    config=api().build_config(ROOT,tmp_path,fp,'a'*64,{'one.py':'b'*64})
    args,env=api().launch_spec(ROOT,config,tmp_path/'config.json')
    assert args[-2:]==['-B',str(ROOT/'verified_driver/v1/live_chain/harness.py')]
    assert args[-3]==INNER_PYTHON
    assert env['RTN_STEPS']=='1'
    assert env['OMP_NUM_THREADS']==env['OPENBLAS_NUM_THREADS']=='1'
    assert env['RTN_QUOTA_FILE']=='/owned/writer_quota.txt'
    assert env['RTN_QUOTA_BYTES']=='671088640'
    assert not any('V1_STORE' in key or 'CURRENT' in key or 'V1_SESSION' in key for key in env)
    assert config['certified_state_progress'] is False
    assert config['max_native_steps']==13
    assert config['stop_at']=='FIRST_APPROVED_MEMSET_RETURN'


def test_resolved_binary_fingerprint_does_not_select_system_python_package_environment(tmp_path):
    fp={'runtime':{'path':'/usr/bin/python3.12'},'libc':{'path':'/prepared/libc'},'gala':{'path':'/prepared/gala'}}
    config=api().build_config(ROOT,tmp_path,fp,'a'*64,{})
    args,_=api().launch_spec(ROOT,config,tmp_path/'config.json')
    assert config['python_executable']==INNER_PYTHON
    assert args[-3]==INNER_PYTHON
    config['python_executable']='/usr/bin/python3.12'
    with pytest.raises(ValueError,match='prepared Python'):
        api().launch_spec(ROOT,config,tmp_path/'config.json')

def test_existing_output_refuses_before_launch(tmp_path,monkeypatch):
    output=tmp_path/'gala-observation.raw.json';output.write_bytes(b'history')
    monkeypatch.setattr(api(),'_run',lambda *args:pytest.fail('duplicate live launch'))
    with pytest.raises(FileExistsError):api().observe_gala({},output,ROOT,gdb_sha256='a'*64,
        source_snapshot={'one.py':'b'*64})
    assert output.read_bytes()==b'history'

def test_gdb_failure_preserves_raw_diagnostic_without_second_launch(tmp_path,monkeypatch):
    mod=api();launched=[]
    monkeypatch.setattr(mod,'_identity',lambda *args:None)
    def run(args,env,timeout,cap):
        import json
        launched.append(args)
        config=__import__('json').loads(Path(env['CM_GALA_OBSERVER_CONFIG']).read_bytes())
        Path(config['result']).write_bytes(adaptive.canonical(dict(diagnostic={
            'stage':'read-full-state','exception_type':'ValueError','exception_message':'x87 missing'})))
        return {'returncode':2,'stop_reason':None,'stdout':'','stderr':'x87 missing'}
    monkeypatch.setattr(mod,'_run',run)
    fp={'runtime':{'path':'/prepared/python'},'libc':{'path':'/prepared/libc'},'gala':{'path':'/prepared/gala'}}
    output=tmp_path/'gala-observation.raw.json'
    result=mod.observe_gala(fp,output,ROOT,gdb_sha256='a'*64,source_snapshot={'one.py':'b'*64})
    assert len(launched)==1
    assert result['diagnostic']['exception_message']=='x87 missing'
    assert output.is_file()


def proc_fixture(tmp_path):
    import hashlib,json
    proc=tmp_path/'proc';proc.mkdir();(proc/'sys/kernel/random').mkdir(parents=True)
    (proc/'sys/kernel/random/boot_id').write_text('11111111-2222-3333-4444-555555555555')
    exe=tmp_path/'python';exe.write_bytes(b'pinned Python')
    for pid,ppid in ((40,30),(30,20)):
        folder=proc/str(pid);folder.mkdir()
        fields=['S',str(ppid)]+['0']*17+['1234']+['0']*4
        (folder/'stat').write_text(str(pid)+' (python) '+' '.join(fields))
        (folder/'cgroup').write_text('0::/system.slice/owned.service\n')
    (proc/'40/exe').symlink_to(exe)
    (proc/'self').mkdir();(proc/'self/cgroup').write_text('0::/system.slice/owned.service\n')
    config=dict(candidate_birth=str(tmp_path/'candidate.json'),birth=str(tmp_path/'owned.json'),
        fingerprint={'runtime':{'sha256':hashlib.sha256(exe.read_bytes()).hexdigest()}})
    Path(config['candidate_birth']).write_bytes(adaptive.canonical(dict(pid=40)))
    return proc,config


@pytest.mark.parametrize('mutation',['foreign-parent','foreign-cgroup','runtime-drift','clean'])
def test_parent_derives_owned_birth_from_proc_not_claimed_gdb_identity(tmp_path,mutation):
    import json
    proc,config=proc_fixture(tmp_path)
    if mutation=='foreign-parent':(proc/'40/stat').write_text('40 (python) S 0 '+'0 '*17+'1234 0')
    if mutation=='foreign-cgroup':(proc/'40/cgroup').write_text('0::/system.slice/foreign.service\n')
    if mutation=='runtime-drift':config['fingerprint']['runtime']['sha256']='f'*64
    if mutation=='clean':
        birth=api().bind_owned_birth(config,20,proc)
        assert birth==dict(pid=40,linux_boot_id='11111111-2222-3333-4444-555555555555',proc_stat_start_time_ticks=1234)
        assert json.loads(Path(config['birth']).read_bytes())==birth
    else:
        with pytest.raises(ValueError):api().bind_owned_birth(config,20,proc)
        assert not Path(config['birth']).exists()


def test_elf_load_bias_uses_virtual_addresses_in_relro_mapping():
    import struct
    raw=bytearray(0x5000);raw[:7]=b'\x7fELF\x02\x01\x01'
    struct.pack_into('<Q',raw,32,64);struct.pack_into('<HH',raw,54,56,2)
    struct.pack_into('<IIQQQQQQ',raw,64,1,5,0,0,0,0x2000,0x2000,4096)
    struct.pack_into('<IIQQQQQQ',raw,120,1,6,0x2000,0x3000,0,0x2000,0x2000,4096)
    maps=[dict(start=0x700000,end=0x702000,offset=0,perms='r-xp'),
        dict(start=0x703000,end=0x704000,offset=0x2000,perms='r--p'),
        dict(start=0x704000,end=0x705000,offset=0x3000,perms='rw-p')]
    assert api().elf_load_bias(bytes(raw),maps)==0x700000
    maps[-1]['start']+=4096;maps[-1]['end']+=4096
    with pytest.raises(ValueError):api().elf_load_bias(bytes(raw),maps)
