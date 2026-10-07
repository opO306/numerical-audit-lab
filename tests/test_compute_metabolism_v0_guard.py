"""Guard tests use fake controller files and mocked subprocesses only."""
import copy
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
from unittest.mock import Mock

import pytest


@pytest.fixture
def guard():
    from compute_metabolism.v0 import system_guard
    return system_guard


@pytest.fixture
def tree(tmp_path, monkeypatch, guard):
    root = tmp_path / 'cgroup'
    parent = root / 'system.slice'
    unit = parent / 'compute-metabolism-test.service'
    unit.mkdir(parents=True)
    monkeypatch.setattr(guard, 'CGROUP_ROOT', root)
    for path in (unit, parent):
        for name, raw in {'cpu.max': 'max 100000\n', 'memory.max': '4294967296\n',
                          'memory.swap.max': '0\n'}.items():
            (path / name).write_text(raw)
    for name, raw in {'cpuset.cpus.effective': '0-1\n',
                      'cpu.stat': 'usage_usec 10\nuser_usec 7\nsystem_usec 3\nnr_periods 1\nnr_throttled 0\nthrottled_usec 0\n',
                      'memory.current': '42\n', 'memory.peak': '99\n',
                      'memory.events': 'low 0\nhigh 0\nmax 0\noom 0\noom_kill 0\n',
                      'cgroup.procs': str(os.getpid()) + '\n', 'cgroup.events': 'populated 1\nfrozen 0\n'}.items():
        (unit / name).write_text(raw)
    monkeypatch.setattr(guard, '_boot_id', lambda: 'test-boot')
    monkeypatch.setattr(guard, '_process_identity', lambda pid: {'pid': pid, 'start_ticks': '42'})
    return root, parent, unit


def topology():
    return {'0': {'physical_package_id': '0', 'core_id': '0'},
            '1': {'physical_package_id': '0', 'core_id': '1'}}


@pytest.mark.parametrize('key, cpus', [('2c', '0,1'), ('1c', '0'), ('0p5c', '0')])
def test_builder_enforces_exact_unit_and_namespace(guard, key, cpus):
    from compute_metabolism.v0.profiles import get_profile
    args = guard.build_systemd_run_argv(get_profile(key), unit_name='compute-metabolism-test.service',
        artifact_dir=PurePosixPath('/workspace/compute_metabolism/v0/artifacts/test'), command=['/bin/true'])
    for value in ['sudo', '-n', 'systemd-run', '--quiet', '--wait', '--pipe', '--collect',
                  '--uid=1000', '--gid=1003', '--property=WorkingDirectory=/workspace',
                  '--property=MemoryMax=4294967296', '--property=MemorySwapMax=0',
                  '--property=CPUAccounting=yes', '--property=MemoryAccounting=yes',
                  '--property=RuntimeMaxSec=180s', '--property=KillMode=control-group',
                  '--property=OOMPolicy=kill', '--property=MountAPIVFS=yes',
                  '--property=ReadOnlyPaths=/workspace /usr /home/otherside123 /reference',
                  '--property=ReadWritePaths=/workspace/compute_metabolism/v0/artifacts',
                  '--setenv=OMP_NUM_THREADS=1', '--setenv=OPENBLAS_NUM_THREADS=1',
                  '--setenv=RTN_QUOTA_BYTES=671088640', '--setenv=PYTHONDONTWRITEBYTECODE=1',
                  '--setenv=LC_ALL=C.UTF-8', '--setenv=HOME=/home/zun24']:
        assert value in args
    assert '--property=AllowedCPUs=' + cpus in args
    assert '--property=RootDirectory=/home/zun24/compute-metabolism-v0-prepared-20261006/rootfs' in args
    assert '--setenv=RTN_QUOTA_FILE=/workspace/compute_metabolism/v0/artifacts/test/writer_quota.txt' in args
    assert '-m' in args and 'compute_metabolism.v0.system_guard' in args
    if key == '0p5c':
        assert '--property=CPUQuota=50%' in args
        assert '--property=CPUQuotaPeriodSec=100ms' in args
    else:
        assert not any('CPUQuota' in arg for arg in args)


