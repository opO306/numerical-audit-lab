"""Historical snapshot before the authorized Task8 ceiling-only amendment."""
from pathlib import Path
import hashlib,json,os,subprocess,sys
ROOT=Path(__file__).resolve().parents[5];HERE=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from verified_driver.v1.live_chain.session import live_source_snapshot
from verified_driver.v1.model import content_id
def save(name,value):
    with (HERE/name).open('x',encoding='utf-8') as f:json.dump(value,f,sort_keys=True,indent=2)
history={}
for folder,dirs,names in os.walk(ROOT/'verified_driver/v1/artifacts'):
    dirs[:]=[d for d in dirs if d!='__pycache__']
    for name in names:
        p=Path(folder)/name
        if HERE in p.parents or p.is_symlink() or name=='shared-ledger.lock':continue
        with p.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
        history[p.relative_to(ROOT).as_posix()]={'bytes':p.stat().st_size,'sha256':digest}
save('history-before.json',{'files':history})
pins=live_source_snapshot(ROOT);save('source-before.json',pins)
ledger=ROOT/'runtime_trace/regular_nstep/artifacts/budget.json';raw=ledger.read_bytes();budget=json.loads(raw)
assert budget['used_seconds']==3472.7506255470207
with (HERE/'pre-ceiling-budget.snapshot.json').open('xb') as f:f.write(raw)
with (HERE/'pre-ceiling-running.snapshot.json').open('xb') as f:f.write(ledger.with_suffix('.running.json').read_bytes())
with (HERE/'pre-task8-status.md').open('xb') as f:f.write((ROOT/'current/VERIFIED_DRIVER_V1_2026-10-06.md').read_bytes())
for name,args in [('git-before.txt',['status','--short']),('head-before.txt',['rev-parse','HEAD'])]:
    with (HERE/name).open('xb') as f:f.write(subprocess.check_output(['git',*args],cwd=ROOT))
save('preflight.json',{'historical_files':len(history),'source_binding':content_id(pins),'pin_count':len(pins),
    'used_seconds':budget['used_seconds'],'new_ceiling_seconds':4200,'remaining_seconds':4200-budget['used_seconds'],
    'planned_caps_seconds':400,'failure_review_rerun_reserve_seconds':4200-budget['used_seconds']-400,
    'new_ledger':False,'ordinary_larger_campaigns_authorized':False})
print(json.dumps({'history':len(history),'remaining':4200-budget['used_seconds']}))
