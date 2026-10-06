"""Source-identical native fixture test mirror; no new numerical execution."""
from pathlib import Path
import hashlib, json, shutil
ROOT=Path(__file__).resolve().parents[4]
MIRROR=Path('/home/otherside123/verified-driver-v1-test-mirror-2026-10-06')
OLD=Path('/home/otherside123/verified-driver-v0-test-mirror-2026-10-05')
if not MIRROR.exists(): shutil.copytree(OLD,MIRROR,symlinks=True,ignore=shutil.ignore_patterns('tmp-*','__pycache__','.pytest_cache'))
files=[]
for folder in ('verified_driver','runtime_trace','tests'):
    files.extend(p for p in (ROOT/folder).rglob('*.py') if 'artifacts' not in p.relative_to(ROOT/folder).parts and '__pycache__' not in p.parts)
for p in files:
    target=MIRROR/p.relative_to(ROOT); target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(p,target)
    assert p.read_bytes()==target.read_bytes()
fixture=ROOT/'verified_driver/v1/artifacts/fixtures/n3/capture'
if fixture.exists():
    dest=MIRROR/fixture.relative_to(ROOT)
    if not dest.exists(): shutil.copytree(fixture,dest)
    for p in fixture.iterdir():
        if p.is_file(): assert p.read_bytes()==(dest/p.name).read_bytes()
result={'role':'TEST_ONLY saved evidence; no fresh numerics','source_identical':True,'mirror':str(MIRROR),
 'files':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}
(ROOT/'verified_driver/v1/artifacts/workflow/mirror-current.json').write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
print(json.dumps({'mirror':str(MIRROR),'source_identical':True,'files':len(files)}))
