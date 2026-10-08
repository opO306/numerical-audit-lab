"""Synthetic analysis contracts only: no guard/chroot/numerical execution."""
import copy
from dataclasses import asdict
import hashlib
import importlib
import importlib.util
import json
import io
from pathlib import Path
import types

import pytest


@pytest.mark.parametrize('policy', ['STOP_INCOMPLETE', 'UNRESOLVED_VARIABILITY', 'PENDING_ROUND7', 'RESOURCE_PRECEDENCE'])
def test_wave2_writer_policy_receipts_consume_bound_historical_proof(fixture_campaign, policy):
    module = api()
    root, config, add = fixture_campaign
    if policy == 'RESOURCE_PRECEDENCE':
        ledger = campaign.CampaignLedger.open(Path(config['ledger_path']), CampaignLimits())
        ledger.begin_attempt('TEST_ONLY-preflight', 'prior-guard', '2c', 'guard-preflight', 0)
        ledger.finish_attempt('prior-guard', 3648, 1, 0, 0, 'GUARD_COMPLETE')
    add(role='warm-up', round_index=0)
    if policy in ('STOP_INCOMPLETE', 'RESOURCE_PRECEDENCE'):
        for i in range(1, 4):
            add('2c', round_index=i, wall=181, outcome='UNRESOLVED_FAILURE', resource='OUTER_WALL_TIMEOUT')
    else:
        for i in range(1, 8):
            for profile in ('2c', '1c', '0p5c') if i < 7 or policy != 'PENDING_ROUND7' else ('2c',):
                add(profile, round_index=i, wall=1 if i == 1 else 20)
    state = campaign.CampaignLedger.read_snapshot(Path(config['ledger_path']))
    rows = [row for row in state['attempts'] if row['campaign_id'] == config['campaign_id']]
    before = inventory(root.parent)
    receipts, issues = module._finalizations(config, state, rows, root)
    assert issues == []
    last = receipts[-1]['receipt']
    want = 'CONTINUE' if policy == 'PENDING_ROUND7' else 'CAMPAIGN_RESOURCE_EXHAUSTED' if policy == 'RESOURCE_PRECEDENCE' else policy
    assert last['campaign_outcome'] == want
    assert last['policy_status']['campaign_outcome'] == ('STOP_INCOMPLETE' if policy == 'RESOURCE_PRECEDENCE' else want)
    assert last['needs_next_attempt'] is (policy == 'PENDING_ROUND7')
    assert inventory(root.parent) == before
    if policy == 'PENDING_ROUND7':
        assert campaign.next_attempt(rows)['profile'] == '1c'
        assert campaign.next_attempt(rows)['round_index'] == 7
    if policy == 'RESOURCE_PRECEDENCE':
        assert last['resource_reason'] == 'CAMPAIGN_WALL_CEILING'


@pytest.mark.parametrize('mutation', ['policy_status', 'campaign_outcome', 'campaign_stop', 'needs_next_attempt'])
def test_wave2_hash_valid_receipt_policy_substitution_is_refused(fixture_campaign, mutation):
    module = api()
    root, config, add = fixture_campaign
    add(role='warm-up', round_index=0)
    if mutation not in ('policy_status', 'needs_next_attempt'):
        for i in range(1, 4):
            add('2c', round_index=i, wall=181, outcome='UNRESOLVED_FAILURE', resource='OUTER_WALL_TIMEOUT')
    state = campaign.CampaignLedger.read_snapshot(Path(config['ledger_path']))
    pointer = state['campaign_finalizations'][-1]
    path = Path(pointer['locator'])
    receipt = json.loads(path.read_bytes())
    if mutation == 'policy_status':
        receipt['policy_status']['campaign_outcome'] = 'STOP_INCOMPLETE'
    elif mutation == 'campaign_outcome':
        receipt['campaign_outcome'] = 'CONTINUE'
        pointer['campaign_outcome'] = 'CONTINUE'
    elif mutation == 'campaign_stop':
        receipt['campaign_stop'] = False
    else:
        receipt['needs_next_attempt'] = False
    path.chmod(0o600)
    pointer['sha256'] = put(path, receipt)
    rows = [row for row in state['attempts'] if row['campaign_id'] == config['campaign_id']]
    receipts, issues = module._finalizations(config, state, rows, root)
    assert any('finalization' in issue for issue in issues)
    assert not any(item['locator'] == str(path) for item in receipts)


def test_finalfix_partial_metrics_locator_without_invented_values(fixture_campaign):
    root,config,add=fixture_campaign
    parent=add()
    snapshot={'status':'PARTIAL','metrics':[{'initial_acquisition_seconds':.125}]}
    digest=put(parent/'v1/driver-metrics-snapshot.json',snapshot)
    row=campaign.CampaignLedger.read_snapshot(Path(config['ledger_path']))['attempts'][0]
    result=api()._attempt(row,config,root,False)
    metric=result['raw_metrics']['driver_metrics_snapshot']
    assert metric['sha256']==digest and metric['value']==snapshot


def test_finalfix_analysis_resource_cannot_hide_unbound_conflict(fixture_campaign,monkeypatch):
    module=api()
    root,config,add=fixture_campaign
    parent=add(outcome='UNRESOLVED_FAILURE',resource='OUTER_WALL_TIMEOUT',wall=181)
    def semantic(v1,config,n,receipt):
        report=json.loads((v1/'admission.json').read_bytes())
        report['verification_conflict']=True
        context=json.loads((v1.parent/'execution.json').read_bytes())['admission_report']['classification_context']
        return report,context,{}
    monkeypatch.setattr(module,'_semantic_evaluation',semantic)
    row=campaign.CampaignLedger.read_snapshot(Path(config['ledger_path']))['attempts'][0]
    result=module._attempt(row,config,root,True)
    assert not result['analysis_eligible'] and any('semantic fault' in issue for issue in result['issues'])

from compute_metabolism.v0 import campaign
from compute_metabolism.v0.profiles import CampaignLimits, APPROVED_V1_SOURCE_BINDING, APPROVED_N3_FINAL_PUBLIC_BITS


