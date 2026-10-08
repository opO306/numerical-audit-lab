"""Replay immutable old profile authority in an isolated old source universe.

This is an offline native/IEEE evidence recheck, not a current-source promotion
or a numerical execution. Returned authority remains the exact old 40-source
f759 receipt. Current V1 modules are never copied to or imported by the replay.
"""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import subprocess
import sys
import tempfile


OLD_BINDING = 'f75980706aefbbd68cddce09549695c2f633905e01185f92f96660db81a9e2cd'
RUNTIME_PIN = 'c949e61b420696f9ecfc61608d8e0e13be5f12a965e1e103f40ea2941689ddb3'
OLD_PROFILE = '342789260f3f48a9bbe66598cf3690bacc85538cd59944c4b1c4d47630edfe22'
ARCHIVE = 'compute_metabolism/v0/source_epochs/' + OLD_BINDING
AUTHORITY = {
    'adaptive.py': '6d00383ccda53b555930526e9cc46ba2e42c5de90f36b56d80a5ec46f85bffbb',
    'profile_verify.py': 'ccd1c4658db2dcab5b6edad56b2492877928c34630fbafba49e0579d5e556c59',
}
# Additional helpers/data are finite and pinned, independently of labels in a
# supplied manifest. No run directory tree or current V1 source is copied.
DEPENDENCIES = {
    'verified_driver/__init__.py': '2c1362913928b2783d6608ce47ac6ce6e0c2bcd6e588aa7b54f86484582aab40',
    'verified_driver/v0/__init__.py': '84b093a322fb69f39601c2ac389570c0603fd44c27ba336774e03f858bebead5',
    'verified_driver/v0/model.py': 'cfd1fb0c1f70a27492687d36b75505cdbab7439e53a48e25cb2499f330bb3b68',
    'lab/__init__.py': '94b2d9ac2feb6370179ca7c1cfc3790705d33bcf31339571b6f0a48e101fee56',
    'independent_checker/__init__.py': 'b602bd82271af1d06693563d12d652da86c3dd1bd39e903c3c07dfa345c1f7df',
    'compute_metabolism/__init__.py': '9be9e607cd4ba418cff0dea58407a3d8f3596868f851ae5fd7c6eef58deb35c7',
    'compute_metabolism/v0/__init__.py': '1a5781d91eac824b12490f15e417eec091f89f164eb8f37f9da38ac9f6782fce',
    'runtime_trace/frozen_binaries/manifest.json': '518756e0307ba95454c54e55dcf8225dccabe40733e719a2d17265bac1c6ddde',
    'runtime_trace/frozen_binaries/libc.so.6': '3a15d66867d83762c7f2f1e37359cb8f6c5743edb369c65285cb0b1c4f7498bf',
    'runtime_trace/caller_transition/frozen_modules/python3.12': 'e50d468e8b0adfb05733f5b87b3cff34829c4a8c1aea50c865aa8bdfe4bb150f',
    'audit/gate2c1/vendor/gala/integrate/cyintegrators/leapfrog.cpython-312-x86_64-linux-gnu.so': 'a6ac98736304bb9f6a92e473bba45da10d9b5b99f8019e2ca15eb6a7f86234fc',
    'audit/gate2c1/vendor/gala/potential/potential/builtin/cybuiltin.cpython-312-x86_64-linux-gnu.so': '33d66d82c34c717560747ffbfca1d98f97432a0a671a0a210a0a225d8367ecaf',
    'runtime_trace/regular_2step/artifacts/known-03/capture.json': '09dd6df89251a44227df92c76848c44ef24c351b0ed94e43259f979a7d5d2752',
    'runtime_trace/regular_2step/artifacts/known-03/trace.jsonl': 'ccdd0be65cc41aec45557ad48a59da4e6986ba7955b47b7ddbf16cd2449ea7fb',
    'runtime_trace/numeric_ir/artifacts/attempt-05/numeric_ir.json': 'bbb912c041cb47cf2f3814d416a298c3c6469c35a47c9b7cda629c11415586ba',
    'current/numeric_ir_v2_independent_audit_evidence_2026-10-03.zip': '6fd330347662c535fd80f7b6c9cc80df0532740883e50ea7c88290a1d39419dc',
}
PROOF_BASE = 'compute_metabolism/v0/execution_profiles/proofs/task8-positive-03-edge-1/'
PROOF = {
    'checkpoint/checkpoint.json': '8c49ea95af86f29bd7d7cf188370ac5ca2fe8ed90058bc7987d5e62c7acd3a93',
    'checkpoint/trace.jsonl': 'f8bc9cef81e40383270b11717890fc1fb5c02d9ff4da144e565f57668151d692',
    'edge/edge.json': 'ac7cf83c37a1e5dad6c1f68a9ef80f4098280f4ca4da621218e479e738273180',
    'edge/completion.json': 'c2213fa639bf5414f3d106efc00aa744cf96bc2bdfb2f37a046e88ffc8535d3f',
    'predecessor.json': '9979a2b110d16b283d5995912608f37817c5713270d46528c652083cb22e4c9e',
}


