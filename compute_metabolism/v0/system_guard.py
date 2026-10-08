"""Linux system transient-unit guard; no numerical or V1 acceptance authority.

The inner wrapper collects cgroup counters while the unit is still alive.
Missing terminal evidence invalidates measurement, including on timeout.
"""
from __future__ import annotations

import argparse
import ctypes
import json
import os
from pathlib import Path, PurePosixPath
import re
import select
import signal
import stat
import subprocess
import sys
import time
import uuid
from typing import NamedTuple, Sequence

from .profiles import CampaignLimits, ProfileSpec, get_profile, parse_cpu_list, parse_cpu_max

CGROUP_ROOT = Path('/sys/fs/cgroup')
PREPARED_ROOT = Path('/home/zun24/compute-metabolism-v0-prepared-20261006/rootfs')
INNER_PYTHON = '/home/otherside123/venvs/gate2c1-trace/bin/python'
ARTIFACT_ROOT = PurePosixPath('/workspace/compute_metabolism/v0/artifacts')
CPU_BASE_COUNTERS = ('usage_usec', 'user_usec', 'system_usec')
CPU_COUNTERS = CPU_BASE_COUNTERS + ('nr_periods', 'nr_throttled', 'throttled_usec')
UNIT_PATTERN = re.compile(r'compute-metabolism-[A-Za-z0-9_-]+\.service\Z')


class UnitExecutionIdentity(NamedTuple):
    uid: int
    gid: int


# One contract supplies both systemd credentials and artifact ownership.
SYSTEM_UNIT_IDENTITY = UnitExecutionIdentity(1000, 1003)


def validate_artifact_ownership(artifact_dir: Path) -> dict:
    identity = SYSTEM_UNIT_IDENTITY
    records = {}
    for path, mode, directory in ((Path(artifact_dir), 0o700, True),
            (Path(artifact_dir) / 'writer_quota.txt', 0o600, False)):
        info = path.lstat()
        if (not (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode))
                or (not directory and info.st_nlink != 1)
                or (info.st_uid, info.st_gid) != identity
                or stat.S_IMODE(info.st_mode) != mode):
            raise ValueError('artifact ownership/type/private permissions mismatch: ' + str(path))
        records['directory' if directory else 'writer_quota'] = dict(
            path=str(path), uid=info.st_uid, gid=info.st_gid, mode=mode)
    return records


def prepare_artifact_ownership(artifact_dir: Path) -> dict:
    """Prepare newly created artifacts; fail before starting any system unit."""
    identity = SYSTEM_UNIT_IDENTITY
    for path, mode, directory in ((Path(artifact_dir), 0o700, True),
            (Path(artifact_dir) / 'writer_quota.txt', 0o600, False)):
        info = path.lstat()
        if (not (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode))
                or (not directory and info.st_nlink != 1)):
            raise ValueError('artifact ownership preparation requires unaliased directory/file')
        # Restrict access before changing owner, including when the caller is root.
        os.chmod(path, mode, follow_symlinks=False)
        if (info.st_uid, info.st_gid) != identity:
            os.chown(path, identity.uid, identity.gid, follow_symlinks=False)
    return validate_artifact_ownership(artifact_dir)


def _validate_unit_execution_identity(argv: Sequence[str]) -> None:
    identity = SYSTEM_UNIT_IDENTITY
    if ([x for x in argv if x.startswith('--uid=')] != [f'--uid={identity.uid}']
            or [x for x in argv if x.startswith('--gid=')] != [f'--gid={identity.gid}']):
        raise ValueError('system unit execution identity differs from artifact ownership contract')


def _approved(profile: ProfileSpec, limits: CampaignLimits | None = None) -> CampaignLimits:
    if type(profile) is not ProfileSpec or profile != get_profile(profile.key):
        raise ValueError('unapproved profile')
    approved = CampaignLimits()
    if limits is not None and (type(limits) is not CampaignLimits or limits != approved):
        raise ValueError('unapproved limits')
    return approved


def _artifact_path(path: PurePosixPath) -> PurePosixPath:
    path = PurePosixPath(path)
    if '..' in path.parts or ARTIFACT_ROOT not in path.parents:
        raise ValueError('artifact path must be strictly inside approved namespace')
    return path


def _owned_name(name: str) -> None:
    if not UNIT_PATTERN.fullmatch(name):
        raise ValueError('invalid owned unit name')


def build_systemd_run_argv(profile: ProfileSpec, *, unit_name: str,
        artifact_dir: PurePosixPath, command: Sequence[str],
        root_directory: Path = PREPARED_ROOT, limits: CampaignLimits | None = None) -> list[str]:
    limits = _approved(profile, limits)
    _owned_name(unit_name)
    artifact_dir = _artifact_path(artifact_dir)
    if not command or any(not isinstance(arg, str) or '\x00' in arg for arg in command):
        raise ValueError('invalid child argv')
    props = {
        'RootDirectory': Path(root_directory).as_posix(), 'WorkingDirectory': '/workspace',
        'MountAPIVFS': 'yes', 'AllowedCPUs': ','.join(map(str, profile.cpus)),
        'MemoryMax': str(limits.memory_bytes), 'MemorySwapMax': str(limits.memory_swap_bytes),
        'CPUAccounting': 'yes', 'MemoryAccounting': 'yes',
        'RuntimeMaxSec': f'{limits.per_run_wall_seconds}s', 'KillMode': 'control-group',
        'OOMPolicy': 'kill', 'Delegate': 'no',
        'ReadOnlyPaths': '/workspace /usr /home/otherside123 /reference',
        'ReadWritePaths': str(ARTIFACT_ROOT),
    }
    if profile.quota_percent is not None:
        props.update(CPUQuota=f'{profile.quota_percent}%', CPUQuotaPeriodSec=f'{profile.quota_period_ms}ms')
    env = {
        'PATH': '/home/otherside123/venvs/gate2c1-trace/bin:/usr/bin:/bin',
        'LC_ALL': 'C.UTF-8', 'PYTHONDONTWRITEBYTECODE': '1', 'HOME': '/home/zun24',
        'OMP_NUM_THREADS': str(limits.omp_num_threads), 'OPENBLAS_NUM_THREADS': str(limits.openblas_num_threads),
        'RTN_QUOTA_FILE': str(artifact_dir / 'writer_quota.txt'), 'RTN_QUOTA_BYTES': str(limits.writer_bytes),
    }
    return ['sudo', '-n', 'systemd-run', '--quiet', '--wait', '--pipe', '--collect',
            f'--uid={SYSTEM_UNIT_IDENTITY.uid}', f'--gid={SYSTEM_UNIT_IDENTITY.gid}', f'--unit={unit_name}',
            *(f'--property={key}={value}' for key, value in props.items()),
            *(f'--setenv={key}={value}' for key, value in env.items()),
            INNER_PYTHON, '-m', 'compute_metabolism.v0.system_guard', 'inner',
            '--profile', profile.key, '--unit', unit_name, '--run-id', artifact_dir.name,
            '--artifact-dir', str(artifact_dir), '--', *command]


