import copy,hashlib,json
from pathlib import Path
import test_compute_metabolism_noescape as _legacy
from compute_metabolism.v0 import cgroup_noescape_check as checker

def test_formal_api_missing_proof_fails_closed(tmp_path):
    assert checker.check_guard(tmp_path,{}, {}, {})['status']=='REFUSED'

def test_formal_rejects_legacy_policy_even_with_pass(tmp_path):
    proof,policy,inner,outer=_legacy.OuterClosureTests().full()
    (tmp_path/'a_security_proof.json').write_text(json.dumps(proof))
    assert checker.check_guard(tmp_path,policy,inner,outer)['status']=='REFUSED'


def formal_fixture(tmp_path):
    q,p,g,o=_legacy.OuterClosureTests().full()
    for row in q['snapshots']:row['evidence']['namespaces'].update(mnt='mnt:[3]',pid='pid:[4]')
    config=dict(run_id=g['run_id'],unit=g['unit'],profile='2c',command=['test'],root_directory='/test',deadline_seconds=3,topology={})
    canonical=checker._canonical
    manifest={'compute_metabolism/v0/cgroup_noescape_check.py':'1'*64}
    binding=dict(run_id=g['run_id'],unit=g['unit'],profile='2c',configuration_sha256=hashlib.sha256(canonical(config)).hexdigest(),source_manifest=manifest,source_binding=hashlib.sha256(canonical(manifest)).hexdigest(),authority_id='test-only',scope='TEST_ONLY',trust_approval=dict(approved_by='fixture',scope='TEST_ONLY',kernel_correct=True,privileged_manager_no_migration_reconfiguration_or_proxy=True,noninterference_scope='correct_kernel_and_approved_privileged_manager_noninterference_for_this_run'))
    binding['credential_baseline']=dict(uid=1000,gid=1003,nss_primary_gid=1003,nss_user='fixture',supplementary_groups=[1003])
    p['binding']=binding;q['security_record']['binding']=copy.deepcopy(binding);p['launch_manifest_sha256']=hashlib.sha256(canonical(dict(schema='cm-a-launch-v1',binding=binding,configuration=config,identity=dict(uid=1000,gid=1003)))).hexdigest();g['a_policy']=copy.deepcopy(p)
    q['security_record']['systemd']['MainPID']='42'
    q['security_record_raw']=json.dumps(q['security_record']);p['security_record_sha256']=hashlib.sha256(q['security_record_raw'].encode()).hexdigest();g['a_policy']=copy.deepcopy(p)
    q['snapshots']=[dict(monotonic_ns=900000000+i*500000000+j*200000000,evidence=copy.deepcopy(q['snapshots'][0]['evidence'])) for i in range(3) for j in range(2)]
    q['snapshots'].append(dict(monotonic_ns=2300000000,evidence=copy.deepcopy(q['snapshots'][0]['evidence'])))
    q['events']=[dict(copy.deepcopy(q['events'][0]),security_index=2*i) for i in range(3)]
    for i,event in enumerate(q['events']):
        for j,sample in enumerate(event['process_samples']):sample.update(begin_ns=910000000+i*500000000+j*1000000,end_ns=910000001+i*500000000+j*1000000)
        event['required_individual_evidence']=dict(identities={'42':event['second']},observations={'42':dict(status='stable',identity=event['second'])},current_pids=[42])
    running=copy.deepcopy(g['before']);running['monotonic_seconds']=1.5
    g['running_snapshots']=[running]
    g['child_identity']=dict(pid=43,start_ticks='100',state='R')
    childstat='43 (child) R 42 '+' '.join(['0']*17)+' 100'
    childidentity=dict(pid=43,start_ticks='100',state='R')
    samples=[dict(kind='stat',raw=childstat,identity=childidentity,ppid=42,begin_ns=1210000000+i*1000000,end_ns=1210000001+i*1000000) for i in range(3)]+[dict(kind='cgroup',raw='0::/system.slice/test.service',begin_ns=1220000000,end_ns=1220000001)]
    g['child_individual_witness']=dict(identity=childidentity,cgroup='0::/system.slice/test.service',process_samples=samples)
    for i,snapshot in enumerate([g['before'],running,g['after']]):
        snapshot.update(acquisition_begin_ns=800000000+i*500000000,acquisition_end_ns=1200000000+i*500000000,process_security_index=2*i,process_security_end_index=2*i+1)
        snapshot['process_observations']={'42':dict(status='group_accounted_bound_identity',identity=q['events'][i]['second'],individual_exit_proven=False)}
    o['before']=copy.deepcopy(g['before']);o['after']=copy.deepcopy(g['after'])
    running_raw=json.dumps(running).encode()+b'\n';(tmp_path/'guard-cgroup-running.jsonl').write_bytes(running_raw)
    g['running_snapshot_chain']=[dict(previous=None,sha256=hashlib.sha256((json.dumps(running,sort_keys=True,allow_nan=False)+'\n').encode()).hexdigest())]
    o['running_file']=dict(path='guard-cgroup-running.jsonl',sha256=hashlib.sha256(running_raw).hexdigest())
    props=q['security_record']['systemd'];rootraw=''.join(k+'='+v+'\n' for k,v in props.items())
    stat=q['events'][0]['process_samples'][0]['raw']
    status='Pid: 42\n'+'\n'.join(k+': '+v for k,v in q['snapshots'][0]['evidence']['status'].items())
    rootrows=[dict(monotonic_ns=t,raw=rootraw,properties=copy.deepcopy(props),proc_status=status,proc_stat=stat,namespaces=q['snapshots'][0]['evidence']['namespaces']) for t in (800000000,1500000000,2100000000)]
    o['security_end_record']=dict(raw=rootraw,props=props,monotonic_ns=2100000000)
    o['a_manager']=dict(launch_manifest=dict(schema='cm-a-launch-v1',binding=binding,configuration=config,identity=dict(uid=1000,gid=1003)),security_rows=rootrows,errors=[])
    raw=json.dumps(q).encode();(tmp_path/'a_security_proof.json').write_bytes(raw);g['a_proof_sha256']=hashlib.sha256(raw).hexdigest()
    return p,g,o

