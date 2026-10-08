"""Independent profile authority: observations and TEST_ONLY never promote."""
import copy
import importlib
import json
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
LIVE = ROOT / 'verified_driver/v1/artifacts/task8/positive-03/runs/actual'


def api():
    name = 'compute_metabolism.v0.profile_verify'
    assert importlib.util.find_spec(name) is not None, 'independent profile gate missing'
    return importlib.import_module(name)


def observation(assembly='vmovdqu64 %zmm0,(%rdi)'):
    return dict(schema='COMPUTE_METABOLISM_OBSERVATION_V1', mode='OBSERVATION',
        certified_state_progress=False, fingerprint=dict(v1_source_binding='f'*64),
        call_origin=dict(kind='SYNTHETIC_PYTHON_CTYPES', authorized_gala_call=False),
        entry=100, library=dict(sha256='a'*64, build_id='ab'),
        input=dict(destination=4096, length=16, fill=0), observed_result=dict(return_value=4096),
        trace=[dict(seq=0, pc=100, next_pc=106, bytes='6201', assembly=assembly,
            before=dict(registers=dict(rdi=4096, rax=0), vectors=dict(zmm0='00'*64)),
            after=dict(registers=dict(rdi=4096, rax=4096), vectors=dict(zmm0='00'*64)),
            reads=[dict(address=8192, size=8, bytes_hex='00'*8)],
            writes=[dict(address=4096, size=16, before_hex='00'*16, after_hex='00'*16)],
            memory_effects_complete=False, unknown_effects=['outside window unobserved'])],
        coverage='DESTINATION_AND_SENTINEL_WINDOW_ONLY')


def test_unknown_instruction_retains_actual_inputs_outputs_and_concrete_rules():
    result = api().inspect_observation(observation())
    assert result['promotion_allowed'] is False
    assert result['instruction_counts']['total'] == 1
    assert result['instruction_counts']['needs_new_semantics'] == 1
    item = result['unknown_instructions'][0]
    assert item['actual_inputs']['registers']['rdi'] == 4096
    assert item['actual_outputs']['registers']['rax'] == 4096
    assert item['memory_effects']['writes'][0]['size'] == 16
    assert item['required_rule']['registers'] and item['required_rule']['memory']
    assert item['positive_test']['instruction_bytes'] == '6201'
    assert {case['mutation'] for case in item['negative_tests']} >= {
        'changed_output', 'outside_destination_write', 'unmodelled_register_change', 'instruction_bytes'}
    assert result['reads'][0]['address'] == 8192
    assert result['writes'][0]['address'] == 4096
    assert 'registers.rax' in result['changed_registers']


def test_known_mnemonic_with_unsupported_vector_operand_is_unknown():
    result = api().inspect_observation(observation('mov %zmm0,%rax'))
    assert result['unknown_instructions']
    assert result['unknown_instructions'][0]['reason'] == 'UNSUPPORTED_OPERAND_FORM'
    assert result['instruction_counts']['known_mnemonic_unsupported'] == 1


def test_known_mnemonic_does_not_claim_effects_without_native_context():
    raw = observation('mov %rdi,%rax')
    result = api().inspect_observation(raw)
    assert result['instruction_counts']['model_known'] == 1
    assert result['instruction_counts']['independently_checked'] == 0
    assert result['effect_coverage']['complete'] is False
    assert result['effect_coverage']['status'] == 'INCOMPLETE'
    assert result['promotion_allowed'] is False
    assert 'FULL_NATIVE_CONTEXT_AND_EFFECTS' in result['required_proofs']


def test_observer_self_asserted_complete_memory_does_not_grant_authority():
    raw = observation('nop'); raw['trace'][0]['memory_effects_complete'] = True
    result = api().inspect_observation(raw)
    assert result['effect_coverage']['complete'] is False
    assert result['promotion_allowed'] is False


