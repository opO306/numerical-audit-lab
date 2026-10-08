"""Explicit source amendment admits current code without rewriting preparation."""
import copy
import hashlib
import importlib
import io
from pathlib import Path
import subprocess
import tarfile

import pytest

from verified_driver.v1.model import content_id
from verified_driver.v1.live_chain.session import live_source_snapshot
from verified_driver.v0.gate import source_snapshot

ROOT = Path(__file__).resolve().parents[1]
OLD = 'f75980706aefbbd68cddce09549695c2f633905e01185f92f96660db81a9e2cd'
ARCHIVE = f'compute_metabolism/v0/source_epochs/{OLD}/source'


def api():
    try:
        return importlib.import_module('compute_metabolism.v0.source_epoch')
    except ModuleNotFoundError:
        pytest.fail('explicit source epoch admission is not implemented')


@pytest.fixture(scope='session')
def immutable_sources():
    current = live_source_snapshot(ROOT)
    old_paths = [path for path in current if not path.startswith('verified_driver/v1/native_evex')]
    runtime_paths = [path.replace('\\', '/') for path in source_snapshot(ROOT)['runtime']]
    archived = subprocess.check_output(['git', 'archive', '--format=tar', 'HEAD',
        *sorted(set(old_paths) | set(runtime_paths))], cwd=ROOT)
    with tarfile.open(fileobj=io.BytesIO(archived)) as archive:
        blobs = {path: archive.extractfile(path).read() for path in set(old_paths) | set(runtime_paths)}
    old = {path: blobs[path] for path in old_paths}
    snapshot = {path: hashlib.sha256(raw).hexdigest() for path, raw in old.items()}
    assert len(snapshot) == 40 and content_id(snapshot) == OLD
    protected = {path: blobs[path] for path in runtime_paths}
    return old, snapshot, protected


@pytest.fixture
def fixture(tmp_path, immutable_sources):
    old, predecessor, protected = immutable_sources
    for relative, raw in {**protected, **old}.items():
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(raw)
    for relative, raw in old.items():
        destination = tmp_path / ARCHIVE / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(raw)
    (tmp_path / 'verified_driver/v1/live_chain/raw.py').write_bytes(b'# TEST_ONLY reviewed V1 dispatch amendment\n')
    (tmp_path / 'verified_driver/v1/native_evex_producer.py').write_bytes(b'# TEST_ONLY native producer bytes\n')
    current = live_source_snapshot(tmp_path)
    epoch = dict(schema='COMPUTE_METABOLISM_SOURCE_EPOCH_V1', predecessor_binding=OLD,
        predecessor_snapshot=copy.deepcopy(predecessor), source_snapshot=current,
        source_binding=content_id(current), source_count=len(current),
        source_amendment='2026-10-07-native-evex-semantics', historical_source_archive=ARCHIVE,
        review_sha256='a' * 64, regression_sha256='b' * 64)
    prepared = dict(python='3.12.3 prepared version', executable='/prepared/bin/python',
        packages={'gala': '1.12.0', 'numpy': '2.5.3'}, files={'/prepared/python': 'c' * 64},
        source_count=40, source_binding=OLD, source_matches=True,
        platform='prepared platform', cpu_affinity=[0, 1])
    runtime = {key: copy.deepcopy(prepared[key]) for key in ['python', 'executable', 'packages', 'files']}
    runtime.update(source_count=len(current), source_binding=content_id(current), source_matches=True,
                   platform='platform remains existing campaign responsibility')
    environment = dict(runtime=runtime, source_snapshot=copy.deepcopy(current), evidence_scope='LIVE')
    return tmp_path, epoch, prepared, environment


def refresh(root, epoch, environment=None):
    current = live_source_snapshot(root)
    epoch.update(source_snapshot=current, source_binding=content_id(current), source_count=len(current))
    if environment is not None:
        environment['source_snapshot'] = copy.deepcopy(current)
        environment['runtime'].update(source_binding=content_id(current), source_count=len(current))


