"""New edge only: actual raw acquisition to generic IR and frozen V2."""
from pathlib import Path
from runtime_trace.regular_nstep.producer import block
from verified_driver.v1.model import digest_bytes
from .raw import validate_edge
from .schema import prior_endpoint, edge_document, completion, write

def build_edge(checkpoint_dir,predecessor,out,repo_root):
    out=Path(out); out.mkdir(parents=True,exist_ok=False)
    doc,event,capture,rows,native,identity=validate_edge(checkpoint_dir,predecessor,repo_root)
    prior=prior_endpoint(predecessor); blocks=[]
    regions=capture['regions'][:2] if predecessor.generation==0 else capture['regions'][-1:]
    for region in regions:
        received=block(capture,rows,region,prior,repo_root); blocks.append(received); prior=received['endpoint']
    edge=edge_document(identity,event,blocks,native,doc['metadata'],predecessor)
    write(out/'edge.json',edge)
    finished=completion(edge,digest_bytes((out/'edge.json').read_bytes())); write(out/'completion.json',finished)
    return {'candidate':edge['candidate'],'completion_sha256':finished['completion_sha256']}
