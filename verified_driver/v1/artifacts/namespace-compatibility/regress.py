"""Ordered compatibility checks, all charged to the existing shared ledger."""
from pathlib import Path
import json, subprocess, sys
ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
v0 = sorted(str(p.relative_to(ROOT)) for p in (ROOT/'tests').glob('test_verified_driver_v0_*.py'))
v1 = sorted(str(p.relative_to(ROOT)) for p in (ROOT/'tests').glob('test_verified_driver_v1_*.py'))
v1 += sorted(str(p.relative_to(ROOT)) for p in (ROOT/'tests').glob('test_live_chain_*.py'))
failed = [line.split('FAILED ',1)[1].split(' - ',1)[0] for line in
          (ROOT/'verified_driver/v1/artifacts/jobs/task5-done/stdout.log').read_text().splitlines()
          if line.startswith('FAILED ')]
assert len(failed) == 10
rt = ['tests/test_regular_nstep_'+name+'.py' for name in ('acquisition','pipeline','raw','resources','public')]
stage = sys.argv[1]
suffix = sys.argv[2] if len(sys.argv)>2 else ''
tests = {'failed10':failed,'v0':v0,'v1':v1,'runtime':rt,'combined':v0+v1}[stage]
if stage == 'combined':
    previous = json.loads((ROOT/'verified_driver/v1/artifacts/jobs/task5-done/execution.json').read_bytes())
    assert set(tests) == set(previous['command'][3:-1])
command = [sys.executable, str(ROOT/'verified_driver/v1/artifacts/workflow/guard.py'),
           '--name','compat-'+stage+suffix,'--seconds','120','--allowance','536870912','--',
           'PY','-m','pytest',*tests,'-q','--junitxml='+str(HERE/(stage+suffix+'-junit.xml'))]
print(json.dumps({'stage':stage,'command':command}),flush=True)
raise SystemExit(subprocess.call(command))