def _boot_id() -> str:
    return Path('/proc/sys/kernel/random/boot_id').read_text().strip()


def current_cgroup_path() -> Path:
    lines = Path('/proc/self/cgroup').read_text().splitlines()
    unified = [line[3:] for line in lines if line.startswith('0::')]
    if len(unified) != 1 or not unified[0].startswith('/') or '..' in PurePosixPath(unified[0]).parts:
        raise ValueError('missing or invalid unified cgroup identity')
    path = CGROUP_ROOT / unified[0].lstrip('/')
    if not path.is_dir():
        raise ValueError('live cgroup unavailable')
    return path


def _ancestors(path: Path) -> list[Path]:
    path, root = path.resolve(strict=True), CGROUP_ROOT.resolve(strict=True)
    if path != root and root not in path.parents:
        raise ValueError('cgroup outside controller mount')
    return [path, *(p for p in path.parents if p == root or root in p.parents)]


def resolve_effective_cpu_max(cgroup_path: Path) -> dict:
    ancestors = []
    for index, path in enumerate(_ancestors(cgroup_path)):
        file = path / 'cpu.max'
        if not file.exists():
            # A leaf may inherit cpu.max; mount root legitimately lacks it.
            if index != 0 and path != CGROUP_ROOT.resolve():
                raise ValueError(f'missing CPU quota ancestor: {file}')
            ancestors.append({'path': str(file), 'raw': None, 'missing_at_root': path == CGROUP_ROOT.resolve()})
            continue
        raw = file.read_text()
        quota, period = parse_cpu_max(raw)
        ancestors.append({'path': str(file), 'raw': raw, 'quota_usec': quota, 'period_usec': period})
    known = [entry for entry in ancestors if entry['raw'] is not None]
    if not known:
        raise ValueError('CPU quota authority unavailable')
    finite = [entry for entry in known if entry['quota_usec'] is not None]
    nearest = known[0]
    return {'source': nearest['path'], 'raw': nearest['raw'],
            'quota_usec': nearest['quota_usec'], 'period_usec': nearest['period_usec'],
            'unlimited': not finite, 'finite_ancestors': finite,
            'ancestors': ancestors, 'scan_root': str(CGROUP_ROOT.resolve())}


def _uint(raw: str) -> int:
    if not raw.strip().isascii() or not raw.strip().isdigit():
        raise ValueError('invalid nonnegative cgroup value')
    return int(raw.strip())


def _limit_scan(cgroup_path: Path, name: str) -> dict:
    entries = []
    for path in _ancestors(cgroup_path):
        file = path / name
        if not file.exists():
            if path != CGROUP_ROOT.resolve():
                raise ValueError(f'missing effective limit authority: {file}')
            entries.append({'path': str(file), 'raw': None, 'missing_at_root': True})
            continue
        raw = file.read_text()
        entries.append({'path': str(file), 'raw': raw, 'bytes': None if raw.strip() == 'max' else _uint(raw)})
    finite = [entry['bytes'] for entry in entries if entry['raw'] is not None and entry['bytes'] is not None]
    return {'effective_bytes': min(finite) if finite else None, 'ancestors': entries,
            'scan_root': str(CGROUP_ROOT.resolve())}


def _counters(raw: str, required: Sequence[str], *, source_file: str, cgroup_path: Path) -> dict:
    result = {}
    for line in raw.splitlines():
        key, value = line.split()
        if key in result:
            raise ValueError('duplicate cgroup counter')
        result[key] = _uint(value)
    missing = [key for key in required if key not in result]
    if missing:
        error = ValueError('missing cgroup counter')
        error.counter_failure = {
            'source_file': source_file, 'required_counters': list(required),
            'found_counters': list(result), 'missing_counters': missing,
            'raw_text': raw, 'cgroup_path': str(cgroup_path),
        }
        raise error
    return result


def _epoch(path: Path) -> dict:
    stat = path.stat()
    return {'path': str(path.resolve()), 'device': stat.st_dev, 'inode': stat.st_ino, 'boot_id': _boot_id()}