def test_builder_rejects_arbitrary_profiles_and_escape(guard):
    from compute_metabolism.v0.profiles import ProfileSpec, get_profile
    with pytest.raises(ValueError):
        guard.build_systemd_run_argv(ProfileSpec('1c', (1,), None, None), unit_name='compute-metabolism-test.service',
            artifact_dir=PurePosixPath('/workspace/compute_metabolism/v0/artifacts/test'), command=['true'])
    with pytest.raises(ValueError):
        guard.build_systemd_run_argv(get_profile('1c'), unit_name='compute-metabolism-test.service',
            artifact_dir=PurePosixPath('/workspace/compute_metabolism/v0/artifacts/../escape'), command=['true'])


def test_missing_unit_cpu_max_uses_parent_with_raw_boundary(tree, guard):
    root, parent, unit = tree
    (unit / 'cpu.max').unlink()
    result = guard.resolve_effective_cpu_max(unit)
    assert result['source'] == str(parent / 'cpu.max')
    assert result['raw'] == 'max 100000\n'
    assert result['quota_usec'] is None
    assert result['scan_root'] == str(root)
    assert result['ancestors'][-1]['missing_at_root'] is True


@pytest.mark.parametrize('key', ['2c', '1c'])
def test_finite_ancestor_rejected_even_below_unlimited_parent(tree, guard, key):
    from compute_metabolism.v0.profiles import get_profile
    root, parent, unit = tree
    (root / 'cpu.max').write_text('80000 100000\n')
    if key == '1c':
        (unit / 'cpuset.cpus.effective').write_text('0\n')
    with pytest.raises(ValueError, match='CPU'):
        guard.validate_enforcement(get_profile(key), guard.read_cgroup_snapshot(unit), topology())


def test_strict_half_quota_and_raw_metrics(tree, guard):
    from compute_metabolism.v0.profiles import get_profile
    _, _, unit = tree
    (unit / 'cpu.max').write_text('50000 100000\n')
    (unit / 'cpuset.cpus.effective').write_text('0\n')
    snap = guard.read_cgroup_snapshot(unit)
    guard.validate_enforcement(get_profile('0p5c'), snap, topology())
    assert snap['raw']['cpu.max'] == '50000 100000\n'
    assert snap['raw']['memory.peak'] == '99\n'
    assert snap['cpu_stat']['usage_usec'] == 10


@pytest.mark.parametrize('file,raw', [('cpuset.cpus.effective', '0\n'), ('memory.max', '2147483648\n'),
    ('memory.swap.max', '1\n')])
def test_wrong_enforcement_refused(tree, guard, file, raw):
    from compute_metabolism.v0.profiles import get_profile
    _, _, unit = tree
    (unit / file).write_text(raw)
    with pytest.raises(ValueError):
        guard.validate_enforcement(get_profile('2c'), guard.read_cgroup_snapshot(unit), topology())


@pytest.mark.parametrize('file,raw', [('memory.max', '2147483648\n'), ('memory.swap.max', '1\n')])
def test_ancestor_memory_or_swap_envelope_mismatch_refused(tree, guard, file, raw):
    from compute_metabolism.v0.profiles import get_profile
    _, parent, unit = tree
    (parent / file).write_text(raw)
    if file == 'memory.swap.max':
        # Child swap0 remains exact effective0: permissive parent must be accepted.
        guard.validate_enforcement(get_profile('2c'), guard.read_cgroup_snapshot(unit), topology())
    else:
        with pytest.raises(ValueError, match='memory'):
            guard.validate_enforcement(get_profile('2c'), guard.read_cgroup_snapshot(unit), topology())


def test_missing_parent_limit_is_unknown(tree, guard):
    _, parent, unit = tree
    (parent / 'memory.max').unlink()
    with pytest.raises(ValueError, match='missing'):
        guard.read_cgroup_snapshot(unit)


