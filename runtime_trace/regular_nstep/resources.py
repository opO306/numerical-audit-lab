"""Bounded Linux process-tree execution and exclusive evidence accounting."""
import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import platform
import selectors
import subprocess
import sys
import time
import uuid


class ResourceRefused(ValueError):
    pass


@dataclass(frozen=True)
class Limits:
    total_seconds: int = 3600
    job_seconds: int = 600
    memory_bytes: int = 4294967296
    storage_bytes: int = 8589934592

    def __post_init__(self):
        for name, maximum in (('total_seconds', 3600), ('job_seconds', 600),
                              ('memory_bytes', 4294967296), ('storage_bytes', 8589934592)):
            value = getattr(self, name)
            if type(value) is not int or not 0 < value <= maximum:
                raise ValueError('invalid approved ceiling: ' + name)


class EvidenceBudget:
    def __init__(self, root, maximum):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        if type(maximum) is not int or maximum <= 0:
            raise ValueError('invalid byte ceiling')
        self.maximum = maximum
        self.used = sum(p.stat().st_size for p in self.root.rglob('*') if p.is_file())

    def reserve(self, count):
        if type(count) is not int or count < 0 or self.used + count > self.maximum:
            raise ResourceRefused('new evidence storage ceiling')
        self.used += count

    def write(self, relative, data):
        path = self.root / relative
        if path.is_absolute() and self.root not in path.resolve().parents:
            raise ValueError('evidence path escapes root')
        if '..' in Path(relative).parts or path.resolve() == self.root:
            raise ValueError('noncanonical evidence path')
        if path.exists():
            raise FileExistsError(path)
        self.reserve(len(data))
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            stream.write(data)


class WriterQuota:
    """Shared per-job allocation. Lock, reserve, then write; no stale balances."""
    def __init__(self, path, maximum):
        self.path, self.maximum = Path(path), maximum
        if type(maximum) is not int or maximum < 0:
            raise ResourceRefused('invalid writer allocation')

    def reserve(self, count):
        import fcntl
        if type(count) is not int or count < 0:
            raise ResourceRefused('invalid writer reservation')
        with self.path.open('a+b') as stream:
            fcntl.flock(stream, fcntl.LOCK_EX)
            stream.seek(0)
            raw = stream.read()
            used = int(raw or b'0')
            if used + count > self.maximum:
                raise ResourceRefused('shared evidence writer allocation exhausted')
            stream.seek(0)
            stream.truncate()
            stream.write(str(used + count).encode())
            stream.flush()


def reserve_writer(count):
    if 'RTN_QUOTA_FILE' not in os.environ:
        raise ResourceRefused('evidence writer requires guarded job allocation')
    WriterQuota(os.environ['RTN_QUOTA_FILE'], int(os.environ['RTN_QUOTA_BYTES'])).reserve(count)


def _strict_load(path):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('duplicate JSON key')
            result[key] = value
        return result
    return json.loads(Path(path).read_bytes(), object_pairs_hook=pairs,
                      parse_constant=lambda v: (_ for _ in ()).throw(ValueError(v)))


def _show(unit):
    result = subprocess.run(['systemctl', '--user', 'show', unit,
        '--property=Result', '--property=MemoryPeak', '--property=MemoryMax',
        '--property=MemorySwapMax', '--property=CPUUsageNSec'], capture_output=True,
        text=True, timeout=5, check=True)
    return dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line)