def _cgroup_membership(path: Path) -> dict:
    started = time.monotonic_ns()
    epoch = _epoch(path)
    files = sorted({path / 'cgroup.procs', *path.glob('**/cgroup.procs')})
    rows, pids = [], set()
    if len(files) > 1024:
        raise ValueError('bounded cgroup membership inventory exceeded')
    for file in files:
        begin = time.monotonic_ns()
        before = file.stat()
        raw = file.read_text()
        after = file.stat()
        if ((before.st_dev, before.st_ino) != (after.st_dev, after.st_ino)
                or len(raw.encode()) > 65536):
            raise ValueError('cgroup membership file identity/size changed')
        values = raw.split()
        if any(not x.isascii() or not x.isdigit() or int(x) <= 0 for x in values):
            raise ValueError('invalid cgroup process identity')
        pids.update(map(int, values))
        rows.append(dict(path=str(file), raw=raw, begin_ns=begin,
                         end_ns=time.monotonic_ns(), device=before.st_dev, inode=before.st_ino))
    if epoch != _epoch(path) or files != sorted({path / 'cgroup.procs', *path.glob('**/cgroup.procs')}):
        raise ValueError('cgroup membership epoch/inventory changed')
    return dict(epoch=epoch, files=rows, pids=sorted(pids),
                begin_ns=started, end_ns=time.monotonic_ns())


def _cgroup_pids(path: Path) -> list[int]:
    return _cgroup_membership(path)['pids']


class _ProcessWitness:
    """Pinned proc directory plus a birth-bound, whole-process pidfd."""
    def __init__(self, pid: int, path: Path):
        self.pid, self.procfd, self.pidfd = pid, None, None
        self.samples = []
        try:
            self.procfd = os.open(f'/proc/{pid}', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
            first = self.identity()
            self.pidfd = os.pidfd_open(pid, 0)
            second = self.identity()
            current = _process_identity(pid)
            if not (first['start_ticks'] == second['start_ticks'] == current['start_ticks']):
                raise ValueError('PID reuse during pidfd binding')
            self.start_ticks = first['start_ticks']
        except BaseException:
            self.close()
            raise

    def _read(self, name: str) -> str:
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=self.procfd)
        try:
            stream = os.fdopen(fd, 'r', encoding='utf-8')
        except BaseException:
            os.close(fd)
            raise
        with stream:
            raw = stream.read(65537)
        if len(raw.encode('utf-8')) > 65536:
            raise ValueError('bounded proc identity record exceeded')
        return raw

    def identity(self) -> dict:
        begin = time.monotonic_ns()
        raw = self._read('stat')
        fields = raw.rsplit(')', 1)[1].split()
        if int(raw.split(' ', 1)[0]) != self.pid or len(fields) < 20 or not fields[19].isdigit():
            raise ValueError('invalid pinned process stat identity')
        value = dict(pid=self.pid, start_ticks=fields[19], state=fields[0])
        self.samples.append(dict(kind='stat', begin_ns=begin, end_ns=time.monotonic_ns(),
                                 raw=raw, identity=value, ppid=int(fields[1])))
        return value

    def cgroup(self) -> str:
        begin = time.monotonic_ns()
        raw = self._read('cgroup')
        self.samples.append(dict(kind='cgroup', begin_ns=begin,
                                 end_ns=time.monotonic_ns(), raw=raw))
        return raw

    def exit_events(self) -> list:
        poller = select.poll()
        poller.register(self.pidfd, select.POLLIN)
        events = poller.poll(0)
        if events and (len(events) != 1 or events[0][0] != self.pidfd
                or not events[0][1] & select.POLLIN
                or events[0][1] & ~(select.POLLIN | select.POLLHUP)):
            raise ValueError('process pidfd exit authority unknown')
        return events

    def close(self) -> None:
        error = None
        for name in ('pidfd', 'procfd'):
            fd = getattr(self, name)
            if fd is not None:
                try:
                    os.close(fd)
                except OSError as exc:
                    error = exc
                finally:
                    setattr(self, name, None)
        if error is not None:
            raise error


def _owned_process_cgroup(witness, path: Path) -> str:
    raw = witness.cgroup()
    lines = [line[3:] for line in raw.splitlines() if line.startswith('0::')]
    if len(lines) != 1 or not lines[0].startswith('/') or PurePosixPath(lines[0]).as_posix() != lines[0]:
        raise ValueError('process cgroup authority unknown')
    if any(x in ('.', '..') for x in lines[0].split('/')[1:]):
        raise ValueError('process cgroup path alias')
    if '(deleted)' in lines[0]:
        raise ValueError('deleted process cgroup refused')
    actual = CGROUP_ROOT / lines[0].lstrip('/')
    if not actual.is_dir() or actual.resolve(strict=True) != actual:
        raise ValueError('process cgroup directory authority unknown')
    if actual != path and path not in actual.parents:
        raise ValueError('live process outside owned cgroup')
    return raw