def test_intel_display_uses_independent_pinned_elf_decode_for_known_form():
    raw=observation('vmovd xmm0,esi'); raw['trace'][0].update(pc=1611652,bytes='c5f96ec6')
    raw['library']['sha256']='3a15d66867d83762c7f2f1e37359cb8f6c5743edb369c65285cb0b1c4f7498bf'
    result=api().inspect_observation(raw)
    assert result['instruction_counts']['model_known']==1
    assert result['unknown_instructions']==[]
    assert result['instruction_counts']['independently_checked']==0
    assert result['promotion_allowed'] is False


def test_intel_display_with_changed_bytes_cannot_borrow_pinned_decode():
    raw=observation('vmovd xmm0,esi'); raw['trace'][0].update(pc=1611652,bytes='c5f96ec7')
    raw['library']['sha256']='3a15d66867d83762c7f2f1e37359cb8f6c5743edb369c65285cb0b1c4f7498bf'
    result=api().inspect_observation(raw)
    assert result['unknown_instructions'][0]['reason']=='PINNED_INSTRUCTION_BYTES_MISMATCH'
    assert result['promotion_allowed'] is False


def test_unpinned_intel_operands_are_unproved_rather_than_att_model_known():
    result=api().inspect_observation(observation('mov rax,rdi'))
    assert result['instruction_counts']['model_known']==0
    assert result['unknown_instructions'][0]['reason']=='UNSUPPORTED_OPERAND_FORM'


@pytest.mark.parametrize('assembly',['xchg %rax,%rbx','vmovdqu (%rdi),%xmm0','movapd %xmm0,(%rdi)'])
def test_existing_mnemonic_with_unmodelled_direction_is_a_new_rule_obligation(assembly):
    result=api().inspect_observation(observation(assembly))
    assert result['instruction_counts']['model_known']==0
    assert result['unknown_instructions'][0]['reason']=='UNSUPPORTED_OPERAND_FORM'


@pytest.mark.parametrize('attack', ['certified', 'normal', 'empty', 'seq', 'nan', 'negative_range'])
def test_invalid_observation_is_rejected(attack):
    raw = observation()
    if attack == 'certified': raw['certified_state_progress'] = True
    elif attack == 'normal': raw['mode'] = 'NORMAL'
    elif attack == 'empty': raw['trace'] = []
    elif attack == 'seq': raw['trace'][0]['seq'] = 2
    elif attack == 'nan': raw['input']['length'] = float('nan')
    else: raw['trace'][0]['writes'][0]['address'] = -1
    with pytest.raises(ValueError): api().inspect_observation(raw)


def test_endpoint_only_self_issued_pass_refuses_without_writing(tmp_path):
    directory = tmp_path/'candidate'; directory.mkdir()
    (directory/'candidate-profile.json').write_text(json.dumps(dict(status='VERIFIED', verdict='PASS')))
    (directory/'observation.raw.json').write_text(json.dumps(observation()))
    result = api().verify_promotion(directory)
    assert result['promotion_allowed'] is False and 'verified_manifest' not in result
    assert set(p.name for p in directory.iterdir()) == {'candidate-profile.json', 'observation.raw.json'}


@pytest.fixture(scope='module')
def historical():
    if importlib.util.find_spec('compute_metabolism.v0.profile_verify') is None:
        return None  # Each test reports the absent gate as its intended RED.
    return api().existing_historical_profile(ROOT)


def write_bundle(directory, profile):
    directory.mkdir()
    bundled=ROOT/'compute_metabolism/v0/execution_profiles/proofs/task8-positive-03-edge-1'
    checkpoint=LIVE/'checkpoint-1' if LIVE.exists() else bundled/'checkpoint'
    edge=LIVE/'edge-1' if LIVE.exists() else bundled/'edge'
    predecessor=LIVE/'edge-1.predecessor.json' if LIVE.exists() else bundled/'predecessor.json'
    shutil.copytree(checkpoint, directory/'checkpoint')
    shutil.copytree(edge, directory/'edge')
    shutil.copyfile(predecessor, directory/'predecessor.json')
    candidate = copy.deepcopy(profile); candidate['status'] = 'CANDIDATE'
    candidate['verification'] = dict(authority=None, independent_verification='PENDING')
    (directory/'candidate-profile.json').write_text(json.dumps(candidate))
    proof = dict(schema='COMPUTE_METABOLISM_INDEPENDENT_PROOF_V1',
        anchor_id='task8-positive-03-edge-1', evidence_role='LIVE',
        checkpoint_directory='checkpoint', derived_directory='edge', predecessor='predecessor.json',
        evidence_sha256=profile['verification']['proof_files_sha256'])
    (directory/'proof-bundle.json').write_text(json.dumps(proof))
    return candidate