def api():
    assert importlib.util.find_spec('compute_metabolism.v0.analyze') is not None, 'Task6 read-only analysis API missing'
    return importlib.import_module('compute_metabolism.v0.analyze')


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(value, sort_keys=True).encode()
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def inventory(root):
    return {str(p.relative_to(root)): (hashlib.sha256(p.read_bytes()).hexdigest(), p.stat().st_mtime_ns)
            for p in root.rglob('*') if p.is_file()}


@pytest.fixture
def fixture_campaign(tmp_path, monkeypatch):
    """Real durable ledger; synthetic saved LIVE-shaped admission/helper boundary."""
    root = tmp_path/'prepared'
    repo = root/'workspace'
    upper = repo/'compute_metabolism/v0/artifacts/operational/budget.json'
    ident = {}
    files = {}
    for name in campaign._IDENTITY_FILES:
        target = repo/name
        target.parent.mkdir(parents=True, exist_ok=True)
        raw = (Path(__file__).parents[1]/name).read_bytes()
        target.write_bytes(raw)
        files[name] = raw
        ident[name] = dict(path=str(target), sha256=hashlib.sha256(raw).hexdigest())
    reference = dict(schema='COMPUTE_METABOLISM_REFERENCE_V0', requested_steps=3,
        source_binding=APPROVED_V1_SOURCE_BINDING, final_public_bits=list(APPROVED_N3_FINAL_PUBLIC_BITS),
        provenance=[dict(locator='historical/TEST_ONLY', sha256='a'*64, role='HISTORICAL_REFERENCE')])
    topology = {'0':dict(core_id='0',physical_package_id='0'), '1':dict(core_id='1',physical_package_id='0')}
    inputs = {}
    for name, doc in zip(campaign._INPUT_FILES, ({'TEST_ONLY':True}, {'topology':topology}, reference)):
        target = tmp_path/name
        digest = put(target,doc)
        files[name] = target.read_bytes()
        inputs[name] = dict(path=str(target),sha256=digest)
    config = dict(schema='COMPUTE_METABOLISM_CAMPAIGN_V0',campaign_id='gcp-test',root_directory=str(root),
        repo_root=str(repo),ledger_path=str(upper), inputs=inputs,identities=ident)
    raw = json.dumps(config).encode()
    campaign.initialize_campaign(config,raw,files)
    campaign_root = upper.parent/'gcp-test'
    def add(profile='2c',role='measured',round_index=1,wall=10,cpu=5,outcome='ACCEPT',resource=None):
        number = len(campaign.CampaignLedger.read_snapshot(upper)['attempts'])
        run_id = f'r{number}'
        branch = 'warmup' if role=='warm-up' else f'round-{round_index:02d}'
        parent = campaign_root/branch/run_id
        v1 = parent/'v1'
        v1.mkdir(parents=True)
        n = 1 if role=='warm-up' else 3
        attempt_config = dict(run_id=run_id,campaign_id='gcp-test',profile=profile,role=role,
            requested_steps=n,round_index=round_index,repo_root='/workspace',
            attempt_root='/'+parent.relative_to(root).as_posix(),ledger_path='/'+upper.relative_to(root).as_posix())
        for prefix,name in (('execution_environment','execution-environment.json'),('campaign_environment','campaign-environment.json'),('reference','reference.json')):
            attempt_config[prefix+'_path']='/'+(campaign_root/name).relative_to(root).as_posix()
            attempt_config[prefix+'_sha256']=inputs[name]['sha256']
        config_hash = put(parent.parent/f'config-{run_id}.json',attempt_config)
        epoch = dict(path='/sys/fs/cgroup/system.slice/compute-metabolism-test.service',device=1,inode=2,boot_id='test-boot')
        before = dict(epoch=epoch,cpus=[0,1] if profile=='2c' else [0],monotonic_seconds=1,
            cpu_max=dict(unlimited=True,finite_ancestors=[]) if profile!='0p5c' else dict(unlimited=False,quota_usec=50000,period_usec=100000,finite_ancestors=[]),
            raw={'memory.max':'4294967296','memory.swap.max':'0'},memory={'effective_bytes':4294967296},swap={'effective_bytes':0},
            cpu_stat=dict(usage_usec=10,user_usec=7,system_usec=3,nr_periods=1,nr_throttled=0,throttled_usec=0),
            memory_events=dict(oom=0,oom_kill=0),memory_peak=50,pids=[42],process_identities={'42':dict(start_ticks='55')})
        after = copy.deepcopy(before)
        after['monotonic_seconds'] = 1+wall
        after['cpu_stat']['usage_usec'] = 10+int(cpu*1000000)
        if resource=='CGROUP_OOM': after['memory_events']['oom_kill']=1
        guard = dict(run_id=run_id,profile=profile,unit=epoch['path'].split('/')[-1],test_only=False,deadline_seconds=180,
            writer_bytes=671088640,before=before,after=after,wall_seconds=wall,terminal=True,launcher_reaped=True,
            measurement_valid=True,outer_timeout_proved=resource=='OUTER_WALL_TIMEOUT',outcome='GUARD_COMPLETE',
            inner=dict(topology_before=topology,topology_after=topology,wrapper_identity=dict(pid=42,start_ticks='55'),
                containment=dict(remaining_pids=[]),cleanup_errors=[],final_errors=[]))
        guard_hash=put(parent/'guard-outer.json',guard)
        guard.update(proof_locator=str(parent/'guard-outer.json'),proof_sha256=guard_hash)
        manifest=dict(schema='COMPUTE_METABOLISM_ATTEMPT_V0',run_id=run_id,profile=profile,campaign_id='gcp-test',role=role,
            round_index=round_index,requested_steps=n,evidence_scope='LIVE',inputs={k:v['sha256'] for k,v in inputs.items()})
        for name in campaign._CONTEXT_FILES:
            if name in files: (v1/name).write_bytes(files[name])
            elif name=='attempt.json': put(v1/name,manifest)
            elif name=='admission.json': continue
            else: put(v1/name,{'TEST_ONLY':True})
        context=dict(run_id=run_id,campaign_id='gcp-test',profile=profile,role=role,round_index=round_index,unit=guard['unit'],epoch=epoch,
            evidence_scope='LIVE',source_binding=APPROVED_V1_SOURCE_BINDING,input_sha256=manifest['inputs'],
            manifest_sha256=hashlib.sha256((v1/'attempt.json').read_bytes()).hexdigest(),
            environment_before_sha256=hashlib.sha256((v1/'environment-before.json').read_bytes()).hexdigest(),
            environment_after_sha256=hashlib.sha256((v1/'environment-after.json').read_bytes()).hexdigest(),
            upper_before_sha256=hashlib.sha256((v1/'upper-ledger-before.json').read_bytes()).hexdigest())
        admission=dict(schema='COMPUTE_METABOLISM_ADMISSION_V0',run_id=run_id,requested_steps=n,outcome=outcome,
            admitted=outcome=='ACCEPT',evidence_scope='LIVE',correctness_authority='EXISTING_HASH_BOUND_LIVE_CHECKER',
            raw_v1_result=dict(verdict='ACCEPT' if outcome=='ACCEPT' else 'STOP'),formal_certification=False,
            final_public_bits=list(APPROVED_N3_FINAL_PUBLIC_BITS))
        put(v1/'admission.json',admission)
        put(v1/f'runs/{run_id}/metrics.json',[dict(paused_seconds=10,seal_seconds=2,produce_seconds=3,check_seconds=4,publication_seconds=1)])
        (parent/'writer_quota.txt').write_bytes(b'17')
        enriched=dict(admission,classification_context=context)
        hashes={name:hashlib.sha256((v1/name).read_bytes()).hexdigest() for name in campaign._CONTEXT_FILES}
        stdout=json.dumps(dict(context=context,evidence_sha256=hashes)).encode()
        admin=dict(measurement_role='ADMINISTRATION_ONLY',returncode=0,stdout_hex=stdout.hex(),stderr_hex='',
            stdout_sha256=hashlib.sha256(stdout).hexdigest(),stderr_sha256=hashlib.sha256(b'').hexdigest(),evidence_sha256=hashes,wall_seconds=.01)
        classified=campaign.classify_attempt(enriched,guard,1)
        if role=='warm-up' and classified['wrapper_outcome']!='ACCEPT': classified.update(campaign_stop=True,campaign_outcome='STOP')
        host_modules={name:dict(origin=str(repo/f'compute_metabolism/v0/{name}.py'),spec_origin=str(repo/f'compute_metabolism/v0/{name}.py'),
            expected_origin=str(repo/f'compute_metabolism/v0/{name}.py'),sha256=ident[f'compute_metabolism/v0/{name}.py']['sha256'],
            expected_sha256=ident[f'compute_metabolism/v0/{name}.py']['sha256']) for name in ('profiles','system_guard')}
        execution=dict(schema='COMPUTE_METABOLISM_EXECUTION_V0',run_id=run_id,classification=classified,admission_report=enriched,
            guard_receipt=guard,config_sha256=config_hash,identities_before=ident,
            identities_after={k:v['sha256'] for k,v in ident.items()},writer_reserved_bytes=17,retained_bytes=1,
            administration=admin,host_dependencies_before=dict(status='VALID',modules=host_modules),host_dependencies_after=dict(status='VALID',modules=host_modules))
        retained=campaign.logical_tree_bytes(parent)
        for _ in range(32):
            execution['retained_bytes']=retained
            payload=json.dumps(execution,sort_keys=True).encode()
            actual=campaign.logical_tree_bytes(parent)+len(payload)
            if actual==retained: break
            retained=actual
        else: raise AssertionError('synthetic execution size did not converge')
        (parent/'execution.json').write_bytes(payload)
        execution_hash=hashlib.sha256(payload).hexdigest()
        ledger=campaign.CampaignLedger.open(upper,CampaignLimits())
        ledger.begin_attempt('gcp-test',run_id,profile,role,round_index)
        with ledger._authority():
            state=campaign._read(upper)
            record=ledger._running_record(state,run_id)
            record.update(classified,execution_locator=str(parent/'execution.json'),execution_sha256=execution_hash)
            ledger._write(state)
        ledger.finish_attempt(run_id,wall,classified.get('cpu_seconds'),17,retained,classified['wrapper_outcome'])
        rows = [row for row in ledger.snapshot()['attempts'] if row['campaign_id']=='gcp-test']
        campaign._finalize_upper(ledger,config,run_id,campaign.next_attempt(rows) is not None,'POST_FINISH')
        return parent
    return campaign_root, config, add