def _sample_processes(path: Path, enumerated: list[int]) -> tuple[dict, dict, list[int]]:
    identities, observations = {}, {}
    for pid in enumerated:
        witness, evidence = None, dict(pid=pid)
        try:
            witness = _ProcessWitness(pid, path)
            first = witness.identity()
            evidence['first_identity'] = first
            evidence['first_cgroup'] = _owned_process_cgroup(witness, path)
            membership1 = _cgroup_membership(path)
            second = witness.identity()
            evidence['second_identity'] = second
            evidence['second_cgroup'] = _owned_process_cgroup(witness, path)
            membership2 = _cgroup_membership(path)
            evidence.update(membership1=membership1, membership2=membership2)
            if not (first['start_ticks'] == second['start_ticks'] == witness.start_ticks):
                raise ValueError('PID reuse during sample')
            events = witness.exit_events()
            if pid in membership1['pids'] and pid in membership2['pids'] and not events:
                identities[str(pid)] = second
                observations[str(pid)] = dict(status='stable', identity=second)
            else:
                if pid == os.getpid() or not events:
                    raise ValueError(f'process membership authority unknown: {second!r}')
                # POLLIN precedes terminal membership: leader Z alone does not
                # prove that every thread has exited. A reaped proc is refused.
                terminal = witness.identity()
                terminal_cgroup = _owned_process_cgroup(witness, path)
                if terminal['start_ticks'] != witness.start_ticks or terminal['state'] not in ('Z', 'X'):
                    raise ValueError('terminal process identity authority unknown')
                evidence.update(basis='BOUND_PROCESS_PIDFD_AND_TERMINAL_OWNED_CGROUP',
                                terminal_identity=terminal, terminal_cgroup=terminal_cgroup,
                                pidfd_events=events, process_samples=getattr(witness, 'samples', []))
                observations[str(pid)] = dict(status='exited_during_sample',
                                              observed_identity=terminal, exit_evidence=evidence)
        except (FileNotFoundError, ProcessLookupError) as exc:
            error = ValueError(f'process identity authority unknown: PID {pid}; positive terminal membership unavailable')
            error.process_evidence = evidence
            raise error from exc
        except ValueError as exc:
            exc.process_evidence = evidence
            if witness is not None:
                evidence['process_samples'] = getattr(witness, 'samples', [])
            raise
        finally:
            if witness is not None:
                witness.close()
    current = _cgroup_pids(path)
    for pid in current:
        if observations.get(str(pid), {}).get('status') == 'exited_during_sample':
            raise ValueError('PID reappeared after proven process termination')
        if pid not in enumerated:
            observations[str(pid)] = dict(status='appeared_during_sample', identity=None)
    if os.getpid() in enumerated and str(os.getpid()) not in identities:
        raise ValueError('wrapper process identity authority unavailable')
    return identities, observations, current


def read_cgroup_snapshot(cgroup_path: Path, *, profile: ProfileSpec | None = None) -> dict:
    # Legacy callers retain the strict full set; only approved unlimited
    # profiles may omit controller-dependent bandwidth counters.
    required_cpu = CPU_COUNTERS
    if profile is not None:
        _approved(profile)
        if profile.quota_percent is None:
            required_cpu = CPU_BASE_COUNTERS
    path = cgroup_path.resolve(strict=True)
    epoch = _epoch(path)
    raw = {name: (path / name).read_text() for name in (
        'cpuset.cpus.effective', 'cpu.stat', 'memory.max', 'memory.swap.max',
        'memory.current', 'memory.peak', 'memory.events', 'cgroup.procs', 'cgroup.events')}
    cpu_max = resolve_effective_cpu_max(path)
    raw['cpu.max'] = cpu_max['raw']
    try:
        result = {'epoch': epoch, 'monotonic_seconds': time.monotonic(), 'raw': raw,
                  'cpus': list(parse_cpu_list(raw['cpuset.cpus.effective'].strip())),
                  'cpu_max': cpu_max, 'cpu_stat': _counters(raw['cpu.stat'], required_cpu,
                      source_file='cpu.stat', cgroup_path=path),
                  'memory': _limit_scan(path, 'memory.max'), 'swap': _limit_scan(path, 'memory.swap.max'),
                  'memory_current': _uint(raw['memory.current']), 'memory_peak': _uint(raw['memory.peak']),
                  'memory_events': _counters(raw['memory.events'], ('oom', 'oom_kill'),
                      source_file='memory.events', cgroup_path=path),
                  'pids': _cgroup_pids(path)}
    except ValueError as exc:
        if hasattr(exc, 'counter_failure'):
            exc.raw_counter_files = {name: raw[name] for name in ('cpu.stat', 'memory.events')}
        raise
    result['enumerated_pids'] = result['pids']
    result['process_identities'], result['process_observations'], result['pids'] = _sample_processes(path, result['pids'])
    if epoch != _epoch(path):
        raise ValueError('cgroup epoch changed while reading')
    return result


def read_cpu_topology() -> dict:
    result = {}
    for cpu in (0, 1):
        base = Path(f'/sys/devices/system/cpu/cpu{cpu}/topology')
        result[str(cpu)] = {name: (base / name).read_text().strip()
                            for name in ('physical_package_id', 'core_id')}
    return result


def validate_enforcement(profile: ProfileSpec, snapshot: dict, topology: dict) -> None:
    limits = _approved(profile)
    required_cpu = CPU_BASE_COUNTERS if profile.quota_percent is None else CPU_COUNTERS
    if any(field not in snapshot['cpu_stat'] for field in required_cpu):
        raise ValueError('missing cgroup counter')
    if tuple(snapshot['cpus']) != profile.cpus:
        raise ValueError('CPU set mismatch')
    cpu = snapshot['cpu_max']
    if profile.quota_percent is None:
        if not cpu['unlimited']:
            raise ValueError('CPU ancestor quota restricts unlimited profile')
    else:
        if (cpu['quota_usec'], cpu['period_usec']) != (50000, 100000):
            raise ValueError('CPU quota/period mismatch')
        # A stricter ancestor changes the effective envelope.
        if any(entry['quota_usec'] * 100000 < 50000 * entry['period_usec']
               for entry in cpu['finite_ancestors']):
            raise ValueError('CPU ancestor quota restricts half-core profile')
    if _uint(snapshot['raw']['memory.max']) != limits.memory_bytes or snapshot['memory']['effective_bytes'] != limits.memory_bytes:
        raise ValueError('memory enforcement mismatch')
    if _uint(snapshot['raw']['memory.swap.max']) != 0 or snapshot['swap']['effective_bytes'] != 0:
        raise ValueError('swap enforcement mismatch')
    for cpu_id in profile.cpus:
        core = topology[str(cpu_id)]
        if not core['core_id'].isdigit() or not core['physical_package_id'].isdigit():
            raise ValueError('guest core topology unavailable')
    if len(profile.cpus) == 2:
        pairs = [(topology[str(cpu)]['physical_package_id'], topology[str(cpu)]['core_id']) for cpu in profile.cpus]
        if pairs[0] == pairs[1]:
            raise ValueError('guest core identities are not distinct')


