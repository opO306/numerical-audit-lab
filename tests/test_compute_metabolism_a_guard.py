import inspect
import pytest
from compute_metabolism.v0 import system_guard as g, cgroup_noescape as a
from compute_metabolism.v0.profiles import get_profile

def test_sampler_is_explicit():
    assert 'sampler' in inspect.signature(g.read_cgroup_snapshot).parameters

def test_monitor_configure_never_mutates_guard():
    class Guard: pass
    guard=Guard(); original=lambda *args: None; guard._sample_processes=original
    assert not hasattr(a, 'configure') or 'g._sample_processes=' not in inspect.getsource(a.configure).replace(' ', '')

def test_systemd_security_is_formal():
    argv=g.build_systemd_run_argv(get_profile('2c'),unit_name='compute-metabolism-test.service',artifact_dir=g.ARTIFACT_ROOT/'test',command=['/bin/true'])
    for prop in ('NoNewPrivileges=yes','CapabilityBoundingSet=','AmbientCapabilities=','ProtectControlGroups=yes','RestrictNamespaces=yes','RestrictSUIDSGID=yes'):
        assert '--property='+prop in argv

def test_authority_required_before_launch(tmp_path, monkeypatch):
    monkeypatch.setattr(g.subprocess,'Popen',lambda *a,**k: pytest.fail('unauthorized child launch'))
    with pytest.raises(ValueError,match='A authority'):
        g.run_system_guard(get_profile('2c'),run_id='test',artifact_dir=tmp_path/'test',command=['true'],topology={})

def test_unsupported_a_refused(tmp_path):
    with pytest.raises(ValueError,match='2c'):
        g.run_system_guard(get_profile('1c'),run_id='test',artifact_dir=tmp_path/'test',command=['true'],topology={},require_a=True,a_authority={})


def authority():
    from compute_metabolism.v0.cgroup_noescape_policy import TRUST_SCOPE
    return dict(scope='TEST_ONLY',authority_id='TEST_ONLY-unit',trust_approval=dict(approved_by='test human',scope='TEST_ONLY',noninterference_scope=TRUST_SCOPE,kernel_correct=True,privileged_manager_no_migration_reconfiguration_or_proxy=True),source_manifest={n:'0'*64 for n in ('compute_metabolism/v0/system_guard.py','compute_metabolism/v0/cgroup_noescape.py','compute_metabolism/v0/cgroup_noescape_policy.py','compute_metabolism/v0/cgroup_noescape_check.py')})

@pytest.mark.parametrize('mutation',[lambda x:x.pop('trust_approval'),lambda x:x['trust_approval'].update(kernel_correct=False),lambda x:x['trust_approval'].update(privileged_manager_no_migration_reconfiguration_or_proxy=False),lambda x:x['trust_approval'].update(noninterference_scope='all future runs'),lambda x:x.update(source_manifest={}),lambda x:x.update(scope='arbitrary')])
def test_missing_or_weakened_authority_refused(mutation):
    from compute_metabolism.v0.cgroup_noescape_policy import validate_authority
    value=authority();mutation(value)
    with pytest.raises(ValueError):validate_authority(get_profile('2c'),True,value)

def test_testonly_authority_cannot_authorize_live(tmp_path):
    with pytest.raises(ValueError,match='LIVE'):
        g.run_system_guard(get_profile('2c'),run_id='test',artifact_dir=tmp_path/'test',command=['true'],topology={},a_authority=authority())

def test_live_authority_cannot_authorize_probe(tmp_path):
    value=authority();value['scope']='LIVE';value['trust_approval']['scope']='LIVE'
    with pytest.raises(ValueError,match='TEST_ONLY'):
        g.run_system_guard_test_only_probe(get_profile('2c'),test_only_wall_seconds=5,run_id='test',artifact_dir=tmp_path/'test',command=['true'],topology={},a_authority=value)

