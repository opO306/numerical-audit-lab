"""Final read-only source/history/resource/Git inventory after Task 6."""
from pathlib import Path
import hashlib,json,subprocess,sys,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[4]; HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from verified_driver.v1.live_chain.session import live_source_snapshot
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
history=json.loads((HERE/'historical-before.json').read_bytes())
changed=[]
for name,want in history['files'].items():
    p=ROOT/name; actual={'bytes':p.stat().st_size,'sha256':sha(p)} if p.is_file() else None
    if actual!=want: changed.append(name)
assert not changed,changed
runtime={}
import os
for folder,dirs,files in os.walk(ROOT/'runtime_trace'):
    dirs[:]=[d for d in dirs if d not in ('artifacts','__pycache__')]
    for name in files:
        if name.endswith('.py'):
            p=Path(folder)/name; runtime[p.relative_to(ROOT).as_posix()]=sha(p)
for name in ('lab/v2_bound.py','independent_checker/oracle.py'):runtime[name]=sha(ROOT/name)
approved_sha='c949e61b420696f9ecfc61608d8e0e13be5f12a965e1e103f40ea2941689ddb3'
approved=next(json.loads(p.read_bytes()) for p in (ROOT/'verified_driver/v0/artifacts').rglob('integration_source_pinset.json') if sha(p)==approved_sha)
assert len(runtime)==89 and runtime==approved
pins=live_source_snapshot(ROOT)
moved=json.loads((HERE/'relocation.json').read_bytes())['moved_files']
assert all('verified_driver/v1/live_chain/'+name in pins for name in moved)
assert 'verified_driver/v1/live_chain/supervisor.py' in pins
with (ROOT/'verified_driver/v1/artifacts/task6-source-pinset.json').open('x') as f:json.dump(pins,f,sort_keys=True,indent=2)
tree=ET.parse(ROOT/'verified_driver/v1/artifacts/task6-done-junit.xml')
cases=tree.findall('.//testcase')
assert len(cases)==264 and not tree.findall('.//failure') and not tree.findall('.//error') and not tree.findall('.//skipped')
counts={}
for case in cases:
    name=case.attrib['classname'];counts[name]=counts.get(name,0)+1
ledger=json.loads((ROOT/'runtime_trace/regular_nstep/artifacts/budget.json').read_bytes())
running=json.loads((ROOT/'runtime_trace/regular_nstep/artifacts/budget.running.json').read_bytes())
assert running['state']=='FINISHED'
diff=subprocess.run(['git','diff','--check'],cwd=ROOT,capture_output=True,text=True)
assert diff.returncode==0
status=subprocess.check_output(['git','status','--short'],cwd=ROOT,text=True)
staged=subprocess.check_output(['git','diff','--cached','--name-only'],cwd=ROOT,text=True)
assert not staged
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
assert head=='fbbb90171c43ed5462e9584c2621cb0b86b80bd4'
with (ROOT/'verified_driver/v1/artifacts/task6-git-status.txt').open('x') as f:f.write(status)
result={'final_passed':len(cases),'failures':0,'errors':0,'skips':0,'tests_by_module':counts,
 'pre_compatibility_historical_checked':len(history['files']),'historical_changed':changed,
 'protected_inventory_report':'verified_driver/v1/artifacts/preservation/task6-final.json',
 'approved_runtime_pinset_files':len(runtime),'approved_pinset_sha256':approved_sha,
 'v1_pinset_files':len(pins),'relocated_live_chain_pinned':len(moved),'supervisor_pinned':True,
 'head':head,'git_diff_check':diff.returncode,'staged_files':staged,
 'used_seconds':ledger['used_seconds'],'remaining_seconds':3600-ledger['used_seconds'],
 'compatibility_guarded_seconds':3230.3961637530215-3113.881535818022,
 'task6_guarded_seconds':ledger['used_seconds']-3230.3961637530215,
 'guarded_seconds_this_work':ledger['used_seconds']-3113.881535818022}
with (ROOT/'verified_driver/v1/artifacts/task6-final-inventory.json').open('x') as f:json.dump(result,f,sort_keys=True,indent=2)
print(json.dumps(result))