def test_historical_live_gate_rechecks_exact_approved_domain(historical):
    api()
    assert historical['status'] == 'VERIFIED'
    assert historical['entry_points'] == [1611648]
    assert historical['allowed_path'] == [1611648,1611652,1611656,1611659,1611663,1611872,1611877,1611880,1611904,1611908,1611914]
    assert historical['expected_inputs'] == dict(destination='approved_gala_gradient', lengths=[16], fill_values=[0],
        domain_status='EXACT_AUDITED_CALL_DOMAIN')
    assert historical['allowed_call_origins'] == [dict(sha256='a6ac98736304bb9f6a92e473bba45da10d9b5b99f8019e2ca15eb6a7f86234fc', elf_address=25424)]
    assert historical['verification']['negative_controls']
    assert historical['verification']['raw_effects_rechecked'] is True
    assert historical['verification']['source_count'] == 40
    assert historical['verification']['formal_certification'] is False


def test_promotion_reconstructs_manifest_after_full_checker_and_negative_replay(tmp_path, historical):
    api()
    write_bundle(tmp_path/'candidate', historical)
    result = api().verify_promotion(tmp_path/'candidate')
    assert result['promotion_allowed'] is True, result
    assert result['verified_manifest'] == historical
    assert result['numerical_certification'] is False


@pytest.mark.parametrize('drift', ['entry','path','caller','library_hash','build_id','length','result','coverage','register','rank','source'])
def test_candidate_contract_drift_cannot_borrow_live_proof(tmp_path, historical, drift):
    api()
    directory=tmp_path/'candidate'; candidate=write_bundle(directory,historical)
    if drift=='entry': candidate['entry_points']=[100]
    elif drift=='path': candidate['allowed_path'].append(999)
    elif drift=='caller': candidate['allowed_call_origins'][0]['elf_address']+=1
    elif drift=='library_hash': candidate['libraries']['libc']['sha256']='f'*64
    elif drift=='build_id': candidate['libraries']['libc']['build_id']='ff'
    elif drift=='length': candidate['expected_inputs']['lengths'].append(32)
    elif drift=='result': candidate['expected_result']['return_value']='anything'
    elif drift=='coverage': candidate['memory_contract']['coverage']='ENDPOINT_ONLY'
    elif drift=='register': candidate['allowed_state_changes'].append('rbx')
    elif drift=='rank': candidate['verified_capability_rank']=999
    else: candidate['v1_source_binding']='f'*64
    (directory/'candidate-profile.json').write_text(json.dumps(candidate))
    result=api().verify_promotion(directory)
    assert result['promotion_allowed'] is False and 'verified_manifest' not in result


@pytest.mark.parametrize('attack', ['self_pass','unknown_anchor','test_only','checkpoint','raw','edge','completion','path_escape'])
def test_live_proof_identity_or_scope_substitution_refuses(tmp_path, historical, attack):
    api()
    directory=tmp_path/'candidate'; write_bundle(directory,historical)
    bundle=json.loads((directory/'proof-bundle.json').read_bytes())
    if attack=='self_pass': bundle['verdict']='PASS'
    elif attack=='unknown_anchor': bundle['anchor_id']='self-issued-live'
    elif attack=='test_only': bundle['evidence_role']='TEST_ONLY'
    elif attack=='path_escape': bundle['checkpoint_directory']='../outside'
    else:
        name={'checkpoint':'checkpoint/checkpoint.json','raw':'checkpoint/trace.jsonl',
            'edge':'edge/edge.json','completion':'edge/completion.json'}[attack]
        p=directory/name; p.chmod(0o600); p.write_bytes(p.read_bytes()+b' ')
    (directory/'proof-bundle.json').write_text(json.dumps(bundle))
    assert api().verify_promotion(directory)['promotion_allowed'] is False