def test_same_guest_core_refused(tree, guard):
    from compute_metabolism.v0.profiles import get_profile
    _, _, unit = tree
    topo = topology()
    topo['1']['core_id'] = '0'
    with pytest.raises(ValueError, match='core'):
        guard.validate_enforcement(get_profile('2c'), guard.read_cgroup_snapshot(unit), topo)


def test_epoch_reset_or_missing_counter_not_measured_as_zero(tree, guard):
    _, _, unit = tree
    before = guard.read_cgroup_snapshot(unit)
    after = copy.deepcopy(before)
    after['cpu_stat']['usage_usec'] = 9
    with pytest.raises(ValueError):
        guard.validate_snapshot_pair(before, after)
    after = copy.deepcopy(before)
    after['epoch']['inode'] += 1
    with pytest.raises(ValueError):
        guard.validate_snapshot_pair(before, after)
    (unit / 'memory.peak').unlink()
    with pytest.raises((OSError, ValueError)):
        guard.read_cgroup_snapshot(unit)


def setup_outer(tmp_path, monkeypatch, guard, returncode=0, timeout=False):
    rootfs = tmp_path / 'rootfs'
    artifact = rootfs / 'workspace/compute_metabolism/v0/artifacts/test'
    artifact.parent.mkdir(parents=True)
    process = Mock()
    process.returncode = returncode
    if timeout:
        process.wait.side_effect = [subprocess.TimeoutExpired('systemd-run', .1), 0]
    else:
        process.wait.return_value = returncode
    monkeypatch.setattr(guard.subprocess, 'Popen', Mock(return_value=process))
    monkeypatch.setattr(guard, '_stop_owned_unit', Mock(return_value={'terminal': True, 'commands': []}))
    monkeypatch.setattr(guard, '_unit_terminal', lambda unit, evidence=None: True)
    return rootfs, artifact, process


def test_outer_success_without_final_receipt_invalid(guard, tmp_path, monkeypatch):
    from compute_metabolism.v0.profiles import get_profile
    rootfs, artifact, _ = setup_outer(tmp_path, monkeypatch, guard)
    result = guard.run_system_guard(get_profile('2c'), run_id='test', artifact_dir=artifact,
        command=['/bin/true'], topology=topology(), root_directory=rootfs)
    assert result['outcome'] == 'ENVIRONMENT_INVALID'
    assert result['measurement_valid'] is False
    assert result['after'] is None
    assert (artifact / 'guard-outer.json').exists()
    assert (artifact / 'writer_quota.txt').read_text() == '0'


def test_outer_timeout_records_cleanup_time_and_missing_final_invalid(guard, tmp_path, monkeypatch):
    from compute_metabolism.v0.profiles import get_profile
    rootfs, artifact, process = setup_outer(tmp_path, monkeypatch, guard, timeout=True)
    times = iter([1.0, 1.0, 1.2, 2.5])
    monkeypatch.setattr(guard.time, 'monotonic', lambda: next(times))
    result = guard.run_system_guard_test_only_probe(get_profile('2c'), test_only_wall_seconds=.1,
        run_id='test', artifact_dir=artifact, command=['/bin/true'], topology=topology(), root_directory=rootfs)
    assert result['outer_timeout_proved'] is True
    assert result['wall_seconds'] == 1.5
    assert result['outcome'] == 'ENVIRONMENT_INVALID'
    assert process.wait.call_count == 2
    assert process.kill.called
    guard._stop_owned_unit.assert_called_once()


def test_campaign_api_cannot_override_timeout(guard):
    from compute_metabolism.v0.profiles import get_profile
    with pytest.raises(TypeError):
        guard.run_system_guard(get_profile('1c'), run_id='x', artifact_dir=Path('/tmp/x'),
            command=['true'], topology=topology(), test_only_wall_seconds=999)


def test_owned_unit_cleanup_targets_system_control_group_and_confirms_terminal(guard, monkeypatch):
    outputs = [subprocess.CompletedProcess([], 0, '', ''), subprocess.CompletedProcess([], 0, '', '')]
    run = Mock(side_effect=outputs)
    monkeypatch.setattr(guard.subprocess, 'run', run)
    monkeypatch.setattr(guard, '_unit_terminal', lambda unit, evidence=None: True)
    result = guard._stop_owned_unit('compute-metabolism-test.service')
    assert result['terminal'] is True
    assert '--kill-whom=main' in run.call_args_list[0].args[0]
    assert 'compute-metabolism-test.service' in run.call_args_list[0].args[0]


