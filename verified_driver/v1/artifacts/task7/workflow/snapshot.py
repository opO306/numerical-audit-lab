"""Pre-Task7 immutable history and exact source baseline, no ledger changes."""
from pathlib import Path
import hashlib,json,os,shutil,subprocess
ROOT=Path(__file__).resolve().parents[5]; HERE=Path(__file__).resolve().parent.parent
files={}
for folder,dirs,names in os.walk(ROOT/'verified_driver/v1/artifacts'):
    dirs[:]=[d for d in dirs if d!='__pycache__']
    for name in names:
        p=Path(folder)/name
        if HERE in p.parents or p.is_symlink() or name=='shared-ledger.lock':continue
        with p.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
        files[p.relative_to(ROOT).as_posix()]={'bytes':p.stat().st_size,'sha256':digest}
with (HERE/'history-before.json').open('x') as f:json.dump({'files':files,'mutable_exclusion':'workflow/shared-ledger.lock'},f,sort_keys=True,indent=2)
baseline={}
for p in (ROOT/'verified_driver/v1').rglob('*.py'):
    if 'artifacts' in p.relative_to(ROOT/'verified_driver/v1').parts or '__pycache__' in p.parts:continue
    baseline[p.relative_to(ROOT).as_posix()]=hashlib.sha256(p.read_bytes()).hexdigest()
with (HERE/'source-before.json').open('x') as f:json.dump(baseline,f,sort_keys=True,indent=2)
shutil.copyfile(ROOT/'current/VERIFIED_DRIVER_V1_2026-10-06.md',HERE/'pre-task7-status.md')
ledger=json.loads((ROOT/'runtime_trace/regular_nstep/artifacts/budget.json').read_bytes())
assert ledger['used_seconds']==3353.251577895021
with (HERE/'preflight.json').open('x') as f:json.dump({'used_seconds':ledger['used_seconds'],'remaining_seconds':3600-ledger['used_seconds'],
 'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'history_files':len(files),'v1_python_files':len(baseline)},f,sort_keys=True,indent=2)
print(json.dumps({'history_files':len(files),'source_files':len(baseline),'used_seconds':ledger['used_seconds']}))
