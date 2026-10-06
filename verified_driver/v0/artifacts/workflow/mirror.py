"""Native filesystem test mirror; never a substituted numerical executor."""
from pathlib import Path
import hashlib
import json
import shutil

ROOT=Path(__file__).resolve().parents[4]
MIRROR=Path('/home/otherside123/verified-driver-v0-test-mirror-2026-10-05')
SOURCE=Path(json.loads((ROOT/'runtime_trace/regular_nstep/artifacts/external-proof-receipts/public-checker-receipt.json').read_bytes())['cwd'])
assert SOURCE.resolve().is_relative_to(Path('/home/otherside123/runtime-nstep-portability-proof-2026-10-05'))
def sha(p):
    with p.open('rb') as f: return hashlib.file_digest(f,'sha256').hexdigest()
if not MIRROR.exists(): shutil.copytree(SOURCE,MIRROR)
pins=json.loads((ROOT/'runtime_trace/regular_nstep/artifacts/connected10-final2/integration_source_pinset.json').read_bytes())
files=[ROOT/relative for relative in pins]
files.extend((ROOT/'tests').glob('*.py'))
files.extend((ROOT/'verified_driver').glob('*.py'))
files.extend((ROOT/'verified_driver/v0').glob('*.py'))
for path in files:
    target=MIRROR/path.relative_to(ROOT)
    target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(path,target)
    assert sha(path)==sha(target)
case=ROOT/'runtime_trace/regular_nstep/artifacts/connected10-final2'
target=MIRROR/case.relative_to(ROOT)
if not target.exists(): shutil.copytree(case,target)
for path in case.rglob('*'):
    if path.is_file(): assert sha(path)==sha(target/path.relative_to(case))
(MIRROR/'verified_driver/v0/artifacts').mkdir(parents=True,exist_ok=True)
result={'schema':'source-identical-native-test-mirror-v1','root':str(MIRROR),'existing_snapshot':str(SOURCE),
    'synced_files':{str(p.relative_to(ROOT)):sha(p) for p in files},'runtime_sources':len(pins),
    'role':'stored-evidence and storage/transaction tests; real authority run still uses managed source','core_bytes_identical':True}
(ROOT/'verified_driver/v0/artifacts/workflow/mirror-current.json').write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
print(json.dumps({'mirror':str(MIRROR),'synced_files':len(files),'core_bytes_identical':True}))