def fake_semantics(monkeypatch, module):
    # Existing evaluator is separately covered by Task4; this replaces only the
    # approved external prepared-Python boundary, never ledger/classifier logic.
    def evaluate(root,config,n,receipt):
        report=json.loads((root/'admission.json').read_bytes())
        context=json.loads((root.parent/'execution.json').read_bytes())['admission_report']['classification_context']
        return report,context,dict(measurement_role='ADMINISTRATION_ONLY',wall_seconds=.02,status='SYNTHETIC_BOUNDARY')
    monkeypatch.setattr(module,'_semantic_evaluation',evaluate)


def complete(root,config,add):
    add(role='warm-up',round_index=0)
    for i,order in enumerate((('2c','1c','0p5c'),('1c','0p5c','2c'),('0p5c','2c','1c')),1):
        for p in order: add(p,round_index=i,wall={'2c':10,'1c':20,'0p5c':40}[p],cpu={'2c':5,'1c':6,'0p5c':7}[p])


def test_empty_campaign_is_incomplete_and_readonly(fixture_campaign):
    module=api()
    root,_,_=fixture_campaign
    before=inventory(root.parent)
    summary=module.analyze_campaign(root)
    assert summary['outcome']=='INCOMPLETE'
    assert summary['counts']['all_attempts']==0
    assert summary['raw_tree']['before_sha256']==summary['raw_tree']['after_sha256']
    assert inventory(root.parent)==before


