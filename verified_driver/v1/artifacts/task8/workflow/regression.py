from pathlib import Path
import subprocess,sys
ROOT=Path(__file__).resolve().parents[5];HERE=Path(__file__).resolve().parent.parent
tests=sorted(str(p.relative_to(ROOT)) for p in (ROOT/'tests').glob('test_verified_driver_v[01]_*.py'))
tests+=sorted(str(p.relative_to(ROOT)) for p in (ROOT/'tests').glob('test_live_chain_*.py'))
tests+=['tests/test_regular_nstep_'+s+'.py' for s in ('acquisition','pipeline','raw','resources','public')]
name=sys.argv[1]
raise SystemExit(subprocess.call([sys.executable,str(HERE/'workflow/guard.py'),'--stage','regression','--name',name,'--','PY','-m','pytest',*tests,'-q','--junitxml='+str(HERE/(name+'-junit.xml'))]))