def test_current_new_binding_admitted_with_immutable_40_source_preparation(fixture):
    root, epoch, prepared, environment = fixture
    frozen = copy.deepcopy((epoch, prepared, environment))
    current, binding = api().validate_epoch(epoch, root)
    assert current == epoch['source_snapshot']
    assert binding == epoch['source_binding'] != OLD
    assert len(current) == 41
    assert api().validate_environment_identity(environment, prepared, epoch, root) is None
    assert (epoch, prepared, environment) == frozen
    current['tamper-after-return'] = 'c' * 64
    assert 'tamper-after-return' not in epoch['source_snapshot']


@pytest.mark.parametrize('name', ['raw.py', 'gdb_live.py', 'producer.py', 'checker.py'])
def test_finite_reviewed_existing_V1_amendments_allowed(fixture, name):
    root, epoch, prepared, environment = fixture
    (root / 'verified_driver/v1/live_chain' / name).write_bytes(b'# TEST_ONLY explicit reviewed amendment\n')
    refresh(root, epoch, environment)
    api().validate_environment_identity(environment, prepared, epoch, root)


@pytest.mark.parametrize('name', ['native_evex_checker.py', 'native_evex_capture.py',
    'native_evex_graph_producer.py', 'native_evex_graph_checker.py', 'native_evex_raw.py',
    'native_evex_collector.py', 'native_evex_profile.py', 'native_evex_block.py'])
def test_finite_new_native_files_allowed_with_exact_epoch_binding(fixture, name):
    root, epoch, _, _ = fixture
    (root / 'verified_driver/v1' / name).write_bytes(b'# TEST_ONLY fresh reviewed bytes\n')
    refresh(root, epoch)
    assert api().validate_epoch(epoch, root)[0] == epoch['source_snapshot']


@pytest.mark.parametrize('relative', ['runtime_trace/semantics.py', 'lab/v2_bound.py',
    'independent_checker/oracle.py', 'verified_driver/v1/gate.py',
    'verified_driver/v1/live_chain/session.py', 'runtime_trace/numeric_ir/translator.py'])
def test_changed_unapproved_existing_source_refuses_even_after_rebinding(fixture, relative):
    root, epoch, _, _ = fixture
    with (root / relative).open('ab') as output:
        output.write(b'\n# drift\n')
    refresh(root, epoch)
    with pytest.raises(ValueError):
        api().validate_epoch(epoch, root)


@pytest.mark.parametrize('relative', ['verified_driver/v1/unrelated.py',
    'verified_driver/v1/native_evex_unreviewed.py', 'verified_driver/v1/live_chain/unrelated.py',
    'verified_driver/v1/new_namespace/unrelated.py', 'runtime_trace/new_semantics.py'])
def test_arbitrary_new_source_refuses(fixture, relative):
    root, epoch, _, _ = fixture
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b'# unreviewed source\n')
    refresh(root, epoch)
    with pytest.raises(ValueError):
        api().validate_epoch(epoch, root)


def test_all_40_archived_source_bytes_are_rechecked(fixture):
    root, epoch, _, _ = fixture
    path = root / ARCHIVE / 'verified_driver/v1/live_chain/raw.py'
    path.write_bytes(b'# modified historical source\n')
    with pytest.raises(ValueError, match='archive'):
        api().validate_epoch(epoch, root)


def test_missing_archive_or_unchanged_historical_binding_is_not_new_epoch(fixture):
    root, epoch, _, _ = fixture
    (root / ARCHIVE / 'verified_driver/v1/model.py').unlink()
    with pytest.raises(ValueError):
        api().validate_epoch(epoch, root)