def test_inner_does_not_start_child_before_live_validation(tree, guard, tmp_path, monkeypatch):
    _, _, unit = tree
    (unit / 'cpuset.cpus.effective').write_text('7\n')
    monkeypatch.setattr(guard, 'current_cgroup_path', lambda: unit)
    monkeypatch.setattr(guard, 'read_cpu_topology', topology)
    monkeypatch.setattr(guard, '_enable_subreaper', lambda: None)
    popen = Mock()
    monkeypatch.setattr(guard.subprocess, 'Popen', popen)
    result = guard.run_inner(profile_key='2c', run_id='test', unit_name=unit.name,
        artifact_dir=tmp_path, command=['/bin/true'])
    assert result['outcome'] == 'ENVIRONMENT_INVALID'
    assert not popen.called


def test_inner_final_after_workers_drained(tree, guard, tmp_path, monkeypatch):
    _, _, unit = tree
    monkeypatch.setattr(guard, 'current_cgroup_path', lambda: unit)
    monkeypatch.setattr(guard, 'read_cpu_topology', topology)
    monkeypatch.setattr(guard, '_enable_subreaper', lambda: None)
    monkeypatch.setattr(guard, '_process_identity', lambda pid: {'pid': pid, 'start_ticks': '42'})
    process = Mock(pid=123, returncode=0)
    process.wait.return_value = 0
    monkeypatch.setattr(guard.subprocess, 'Popen', Mock(return_value=process))
    def drain(path, **kwargs):
        (unit / 'cpu.stat').write_text('usage_usec 30\nuser_usec 20\nsystem_usec 10\nnr_periods 2\nnr_throttled 1\nthrottled_usec 1\n')
        return {'remaining_pids': [], 'reaped_pids': [123]}
    monkeypatch.setattr(guard, '_drain_owned_children', drain)
    result = guard.run_inner(profile_key='2c', run_id='test', unit_name=unit.name,
        artifact_dir=tmp_path, command=['/bin/true'])
    assert result['after']['cpu_stat']['usage_usec'] == 30
    assert result['delta']['usage_usec'] == 20
    assert result['containment']['remaining_pids'] == []
    assert (tmp_path / 'guard-cgroup-final.json').exists()


def test_inner_cli_parses_options_before_child_argv(guard, tmp_path, monkeypatch):
    runner = Mock(return_value={'outcome': 'GUARD_COMPLETE', 'measurement_valid': True})
    monkeypatch.setattr(guard, 'run_inner', runner)
    assert guard.main(['inner', '--profile', '1c', '--unit', 'compute-metabolism-test.service',
        '--run-id', 'test', '--artifact-dir', '/workspace/compute_metabolism/v0/artifacts/test',
        '--', '/bin/echo', '--test-child-option']) == 0
    assert runner.call_args.kwargs['command'] == ['/bin/echo', '--test-child-option']


def test_unreaped_launcher_is_killed_and_reaped(guard, tmp_path, monkeypatch):
    from compute_metabolism.v0.profiles import get_profile
    rootfs, artifact, process = setup_outer(tmp_path, monkeypatch, guard, timeout=True)
    process.wait.side_effect = [subprocess.TimeoutExpired('systemd-run', .1),
                               subprocess.TimeoutExpired('systemd-run', 10),
                               subprocess.TimeoutExpired('systemd-run', 10), 0]
    result = guard.run_system_guard_test_only_probe(get_profile('2c'), test_only_wall_seconds=.01,
        run_id='test', artifact_dir=artifact, command=['true'], topology=topology(), root_directory=rootfs)
    assert process.kill.called
    assert result['launcher_reaped'] is True