def test_stable_actual_bound_contract_stats_ratios_and_no_timing_sum(fixture_campaign,monkeypatch):
    module=api(); fake_semantics(monkeypatch,module)
    root,config,add=fixture_campaign; complete(root,config,add)
    before=inventory(root.parent)
    result=module.analyze_campaign(root)
    assert result['outcome']=='COMPLETE'
    assert result['counts']==dict(all_attempts=10,campaign_attempts=10,warm_up=1,measured=9,guard_preflight=0)
    assert result['profiles']['1c']['outer_wall_seconds']==dict(n=3,mean=20.0,sample_sd=0.0,cv=0.0,unit='seconds')
    assert result['profiles']['1c']['cpu_seconds']['mean']==6
    assert result['derived_ratios']['1c']['outer_wall_ratio']==2
    assert result['derived_ratios']['1c']['cpu_ratio']==1.2
    assert result['derived_ratios']['1c']['measurement_role']=='DERIVED_ONLY'
    assert result['attempts'][1]['raw_metrics']['v1_metrics']['value'][0]['paused_seconds']==10
    assert result['timing_contract']['wall_authority']=='OUTER_GUARD_WALL'
    assert 'total_seconds' not in result['attempts'][1]['raw_metrics']
    assert before==inventory(root.parent)


@pytest.mark.parametrize('mutation', ['execution_hash','guard_hash','helper_hash','profile','n3bits','test_only','finalization'])
def test_saved_labels_cannot_admit_tampered_evidence(fixture_campaign,monkeypatch,mutation):
    module=api(); fake_semantics(monkeypatch,module)
    root,_,add=fixture_campaign
    parent=add()
    path=parent/'execution.json'; execution=json.loads(path.read_bytes())
    if mutation=='execution_hash': path.write_bytes(path.read_bytes()+b' ')
    elif mutation=='guard_hash': (parent/'guard-outer.json').write_bytes(b'{}')
    elif mutation=='helper_hash': execution['administration']['stdout_sha256']='0'*64
    elif mutation=='profile': execution['admission_report']['classification_context']['profile']='1c'
    elif mutation=='n3bits':
        admission=json.loads((parent/'v1/admission.json').read_bytes()); admission['final_public_bits'][0]='bad'
        put(parent/'v1/admission.json',admission)
    elif mutation=='test_only': execution['admission_report']['evidence_scope']='TEST_ONLY'
    elif mutation=='finalization':
        final=next(root.glob('campaign-finalization-*.json')); final.chmod(0o600); final.write_bytes(b'{}')
    if mutation in ('helper_hash','profile','test_only'):
        digest=put(path,execution); state=json.loads((root.parent/'budget.json').read_bytes()); state['attempts'][0]['execution_sha256']=digest; put(root.parent/'budget.json',state)
    result=module.analyze_campaign(root)
    assert result['outcome']!='COMPLETE'
    assert not result['attempts'][0]['analysis_eligible']
    assert result['profiles']['2c']['outer_wall_seconds']['n']==0


@pytest.mark.parametrize('n,want',[(3,'EXPAND_TO_5'),(5,'EXPAND_TO_7'),(7,'UNRESOLVED_VARIABILITY')])
def test_mixed_outcomes_do_not_use_accept_subset_stability(fixture_campaign,monkeypatch,n,want):
    module=api(); fake_semantics(monkeypatch,module)
    root,_,add=fixture_campaign
    add(role='warm-up',round_index=0)
    for i in range(1,n+1): add('0p5c',round_index=i,wall=181 if i==1 else 10,outcome='UNRESOLVED_FAILURE' if i==1 else 'ACCEPT',resource='OUTER_WALL_TIMEOUT' if i==1 else None)
    result=module.analyze_campaign(root)
    assert result['profiles']['0p5c']['decision']['decision']==want
    assert result['profiles']['0p5c']['outer_wall_seconds']['n']==n-1
    assert result['derived_ratios']=={}
    assert result['outcome']!='COMPLETE'


def test_changed_current_source_preserves_failed_and_partial_history(fixture_campaign):
    module=api(); root,config,add=fixture_campaign
    add(outcome='ENVIRONMENT_INVALID')
    Path(config['identities']['compute_metabolism/v0/run_v1.py']['path']).write_bytes(b'changed')
    ledger=campaign.CampaignLedger.open(Path(config['ledger_path']),CampaignLimits())
    ledger.begin_attempt('gcp-test','partial','1c','measured',2)
    ledger.record_unresolved('partial',dict(outcome='UNRESOLVED_FAILURE',reason='interrupted'))
    before=inventory(root.parent)
    result=module.analyze_campaign(root)
    assert result['counts']['campaign_attempts']==2
    assert result['attempts'][0]['raw_record']['outcome']=='ENVIRONMENT_INVALID'
    assert result['attempts'][1]['raw_record']['partial_receipts'][0]['reason']=='interrupted'
    assert result['attempts'][0]['raw_record']['cpu_seconds'] == 5
    assert result['outcome']=='STOP'
    assert inventory(root.parent)==before


def test_cli_exclusive_versions_and_outputs_count_without_ledger_write(fixture_campaign,monkeypatch,capsys):
    module=api(); fake_semantics(monkeypatch,module)
    root,config,add=fixture_campaign; complete(root,config,add)
    ledger_before=(root.parent/'budget.json').read_bytes()
    assert module.main(['--campaign-root',str(root)])==0
    first=(root/'analysis/summary.json').read_bytes()
    summary=json.loads(first)
    assert summary['output_accounting']['output_bytes']==sum(p.stat().st_size for p in (root/'analysis').iterdir() if p.is_file())
    assert summary['output_accounting']['projected_upper_bytes']==campaign.logical_tree_bytes(root.parent)
    assert module.main(['--campaign-root',str(root)])==0
    assert (root/'analysis/summary.json').read_bytes()==first
    assert (root/'analysis/version-0001/summary.json').is_file()
    assert (root.parent/'budget.json').read_bytes()==ledger_before

