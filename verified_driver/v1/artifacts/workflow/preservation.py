"""Read-only exact protected-byte recheck; never rewrites baseline/history."""
from pathlib import Path
import argparse, hashlib, json
ROOT=Path(__file__).resolve().parents[4]
p=argparse.ArgumentParser(); p.add_argument('--name',required=True); a=p.parse_args()
baseline=json.loads((ROOT/'verified_driver/v1/artifacts/preservation/before.json').read_bytes())
changed=[]; checked=0
for name,want in baseline['files'].items():
    file=Path(name)
    try:
        with file.open('rb') as stream: digest=hashlib.file_digest(stream,'sha256').hexdigest()
        actual={'bytes':file.stat().st_size,'sha256':digest}
    except OSError as exc: actual={'error':str(exc)}
    if actual!=want: changed.append({'path':name,'before':want,'after':actual})
    checked+=1
result={'schema':'V1_PROTECTED_RECHECK','checked_files':checked,'changed':changed,'mutable_exclusions':baseline['mutable_exclusions']}
out=ROOT/'verified_driver/v1/artifacts/preservation'/(a.name+'.json')
with out.open('x',encoding='utf-8') as f: json.dump(result,f,sort_keys=True,indent=2); f.write('\n')
print(json.dumps({'checked_files':checked,'changed_count':len(changed),'report':str(out)}))
raise SystemExit(1 if changed else 0)