def test_formal_complete_fixture_pass(tmp_path):
    p,g,o=formal_fixture(tmp_path)
    assert checker.check_guard(tmp_path,p,g,o)['status']=='A_INDEPENDENT_CHECK_PASS'

import pytest
@pytest.mark.parametrize('mutation',['omitted_running','raw_running_cpu','raw_running_memory','epoch','counter_reset','config','root_raw','root_birth','root_time','trust','proof_hash','missing_security','missing_process_link'])
def test_formal_mutations_refused(tmp_path,mutation):
    p,g,o=formal_fixture(tmp_path)
    if mutation=='omitted_running':g['running_snapshots']=[]
    elif mutation=='raw_running_cpu':g['running_snapshots'][0]['raw']['cpu.stat']='usage_usec 999\nuser_usec 8\nsystem_usec 2\n'
    elif mutation=='raw_running_memory':g['running_snapshots'][0]['raw']['memory.current']='999\n'
    elif mutation=='epoch':g['running_snapshots'][0]['epoch']['inode']=999
    elif mutation=='counter_reset':g['running_snapshots'][0]['cpu_stat']['usage_usec']=0
    elif mutation=='config':o['a_manager']['launch_manifest']['configuration']['command']=['bad']
    elif mutation=='root_raw':o['a_manager']['security_rows'][1]['raw']='Delegate=yes\n'
    elif mutation=='root_birth':o['a_manager']['security_rows'][1]['proc_stat']='43 '+o['a_manager']['security_rows'][1]['proc_stat'].split(' ',1)[1]
    elif mutation=='root_time':o['a_manager']['security_rows'][-1]['monotonic_ns']=1
    elif mutation=='trust':p['binding']['trust_approval']['approved_by']=''
    elif mutation=='proof_hash':g['a_proof_sha256']='0'*64
    else:
        q=json.loads((tmp_path/'a_security_proof.json').read_text())
        if mutation=='missing_security':q['snapshots']=q['snapshots'][:2]
        else:q['events']=q['events'][:1]
        raw=json.dumps(q).encode();(tmp_path/'a_security_proof.json').write_bytes(raw);g['a_proof_sha256']=hashlib.sha256(raw).hexdigest()
    assert checker.check_guard(tmp_path,p,g,o)['status']=='REFUSED'


def test_future_gala_refuses_implicit_live_authority():
    from compute_metabolism.v0 import gala_observation_run
    with pytest.raises(ValueError,match='explicit approved LIVE A authority'):
        gala_observation_run.run_observation('/unused','unused',{}, {}, {})

def test_current_promotion_roles_include_a_proof_contract():
    from compute_metabolism.v0 import evex_profile
    assert evex_profile.A_FILE_ROLES=={'a_policy','a_proof','a_independent_check','guard_running','a_launch_manifest','a_manager_security'}