def _require(value, reason):
    if not value:
        raise ValueError('REFUSED: historical profile ' + reason)


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=True, allow_nan=False).encode('ascii')


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _path(path):
    absolute = Path(os.path.abspath(path))
    for parent in (absolute, *absolute.parents):
        info = parent.lstat()
        _require(not stat.S_ISLNK(info.st_mode) and not getattr(info, 'st_file_attributes', 0) & 0x400,
                 'unaliased path required: ' + str(parent))
    return absolute


def _bytes(path):
    path = _path(path); info = path.stat()
    _require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_size <= 536870912,
             'bounded single-link file required: ' + str(path))
    return path.read_bytes()


def _json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            _require(key not in result, 'duplicate JSON key')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite JSON')))


def _inventory(root, *, runtime=False):
    found = set()
    for folder, directories, files in os.walk(_path(root), followlinks=False):
        if runtime:
            directories[:] = [d for d in directories if d not in ('artifacts', '__pycache__')]
        for name in directories:
            _path(Path(folder) / name)
        for name in files:
            path = _path(Path(folder) / name)
            if not runtime or name.endswith('.py'):
                found.add(path.relative_to(root).as_posix())
    return found


def _snapshot_paths(snapshot):
    _require(type(snapshot) is dict, 'source snapshot mapping')
    for relative, digest in snapshot.items():
        _require(type(relative) is str and relative and '\\' not in relative and ':' not in relative
                 and not PurePosixPath(relative).is_absolute()
                 and all(p not in ('', '.', '..') for p in relative.split('/')),
                 'canonical source path')
        _require(type(digest) is str and len(digest) == 64
                 and all(c in '0123456789abcdef' for c in digest), 'source SHA256')


def _payload(repo_root):
    root = _path(repo_root); archived = root / ARCHIVE
    manifest = _json(_bytes(archived / 'manifest.json'))
    _require(set(manifest) == {'schema','source_binding','source_count','source_snapshot',
                              'authority','historical_pass_reclassified'}
             and manifest['schema'] == 'IMMUTABLE_HISTORICAL_V1_SOURCE_EPOCH'
             and manifest['source_binding'] == OLD_BINDING
             and type(manifest['source_count']) is int and manifest['source_count'] == 40
             and manifest['authority'] == AUTHORITY
             and manifest['historical_pass_reclassified'] is False, 'immutable archive manifest')
    snapshot = manifest['source_snapshot']; _snapshot_paths(snapshot)
    _require(len(snapshot) == 40 and _sha(_canonical(snapshot)) == OLD_BINDING,
             'immutable old 40-source binding')
    _require(_inventory(archived / 'source') == set(snapshot), 'exact old source archive inventory')
    _require(_inventory(archived / 'authority') == set(AUTHORITY), 'exact old authority inventory')
    payload = {}
    def bind(relative, origin, want):
        raw = _bytes(origin)
        _require(_sha(raw) == want, 'byte identity: ' + relative)
        _require(relative not in payload or payload[relative] == raw, 'conflicting pinned source')
        payload[relative] = raw
    for relative, digest in snapshot.items():
        bind(relative, archived / 'source' / relative, digest)
    for relative, digest in AUTHORITY.items():
        bind('compute_metabolism/v0/' + relative, archived / 'authority' / relative, digest)
    runtime = {'runtime_trace/' + p: _sha(_bytes(root / 'runtime_trace' / p))
               for p in _inventory(root / 'runtime_trace', runtime=True)}
    for relative in ('lab/v2_bound.py', 'independent_checker/oracle.py'):
        runtime[relative] = _sha(_bytes(root / relative))
    _require(len(runtime) == 89 and _sha(_canonical(runtime) + b'\n') == RUNTIME_PIN,
             'protected Runtime 89-source pinset drift')
    for relative, digest in runtime.items():
        bind(relative, root / relative, digest)
    for relative, digest in DEPENDENCIES.items():
        bind(relative, root / relative, digest)
    for relative, digest in PROOF.items():
        bind(PROOF_BASE + relative, root / PROOF_BASE / relative, digest)
    pointer = _bytes(root / PROOF_BASE / 'checkpoint/CHECKPOINT')
    _require(pointer == (PROOF['checkpoint/checkpoint.json'] + '\n').encode(), 'old checkpoint pointer')
    payload[PROOF_BASE + 'checkpoint/CHECKPOINT'] = pointer
    # An exclusive temporary root must expose precisely the old 19 V1 modules.
    _require({p for p in payload if p.startswith('verified_driver/v1/')} ==
             {p for p in snapshot if p.startswith('verified_driver/v1/')}, 'current V1 leakage')
    return payload


