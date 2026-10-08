"""TEST_ONLY immutable hand contexts; no LIVE or Gala execution authority."""
import copy
import importlib
import json
from pathlib import Path

import pytest

from test_compute_metabolism_gala_origin import fixture, LIBC, GALA


def api():
    try:
        return importlib.import_module('compute_metabolism.v0.evex_profile')
    except ModuleNotFoundError:
        pytest.fail('independent EVEX promotion gate missing')


def sample(tmp_path):
    values = fixture(tmp_path)
    values[0]['fingerprint']['runtime'] = dict(path='/prepared/python',
        sha256='e50d468e8b0adfb05733f5b87b3cff34829c4a8c1aea50c865aa8bdfe4bb150f',
        build_id='337d65cf00021797985cc9f77c0cc334a9fbeb38')
    values[2]['runtime'] = copy.deepcopy(values[0]['fingerprint']['runtime'])
    return values


def test_candidate_is_exact_finite_pending_and_keeps_synthetic_ancestor_only_as_sha(tmp_path):
    doc, *_ = sample(tmp_path)
    result = api().build_candidate(doc, 'aa'*32)
    assert result['profile_id'] == 'libc-memset-avx512-evex-16zero-v1'
    assert result['status'] == 'CANDIDATE'
    assert result['required_cpu_features'] == ['avx512f','avx512bw','avx512vl','bmi2']
    assert result['entry_points'] == [0x1996c0]
    assert result['allowed_path'] == [row['elf_pc'] for row in doc['native']['steps']]
    assert result['allowed_call_origins'] == [dict(sha256=doc['fingerprint']['gala']['sha256'],elf_address=0x6350)]
    assert result['expected_inputs']['lengths'] == [16]
    assert result['expected_inputs']['fill_values'] == [0]
    assert result['derived_from'] == {'candidate_sha256':'aa'*32}
    assert result['verification']['authority'] is None
    assert result['verification']['independent_verification'] == 'PENDING'
    assert 'LIVE' not in json.dumps(result['verification'])


@pytest.mark.parametrize('attack',['oldsha','entry','path','caller','length','fill','libc','binding'])
def test_candidate_contract_cannot_expand_domain(tmp_path,attack):
    doc,*_ = sample(tmp_path);old = 'aa'*32
    if attack=='oldsha':old='PASS'
    elif attack=='entry':doc['fingerprint']['libc']['memset_elf_entry']+=1
    elif attack=='path':doc['native']['steps'][1]['instruction_bytes']='62e27d287ac7'
    elif attack=='caller':doc['caller']['elf_pc']+=1
    elif attack=='length':doc['native']['domain']['length']=32
    elif attack=='fill':doc['native']['domain']['fill']=1
    elif attack=='libc':doc['fingerprint']['libc']['sha256']='aa'*32
    elif attack=='binding':doc['source_binding']='aa'*32
    with pytest.raises(ValueError):api().build_candidate(doc,old)


def test_all_eleven_fresh_controls_use_independent_replay_and_preserve_required_names(tmp_path):
    doc,repo,fp,sources,birth = sample(tmp_path)
    receipts = api()._negative_controls(doc,repo,fp,sources,LIBC,GALA,birth,
        same_value_address=doc['native']['steps'][11]['writes'][0]['address'])
    assert [r['mutation'] for r in receipts] == list(api().NEGATIVE_CLASSES)
    assert len(receipts)==11
    assert all(r['verdict']=='REFUSED' and len(r['mutant_sha256'])==64 for r in receipts)
    assert doc['native']['steps'][11]['writes'] and doc['caller']['before']['registers']['rsi']==0


def test_enabled_same_value_writes_retained_and_checked_against_native_footprint(tmp_path):
    doc,*_ = sample(tmp_path)
    samples = [dict(w,before_hex='00',actual_after_hex='00',value_changed=False,
        basis='DERIVED_ENABLED_STORE_WITH_ACTUAL_PRE_POST_BYTES')
        for w in doc['native']['steps'][11]['writes']]
    api()._validate_writes(samples,doc)
    for change in ('omitted','address','changed','before','after'):
        mutated=copy.deepcopy(samples)
        if change=='omitted':mutated.pop()
        elif change=='address':mutated[0]['address']+=16
        elif change=='changed':mutated[0]['value_changed']=True
        elif change=='before':mutated[0]['before_hex']='0000'
        elif change=='after':mutated[0]['actual_after_hex']='01'
        with pytest.raises(ValueError):api()._validate_writes(mutated,doc)


@pytest.mark.parametrize('attack',['missing','TEST_ONLY','self_PASS','escape','alias'])
def test_production_promotion_refuses_unanchored_or_test_only_evidence(tmp_path,attack):
    doc,*_ = sample(tmp_path);directory=tmp_path/'candidate';directory.mkdir()
    candidate=api().build_candidate(doc,'aa'*32)
    (directory/'candidate-profile.json').write_text(json.dumps(candidate))
    if attack!='missing':
        proof=dict(schema='COMPUTE_METABOLISM_GALA_EVEX_PROOF_V1',evidence_role='TEST_ONLY',
            promotion_allowed=True,verdict='PASS',files={})
        if attack=='self_PASS':proof['evidence_role']='LIVE'
        if attack=='escape':proof['files']={'observation':{'path':'../escape','sha256':'aa'*32}}
        path=directory/'proof-bundle.json'
        if attack=='alias':
            other=tmp_path/'proof.json';other.write_text(json.dumps(proof));path.symlink_to(other)
        else:path.write_text(json.dumps(proof))
    report=api().verify_promotion(directory,tmp_path)
    assert report['promotion_allowed'] is False and report['required_proofs']
    assert 'verified_manifest' not in report


def test_registered_label_does_not_grant_authority(tmp_path):
    doc,*_ = sample(tmp_path)
    profile=api().build_candidate(doc,'aa'*32);profile['status']='VERIFIED'
    profile['verification']={'authority':'INDEPENDENT_GALA_EVEX_PROFILE_V1','verdict':'PASS'}
    with pytest.raises(ValueError):api().verify_registered_profile(profile,tmp_path)


@pytest.mark.parametrize('relative',['../outside','/absolute','a//b','a/./b','a\\b','a:b'])
def test_proof_locators_reject_aliasing_and_namespace_escape(tmp_path,relative):
    with pytest.raises(ValueError):api()._read_ref(tmp_path,{'path':relative,'sha256':'aa'*32})