@pytest.mark.parametrize('field,value', [
    ('schema','other'), ('predecessor_binding','0' * 64),
    ('source_binding',OLD), ('source_count',40), ('source_count',True),
    ('source_amendment','arbitrary-amendment'), ('historical_source_archive','../outside'),
    ('review_sha256','A' * 64), ('review_sha256',True), ('regression_sha256','PASS'),
])
def test_epoch_schema_count_binding_and_review_hashes_strict(fixture, field, value):
    root, epoch, _, _ = fixture
    epoch[field] = value
    with pytest.raises(ValueError):
        api().validate_epoch(epoch, root)


@pytest.mark.parametrize('attack', ['predecessor_snapshot', 'extra_field', 'snapshot_hash',
    'source_after_freeze', 'no_epoch', 'old40_environment'])
def test_frozen_epoch_and_snapshot_drift_refuse(fixture, attack):
    root, epoch, prepared, environment = fixture
    if attack == 'predecessor_snapshot': epoch['predecessor_snapshot']['verified_driver/v1/gate.py'] = '0' * 64
    if attack == 'extra_field': epoch['PASS'] = True
    if attack == 'snapshot_hash': epoch['source_snapshot']['verified_driver/v1/native_evex_producer.py'] = '0' * 64
    if attack == 'source_after_freeze': (root / 'verified_driver/v1/native_evex_producer.py').write_bytes(b'# later mutation\n')
    if attack == 'no_epoch': epoch = None
    if attack == 'old40_environment': environment['runtime'].update(source_count=40,source_binding=OLD)
    with pytest.raises(ValueError):
        api().validate_environment_identity(environment, prepared, epoch, root)


@pytest.mark.parametrize('field', ['python', 'executable', 'packages', 'files',
    'source_binding', 'source_count', 'source_matches', 'source_snapshot'])
def test_environment_runtime_package_binary_and_source_drift_refuse(fixture, field):
    root, epoch, prepared, environment = fixture
    if field == 'source_snapshot': environment['source_snapshot'] = epoch['predecessor_snapshot']
    elif field == 'packages': environment['runtime'][field]['numpy'] = 'changed'
    elif field == 'files': environment['runtime'][field]['/prepared/python'] = 'd' * 64
    elif field == 'source_matches': environment['runtime'][field] = 1
    elif field == 'source_count': environment['runtime'][field] = 40
    else: environment['runtime'][field] = 'changed'
    with pytest.raises(ValueError):
        api().validate_environment_identity(environment, prepared, epoch, root)


@pytest.mark.parametrize('field,value', [('source_count',41), ('source_count',True),
    ('source_binding','d' * 64), ('source_matches',1)])
def test_prepared_old_provenance_cannot_be_relabeled_current(fixture, field, value):
    root, epoch, prepared, environment = fixture
    prepared[field] = value
    with pytest.raises(ValueError):
        api().validate_environment_identity(environment, prepared, epoch, root)


def test_complete_package_and_binary_sets_exact(fixture):
    root, epoch, prepared, environment = fixture
    environment['runtime']['packages']['unprepared-extra'] = '1.0'
    with pytest.raises(ValueError):
        api().validate_environment_identity(environment, prepared, epoch, root)
    environment['runtime']['packages'] = copy.deepcopy(prepared['packages'])
    environment['runtime']['files']['/extra/binary'] = 'd' * 64
    with pytest.raises(ValueError):
        api().validate_environment_identity(environment, prepared, epoch, root)


def test_historical_archive_extra_file_refuses(fixture):
    root, epoch, _, _ = fixture
    (root / ARCHIVE / 'unbound-extra.py').write_bytes(b'# extra historical file\n')
    with pytest.raises(ValueError, match='archive'):
        api().validate_epoch(epoch, root)


def test_historical_archive_hardlink_alias_refuses(fixture):
    import os
    root, epoch, _, _ = fixture
    archived = root / ARCHIVE / 'verified_driver/v1/model.py'
    os.link(archived, root / 'external-archive-alias.py')
    with pytest.raises(ValueError, match='archive/source'):
        api().validate_epoch(epoch, root)
