"""V0 metadata wrapper; numerical jobs charge the existing approved RT ledger."""
import argparse
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT))
from runtime_trace.regular_nstep.resources import Limits, run_guarded
p=argparse.ArgumentParser()
p.add_argument('--name',required=True)
p.add_argument('--allowance',type=int,default=67108864)
p.add_argument('--mirror',action='store_true')
a,cmd=p.parse_known_args()
if cmd[0]=='--': cmd.pop(0)
if cmd[0]=='PY': cmd[0]=sys.executable
out=ROOT/'verified_driver/v0/artifacts/jobs'/a.name
cwd=Path('/home/otherside123/verified-driver-v0-test-mirror-2026-10-05') if a.mirror else ROOT
result=run_guarded(cmd,Limits(),out,ROOT/'runtime_trace/regular_nstep/artifacts/budget.json',cwd=cwd,
    artifact_allowance=a.allowance,env={'GIT_DIR':'/mnt/d/numerical-audit-lab-recovered-2026-10-01/.git/worktrees/numerical-audit-lab-recovered-2026-10-01',
    'GIT_WORK_TREE':str(ROOT)})
print(result)
raise SystemExit(result['return_code'] if result['return_code'] is not None else 2)