@pytest.mark.parametrize('failure',[False,True])
def test_configure_scoped_monitor_does_not_leak(monkeypatch,tmp_path,failure):
    import types
    policy=dict(security_record_path=str(tmp_path/'record'))
    policy_path=tmp_path/'record';policy_path.write_text('{}')
    monkeypatch.setattr(a,'read_record',lambda _: {})
    original=lambda *args: None
    fake=types.SimpleNamespace(_sample_processes=original)
    monitor=a.configure(fake,tmp_path,policy)
    if failure:
        with pytest.raises(RuntimeError):
            raise RuntimeError('deliberate run exception')
    assert fake._sample_processes is original
    another=a.configure(fake,tmp_path,policy)
    assert another is not monitor and another.events==[] and another.snapshots==[]
    assert fake._sample_processes is original


def test_2c_a_cannot_be_disabled(tmp_path):
    with pytest.raises(ValueError,match='bypassed'):
        g.run_system_guard(get_profile('2c'),run_id='test',artifact_dir=tmp_path/'test',command=['true'],topology={},require_a=False)


@pytest.mark.parametrize('groups',['1003','1003 9999'])
def test_root_manager_preparation_is_retained_but_not_admitted(tmp_path,monkeypatch,groups):
    import json, types, time
    from compute_metabolism.v0 import cgroup_noescape_policy as policy
    if g.os.geteuid()!=0: pytest.skip('root ownership contract requires root unit harness')
    monkeypatch.setattr(policy,'verify_sources',lambda *args:None)
    monkeypatch.setattr(policy.pwd,'getpwuid',lambda _:types.SimpleNamespace(pw_name='approved',pw_gid=1000))
    monkeypatch.setattr(policy.os,'getgrouplist',lambda *args:[1003])
    value=authority();value['evidence_root']=str(tmp_path);artifact=tmp_path/'artifact';artifact.mkdir()
    configuration=dict(run_id='run',unit='compute-metabolism-test.service',profile='2c',command=['true'],root_directory=str(tmp_path),deadline_seconds=5,topology={})
    manager=policy.Manager(authority=value,root=tmp_path,artifact_dir=artifact,configuration=configuration,identity=g.SYSTEM_UNIT_IDENTITY)
    call=[0]
    def actual():
        call[0]+=1
        if call[0]==2:
            (artifact/'a-wrapper-ready.json').write_text(json.dumps(dict(unit=configuration['unit'],run_id='run',pid=123,start_ticks='99')))
        if call[0]==3:
            (artifact/'a-completion-ready.json').write_text(json.dumps(dict(unit=configuration['unit'],run_id='run',pid=123,after_monotonic=0)))
        return dict(monotonic_ns=time.monotonic_ns(),raw='Id=compute-metabolism-test.service\n',properties=dict(Id=configuration['unit'],ExecMainPID='123',MainPID='123',ControlGroup='/system.slice/'+configuration['unit']),proc_status='Uid: 1000 1000 1000 1000\nGid: 1003 1003 1003 1003\nGroups: '+groups+'\n',proc_stat='123 (wrapper) R 1 '+' '.join(['0']*17)+' 99',namespaces={'cgroup':'cgroup:[2]'})
    monkeypatch.setattr(manager,'read_actual',actual)
    manager.run();evidence=manager.finish()
    assert len(evidence['preparation_rows'])==1
    if groups=='1003':
        assert not evidence['errors'] and len(evidence['security_rows'])>=3
        assert (manager.dir/'a-policy.json').exists() and (manager.dir/'security-end.json').exists()
        assert evidence['policy']['binding']['credential_baseline']['supplementary_groups']==[1003]
    else:
        assert evidence['errors'] and not (manager.dir/'a-policy.json').exists()
        assert evidence['security_rows']==[]


