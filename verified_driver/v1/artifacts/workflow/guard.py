"""Tests charge only the existing shared ledger, with Linux tree limits."""
from pathlib import Path
import argparse, fcntl, json, subprocess, sys
ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT))
from runtime_trace.regular_nstep import resources
from runtime_trace.regular_nstep.resources import Limits, run_guarded
p=argparse.ArgumentParser(); p.add_argument('--name',required=True); p.add_argument('--seconds',type=int,default=60)
p.add_argument('--allowance',type=int,default=67108864); p.add_argument('--managed',action='store_true')
a,cmd=p.parse_known_args()
if cmd and cmd[0]=='--': cmd.pop(0)
if cmd and cmd[0]=='PY': cmd[0]=sys.executable
cwd=ROOT if a.managed else Path('/home/otherside123/verified-driver-v1-test-mirror-2026-10-06')
lock=(ROOT/'verified_driver/v1/artifacts/workflow/shared-ledger.lock').open('a+b')
fcntl.flock(lock,fcntl.LOCK_EX)
scan=json.loads(subprocess.check_output([
 '/mnt/c/Users/zun24/AppData/Local/Programs/Python/Python312/python.exe',
 'C:/Users/zun24/.codex/worktrees/runtime-nstep/numerical-audit-lab-recovered-2026-10-01/verified_driver/v1/artifacts/workflow/storage.py']))
class ScannedBudget(resources.EvidenceBudget):
    def __init__(self,root,maximum):
        self.root=Path(root).resolve(); self.maximum=maximum; self.used=scan['actual_storage_bytes']
resources.EvidenceBudget=ScannedBudget
result=run_guarded(cmd,Limits(job_seconds=a.seconds),ROOT/'verified_driver/v1/artifacts/jobs'/a.name,
 ROOT/'runtime_trace/regular_nstep/artifacts/budget.json',cwd=cwd,artifact_allowance=a.allowance,
 env={'GIT_DIR':'/mnt/d/numerical-audit-lab-recovered-2026-10-01/.git/worktrees/numerical-audit-lab-recovered-2026-10-01','GIT_WORK_TREE':str(ROOT)})
with (ROOT/'verified_driver/v1/artifacts/jobs'/a.name/'storage-preflight.json').open('x') as f: json.dump(scan,f,sort_keys=True)
print(result)
raise SystemExit(result['return_code'] if result['return_code'] is not None else 2)