@pytest.mark.parametrize('cleanup_error', [False, True])
def test_valid_outer_receipt_is_bound_and_counter_delta_used(tree, guard, tmp_path, monkeypatch, cleanup_error):
    from compute_metabolism.v0.profiles import get_profile
    _, _, unit = tree
    rootfs, artifact, process = setup_outer(tmp_path, monkeypatch, guard)
    if cleanup_error:
        monkeypatch.setattr(guard, '_unit_terminal', lambda unit, evidence=None: False)
        monkeypatch.setattr(guard, '_stop_owned_unit', Mock(return_value={
            'terminal': True, 'commands': [], 'errors': ['TERM timeout']}))
    def finish(timeout):
        argv = guard.subprocess.Popen.call_args.args[0]
        unit_name = next(arg.split('=', 1)[1] for arg in argv if arg.startswith('--unit='))
        renamed = unit.with_name(unit_name)
        unit.rename(renamed)
        before = guard.read_cgroup_snapshot(renamed)
        after = copy.deepcopy(before)
        after['cpu_stat']['usage_usec'] = 1000010
        record = {'run_id': 'test', 'unit': unit_name, 'profile': '2c', 'before': before,
            'after': after, 'measurement_valid': True, 'outcome': 'GUARD_COMPLETE',
            'wrapper_identity': {'pid': os.getpid(), 'start_ticks': '42'},
            'topology_before': topology(), 'topology_after': topology(),
            'containment': {'remaining_pids': [], 'reaped_pids': []}}
        (artifact / 'guard-cgroup-before.json').write_text(json.dumps({'before': before}))
        (artifact / 'guard-cgroup-final.json').write_text(json.dumps(record))
        return 0
    process.wait.side_effect = finish
    result = guard.run_system_guard(get_profile('2c'), run_id='test', artifact_dir=artifact,
        command=['true'], topology=topology(), root_directory=rootfs)
    if cleanup_error:
        assert result['outcome'] == 'ENVIRONMENT_INVALID'
        assert result['cleanup_attempts'][0]['errors'] == ['TERM timeout']
    else:
        assert result['outcome'] == 'GUARD_COMPLETE'
        assert result['delta']['cpu_seconds'] == 1
    assert result['launcher_reaped'] is True


def test_owned_cleanup_escalates_all_and_preserves_command_failures(guard, monkeypatch):
    monkeypatch.setattr(guard, '_unit_terminal', Mock(side_effect=[False, False, True]))
    run = Mock(return_value=subprocess.CompletedProcess([], 1, '', 'failed'))
    monkeypatch.setattr(guard.subprocess, 'run', run)
    clock_values = iter([0, 0, 3])
    monkeypatch.setattr(guard.time, 'monotonic', lambda: next(clock_values))
    monkeypatch.setattr(guard.time, 'sleep', lambda _: None)
    result = guard._stop_owned_unit('compute-metabolism-test.service')
    assert result['terminal'] is False  # two explicit termination checks both nonterminal
    assert '--kill-whom=all' in result['commands'][1]['argv']
    assert '--signal=SIGKILL' in result['commands'][1]['argv']
    assert result['commands'][0]['returncode'] == 1


def test_running_enforcement_drift_terminates_owned_child_and_invalidates(tree, guard, tmp_path, monkeypatch):
    _, _, unit = tree
    monkeypatch.setattr(guard, 'current_cgroup_path', lambda: unit)
    monkeypatch.setattr(guard, 'read_cpu_topology', topology)
    monkeypatch.setattr(guard, '_enable_subreaper', lambda: None)
    monkeypatch.setattr(guard, '_process_identity', lambda pid: {'pid': pid, 'start_ticks': '42'})
    process = Mock(pid=123, returncode=0)
    calls = []
    def wait(timeout=None):
        if timeout is not None and not calls:
            calls.append(True)
            (unit / 'cpuset.cpus.effective').write_text('7\n')
            raise subprocess.TimeoutExpired('child', .1)
        return -9
    process.wait.side_effect = wait
    monkeypatch.setattr(guard.subprocess, 'Popen', Mock(return_value=process))
    drained = []
    def drain(path, **kwargs):
        drained.append(kwargs['interrupted']())
        return {'remaining_pids': [], 'reaped_pids': [123]}
    monkeypatch.setattr(guard, '_drain_owned_children', drain)
    result = guard.run_inner(profile_key='2c', run_id='test', unit_name=unit.name,
        artifact_dir=tmp_path, command=['true'])
    assert result['outcome'] == 'ENVIRONMENT_INVALID'
    assert result['measurement_valid'] is False
    assert drained == [True]
    assert (tmp_path / 'guard-cgroup-running.jsonl').exists()


