"""Real module schemas, strict provenance, and unchanged public fresh relocation."""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

import pytest

from runtime_trace.regular_2step import checker, delivery
from runtime_trace.regular_2step.schema import load, write, component_hashes, completion

ROOT = Path(__file__).resolve().parents[3]
PACKAGE = ROOT / 'runtime_trace/regular_2step'


@pytest.mark.parametrize('case', ['known', 'fresh'])
def test_actual_four_module_schema(case):
    capture = load(PACKAGE / f'artifacts/{case}-03/capture.json')
    assert len(capture['modules']) == 4
    assert all(set(m) == {'path', 'sha256', 'load_base', 'segments', 'wheel_member'}
               for m in capture['modules'].values())
    denied, required = delivery.relocated_module_paths(capture, ROOT)
    assert denied == sorted(m['path'] for m in capture['modules'].values())
    assert len(required) == 4
    assert {hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in required} == {
        m['sha256'] for m in capture['modules'].values()}
    assert all(Path(p).is_relative_to(ROOT) for p in required)


def test_unknown_module_hash_refused():
    capture = load(PACKAGE / 'artifacts/fresh-03/capture.json')
    next(iter(capture['modules'].values()))['sha256'] = '0' * 64
    with pytest.raises(delivery.SealRefused, match='unregistered frozen module'):
        delivery.relocated_module_paths(capture, ROOT)


@pytest.mark.parametrize('manifest_relative', [
    'runtime_trace/frozen_binaries/manifest.json',
    'runtime_trace/caller_transition/frozen_modules/manifest.json',
])
def test_escaping_packaged_path_refused(tmp_path, manifest_relative):
    from runtime_trace.regular_2step.structure import _frozen_modules, StructureRefused
    root = tmp_path / 'package'
    for relative in ('runtime_trace/frozen_binaries/manifest.json',
                     'runtime_trace/caller_transition/frozen_modules/manifest.json'):
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, destination)
    for path, _ in _frozen_modules(ROOT).values():
        destination = root / path.relative_to(ROOT)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
    manifest = load(root / manifest_relative)
    digest = next(iter(manifest['modules']))
    outside = tmp_path / 'outside.elf'
    outside.write_bytes(_frozen_modules(ROOT)[digest][1])
    manifest['modules'][digest] = str(outside)
    write(root / manifest_relative, manifest)
    capture = load(PACKAGE / 'artifacts/fresh-03/capture.json')
    with pytest.raises(StructureRefused, match='frozen module path'):
        delivery.relocated_module_paths(capture, root)


@pytest.mark.parametrize('field,value', [
    ('distinct_from_known_path', '/wrong/acquisition/root/runtime_trace/regular_2step/artifacts/known-03'),
    ('verdict', 'WRONG_METADATA'),
])
def test_repaired_lower_component_metadata_refused(tmp_path, field, value):
    out = tmp_path / 'derived'
    shutil.copytree(PACKAGE / 'artifacts/derived/fresh', out)
    components = load(out / 'components.json')
    components['structure'][field] = value
    write(out / 'components.json', components)
    chain = load(out / 'chain.json')
    chain['ordered_component_hashes'] = component_hashes(out)
    chain['completion_sha256'] = completion(chain)
    write(out / 'chain.json', chain)
    result = checker.check(PACKAGE / 'artifacts/fresh-03', out, ROOT)
    write(tmp_path / 'result.json', result)
    assert result['verdict'] == 'REFUSED'
    assert result['stage'] == 'SEMANTIC'
    assert result['reason'] == 'lower component semantic receipt mismatch'


def test_public_fresh_checker_relocated_unchanged_artifacts(tmp_path):
    relocated = tmp_path / 'relocated'
    relocated.mkdir()
    # Snapshot tracked bytes and new covering tests; preserve all inputs and
    # command/output/time in pytest's explicitly retained attempt directory.
    tracked = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0')
    paths = {p for p in tracked if p}
    paths.update(str(p.relative_to(ROOT)) for p in (PACKAGE / 'tests').glob('*.py'))
    for relative in sorted(paths):
        source, target = ROOT / relative, relocated / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    capture = relocated / 'runtime_trace/regular_2step/artifacts/fresh-03'
    derived = relocated / 'runtime_trace/regular_2step/artifacts/derived/fresh'
    provenance = load(derived / 'components.json')['structure']['distinct_from_known_path']
    assert not provenance.startswith(str(relocated))
    identities = {}
    for directory in (capture, derived):
        for path in directory.iterdir():
            if path.is_file():
                relative = path.relative_to(relocated)
                assert path.read_bytes() == (ROOT / relative).read_bytes()
                identities[str(relative)] = hashlib.sha256(path.read_bytes()).hexdigest()
    hook = tmp_path / 'hook'
    hook.mkdir()
    (hook / 'sitecustomize.py').write_text(delivery.AUDIT_HOOK)
    audit = tmp_path / 'audit.jsonl'
    denied, required = delivery.relocated_module_paths(load(capture / 'capture.json'), relocated)
    env = dict(os.environ)
    env.update(PYTHONPATH=str(hook) + os.pathsep + str(relocated),
               REGULAR2_AUDIT_LOG=str(audit), REGULAR2_DENIED_ROOT=str(ROOT),
               REGULAR2_RELOCATED_ROOT=str(relocated), REGULAR2_DENIED_PATHS=json.dumps(denied))
    command = [sys.executable, '-m', 'runtime_trace.regular_2step.checker',
               '--root', str(relocated), '--capture', str(capture), '--derived', str(derived)]
    started = time.monotonic()
    result = subprocess.run(command, cwd=relocated, env=env, capture_output=True, text=True)
    receipt = {'command': command, 'cwd': str(relocated), 'exit_code': result.returncode,
               'stdout': result.stdout, 'stderr': result.stderr,
               'wall_seconds': time.monotonic() - started, 'unchanged_inputs': identities,
               'source_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                                 for p in PACKAGE.glob('*.py')}}
    write(tmp_path / 'public-checker-receipt.json', receipt)
    assert result.returncode == 0, receipt
    report = json.loads(result.stdout)
    assert report['verdict'] == 'CHECKER_PASS' and report['test_trust_mode'] is False
    events = [json.loads(line) for line in audit.read_text().splitlines()]
    assert not any(e['event'].startswith('DENIED') for e in events)
    opened = {e['path'] for e in events if e['event'] == 'OPEN'}
    targets = {arg for e in events if e['event'] == 'SUBPROCESS' and 'objdump' in Path(e['argv'][0]).name
               for arg in e['argv'] if os.path.isabs(arg)}
    assert set(required) <= opened
    assert set(required) <= targets
    assert {str(capture / 'capture.json'), str(capture / 'trace.jsonl'),
            str(derived / 'components.json'), str(derived / 'chain.json')} <= opened
