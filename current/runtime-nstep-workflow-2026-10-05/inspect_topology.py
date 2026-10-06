import json
from pathlib import Path
from runtime_trace.regular_2step import checker as c
from runtime_trace.regular_2step.schema import load
r=Path('.')
p=r/'runtime_trace/regular_nstep/artifacts/native10-02/capture';o=r/'runtime_trace/regular_2step/artifacts/known-03'
a,b=load(p/'capture.json'),load(o/'capture.json')
x=[json.loads(z) for z in (p/'trace.jsonl').read_bytes().splitlines()];y=[json.loads(z) for z in (o/'trace.jsonl').read_bytes().splitlines()]
for i in (0,1):
 ar,br=a['regions'][i],b['regions'][i]
 aa=c.prefix_structure(x[ar['start_seq']:ar['end_seq']],ar,a['modules']);bb=c.prefix_structure(y[br['start_seq']:br['end_seq']],br,b['modules'])
 for key in aa:
  differences=[(j,v,bb[key][j]) for j,v in enumerate(aa[key]) if v!=bb[key][j]]
  print(i,key,len(differences),str(differences[:5])[:5000])
