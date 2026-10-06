import argparse
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from runtime_trace.regular_nstep.resources import run_guarded, Limits
p = argparse.ArgumentParser()
p.add_argument('--out', required=True)
p.add_argument('--allowance', type=int, default=67108864)
p.add_argument('--git-dir')
p.add_argument('--git-work-tree')
a, cmd = p.parse_known_args()
if cmd[0] == '--': cmd.pop(0)
if cmd[0] == 'PY': cmd[0] = sys.executable
env = {}
if a.git_dir: env['GIT_DIR'] = a.git_dir
if a.git_work_tree: env['GIT_WORK_TREE'] = a.git_work_tree
receipt = run_guarded(cmd, Limits(), ROOT / a.out,
    ROOT / 'runtime_trace/regular_nstep/artifacts/budget.json', cwd=ROOT,
    artifact_allowance=a.allowance, env=env)
print(receipt)
raise SystemExit(0 if receipt['verdict'] == 'EXECUTED' else 2)
