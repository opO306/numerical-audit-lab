"""Task7 unit/saved attacks only, charged through the unchanged shared guard."""
from pathlib import Path
import os,subprocess,sys
ROOT=Path(__file__).resolve().parents[5]; HERE=Path(__file__).resolve().parent.parent
name=sys.argv[1]; stage=sys.argv[2]
if stage=='attacks':tests=['tests/test_verified_driver_v1_attacks.py']
elif stage=='all':
    tests=sorted(str(p.relative_to(ROOT)) for p in (ROOT/'tests').glob('test_verified_driver_v[01]_*.py'))
    tests+=sorted(str(p.relative_to(ROOT)) for p in (ROOT/'tests').glob('test_live_chain_*.py'))
    tests+=['tests/test_regular_nstep_'+s+'.py' for s in ('acquisition','pipeline','raw','resources','public')]
else:raise ValueError('unit/selected regression stages only')
os.environ['V1_TASK7_RUN']=name
command=[sys.executable,str(ROOT/'verified_driver/v1/artifacts/workflow/guard.py'),
 '--name',name,'--seconds','120' if stage=='all' else '45','--allowance','536870912','--',
 'PY','-m','pytest',*tests,'-q','--junitxml='+str(HERE/(name+'-junit.xml'))]
raise SystemExit(subprocess.call(command))