@pytest.mark.parametrize('fault',['none','run','n','tree','source','timeout','overflow','changed'])
def test_prepared_helper_fixed_namespace_hash_response_and_failures(fixture_campaign,monkeypatch,fault):
    module=api(); root,config,add=fixture_campaign; parent=add()
    from compute_metabolism.v0 import system_guard
    monkeypatch.setattr(system_guard,'PREPARED_ROOT',Path(config['root_directory']))
    execution=json.loads((parent/'execution.json').read_bytes())
    report=json.loads((parent/'v1/admission.json').read_bytes())
    context=execution['admission_report']['classification_context']
    def boundary(argv,request,cwd):
        assert argv==campaign.prepared_helper_argv(Path(config['root_directory']),'evaluation')
        assert cwd==Path(config['repo_root'])
        payload=json.loads(request)
        assert payload['root']=='/workspace/compute_metabolism/v0/artifacts/operational/gcp-test/round-01/r0/v1'
        assert payload['requested_steps']==3
        response=dict(report=copy.deepcopy(report),context=copy.deepcopy(context),requested_steps=3,
            attempt_tree_sha256=payload['attempt_tree_sha256'],raw_preserved=True)
        if fault=='run': response['report']['run_id']='foreign'
        if fault=='n': response['requested_steps']=1
        if fault=='tree': response['attempt_tree_sha256']='0'*64
        if fault=='source': response['context']['source_binding']='0'*64
        if fault=='changed': (parent/'v1/environment-before.json').write_bytes(b'changed')
        return dict(returncode=0,stdout=json.dumps(response).encode(),stderr=b'',timed_out=fault=='timeout',overflow=fault=='overflow')
    monkeypatch.setattr(module,'_bounded_process',boundary)
    if fault=='none':
        before=inventory(root.parent)
        result,_,admin=module._semantic_evaluation(parent/'v1',config,3,execution['guard_receipt'])
        assert result['run_id']=='r0' and admin['measurement_role']=='ADMINISTRATION_ONLY'
        assert inventory(root.parent)==before
    else:
        with pytest.raises(ValueError): module._semantic_evaluation(parent/'v1',config,3,execution['guard_receipt'])


@pytest.mark.parametrize('inner',['/workspace/compute_metabolism/v0/artifacts/operational/gcp-test/round-08/r0/v1',
    '/workspace/compute_metabolism/v0/artifacts/operational/gcp-test/round-01/r0/../v1', '/tmp/foreign/v1'])
def test_helper_refuses_unapproved_namespace_without_evaluation(monkeypatch,inner):
    module=api()
    import io
    monkeypatch.setattr(module.sys,'stdin',type('Input',(),{'buffer':io.BytesIO(json.dumps(dict(root=inner,requested_steps=3,attempt_tree_sha256='0'*64)).encode())})())
    with pytest.raises(ValueError): module._evaluation_helper()


def test_analysis_output_crossing_ceiling_keeps_every_byte_and_reports_stop(fixture_campaign,monkeypatch):
    module=api(); fake_semantics(monkeypatch,module)
    root,config,add=fixture_campaign; complete(root,config,add)
    summary=module.analyze_campaign(root)
    assert summary['outcome']=='COMPLETE'
    sparse=root.parent/'retained-output-boundary.bin'
    needed=3221225472-campaign.logical_tree_bytes(root.parent)-100
    with sparse.open('wb') as stream: stream.truncate(needed)
    before_ledger=(root.parent/'budget.json').read_bytes()
    directory=module._write_analysis(root,summary)
    result=json.loads((directory/'summary.json').read_bytes())
    assert result['outcome']=='PENDING_PUBLICATION' and result['proposed_outcome']=='STOP'
    assert json.loads((directory/'publication.json').read_bytes())['outcome']=='STOP'
    assert result['output_accounting']['projected_upper_bytes']>=3221225472
    assert result['output_accounting']['projected_upper_bytes']==campaign.logical_tree_bytes(root.parent)
    assert sparse.stat().st_size==needed
    assert (root.parent/'budget.json').read_bytes()==before_ledger


def test_stable_resource_first_three_half_core_without_performance_ratio(fixture_campaign,monkeypatch):
    module=api(); fake_semantics(monkeypatch,module)
    root,_,add=fixture_campaign
    add(role='warm-up',round_index=0)
    for i,order in enumerate((('2c','1c','0p5c'),('1c','0p5c','2c'),('0p5c','2c','1c')),1):
        for profile in order:
            add(profile,round_index=i,wall=181 if profile=='0p5c' else 10,
                outcome='UNRESOLVED_FAILURE' if profile=='0p5c' else 'ACCEPT',
                resource='OUTER_WALL_TIMEOUT' if profile=='0p5c' else None)
    result=module.analyze_campaign(root)
    assert result['outcome']=='COMPLETE'
    assert result['profiles']['0p5c']['decision']['decision']=='STABLE_RESOURCE_REFUSAL'
    assert result['profiles']['0p5c']['outer_wall_seconds']['n']==0
    assert '0p5c' not in result['derived_ratios']


def test_sample_sd_preserves_cpu_outlier_and_blocks_comparison(fixture_campaign,monkeypatch):
    module=api(); fake_semantics(monkeypatch,module)
    root,_,add=fixture_campaign; add(role='warm-up',round_index=0)
    for i in range(1,4): add(round_index=i,wall=10,cpu=i)
    result=module.analyze_campaign(root)
    assert result['profiles']['2c']['cpu_seconds']==dict(n=3,mean=2.0,sample_sd=1.0,cv=.5,unit='seconds')
    assert result['profiles']['2c']['decision']['decision']=='EXPAND_TO_5'
    assert len(result['attempts'])==4 and result['derived_ratios']=={}


