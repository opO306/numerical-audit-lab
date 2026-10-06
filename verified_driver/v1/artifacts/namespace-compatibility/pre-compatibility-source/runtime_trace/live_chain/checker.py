"""Independent IR graph and rational Form reconstruction for the new edge."""
from pathlib import Path
from runtime_trace.regular_2step import checker as audited
from runtime_trace.regular_2step.schema import namespaced, canonical, load
from runtime_trace.regular_nstep.schema import boundary
from verified_driver.v1.model import digest_bytes, content_id
from .raw import validate_edge
from .schema import prior_endpoint, edge_document, completion, write

def check_edge(checkpoint_dir,derived_dir,predecessor,repo_root,report=None):
    stage='RAW'
    try:
        doc,event,capture,rows,native,identity=validate_edge(checkpoint_dir,predecessor,repo_root)
        out=Path(derived_dir); received=load(out/'edge.json'); supplied=load(out/'completion.json')
        stage='HASH'; want_hash=digest_bytes((out/'edge.json').read_bytes())
        if supplied['edge_sha256']!=want_hash or supplied['completion_sha256']!=content_id({k:v for k,v in supplied.items() if k!='completion_sha256'}): raise ValueError('edge/completion integrity')
        stage='SEMANTIC'; prior=prior_endpoint(predecessor); blocks=[]
        regions=capture['regions'][:2] if predecessor.generation==0 else capture['regions'][-1:]
        for region in regions:
            namespace=capture['acquisition_id']+'/'+region['occurrence']
            view=[None]*region['start_seq']+rows[region['start_seq']:region['end_seq']]
            ops,values,state=audited.graph(capture,view,[region],Path(repo_root))
            ir={'schema':'regular-nstep-body-ir-v1','namespace':namespace,'acquisition_id':capture['acquisition_id'],
              'region':region,'operations':namespaced(ops,namespace),'values':namespaced(values,namespace)}
            link=boundary(capture,region,prior)
            lanes=audited.final_lanes({**capture,'regions':[None,None,region]},values,state,namespace)
            lanes=[{**e,'occurrence':region['occurrence']} for e in lanes]
            v2,endpoint=audited.expected_forms(ir,link,lanes,Path(repo_root))
            blocks.append({'ir':ir,'boundary':link,'v2':v2,'endpoint':endpoint}); prior=endpoint
        expected=edge_document(identity,event,blocks,native,doc['metadata'],predecessor)
        if canonical(expected)!=canonical(received): raise ValueError('independent exact new-edge IR/Form/continuation/native correspondence')
        finished=completion(expected,want_hash)
        if canonical(finished)!=canonical(supplied): raise ValueError('honest edge completion/frontier/scope')
        result={'schema':'LIVE_EDGE_CHECK_V1','verdict':'CHECKER_PASS','candidate':expected['candidate'],
          'checkpoint_id':identity,'completion_sha256':finished['completion_sha256'],
          'requested_complete':finished['requested_complete'],'checked_step':event.completed_step,
          'evidence_role':doc['metadata'].get('evidence_role','LIVE'),'formal_certification':False,
          'init_to_step1':'UNTRACED','post_terminal_frontier':'UNTRACED'}
    except Exception as exc:
        result={'schema':'LIVE_EDGE_CHECK_V1','verdict':'REFUSED','failure_stage':stage,
          'requested_complete':False,'reason':str(exc)}
    if report is not None: write(report,result)
    return result
