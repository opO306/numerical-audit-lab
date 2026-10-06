"""Actual Git status/diff and explicit untracked-source review package; no index writes."""
from pathlib import Path
import hashlib
import json
import subprocess
ROOT=Path(__file__).resolve().parents[4]
OUT=ROOT/'verified_driver/v0/artifacts/review'
OUT.mkdir(exist_ok=True)
files=sorted([*(ROOT/'verified_driver').glob('*.py'),*(ROOT/'verified_driver/v0').glob('*.py'),
    *(ROOT/'tests').glob('test_verified_driver_v0_*.py'),ROOT/'tests/verified_driver_v0_support.py'])
report=ROOT/'current/VERIFIED_DRIVER_V0_2026-10-05.md'
if report.exists(): files.append(report)
def git(*args): return subprocess.check_output(['git',*args],cwd=ROOT,text=True,encoding='utf-8')
(OUT/'git-status.txt').write_text(git('status','--short'),encoding='utf-8')
(OUT/'git-diff.patch').write_text(git('diff','--no-ext-diff'),encoding='utf-8')
patch=[]; inventory={}
for p in files:
    raw=p.read_bytes(); relative=str(p.relative_to(ROOT)).replace('\\','/')
    inventory[relative]={'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw),'lines':len(raw.splitlines())}
    result=subprocess.run(['git','diff','--no-index','--','NUL',str(p)],cwd=ROOT,text=True,encoding='utf-8',capture_output=True)
    if result.returncode not in (0,1): raise RuntimeError(result.stderr)
    patch.append(result.stdout)
(OUT/'untracked-source-git-diff.patch').write_text(''.join(patch),encoding='utf-8')
payload={'head':git('rev-parse','HEAD').strip(),'tracked_diff_bytes':len((OUT/'git-diff.patch').read_bytes()),
    'tracked_status':git('status','--porcelain','--untracked-files=no'),'new_driver_review_files':inventory,
    'note':'BASE==HEAD because commit/push forbidden. RT N-step prior uncommitted assets remain prior input, not this Driver diff.'}
(OUT/'source-inventory.json').write_text(json.dumps(payload,sort_keys=True,indent=2)+'\n')
(OUT/'package.md').write_text('# Verified Driver V0 review package\n\n'+
    'Managed root: '+str(ROOT)+'\n\nBase and Head: '+payload['head']+'\n\n'+
    'Review all listed new untracked Driver sources/tests; ordinary tracked diff is empty. Use the actual no-index Git patch and source inventory.\n\n'+
    '\n'.join('- '+str(p) for p in files)+'\n\n'+
    'Spec/plan: docs/superpowers/specs/2026-10-05-verified-driver-v0-design.md; docs/superpowers/plans/2026-10-05-verified-driver-v0.md.\n'+
    'Final fresh evidence: verified_driver/v0/artifacts/authority-03/. Full selected regression: final-review-green-junit.xml (119 pass). Preservation: artifacts/preservation/after-final.json (6892 unchanged).\n'+
    'Ledger rulings: .superpowers/sdd/2026-10-05-verified-driver-v0/progress.md.\n',encoding='utf-8')
print(json.dumps({'files':len(files),'new_lines':sum(v['lines'] for v in inventory.values()),'tracked_diff_bytes':payload['tracked_diff_bytes'],'package':str(OUT/'package.md')}))