def test_saved_host_valid_label_without_origin_hash_evidence_refuses(fixture_campaign,monkeypatch):
    module=api(); fake_semantics(monkeypatch,module)
    root,config,add=fixture_campaign; parent=add()
    path=parent/'execution.json'; execution=json.loads(path.read_bytes())
    execution['host_dependencies_before']=dict(status='VALID')
    digest=put(path,execution)
    state=json.loads((root.parent/'budget.json').read_bytes()); state['attempts'][0]['execution_sha256']=digest; put(root.parent/'budget.json',state)
    result=module._attempt(state['attempts'][0],config,root,True)
    assert not result['analysis_eligible']


def test_report_provenance_binds_executing_analyzer_source(fixture_campaign):
    module=api(); root,_,_=fixture_campaign
    result=module.analyze_campaign(root)
    assert result['analysis_source']['origin']==str(Path(module.__file__).resolve())
    assert result['analysis_source']['sha256']==hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()


def test_semantic_boundary_failure_retains_administrative_receipt(fixture_campaign,monkeypatch):
    module=api(); root,_,add=fixture_campaign; add()
    def failure(*args):
        raise module.SemanticFailure('synthetic prepared helper timeout',dict(measurement_role='ADMINISTRATION_ONLY',timed_out=True,wall_seconds=30))
    monkeypatch.setattr(module,'_semantic_evaluation',failure)
    result=module.analyze_campaign(root)
    assert result['outcome']=='STOP'
    assert result['attempts'][0]['administrative_evaluation']['timed_out'] is True
    assert result['attempts'][0]['raw_record']['outer_wall_seconds']==10

@pytest.mark.parametrize('fault',['retained','config_path','config_ledger','config_input'])
def test_bound_execution_cannot_hide_raw_cost_or_inner_config_fault(fixture_campaign,monkeypatch,fault):
    module=api(); fake_semantics(monkeypatch,module)
    root,config,add=fixture_campaign; parent=add()
    path=parent/'execution.json'; execution=json.loads(path.read_bytes())
    record=campaign.CampaignLedger.read_snapshot(Path(config['ledger_path']))['attempts'][0]
    if fault=='retained':
        execution['retained_bytes']=record['retained_bytes']=1
    else:
        config_path=parent.parent/'config-r0.json'; attempt=json.loads(config_path.read_bytes())
        key={'config_path':'attempt_root','config_ledger':'ledger_path','config_input':'reference_sha256'}[fault]
        attempt[key]='foreign'
        execution['config_sha256']=put(config_path,attempt)
    record['execution_sha256']=put(path,execution)
    result=module._attempt(record,config,root,True)
    assert not result['analysis_eligible']


def test_helper_deadline_covers_blocked_stdin_delivery(monkeypatch):
    module=api()
    import io
    import threading
    import subprocess
    killed=threading.Event()
    class Input:
        def write(self,request):
            if not killed.wait(.2): raise AssertionError('timeout waiter never started during blocked stdin')
        def close(self): pass
    class Process:
        stdin=Input(); stdout=io.BytesIO(b''); stderr=io.BytesIO(b''); returncode=-9
        def wait(self,timeout=None):
            if timeout is not None:
                assert timeout==30
                raise subprocess.TimeoutExpired('synthetic fixed helper',30)
            return -9
        def kill(self): killed.set()
    monkeypatch.setattr(module.subprocess,'Popen',lambda *args,**kwargs:Process())
    result=module._bounded_process(['synthetic-fixed-helper'],b'bounded-request',Path('.'))
    assert result['timed_out'] is True and result['returncode']==-9

@pytest.mark.parametrize('phase',['before','during'])
def test_publication_same_size_raw_mutation_never_submits_complete(fixture_campaign,monkeypatch,phase):
    module=api(); fake_semantics(monkeypatch,module)
    root,config,add=fixture_campaign; complete(root,config,add)
    target=root/'round-01/r1/guard-outer.json'
    original=target.read_bytes()
    altered=original.replace(b'"wall_seconds": 10',b'"wall_seconds": 11')
    assert altered!=original and len(altered)==len(original)
    original_analyze=module.analyze_campaign
    if phase=='before':
        def analyzed(path):
            summary=original_analyze(path); target.write_bytes(altered); return summary
        monkeypatch.setattr(module,'analyze_campaign',analyzed)
    else:
        original_write=campaign._exclusive_raw
        def mutating_write(path,raw):
            original_write(path,raw)
            if path.name=='summary.json': target.write_bytes(altered)
        monkeypatch.setattr(campaign,'_exclusive_raw',mutating_write)
    assert module.main(['--campaign-root',str(root)])==2
    assert target.read_bytes()==altered
    candidate=json.loads((root/'analysis/summary.json').read_bytes())
    publication=json.loads((root/'analysis/publication.json').read_bytes())
    assert candidate['outcome']!='COMPLETE'
    assert publication['outcome']=='STOP'
    assert publication['summary_sha256']==hashlib.sha256((root/'analysis/summary.json').read_bytes()).hexdigest()
    assert (root/'analysis/report.md').is_file()


@pytest.mark.parametrize('fault',['campaign_origin','campaign_bytes','profiles_origin','guard_origin','analyzer_alias'])
def test_actual_imported_host_source_drift_blocks_helper_and_preserves_history(fixture_campaign,monkeypatch,tmp_path,fault):
    module=api(); root,config,add=fixture_campaign; add()
    before=inventory(root.parent)
    def forbidden(*args): raise AssertionError('drift must never invoke semantic helper')
    monkeypatch.setattr(module,'_semantic_evaluation',forbidden)
    from compute_metabolism.v0 import profiles,system_guard
    if fault=='campaign_origin': monkeypatch.setattr(campaign,'__file__',str(tmp_path/'shadow/campaign.py'))
    elif fault=='campaign_bytes':
        host_repo=tmp_path/'host'
        analyzer=host_repo/'compute_metabolism/v0/analyze.py'; analyzer.parent.mkdir(parents=True)
        analyzer.write_bytes(Path(module.__file__).read_bytes())
        shadow=analyzer.parent/'campaign.py'; shadow.write_bytes(Path(campaign.__file__).read_bytes()+b'\n')
        monkeypatch.setattr(module,'__file__',str(analyzer)); monkeypatch.setattr(module.__spec__,'origin',str(analyzer))
        monkeypatch.setattr(campaign,'__file__',str(shadow)); monkeypatch.setattr(campaign.__spec__,'origin',str(shadow))
    elif fault=='profiles_origin': monkeypatch.setattr(profiles,'__file__',str(tmp_path/'shadow/profiles.py'))
    elif fault=='guard_origin': monkeypatch.setattr(system_guard,'__file__',str(tmp_path/'shadow/system_guard.py'))
    elif fault=='analyzer_alias': monkeypatch.setattr(module,'CampaignLimits',lambda:CampaignLimits())
    result=module.analyze_campaign(root)
    assert result['outcome']=='STOP'
    assert result['actual_host_dependencies_before']['status']=='ENVIRONMENT_INVALID'
    assert result['counts']['campaign_attempts']==1
    assert not any(item['analysis_eligible'] or item['performance_eligible'] for item in result['attempts'])
    assert result['profiles']['2c']['outer_wall_seconds']['n']==0
    assert result['attempts'][0]['raw_record']['outcome']=='ACCEPT'
    assert inventory(root.parent)==before


