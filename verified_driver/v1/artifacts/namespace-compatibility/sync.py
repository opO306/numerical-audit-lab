"""Copy the combined product's exact source bytes to the native test tree."""
from pathlib import Path
import hashlib, json, shutil
ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
MIRROR = Path('/home/otherside123/verified-driver-v1-test-mirror-2026-10-06')
assert MIRROR.is_dir()
legacy = MIRROR / 'runtime_trace/live_chain'
for p in legacy.glob('*.py'):
    assert p.resolve().is_relative_to(MIRROR.resolve())
    assert p.name in ['__init__.py','checker.py','checkpoint.py','gdb_live.py','harness.py',
                      'producer.py','protocol.py','raw.py','schema.py','session.py','worker.py']
    p.unlink()
files = {}
for base in ('verified_driver','runtime_trace','tests'):
    for p in (ROOT / base).rglob('*.py'):
        if 'artifacts' in p.relative_to(ROOT / base).parts or '__pycache__' in p.parts:
            continue
        target = MIRROR / p.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(p, target)
        assert p.read_bytes() == target.read_bytes()
        files[p.relative_to(ROOT).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
assert not list(legacy.glob('*.py'))
with (HERE / 'combined-source-mirror.json').open('x') as f:
    json.dump({'combined_product_tree':True, 'source_identical':True,
               'mirror':str(MIRROR), 'files':files}, f, sort_keys=True, indent=2)
print(json.dumps({'combined_source_files':len(files),'source_identical':True}))
