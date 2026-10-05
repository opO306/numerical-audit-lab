from .wire import digest


def bind(obj, spec):
    state,acq=obj['state'],obj['acquisition']
    roles={'i':state['atoms'][0]['atom_id'],'j':state['atoms'][1]['atom_id']}
    projection={'spec_sha256':spec.sha256,'constants_sha256':spec.hashes['constants.json'],
        'domain_sha256':spec.hashes['physical-domain.json'],'atom_roles':roles,
        'position_raw':[a['position_raw'] for a in state['atoms']],
        'species':[a['species'] for a in state['atoms']], 'position_grid':state['position_grid'],
        'full_dt':{'n':'40','d':'1'},'kick_fraction':{'n':'1','d':'2'}}
    full=digest(state,'LAB_C1B1_FULL_STATE_V1')
    proj=digest(projection,'LAB_C1B1_IMPULSE_PROJECTION_V1')
    acquired=digest({'state':state,'acquisition':acq},'LAB_C1B1_ACQUISITION_RECORD_V1')
    occurrence={k:acq[k] for k in ['record_id','acquisition_id','phase','full_half',
        'executor_source_sha256','acquisition_tool_sha256','previous_occurrence_sha256']}
    occurrence.update(acquisition_record_sha256=acquired,full_state_sha256=full,
                      projection_sha256=proj,atom_roles=roles,axis_order=['x','y','z'])
    math={'projection_sha256':proj,'methods':dict(spec.identity['payload_schemas']['methods']),
          'axis_order':['x','y','z']}
    return {'input_sha256':digest(obj),'full_state_sha256':full,'projection_sha256':proj,
        'math_request_sha256':digest(math,'LAB_C1B1_MATH_REQUEST_V1'),
        'occurrence_sha256':digest(occurrence,'LAB_C1B1_OCCURRENCE_V1'),
        'acquisition_record_sha256':acquired,'budget_sha256':digest(obj['budget'],'LAB_C1B1_BUDGET_V1')}
