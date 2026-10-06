"""Metadata-only before/after byte preservation, excluding approved mutable ledger."""
from pathlib import Path
import hashlib
import json
import stat
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[4]
ORIGINAL=Path('D:/numerical-audit-lab-recovered-2026-10-01')
OUT=ROOT/'verified_driver/v0/artifacts/preservation'
OUT.mkdir(exist_ok=True)
def sha(p):
    with p.open('rb') as f: return hashlib.file_digest(f,'sha256').hexdigest()
def record(p): return {'bytes':p.stat().st_size,'sha256':sha(p)}
excluded={ROOT/'runtime_trace/regular_nstep/artifacts/budget.json',ROOT/'runtime_trace/regular_nstep/artifacts/budget.running.json'}
if sys.argv[1]=='before':
    files={}
    for path in (ROOT/'runtime_trace').rglob('*'):
        info=path.lstat()
        if path in excluded or '__pycache__' in path.parts or getattr(info,'st_file_attributes',0)&0x400: continue
        if stat.S_ISREG(info.st_mode): files[str(path)]=record(path)
    base=json.loads((ORIGINAL/'current/runtime-nstep-preflight-2026-10-05/baseline.json').read_bytes())
    for e in base['protected_files']+base['other_work_files']:
        path=ORIGINAL/e['path']; files[str(path)]=record(path)
    for path in [ROOT/'lab/v2_bound.py',ROOT/'docs/superpowers/specs/2026-10-05-verified-driver-v0-design.md',ROOT/'docs/superpowers/plans/2026-10-05-verified-driver-v0.md']:
        files[str(path)]=record(path)
    payload={'schema':'driver-v0-protected-baseline-v1','files':files,'mutable_exclusions':[str(p) for p in excluded],
        'git':{str(p):{'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=p,text=True).strip(),
            'status':subprocess.check_output(['git','status','--short'],cwd=p,text=True)} for p in [ROOT,ORIGINAL]}}
    destination=OUT/'before.json'
else:
    baseline=json.loads((OUT/'before.json').read_bytes())
    changed=[name for name,r in baseline['files'].items() if not Path(name).is_file() or record(Path(name))!=r]
    payload={'schema':'driver-v0-protected-preservation-v1','checked_files':len(baseline['files']),'changed_or_missing':changed,
        'baseline_sha256':sha(OUT/'before.json'),'mutable_exclusions':baseline['mutable_exclusions']}
    destination=OUT/('after'+('-'+sys.argv[2] if len(sys.argv)>2 else '')+'.json')
with destination.open('x',encoding='utf-8') as f: json.dump(payload,f,sort_keys=True,indent=2); f.write('\n')
print(json.dumps({'path':str(destination),'files':len(payload.get('files',{})),'changed_or_missing':payload.get('changed_or_missing')}))
if payload.get('changed_or_missing'): raise SystemExit(2)