def test_test_only_checker_positive_is_not_numerical_authority(tmp_path, monkeypatch):
    api()
    monkeypatch.setenv('RTN_QUOTA_FILE',str(tmp_path/'test-only-quota'))
    monkeypatch.setenv('RTN_QUOTA_BYTES','16777216')
    from tests.live_chain_fixture import checkpoint
    from verified_driver.v1.model import chain_genesis
    from verified_driver.v1.live_chain.producer import build_edge
    from verified_driver.v1.live_chain.checker import check_edge
    pred=chain_genesis(ROOT,3); cp,_,_=checkpoint(tmp_path/'fixture',pred,1)
    out=tmp_path/'derived'; build_edge(cp,pred,out,ROOT)
    assert check_edge(cp,out,pred,ROOT)['verdict']=='CHECKER_PASS'
    directory=tmp_path/'candidate'; directory.mkdir()
    (directory/'candidate-profile.json').write_text(json.dumps(dict(status='CANDIDATE')))
    (directory/'proof-bundle.json').write_text(json.dumps(dict(schema='COMPUTE_METABOLISM_INDEPENDENT_PROOF_V1',
        anchor_id='task8-positive-03-edge-1',evidence_role='TEST_ONLY')))
    assert api().verify_promotion(directory)['promotion_allowed'] is False


def test_registered_authority_label_alone_is_rejected(historical):
    api()
    forged=copy.deepcopy(historical); forged['entry_points']=[100]
    with pytest.raises(ValueError): api().verify_registered_profile(forged,ROOT)


def test_registered_authentic_profile_is_rechecked(historical):
    api()
    assert api().verify_registered_profile(historical,ROOT)==historical


def bundled_proof(root):
    base=root/'compute_metabolism/v0/execution_profiles/proofs/task8-positive-03-edge-1'
    base.mkdir(parents=True)
    bundled=ROOT/'compute_metabolism/v0/execution_profiles/proofs/task8-positive-03-edge-1'
    shutil.copytree(LIVE/'checkpoint-1' if LIVE.exists() else bundled/'checkpoint',base/'checkpoint')
    shutil.copytree(LIVE/'edge-1' if LIVE.exists() else bundled/'edge',base/'edge')
    shutil.copyfile(LIVE/'edge-1.predecessor.json' if LIVE.exists() else bundled/'predecessor.json',base/'predecessor.json')
    return base


def test_bundled_anchor_is_authenticated_when_ignored_original_absent(tmp_path):
    gate=api(); bundled_proof(tmp_path)
    anchor=gate.REVIEWED_LIVE_ANCHORS['task8-positive-03-edge-1']
    document,hashes=gate._authenticate(gate._anchor_paths(tmp_path,anchor),anchor)
    assert document['metadata']['evidence_role']=='LIVE'
    assert hashes['checkpoint.json']=='8c49ea95af86f29bd7d7cf188370ac5ca2fe8ed90058bc7987d5e62c7acd3a93'


def test_bundled_anchor_cannot_hide_corrupt_present_original(tmp_path):
    gate=api(); bundled=bundled_proof(tmp_path)
    original=tmp_path/'verified_driver/v1/artifacts/task8/positive-03/runs/actual'
    original.mkdir(parents=True)
    shutil.copytree(bundled/'checkpoint',original/'checkpoint-1')
    shutil.copytree(bundled/'edge',original/'edge-1')
    shutil.copyfile(bundled/'predecessor.json',original/'edge-1.predecessor.json')
    p=original/'checkpoint-1/checkpoint.json'; p.chmod(0o600); p.write_bytes(p.read_bytes()+b' ')
    anchor=gate.REVIEWED_LIVE_ANCHORS['task8-positive-03-edge-1']
    with pytest.raises(ValueError): gate._authenticate(gate._anchor_paths(tmp_path,anchor),anchor)
