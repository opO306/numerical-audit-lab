"""Designer-approved namespace relocation; historical evidence is read-only."""
from pathlib import Path
import hashlib, json, shutil, subprocess

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
names = ['__init__.py', 'checker.py', 'checkpoint.py', 'gdb_live.py',
         'harness.py', 'producer.py', 'protocol.py', 'raw.py', 'schema.py',
         'session.py', 'worker.py']
old = ROOT / 'runtime_trace/live_chain'
new = ROOT / 'verified_driver/v1/live_chain'
assert sorted(p.name for p in old.glob('*.py')) == sorted(names)
assert not new.exists()
historical = {}
for p in (ROOT / 'verified_driver/v1/artifacts').rglob('*'):
    if HERE in p.parents or '__pycache__' in p.parts or p.is_symlink() or not p.is_file():
        continue
    if p.name == 'shared-ledger.lock':
        continue
    historical[p.relative_to(ROOT).as_posix()] = {
        'bytes': p.stat().st_size,
        'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
with (HERE / 'historical-before.json').open('x') as f:
    json.dump({'role': 'pre-compatibility historical evidence', 'files': historical}, f, sort_keys=True, indent=2)
history = HERE / 'pre-compatibility-source'
history.mkdir()
targets = list(old.glob('*.py')) + list((ROOT / 'verified_driver/v1').glob('*.py'))
targets += [p for p in (ROOT / 'tests').glob('*.py') if b'runtime_trace.live_chain' in p.read_bytes()]
for p in targets:
    saved = history / p.relative_to(ROOT)
    saved.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(p, saved)
shutil.copyfile(ROOT / 'current/VERIFIED_DRIVER_V1_2026-10-06.md', HERE / 'pre-compatibility-status.md')
new.mkdir()
for name in names:
    p = old / name
    target = new / name
    assert p.resolve().is_relative_to(ROOT) and target.resolve().is_relative_to(ROOT)
    shutil.move(str(p), str(target))
targets = list(new.glob('*.py')) + list((ROOT / 'verified_driver/v1').glob('*.py'))
targets += [p for p in (ROOT / 'tests').glob('*.py') if b'runtime_trace.live_chain' in p.read_bytes()]
for p in targets:
    data = p.read_bytes().replace(b'runtime_trace.live_chain', b'verified_driver.v1.live_chain')
    data = data.replace(b'runtime_trace/live_chain', b'verified_driver/v1/live_chain')
    if p.name in ('harness.py', 'gdb_live.py') and p.parent == new:
        data = data.replace(b'Path(__file__).resolve().parents[2]', b'Path(__file__).resolve().parents[3]')
    p.write_bytes(data)
result = {'moved_files': names, 'historical_files': len(historical),
          'source_scope': 'imports, executable paths, root depth, V1 source pinning only',
          'old_python_files': [p.name for p in old.glob('*.py')]}
with (HERE / 'relocation.json').open('x') as f:
    json.dump(result, f, sort_keys=True, indent=2)
print(json.dumps(result))