@pytest.mark.parametrize('roles',[[],['a_policy'],['a_proof']])
def test_v2_promotion_refuses_missing_a_inventory(tmp_path,roles):
    from compute_metabolism.v0 import evex_profile
    (tmp_path/'candidate-profile.json').write_text('{}')
    proof=dict(schema='COMPUTE_METABOLISM_GALA_EVEX_PROOF_V2',evidence_role='LIVE',campaign_id='campaign',run_id='run',files={r:{} for r in roles},gate_source_snapshot={},required_negative_classes=list(evex_profile.NEGATIVE_CLASSES))
    (tmp_path/'proof-bundle.json').write_text(json.dumps(proof))
    result=evex_profile.verify_promotion(tmp_path,tmp_path)
    assert result['promotion_allowed'] is False and 'inventory' in str(result['required_proofs'])

def test_v1_current_promotion_cannot_downgrade(tmp_path):
    from compute_metabolism.v0 import evex_profile
    (tmp_path/'candidate-profile.json').write_text('{}')
    proof=dict(schema='COMPUTE_METABOLISM_GALA_EVEX_PROOF_V1',evidence_role='LIVE',campaign_id='campaign',run_id='run',files={},gate_source_snapshot={},required_negative_classes=[])
    (tmp_path/'proof-bundle.json').write_text(json.dumps(proof))
    result=evex_profile.verify_promotion(tmp_path,tmp_path)
    assert result['promotion_allowed'] is False and 'formal A V2' in str(result['required_proofs'])


def test_future_gala_status_requires_independent_a_check(tmp_path):
    from compute_metabolism.v0 import gala_observation_run
    receipt=dict(outcome='GUARD_COMPLETE',measurement_valid=True)
    assert gala_observation_run.observation_status(receipt,tmp_path,True)==('UNRESOLVED_FAILURE','OBSERVATION_FAILED')


def test_future_review_and_regression_include_formal_a_contract():
    from compute_metabolism.v0 import evex_profile
    assert 'formal_a_group_policy_and_independent_resource_check' in evex_profile.REVIEW_OBLIGATIONS
    assert 'tests/test_compute_metabolism_a_proof.py' in evex_profile.REQUIRED_TEST_FILES


@pytest.mark.parametrize('attack',['chain','event_time','drop_event','snapshot_identity','child_missing','child_raw','child_time'])
def test_formal_process_and_chain_evidence_fail_closed(tmp_path,attack):
    p,g,o=formal_fixture(tmp_path)
    if attack=='chain':g['running_snapshot_chain']=[]
    elif attack=='snapshot_identity':g['before']['process_identities']['42']['start_ticks']='999';o['before']=copy.deepcopy(g['before'])
    elif attack=='child_missing':del g['child_individual_witness']
    elif attack=='child_raw':g['child_individual_witness']['process_samples'][0]['raw']='43 (child) R 999 '+' '.join(['0']*17)+' 100'
    elif attack=='child_time':g['child_individual_witness']['process_samples'][0]['begin_ns']=0
    else:
        q=json.loads((tmp_path/'a_security_proof.json').read_text())
        if attack=='event_time':q['events'][0]['process_samples'][0]['begin_ns']=0
        else:q['events']=q['events'][1:]
        raw=json.dumps(q).encode();(tmp_path/'a_security_proof.json').write_bytes(raw);g['a_proof_sha256']=hashlib.sha256(raw).hexdigest()
    assert checker.check_guard(tmp_path,p,g,o)['status']=='REFUSED'


def test_independent_reads_may_change_state_with_same_process_birth(tmp_path):
    p,g,o=formal_fixture(tmp_path)
    q=json.loads((tmp_path/'a_security_proof.json').read_text())
    strict=q['events'][0]['required_individual_evidence']
    strict['identities']['42']['state']='S';strict['observations']['42']['identity']['state']='S'
    raw=json.dumps(q).encode();(tmp_path/'a_security_proof.json').write_bytes(raw);g['a_proof_sha256']=hashlib.sha256(raw).hexdigest()
    assert checker.check_guard(tmp_path,p,g,o)['status']=='A_INDEPENDENT_CHECK_PASS'


