"""Finite actual-call orchestration remains isolated from certified state."""
import copy,importlib
import pytest

def test_observation_environment_preserves_history_and_binds_new_epoch():
    api=importlib.import_module('compute_metabolism.v0.gala_observation_run')
    prior=dict(schema='COMPUTE_METABOLISM_ENVIRONMENT_V0',instance_id='123',boot_id='boot',
        topology={'0':{}},platform='live',execution_profile={'old':'binding'},execution_registry_sha256='a'*64)
    original=copy.deepcopy(prior);epoch={'source_binding':'b'*64}
    result=api.observation_environment(prior,epoch)
    assert prior==original and result=={k:v for k,v in prior.items() if k not in ('execution_profile','execution_registry_sha256')}|{'source_epoch':epoch}
    assert result['source_epoch'] is not epoch

@pytest.mark.parametrize('attack',['missing_measurement','diagnostic','not_normal','source'])
def test_actual_gala_observation_cannot_pass_on_exit_code_alone(tmp_path,attack):
    api=importlib.import_module('compute_metabolism.v0.gala_observation_run')
    receipt=dict(outcome='GUARD_COMPLETE',measurement_valid=True)
    match=True
    if attack=='missing_measurement':receipt['measurement_valid']=False
    elif attack=='diagnostic':(tmp_path/'diagnostic.json').write_bytes(b'{}')
    elif attack=='not_normal':receipt['outcome']='UNRESOLVED_FAILURE'
    elif attack=='source':match=False
    outcome,status=api.observation_status(receipt,tmp_path,match)
    assert status=='OBSERVATION_FAILED' and outcome!='GUARD_COMPLETE'