def test_actual_imported_source_drift_during_analysis_revokes_all_eligibility(fixture_campaign,monkeypatch,tmp_path):
    module=api(); root,config,add=fixture_campaign; add()
    from compute_metabolism.v0 import system_guard
    def drifting(root,config,n,receipt):
        report=json.loads((root/'admission.json').read_bytes())
        context=json.loads((root.parent/'execution.json').read_bytes())['admission_report']['classification_context']
        monkeypatch.setattr(system_guard,'__file__',str(tmp_path/'shadow/system_guard.py'))
        return report,context,dict(measurement_role='ADMINISTRATION_ONLY',wall_seconds=.02)
    monkeypatch.setattr(module,'_semantic_evaluation',drifting)
    result=module.analyze_campaign(root)
    assert result['actual_host_dependencies_before']['status']=='VALID'
    assert result['actual_host_dependencies_after']['status']=='ENVIRONMENT_INVALID'
    assert result['outcome']=='STOP' and not result['attempts'][0]['analysis_eligible']
    assert result['profiles']['2c']['outer_wall_seconds']['n']==0


def test_publication_rechecks_actual_imported_source_after_analysis(fixture_campaign,monkeypatch,tmp_path):
    module=api(); fake_semantics(monkeypatch,module)
    root,config,add=fixture_campaign; complete(root,config,add)
    summary=module.analyze_campaign(root)
    assert summary['outcome']=='COMPLETE'
    from compute_metabolism.v0 import system_guard
    monkeypatch.setattr(system_guard,'__file__',str(tmp_path/'shadow/system_guard.py'))
    destination=module._write_analysis(root,summary)
    assert summary['outcome']=='STOP'
    receipt=json.loads((destination/'publication.json').read_bytes())
    assert receipt['outcome']=='STOP' and receipt['source_verified'] is False


def test_same_size_publication_receipt_substitution_is_preserved_and_stops(fixture_campaign,monkeypatch,capsys):
    module=api(); fake_semantics(monkeypatch,module)
    root,config,add=fixture_campaign; complete(root,config,add)
    raw_before=inventory(root.parent)
    original_write=campaign._exclusive_raw
    altered_receipt=[]
    def substitute(path,raw):
        original_write(path,raw)
        if path.name=='publication.json':
            document=json.loads(raw)
            original_hash=document['summary_sha256']
            replacement=('0' if original_hash[0]!='0' else '1')+original_hash[1:]
            altered=raw.replace(original_hash.encode(),replacement.encode(),1)
            assert altered!=raw and len(altered)==len(raw)
            path.chmod(0o600); path.write_bytes(altered); path.chmod(0o444)
            altered_receipt.append(altered)
    monkeypatch.setattr(campaign,'_exclusive_raw',substitute)
    assert module.main(['--campaign-root',str(root)])==2
    status=json.loads(capsys.readouterr().out.strip())
    assert status['outcome']=='STOP'
    destination=root/'analysis'
    assert (destination/'publication.json').read_bytes()==altered_receipt[0]
    stop=json.loads((destination/'publication-stop.json').read_bytes())
    assert stop['outcome']=='STOP' and stop['reason']=='PUBLICATION_INTEGRITY_CHANGED'
    assert stop['publication_sha256']==hashlib.sha256(altered_receipt[0]).hexdigest()
    assert json.loads((destination/'summary.json').read_bytes())['outcome']=='PENDING_PUBLICATION'
    after=inventory(root.parent)
    assert {name:item for name,item in after.items() if not Path(name).is_relative_to(Path(root.name)/'analysis')}==raw_before
    assert status['output_accounting']['output_bytes']==sum(path.stat().st_size for path in destination.iterdir())
    assert status['output_accounting']['projected_upper_bytes']==campaign.logical_tree_bytes(root.parent)