def test_future_gala_rejects_different_a_epoch_before_ledger_or_launch():
    from compute_metabolism.v0 import gala_observation_run
    manifest={name:'1'*64 for name in ('compute_metabolism/v0/system_guard.py','compute_metabolism/v0/cgroup_noescape.py','compute_metabolism/v0/cgroup_noescape_policy.py','compute_metabolism/v0/cgroup_noescape_check.py')}
    authority=dict(scope='LIVE',authority_id='explicit-live',source_manifest=manifest,source_epoch={'source_binding':'different'},v1_source_binding='same',trust_approval=dict(approved_by='fixture',scope='LIVE',noninterference_scope='correct_kernel_and_approved_privileged_manager_noninterference_for_this_run',kernel_correct=True,privileged_manager_no_migration_reconfiguration_or_proxy=True))
    with pytest.raises(ValueError,match='exact prelaunch Gala A source epoch'):
        gala_observation_run.run_observation('/unused','unused',{'v1_source_binding':'same'},{'source_binding':'approved'},manifest,a_authority=authority)


def terminal_fixture(tmp_path):
    p,g,o=formal_fixture(tmp_path)
    q=json.loads((tmp_path/'a_security_proof.json').read_text())
    event=copy.deepcopy(q['events'][1]);event['pid']=43
    identity=dict(pid=43,start_ticks='100',state='Z');stat='43 (child) Z 42 '+' '.join(['0']*17)+' 100'
    event['first']=copy.deepcopy(identity);event['second']=copy.deepcopy(identity)
    for i,sample in enumerate(event['process_samples']):
        sample.update(begin_ns=1530000000+i*1000000,end_ns=1530000001+i*1000000)
        if sample['kind']=='stat':sample.update(raw=stat,identity=copy.deepcopy(identity),ppid=42)
    membership=dict(epoch=copy.deepcopy(g['before']['epoch']),pids=[42],begin_ns=1420000000,end_ns=1430000000,files=[dict(path=g['before']['epoch']['path']+'/cgroup.procs',raw='42\n',begin_ns=1420000001,end_ns=1420000002,device=1,inode=2)])
    strict_samples=copy.deepcopy(event['process_samples'])
    exit_proof=dict(basis='BOUND_PROCESS_PIDFD_AND_TERMINAL_OWNED_CGROUP',terminal_identity=copy.deepcopy(identity),terminal_cgroup='0::/system.slice/test.service',pidfd_events=[[5,1]],process_samples=strict_samples,membership1=copy.deepcopy(membership),membership2=copy.deepcopy(membership))
    event['required_individual_evidence']=dict(identities={},observations={'43':dict(status='exited_during_sample',observed_identity=copy.deepcopy(identity),exit_evidence=exit_proof)},current_pids=[42])
    q['events'].insert(2,event)
    running=g['running_snapshots'][0];running['enumerated_pids']=[42,43];running['process_identities']['43']=copy.deepcopy(identity);running['process_observations']['43']=dict(status='group_accounted_bound_identity',identity=copy.deepcopy(identity),individual_exit_proven=False)
    raw=json.dumps(running).encode()+b'\n';(tmp_path/'guard-cgroup-running.jsonl').write_bytes(raw);o['running_file']['sha256']=hashlib.sha256(raw).hexdigest();g['running_snapshot_chain']=[dict(previous=None,sha256=hashlib.sha256((json.dumps(running,sort_keys=True,allow_nan=False)+'\n').encode()).hexdigest())]
    raw=json.dumps(q).encode();(tmp_path/'a_security_proof.json').write_bytes(raw);g['a_proof_sha256']=hashlib.sha256(raw).hexdigest()
    return p,g,o

def test_protected_terminal_witness_complete_pass(tmp_path):
    p,g,o=terminal_fixture(tmp_path)
    assert checker.check_guard(tmp_path,p,g,o)['status']=='A_INDEPENDENT_CHECK_PASS'

@pytest.mark.parametrize('attack',['raw_terminal_state','pidfd_mask','membership_raw'])
def test_protected_terminal_witness_mutations_refused(tmp_path,attack):
    p,g,o=terminal_fixture(tmp_path);q=json.loads((tmp_path/'a_security_proof.json').read_text());exit_proof=q['events'][2]['required_individual_evidence']['observations']['43']['exit_evidence']
    if attack=='raw_terminal_state':exit_proof['process_samples'][-2]['raw']=exit_proof['process_samples'][-2]['raw'].replace(') Z ',') R ')
    elif attack=='pidfd_mask':exit_proof['pidfd_events']=[[5,16]]
    else:exit_proof['membership1']['files'][0]['raw']='99\n'
    raw=json.dumps(q).encode();(tmp_path/'a_security_proof.json').write_bytes(raw);g['a_proof_sha256']=hashlib.sha256(raw).hexdigest()
    assert checker.check_guard(tmp_path,p,g,o)['status']=='REFUSED'