def validate_snapshot_pair(before: dict, after: dict) -> dict:
    if before['epoch'] != after['epoch']:
        raise ValueError('cgroup epoch replaced')
    if after['monotonic_seconds'] < before['monotonic_seconds']:
        raise ValueError('snapshot clock reversed')
    for pid in before['process_identities'].keys() & after['process_identities'].keys():
        if before['process_identities'][pid]['start_ticks'] != after['process_identities'][pid]['start_ticks']:
            raise ValueError(f'PID reuse between snapshots: {pid}')
    delta = {}
    for field in CPU_COUNTERS:
        if (field not in CPU_BASE_COUNTERS and field not in before['cpu_stat']
                and field not in after['cpu_stat']):
            continue
        value = after['cpu_stat'][field] - before['cpu_stat'][field]
        if value < 0:
            raise ValueError('cgroup CPU counter reset')
        delta[field] = value
    for key in before['memory_events']:
        if after['memory_events'][key] < before['memory_events'][key]:
            raise ValueError('cgroup memory event reset')
    if after['memory_peak'] < before['memory_peak']:
        raise ValueError('memory peak reset')
    delta['cpu_seconds'] = delta['usage_usec'] / 1_000_000
    return delta


def _write_json(path: Path, value: dict) -> None:
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())


def _failure(exc: Exception) -> dict:
    def decoded(value):
        return value.decode('utf-8', errors='replace') if isinstance(value, bytes) else value
    return {'error': f'{type(exc).__name__}: {exc}',
            'stdout': decoded(getattr(exc, 'stdout', None)),
            'stderr': decoded(getattr(exc, 'stderr', None))}


def _process_identity(pid: int) -> dict:
    raw = Path(f'/proc/{pid}/stat').read_text()
    fields = raw.rsplit(')', 1)[1].split()
    return {'pid': pid, 'start_ticks': fields[19], 'state': fields[0]}


def _enable_subreaper() -> None:
    # PR_SET_CHILD_SUBREAPER: adopted descendants can be waited/reaped here.
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(36, 1, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), 'PR_SET_CHILD_SUBREAPER failed')


def _drain_owned_children(path: Path, *, interrupted=lambda: False) -> dict:
    reaped = []
    signals = []
    own_epoch = _epoch(path)
    while True:
        no_children = False
        while True:
            try:
                pid, _ = os.waitpid(-1, os.WNOHANG)
            except ChildProcessError:
                no_children = True
                break
            if not pid:
                break
            reaped.append(pid)
        if _epoch(path) != own_epoch:
            raise ValueError('owned cgroup epoch changed during drain')
        remaining = [pid for pid in _cgroup_pids(path) if pid != os.getpid()]
        if not remaining:
            # cgroup.procs can omit zombies. Verify no adopted children remain
            # waitable before declaring reap complete.
            if no_children:
                return {'remaining_pids': [], 'reaped_pids': reaped, 'signals': signals}
            try:
                pid, _ = os.waitpid(-1, os.WNOHANG)
            except ChildProcessError:
                return {'remaining_pids': [], 'reaped_pids': reaped, 'signals': signals}
            if pid:
                reaped.append(pid)
            else:
                time.sleep(.02)
            continue
        if interrupted():
            # pidfds prevent PID-reuse races; only identities currently in this
            # owned cgroup are selected. UID1000/Delegate=no cannot move work out.
            for pid in remaining:
                try:
                    fd = os.pidfd_open(pid)
                    try:
                        if pid in _cgroup_pids(path):
                            signal.pidfd_send_signal(fd, signal.SIGKILL)
                            signals.append(pid)
                    finally:
                        os.close(fd)
                except ProcessLookupError:
                    pass
        time.sleep(.02)