@pytest.mark.parametrize('adaptive',[False,True])
@pytest.mark.parametrize('mutation',['none','missing_epoch','extra','missing_base','epoch_without_saved_epoch'])
def test_epoch_saved_helper_exact_source_inventory(tmp_path,monkeypatch,adaptive,mutation):
    """Only the external helper origin/evaluator boundary is TEST_ONLY mocked."""
    module=api();root=tmp_path/'attempt/v1';root.mkdir(parents=True)
    identity_config={'gate_source_snapshot':{}}
    if adaptive:identity_config['adaptive_version']='COMPUTE_METABOLISM_ADAPTIVE_V1'
    names=set(campaign.identity_names(identity_config))
    if mutation=='missing_epoch':names.remove(campaign._EPOCH_IDENTITY_FILES[0])
    elif mutation=='extra':names.add('compute_metabolism/v0/arbitrary_override.py')
    elif mutation=='missing_base':names.remove(campaign._IDENTITY_FILES[0])
    saved_env={} if mutation=='epoch_without_saved_epoch' else {'source_epoch':{'TEST_ONLY':True}}
    put(root/'campaign-environment.json',saved_env);put(root/'reference.json',{'TEST_ONLY':True})
    tree=inventory(root.parent)
    request=dict(root='/TEST_ONLY/v1',requested_steps=1,
        attempt_tree_sha256=module._tree(root.parent)['sha256'],analysis_source_sha256='b'*64,
        source_sha256={name:'a'*64 for name in names})
    output=io.BytesIO();monkeypatch.setattr(module,'sys',types.SimpleNamespace(
        stdin=types.SimpleNamespace(buffer=io.BytesIO(json.dumps(request).encode())),
        stdout=types.SimpleNamespace(buffer=output)))
    monkeypatch.setattr(module,'__file__','/workspace/compute_metabolism/v0/analyze.py')
    monkeypatch.setattr(campaign,'_helper_root',lambda _:root)
    checked=[];frozen_read=campaign._frozen_read
    def read(path,digest):
        if Path(path).is_relative_to(root):return frozen_read(path,digest)
        checked.append(str(path))
        return b''
    monkeypatch.setattr(campaign,'_frozen_read',read)
    from compute_metabolism.v0 import run_v1
    for name,dependency in [('campaign',campaign),('run_v1',run_v1)]:
        origin=f'/workspace/compute_metabolism/v0/{name}.py'
        monkeypatch.setattr(dependency,'__file__',origin)
        monkeypatch.setattr(dependency.__spec__,'origin',origin)
    calls=[]
    monkeypatch.setattr(run_v1,'evaluate_v1_evidence',lambda *_:calls.append('evaluation') or {'TEST_ONLY':True})
    monkeypatch.setattr(campaign,'_saved_classification_context',lambda _:dict(TEST_ONLY=True))
    if mutation=='none':
        module._evaluation_helper()
        response=json.loads(output.getvalue())
        assert response['raw_preserved'] is True and calls==['evaluation']
        assert set(checked[1:])=={str(Path('/workspace')/name) for name in names}
    else:
        with pytest.raises(ValueError,match='complete helper source binding'):module._evaluation_helper()
        assert calls==[] and output.getvalue()==b''
    assert inventory(root.parent)==tree


@pytest.mark.parametrize('adaptive',[False,True])
@pytest.mark.parametrize('mutation',['none','missing_epoch','extra'])
@pytest.mark.parametrize('cpu_mode',['current','legacy'])
def test_epoch_saved_attempt_exact_host_dependency_inventory(fixture_campaign,monkeypatch,adaptive,mutation,cpu_mode):
    module=api();root,config,add=fixture_campaign
    parent=add(outcome='ENVIRONMENT_INVALID' if cpu_mode=='legacy' else 'ACCEPT')
    config['gate_source_snapshot']={}
    if adaptive:config['adaptive_version']='COMPUTE_METABOLISM_ADAPTIVE_V1'
    repo=Path(config['repo_root'])
    for name in campaign.identity_names(config):
        if name not in config['identities']:
            config['identities'][name]=dict(path=str(repo/name),sha256='a'*64)
    names={'profiles','system_guard','source_epoch','historical_profile','evex_profile','gala_origin_check'}
    if adaptive:names|={'adaptive','profile_verify'}
    if mutation=='missing_epoch':names.remove('source_epoch')
    elif mutation=='extra':
        names.add('arbitrary_override')
        config['identities']['compute_metabolism/v0/arbitrary_override.py']=dict(
            path=str(repo/'compute_metabolism/v0/arbitrary_override.py'),sha256='a'*64)
    modules={name:dict(origin=str(repo/f'compute_metabolism/v0/{name}.py'),
        spec_origin=str(repo/f'compute_metabolism/v0/{name}.py'),
        expected_origin=str(repo/f'compute_metabolism/v0/{name}.py'),
        sha256=config['identities'][f'compute_metabolism/v0/{name}.py']['sha256'],
        expected_sha256=config['identities'][f'compute_metabolism/v0/{name}.py']['sha256']) for name in names}
    execution_path=parent/'execution.json';execution=json.loads(execution_path.read_bytes())
    execution.update(identities_before=copy.deepcopy(config['identities']),
        identities_after={name:item['sha256'] for name,item in config['identities'].items()},
        host_dependencies_before=dict(status='VALID',modules=modules),
        host_dependencies_after=dict(status='VALID',modules=modules))
    if cpu_mode=='legacy':
        execution['classification']=campaign.classify_attempt(execution['admission_report'],
            execution['guard_receipt'],execution['retained_bytes'],preserve_legacy_cpu=True)
    for _ in range(32):
        put(execution_path,execution);retained=campaign.logical_tree_bytes(parent)
        if execution['retained_bytes']==retained:break
        execution['retained_bytes']=retained
    else:raise AssertionError('test receipt size convergence')
    row=copy.deepcopy(campaign.CampaignLedger.read_snapshot(Path(config['ledger_path']))['attempts'][0])
    row.update(execution_sha256=hashlib.sha256(execution_path.read_bytes()).hexdigest(),retained_bytes=retained)
    if cpu_mode=='legacy':
        for key in ('cpu_accounting_version','cpu_measurement_status','cpu_measurement_error'):row.pop(key,None)
        row.update(execution['classification'],cpu_seconds=None)
    fake_semantics(monkeypatch,module);before=inventory(root.parent)
    result=module._attempt(row,config,root,True)
    if mutation=='none':
        if cpu_mode=='current':assert result['analysis_eligible'] is True, result['issues']
        else:
            assert result['analysis_eligible'] is False
            assert any('fault outcome is not admissible' in issue for issue in result['issues'])
            assert result['verified_classification']['wrapper_outcome']=='ENVIRONMENT_INVALID'
        expected_cpu=None if cpu_mode=='legacy' else 5.0
        assert result['verified_classification'].get('cpu_seconds')==expected_cpu
        assert row['cpu_seconds']==expected_cpu
    else:
        assert result['analysis_eligible'] is False
        assert any('complete imported host source evidence' in issue for issue in result['issues'])
    assert inventory(root.parent)==before
