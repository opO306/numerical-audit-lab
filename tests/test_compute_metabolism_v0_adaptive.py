"""Adaptive layer contracts; TEST_ONLY fixtures grant no production authority."""
import copy, hashlib, importlib, json
from pathlib import Path
import pytest
from tests.test_compute_metabolism_v0_campaign import api, classification_fixture


def adaptive():
    name='compute_metabolism.v0.adaptive'
    assert importlib.util.find_spec(name) is not None, 'adaptive registry/detection/selection API missing'
    return importlib.import_module(name)


def fingerprint():
    return dict(schema='COMPUTE_METABOLISM_FINGERPRINT_V1',cpu_features=['avx2','erms','avx512vl','avx512bw'],
        cpu_vendor='TEST_ONLY',cpu_model='TEST_ONLY cpu',platform='TEST_ONLY Linux',
        libc=dict(sha256='a'*64,build_id='ab'*20,memset_elf_entry=100),
        gala=dict(sha256='b'*64,build_id='bc'*20),runtime=dict(sha256='c'*64,build_id='cd'*20),v1_source_binding='d'*64)


def profile(pid='base', entry=100, rank=10, status='VERIFIED'):
    return dict(schema='COMPUTE_METABOLISM_EXECUTION_PROFILE_V1',profile_id=pid,status=status,
        required_cpu_features=['avx2','erms'],environment=dict(cpu_arch='x86_64'),
        libraries=dict(libc=dict(sha256='a'*64,build_id='ab'*20),gala=dict(sha256='b'*64,build_id='bc'*20),runtime=dict(sha256='c'*64,build_id='cd'*20)),
        v1_source_binding='d'*64,allowed_call_origins=[dict(sha256='b'*64,elf_address=20)],
        entry_points=[entry],allowed_path=[entry,entry+1],expected_inputs=dict(lengths=[16],fill_values=[0]),
        memory_contract=dict(reads=['return_address'],writes=['destination[0:length]']),
        expected_result=dict(return_value='destination',bytes='fill_byte'),
        allowed_state_changes=['caller_saved_registers','destination'],forbidden_state_changes=['outside_destination','callee_saved_registers'],
        verified_capability_rank=rank,derived_from=None,verification=dict(authority='TEST_ONLY',tests=['positive','negative'],evidence_sha256=['e'*64]))


def observation():
    return dict(schema='COMPUTE_METABOLISM_OBSERVATION_V1',mode='OBSERVATION',certified_state_progress=False,
        fingerprint=fingerprint(),call_origin=dict(sha256='b'*64,elf_address=20),entry=100,
        library=dict(sha256='a'*64,build_id='ab'*20),input=dict(destination=4096,length=16,fill=0),
        before_memory='11'*16,after_memory='00'*16,trace=[dict(seq=0,pc=100,bytes='c3',assembly='ret',
            before=dict(rax=0,rsp=200),after=dict(rax=4096,rsp=208),reads=[],writes=[],memory_effects_complete=False)],
        observed_result=dict(return_value=4096),coverage='OBSERVED_SAMPLE_ONLY')


def test_verified_selector_prefers_best_compatible_and_excludes_candidates():
    a=adaptive(); fp=fingerprint(); low=profile(); high=profile('better',rank=30); unknown=profile('unknown',rank=100,status='CANDIDATE')
    assert a.select_profile([unknown,low,high],fp)['profile_id']=='better'
    assert a.select_profile([unknown],fp) is None


@pytest.mark.parametrize('drift',['feature','libc_hash','build_id','entry','gala','runtime','binding'])
def test_selector_refuses_incompatible_environment(drift):
    a=adaptive(); fp=fingerprint()
    if drift=='feature':fp['cpu_features']=[]
    elif drift=='libc_hash':fp['libc']['sha256']='f'*64
    elif drift=='build_id':fp['libc']['build_id']='ff'*20
    elif drift=='entry':fp['libc']['memset_elf_entry']=999
    elif drift in ('gala','runtime'):fp[drift]['sha256']='f'*64
    else:fp['v1_source_binding']='f'*64
    assert a.select_profile([profile()],fp) is None


def test_missing_profile_returns_observation_without_certified_authority():
    a=adaptive(); decision=a.plan_execution([],fingerprint())
    assert decision['mode']=='OBSERVATION' and decision['certified_state_progress'] is False