def test_a_roles_materialize_exact_root_originals(tmp_path):
    import json, stat, types, hashlib
    if g.os.geteuid()!=0: pytest.skip('root ownership harness')
    root=tmp_path/'root';root.mkdir();artifact=tmp_path/'artifact';artifact.mkdir()
    policy_raw=b'{"policy":"original bytes and spaces"}\n'
    launch_raw=b'{ "launch": "exact original" }\n'
    (root/'a-policy.json').write_bytes(policy_raw);(root/'launch-manifest.json').write_bytes(launch_raw)
    for file in root.iterdir():file.chmod(0o444)
    (artifact/'a_security_proof.json').write_bytes(b'{"proof":true}\n')
    (artifact/'guard-cgroup-running.jsonl').write_bytes(b'{"running":true}\n')
    manager=types.SimpleNamespace(dir=root,rows=[{'raw':'actual'}])
    verdict={'status':'A_INDEPENDENT_CHECK_PASS','proof':'actual','proof_sha256':hashlib.sha256((artifact/'a_security_proof.json').read_bytes()).hexdigest(),'running_sha256':hashlib.sha256((artifact/'guard-cgroup-running.jsonl').read_bytes()).hexdigest()}
    refs=g._materialize_a_artifacts(artifact,manager,verdict)
    assert set(refs)=={'a_policy','a_proof','a_independent_check','guard_running','a_launch_manifest','a_manager_security'}
    assert (artifact/'a-policy.json').read_bytes()==policy_raw
    assert (artifact/'a-launch-manifest.json').read_bytes()==launch_raw
    assert json.loads((artifact/'a-manager-security.json').read_bytes())==manager.rows
    assert json.loads((artifact/'a-independent-check.json').read_bytes())==verdict
    for role in ('a_policy','a_launch_manifest','a_manager_security','a_independent_check'):
        file=artifact/refs[role]['path'];info=file.stat()
        assert info.st_uid==info.st_gid==0 and stat.S_IMODE(info.st_mode)==0o444
    for role,locator in refs.items():
        raw=(artifact/locator['path']).read_bytes()
        assert locator['sha256']==hashlib.sha256(raw).hexdigest() and locator['bytes']==len(raw)


def test_a_roles_missing_original_refused(tmp_path):
    import types
    artifact=tmp_path/'artifact';artifact.mkdir()
    with pytest.raises((OSError,ValueError)):
        g._materialize_a_artifacts(artifact,types.SimpleNamespace(dir=tmp_path,rows=[]),{'status':'A_INDEPENDENT_CHECK_PASS'})


@pytest.mark.parametrize('checker_result',[None,{'status':'REFUSED','error':'deliberate missing evidence'}])
def test_outer_refuses_missing_independent_checker_even_child_zero(tmp_path,monkeypatch,checker_result):
    import types
    from compute_metabolism.v0 import cgroup_noescape_check
    monkeypatch.setattr(cgroup_noescape_check,'check_guard',lambda *args:checker_result)
    result=dict(outcome='GUARD_COMPLETE',measurement_valid=True,returncode=0,inner={'child_returncode':0})
    g._finalize_a_guard(tmp_path,types.SimpleNamespace(policy={}),result)
    assert result['outcome']=='ENVIRONMENT_INVALID' and result['measurement_valid'] is False
    assert 'a_evidence_error' in result and 'a_artifacts' not in result


def test_outer_refuses_missing_root_role_even_independent_pass(tmp_path,monkeypatch):
    import types
    from compute_metabolism.v0 import cgroup_noescape_check
    monkeypatch.setattr(cgroup_noescape_check,'check_guard',lambda *args:{'status':'A_INDEPENDENT_CHECK_PASS'})
    result=dict(outcome='GUARD_COMPLETE',measurement_valid=True,returncode=0,inner={'child_returncode':0})
    g._finalize_a_guard(tmp_path,types.SimpleNamespace(policy={},dir=tmp_path,rows=[]),result)
    assert result['outcome']=='ENVIRONMENT_INVALID' and result['measurement_valid'] is False
    assert 'a_evidence_error' in result and 'a_artifacts' not in result