def run_inner(*, profile_key: str, run_id: str, unit_name: str,
              artifact_dir: Path, command: Sequence[str]) -> dict:
    profile = get_profile(profile_key)
    _owned_name(unit_name)
    result = {'run_id': run_id, 'unit': unit_name, 'profile': profile_key,
              'outcome': 'ENVIRONMENT_INVALID', 'before': None, 'after': None,
              'measurement_valid': False, 'child_returncode': None}
    stopped = [False]
    def stop(signum, frame):
        stopped[0] = True
    old_handlers = {sig: signal.signal(sig, stop) for sig in (signal.SIGTERM, signal.SIGINT)}
    process = None
    path = None
    stage = 'enable_subreaper'
    try:
        _enable_subreaper()
        stage = 'current_cgroup_path'
        path = current_cgroup_path()
        stage = 'validate_cgroup_identity'
        if path.name != unit_name or path.parent.name != 'system.slice':
            raise ValueError('wrapper is outside owned system.slice unit')
        stage = 'wrapper_identity'
        result['wrapper_identity'] = _process_identity(os.getpid())
        stage = 'read_cpu_topology'
        result['topology_before'] = read_cpu_topology()
        stage = 'read_cgroup_snapshot'
        result['before'] = read_cgroup_snapshot(path, profile=profile)
        stage = 'validate_enforcement'
        validate_enforcement(profile, result['before'], result['topology_before'])
        stage = 'validate_wrapper_membership'
        if os.getpid() not in result['before']['pids']:
            raise ValueError('wrapper cgroup membership unavailable')
        stage = 'write_before_receipt'
        _write_json(artifact_dir / 'guard-cgroup-before.json', result)
        stage = 'child_execution'
        if stopped[0]:
            raise ValueError('wrapper interrupted before child launch')
        process = subprocess.Popen(list(command), stdin=subprocess.DEVNULL)
        result['child_identity'] = _process_identity(process.pid)
        while True:
            try:
                result['child_returncode'] = process.wait(timeout=.1)
                break
            except subprocess.TimeoutExpired:
                running = read_cgroup_snapshot(path, profile=profile)
                # Preserve the observed violation before refusing more work.
                with (artifact_dir / 'guard-cgroup-running.jsonl').open('a', encoding='utf-8') as stream:
                    stream.write(json.dumps(running, sort_keys=True, allow_nan=False) + '\n')
                validate_enforcement(profile, running, read_cpu_topology())
                validate_snapshot_pair(result['before'], running)
                if stopped[0]:
                    # Leave the wrapper alive to collect after all owned work.
                    result['containment'] = _drain_owned_children(path, interrupted=lambda: True)
        result['outcome'] = 'GUARD_COMPLETE' if result['child_returncode'] == 0 and not stopped[0] else 'UNRESOLVED_FAILURE'
    except Exception as exc:
        result['error'] = f'{type(exc).__name__}: {exc}'
        diagnostic = {
            'schema': 'compute-metabolism-v0-guard-diagnostic-v1',
            'run_id': run_id, 'unit': unit_name, 'profile': profile_key,
            'stage': stage, 'exception_type': type(exc).__name__,
            'exception_message': str(exc), 'cgroup_path': str(path) if path is not None else None,
            'wrapper_pid': os.getpid(), 'before_available': result['before'] is not None,
            'outcome': 'ENVIRONMENT_INVALID', 'measurement_valid': False,
        }
        if hasattr(exc, 'process_evidence'):
            diagnostic['process_evidence'] = exc.process_evidence
        if hasattr(exc, 'counter_failure'):
            diagnostic['counter_failure'] = exc.counter_failure
            diagnostic['raw_counter_files'] = exc.raw_counter_files
        result['diagnostic'] = diagnostic
        try:
            # Separate error evidence never substitutes for a final measurement.
            _write_json(artifact_dir / 'guard-diagnostic.json', diagnostic)
            for name, raw in diagnostic.get('raw_counter_files', {}).items():
                with (artifact_dir / name).open('xb') as stream:
                    stream.write(raw.encode('utf-8'))
                    stream.flush()
                    os.fsync(stream.fileno())
        except Exception as write_exc:
            diagnostic['receipt_write_error'] = _failure(write_exc)
    finally:
        try:
            if path is not None and result['before'] is not None:
                result['cleanup_errors'] = []
                try:
                    result['containment'] = _drain_owned_children(path, interrupted=lambda: stopped[0] or 'error' in result)
                except Exception as exc:
                    result['cleanup_errors'].append({'stage': 'drain', **_failure(exc)})
                    # A failed natural drain must not suppress an owned kill
                    # drain, direct child reap, or attempted final collection.
                    try:
                        result['containment'] = _drain_owned_children(path, interrupted=lambda: True)
                    except Exception as retry_exc:
                        result['cleanup_errors'].append({'stage': 'forced_drain', **_failure(retry_exc)})
                if process is not None:
                    if result['cleanup_errors']:
                        try:
                            process.kill()
                        except Exception as exc:
                            result['cleanup_errors'].append({'stage': 'child_kill', **_failure(exc)})
                    try:
                        result['child_returncode'] = process.wait(timeout=5)
                    except Exception as exc:
                        result['cleanup_errors'].append({'stage': 'child_reap', **_failure(exc)})
                result['final_errors'] = []
                result['topology_after'] = None
                try:
                    result['topology_after'] = read_cpu_topology()
                except Exception as exc:
                    result['final_errors'].append({'stage': 'topology', **_failure(exc)})
                try:
                    result['after'] = read_cgroup_snapshot(path, profile=profile)
                except Exception as exc:
                    result['final_errors'].append({'stage': 'cgroup_snapshot', **_failure(exc)})
                if result['after'] is not None and result['topology_after'] is not None:
                    try:
                        validate_enforcement(profile, result['after'], result['topology_after'])
                        if result['topology_before'] != result['topology_after']:
                            raise ValueError('guest topology changed')
                        result['delta'] = validate_snapshot_pair(result['before'], result['after'])
                        if result.get('containment', {}).get('remaining_pids') or any(pid != os.getpid() for pid in result['after']['pids']):
                            raise ValueError('owned descendants remain at final snapshot')
                    except Exception as exc:
                        result['final_errors'].append({'stage': 'final_validation', **_failure(exc)})
                result['measurement_valid'] = ('error' not in result and not result['cleanup_errors']
                    and not result['final_errors'] and 'containment' in result)
                if not result['measurement_valid']:
                    result['outcome'] = 'ENVIRONMENT_INVALID'
                result['interrupted'] = stopped[0]
                _write_json(artifact_dir / 'guard-cgroup-final.json', result)
        except Exception as exc:
            result.update(outcome='ENVIRONMENT_INVALID', measurement_valid=False,
                          final_error=f'{type(exc).__name__}: {exc}')
            try:
                _write_json(artifact_dir / 'guard-cgroup-invalid.json', result)
            except Exception as write_exc:
                result['invalid_receipt_error'] = _failure(write_exc)
        for sig, handler in old_handlers.items():
            signal.signal(sig, handler)
    return result