def run_guarded(command, limits, out, ledger, *, cwd=None, env=None, artifact_allowance=0):
    """One job at a time. Cumulative wall time includes the complete unit wait."""
    if platform.system() != 'Linux':
        raise ResourceRefused('Linux cgroup guard required')
    out, ledger = Path(out).resolve(), Path(ledger).resolve()
    marker = ledger.with_suffix('.running.json')
    if marker.exists() and _strict_load(marker).get('state') != 'FINISHED':
        raise ResourceRefused('unreconciled prior job prohibits new execution')
    prior = _strict_load(ledger) if ledger.exists() else {'used_seconds': 0., 'jobs': []}
    used = prior.get('used_seconds')
    if type(used) not in (int, float) or isinstance(used, bool) or not 0 <= used <= limits.total_seconds:
        raise ResourceRefused('invalid cumulative ledger')
    allowance = min(limits.job_seconds, int(limits.total_seconds - used))
    if allowance < 1:
        raise ResourceRefused('cumulative execution allowance exhausted')
    if out.exists():
        raise FileExistsError(out)
    budget = EvidenceBudget(ledger.parent, limits.storage_bytes)
    # Reserve receipts before the job. Capture/derived writers have their own
    # bounded reservations; a subsequent invocation reconciles actual files.
    if len(json.dumps(list(command), ensure_ascii=True).encode()) > 8192:
        raise ResourceRefused('bounded command/receipt size')
    budget.reserve(32768 + len(json.dumps(prior).encode()))
    budget.reserve(artifact_allowance)
    out.mkdir(parents=True, exist_ok=False)
    quota_file = out / 'writer_quota.txt'
    quota_file.write_text('0')
    unit = 'nstep-' + uuid.uuid4().hex
    child_report = out / 'child_measurement.json'
    working = str(Path(cwd or os.getcwd()).resolve())
    launch = ['systemd-run', '--quiet', '--user', '--wait', '--pipe', '--unit=' + unit,
        '--working-directory=' + working, '--property=MemoryAccounting=yes',
        '--property=MemoryMax=' + str(limits.memory_bytes), '--property=MemorySwapMax=0',
        '--property=RuntimeMaxSec=' + str(allowance), '--property=OOMPolicy=kill',
        '--property=KillMode=control-group', sys.executable, '-m',
        'runtime_trace.regular_nstep.resources', '--child-report', str(child_report),
        '--memory', str(limits.memory_bytes), '--file-limit', str(limits.storage_bytes), '--', *command]
    # Transient services do not inherit caller environment. Pass only explicit
    # overrides and numerical/thread settings, never unrelated secrets.
    environment = {'PYTEST_DISABLE_PLUGIN_AUTOLOAD': '1', 'OMP_NUM_THREADS': '1',
                   'OPENBLAS_NUM_THREADS': '1', **(env or {}),
                   'RTN_QUOTA_FILE': str(quota_file), 'RTN_QUOTA_BYTES': str(artifact_allowance)}
    for key, value in environment.items():
        if not key.replace('_', '').isalnum() or '\x00' in str(value):
            raise ValueError('invalid job environment')
        launch.insert(2, '--setenv=' + key + '=' + str(value))
    started = time.monotonic()
    marker.write_text(json.dumps({'state': 'RUNNING', 'path': str(out),
        'unit': unit, 'started_monotonic': started, 'previous_used_seconds': used}) + '\n')
    process = subprocess.Popen(launch, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    resource_failure = None
    with (out / 'stdout.log').open('xb') as log:
        while selector.get_map():
            if time.monotonic() - started > allowance + 5:
                resource_failure = 'wall watchdog'
                subprocess.run(['systemctl', '--user', 'kill', '--kill-whom=all', unit],
                               capture_output=True, timeout=5)
            for key, _ in selector.select(.1):
                chunk = os.read(key.fd, 65536)
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                try:
                    budget.reserve(len(chunk))
                    log.write(chunk)
                except ResourceRefused:
                    resource_failure = 'log/evidence storage ceiling'
                    subprocess.run(['systemctl', '--user', 'kill', '--kill-whom=all', unit],
                                   capture_output=True, timeout=5)
    selector.close()
    code = process.wait(timeout=5)
    elapsed = time.monotonic() - started
    try:
        props = _show(unit)
    except Exception as exc:
        props = {'inspection_error': str(exc)}
        resource_failure = resource_failure or 'controller receipt unavailable'
    try:
        child = _strict_load(child_report) if child_report.exists() else {}
    except Exception as exc:
        child = {'inspection_error': str(exc)}
        resource_failure = resource_failure or 'malformed child measurement'
    enforced = child.get('memory_max') == limits.memory_bytes and child.get('memory_swap_max') == 0
    if not enforced:
        resource_failure = resource_failure or 'child did not verify cgroup limits'
    if props.get('Result') in ('timeout', 'oom-kill', 'resources'):
        resource_failure = resource_failure or props['Result']
    receipt = {'schema': 'nstep-guarded-execution-v1', 'host': platform.node(),
        'platform': platform.platform(), 'python': platform.python_version(),
        'command': list(command), 'cwd': working, 'unit': unit, 'return_code': code,
        'wall_seconds': elapsed, 'memory_limit': limits.memory_bytes,
        'enforced_memory_bytes': child.get('memory_max'),
        'enforced_swap_bytes': child.get('memory_swap_max'),
        'peak_tree_memory_bytes': (int(props['MemoryPeak']) if props.get('MemoryPeak', '').isdigit()
                                   else child.get('cgroup_memory_peak_bytes')),
        'sampled_tree_rss_peak_bytes': child.get('sampled_tree_rss_peak_bytes'),
        'rss_sample_interval_seconds': .02, 'systemd': props,
        'requested_complete': False, 'resource_failure': resource_failure,
        'verdict': 'REFUSED_RESOURCE' if resource_failure else ('EXECUTED' if code == 0 else 'FAILED')}
    (out / 'execution.json').write_text(json.dumps(receipt, sort_keys=True) + '\n')
    prior['used_seconds'] += elapsed
    prior['jobs'].append({'path': str(out), 'wall_seconds': elapsed,
                          'host': receipt['host'], 'return_code': code})
    # Serialized execution is part of the public contract; no concurrent writers.
    temporary = ledger.with_name(ledger.name + '.pending')
    temporary.write_text(json.dumps(prior, sort_keys=True) + '\n')
    temporary.replace(ledger)
    # Any earlier exception leaves RUNNING and refuses later jobs. Receipt or
    # ledger failure can never give the same execution allowance back silently.
    marker.write_text(json.dumps({'state': 'FINISHED', 'path': str(out),
        'wall_seconds': elapsed, 'new_used_seconds': prior['used_seconds']}) + '\n')
    subprocess.run(['systemctl', '--user', 'reset-failed', unit], capture_output=True, timeout=5)
    return receipt


def _rss(cgroup):
    """Sample every descendant cgroup, including descendants spawned by GDB."""
    total, pids = 0, set()
    for path in [cgroup / 'cgroup.procs', *cgroup.rglob('cgroup.procs')]:
        pids.update(path.read_text().split())
    for pid in pids:
        try:
            for line in Path('/proc', pid, 'status').read_text().splitlines():
                if line.startswith('VmRSS:'):
                    total += int(line.split()[1]) * 1024
        except (FileNotFoundError, ProcessLookupError):
            pass
    return total


def _child(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument('--child-report', type=Path, required=True)
    parser.add_argument('--memory', type=int, required=True)
    parser.add_argument('--file-limit', type=int, required=True)
    args, command = parser.parse_known_args(argv)
    if command and command[0] == '--':
        command.pop(0)
    relative = next(line.split(':', 2)[2] for line in Path('/proc/self/cgroup').read_text().splitlines()
                    if line.startswith('0:'))
    cgroup = Path('/sys/fs/cgroup') / relative.lstrip('/')
    maximum = int((cgroup / 'memory.max').read_text())
    swap = int((cgroup / 'memory.swap.max').read_text())
    if maximum != args.memory or swap != 0:
        raise ResourceRefused('effective cgroup ceiling mismatch')
    import resource
    resource.setrlimit(resource.RLIMIT_FSIZE, (args.file_limit, args.file_limit))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    args.child_report.write_text(json.dumps({'memory_max': maximum, 'memory_swap_max': swap,
        'guard_verified_before_command': True}) + '\n')
    process = subprocess.Popen(command)
    peak = 0
    while process.poll() is None:
        peak = max(peak, _rss(cgroup))
        time.sleep(.02)
    args.child_report.write_text(json.dumps({'memory_max': maximum, 'memory_swap_max': swap,
        'cgroup_memory_peak_bytes': int((cgroup / 'memory.peak').read_text()),
        'sampled_tree_rss_peak_bytes': peak, 'command_exit_code': process.returncode}) + '\n')
    return process.returncode if process.returncode >= 0 else 128 - process.returncode


if __name__ == '__main__':
    raise SystemExit(_child(sys.argv[1:]))
