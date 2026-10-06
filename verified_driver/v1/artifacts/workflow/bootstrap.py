"""Metadata only: protected inventory and this plan's normalized skill scripts."""
from pathlib import Path
import hashlib, json, os, stat, subprocess
ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
def sha(p):
    with p.open('rb') as f: return hashlib.file_digest(f, 'sha256').hexdigest()
out=HERE.parent/'preservation'; out.mkdir(exist_ok=True)
excluded={'runtime_trace/regular_nstep/artifacts/budget.json','runtime_trace/regular_nstep/artifacts/budget.running.json'}
files={}
for base in ('runtime_trace','verified_driver/v0','lab','independent_checker','audit/gate2c1/vendor'):
    for p in (ROOT/base).rglob('*'):
        info=p.lstat()
        if '__pycache__' in p.parts or getattr(info,'st_file_attributes',0)&0x400: continue
        if stat.S_ISREG(info.st_mode) and p.relative_to(ROOT).as_posix() not in excluded:
            files[str(p)]={'bytes':info.st_size,'sha256':sha(p)}
previous=json.loads((ROOT/'verified_driver/v0/artifacts/preservation/before.json').read_bytes())
for name in previous['files']:
    p=Path(name)
    if p.is_file() and p.relative_to(ROOT).as_posix() not in excluded if p.is_relative_to(ROOT) else p.is_file():
        files[str(p)]={'bytes':p.stat().st_size,'sha256':sha(p)}
payload={'schema':'V1_PROTECTED_BASELINE','files':files,'mutable_exclusions':sorted(excluded),
 'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
 'status':subprocess.check_output(['git','status','--short'],cwd=ROOT,text=True)}
if not (out/'before.json').exists():
    with (out/'before.json').open('x') as f: json.dump(payload,f,sort_keys=True,indent=2)
skills=Path('C:/Users/zun24/.codex/plugins/cache/openai-curated-remote/superpowers/6.4.2/skills')
for family in ('executing-plans','subagent-driven-development'):
    for p in (skills/family/'scripts').glob('*'):
        if not p.is_file(): continue
        target=HERE/'skills'/family/'scripts'/p.name; target.parent.mkdir(parents=True,exist_ok=True)
        data=p.read_text(encoding='utf-8')
        if target.exists() and target.stat().st_size:
            assert target.read_text(encoding='utf-8')==data
        else:
            with target.open('w',encoding='utf-8',newline='\n') as f: f.write(data)
print(json.dumps({'protected_files':len(files),'baseline':str(out/'before.json')}))