_REPLAY = r'''
import hashlib,json,os,pathlib,sys
root=pathlib.Path(sys.argv[1]).resolve()
os.chdir(root)
os.environ['PATH']='/usr/bin:/bin'
os.environ['PYTHONDONTWRITEBYTECODE']='1'
sys.dont_write_bytecode=True
sys.path.insert(0,str(root))
pins=json.loads((root/'isolated-inputs.json').read_bytes())
actual={p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}
assert actual==set(pins)|{'isolated-inputs.json'}, 'isolated input inventory'
for relative,digest in pins.items():
    assert hashlib.sha256((root/relative).read_bytes()).hexdigest()==digest, relative
assert not any('native_evex' in p for p in pins), 'current V1 source leakage'
from compute_metabolism.v0.profile_verify import verify_registered_profile
profile=json.loads(sys.stdin.buffer.read())
result=verify_registered_profile(profile,root)
for name,module in tuple(sys.modules.items()):
    if name.split('.')[0] in {'runtime_trace','verified_driver','compute_metabolism','lab','independent_checker'}:
        origin=getattr(module,'__file__',None)
        if origin is None:
            # Runtime Trace intentionally has a namespace package at its root.
            # Every search location must still be the sole isolated directory,
            # and its contents must include authenticated source inputs.
            expected=root.joinpath(*name.split('.'))
            locations=tuple(pathlib.Path(p).resolve() for p in getattr(module,'__path__',()))
            assert locations==(expected,), 'unbound namespace origin: '+name
            assert any(p.startswith(expected.relative_to(root).as_posix()+'/') for p in pins), name
            continue
        path=pathlib.Path(origin).resolve()
        assert path.is_relative_to(root), 'module outside isolated root: '+name
        relative=path.relative_to(root).as_posix()
        assert relative in pins and hashlib.sha256(path.read_bytes()).hexdigest()==pins[relative], name
assert not any(n=='gala' or n.startswith('gala.') for n in sys.modules), 'numerical runtime import'
print(json.dumps(result,sort_keys=True,separators=(',',':'),allow_nan=False))
'''


def _execute(root, profile):
    if os.name == 'nt':
        # wslpath translates only the exclusively created temporary directory.
        translated = subprocess.run(['wsl.exe','--exec','/usr/bin/wslpath','-a','-u',str(root)],
            capture_output=True, text=True, timeout=30)
        _require(translated.returncode == 0, 'WSL path conversion unavailable: ' + translated.stderr[-1000:])
        path = translated.stdout.strip()
        _require(path.startswith('/mnt/') and '\n' not in path, 'single mounted replay root')
        command = ['wsl.exe','--exec','/usr/bin/python3','-I','-B','-S','-c',_REPLAY,path]
    else:
        command = [sys.executable,'-I','-B','-S','-c',_REPLAY,str(root)]
    process = subprocess.run(command, input=_canonical(profile), capture_output=True,
                             cwd=root, timeout=180)
    _require(process.returncode == 0, 'isolated old full replay: ' + process.stderr.decode('utf-8',errors='replace')[-3000:])
    _require(len(process.stdout) <= 1048576, 'bounded replay result')
    return _json(process.stdout)


def verify_historical_profile(profile, repo_root):
    """Return the exact verified old manifest after full gate + eight negatives.

    No source/evidence edits, profile status updates, or authority over current
    EVEX semantics occur. The temporary replay inputs are exclusive byte copies.
    """
    try:
        _require(type(profile) is dict and _sha(_canonical(profile)) == OLD_PROFILE,
                 'exact old registered profile/receipt required')
        payload = _payload(repo_root)
        with tempfile.TemporaryDirectory(prefix='compute-historical-old-source-') as directory:
            root = Path(directory)
            for relative, raw in payload.items():
                target = root / relative; target.parent.mkdir(parents=True, exist_ok=True)
                with target.open('xb') as stream:
                    stream.write(raw)
            pins = {relative: _sha(raw) for relative, raw in payload.items()}
            with (root / 'isolated-inputs.json').open('xb') as stream:
                stream.write(_canonical(pins))
            result = _execute(root, profile)
        _require(_canonical(result) == _canonical(profile), 'old gate result/receipt drift')
        return result
    except (OSError, subprocess.SubprocessError, TypeError, KeyError) as exc:
        raise ValueError('REFUSED: historical profile ' + str(exc)) from exc
