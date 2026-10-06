"""Exact Git readout plus unstaged source diff; never touches the index."""
from pathlib import Path
import difflib, hashlib, json, subprocess
ROOT=Path(__file__).resolve().parents[4]
out=ROOT/'verified_driver/v1/artifacts/task5-git'; out.mkdir(exist_ok=False)
def git(*args): return subprocess.check_output(['git','-C',str(ROOT),*args])
for name,args in [('status.txt',('status','--short')),('tracked.diff',('diff','--binary')),('tracked-stat.txt',('diff','--stat')),
                  ('staged.diff',('diff','--cached')),('head.txt',('rev-parse','HEAD'))]:
    (out/name).write_bytes(git(*args))
files=sorted(list((ROOT/'runtime_trace/live_chain').glob('*.py'))+list((ROOT/'verified_driver/v1').glob('*.py'))+
  list((ROOT/'tests').glob('*live_chain*.py'))+list((ROOT/'tests').glob('*verified_driver_v1*.py'))+
  [ROOT/'current/VERIFIED_DRIVER_V1_2026-10-06.md'])
patch=[]; inventory={}
for p in files:
    relative=p.relative_to(ROOT).as_posix(); raw=p.read_bytes(); inventory[relative]=hashlib.sha256(raw).hexdigest()
    patch.append('diff --git a/'+relative+' b/'+relative+'\nnew file mode 100644\n')
    patch.extend(difflib.unified_diff([],raw.decode('utf-8').splitlines(keepends=True),fromfile='/dev/null',tofile='b/'+relative))
(out/'untracked-source.diff').write_text(''.join(patch),encoding='utf-8',newline='\n')
(out/'source-sha256.json').write_text(json.dumps(inventory,sort_keys=True,indent=2)+'\n',encoding='utf-8')
check=subprocess.run(['git','-C',str(ROOT),'diff','--check'],capture_output=True)
(out/'diff-check.txt').write_bytes(check.stdout+check.stderr)
print(json.dumps({'files':len(files),'git_diff_check':check.returncode,'staged_diff_bytes':(out/'staged.diff').stat().st_size,'directory':str(out)}))