def test_snapshot_records_live_process_start_identity(tree, guard):
    _, _, unit = tree
    snap = guard.read_cgroup_snapshot(unit)
    assert snap['process_identities'][str(os.getpid())]['pid'] == os.getpid()
    assert snap['process_identities'][str(os.getpid())]['start_ticks'].isdigit()


def test_terminal_unit_proof_retains_raw_systemctl_state(guard, monkeypatch):
    raw = 'LoadState=not-found\nActiveState=inactive\nSubState=dead\nControlGroup=\n'
    monkeypatch.setattr(guard.subprocess, 'run', Mock(return_value=subprocess.CompletedProcess([], 0, raw, '')))
    evidence = []
    assert guard._unit_terminal('compute-metabolism-test.service', evidence=evidence)
    assert evidence[0]['stdout'] == raw
    assert evidence[0]['returncode'] == 0


def test_empty_cgroup_still_reaps_adopted_zombie(guard, tree, monkeypatch):
    _, _, unit = tree
    monkeypatch.setattr(guard, '_cgroup_pids', lambda path: [os.getpid()])
    waiter = Mock(side_effect=[(0, 0), (124, 0), ChildProcessError()])
    monkeypatch.setattr(guard.os, 'waitpid', waiter)
    monkeypatch.setattr(guard.os, 'WNOHANG', 1, raising=False)
    result = guard._drain_owned_children(unit)
    assert result['reaped_pids'] == [124]


def test_worker_exit_during_sampling_preserves_cgroup_authority(tree, guard, monkeypatch):
    _, _, unit = tree
    exited = []
    monkeypatch.setattr(guard, '_cgroup_pids', lambda path: [os.getpid()] if exited else [os.getpid(), 123])
    def identity(pid):
        if pid == 123:
            exited.append(True)
            raise FileNotFoundError('/proc/123/stat')
        return {'pid': pid, 'start_ticks': '42'}
    monkeypatch.setattr(guard, '_process_identity', identity)
    snap = guard.read_cgroup_snapshot(unit)
    assert snap['cpu_stat']['usage_usec'] == 10
    assert snap['process_observations']['123']['status'] == 'exited_during_sample'
    assert '123' not in snap['process_identities']


def test_same_pid_reuse_during_sampling_is_refused(tree, guard, monkeypatch):
    _, _, unit = tree
    monkeypatch.setattr(guard, '_cgroup_pids', lambda path: [os.getpid(), 123])
    starts = iter(['10', '11'])
    def identity(pid):
        return {'pid': pid, 'start_ticks': next(starts) if pid == 123 else '42'}
    monkeypatch.setattr(guard, '_process_identity', identity)
    with pytest.raises(ValueError, match='reuse'):
        guard.read_cgroup_snapshot(unit)


def test_missing_stat_with_retained_membership_is_unknown_not_exit(tree, guard, monkeypatch):
    _, _, unit = tree
    monkeypatch.setattr(guard, '_cgroup_pids', lambda path: [os.getpid(), 123])
    def identity(pid):
        if pid == 123:
            raise FileNotFoundError('/proc/123/stat')
        return {'pid': pid, 'start_ticks': '42'}
    monkeypatch.setattr(guard, '_process_identity', identity)
    with pytest.raises(ValueError, match='authority'):
        guard.read_cgroup_snapshot(unit)


