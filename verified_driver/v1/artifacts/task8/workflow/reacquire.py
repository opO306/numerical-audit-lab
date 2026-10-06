"""Necessary source-bound re-execution after final review containment fix."""
from pathlib import Path
import subprocess,sys
HERE=Path(__file__).resolve().parent
PY=sys.executable
selection=[('ordinary','ordinary-02'),('positive','positive-03'),('negative','negative-02'),('nonterminal','nonterminal-02'),('terminal','terminal-02'),('paused-death','paused-death-02'),('active-death','active-death-02'),('interruption','interruption-02')]
start=int(sys.argv[1]);end=int(sys.argv[2])
for stage,name in selection[start:end]:
    args=['--control-ref','ordinary-02','--positive-ref','positive-03','--negative-ref','negative-02']
    subprocess.run([PY,str(HERE/'guard.py'),'--stage',stage,'--name','task8-'+name,'--allowance','1073741824','--',PY,str(HERE/'live_runs.py'),stage,name,*args],check=True)
    subprocess.run([PY,str(HERE/'export.py'),name],check=True)
    print('REACQUIRED '+name,flush=True)