@pytest.mark.parametrize('drift',['profile','manifest','platform','cpu','libc','source'])
def test_campaign_profile_binding_is_fixed(drift):
    a=adaptive(); fp=fingerprint(); p=profile(); bound=a.bind_campaign(p,fp)
    a.validate_campaign_binding(bound,fp,[p])
    changed=copy.deepcopy(fp); manifest=copy.deepcopy(p)
    if drift=='profile':bound['profile_id']='foreign'
    elif drift=='manifest':manifest['allowed_path'].append(300)
    elif drift=='platform':changed['platform']='changed'
    elif drift=='cpu':changed['cpu_model']='changed'
    elif drift=='libc':changed['libc']['sha256']='f'*64
    else:changed['v1_source_binding']='f'*64
    with pytest.raises(ValueError):a.validate_campaign_binding(bound,changed,[manifest])


def test_candidate_generator_preserves_unknowns_raw_evidence_and_test_skeletons(tmp_path):
    a=adaptive(); o=observation(); o['trace'][0]['assembly']='TEST_ONLY_unknown %r1'; nearest=profile()
    got=a.generate_candidate(o,nearest,tmp_path/'candidate')
    for name in ('candidate-profile.json','difference-report.json','proof-obligations.json','generated-negative-tests.py','generated-positive-fixture.json','observation.raw.json'):
        assert (tmp_path/'candidate'/name).is_file()
    assert got['status']=='CANDIDATE' and got['derived_from']['profile_id']=='base'
    obligations=json.loads((tmp_path/'candidate/proof-obligations.json').read_bytes())
    assert obligations['promotion_allowed'] is False and obligations['unknown_instructions']
    assert json.loads((tmp_path/'candidate/observation.raw.json').read_bytes())==o
    compile((tmp_path/'candidate/generated-negative-tests.py').read_text(),'<generated>','exec')
    with pytest.raises(FileExistsError):a.generate_candidate(o,nearest,tmp_path/'candidate')


def test_observation_cannot_publish_a_certified_state(tmp_path):
    a=adaptive();o=observation();o['certified_state_progress']=True
    with pytest.raises(ValueError):a.generate_candidate(o,profile(),tmp_path/'bad')
    assert not (tmp_path/'bad').exists()


def test_forged_pass_or_endpoint_match_cannot_promote_candidate(tmp_path):
    a=adaptive();got=a.generate_candidate(observation(),profile(),tmp_path/'candidate')
    got['status']='VERIFIED'; got['self_reported_verdict']='PASS'
    with pytest.raises(ValueError):a.promote_candidate(tmp_path/'candidate',tmp_path/'registry')
    assert not (tmp_path/'registry').exists()


def test_elf_build_id_is_observed_from_binary_not_user_label():
    a=adaptive();binary=Path(__file__).parents[1]/'runtime_trace/frozen_binaries/libc.so.6'
    assert hashlib.sha256(binary.read_bytes()).hexdigest()=='3a15d66867d83762c7f2f1e37359cb8f6c5743edb369c65285cb0b1c4f7498bf'
    assert a.elf_build_id(binary.read_bytes())
    with pytest.raises(ValueError):a.elf_build_id(b'not ELF')


@pytest.mark.parametrize('outcome',['ENVIRONMENT_INVALID','REFUSED_VERIFICATION','UNRESOLVED_FAILURE'])
def test_failed_attempt_retains_valid_guard_cpu_measurement(api,tmp_path,outcome):
    report,receipt=classification_fixture(tmp_path,outcome,False)
    result=api.classify_attempt(report,receipt,10)
    assert result['cpu_seconds']==pytest.approx((receipt['after']['cpu_stat']['usage_usec']-receipt['before']['cpu_stat']['usage_usec'])/1e6)
    assert result['cpu_measurement_status']=='AVAILABLE'
    assert result['wrapper_outcome']!='ACCEPT'


def test_measurement_cpu_does_not_accept_invalid_guard_proof(api,tmp_path):
    report,receipt=classification_fixture(tmp_path,'ENVIRONMENT_INVALID',False);receipt['proof_sha256']='0'*64
    result=api.classify_attempt(report,receipt,10)
    assert result.get('cpu_seconds') is None and result['wrapper_outcome']!='ACCEPT'