def _unit_terminal(unit_name: str, evidence: list | None = None) -> bool:
    _owned_name(unit_name)
    observed = {'unit': unit_name, 'returncode': None, 'stdout': None, 'stderr': None}
    if evidence is not None:
        evidence.append(observed)
    try:
        proc = subprocess.run(['sudo', '-n', 'systemctl', 'show', unit_name,
                               '--property=LoadState,ActiveState,SubState,ControlGroup'],
                              capture_output=True, text=True, timeout=5)
    except Exception as exc:
        observed.update(_failure(exc))
        raise
    observed.update(returncode=proc.returncode, stdout=proc.stdout, stderr=proc.stderr,
                    monotonic_seconds=time.monotonic())
    if proc.returncode != 0:
        raise ValueError('unit termination authority unavailable')
    props = dict(line.split('=', 1) for line in proc.stdout.splitlines() if '=' in line)
    if props.get('LoadState') == 'not-found':
        return True
    if props.get('ActiveState') not in ('inactive', 'failed'):
        return False
    cg = props.get('ControlGroup')
    if cg:
        if not cg.startswith('/system.slice/') or PurePosixPath(cg).name != unit_name:
            raise ValueError('unit ControlGroup identity mismatch')
        path = CGROUP_ROOT / cg.lstrip('/')
        if path.exists() and _cgroup_pids(path):
            return False
    return True


def _stop_owned_unit(unit_name: str) -> dict:
    _owned_name(unit_name)
    commands = []
    states = []
    errors = []
    # SIGTERM main permits final snapshot. The systemd KillMode remains
    # control-group for the definitive stop, including new process sessions.
    def run(argv):
        record = {'argv': argv, 'returncode': None, 'stdout': None, 'stderr': None}
        commands.append(record)
        try:
            proc = subprocess.run(argv, capture_output=True, text=True, timeout=5)
            record.update(returncode=proc.returncode, stdout=proc.stdout, stderr=proc.stderr)
            if proc.returncode != 0:
                errors.append({'stage': argv[3], 'returncode': proc.returncode})
        except Exception as exc:
            record.update(_failure(exc))
            errors.append({'stage': argv[3], **_failure(exc)})
    def query():
        try:
            return _unit_terminal(unit_name, evidence=states)
        except Exception as exc:
            errors.append({'stage': 'unit_state', **_failure(exc)})
            return False
    run(['sudo', '-n', 'systemctl', 'kill', '--kill-whom=main', '--signal=SIGTERM', unit_name])
    grace_end = time.monotonic() + 2
    while time.monotonic() < grace_end:
        if query() and not errors:
            return {'terminal': True, 'commands': commands, 'unit_states': states, 'errors': errors}
        if errors:
            break
        time.sleep(.05)
    run(['sudo', '-n', 'systemctl', 'kill', '--kill-whom=all', '--signal=SIGKILL', unit_name])
    run(['sudo', '-n', 'systemctl', 'stop', unit_name])
    return {'terminal': query(), 'commands': commands, 'unit_states': states, 'errors': errors}


def run_system_guard(profile: ProfileSpec, *, run_id: str, artifact_dir: Path,
        command: Sequence[str], topology: dict, root_directory: Path = PREPARED_ROOT,
        limits: CampaignLimits | None = None) -> dict:
    limits = _approved(profile, limits)
    return _run_outer(profile, run_id=run_id, artifact_dir=artifact_dir, command=command,
                      topology=topology, root_directory=root_directory,
                      limits=limits, deadline_seconds=limits.per_run_wall_seconds, test_only=False)


def run_system_guard_test_only_probe(profile: ProfileSpec, *, test_only_wall_seconds: float,
        run_id: str, artifact_dir: Path, command: Sequence[str], topology: dict,
        root_directory: Path = PREPARED_ROOT) -> dict:
    if type(test_only_wall_seconds) not in (int, float) or not 0 < test_only_wall_seconds < 180:
        raise ValueError('TEST_ONLY probe requires a shorter deadline')
    return _run_outer(profile, run_id=run_id, artifact_dir=artifact_dir, command=command,
                      topology=topology, root_directory=root_directory, limits=_approved(profile),
                      deadline_seconds=test_only_wall_seconds, test_only=True)