def test_guard_pass_labels_are_insufficient_without_raw_measurement_and_containment():
    with pytest.raises(ValueError):api()._validate_guard(
        {'outcome':'GUARD_COMPLETE','measurement_valid':True,'test_only':False},
        {'measurement_valid':True}, {'before':{}}, {}, 'run-one')


@pytest.mark.parametrize('attack',['digest','hardlink','symlink','size','duplicate','nonfinite'])
def test_proof_file_authentication_and_strict_json(tmp_path,attack):
    import hashlib,os
    path=tmp_path/'one.json';path.write_bytes(b'{"x":1}')
    reference={'path':'one.json','sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    if attack=='digest':reference['sha256']='aa'*32
    elif attack=='hardlink':os.link(path,tmp_path/'other.json')
    elif attack=='symlink':
        original=tmp_path/'original.json';path.rename(original);path.symlink_to(original)
    elif attack=='duplicate':path.write_bytes(b'{"x":1,"x":2}')
    elif attack=='nonfinite':path.write_bytes(b'{"x":NaN}')
    if attack in ('duplicate','nonfinite'):
        with pytest.raises(ValueError):api()._json(path.read_bytes())
    else:
        with pytest.raises(ValueError):api()._read_ref(tmp_path,reference,1 if attack=='size' else 100)


def test_generated_original_skeleton_classes_are_replayed_not_discarded(tmp_path):
    doc,repo,fp,sources,birth=sample(tmp_path)
    results=api()._negative_controls(doc,repo,fp,sources,LIBC,GALA,birth,api().SKELETON_CLASSES)
    assert [r['mutation'] for r in results]==list(api().SKELETON_CLASSES)
    assert all(r['verdict']=='REFUSED' for r in results)


def test_actual_environment_schema_uses_prepared_identity_and_all_cpu_steal_counters(tmp_path,monkeypatch):
    mod=api();identity={'python':'pinned'};prepared={'identity':identity,'metadata':'immutable old document'}
    seen=[]
    def validate(environment,actual_identity,epoch,root):
        assert actual_identity==identity
        seen.append(actual_identity)
    monkeypatch.setattr(mod.source_epoch,'validate_environment_identity',validate)
    frozen=dict(schema='COMPUTE_METABOLISM_ENVIRONMENT_V0',instance_id='123',boot_id='boot',topology={'0':{}},platform='Linux')
    environment=dict(evidence_scope='LIVE',execution_fingerprint={'frozen':True},
        instance_observation=dict(instance_id='123',raw='123\n',observed_utc='2026-10-07T00:00:00Z'),
        boot_id='boot',topology={'0':{}},runtime={'platform':'Linux'},
        thread_environment={'OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1'},
        proc=dict(loadavg='0 0 0 1/1 1',cpu_pressure='some avg10=0',
            stat='cpu 1 2 3 4 5 6 7 8\ncpu0 1 2 3 4 5 6 7 9\n',steal_ticks={'cpu':8,'cpu0':9}))
    assert mod._environment(environment,prepared,{},tmp_path,frozen,{'frozen':True}) is None
    assert seen==[identity]
    environment['proc']['steal_ticks']={'cpu':8}
    with pytest.raises(ValueError):mod._environment(environment,prepared,{},tmp_path,frozen,{'frozen':True})


def test_exact_related_regression_inventory_and_library_paths(tmp_path):
    mod=api();tests=tmp_path/'tests';tests.mkdir()
    for name in ('test_compute_metabolism_x.py','test_v1_evex_x.py','test_regular_nstep_x.py',
        'test_verified_driver_v1_x.py','test_caller_transition_x.py','test_gate2c1_x.py','test_music_unrelated.py'):
        (tests/name).write_text('# test source\n')
    inventory=mod.regression_test_files(tmp_path)
    assert 'tests/test_music_unrelated.py' not in inventory
    assert len(inventory)==6 and inventory==sorted(inventory)


def test_related_regression_keeps_all_original_runtime_gate_and_authority_tests(tmp_path):
    tests=tmp_path/'tests';tests.mkdir()
    required=('test_gate0.py','test_gate0_closure.py','test_gate1.py','test_gate2a.py',
        'test_gate2a_sealed.py','test_gate2b.py','test_gate2b_adapter.py','test_gate2c.py',
        'test_gate2c_sealed.py','test_independence.py','test_provenance.py',
        'test_post_seal_audit.py','test_ported_hard_cases.py')
    for name in (*required,'test_c1b1_slow.py','test_impulse_reference_model.py'):
        (tests/name).write_text('# TEST_ONLY inventory fixture\n')
    assert api().regression_test_files(tmp_path)==sorted('tests/'+name for name in required)


RUNTIME_TEST_DIRS=('runtime_trace/tests','runtime_trace/caller_transition/tests',
    'runtime_trace/numeric_ir/tests','runtime_trace/numeric_ir/v2/tests','runtime_trace/regular_2step/tests')


def test_related_regression_includes_runtime_owned_namespaces_without_artifacts(tmp_path):
    required=[directory+'/test_original.py' for directory in RUNTIME_TEST_DIRS]
    for relative in (*required,'runtime_trace/artifacts/tests/test_unrelated.py',
        'runtime_trace/unreviewed/tests/test_unrelated.py'):
        path=tmp_path/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('# TEST_ONLY\n')
    assert api().regression_test_files(tmp_path)==sorted(required)


def test_test_only_regression_parser_accepts_runtime_inventory_and_refuses_extra_path(tmp_path):
    """Component parsing only; these literals do not authorize LIVE promotion."""
    import hashlib
    mod=api()
    sources=('verified_driver/v1/native_evex_producer.py','verified_driver/v1/native_evex_checker.py',
        'verified_driver/v1/native_evex_collector.py','verified_driver/v1/native_evex_capture.py',
        'verified_driver/v1/native_evex_profile.py','compute_metabolism/v0/gala_origin_check.py',
        'compute_metabolism/v0/gdb_gala_observer.py','compute_metabolism/v0/gala_observer.py',
        'compute_metabolism/v0/system_guard.py','compute_metabolism/v0/evex_profile.py',
        'compute_metabolism/v0/source_epoch.py','compute_metabolism/v0/historical_profile.py')
    def put(relative,raw):
        path=tmp_path/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
        return dict(path=relative,sha256=hashlib.sha256(raw).hexdigest())
    gate={path:put(path,b'# TEST_ONLY source parser fixture\n')['sha256'] for path in sources}
    obligations={name:dict(source_sha256=copy.deepcopy(gate),supporting_file=put('support/'+name+'.txt',
        ('TEST_ONLY '+name+' '+','.join(gate.values())).encode())) for name in mod.REVIEW_OBLIGATIONS}
    review=dict(schema='COMPUTE_METABOLISM_EVEX_SOURCE_REVIEW_V1',evidence_role='SOURCE_REVIEW',
        source_binding='aa'*32,gate_source_snapshot=gate,obligations=obligations,unresolved_findings=[])
    for path in (*sorted(mod.REQUIRED_TEST_FILES),*[d+'/test_original.py' for d in RUNTIME_TEST_DIRS]):
        put(path,b'# TEST_ONLY original suite source\n')
    inventory=mod.regression_test_files(tmp_path)
    regression=dict(schema='COMPUTE_METABOLISM_EVEX_SOURCE_REGRESSION_V1',source_binding='aa'*32,
        gate_source_snapshot=gate,test_files={p:hashlib.sha256((tmp_path/p).read_bytes()).hexdigest() for p in inventory},
        command=['/prepared/python','-B','-m','pytest',*inventory,'-q'],returncode=0,
        output=put('support/regression.txt',b'TEST_ONLY component output: 1 passed\n'))
    assert mod._review_regression(tmp_path,review,regression,{'source_binding':'aa'*32},gate) is None
    regression['test_files']['runtime_trace/unreviewed/tests/test_unrelated.py']='aa'*32
    with pytest.raises(ValueError):mod._review_regression(tmp_path,review,regression,{'source_binding':'aa'*32},gate)



# TEST_ONLY parser replay of the earlier synthetic observation's actual guard
# receipts. Original documents are immutable and their hashes are preserved
# below. This fixture has no actual Gala observation or promotion authority.
BORROWED_GUARD_HASHES = {"guard-cgroup-before.json":"ae91c303341d31aeb3386c3339060074aa9c0d94ba443404dc9bd7dab1c43fa8","guard-cgroup-final.json":"f755f5c7af5de82af8cc0ab919f0f9580b7f2987583247f46ae7a9be03d52758","guard-outer.json":"0bba5f9e7e717b0fbe09b9a8c9db485b0bebf578247ac9fd84b866ddc89d2b91"}
BORROWED_GUARD_COMPONENT = json.loads(r'''{"before":{"after":null,"before":{"cpu_max":{"ancestors":[{"missing_at_root":false,"path":"/sys/fs/cgroup/system.slice/compute-metabolism-52a6940354db45838919ba1b3728ad63.service/cpu.max","raw":null},{"path":"/sys/fs/cgroup/system.slice/cpu.max","period_usec":100000,"quota_usec":null,"raw":"max 100000\n"},{"missing_at_root":true,"path":"/sys/fs/cgroup/cpu.max","raw":null}],"finite_ancestors":[],"period_usec":100000,"quota_usec":null,"raw":"max 100000\n","scan_root":"/sys/fs/cgroup","source":"/sys/fs/cgroup/system.slice/cpu.max","unlimited":true},"cpu_stat":{"nice_usec":0,"system_usec":11918,"usage_usec":226454,"user_usec":214535},"cpus":[0,1],"enumerated_pids":[13600],"epoch":{"boot_id":"e1a13853-84ed-40b9-aec1-fdb49bea7e05","device":27,"inode":27768,"path":"/sys/fs/cgroup/system.slice/compute-metabolism-52a6940354db45838919ba1b3728ad63.service"},"memory":{"ancestors":[{"bytes":4294967296,"path":"/sys/fs/cgroup/system.slice/compute-metabolism-52a6940354db45838919ba1b3728ad63.service/memory.max","raw":"4294967296\n"},{"bytes":null,"path":"/sys/fs/cgroup/system.slice/memory.max","raw":"max\n"},{"missing_at_root":true,"path":"/sys/fs/cgroup/memory.max","raw":null}],"effective_bytes":4294967296,"scan_root":"/sys/fs/cgroup"},"memory_current":15695872,"memory_events":{"high":0,"low":0,"max":0,"oom":0,"oom_group_kill":0,"oom_kill":0},"memory_peak":15974400,"monotonic_seconds":29516.41300115,"pids":[13600],"process_identities":{"13600":{"pid":13600,"start_ticks":"2951618","state":"R"}},"process_observations":{"13600":{"identity":{"pid":13600,"start_ticks":"2951618","state":"R"},"status":"stable"}},"raw":{"cgroup.events":"populated 1\nfrozen 0\n","cgroup.procs":"13600\n","cpu.max":"max 100000\n","cpu.stat":"usage_usec 226454\nuser_usec 214535\nsystem_usec 11918\nnice_usec 0\n","cpuset.cpus.effective":"0-1\n","memory.current":"15695872\n","memory.events":"low 0\nhigh 0\nmax 0\noom 0\noom_kill 0\noom_group_kill 0\n","memory.max":"4294967296\n","memory.peak":"15974400\n","memory.swap.max":"0\n"},"swap":{"ancestors":[{"bytes":0,"path":"/sys/fs/cgroup/system.slice/compute-metabolism-52a6940354db45838919ba1b3728ad63.service/memory.swap.max","raw":"0\n"},{"bytes":null,"path":"/sys/fs/cgroup/system.slice/memory.swap.max","raw":"max\n"},{"missing_at_root":true,"path":"/sys/fs/cgroup/memory.swap.max","raw":null}],"effective_bytes":0,"scan_root":"/sys/fs/cgroup"}},"child_returncode":null,"measurement_valid":false,"outcome":"ENVIRONMENT_INVALID","profile":"2c","run_id":"observation-memset-evex-01","topology_before":{"0":{"core_id":"0","physical_package_id":"0"},"1":{"core_id":"1","physical_package_id":"0"}},"unit":"compute-metabolism-52a6940354db45838919ba1b3728ad63.service","wrapper_identity":{"pid":13600,"start_ticks":"2951618","state":"R"}},"final":{"after":{"cpu_max":{"ancestors":[{"missing_at_root":false,"path":"/sys/fs/cgroup/system.slice/compute-metabolism-52a6940354db45838919ba1b3728ad63.service/cpu.max","raw":null},{"path":"/sys/fs/cgroup/system.slice/cpu.max","period_usec":100000,"quota_usec":null,"raw":"max 100000\n"},{"missing_at_root":true,"path":"/sys/fs/cgroup/cpu.max","raw":null}],"finite_ancestors":[],"period_usec":100000,"quota_usec":null,"raw":"max 100000\n","scan_root":"/sys/fs/cgroup","source":"/sys/fs/cgroup/system.slice/cpu.max","unlimited":true},"cpu_stat":{"nice_usec":0,"system_usec":500567,"usage_usec":7596612,"user_usec":7096044},"cpus":[0,1],"enumerated_pids":[13600],"epoch":{"boot_id":"e1a13853-84ed-40b9-aec1-fdb49bea7e05","device":27,"inode":27768,"path":"/sys/fs/cgroup/system.slice/compute-metabolism-52a6940354db45838919ba1b3728ad63.service"},"memory":{"ancestors":[{"bytes":4294967296,"path":"/sys/fs/cgroup/system.slice/compute-metabolism-52a6940354db45838919ba1b3728ad63.service/memory.max","raw":"4294967296\n"},{"bytes":null,"path":"/sys/fs/cgroup/system.slice/memory.max","raw":"max\n"},{"missing_at_root":true,"path":"/sys/fs/cgroup/memory.max","raw":null}],"effective_bytes":4294967296,"scan_root":"/sys/fs/cgroup"},"memory_current":16711680,"memory_events":{"high":0,"low":0,"max":0,"oom":0,"oom_group_kill":0,"oom_kill":0},"memory_peak":166838272,"monotonic_seconds":29523.593538815,"pids":[13600],"process_identities":{"13600":{"pid":13600,"start_ticks":"2951618","state":"R"}},"process_observations":{"13600":{"identity":{"pid":13600,"start_ticks":"2951618","state":"R"},"status":"stable"}},"raw":{"cgroup.events":"populated 1\nfrozen 0\n","cgroup.procs":"13600\n","cpu.max":"max 100000\n","cpu.stat":"usage_usec 7596612\nuser_usec 7096044\nsystem_usec 500567\nnice_usec 0\n","cpuset.cpus.effective":"0-1\n","memory.current":"16711680\n","memory.events":"low 0\nhigh 0\nmax 0\noom 0\noom_kill 0\noom_group_kill 0\n","memory.max":"4294967296\n","memory.peak":"166838272\n","memory.swap.max":"0\n"},"swap":{"ancestors":[{"bytes":0,"path":"/sys/fs/cgroup/system.slice/compute-metabolism-52a6940354db45838919ba1b3728ad63.service/memory.swap.max","raw":"0\n"},{"bytes":null,"path":"/sys/fs/cgroup/system.slice/memory.swap.max","raw":"max\n"},{"missing_at_root":true,"path":"/sys/fs/cgroup/memory.swap.max","raw":null}],"effective_bytes":0,"scan_root":"/sys/fs/cgroup"}},"before":{"cpu_max":{"ancestors":[{"missing_at_root":false,"path":"/sys/fs/cgroup/system.slice/compute-metabolism-52a6940354db45838919ba1b3728ad63.service/cpu.max","raw":null},{"path":"/sys/fs/cgroup/system.slice/cpu.max","period_usec":100000,"quota_usec":null,"raw":"max 100000\n"},{"missing_at_root":true,"path":"/sys/fs/cgroup/cpu.max","raw":null}],"finite_ancestors":[],"period_usec":100000,"quota_usec":null,"raw":"max 100000\n","scan_root":"/sys/fs/cgroup","source":"/sys/fs/cgroup/system.slice/cpu.max","unlimited":true},"cpu_stat":{"nice_usec":0,"system_usec":11918,"usage_usec":226454,"user_usec":214535},"cpus":[0,1],"enumerated_pids":[13600],"epoch":{"boot_id":"e1a13853-84ed-40b9-aec1-fdb49bea7e05","device":27,"inode":27768,"path":"/sys/fs/cgroup/system.slice/compute-metabolism-52a6940354db45838919ba1b3728ad63.service"},"memory":{"ancestors":[{"bytes":4294967296,"path":"/sys/fs/cgroup/system.slice/compute-metabolism-52a6940354db45838919ba1b3728ad63.service/memory.max","raw":"4294967296\n"},{"bytes":null,"path":"/sys/fs/cgroup/system.slice/memory.max","raw":"max\n"},{"missing_at_root":true,"path":"/sys/fs/cgroup/memory.max","raw":null}],"effective_bytes":4294967296,"scan_root":"/sys/fs/cgroup"},"memory_current":15695872,"memory_events":{"high":0,"low":0,"max":0,"oom":0,"oom_group_kill":0,"oom_kill":0},"memory_peak":15974400,"monotonic_seconds":29516.41300115,"pids":[13600],"process_identities":{"13600":{"pid":13600,"start_ticks":"2951618","state":"R"}},"process_observations":{"13600":{"identity":{"pid":13600,"start_ticks":"2951618","state":"R"},"status":"stable"}},"raw":{"cgroup.events":"populated 1\nfrozen 0\n","cgroup.procs":"13600\n","cpu.max":"max 100000\n","cpu.stat":"usage_usec 226454\nuser_usec 214535\nsystem_usec 11918\nnice_usec 0\n","cpuset.cpus.effective":"0-1\n","memory.current":"15695872\n","memory.events":"low 0\nhigh 0\nmax 0\noom 0\noom_kill 0\noom_group_kill 0\n","memory.max":"4294967296\n","memory.peak":"15974400\n","memory.swap.max":"0\n"},"swap":{"ancestors":[{"bytes":0,"path":"/sys/fs/cgroup/system.slice/compute-metabolism-52a6940354db45838919ba1b3728ad63.service/memory.swap.max","raw":"0\n"},{"bytes":null,"path":"/sys/fs/cgroup/system.slice/memory.swap.max","raw":"max\n"},{"missing_at_root":true,"path":"/sys/fs/cgroup/memory.swap.max","raw":null}],"effective_bytes":0,"scan_root":"/sys/fs/cgroup"}},"child_identity":{"pid":13601,"start_ticks":"2951641","state":"R"},"child_returncode":0,"cleanup_errors":[],"containment":{"reaped_pids":[],"remaining_pids":[],"signals":[]},"delta":{"cpu_seconds":7.370158,"system_usec":488649,"usage_usec":7370158,"user_usec":6881509},"final_errors":[],"interrupted":false,"measurement_valid":true,"outcome":"GUARD_COMPLETE","profile":"2c","run_id":"observation-memset-evex-01","topology_after":{"0":{"core_id":"0","physical_package_id":"0"},"1":{"core_id":"1","physical_package_id":"0"}},"topology_before":{"0":{"core_id":"0","physical_package_id":"0"},"1":{"core_id":"1","physical_package_id":"0"}},"unit":"compute-metabolism-52a6940354db45838919ba1b3728ad63.service","wrapper_identity":{"pid":13600,"start_ticks":"2951618","state":"R"}},"outer":{"after":{"cpu_max":{"ancestors":[{"missing_at_root":false,"path":"/sys/fs/cgroup/system.slice/compute-metabolism-52a6940354db45838919ba1b3728ad63.service/cpu.max","raw":null},{"path":"/sys/fs/cgroup/system.slice/cpu.max","period_usec":100000,"quota_usec":null,"raw":"max 100000\n"},{"missing_at_root":true,"path":"/sys/fs/cgroup/cpu.max","raw":null}],"finite_ancestors":[],"period_usec":100000,"quota_usec":null,"raw":"max 100000\n","scan_root":"/sys/fs/cgroup","source":"/sys/fs/cgroup/system.slice/cpu.max","unlimited":true},"cpu_stat":{"nice_usec":0,"system_usec":500567,"usage_usec":7596612,"user_usec":7096044},"cpus":[0,1],"enumerated_pids":[13600],"epoch":{"boot_id":"e1a13853-84ed-40b9-aec1-fdb49bea7e05","device":27,"inode":27768,"path":"/sys/fs/cgroup/system.slice/compute-metabolism-52a6940354db45838919ba1b3728ad63.service"},"memory":{"ancestors":[{"bytes":4294967296,"path":"/sys/fs/cgroup/system.slice/compute-metabolism-52a6940354db45838919ba1b3728ad63.service/memory.max","raw":"4294967296\n"},{"bytes":null,"path":"/sys/fs/cgroup/system.slice/memory.max","raw":"max\n"},{"missing_at_root":true,"path":"/sys/fs/cgroup/memory.max","raw":null}],"effective_bytes":4294967296,"scan_root":"/sys/fs/cgroup"},"memory_current":16711680,"memory_events":{"high":0,"low":0,"max":0,"oom":0,"oom_group_kill":0,"oom_kill":0},"memory_peak":166838272,"monotonic_seconds":29523.593538815,"pids":[13600],"process_identities":{"13600":{"pid":13600,"start_ticks":"2951618","state":"R"}},"process_observations":{"13600":{"identity":{"pid":13600,"start_ticks":"2951618","state":"R"},"status":"stable"}},"raw":{"cgroup.events":"populated 1\nfrozen 0\n","cgroup.procs":"13600\n","cpu.max":"max 100000\n","cpu.stat":"usage_usec 7596612\nuser_usec 7096044\nsystem_usec 500567\nnice_usec 0\n","cpuset.cpus.effective":"0-1\n","memory.current":"16711680\n","memory.events":"low 0\nhigh 0\nmax 0\noom 0\noom_kill 0\noom_group_kill 0\n","memory.max":"4294967296\n","memory.peak":"166838272\n","memory.swap.max":"0\n"},"swap":{"ancestors":[{"bytes":0,"path":"/sys/fs/cgroup/system.slice/compute-metabolism-52a6940354db45838919ba1b3728ad63.service/memory.swap.max","raw":"0\n"},{"bytes":null,"path":"/sys/fs/cgroup/system.slice/memory.swap.max","raw":"max\n"},{"missing_at_root":true,"path":"/sys/fs/cgroup/memory.swap.max","raw":null}],"effective_bytes":0,"scan_root":"/sys/fs/cgroup"}},"argv":["sudo","-n","systemd-run","--quiet","--wait","--pipe","--collect","--uid=1000","--gid=1003","--unit=compute-metabolism-52a6940354db45838919ba1b3728ad63.service","--property=RootDirectory=/home/zun24/compute-metabolism-v0-prepared-20261006/rootfs","--property=WorkingDirectory=/workspace","--property=MountAPIVFS=yes","--property=AllowedCPUs=0,1","--property=MemoryMax=4294967296","--property=MemorySwapMax=0","--property=CPUAccounting=yes","--property=MemoryAccounting=yes","--property=RuntimeMaxSec=180s","--property=KillMode=control-group","--property=OOMPolicy=kill","--property=Delegate=no","--property=ReadOnlyPaths=/workspace /usr /home/otherside123 /reference","--property=ReadWritePaths=/workspace/compute_metabolism/v0/artifacts","--setenv=PATH=/home/otherside123/venvs/gate2c1-trace/bin:/usr/bin:/bin","--setenv=LC_ALL=C.UTF-8","--setenv=PYTHONDONTWRITEBYTECODE=1","--setenv=HOME=/home/zun24","--setenv=OMP_NUM_THREADS=1","--setenv=OPENBLAS_NUM_THREADS=1","--setenv=RTN_QUOTA_FILE=/workspace/compute_metabolism/v0/artifacts/operational/gcp-v0-20261007-restart1/observations/observation-memset-evex-01/writer_quota.txt","--setenv=RTN_QUOTA_BYTES=671088640","/home/otherside123/venvs/gate2c1-trace/bin/python","-m","compute_metabolism.v0.system_guard","inner","--profile","2c","--unit","compute-metabolism-52a6940354db45838919ba1b3728ad63.service","--run-id","observation-memset-evex-01","--artifact-dir","/workspace/compute_metabolism/v0/artifacts/operational/gcp-v0-20261007-restart1/observations/observation-memset-evex-01","--","/home/otherside123/venvs/gate2c1-trace/bin/python","-B","-m","compute_metabolism.v0.observation_run","--inner-config","/workspace/compute_metabolism/v0/artifacts/operational/gcp-v0-20261007-restart1/observations/config-observation-memset-evex-01.json","--config-sha256","ae301520d0ac2ee1fcbb3bf46ec204538cec3e21027800cfbc0b4807f617f536"],"before":{"cpu_max":{"ancestors":[{"missing_at_root":false,"path":"/sys/fs/cgroup/system.slice/compute-metabolism-52a6940354db45838919ba1b3728ad63.service/cpu.max","raw":null},{"path":"/sys/fs/cgroup/system.slice/cpu.max","period_usec":100000,"quota_usec":null,"raw":"max 100000\n"},{"missing_at_root":true,"path":"/sys/fs/cgroup/cpu.max","raw":null}],"finite_ancestors":[],"period_usec":100000,"quota_usec":null,"raw":"max 100000\n","scan_root":"/sys/fs/cgroup","source":"/sys/fs/cgroup/system.slice/cpu.max","unlimited":true},"cpu_stat":{"nice_usec":0,"system_usec":11918,"usage_usec":226454,"user_usec":214535},"cpus":[0,1],"enumerated_pids":[13600],"epoch":{"boot_id":"e1a13853-84ed-40b9-aec1-fdb49bea7e05","device":27,"inode":27768,"path":"/sys/fs/cgroup/system.slice/compute-metabolism-52a6940354db45838919ba1b3728ad63.service"},"memory":{"ancestors":[{"bytes":4294967296,"path":"/sys/fs/cgroup/system.slice/compute-metabolism-52a6940354db45838919ba1b3728ad63.service/memory.max","raw":"4294967296\n"},{"bytes":null,"path":"/sys/fs/cgroup/system.slice/memory.max","raw":"max\n"},{"missing_at_root":true,"path":"/sys/fs/cgroup/memory.max","raw":null}],"effective_bytes":4294967296,"scan_root":"/sys/fs/cgroup"},"memory_current":15695872,"memory_events":{"high":0,"low":0,"max":0,"oom":0,"oom_group_kill":0,"oom_kill":0},"memory_peak":15974400,"monotonic_seconds":29516.41300115,"pids":[13600],"process_identities":{"13600":{"pid":13600,"start_ticks":"2951618","state":"R"}},"process_observations":{"13600":{"identity":{"pid":13600,"start_ticks":"2951618","state":"R"},"status":"stable"}},"raw":{"cgroup.events":"populated 1\nfrozen 0\n","cgroup.procs":"13600\n","cpu.max":"max 100000\n","cpu.stat":"usage_usec 226454\nuser_usec 214535\nsystem_usec 11918\nnice_usec 0\n","cpuset.cpus.effective":"0-1\n","memory.current":"15695872\n","memory.events":"low 0\nhigh 0\nmax 0\noom 0\noom_kill 0\noom_group_kill 0\n","memory.max":"4294967296\n","memory.peak":"15974400\n","memory.swap.max":"0\n"},"swap":{"ancestors":[{"bytes":0,"path":"/sys/fs/cgroup/system.slice/compute-metabolism-52a6940354db45838919ba1b3728ad63.service/memory.swap.max","raw":"0\n"},{"bytes":null,"path":"/sys/fs/cgroup/system.slice/memory.swap.max","raw":"max\n"},{"missing_at_root":true,"path":"/sys/fs/cgroup/memory.swap.max","raw":null}],"effective_bytes":0,"scan_root":"/sys/fs/cgroup"}},"cleanup_attempts":[],"deadline_seconds":180,"delta":{"cpu_seconds":7.370158,"system_usec":488649,"usage_usec":7370158,"user_usec":6881509},"inner":{"after":{"cpu_max":{"ancestors":[{"missing_at_root":false,"path":"/sys/fs/cgroup/system.slice/compute-metabolism-52a6940354db45838919ba1b3728ad63.service/cpu.max","raw":null},{"path":"/sys/fs/cgroup/system.slice/cpu.max","period_usec":100000,"quota_usec":null,"raw":"max 100000\n"},{"missing_at_root":true,"path":"/sys/fs/cgroup/cpu.max","raw":null}],"finite_ancestors":[],"period_usec":100000,"quota_usec":null,"raw":"max 100000\n","scan_root":"/sys/fs/cgroup","source":"/sys/fs/cgroup/system.slice/cpu.max","unlimited":true},"cpu_stat":{"nice_usec":0,"system_usec":500567,"usage_usec":7596612,"user_usec":7096044},"cpus":[0,1],"enumerated_pids":[13600],"epoch":{"boot_id":"e1a13853-84ed-40b9-aec1-fdb49bea7e05","device":27,"inode":27768,"path":"/sys/fs/cgroup/system.slice/compute-metabolism-52a6940354db45838919ba1b3728ad63.service"},"memory":{"ancestors":[{"bytes":4294967296,"path":"/sys/fs/cgroup/system.slice/compute-metabolism-52a6940354db45838919ba1b3728ad63.service/memory.max","raw":"4294967296\n"},{"bytes":null,"path":"/sys/fs/cgroup/system.slice/memory.max","raw":"max\n"},{"missing_at_root":true,"path":"/sys/fs/cgroup/memory.max","raw":null}],"effective_bytes":4294967296,"scan_root":"/sys/fs/cgroup"},"memory_current":16711680,"memory_events":{"high":0,"low":0,"max":0,"oom":0,"oom_group_kill":0,"oom_kill":0},"memory_peak":166838272,"monotonic_seconds":29523.593538815,"pids":[13600],"process_identities":{"13600":{"pid":13600,"start_ticks":"2951618","state":"R"}},"process_observations":{"13600":{"identity":{"pid":13600,"start_ticks":"2951618","state":"R"},"status":"stable"}},"raw":{"cgroup.events":"populated 1\nfrozen 0\n","cgroup.procs":"13600\n","cpu.max":"max 100000\n","cpu.stat":"usage_usec 7596612\nuser_usec 7096044\nsystem_usec 500567\nnice_usec 0\n","cpuset.cpus.effective":"0-1\n","memory.current":"16711680\n","memory.events":"low 0\nhigh 0\nmax 0\noom 0\noom_kill 0\noom_group_kill 0\n","memory.max":"4294967296\n","memory.peak":"166838272\n","memory.swap.max":"0\n"},"swap":{"ancestors":[{"bytes":0,"path":"/sys/fs/cgroup/system.slice/compute-metabolism-52a6940354db45838919ba1b3728ad63.service/memory.swap.max","raw":"0\n"},{"bytes":null,"path":"/sys/fs/cgroup/system.slice/memory.swap.max","raw":"max\n"},{"missing_at_root":true,"path":"/sys/fs/cgroup/memory.swap.max","raw":null}],"effective_bytes":0,"scan_root":"/sys/fs/cgroup"}},"before":{"cpu_max":{"ancestors":[{"missing_at_root":false,"path":"/sys/fs/cgroup/system.slice/compute-metabolism-52a6940354db45838919ba1b3728ad63.service/cpu.max","raw":null},{"path":"/sys/fs/cgroup/system.slice/cpu.max","period_usec":100000,"quota_usec":null,"raw":"max 100000\n"},{"missing_at_root":true,"path":"/sys/fs/cgroup/cpu.max","raw":null}],"finite_ancestors":[],"period_usec":100000,"quota_usec":null,"raw":"max 100000\n","scan_root":"/sys/fs/cgroup","source":"/sys/fs/cgroup/system.slice/cpu.max","unlimited":true},"cpu_stat":{"nice_usec":0,"system_usec":11918,"usage_usec":226454,"user_usec":214535},"cpus":[0,1],"enumerated_pids":[13600],"epoch":{"boot_id":"e1a13853-84ed-40b9-aec1-fdb49bea7e05","device":27,"inode":27768,"path":"/sys/fs/cgroup/system.slice/compute-metabolism-52a6940354db45838919ba1b3728ad63.service"},"memory":{"ancestors":[{"bytes":4294967296,"path":"/sys/fs/cgroup/system.slice/compute-metabolism-52a6940354db45838919ba1b3728ad63.service/memory.max","raw":"4294967296\n"},{"bytes":null,"path":"/sys/fs/cgroup/system.slice/memory.max","raw":"max\n"},{"missing_at_root":true,"path":"/sys/fs/cgroup/memory.max","raw":null}],"effective_bytes":4294967296,"scan_root":"/sys/fs/cgroup"},"memory_current":15695872,"memory_events":{"high":0,"low":0,"max":0,"oom":0,"oom_group_kill":0,"oom_kill":0},"memory_peak":15974400,"monotonic_seconds":29516.41300115,"pids":[13600],"process_identities":{"13600":{"pid":13600,"start_ticks":"2951618","state":"R"}},"process_observations":{"13600":{"identity":{"pid":13600,"start_ticks":"2951618","state":"R"},"status":"stable"}},"raw":{"cgroup.events":"populated 1\nfrozen 0\n","cgroup.procs":"13600\n","cpu.max":"max 100000\n","cpu.stat":"usage_usec 226454\nuser_usec 214535\nsystem_usec 11918\nnice_usec 0\n","cpuset.cpus.effective":"0-1\n","memory.current":"15695872\n","memory.events":"low 0\nhigh 0\nmax 0\noom 0\noom_kill 0\noom_group_kill 0\n","memory.max":"4294967296\n","memory.peak":"15974400\n","memory.swap.max":"0\n"},"swap":{"ancestors":[{"bytes":0,"path":"/sys/fs/cgroup/system.slice/compute-metabolism-52a6940354db45838919ba1b3728ad63.service/memory.swap.max","raw":"0\n"},{"bytes":null,"path":"/sys/fs/cgroup/system.slice/memory.swap.max","raw":"max\n"},{"missing_at_root":true,"path":"/sys/fs/cgroup/memory.swap.max","raw":null}],"effective_bytes":0,"scan_root":"/sys/fs/cgroup"}},"child_identity":{"pid":13601,"start_ticks":"2951641","state":"R"},"child_returncode":0,"cleanup_errors":[],"containment":{"reaped_pids":[],"remaining_pids":[],"signals":[]},"delta":{"cpu_seconds":7.370158,"system_usec":488649,"usage_usec":7370158,"user_usec":6881509},"final_errors":[],"interrupted":false,"measurement_valid":true,"outcome":"GUARD_COMPLETE","profile":"2c","run_id":"observation-memset-evex-01","topology_after":{"0":{"core_id":"0","physical_package_id":"0"},"1":{"core_id":"1","physical_package_id":"0"}},"topology_before":{"0":{"core_id":"0","physical_package_id":"0"},"1":{"core_id":"1","physical_package_id":"0"}},"unit":"compute-metabolism-52a6940354db45838919ba1b3728ad63.service","wrapper_identity":{"pid":13600,"start_ticks":"2951618","state":"R"}},"launcher_reaped":true,"measurement_valid":true,"outcome":"GUARD_COMPLETE","outer_timeout_proved":false,"profile":"2c","returncode":0,"run_id":"observation-memset-evex-01","terminal":true,"test_only":false,"unit":"compute-metabolism-52a6940354db45838919ba1b3728ad63.service","unit_states":[{"monotonic_seconds":29523.777660891,"returncode":0,"stderr":"","stdout":"ControlGroup=\nLoadState=not-found\nActiveState=inactive\nSubState=dead\n","unit":"compute-metabolism-52a6940354db45838919ba1b3728ad63.service"}],"wall_seconds":7.642243361999135,"writer_bytes":671088640}}''')


def borrowed_guard():
    value=copy.deepcopy(BORROWED_GUARD_COMPONENT)
    config={'campaign_environment':{'topology':value['final']['topology_before']}}
    return value,config


def test_test_only_cpu_accounting_rechecks_guest_bytes_and_requires_fixed_host_locator(tmp_path):
    """Borrowed raw counters exercise mapping only, without LIVE Gala authority."""
    import hashlib
    mod=api();value,_=borrowed_guard();outer=value['outer']
    relative='compute_metabolism/v0/artifacts/operational/campaign-one/observations/run-one/guard-outer.json'
    path=tmp_path/relative;path.parent.mkdir(parents=True);path.write_bytes(mod._canonical(outer))
    reference=dict(path=relative,sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    measured=mod.measured_guard_cost(dict(outer,proof_locator=str(path),proof_sha256=reference['sha256']))
    claimed=copy.deepcopy(measured)
    claimed['cpu_measurement_proof']['locator']=str(mod.system_guard.PREPARED_ROOT/'workspace'/relative)
    assert mod._validate_cpu_accounting(claimed,outer,tmp_path,reference)==claimed
    for mutation in ('guest_alias','other_host','usage','sha','status'):
        wrong=copy.deepcopy(claimed)
        if mutation=='guest_alias':wrong['cpu_measurement_proof']['locator']=str(path)
        elif mutation=='other_host':wrong['cpu_measurement_proof']['locator']='/arbitrary/guard-outer.json'
        elif mutation=='usage':wrong['cpu_measurement_proof']['usage_usec']+=1
        elif mutation=='sha':wrong['cpu_measurement_proof']['sha256']='aa'*32
        else:wrong['cpu_measurement_status']='AVAILABLE_BY_LABEL'
        with pytest.raises(ValueError):mod._validate_cpu_accounting(wrong,outer,tmp_path,reference)


def test_prior_actual_raw_guard_parses_only_as_test_only_component(monkeypatch):
    value,config=borrowed_guard();mod=api()
    monkeypatch.setattr(mod.system_guard,'UNIT_PATTERN',mod.system_guard.UNIT_PATTERN.pattern)
    result=mod._validate_guard(value['outer'],value['final'],value['before'],config,value['outer']['run_id'])
    assert result['usage_usec']>0 and result['cpu_seconds']>0
    assert 'promotion_allowed' not in result


@pytest.mark.parametrize('attack',['raw_cpu','ancestor_quota','leftover_pid','containment','terminal_order','terminal_cgroup'])
def test_real_schema_guard_mutations_refuse_in_test_only_component(attack):
    value,config=borrowed_guard();outer=value['outer'];final=value['final'];before=value['before']
    if attack=='raw_cpu':
        final['after']['cpu_stat']['usage_usec']+=1
    elif attack=='ancestor_quota':
        final['after']['cpu_max']['ancestors'][1]['raw']='50000 100000\n'
    elif attack=='leftover_pid':
        final['after']['pids'].append(123456)
    elif attack=='containment':
        final['containment']['remaining_pids']=[123456]
    elif attack=='terminal_order':
        for state in outer['unit_states']:state['monotonic_seconds']=0
    elif attack=='terminal_cgroup':
        for state in outer['unit_states']:
            state['stdout']='LoadState=loaded\nActiveState=failed\nControlGroup=/system.slice/foreign.service\n'
    outer['inner']=final;outer['before']=final['before'];outer['after']=final['after']
    with pytest.raises(ValueError):api()._validate_guard(outer,final,before,config,outer['run_id'])


def test_exact_original_attempt_and_separate_proof_accounting_namespaces():
    paths=api()._namespaces('old-campaign','gala-observation-01')
    base='compute_metabolism/v0/artifacts/operational/old-campaign/observations/'
    assert paths==dict(attempt=base+'gala-observation-01/',proof=base+'proofs/gala-observation-01/',
        upper_before=base+'upper-before-gala-observation-01.raw.json')
    for campaign,run in (('../old','one'),('old','one/next'),('old',True)):
        with pytest.raises(ValueError):api()._namespaces(campaign,run)


def test_approved_runtime_binary_links_resolve_but_evidence_aliases_still_refuse(tmp_path):
    from verified_driver.v1.native_evex_checker import _elf
    import hashlib
    path=tmp_path/'approved-libc';path.symlink_to(LIBC)
    expected=dict(sha256=hashlib.sha256(LIBC.read_bytes()).hexdigest(),build_id=_elf(LIBC.read_bytes())[1])
    actual=api()._library_identity(path,expected)
    assert actual['resolved_path']==str(LIBC.resolve()) and actual['sha256']==expected['sha256']
    with pytest.raises(ValueError):api()._read_ref(tmp_path,dict(path=path.name,sha256=expected['sha256']))
    expected['build_id']='ff'*20
    with pytest.raises(ValueError):api()._library_identity(path,expected)


def test_omission_mutant_removes_authenticated_unchanged_lane_not_last_lane(tmp_path,monkeypatch):
    mod=api();doc,repo,fp,sources,birth=sample(tmp_path)
    writes=doc['native']['steps'][11]['writes']
    samples=[dict(w,before_hex='00' if i==0 else '01',actual_after_hex='00',value_changed=i!=0,
        basis='DERIVED_ENABLED_STORE_WITH_ACTUAL_PRE_POST_BYTES') for i,w in enumerate(writes)]
    address=mod._validate_writes(samples,doc)
    assert address==writes[0]['address']
    real=mod.verify_observation;seen=[]
    def independent(mutant,*args):
        seen.append(mutant)
        return real(mutant,*args)
    monkeypatch.setattr(mod,'verify_observation',independent)
    results=mod._negative_controls(doc,repo,fp,sources,LIBC,GALA,birth,
        classes=('samevaluewriteomission',),same_value_address=address)
    assert results[0]['verdict']=='REFUSED'
    actual=seen[0]['native']['steps'][11]['writes']
    assert writes[0] not in actual and writes[-1] in actual


def test_actual_guarded_gala_job_argv_is_bound_to_sealed_config_not_labels():
    from pathlib import PurePosixPath
    mod=api();campaign='old-campaign';run='actual-gala-one';unit='compute-metabolism-actual-gala-one.service'
    paths=mod._namespaces(campaign,run)
    reference=dict(path='compute_metabolism/v0/artifacts/operational/'+campaign+'/observations/config-'+run+'.json',sha256='aa'*32)
    inner=[mod.system_guard.INNER_PYTHON,'-B','-m','compute_metabolism.v0.gala_observation_run',
        '--inner-config','/workspace/'+reference['path'],'--config-sha256',reference['sha256']]
    argv=mod.system_guard.build_systemd_run_argv(mod.get_profile('2c'),unit_name=unit,
        artifact_dir=PurePosixPath('/workspace/'+paths['attempt'].rstrip('/')),command=inner,
        root_directory=mod.system_guard.PREPARED_ROOT,limits=mod.CampaignLimits())
    outer={'argv':argv,'unit':unit}
    mod._validate_guard_launch(outer,reference,paths['attempt'])
    changed=copy.deepcopy(outer);changed['argv'][-1]='["/bin/true"]'
    with pytest.raises(ValueError):mod._validate_guard_launch(changed,reference,paths['attempt'])