def test_campaign_analysis_share_prepared_python_helper_contract(api,tmp_path):
    assert hasattr(api,'prepared_helper_argv'),'shared direct prepared Python helper contract missing'
    from compute_metabolism.v0 import system_guard,analyze
    argv=api.prepared_helper_argv(system_guard.PREPARED_ROOT,'classification')
    assert argv[:5]==['sudo','-n','chroot',str(system_guard.PREPARED_ROOT),system_guard.INNER_PYTHON]
    assert '/usr/bin/env' not in argv and argv[5:7]==['-B','-c']
    assert 'os.chdir' in argv[-1] and 'sys.path' in argv[-1]
    assert hasattr(analyze,'prepared_helper_argv') and analyze.prepared_helper_argv is api.prepared_helper_argv


def test_unknown_helper_operation_never_runs_arbitrary_code(api):
    assert hasattr(api,'prepared_helper_argv'),'shared helper missing'
    from compute_metabolism.v0 import system_guard
    with pytest.raises(ValueError):api.prepared_helper_argv(system_guard.PREPARED_ROOT,'arbitrary import')

def test_new_numerical_runner_refuses_unbound_adaptive_identity_before_store():
    from compute_metabolism.v0 import run_v1
    assert hasattr(run_v1,'_validate_execution_profile')
    with pytest.raises(run_v1.AdmissionFailure,match='execution profile'):
        run_v1._validate_execution_profile({}, {}, Path(__file__).parents[1])

def test_library_build_id_absence_is_not_compatible():
    a=adaptive();fp=fingerprint();del fp['gala']['build_id']
    assert a.select_profile([profile()],fp) is None

@pytest.mark.parametrize('drift',['path','caller','length','fill'])
def test_profile_trace_cannot_expand_verified_native_domain(drift):
    a=adaptive();p=profile();rows=[dict(module_sha256='b'*64,elf_address=20),
        dict(module_sha256='a'*64,elf_address=100,pre=dict(gpr=dict(rdx='0x10',rsi='0x0')))]
    assert hasattr(a,'validate_native_domain')
    a.validate_native_domain(p,rows)
    if drift=='path':rows[1]['elf_address']=777
    elif drift=='caller':rows[0]['elf_address']=19
    elif drift=='length':rows[1]['pre']['gpr']['rdx']='0x20'
    else:rows[1]['pre']['gpr']['rsi']='0x1'
    with pytest.raises(ValueError):a.validate_native_domain(p,rows)

def test_explicit_independent_promotion_preserves_registry_history_and_refuses_duplicate(tmp_path):
    a=adaptive()
    from compute_metabolism.v0.profile_verify import existing_historical_profile
    from tests.test_compute_metabolism_v0_profile_verify import write_bundle
    p=existing_historical_profile(Path(__file__).parents[1])
    candidate=tmp_path/'candidate';write_bundle(candidate,p)
    registry=tmp_path/'registry';registry.mkdir()
    original=a.canonical(dict(schema='COMPUTE_METABOLISM_PROFILE_REGISTRY_V1',profiles=[]))
    (registry/'registry.json').write_bytes(original)
    promoted=a.promote_candidate(candidate,registry)
    assert promoted['status']=='VERIFIED' and a.load_registry(registry)==[promoted]
    assert (registry/'history'/(hashlib.sha256(original).hexdigest()+'.raw')).read_bytes()==original
    index=(registry/'registry.json').read_bytes()
    with pytest.raises(ValueError):a.promote_candidate(candidate,registry)
    assert (registry/'registry.json').read_bytes()==index

def test_failed_cpu_cost_legacy_classification_is_not_rewritten(api,tmp_path):
    report,receipt=classification_fixture(tmp_path,'ENVIRONMENT_INVALID',False)
    original=api.classify_attempt(report,receipt,1,preserve_legacy_cpu=True)
    assert original.get('cpu_seconds') is None and 'cpu_accounting_version' not in original
    new=api.classify_attempt(report,receipt,1)
    assert new['cpu_seconds']==5 and new['wrapper_outcome']==original['wrapper_outcome']

@pytest.mark.parametrize('mutation',['result','unmodelled_instruction','out_of_range_write'])
def test_generated_negative_cases_execute_and_preserve_refusal(tmp_path,mutation):
    a=adaptive();directory=tmp_path/'candidate'
    a.generate_candidate(observation(),profile(),directory)
    source=directory/'generated-negative-tests.py'
    namespace={'__file__':str(source)}
    exec(compile(source.read_text(),str(source),'exec'),namespace)
    namespace['test_generated_observation_refuses_promotion'](mutation)