def _run_outer(profile, *, run_id, artifact_dir, command, topology, root_directory,
               limits, deadline_seconds, test_only):
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', run_id):
        raise ValueError('invalid run ID')
    root = Path(root_directory).resolve(strict=True)
    path = Path(artifact_dir).resolve()
    inner = _artifact_path(PurePosixPath('/') / path.relative_to(root).as_posix())
    if path.name != run_id:
        raise ValueError('artifact basename must bind run ID')
    unit = f'compute-metabolism-{uuid.uuid4().hex}.service'
    argv = build_systemd_run_argv(profile, unit_name=unit, artifact_dir=inner,
                                  command=command, root_directory=root, limits=limits)
    path.mkdir(mode=0o700, exist_ok=False)
    with (path / 'writer_quota.txt').open('xb') as quota:
        quota.write(b'0')
    ownership = prepare_artifact_ownership(path)
    _validate_unit_execution_identity(argv)
    result = {'run_id': run_id, 'unit': unit, 'profile': profile.key, 'argv': argv,
              'test_only': test_only, 'deadline_seconds': deadline_seconds,
              'writer_bytes': limits.writer_bytes, 'before': None, 'after': None,
              'outcome': 'ENVIRONMENT_INVALID', 'measurement_valid': False,
              'outer_timeout_proved': False, 'terminal': False, 'returncode': None,
              'launcher_reaped': False, 'unit_states': [], 'cleanup_attempts': [],
              'artifact_ownership': ownership}
    def cleanup():
        attempt = _stop_owned_unit(unit)
        result['cleanup_attempts'].append(attempt)
        result['cleanup'] = attempt
        return attempt
    started = time.monotonic()
    process = None
    try:
        # Recheck immediately before launch; a successful chown call is not proof.
        validate_artifact_ownership(path)
        _validate_unit_execution_identity(argv)
        # Files avoid PIPE deadlock/unbounded communicate buffering. No timeout
        # cleanup can be avoided by a child holding stdout open.
        with (path / 'systemd-stdout.log').open('xb') as stdout, (path / 'systemd-stderr.log').open('xb') as stderr:
            process = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr)
            try:
                remaining = deadline_seconds - (time.monotonic() - started)
                if remaining <= 0:
                    raise subprocess.TimeoutExpired(argv, deadline_seconds)
                result['returncode'] = process.wait(timeout=remaining)
                result['launcher_reaped'] = True
            except subprocess.TimeoutExpired:
                observed = time.monotonic()
                # wait timeout alone is not a proved monotonic deadline.
                result['outer_timeout_proved'] = observed - started >= deadline_seconds
                result['timeout_observed_monotonic'] = observed
                result['cleanup'] = cleanup()
                result['terminal'] = result['cleanup']['terminal']
                # A not-yet-created unit may still have a live systemd-run
                # launcher. Cancel that owned launcher before proving absence.
                process.kill()
                result['launcher_stop_requested'] = True
                result['returncode'] = process.wait(timeout=10)
                result['launcher_reaped'] = True
                result['terminal'] = False  # recheck only after launcher reap
            if not result['terminal']:
                result['terminal'] = _unit_terminal(unit, evidence=result['unit_states'])
                if not result['terminal']:
                    result['cleanup'] = cleanup()
                    result['terminal'] = result['cleanup']['terminal']
    except Exception as exc:
        result['error'] = f'{type(exc).__name__}: {exc}'
        if process is not None:
            try:
                result['cleanup'] = cleanup()
                result['terminal'] = result['cleanup']['terminal']
                result['returncode'] = process.wait(timeout=10)
                result['launcher_reaped'] = True
            except Exception as cleanup_exc:
                result['cleanup_error'] = f'{type(cleanup_exc).__name__}: {cleanup_exc}'
                # This Popen object is the launcher we created. Unit cleanup
                # happens first; killing the launcher never substitutes for it.
                try:
                    process.kill()
                    result['returncode'] = process.wait(timeout=5)
                    result['launcher_reaped'] = True
                except Exception as reap_exc:
                    result['reap_error'] = f'{type(reap_exc).__name__}: {reap_exc}'
            if result['launcher_reaped']:
                try:
                    result['terminal'] = _unit_terminal(unit, evidence=result['unit_states'])
                    if not result['terminal']:
                        result['post_reap_cleanup'] = cleanup()
                        result['terminal'] = result['post_reap_cleanup']['terminal']
                except Exception as unit_exc:
                    result['terminal'] = False
                    result['terminal_error'] = f'{type(unit_exc).__name__}: {unit_exc}'
    finally:
        result['wall_seconds'] = time.monotonic() - started
    try:
        final = json.loads((path / 'guard-cgroup-final.json').read_text())
        if (final['run_id'], final['unit'], final['profile']) != (run_id, unit, profile.key):
            raise ValueError('terminal receipt identity mismatch')
        if (not final['measurement_valid'] or not result['terminal'] or not result['launcher_reaped']
                or 'error' in result or any(attempt.get('errors') for attempt in result['cleanup_attempts'])):
            raise ValueError('terminal authority invalid')
        before_receipt = json.loads((path / 'guard-cgroup-before.json').read_text())
        if before_receipt['before'] != final['before']:
            raise ValueError('before receipt mismatch')
        for which in ('before', 'after'):
            validate_enforcement(profile, final[which], final['topology_' + which])
            if final['topology_' + which] != topology:
                raise ValueError('live topology differs from admitted topology')
            cg = Path(final[which]['epoch']['path'])
            if cg.name != unit or cg.parent.name != 'system.slice':
                raise ValueError('snapshot owned cgroup identity mismatch')
        if final['containment']['remaining_pids']:
            raise ValueError('owned descendants uncontained')
        if any(pid != final['wrapper_identity']['pid'] for pid in final['after']['pids']):
            raise ValueError('descendants remain in terminal snapshot')
        result['before'], result['after'] = final['before'], final['after']
        result['delta'] = validate_snapshot_pair(result['before'], result['after'])
        result['measurement_valid'] = True
        result['inner'] = final
        if result['outer_timeout_proved']:
            result.update(outcome='REFUSED_RESOURCE', resource_reason='OUTER_WALL_TIMEOUT')
        elif result['wall_seconds'] > deadline_seconds:
            result.update(outcome='REFUSED_RESOURCE', resource_reason='OUTER_WALL_TIMEOUT', outer_timeout_proved=True)
        elif result['returncode'] == 0 and final['outcome'] == 'GUARD_COMPLETE':
            result['outcome'] = 'GUARD_COMPLETE'
        else:
            result['outcome'] = 'UNRESOLVED_FAILURE'
    except Exception as exc:
        result.update(outcome='ENVIRONMENT_INVALID', measurement_valid=False,
                      measurement_error=f'{type(exc).__name__}: {exc}')
    _write_json(path / 'guard-outer.json', result)
    return result


def main(argv: Sequence[str] | None = None) -> int:
    raw_args = list(sys.argv[1:] if argv is None else argv)
    if '--' not in raw_args:
        raise ValueError('inner CLI requires explicit child argv separator')
    split = raw_args.index('--')
    option_args, command = raw_args[:split], raw_args[split + 1:]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['inner'])
    parser.add_argument('--profile', choices=['2c', '1c', '0p5c'], required=True)
    parser.add_argument('--unit', required=True)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--artifact-dir', type=Path, required=True)
    args = parser.parse_args(option_args)
    if not command:
        parser.error('child argv required')
    _artifact_path(PurePosixPath(args.artifact_dir))
    result = run_inner(profile_key=args.profile, run_id=args.run_id, unit_name=args.unit,
                       artifact_dir=args.artifact_dir, command=command)
    if 'diagnostic' in result:
        print(json.dumps(result['diagnostic'], sort_keys=True, allow_nan=False), file=sys.stderr, flush=True)
    return 0 if result['outcome'] == 'GUARD_COMPLETE' and result['measurement_valid'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
