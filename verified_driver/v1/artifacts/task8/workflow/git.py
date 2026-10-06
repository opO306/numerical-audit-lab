"""Exact read-only Git submission, with no index/worktree mutation."""
from pathlib import Path
import json,subprocess
ROOT=Path(__file__).resolve().parents[5];HERE=Path(__file__).resolve().parent.parent
def run(args):
    p=subprocess.run(['git',*args],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    return {'args':args,'exit_code':p.returncode,'stdout':p.stdout.decode('utf-8',errors='replace'),'stderr':p.stderr.decode('utf-8',errors='replace')}
head=run(['rev-parse','HEAD']);branch=run(['branch','--show-current']);check=run(['diff','--check']);index=run(['diff','--cached','--name-only'])
assert head['stdout'].strip()=='fbbb90171c43ed5462e9584c2621cb0b86b80bd4' and branch['stdout'].strip()=='codex/runtime-trace'
assert check['exit_code']==0 and index['exit_code']==0 and not index['stdout'].strip()
names=['verified_driver/v1/controller.py','verified_driver/v1/replay.py','verified_driver/v1/containment.py','verified_driver/v1/live_chain/supervisor.py','tests/test_verified_driver_v1_review.py']
untracked=[run(['diff','--no-index','--check','NUL',n]) for n in names]
assert all(r['exit_code'] in (0,1) and not r['stdout'] and not r['stderr'] for r in untracked)
status=run(['status','--short','--untracked-files=all']);assert status['exit_code']==0
with (HERE/'git-status.txt').open('x',encoding='utf-8',newline='\n') as f:f.write(status['stdout'])
with (HERE/'git-verification.json').open('x',encoding='utf-8',newline='\n') as f:json.dump({'head':head,'branch':branch,'diff_check':check,'index':index,'untracked_whitespace_checks':untracked,'status':status,'staging_commit_push_performed':False},f,sort_keys=True,indent=2);f.write('\n')
print(json.dumps({'HEAD':head['stdout'].strip(),'branch':branch['stdout'].strip(),'index_empty':True,'diff_check_exit':check['exit_code'],'untracked_whitespace_diagnostics':0,'status_lines':len(status['stdout'].splitlines())}))
