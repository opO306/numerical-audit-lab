"""Exact protected history, namespace, pinset and Git submission checks."""
from pathlib import Path
import hashlib, json, subprocess, sys
ROOT=Path(__file__).resolve().parents[4]
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
def digest(p):
    with p.open('rb') as f: return hashlib.file_digest(f,'sha256').hexdigest()
history=json.loads((HERE/'historical-before.json').read_bytes())
changed=[]
for name,want in history['files'].items():
    p=ROOT/name
    actual={'bytes':p.stat().st_size,'sha256':digest(p)} if p.is_file() else None
    if actual!=want: changed.append({'path':name,'before':want,'after':actual})
assert not changed, changed
source_snapshot={}
for p in (ROOT/'runtime_trace').rglob('*.py'):
    if 'artifacts' not in p.relative_to(ROOT/'runtime_trace').parts and '__pycache__' not in p.parts:
        source_snapshot[p.relative_to(ROOT).as_posix()]=digest(p)
for name in ('lab/v2_bound.py','independent_checker/oracle.py'):
    source_snapshot[name]=digest(ROOT/name)
approved_sha='c949e61b420696f9ecfc61608d8e0e13be5f12a965e1e103f40ea2941689ddb3'
approved=None
for p in (ROOT/'verified_driver/v0/artifacts').rglob('integration_source_pinset.json'):
    if digest(p)==approved_sha:
        approved=json.loads(p.read_bytes()); break
assert approved is not None and len(approved)==89
assert source_snapshot==approved
from verified_driver.v1.live_chain.session import live_source_snapshot
pins=live_source_snapshot(ROOT)
names=json.loads((HERE/'relocation.json').read_bytes())['moved_files']
assert all('verified_driver/v1/live_chain/'+name in pins for name in names)
assert not any(name.startswith('runtime_trace/live_chain/') for name in pins)
assert not list((ROOT/'runtime_trace/live_chain').glob('*.py'))
source_changes=[]
archived=HERE/'pre-compatibility-source'
for p in archived.rglob('*.py'):
    name=p.relative_to(archived).as_posix()
    newname=name.replace('runtime_trace/live_chain/','verified_driver/v1/live_chain/')
    expected=p.read_bytes().replace(b'runtime_trace.live_chain',b'verified_driver.v1.live_chain').replace(b'runtime_trace/live_chain',b'verified_driver/v1/live_chain')
    if name in ('runtime_trace/live_chain/harness.py','runtime_trace/live_chain/gdb_live.py'):
        expected=expected.replace(b'Path(__file__).resolve().parents[2]',b'Path(__file__).resolve().parents[3]')
    assert (ROOT/newname).read_bytes()==expected, newname
    if p.read_bytes()!=expected: source_changes.append(newname)
with (HERE/'v1-source-pinset.json').open('x') as f: json.dump(pins,f,sort_keys=True,indent=2)
diff=subprocess.run(['git','diff','--check'],cwd=ROOT,capture_output=True,text=True)
assert diff.returncode==0, diff.stdout+diff.stderr
status=subprocess.check_output(['git','status','--short'],cwd=ROOT,text=True)
with (HERE/'git-status.txt').open('x') as f: f.write(status)
with (HERE/'git-diff-check.txt').open('x') as f: f.write('exit_code=0\n'+diff.stdout+diff.stderr)
staged=subprocess.check_output(['git','diff','--cached','--name-only'],cwd=ROOT,text=True)
assert not staged
ledger=json.loads((ROOT/'runtime_trace/regular_nstep/artifacts/budget.json').read_bytes())
result={'historical_files_checked':len(history['files']),'historical_changed':changed,
        'approved_runtime_files':len(approved),'approved_pinset_sha256':approved_sha,
        'runtime_source_bytes_and_universe_unchanged':True,'moved_live_chain_files_pinned':len(names),
        'v1_source_pinset_files':len(pins),'namespace_only_source_changes':source_changes,
        'git_diff_check':0,'staged_files':staged,'used_seconds':ledger['used_seconds'],
        'remaining_seconds':3600-ledger['used_seconds']}
with (HERE/'verification.json').open('x') as f: json.dump(result,f,sort_keys=True,indent=2)
print(json.dumps(result))
