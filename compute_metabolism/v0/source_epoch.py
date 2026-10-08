"""Read-only admission of one explicit V1 source epoch amendment.

The prepared runtime remains the immutable old 40-source/f759 identity. This
module admits a separately frozen current source snapshot; it does not alter
old receipts, confer numerical/profile authority, or interpret review PASS
labels. Review/regression hashes identify external evidence whose substantive
verification belongs to the caller. Runtime environment fields here are the
caller-acquired identities, compared exactly with the prepared identity.
"""
from copy import deepcopy
import hashlib
import os
from pathlib import Path, PurePosixPath
import re
import stat

from verified_driver.v0.gate import source_snapshot as protected_snapshot
from verified_driver.v1.live_chain.session import live_source_snapshot
from verified_driver.v1.model import canonical_bytes, content_id, digest_bytes


PREDECESSOR_BINDING = 'f75980706aefbbd68cddce09549695c2f633905e01185f92f96660db81a9e2cd'
PROTECTED_RUNTIME_PINSET = 'c949e61b420696f9ecfc61608d8e0e13be5f12a965e1e103f40ea2941689ddb3'
SOURCE_AMENDMENT = '2026-10-07-native-evex-semantics'
HISTORICAL_SOURCE_ARCHIVE = f'compute_metabolism/v0/source_epochs/{PREDECESSOR_BINDING}/source'
CHANGED_EXISTING_PATHS = frozenset('verified_driver/v1/live_chain/' + name
    for name in ('raw.py', 'gdb_live.py', 'producer.py', 'checker.py'))
NEW_NATIVE_PATHS = frozenset('verified_driver/v1/' + name for name in (
    'native_evex_producer.py', 'native_evex_checker.py', 'native_evex_capture.py',
    'native_evex_graph_producer.py', 'native_evex_graph_checker.py',
    'native_evex_raw.py', 'native_evex_collector.py', 'native_evex_profile.py', 'native_evex_block.py'))
_EPOCH_KEYS = {'schema', 'predecessor_binding', 'predecessor_snapshot', 'source_snapshot',
    'source_binding', 'source_count', 'source_amendment', 'historical_source_archive',
    'review_sha256', 'regression_sha256'}


def _require(condition, reason):
    if not condition:
        raise ValueError('REFUSED: source epoch ' + reason)


def _hash(value, label):
    _require(type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None,
             'strict SHA256 ' + label)


def _relative(value):
    _require(type(value) is str and value and '\\' not in value and ':' not in value,
             'canonical relative source path')
    path = PurePosixPath(value)
    _require(not path.is_absolute() and all(part not in ('.', '..') for part in value.split('/'))
             and path.as_posix() == value, 'canonical relative source path')
    return path


def _safe_path(path):
    absolute = Path(os.path.abspath(path))
    for parent in reversed((absolute, *absolute.parents)):
        info = parent.lstat()
        _require(not stat.S_ISLNK(info.st_mode) and not getattr(info, 'st_file_attributes', 0) & 0x400,
                 'archive/source alias refused: ' + str(parent))
    return absolute


def _regular_bytes(path):
    path = _safe_path(path)
    info = path.lstat()
    _require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1,
             'archive/source must be unaliased regular file: ' + str(path))
    return path.read_bytes()


def _inventory(directory, *, excluded=()):
    directory = _safe_path(directory)
    _require(directory.is_dir(), 'archive/source directory unavailable')
    result = set()
    for folder, directories, files in os.walk(directory, followlinks=False):
        if Path(folder) == directory:
            directories[:] = [name for name in directories if name not in excluded]
        for name in directories:
            _safe_path(Path(folder) / name)
        for name in files:
            item = Path(folder) / name
            _safe_path(item)
            result.add(item.relative_to(directory).as_posix())
    return result


def _snapshot(value, label):
    _require(type(value) is dict and value, 'complete ' + label)
    for relative, digest in value.items():
        _relative(relative)
        _hash(digest, label + ' ' + relative)


