"""Diagnose protected V0 pinset conflict without changing either contract."""
from pathlib import Path
import hashlib, json, os
ROOT=Path(__file__).resolve().parents[4]
pins_path=ROOT/'runtime_trace/regular_nstep/artifacts/connected10-final2/integration_source_pinset.json'
pins=json.loads(pins_path.read_bytes()); actual={}
for base,dirs,files in os.walk(ROOT/'runtime_trace'):
    dirs[:]=[d for d in dirs if d not in ('artifacts','__pycache__')]
    for name in files:
        if name.endswith('.py'):
            p=Path(base)/name; actual[p.relative_to(ROOT).as_posix()]=hashlib.sha256(p.read_bytes()).hexdigest()
for relative in ('lab/v2_bound.py','independent_checker/oracle.py'):
    actual[relative]=hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()
result={'schema':'V1_V0_PINSET_CONFLICT','approved_pinset_sha256':hashlib.sha256(pins_path.read_bytes()).hexdigest(),
 'approved_count':len(pins),'current_count':len(actual),'added':sorted(set(actual)-set(pins)),
 'removed':sorted(set(pins)-set(actual)),'changed_protected':sorted(k for k in pins.keys()&actual.keys() if pins[k]!=actual[k]),
 'combined_regression':{'passed':173,'failed':10,'receipt':'verified_driver/v1/artifacts/jobs/task5-done/execution.json'},
 'status':'DESIGNER_DECISION_REQUIRED; no V0 gate/pinset changes'}
out=ROOT/'verified_driver/v1/artifacts/task5-compatibility-conflict.json'
with out.open('x',encoding='utf-8') as f: json.dump(result,f,sort_keys=True,indent=2); f.write('\n')
print(json.dumps(result))
