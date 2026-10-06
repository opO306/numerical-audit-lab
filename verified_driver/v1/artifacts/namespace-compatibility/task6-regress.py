from pathlib import Path
import subprocess,sys
ROOT=Path(__file__).resolve().parents[4]
tests=sorted(str(p.relative_to(ROOT)) for p in (ROOT/'tests').glob('test_verified_driver_v[01]_*.py'))
tests+=sorted(str(p.relative_to(ROOT)) for p in (ROOT/'tests').glob('test_live_chain_*.py'))
tests+=['tests/test_regular_nstep_'+name+'.py' for name in ('acquisition','pipeline','raw','resources','public')]
command=[sys.executable,str(ROOT/'verified_driver/v1/artifacts/workflow/guard.py'),
         '--name','task6-done','--seconds','120','--allowance','536870912','--',
         'PY','-m','pytest',*tests,'-q','--junitxml='+str(ROOT/'verified_driver/v1/artifacts/task6-done-junit.xml')]
raise SystemExit(subprocess.call(command))