@pytest.mark.parametrize('failure', [subprocess.TimeoutExpired('systemctl', 5, output='partial'), OSError('command failed')])
def test_main_term_exception_does_not_abort_whole_unit_escalation(guard, monkeypatch, failure):
    run = Mock(side_effect=[failure, subprocess.CompletedProcess([], 0, '', ''),
                           subprocess.CompletedProcess([], 0, '', '')])
    monkeypatch.setattr(guard.subprocess, 'run', run)
    states = Mock(side_effect=[ValueError('query unavailable'), False])
    monkeypatch.setattr(guard, '_unit_terminal', states)
    result = guard._stop_owned_unit('compute-metabolism-test.service')
    assert '--kill-whom=all' in result['commands'][1]['argv']
    assert 'stop' in result['commands'][2]['argv']
    assert result['commands'][0]['error']
    assert result['errors']
    assert result['terminal'] is False
    assert states.call_count == 2


def test_grace_query_exception_retains_state_and_escalates(guard, monkeypatch):
    run = Mock(side_effect=[subprocess.CompletedProcess([], 0, '', ''),
        subprocess.TimeoutExpired('show', 5, output='partial show'),
        subprocess.CompletedProcess([], 0, '', ''), subprocess.CompletedProcess([], 0, '', ''),
        subprocess.CompletedProcess([], 0, 'LoadState=not-found\n', '')])
    monkeypatch.setattr(guard.subprocess, 'run', run)
    result = guard._stop_owned_unit('compute-metabolism-test.service')
    assert result['terminal'] is True
    assert len(result['commands']) == 3
    assert result['unit_states'][0]['error']
    assert result['unit_states'][0]['stdout'] == 'partial show'
    assert result['errors']


def test_inner_drain_exception_still_reaps_and_collects_invalid_final(tree, guard, tmp_path, monkeypatch):
    _, _, unit = tree
    monkeypatch.setattr(guard, 'current_cgroup_path', lambda: unit)
    monkeypatch.setattr(guard, 'read_cpu_topology', topology)
    monkeypatch.setattr(guard, '_enable_subreaper', lambda: None)
    process = Mock(pid=123, returncode=0)
    process.wait.return_value = 0
    monkeypatch.setattr(guard.subprocess, 'Popen', Mock(return_value=process))
    drain = Mock(side_effect=[OSError('drain unavailable'), {'remaining_pids': [], 'reaped_pids': [123]}])
    monkeypatch.setattr(guard, '_drain_owned_children', drain)
    result = guard.run_inner(profile_key='2c', run_id='test', unit_name=unit.name,
        artifact_dir=tmp_path, command=['true'])
    assert drain.call_count == 2
    assert drain.call_args.kwargs['interrupted']()
    assert process.wait.call_count == 2
    assert result['after'] is not None
    assert result['measurement_valid'] is False
    assert result['outcome'] == 'ENVIRONMENT_INVALID'
    assert 'drain unavailable' in str(result['cleanup_errors'])
    assert (tmp_path / 'guard-cgroup-final.json').exists()


def test_outer_cleanup_attempts_survive_retry(guard, tmp_path, monkeypatch):
    from compute_metabolism.v0.profiles import get_profile
    rootfs, artifact, process = setup_outer(tmp_path, monkeypatch, guard, timeout=True)
    first = {'terminal': False, 'commands': [{'error': 'TERM timeout'}], 'errors': ['TERM timeout']}
    second = {'terminal': False, 'commands': [{'error': 'KILL timeout'}], 'errors': ['KILL timeout']}
    third = {'terminal': False, 'commands': [], 'errors': ['unknown terminal']}
    monkeypatch.setattr(guard, '_stop_owned_unit', Mock(side_effect=[first, second, third]))
    monkeypatch.setattr(guard, '_unit_terminal', lambda unit, evidence=None: False)
    result = guard.run_system_guard_test_only_probe(get_profile('2c'), test_only_wall_seconds=.1,
        run_id='test', artifact_dir=artifact, command=['true'], topology=topology(), root_directory=rootfs)
    assert result['cleanup_attempts'][:2] == [first, second]
    assert result['launcher_reaped'] is True
    assert result['terminal'] is False
    assert result['measurement_valid'] is False
    assert process.kill.called


