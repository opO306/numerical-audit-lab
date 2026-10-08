"""Observation authority is separate from numerical campaign resumption."""
import copy,importlib,json
from pathlib import Path
import pytest
from tests.test_compute_metabolism_v0_campaign import cli_config,api

def module():
    assert importlib.util.find_spec('compute_metabolism.v0.observation_run') is not None
    return importlib.import_module('compute_metabolism.v0.observation_run')

def test_observation_requires_durable_stop_before_new_running(api,tmp_path,monkeypatch):
    m=module();path,sha,config=cli_config(tmp_path,monkeypatch)
    files={n:Path(x['path']).read_bytes() for g in ('inputs','identities') for n,x in config[g].items()}
    api.initialize_campaign(config,path.read_bytes(),files)
    ledger=api.CampaignLedger.open(Path(config['ledger_path']),api.CampaignLimits())
    before=ledger.path.read_bytes()
    with pytest.raises(ValueError,match='STOP'):
        m._begin_observation(ledger,'observation-01','a'*64)
    assert ledger.path.read_bytes()==before

def test_observation_begin_preserves_cost_and_cannot_recover_running(api,tmp_path,monkeypatch):
    m=module();path,sha,config=cli_config(tmp_path,monkeypatch)
    files={n:Path(x['path']).read_bytes() for g in ('inputs','identities') for n,x in config[g].items()}
    api.initialize_campaign(config,path.read_bytes(),files)
    ledger=api.CampaignLedger.open(Path(config['ledger_path']),api.CampaignLimits())
    ledger.begin_attempt(config['campaign_id'],'old','2c','warm-up',0)
    ledger.finish_attempt('old',8.891162582000106,None,0,0,'UNRESOLVED_FAILURE')
    api._finalize_upper(ledger,config,'old',False,'POST_FINISH')
    old=api.CampaignLedger.read_snapshot(ledger.path)
    m._begin_observation(ledger,'observation-01','a'*64)
    new=api.CampaignLedger.read_snapshot(ledger.path)
    assert new['attempts'][0]==old['attempts'][0] and new['total_wall_seconds']==old['total_wall_seconds']
    assert new['attempts'][-1]['kind']=='OBSERVATION' and new['attempts'][-1]['certified_state_progress'] is False
    assert new['formal_campaign']==old['formal_campaign'] and new['limits']==old['limits']
    with pytest.raises(api.UnresolvedPriorAttempt):m._begin_observation(ledger,'observation-02','b'*64)
    ledger.finish_attempt('observation-01',2,1,0,0,'GUARD_COMPLETE')
    assert api.CampaignLedger.read_snapshot(ledger.path)['total_wall_seconds']==old['total_wall_seconds']+2
    assert api.CampaignLedger.read_snapshot(ledger.path)['attempts'][0]['cpu_seconds'] is None

def test_observation_cannot_overwrite_namespace_or_invoke_arbitrary_command(api,tmp_path,monkeypatch):
    m=module()
    assert not hasattr(m,'arbitrary_command')
    with pytest.raises(ValueError):m.run_observation(Path('/unapproved'), 'observation-01',{})

@pytest.mark.parametrize('fault',['guard','after','before','source','terminal','measurement'])
def test_cpu_cost_and_candidate_presence_cannot_hide_observation_failure(tmp_path,fault):
    m=module();out=tmp_path/'observation';(out/'candidate').mkdir(parents=True)
    (out/'candidate/candidate-profile.json').write_text('{}')
    (out/'observation.raw.json').write_text(json.dumps(dict(terminal=dict(status='OBSERVED_RETURN'))))
    receipt=dict(outcome='GUARD_COMPLETE',measurement_valid=True)
    assert hasattr(m,'_observation_status')
    if fault=='guard':receipt['outcome']='UNRESOLVED_FAILURE'
    elif fault=='after':(out/'after-diagnostic.json').write_text('{}')
    elif fault=='before':(out/'diagnostic.json').write_text('{}')
    elif fault=='terminal':(out/'observation.raw.json').write_text(json.dumps(dict(terminal=dict(status='STOP_ERROR'))))
    elif fault=='measurement':receipt['measurement_valid']=False
    outcome,status=m._observation_status(receipt,out,fault!='source')
    assert outcome!='GUARD_COMPLETE' and status=='OBSERVATION_FAILED'

@pytest.mark.parametrize('outcome',['ENVIRONMENT_INVALID','REFUSED_VERIFICATION','UNRESOLVED_FAILURE'])
def test_observation_cost_or_cap_does_not_replace_existing_failure(outcome):
    m=module();assert hasattr(m,'_final_status')
    assert m._final_status(outcome,'OBSERVATION_FAILED',False,100663297)==(outcome,'OBSERVATION_FAILED')

def test_observation_record_and_accounting_use_final_retained_outcome(tmp_path):
    m=module();assert hasattr(m,'_execution_payload')
    from compute_metabolism.v0.profiles import CampaignLimits
    record=dict(wrapper_outcome='GUARD_COMPLETE',observation_outcome='OBSERVED_UNCERTIFIED',cpu_accounting=dict(cpu_seconds=1))
    payload,retained=m._execution_payload(record,tmp_path)
    saved=json.loads(payload)
    assert saved['retained_bytes']==retained==len(payload)
    assert saved['wrapper_outcome']==record['wrapper_outcome']=='GUARD_COMPLETE'
