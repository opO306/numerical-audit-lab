"""GCP Linux permission behavior; no Gala and no numerical execution."""
import json
import os
from pathlib import PurePosixPath
import subprocess
import sys
from unittest.mock import Mock

import pytest

from compute_metabolism.v0 import system_guard as guard
from compute_metabolism.v0.profiles import get_profile


def created(tmp_path):
    # Parent traversal is unrelated to the run-directory write contract.
    tmp_path.chmod(0o755)
    for p in tmp_path.parents:
        if p.name.startswith('pytest-'):
            p.chmod(0o755)
    path = tmp_path / 'run'
    path.mkdir(mode=0o755)
    (path / 'writer_quota.txt').write_bytes(b'0')
    return path


def as_identity(path, uid, gid, code):
    argv = ['sudo', '-n', 'setpriv', '--reuid', str(uid), '--regid', str(gid),
            '--clear-groups', '/usr/bin/python3', '-B', '-c', code, str(path)]
    return subprocess.run(argv, capture_output=True, text=True, timeout=10)


def test_root_created_artifacts_become_private_worker_writable(tmp_path):
    path = created(tmp_path)
    subprocess.run(['sudo', '-n', 'chown', '0:0', str(path), str(path/'writer_quota.txt')], check=True)
    # This reproduces the actual root:root 0755 directory from the failed run.
    code = ('from pathlib import Path;from compute_metabolism.v0 import system_guard as g;'
            'import json,sys;print(json.dumps(g.prepare_artifact_ownership(Path(sys.argv[1]))))')
    prepared = subprocess.run(['sudo', '-n', sys.executable, '-B', '-c', code, str(path)],
                              capture_output=True, text=True, timeout=10)
    assert prepared.returncode == 0, prepared.stderr
    assert (path.stat().st_uid, path.stat().st_gid, path.stat().st_mode & 0o777) == (1000, 1003, 0o700)
    quota = path/'writer_quota.txt'
    assert (quota.stat().st_uid, quota.stat().st_gid, quota.stat().st_mode & 0o777) == (1000, 1003, 0o600)
    args = guard.build_systemd_run_argv(get_profile('2c'), unit_name='compute-metabolism-owned.service',
        artifact_dir=PurePosixPath('/workspace/compute_metabolism/v0/artifacts/run'), command=['/bin/true'])
    assert '--uid=1000' in args and '--gid=1003' in args
    worker = as_identity(path, 1000, 1003,
        "from pathlib import Path;import sys;p=Path(sys.argv[1]);"
        "(p/'writer_quota.txt').write_bytes(b'7');(p/'guard-cgroup-before.json').write_bytes(b'{}')")
    assert worker.returncode == 0, worker.stderr
    assert quota.read_bytes() == b'7' and (path/'guard-cgroup-before.json').read_bytes() == b'{}'
    foreign = as_identity(path, 65534, 65534,
        "from pathlib import Path;import sys;(Path(sys.argv[1])/'unauthorized').write_bytes(b'x')")
    assert foreign.returncode != 0 and 'PermissionError' in foreign.stderr
    assert not (path/'unauthorized').exists()


@pytest.mark.parametrize('which', ['directory', 'quota'])
def test_wrong_uid_gid_is_refused(tmp_path, which):
    path = created(tmp_path)
    guard.prepare_artifact_ownership(path)
    target = path if which == 'directory' else path/'writer_quota.txt'
    subprocess.run(['sudo', '-n', 'chown', '0:0', str(target)], check=True)
    try:
        with pytest.raises(ValueError, match='ownership'):
            guard.validate_artifact_ownership(path)
    finally:
        subprocess.run(['sudo', '-n', 'chown', '1000:1003', str(target)], check=True)


def outer_paths(tmp_path):
    root = tmp_path/'rootfs'
    path = root/'workspace/compute_metabolism/v0/artifacts/run'
    path.parent.mkdir(parents=True)
    return root, path


def test_permission_preparation_failure_prevents_system_unit_launch(tmp_path, monkeypatch):
    root, path = outer_paths(tmp_path)
    launch = Mock(side_effect=AssertionError('system unit must not start'))
    monkeypatch.setattr(guard.subprocess, 'Popen', launch)
    monkeypatch.setattr(guard.os, 'chmod', Mock(side_effect=PermissionError('TEST_ONLY chmod failure')))
    with pytest.raises(PermissionError):
        guard.run_system_guard(get_profile('2c'), run_id='run', artifact_dir=path,
            command=['/bin/true'], topology={}, root_directory=root)
    assert not launch.called


def test_failed_owner_change_prevents_system_unit_launch(tmp_path, monkeypatch):
    root, path = outer_paths(tmp_path)
    # Force a mismatched identity without requiring a root pytest process.
    monkeypatch.setattr(guard, 'SYSTEM_UNIT_IDENTITY', guard.UnitExecutionIdentity(12345, 12345))
    monkeypatch.setattr(guard.os, 'chown', Mock(side_effect=PermissionError('TEST_ONLY chown failure')))
    launch = Mock(side_effect=AssertionError('system unit must not start'))
    monkeypatch.setattr(guard.subprocess, 'Popen', launch)
    with pytest.raises(PermissionError):
        guard.run_system_guard(get_profile('2c'), run_id='run', artifact_dir=path,
            command=['/bin/true'], topology={}, root_directory=root)
    assert not launch.called


@pytest.mark.parametrize('option', ['--uid=1000', '--gid=1003'])
def test_unit_uid_gid_cannot_diverge_from_artifact_owner(tmp_path, monkeypatch, option):
    root, path = outer_paths(tmp_path)
    builder = guard.build_systemd_run_argv
    def wrong(*args, **kwargs):
        return [option.split('=')[0]+'=12345' if x == option else x for x in builder(*args, **kwargs)]
    monkeypatch.setattr(guard, 'build_systemd_run_argv', wrong)
    launch = Mock(side_effect=AssertionError('system unit must not start'))
    monkeypatch.setattr(guard.subprocess, 'Popen', launch)
    with pytest.raises(ValueError, match='execution identity'):
        guard.run_system_guard(get_profile('2c'), run_id='run', artifact_dir=path,
            command=['/bin/true'], topology={}, root_directory=root)
    assert not launch.called


def test_successful_chown_return_without_changed_owner_is_refused(tmp_path, monkeypatch):
    root, path = outer_paths(tmp_path)
    monkeypatch.setattr(guard, 'SYSTEM_UNIT_IDENTITY', guard.UnitExecutionIdentity(12345, 12345))
    monkeypatch.setattr(guard.os, 'chown', Mock(return_value=None))
    launch = Mock(side_effect=AssertionError('system unit must not start'))
    monkeypatch.setattr(guard.subprocess, 'Popen', launch)
    with pytest.raises(ValueError, match='ownership'):
        guard.run_system_guard(get_profile('2c'), run_id='run', artifact_dir=path,
            command=['/bin/true'], topology={}, root_directory=root)
    assert not launch.called


@pytest.fixture(autouse=True)
def isolate_ownership_before_a_manager(monkeypatch):
    # These tests reject ownership before any unit can launch; the A authority
    # boundary is independently exercised by test_compute_metabolism_a_guard.
    from compute_metabolism.v0 import cgroup_noescape_policy
    monkeypatch.setattr(cgroup_noescape_policy,'validate_authority',lambda *args: None)
