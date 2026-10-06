"""Separate no-GDB measurements of the unchanged original Gala API harness."""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from runtime_trace.regular_nstep.resources import Limits, run_guarded
base = ROOT / 'runtime_trace/regular_nstep/artifacts/original-baselines'
base.mkdir(exist_ok=False)
for n in (10, 100):
    output = base / f'output{n}'
    output.mkdir()
    receipt = run_guarded([sys.executable, '-m', 'runtime_trace.regular_nstep.harness'],
        Limits(), base / f'job{n}', base.parent / 'budget.json', cwd=ROOT,
        env={'RTN_STEPS': str(n), 'RT_OUTPUT': str(output)}, artifact_allowance=2097152)
    print(receipt, flush=True)
    if receipt['verdict'] != 'EXECUTED':
        raise SystemExit(2)
