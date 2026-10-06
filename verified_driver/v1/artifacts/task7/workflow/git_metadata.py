"""Final Git/status submission, read-only Git operations only."""
from pathlib import Path
import difflib,json,subprocess
ROOT=Path(__file__).resolve().parents[5]; HERE=Path(__file__).resolve().parent.parent
def git(*args):return subprocess.run(['git','-C',str(ROOT),*args],capture_output=True)
outputs={}
for name,args in [('git-status.txt',('status','--short')),('git-tracked-stat.txt',('diff','--stat')),
                  ('git-staged.txt',('diff','--cached','--name-only')),('git-diff-check.txt',('diff','--check')),
                  ('git-new-attack-diff-check.txt',('diff','--no-index','--check','--','NUL','tests/test_verified_driver_v1_attacks.py'))]:
    result=git(*args)
    if (HERE/name).exists():assert (HERE/name).read_bytes()==result.stdout+result.stderr
    else:
        with (HERE/name).open('xb') as stream:stream.write(result.stdout+result.stderr)
    outputs[name]={'return_code':result.returncode,'bytes':len(result.stdout+result.stderr)}
assert outputs['git-diff-check.txt']=={'return_code':0,'bytes':0}
assert outputs['git-new-attack-diff-check.txt']=={'return_code':1,'bytes':0}
assert outputs['git-staged.txt']['bytes']==0
meta={'head':git('rev-parse','HEAD').stdout.decode().strip(),
      'branch':git('branch','--show-current').stdout.decode().strip(),
      'operations':outputs,'staging_commit_push_performed':False,'task7_product_source_changed':False,
      'preexisting_tracked_design_edit':'docs/superpowers/specs/2026-10-06-verified-driver-v1-certified-chain-design.md',
      'mutable_ledger_files':['runtime_trace/regular_nstep/artifacts/budget.json','runtime_trace/regular_nstep/artifacts/budget.running.json']}
assert meta['head']=='fbbb90171c43ed5462e9584c2621cb0b86b80bd4'
with (HERE/'git-verification.json').open('x',encoding='utf-8',newline='\n') as stream:json.dump(meta,stream,sort_keys=True,indent=2);stream.write('\n')
test=ROOT/'tests/test_verified_driver_v1_attacks.py'
patch=''.join(difflib.unified_diff([],test.read_text().splitlines(keepends=True),fromfile='/dev/null',tofile='b/tests/test_verified_driver_v1_attacks.py'))
before=(HERE/'pre-task7-status.md').read_text(encoding='utf-8').splitlines(keepends=True)
after=(ROOT/'current/VERIFIED_DRIVER_V1_2026-10-06.md').read_text(encoding='utf-8').splitlines(keepends=True)
patch+=''.join(difflib.unified_diff(before,after,fromfile='a/current/VERIFIED_DRIVER_V1_2026-10-06.md',tofile='b/current/VERIFIED_DRIVER_V1_2026-10-06.md'))
with (HERE/'task7-only-review.diff').open('x',encoding='utf-8',newline='\n') as stream:stream.write(patch)
with (HERE/'git-submission.md').open('x',encoding='utf-8',newline='\n') as stream:
    stream.write('# Task 7 Git verification\n\nHEAD and branch unchanged. Tracked git diff --check exits 0 with no output. The new untracked attack file no-index check exits 1 because differences exist against NUL, with no whitespace diagnostics (0 output bytes). Index is empty. No staging/commit/push. Tracked edits are the preexisting design edit plus the same two authorized shared ledger files; all V1 product source bytes are unchanged in Task 7.\n\nTask7-only-review.diff shows the new attack file and current status update. Other Task7 additions are exclusive workflow/report/RED/GREEN receipts under task7/ and its three guarded jobs, plus the additive progress log and preservation/task7-final.json.\n')
print(json.dumps(meta))
