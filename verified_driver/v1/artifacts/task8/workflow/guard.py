"""Task8-only outer guard: user-approved4200, unchanged protected primitives."""
from pathlib import Path
import argparse,fcntl,hashlib,json,subprocess,sys
ROOT=Path(__file__).resolve().parents[5];HERE=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from runtime_trace.regular_nstep import resources
CAPS={'ordinary':10,'positive':55,'negative':60,'nonterminal':45,'terminal':55,
      'paused-death':15,'active-death':15,'interruption':25,'regression':120,'review-test':120}
p=argparse.ArgumentParser();p.add_argument('--authorize',action='store_true');p.add_argument('--stage');p.add_argument('--name');p.add_argument('--allowance',type=int,default=536870912)
a,cmd=p.parse_known_args()
ledger=ROOT/'runtime_trace/regular_nstep/artifacts/budget.json'
with (ROOT/'verified_driver/v1/artifacts/workflow/shared-ledger.lock').open('a+b') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX)
    prior=json.loads(ledger.read_bytes())
    if a.authorize:
        snapshot=json.loads((HERE/'pre-ceiling-budget.snapshot.json').read_bytes())
        assert prior==snapshot and prior['used_seconds']==3472.7506255470207
        assert json.loads(ledger.with_suffix('.running.json').read_bytes())['state']=='FINISHED'
        prior['approved_total_seconds']=4200
        prior['ceiling_authorizations']=[{'previous_ceiling':3600,'approved_ceiling':4200,
          'used_seconds_at_authorization':prior['used_seconds'],'scope':'Task8 existing plan only; unchanged job caps; surplus only necessary failed/review reruns',
          'basis':'Direct designer instruction in current conversation; no reset/replacement/new ledger'}]
        assert prior['jobs']==snapshot['jobs']
        with ledger.open('w') as f:json.dump(prior,f,sort_keys=True);f.write('\n')
        with (HERE/'ceiling-amendment.json').open('x') as f:json.dump({'existing_ledger':str(ledger),'old_ceiling':3600,'new_ceiling':4200,'used_seconds_unchanged':prior['used_seconds'],'jobs_unchanged':True,'jobs_count':len(prior['jobs']),'pre_amendment_snapshot_sha256':hashlib.sha256((HERE/'pre-ceiling-budget.snapshot.json').read_bytes()).hexdigest()},f,sort_keys=True,indent=2)
        print({'used_seconds':prior['used_seconds'],'ceiling':4200});raise SystemExit(0)
    assert prior['approved_total_seconds']==4200 and a.stage in CAPS and a.name
    if cmd and cmd[0]=='--':cmd.pop(0)
    if cmd and cmd[0]=='PY':cmd[0]=sys.executable
    class ApprovedTask8Limits:
        total_seconds=4200;job_seconds=CAPS[a.stage];memory_bytes=4294967296;storage_bytes=8589934592
    scan=json.loads(subprocess.check_output(['/mnt/c/Users/zun24/AppData/Local/Programs/Python/Python312/python.exe','C:/Users/zun24/.codex/worktrees/runtime-nstep/numerical-audit-lab-recovered-2026-10-01/verified_driver/v1/artifacts/workflow/storage.py']))
    class ScannedBudget(resources.EvidenceBudget):
        def __init__(self,root,maximum):self.root=Path(root).resolve();self.maximum=maximum;self.used=scan['actual_storage_bytes']
    resources.EvidenceBudget=ScannedBudget
    result=resources.run_guarded(cmd,ApprovedTask8Limits(),ROOT/'verified_driver/v1/artifacts/jobs'/a.name,ledger,
       cwd='/home/otherside123/verified-driver-v1-test-mirror-2026-10-06',artifact_allowance=a.allowance,
       env={'GIT_DIR':'/mnt/d/numerical-audit-lab-recovered-2026-10-01/.git/worktrees/numerical-audit-lab-recovered-2026-10-01','GIT_WORK_TREE':str(ROOT)})
    with (ROOT/'verified_driver/v1/artifacts/jobs'/a.name/'task8-authorization.json').open('x') as f:json.dump({'stage':a.stage,'job_cap':CAPS[a.stage],'total_ceiling':4200,'storage':scan},f,sort_keys=True)
    print(result);raise SystemExit(result['return_code'] if result['return_code'] is not None else 2)