def test_worker_exit_running_sample_does_not_kill_requested_work(tree, guard, tmp_path, monkeypatch):
    _, _, unit = tree
    monkeypatch.setattr(guard, 'current_cgroup_path', lambda: unit)
    monkeypatch.setattr(guard, 'read_cpu_topology', topology)
    monkeypatch.setattr(guard, '_enable_subreaper', lambda: None)
    stage = ['before']
    def members(path):
        return [os.getpid(), 123, 124] if stage[0] == 'exiting' else ([os.getpid(), 124] if stage[0] == 'running' else [os.getpid()])
    def identity(pid):
        if pid == 123:
            stage[0] = 'running'
            raise FileNotFoundError('/proc/123/stat')
        return {'pid': pid, 'start_ticks': '42'}
    monkeypatch.setattr(guard, '_cgroup_pids', members)
    monkeypatch.setattr(guard, '_process_identity', identity)
    process = Mock(pid=124, returncode=0)
    waits = []
    def wait(timeout=None):
        if not waits:
            waits.append(True)
            stage[0] = 'exiting'
            raise subprocess.TimeoutExpired('child', .1)
        stage[0] = 'finished'
        return 0
    process.wait.side_effect = wait
    monkeypatch.setattr(guard.subprocess, 'Popen', Mock(return_value=process))
    monkeypatch.setattr(guard, '_drain_owned_children', Mock(return_value={'remaining_pids': [], 'reaped_pids': [124]}))
    result = guard.run_inner(profile_key='2c', run_id='test', unit_name=unit.name, artifact_dir=tmp_path, command=['true'])
    assert result['outcome'] == 'GUARD_COMPLETE'
    assert result['measurement_valid'] is True
    assert not process.kill.called
    running = json.loads((tmp_path / 'guard-cgroup-running.jsonl').read_text())
    assert running['process_observations']['123']['status'] == 'exited_during_sample'
    assert result['after']['pids'] == [os.getpid()]


def test_inner_repeated_drain_and_kill_errors_still_attempt_reap_final(tree, guard, tmp_path, monkeypatch):
    _, _, unit = tree
    monkeypatch.setattr(guard, 'current_cgroup_path', lambda: unit)
    monkeypatch.setattr(guard, 'read_cpu_topology', topology)
    monkeypatch.setattr(guard, '_enable_subreaper', lambda: None)
    process = Mock(pid=123, returncode=0)
    process.wait.return_value = 0
    process.kill.side_effect = OSError('kill failed')
    monkeypatch.setattr(guard.subprocess, 'Popen', Mock(return_value=process))
    drain = Mock(side_effect=OSError('drain failed'))
    monkeypatch.setattr(guard, '_drain_owned_children', drain)
    result = guard.run_inner(profile_key='2c', run_id='test', unit_name=unit.name, artifact_dir=tmp_path, command=['true'])
    assert drain.call_count == 2
    assert process.wait.call_count == 2
    assert result['after'] is not None
    assert len(result['cleanup_errors']) == 3
    assert result['measurement_valid'] is False


def test_final_topology_failure_does_not_suppress_available_cgroup_snapshot(tree, guard, tmp_path, monkeypatch):
    _, _, unit = tree
    monkeypatch.setattr(guard, 'current_cgroup_path', lambda: unit)
    monkeypatch.setattr(guard, 'read_cpu_topology', Mock(side_effect=[topology(), OSError('topology unavailable')]))
    monkeypatch.setattr(guard, '_enable_subreaper', lambda: None)
    process = Mock(pid=123, returncode=0)
    process.wait.return_value = 0
    monkeypatch.setattr(guard.subprocess, 'Popen', Mock(return_value=process))
    monkeypatch.setattr(guard, '_drain_owned_children', Mock(return_value={'remaining_pids': [], 'reaped_pids': [123]}))
    result = guard.run_inner(profile_key='2c', run_id='test', unit_name=unit.name, artifact_dir=tmp_path, command=['true'])
    assert result['after'] is not None
    assert result['measurement_valid'] is False
    assert result['outcome'] == 'ENVIRONMENT_INVALID'
    assert 'topology unavailable' in str(result['final_errors'])