def _validate_epoch(epoch, repo_root):
    _require(type(epoch) is dict and set(epoch) == _EPOCH_KEYS, 'exact epoch schema required')
    _require(epoch['schema'] == 'COMPUTE_METABOLISM_SOURCE_EPOCH_V1', 'schema mismatch')
    _require(epoch['predecessor_binding'] == PREDECESSOR_BINDING, 'immutable predecessor binding')
    _require(epoch['source_amendment'] == SOURCE_AMENDMENT, 'unreviewed source amendment')
    _require(epoch['historical_source_archive'] == HISTORICAL_SOURCE_ARCHIVE, 'immutable archive path')
    _hash(epoch['review_sha256'], 'review receipt')
    _hash(epoch['regression_sha256'], 'regression receipt')
    _hash(epoch['source_binding'], 'current binding')
    predecessor, supplied = epoch['predecessor_snapshot'], epoch['source_snapshot']
    _snapshot(predecessor, 'predecessor snapshot')
    _snapshot(supplied, 'current snapshot')
    _require(len(predecessor) == 40 and content_id(predecessor) == PREDECESSOR_BINDING,
             'actual immutable 40-source predecessor snapshot')
    _require(type(epoch['source_count']) is int and epoch['source_count'] == len(supplied),
             'strict current source count')
    _require(epoch['source_binding'] == content_id(supplied) and epoch['source_binding'] != PREDECESSOR_BINDING,
             'exact fresh current source binding')
    _require(set(predecessor) <= set(supplied), 'old source paths cannot disappear')
    added = set(supplied) - set(predecessor)
    _require(added and added <= NEW_NATIVE_PATHS,
             'new source path outside finite reviewed native allowlist')
    changed = {relative for relative in predecessor if predecessor[relative] != supplied[relative]}
    _require(changed <= CHANGED_EXISTING_PATHS, 'changed existing source outside reviewed V1 allowance')
    root = _safe_path(repo_root)
    archive = root / HISTORICAL_SOURCE_ARCHIVE
    _require(_inventory(archive) == set(predecessor), 'archive must contain exactly all 40 predecessor files')
    for relative, want in predecessor.items():
        _require(digest_bytes(_regular_bytes(archive / relative)) == want,
                 'archive bytes changed: ' + relative)
    runtime = {relative.replace('\\', '/'): digest for relative, digest in protected_snapshot(root)['runtime'].items()}
    _require(len(runtime) == 89 and
             hashlib.sha256(canonical_bytes(runtime) + b'\n').hexdigest() == PROTECTED_RUNTIME_PINSET,
             'protected Runtime Trace 89-file pinset changed')
    for relative, want in runtime.items():
        _require(digest_bytes(_regular_bytes(root / relative)) == want,
                 'protected Runtime source changed during admission: ' + relative)
    # Reject Python files outside the live source snapshot's two V1 globs too.
    v1_inventory = {'verified_driver/v1/' + relative for relative in
        _inventory(root / 'verified_driver/v1', excluded=('artifacts',))
        if relative.lower().endswith('.py')}
    expected_v1 = {relative for relative in supplied if relative.startswith('verified_driver/v1/')}
    _require(v1_inventory == expected_v1, 'unbound additional V1 Python source')
    current = live_source_snapshot(root)
    _require(current == supplied and content_id(current) == epoch['source_binding'],
             'current complete source snapshot drift')
    for relative, want in current.items():
        _require(digest_bytes(_regular_bytes(root / relative)) == want, 'source changed during admission: ' + relative)
    return deepcopy(current), content_id(current)


def validate_epoch(epoch, repo_root):
    """Return (current_snapshot, binding); performs no writes or authorization.

    The caller must hash-bind the epoch document before any attempt and verify
    its review/regression receipts independently. This API only admits source
    identity under the fixed amendment and preserved historical preparation.
    """
    try:
        return _validate_epoch(epoch, repo_root)
    except (KeyError, TypeError, OSError) as exc:
        raise ValueError('REFUSED: source epoch unavailable/incomplete evidence: ' + str(exc)) from exc


def _identity_map(value, label, *, digests=False):
    _require(type(value) is dict and value, 'complete prepared ' + label)
    for key, item in value.items():
        _require(type(key) is str and key and type(item) is str and item, 'strict prepared ' + label)
        if digests:
            _hash(item, label + ' ' + key)


def validate_environment_identity(environment, prepared_identity, epoch, repo_root):
    """Compare newly acquired environment with old prepared runtime + new epoch.

    Python/executable/package/binary identities must equal preparation exactly;
    source identity must equal the independently rechecked epoch. Platform,
    topology, resource, freshness, acquisition, and numerical checks remain in
    their existing campaign gates. No historical PASS is reclassified here.
    """
    try:
        current, binding = validate_epoch(epoch, repo_root)
        prepared = prepared_identity
        _require(type(prepared) is dict and type(prepared['source_count']) is int and
                 prepared['source_count'] == 40 and prepared['source_binding'] == PREDECESSOR_BINDING and
                 prepared['source_matches'] is True, 'prepared provenance must remain old 40/f759 identity')
        for name in ('python', 'executable'):
            _require(type(prepared[name]) is str and prepared[name], 'complete prepared ' + name)
        _identity_map(prepared['packages'], 'packages')
        _identity_map(prepared['files'], 'binary files', digests=True)
        _require(type(environment) is dict and type(environment['runtime']) is dict,
                 'complete newly acquired environment runtime')
        runtime = environment['runtime']
        for name in ('python', 'executable', 'packages', 'files'):
            _require(runtime[name] == prepared[name], 'runtime identity drift: ' + name)
        _require(type(runtime['source_count']) is int and runtime['source_count'] == len(current) and
                 runtime['source_binding'] == binding and runtime['source_matches'] is True,
                 'current environment count/binding/match must equal epoch')
        _require(environment['source_snapshot'] == current, 'current environment source snapshot mismatch')
    except (KeyError, TypeError, OSError) as exc:
        raise ValueError('REFUSED: source epoch incomplete environment identity: ' + str(exc)) from exc
