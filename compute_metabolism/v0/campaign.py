"""Durable, exclusive upper allowance for all Compute Metabolism V0 attempts.

The ledger's parent is the entire retained artifact root. Prepared rootfs and
source must live outside it. All file entries, including metadata and hardlink
entries, count by logical length. This module never deletes evidence to fit a cap.
An attempt remains RUNNING until the caller has confirmed terminal/reaped owned
work. Unknown containment must use record_unresolved(), which cannot be released
through finish_attempt(). No stale recovery/reset API is supplied.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict
import json
import hashlib
import argparse
import math
import os
from pathlib import Path
import re
import stat
import tempfile
import subprocess
import sys
import time
from typing import Iterator

from .profiles import CampaignLimits, get_profile


class LedgerIntegrityError(ValueError):
    """Missing, incompatible, or inconsistent upper allowance."""


class UnsafeArtifactTree(ValueError):
    """Artifact accounting would follow an alias or nonregular entry."""


class UnresolvedPriorAttempt(RuntimeError):
    """A durable RUNNING marker still owns the next-attempt authority."""


class AttemptIdentityError(ValueError):
    """Duplicate ID or a finish/receipt for a different running attempt."""


class CampaignResourceExhausted(RuntimeError):
    """The upper allowance cannot fully fund a new numerical attempt."""


_SCHEMA = 'compute-metabolism-v0-upper-ledger-v1'
_OUTCOMES = frozenset(('ACCEPT', 'REFUSED_RESOURCE', 'REFUSED_VERIFICATION',
                      'ENVIRONMENT_INVALID', 'UNRESOLVED_FAILURE', 'GUARD_COMPLETE'))
_UNKNOWN_CPU_OUTCOMES = frozenset(('REFUSED_VERIFICATION', 'ENVIRONMENT_INVALID', 'UNRESOLVED_FAILURE'))
_ROLES = frozenset(('measured', 'warm-up', 'guard-preflight'))
_IDENTIFIER = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]*\Z')


def _number(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f'{label} must be finite nonnegative numeric')
    try:
        valid = math.isfinite(value) and value >= 0
    except OverflowError:
        valid = False
    if not valid:
        raise ValueError(f'{label} must be finite nonnegative numeric')
    return float(value)


def _integer(value: object, label: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f'{label} must be a nonnegative integer')
    return value


def _identifier(value: str, label: str) -> str:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise ValueError(f'{label} must be a simple nonempty identifier')
    return value


def _alias(info: os.stat_result) -> bool:
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, 'st_file_attributes', 0) & 0x400)


def _safe_path(path: Path) -> Path:
    path = Path(path)
    if '..' in path.parts:
        raise UnsafeArtifactTree('parent traversal is forbidden')
    absolute = Path(os.path.abspath(path))
    for item in reversed((absolute, *absolute.parents)):
        try:
            info = item.lstat()
        except FileNotFoundError:
            continue
        if _alias(info):
            raise UnsafeArtifactTree(f'alias path refused: {item}')
    return absolute


def logical_tree_bytes(path: Path) -> int:
    """Count logical bytes per regular file entry; refuse aliases/special files.

    Linux traversal opens directories with O_NOFOLLOW and checks directory
    identity, avoiding symlink substitution between inspection and traversal.
    Windows additionally refuses all reparse-point entries (including junctions).
    """
    path = _safe_path(path)
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode):
        raise UnsafeArtifactTree('artifact root must be a directory')

    def walk(directory: Path, expected: os.stat_result) -> int:
        descriptor = None
        if os.name == 'posix':
            descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            actual = os.fstat(descriptor)
            if (actual.st_dev, actual.st_ino) != (expected.st_dev, expected.st_ino):
                os.close(descriptor)
                raise UnsafeArtifactTree('artifact directory identity changed')
        try:
            total = 0
            with os.scandir(descriptor if descriptor is not None else directory) as entries:
                for entry in entries:
                    item = directory / entry.name
                    item_info = entry.stat(follow_symlinks=False)
                    if _alias(item_info):
                        raise UnsafeArtifactTree(f'alias entry refused: {item}')
                    if stat.S_ISREG(item_info.st_mode):
                        total += item_info.st_size
                    elif stat.S_ISDIR(item_info.st_mode):
                        total += walk(item, item_info)
                    else:
                        raise UnsafeArtifactTree(f'nonregular entry refused: {item}')
            return total
        finally:
            if descriptor is not None:
                os.close(descriptor)
    return walk(path, info)


def _encode(state: dict) -> bytes:
    return (json.dumps(state, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode('utf-8')


def _read(path: Path) -> dict:
    _safe_path(path)
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise LedgerIntegrityError('ledger must be an unaliased regular file')
    try:
        state = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(state, dict) or state.get('schema') != _SCHEMA:
            raise ValueError('incompatible schema')
        if state['limits'] != asdict(CampaignLimits()):
            raise ValueError('fixed limits mismatch')
        _integer(state['retained_total_bytes'], 'retained_total_bytes')
        ids = set()
        walls = []
        running_records = []
        for record in state['attempts']:
            run_id = _identifier(record['run_id'], 'run_id')
            _identifier(record['campaign_id'], 'campaign_id')
            get_profile(record['profile'])
            if record['role'] not in _ROLES:
                raise ValueError('unknown role')
            _integer(record['round_index'], 'round_index')
            if run_id in ids:
                raise ValueError('duplicate run identity')
            ids.add(run_id)
            if record['status'] == 'RUNNING':
                running_records.append(record)
            elif record['status'] == 'FINISHED':
                walls.append(_number(record['outer_wall_seconds'], 'outer_wall_seconds'))
                _validate_metrics(record['cpu_seconds'], record['writer_reserved_bytes'],
                                  record['retained_bytes'], record['outcome'], record['role'])
                expected_cpu_status = 'UNAVAILABLE' if record['cpu_seconds'] is None else 'AVAILABLE'
                if record['cpu_measurement_status'] != expected_cpu_status:
                    raise ValueError('CPU measurement status mismatch')
            else:
                raise ValueError('unknown attempt status')
        expected_running = None
        if len(running_records) == 1:
            expected_running = {key: running_records[0][key] for key in
                                ('campaign_id', 'run_id', 'profile', 'role', 'round_index')}
        if len(running_records) > 1 or state['running'] != expected_running:
            raise ValueError('running identity mismatch')
        if _number(state['total_wall_seconds'], 'total_wall_seconds') != math.fsum(walls):
            raise ValueError('wall cumulative mismatch')
    except (ValueError, KeyError, TypeError, OverflowError) as error:
        raise LedgerIntegrityError(f'invalid upper ledger: {error}') from error
    return state


def _validate_metrics(cpu: float | None, reserved: int, retained: int, outcome: str, role: str) -> None:
    if outcome not in _OUTCOMES or (outcome == 'GUARD_COMPLETE' and role != 'guard-preflight'):
        raise ValueError('unknown outcome or invalid guard-only outcome')
    if cpu is None:
        if outcome not in _UNKNOWN_CPU_OUTCOMES:
            raise ValueError('complete CPU measurement required for this outcome')
    else:
        _number(cpu, 'cpu_seconds')
    _integer(reserved, 'writer_reserved_bytes')
    _integer(retained, 'retained_bytes')


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(_safe_path(path), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _create_durable_artifact_root(root: Path) -> None:
    """Persist Linux directory entries before any initial allowance is issued.

    Capture the missing child-to-parent chain before mkdir. Also sync all
    existing ancestors: an earlier failed fsync may have left empty directories
    that now exist but whose parent entries still have no durability evidence.
    No Linux error is ignored. Windows directory durability remains unverified.
    """
    root = _safe_path(root)
    missing = []
    existing = root
    while not existing.exists():
        missing.append(existing)
        existing = existing.parent
    root.mkdir(parents=True, exist_ok=True)
    if os.name == 'posix':
        for directory in (*missing, existing, *existing.parents):
            _fsync_directory(directory)


class CampaignLedger:
    """One persistent allowance; every mutation rechecks it under an OS lock."""

    def __init__(self, path: Path, limits: CampaignLimits):
        self.path = path
        self.limits = limits
        self.root = path.parent
        self.authority_path = path.with_name('.' + path.name + '.authority')
        self._owned_run: tuple[str, int] | None = None

    @classmethod
    def read_snapshot(cls, path: Path) -> dict:
        """Read validated disk state and separately observed bytes with zero writes.

        No file/lock creation, reconciliation, or allowance authority is granted.
        Stored retained_total_bytes remains unchanged. The additional
        observed_retained_total_bytes is an unlocked filesystem observation;
        concurrent writers may change the tree between the two reads.
        """
        path = _safe_path(path)
        state = _read(path)
        state['observed_retained_total_bytes'] = logical_tree_bytes(path.parent)
        return state

    @classmethod
    def open(cls, path: Path, limits: CampaignLimits) -> CampaignLedger:
        if type(limits) is not CampaignLimits or asdict(limits) != asdict(CampaignLimits()):
            raise LedgerIntegrityError('only fixed CampaignLimits are permitted')
        path = _safe_path(path)
        # Existing incompatible/historical files are validated before any writes.
        if path.exists():
            _read(path)
        elif path.parent.exists() and any(path.parent.iterdir()):
            raise LedgerIntegrityError('missing upper ledger in nonempty artifact root; reset refused')
        _create_durable_artifact_root(path.parent)
        ledger = cls(path, limits)
        with ledger._authority() as created_authority:
            if path.exists():
                ledger._write(_read(path))
            elif not created_authority or any(p != ledger.authority_path for p in path.parent.iterdir()):
                raise LedgerIntegrityError('missing upper ledger; initialization/reset refused')
            else:
                ledger._write({'schema': _SCHEMA, 'limits': asdict(limits), 'attempts': [], 'start_refusals': [],
                               'running': None, 'total_wall_seconds': 0, 'retained_total_bytes': 0})
        return ledger

    @contextmanager
    def _authority(self) -> Iterator[bool]:
        _safe_path(self.authority_path)
        created = False
        try:
            fd = os.open(self.authority_path, os.O_RDWR | os.O_CREAT | os.O_EXCL, 0o600)
            created = True
            os.write(fd, b'1')
            os.fsync(fd)
        except FileExistsError:
            fd = os.open(self.authority_path, os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0))
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size != 1:
                raise LedgerIntegrityError('invalid exclusive authority file')
            if os.name == 'posix':
                import fcntl
                fcntl.flock(fd, fcntl.LOCK_EX)
            elif os.name == 'nt':
                import msvcrt
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_LOCK, 1)
            else:
                raise LedgerIntegrityError('exclusive durable authority unsupported on this OS')
            try:
                yield created
            finally:
                if os.name == 'posix':
                    fcntl.flock(fd, fcntl.LOCK_UN)
                else:
                    os.lseek(fd, 0, os.SEEK_SET)
                    msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        finally:
            os.close(fd)

    def _prepare_payload(self, state: dict) -> bytes:
        total = logical_tree_bytes(self.root)
        old_size = self.path.stat().st_size if self.path.exists() else 0
        other_bytes = total - old_size
        # The current metadata counts itself. Iterate to the decimal-size fixed point.
        state['retained_total_bytes'] = other_bytes
        while True:
            payload = _encode(state)
            retained = other_bytes + len(payload)
            if retained == state['retained_total_bytes']:
                return payload
            state['retained_total_bytes'] = retained

    def _write(self, state: dict) -> None:
        payload = self._prepare_payload(state)
        fd, name = tempfile.mkstemp(prefix='.' + self.path.name + '.', suffix='.pending', dir=self.root)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        # Failed replacements retain the pending file as failure evidence.
        os.replace(name, self.path)
        if os.name == 'posix':
            _fsync_directory(self.root)

    def snapshot(self) -> dict:
        """Reconcile actual retained bytes and return a detached durable snapshot."""
        with self._authority():
            state = _read(self.path)
            self._write(state)
            return state

    def _can_start(self, state: dict, campaign_id: str | None = None) -> tuple[bool, str | None]:
        if state['running'] is not None:
            return False, 'UNRESOLVED_PRIOR_ATTEMPT'
        if any(record.get('retained_bytes', 0) > self.limits.retained_run_bytes and
               (campaign_id is None or record['campaign_id'] == campaign_id)
               for record in state['attempts']):
            return False, 'EVIDENCE_GROWTH'
        return self._funds(state)

    def _funds(self, state: dict) -> tuple[bool, str | None]:
        if self.limits.total_wall_seconds - state['total_wall_seconds'] < self.limits.per_run_wall_seconds:
            return False, 'CAMPAIGN_WALL_EXHAUSTED'
        if self.limits.retained_total_bytes - state['retained_total_bytes'] < self.limits.retained_run_bytes:
            return False, 'CAMPAIGN_RETAINED_EXHAUSTED'
        return True, None

    def can_start_attempt(self, campaign_id: str | None = None) -> tuple[bool, str | None]:
        """Advisory precheck, repeated at begin; no-ID conservatively sees all STOPs.

        Evidence-growth STOP is campaign scoped. The caller must separately have
        authorization to restart under a new campaign ID; this API never grants
        that approval or resets upper cumulative resources.
        """
        if campaign_id is not None:
            _identifier(campaign_id, 'campaign_id')
        return self._can_start(self.snapshot(), campaign_id)

    def begin_attempt(self, campaign_id: str, run_id: str, profile: str,
                      role: str, round_index: int) -> dict:
        """Persist RUNNING before granting authority; no numerical work starts here."""
        _identifier(campaign_id, 'campaign_id')
        _identifier(run_id, 'run_id')
        get_profile(profile)
        if role not in _ROLES:
            raise ValueError('unknown attempt role')
        _integer(round_index, 'round_index')
        with self._authority():
            state = _read(self.path)
            self._write(state)
            if state['running'] is not None:
                raise UnresolvedPriorAttempt(state['running']['run_id'])
            if any(record['run_id'] == run_id for record in state['attempts']):
                raise AttemptIdentityError('run ID already used')
            allowed, reason = self._can_start(state, campaign_id)
            identity = dict(campaign_id=campaign_id, run_id=run_id, profile=profile,
                            role=role, round_index=round_index)
            if not allowed:
                self._refuse_start(state, identity, reason)
            state['running'] = identity
            record = dict(identity, status='RUNNING', partial_receipts=[])
            state['attempts'].append(record)
            self._prepare_payload(state)
            allowed, reason = self._funds(state)
            if not allowed:
                state['attempts'].pop()
                state['running'] = None
                self._refuse_start(state, identity, reason)
            self._write(state)
            self._owned_run = (run_id, os.getpid())
            return dict(identity)

    def _refuse_start(self, state: dict, identity: dict, reason: str) -> None:
        # Administrative prelaunch refusal grants no executable authority/wall.
        state.setdefault('start_refusals', []).append(dict(identity, reason=reason))
        self._write(state)
        raise CampaignResourceExhausted(reason)

    def _running_record(self, state: dict, run_id: str) -> dict:
        if state['running'] is None or state['running']['run_id'] != run_id:
            raise AttemptIdentityError('no matching RUNNING identity')
        return next(record for record in state['attempts'] if record['run_id'] == run_id)

    def record_unresolved(self, run_id: str, partial_receipt: dict) -> None:
        """Keep partial evidence and permanently block normal finish/new authority."""
        if not isinstance(partial_receipt, dict):
            raise ValueError('partial receipt must be an object')
        receipt = json.loads(_encode(partial_receipt))
        with self._authority():
            state = _read(self.path)
            record = self._running_record(state, run_id)
            record['partial_receipts'].append(receipt)
            record['containment_unresolved'] = True
            self._write(state)

    def finish_attempt(self, run_id: str, outer_wall_seconds: float,
                       cpu_seconds: float | None, writer_reserved_bytes: int,
                       retained_bytes: int, outcome: str) -> dict:
        """Charge actual wall after terminal/reap confirmed by the begin-owning caller.

        CPU None is explicit unavailable evidence for invalid outcomes only.
        Per-attempt writer reservation and retained metrics never replace the
        actual recursive upper artifact measurement. Actual charges are uncapped.
        Only the exact begin-owning object and original OS process may finish;
        reopened objects, spawned processes and forks cannot recover authority.
        """
        wall = _number(outer_wall_seconds, 'outer_wall_seconds')
        with self._authority():
            state = _read(self.path)
            record = self._running_record(state, run_id)
            if self._owned_run != (run_id, os.getpid()):
                raise UnresolvedPriorAttempt('finish requires the same begin-owning object and OS process')
            if record.get('containment_unresolved'):
                raise UnresolvedPriorAttempt('containment remains unresolved; no recovery API')
            _validate_metrics(cpu_seconds, writer_reserved_bytes, retained_bytes, outcome, record['role'])
            record.update(status='FINISHED', outer_wall_seconds=wall,
                          cpu_seconds=cpu_seconds, cpu_measurement_status='UNAVAILABLE' if cpu_seconds is None else 'AVAILABLE',
                          writer_reserved_bytes=writer_reserved_bytes, retained_bytes=retained_bytes,
                          outcome=outcome)
            state['running'] = None
            state['total_wall_seconds'] = math.fsum(r['outer_wall_seconds'] for r in state['attempts'] if r['status'] == 'FINISHED')
            self._write(state)
            self._owned_run = None
            return json.loads(_encode(record))


_ROUND_ORDER = (('2c', '1c', '0p5c'), ('1c', '0p5c', '2c'),
                ('0p5c', '2c', '1c'), ('2c', '0p5c', '1c'),
                ('0p5c', '1c', '2c'), ('1c', '2c', '0p5c'), ('2c', '1c', '0p5c'))
_GLOBAL_REASONS = frozenset(('EVIDENCE_GROWTH', 'CAMPAIGN_EVIDENCE_CEILING', 'CAMPAIGN_WALL_CEILING'))
_FAULTS = frozenset(('REFUSED_VERIFICATION', 'ENVIRONMENT_INVALID', 'UNRESOLVED_FAILURE'))


def sample_cv(values: list[float]) -> float:
    """Sample SD (n-1) / mean; undefined measurements are refused, never zeroed."""
    if len(values) < 2:
        raise ValueError('CV needs at least two measurements')
    numbers = [_number(value, 'CV measurement') for value in values]
    mean = math.fsum(numbers) / len(numbers)
    if mean <= 0:
        raise ValueError('CV requires positive mean')
    return math.sqrt(math.fsum((value - mean)**2 for value in numbers) / (len(numbers)-1)) / mean


def profile_decision(profile: str, attempts: list[dict]) -> dict:
    get_profile(profile)
    rows = [row for row in attempts if row.get('role') == 'measured' and row.get('profile') == profile]
    n = len(rows)
    result = dict(profile=profile, n=n, decision='COLLECT_TO_3', wall_cv=None, cpu_cv=None)
    outcomes = [row.get('wrapper_outcome', row.get('outcome')) for row in rows]
    if any(row.get('status') != 'FINISHED' or row.get('campaign_stop') or outcome in _FAULTS
           or not row.get('invariants_valid') or not row.get('eligible')
           or outcome not in ('ACCEPT', 'REFUSED_RESOURCE')
           or (outcome == 'REFUSED_RESOURCE' and (not row.get('resource_proven') or row.get('resource_reason') in _GLOBAL_REASONS))
           for row, outcome in zip(rows, outcomes)):
        result['decision'] = 'STOP'
        return result
    if n < 3:
        return result
    first = rows[:3]
    if profile == '0p5c' and n == 3 and all(outcome == 'REFUSED_RESOURCE' for outcome in outcomes) and len({row['resource_reason'] for row in first}) == 1:
        result['decision'] = 'STABLE_RESOURCE_REFUSAL'
        return result
    if all(outcome == 'REFUSED_RESOURCE' for outcome in outcomes):
        result['decision'] = 'STOP_INCOMPLETE'
        return result
    if n not in (3, 5, 7):
        result['decision'] = 'COLLECT_TO_5' if n < 5 else 'COLLECT_TO_7' if n < 7 else 'STOP'
        return result
    if all(outcome == 'ACCEPT' for outcome in outcomes):
        try:
            result.update(wall_cv=sample_cv([row['outer_wall_seconds'] for row in rows]),
                          cpu_cv=sample_cv([row['cpu_seconds'] for row in rows]))
        except (KeyError, ValueError, TypeError):
            result['decision'] = 'STOP'
            return result
        if result['wall_cv'] <= .05 and result['cpu_cv'] <= .05:
            result['decision'] = 'STABLE_ACCEPT'
            return result
    result['decision'] = {3:'EXPAND_TO_5', 5:'EXPAND_TO_7', 7:'UNRESOLVED_VARIABILITY'}[n]
    return result


def next_attempt(history: list[dict]) -> dict | None:
    """One exact scheduled item, retaining all attempts and never creating round 8."""
    rows = [row for row in history if row.get('role') != 'guard-preflight']
    if any(row.get('status') != 'FINISHED' or row.get('campaign_stop') or
           row.get('wrapper_outcome', row.get('outcome')) in _FAULTS for row in rows):
        return None
    if not rows:
        return dict(profile='2c', role='warm-up', round_index=0, requested_steps=1)
    warmups = [row for row in rows if row.get('role') == 'warm-up']
    if len(warmups) != 1 or warmups[0].get('outcome') != 'ACCEPT' or not warmups[0].get('eligible'):
        return None
    if any(profile_decision(profile, rows)['decision'] in ('STOP', 'STOP_INCOMPLETE') for profile in ('2c','1c','0p5c')):
        return None
    for round_index, order in enumerate(_ROUND_ORDER, 1):
        prior = [row for row in rows if row.get('role') == 'measured' and row.get('round_index', 0) < round_index]
        decisions = {profile: profile_decision(profile, prior)['decision'] for profile in order}
        if any(value in ('STOP', 'STOP_INCOMPLETE', 'UNRESOLVED_VARIABILITY') for value in decisions.values()):
            return None
        for profile in order:
            if round_index > 3 and decisions[profile] in ('STABLE_ACCEPT', 'STABLE_RESOURCE_REFUSAL'):
                continue
            if not any(row.get('role') == 'measured' and row.get('profile') == profile and row.get('round_index') == round_index for row in rows):
                return dict(profile=profile, role='measured', round_index=round_index, requested_steps=3)
    return None


def _policy_status(history: list[dict]) -> dict:
    decisions = {key: profile_decision(key, history)['decision'] for key in ('2c','1c','0p5c')}
    outcome = 'CONTINUE'
    if any(row.get('campaign_stop') or row.get('status') != 'FINISHED' or
           row.get('wrapper_outcome', row.get('outcome')) in _FAULTS for row in history):
        outcome = 'STOP'
    elif 'STOP' in decisions.values():
        outcome = 'STOP'
    elif 'STOP_INCOMPLETE' in decisions.values():
        outcome = 'STOP_INCOMPLETE'
    elif next_attempt(history) is None and 'UNRESOLVED_VARIABILITY' in decisions.values():
        outcome = 'UNRESOLVED_VARIABILITY'
    return dict(campaign_outcome=outcome, campaign_stop=outcome != 'CONTINUE', profile_decisions=decisions)


def classify_attempt(v1_report: dict, guard_receipt: dict, retained_bytes: int) -> dict:
    """Preserve raw outcomes. A STOP string or quota counter grants no proof."""
    _integer(retained_bytes, 'retained_bytes')
    raw = v1_report.get('raw_v1_result') or {}
    outcome = v1_report.get('outcome')
    result = dict(v1_outcome=raw.get('verdict'), runner_outcome=outcome,
                  guard_outcome=guard_receipt.get('outcome'), wrapper_outcome='UNRESOLVED_FAILURE',
                  campaign_outcome='STOP', campaign_stop=True, eligible=False,
                  invariants_valid=False, resource_proven=False, resource_reason=None,
                  anomalies=[])
    explicit = [error.get('outcome') for error in v1_report.get('runner_errors', [])]
    if 'ENVIRONMENT_INVALID' in explicit:
        outcome = 'ENVIRONMENT_INVALID'
    elif 'REFUSED_VERIFICATION' in explicit:
        outcome = 'REFUSED_VERIFICATION'
    if outcome in ('REFUSED_VERIFICATION', 'ENVIRONMENT_INVALID'):
        result['wrapper_outcome'] = outcome
        result['anomalies'].append(v1_report.get('reason'))
        return result
    if v1_report.get('verification_conflict'):
        result['anomalies'] = v1_report.get('verification_anomalies', [])
        return result
    if not guard_receipt.get('measurement_valid'):
        if 'measurement_valid' in guard_receipt:
            result['wrapper_outcome'] = 'ENVIRONMENT_INVALID'
        return result
    try:
        from . import system_guard as guard
        from .profiles import APPROVED_V1_SOURCE_BINDING
        receipt = guard_receipt
        raw = _frozen_read(Path(receipt['proof_locator']), receipt['proof_sha256'])
        if json.loads(raw) != {key:value for key, value in receipt.items() if key not in ('proof_locator', 'proof_sha256')}:
            raise ValueError('guard proof differs from actual receipt')
        context = v1_report['classification_context']
        if (receipt['test_only'] is not False or not receipt['terminal'] or not receipt['launcher_reaped']
            or receipt['deadline_seconds'] != 180 or receipt['writer_bytes'] != 671088640
            or context['evidence_scope'] != 'LIVE' or v1_report['evidence_scope'] != 'LIVE'
            or context['source_binding'] != APPROVED_V1_SOURCE_BINDING):
            raise ValueError('LIVE guard/source/terminal identity invalid')
        if not context['run_id'] == receipt['run_id'] == v1_report['run_id']:
            raise ValueError('run binding mismatch')
        profile = get_profile(context['profile'])
        if context['profile'] != receipt['profile'] or context['unit'] != receipt['unit'] or context['epoch'] != receipt['before']['epoch']:
            raise ValueError('profile/unit/epoch binding mismatch')
        if Path(context['epoch']['path']).name != receipt['unit'] or Path(context['epoch']['path']).parent.name != 'system.slice' or not guard.UNIT_PATTERN.fullmatch(receipt['unit']):
            raise ValueError('owned cgroup binding mismatch')
        for key in ('manifest_sha256', 'environment_before_sha256', 'environment_after_sha256', 'upper_before_sha256'):
            _hash(context[key])
        if set(context['input_sha256']) != {'execution-environment.json', 'campaign-environment.json', 'reference.json'}:
            raise ValueError('all validated inputs required')
        for digest in context['input_sha256'].values():
            _hash(digest)
        inner = receipt['inner']
        if (inner['topology_before'] != inner['topology_after'] or inner['containment']['remaining_pids']
            or inner.get('cleanup_errors') or inner.get('final_errors') or 'error' in inner
            or 'error' in receipt or any(item.get('errors') for item in receipt.get('cleanup_attempts', []))):
            raise ValueError('guard environment/containment faults')
        for which in ('before', 'after'):
            guard.validate_enforcement(profile, receipt[which], inner['topology_' + which])
        delta = guard.validate_snapshot_pair(receipt['before'], receipt['after'])
        if any(pid != inner['wrapper_identity']['pid'] for pid in receipt['after']['pids']):
            raise ValueError('owned descendants remain')
        result.update(invariants_valid=True, cpu_seconds=delta['cpu_seconds'],
                      outer_wall_seconds=_number(receipt['wall_seconds'], 'guard wall'))
        reason, ceiling, observed = None, None, None
        if receipt.get('outer_timeout_proved') is True and receipt['wall_seconds'] >= 180:
            reason, ceiling, observed = 'OUTER_WALL_TIMEOUT', 180, receipt['wall_seconds']
        elif any(receipt['after']['memory_events'][key] > receipt['before']['memory_events'][key] for key in ('oom','oom_kill')):
            reason, ceiling, observed = 'CGROUP_OOM', CampaignLimits().memory_bytes, receipt['after']['memory_events']
        if retained_bytes > CampaignLimits().retained_run_bytes:
            reason, ceiling, observed = 'EVIDENCE_GROWTH', CampaignLimits().retained_run_bytes, retained_bytes
        if reason:
            result.update(wrapper_outcome='REFUSED_RESOURCE', resource_proven=True, resource_reason=reason,
                          eligible=True, campaign_stop=reason in _GLOBAL_REASONS,
                          campaign_outcome='STOP' if reason in _GLOBAL_REASONS else 'CONTINUE',
                          resource_proof=dict(run_id=receipt['run_id'], unit=receipt['unit'], epoch=context['epoch'],
                              ceiling=ceiling, observed=observed, locator=receipt['proof_locator'], sha256=receipt['proof_sha256']))
        elif outcome == 'ACCEPT' and result['v1_outcome'] == 'ACCEPT' and v1_report.get('admitted') is True and v1_report.get('correctness_authority') == 'EXISTING_HASH_BOUND_LIVE_CHECKER':
            result.update(wrapper_outcome='ACCEPT', eligible=True, campaign_stop=False, campaign_outcome='CONTINUE')
    except (KeyError, ValueError, TypeError, OSError) as exc:
        result.update(wrapper_outcome='ENVIRONMENT_INVALID', campaign_stop=True)
        result['anomalies'].append(f'{type(exc).__name__}: {exc}')
    return result


def _hash(value: str) -> str:
    if not isinstance(value, str) or re.fullmatch('[0-9a-f]{64}', value) is None:
        raise ValueError('exact lowercase SHA256 required')
    return value


def _frozen_read(path: Path, expected: str) -> bytes:
    path = _safe_path(path)
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > 32*1024*1024:
        raise ValueError('bounded single-link regular evidence required')
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != _hash(expected):
        raise ValueError('immutable raw file hash mismatch')
    return raw


_IDENTITY_FILES = ('compute_metabolism/v0/profiles.py', 'compute_metabolism/v0/system_guard.py',
                   'compute_metabolism/v0/run_v1.py', 'compute_metabolism/v0/campaign.py',
                   'docs/superpowers/specs/2026-10-06-compute-metabolism-v0-design.md',
                   'docs/superpowers/plans/2026-10-06-compute-metabolism-v0.md')
_INPUT_FILES = ('execution-environment.json', 'campaign-environment.json', 'reference.json')


def _exclusive_raw(path: Path, raw: bytes) -> None:
    _safe_path(path)
    with path.open('xb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    path.chmod(0o444)
    if os.name == 'posix':
        _fsync_directory(path.parent)


def _configuration(path: Path, expected: str) -> tuple[dict, bytes, dict]:
    from . import system_guard as guard
    raw = _frozen_read(path, expected)
    config = json.loads(raw)
    if config['schema'] != 'COMPUTE_METABOLISM_CAMPAIGN_V0' or re.fullmatch('[a-z0-9][a-z0-9-]{0,63}', config['campaign_id']) is None:
        raise ValueError('frozen campaign schema/identity required')
    root = _safe_path(Path(config['root_directory']))
    repo = _safe_path(Path(config['repo_root']))
    ledger = _safe_path(Path(config['ledger_path']))
    if root != guard.PREPARED_ROOT or repo != root/'workspace' or ledger != repo/'compute_metabolism/v0/artifacts/budget.json':
        raise ValueError('prepared root/workspace/upper namespace required')
    if set(config['inputs']) != set(_INPUT_FILES) or set(config['identities']) != set(_IDENTITY_FILES):
        raise ValueError('all frozen inputs/wrapper/spec/plan identities required')
    files = {}
    for group in ('inputs', 'identities'):
        for name, item in config[group].items():
            source = Path(item['path'])
            target = Path(os.path.abspath(source))
            if group == 'identities' and target != repo/name:
                raise ValueError('wrapper/spec/plan source origin mismatch')
            try:
                target = _safe_path(source)
                files[name] = _frozen_read(target, item['sha256'])
            except (ValueError, OSError) as exc:
                if group != 'identities':
                    raise
                observed = dict(status='ENVIRONMENT_INVALID', prepared_source=name,
                    origin=str(target), expected_sha256=item['sha256'], error=str(exc))
                # The safe path/schema checks above and persistent formal binding
                # below prevent a bad init config from creating a STOP namespace.
                raise HostSourceInvalid('prepared source identity failure: '+name, observed, config) from exc
    if files['compute_metabolism/v0/campaign.py'] != Path(__file__).read_bytes():
        raise ValueError('executing campaign differs from frozen prepared wrapper')
    _bind_host_dependencies(config)
    return config, raw, files


class HostSourceInvalid(ValueError):
    """The actual imported host source does not match frozen authority."""
    def __init__(self, reason, observations, config):
        super().__init__(reason)
        self.observations = observations
        self.config = config


def _bind_host_dependencies(config: dict) -> dict:
    from . import profiles, system_guard
    observations = dict(status='VALID', modules={})
    host_repo = _safe_path(Path(__file__)).parents[2]
    try:
        for name, module in (('profiles',profiles), ('system_guard',system_guard)):
            relative = f'compute_metabolism/v0/{name}.py'
            observed = dict(origin=getattr(module,'__file__',None),
                            spec_origin=getattr(getattr(module,'__spec__',None),'origin',None),
                            expected_origin=str(host_repo/relative), expected_sha256=config['identities'][relative]['sha256'])
            observations['modules'][name] = observed
            source = _safe_path(Path(observed['origin']))
            if source != host_repo/relative or _safe_path(Path(observed['spec_origin'])) != source:
                raise ValueError(f'actual imported {name} source origin mismatch')
            observed['sha256'] = hashlib.sha256(_frozen_read(source, observed['expected_sha256'])).hexdigest()
        if CampaignLimits is not profiles.CampaignLimits or get_profile is not profiles.get_profile:
            raise ValueError('actual imported profile API identity mismatch')
    except (ValueError, OSError, TypeError, KeyError) as exc:
        observations['status'] = 'ENVIRONMENT_INVALID'
        raise HostSourceInvalid(str(exc), observations, config) from exc
    return observations


def _persist_host_source_stop(config: dict, config_hash: str, observations: dict) -> None:
    """A prelaunch source gate failure cannot be silently healed in this campaign."""
    campaign = _safe_path(Path(config['ledger_path']).parent/config['campaign_id'])
    manifest = campaign/'campaign.json'
    if not manifest.exists():
        return  # failed init has never granted a formal namespace
    _frozen_read(manifest,config_hash)
    state = CampaignLedger.read_snapshot(Path(config['ledger_path']))
    if state.get('formal_campaign') != dict(campaign_id=config['campaign_id'],config_sha256=config_hash):
        raise ValueError('source STOP requires matching formal ledger/config identity')
    marker = campaign/'host-source-stop.json'
    if not marker.exists():
        _exclusive_raw(marker,_encode(dict(schema='COMPUTE_METABOLISM_HOST_SOURCE_STOP_V0',
            campaign_id=config['campaign_id'],config_sha256=config_hash,wrapper_outcome='ENVIRONMENT_INVALID',
            campaign_outcome='STOP',campaign_stop=True,host_dependencies=observations)))


def initialize_campaign(config: dict, raw: bytes, files: dict) -> dict:
    """First formal namespace only; prior guard-preflight rows retain all charges."""
    ledger = CampaignLedger.open(Path(config['ledger_path']), CampaignLimits())
    with ledger._authority():
        state = _read(ledger.path)
        if state.get('formal_campaign') is not None or state['running'] is not None or any(row['role'] != 'guard-preflight' for row in state['attempts']):
            raise ValueError('formal campaign already exists or prior numerical/RUNNING evidence; restart not authorized')
        campaign = ledger.root/config['campaign_id']
        if campaign.exists():
            raise ValueError('exclusive formal namespace required')
        # Persist identity before directory work; interruption cannot allow new IDs.
        state['formal_campaign'] = dict(campaign_id=config['campaign_id'], config_sha256=hashlib.sha256(raw).hexdigest())
        ledger._write(state)
        _create_durable_artifact_root(campaign)
        _exclusive_raw(campaign/'campaign.json', raw)
        for name in _INPUT_FILES:
            _exclusive_raw(campaign/name, files[name])
        frozen = campaign/'identity'
        _create_durable_artifact_root(frozen)
        for index, name in enumerate(_IDENTITY_FILES):
            _exclusive_raw(frozen/f'{index:02d}.raw', files[name])
        ledger._write(state)
    return CampaignLedger.read_snapshot(ledger.path)


def _campaign_view(config: dict, raw: bytes) -> tuple[dict, list[dict]]:
    path = Path(config['ledger_path'])
    state = CampaignLedger.read_snapshot(path)
    expected = dict(campaign_id=config['campaign_id'], config_sha256=hashlib.sha256(raw).hexdigest())
    if state.get('formal_campaign') != expected:
        raise ValueError('formal campaign/config binding mismatch')
    campaign = path.parent/config['campaign_id']
    _frozen_read(campaign/'campaign.json', expected['config_sha256'])
    for name in _INPUT_FILES:
        _frozen_read(campaign/name, config['inputs'][name]['sha256'])
    for index, name in enumerate(_IDENTITY_FILES):
        _frozen_read(campaign/'identity'/f'{index:02d}.raw', config['identities'][name]['sha256'])
    rows = [row for row in state['attempts'] if row['campaign_id'] == config['campaign_id']]
    # FINISHED costs remain authoritative even if the subsequent STOP write failed.
    # A saved POST_FINISH receipt is required before another attempt can start.
    for row in rows:
        if row['status'] != 'FINISHED' or not row.get('execution_locator'):
            continue
        finalized = False
        for pointer in state.get('campaign_finalizations',[]):
            if pointer.get('campaign_id') != config['campaign_id'] or pointer.get('run_id') != row['run_id']:
                continue
            try:
                receipt = json.loads(_frozen_read(Path(pointer['locator']),pointer['sha256']))
                finalized = (receipt.get('schema') == 'COMPUTE_METABOLISM_CAMPAIGN_FINALIZATION_V0'
                    and receipt.get('phase') == 'POST_FINISH' and receipt.get('campaign_id') == config['campaign_id']
                    and receipt.get('run_id') == row['run_id'])
            except (OSError, ValueError, KeyError, TypeError):
                finalized = False
            if finalized:
                break
        if not finalized:
            state.setdefault('campaign_finalization_unresolved',dict(run_id=row['run_id'],
                outcome='UNRESOLVED_FAILURE',campaign_outcome='STOP',campaign_stop=True,
                reason='MISSING_DURABLE_POST_FINISH_FINALIZATION',
                execution_locator=row['execution_locator'],execution_sha256=row['execution_sha256']))
            break
    marker = campaign/'host-source-stop.json'
    if marker.exists():
        raw_marker = _frozen_read(marker,hashlib.sha256(marker.read_bytes()).hexdigest())
        stop = json.loads(raw_marker)
        if (stop.get('schema')!='COMPUTE_METABOLISM_HOST_SOURCE_STOP_V0' or stop.get('campaign_id')!=config['campaign_id']
            or stop.get('config_sha256')!=expected['config_sha256'] or stop.get('wrapper_outcome')!='ENVIRONMENT_INVALID'
            or stop.get('campaign_stop') is not True):
            raise ValueError('host source STOP identity invalid')
        state['campaign_environment_stop'] = dict(stop,locator=str(marker),sha256=hashlib.sha256(raw_marker).hexdigest())
    return state, rows


def _upper_resource_status(state: dict, needs_next: bool, proof_path: Path,
                           proof_sha256: str) -> dict:
    """Read-only policy: actual ceilings always apply; unused allowance does not."""
    limits = CampaignLimits()
    wall = state['total_wall_seconds']
    retained = state.get('observed_retained_total_bytes',state['retained_total_bytes'])
    reason = None
    if wall >= limits.total_wall_seconds or (needs_next and limits.total_wall_seconds-wall < limits.per_run_wall_seconds):
        reason, observed, ceiling, allowance = 'CAMPAIGN_WALL_CEILING',wall,limits.total_wall_seconds,limits.per_run_wall_seconds
    elif retained >= limits.retained_total_bytes or (needs_next and limits.retained_total_bytes-retained < limits.retained_run_bytes):
        reason, observed, ceiling, allowance = 'CAMPAIGN_EVIDENCE_CEILING',retained,limits.retained_total_bytes,limits.retained_run_bytes
    if reason:
        return dict(campaign_outcome='CAMPAIGN_RESOURCE_EXHAUSTED',campaign_stop=True,resource_reason=reason,
                    resource_proof=dict(ceiling=ceiling,observed=observed,remaining=ceiling-observed,
                        required_next_allowance=allowance if needs_next else None,locator=str(proof_path),sha256=proof_sha256))
    if state.get('campaign_resource_stop'):
        return dict(state['campaign_resource_stop'])
    return dict(campaign_outcome='CONTINUE',campaign_stop=False,resource_reason=None)


def _finalize_upper(ledger: CampaignLedger, config: dict, run_id: str | None,
                    needs_next: bool, phase: str) -> dict:
    """Append an immutable upper proof/receipt, accounting their own bytes."""
    with ledger._authority():
        state = _read(ledger.path)
        ledger._write(state)
        if state.get('campaign_resource_stop'):
            return dict(state['campaign_resource_stop'])
        campaign = ledger.root/config['campaign_id']
        sequence = len(state.get('campaign_finalizations',[]))+1
        proof_path = campaign/f'upper-finalization-{sequence:04d}.raw.json'
        final_path = campaign/f'campaign-finalization-{sequence:04d}.json'
        proof_raw = ledger.path.read_bytes()
        proof_hash = hashlib.sha256(proof_raw).hexdigest()
        _exclusive_raw(proof_path,proof_raw)
        other_bytes = logical_tree_bytes(ledger.root)-ledger.path.stat().st_size
        observed = logical_tree_bytes(ledger.root)
        seen, padding_cycle = set(), False
        for _ in range(64):
            seen.add(observed)
            candidate = json.loads(_encode(state))
            resource = _upper_resource_status(dict(candidate,observed_retained_total_bytes=observed),
                                               needs_next,proof_path,proof_hash)
            receipt = dict(schema='COMPUTE_METABOLISM_CAMPAIGN_FINALIZATION_V0',
                           campaign_id=config['campaign_id'],run_id=run_id,phase=phase,
                           total_wall_seconds=state['total_wall_seconds'],observed_retained_total_bytes=observed,
                           needs_next_attempt=needs_next,upper_proof_locator=str(proof_path),upper_proof_sha256=proof_hash,
                           **resource)
            policy = _policy_status([row for row in state['attempts'] if row['campaign_id']==config['campaign_id']])
            receipt['policy_status'] = policy
            if not resource['campaign_stop'] and policy['campaign_stop']:
                receipt.update(campaign_stop=True,campaign_outcome=policy['campaign_outcome'])
            payload = _encode(receipt)
            pointer = dict(campaign_id=config['campaign_id'],run_id=run_id,locator=str(final_path),
                           sha256=hashlib.sha256(payload).hexdigest(),campaign_outcome=receipt['campaign_outcome'],
                           metadata_padding='')
            candidate.setdefault('campaign_finalizations',[]).append(pointer)
            if resource['campaign_stop']:
                candidate['campaign_resource_stop'] = dict(receipt,finalization_locator=str(final_path),finalization_sha256=pointer['sha256'])
            candidate['retained_total_bytes'] = observed
            total = other_bytes+len(payload)+len(_encode(candidate))
            if padding_cycle:
                # The highest visited observation maps to a smaller cycle member.
                # This single-copy JSON string adds exactly one actual byte per
                # space without changing the receipt's observed/remaining values.
                if total > observed:
                    raise LedgerIntegrityError('FINALIZATION_SIZING_NONCONVERGENCE; campaign STOP')
                pointer['metadata_padding'] = ' '*(observed-total)
                if other_bytes+len(payload)+len(_encode(candidate)) != observed:
                    raise LedgerIntegrityError('FINALIZATION_SIZING_NONCONVERGENCE; campaign STOP')
                break
            if observed == total:
                break
            if total in seen:
                observed, padding_cycle = max(seen), True
            else:
                observed = total
        else:
            raise LedgerIntegrityError('FINALIZATION_SIZING_NONCONVERGENCE; campaign STOP')
        _exclusive_raw(final_path,payload)
        ledger._write(candidate)
        # No own proof/receipt/pointer bytes disappear from upper accounting.
        actual = logical_tree_bytes(ledger.root)
        if actual != receipt['observed_retained_total_bytes'] or actual != candidate['retained_total_bytes']:
            raise LedgerIntegrityError('finalization retained observation changed; campaign STOP')
        return dict(receipt,finalization_locator=str(final_path),finalization_sha256=pointer['sha256'])


def _saved_classification_context(root: Path) -> dict:
    """Named shared-validator integration. Reads saved evidence; captures nothing."""
    from . import run_v1 as runner
    manifest = runner._json(root/'attempt.json')
    before, pair, delta, reference = runner._environment_evidence(root, manifest)
    upper = runner._saved_upper_before(root, manifest)
    return dict(run_id=manifest['run_id'], profile=manifest['profile'],
        campaign_id=manifest['campaign_id'], round_index=manifest['round_index'], role=manifest['role'],
        unit=Path(pair[0]['snapshot']['epoch']['path']).name, epoch=pair[0]['snapshot']['epoch'],
        evidence_scope=manifest['evidence_scope'], source_binding=before['runtime']['source_binding'],
        input_sha256=manifest['inputs'], upper_before_sha256=manifest['upper_before_sha256'],
        manifest_sha256=hashlib.sha256(runner._read(root/'attempt.json')).hexdigest(),
        environment_before_sha256=hashlib.sha256(runner._read(root/'environment-before.json')).hexdigest(),
        environment_after_sha256=hashlib.sha256(runner._read(root/'environment-after.json')).hexdigest())


_CONTEXT_FILES = ('attempt.json', 'admission.json', 'execution-environment.json',
    'campaign-environment.json', 'reference.json', 'environment-before.json', 'environment-after.json',
    'cgroup-before.json', 'cgroup-after.json', 'guard-before.json', 'upper-ledger-before.json',
    'upper-ledger-before.raw.json', 'upper-authority-before.bin')


class HelperFailure(ValueError):
    """Saved validation failed; exact administrative receipt remains available."""
    def __init__(self, reason: str, administration: dict):
        super().__init__(reason)
        self.administration = administration


def _helper_root(value: str) -> Path:
    from . import system_guard as guard
    from pathlib import PurePosixPath
    path = PurePosixPath(value)
    guard._artifact_path(path)
    if path.name != 'v1' or len(path.relative_to(guard.ARTIFACT_ROOT).parts) != 4:
        raise ValueError('exact campaign/round/run/v1 helper namespace required')
    campaign, round_name, run_id, _ = path.relative_to(guard.ARTIFACT_ROOT).parts
    if (re.fullmatch('[a-z0-9][a-z0-9-]{0,63}', campaign) is None
        or re.fullmatch('[a-z0-9][a-z0-9-]{0,63}', run_id) is None
        or round_name not in ('warmup', *(f'round-{n:02d}' for n in range(1,8)))):
        raise ValueError('bounded campaign/round/run helper identity required')
    return _safe_path(Path(value))


def _classification_helper() -> None:
    """Prepared-rootfs read-only entry; never ledger mutation or live capture."""
    request = json.loads(sys.stdin.read(65537))
    root = _helper_root(request['root'])
    hashes = request['evidence_sha256']
    if set(hashes) != set(_CONTEXT_FILES):
        raise ValueError('complete saved helper evidence hash set required')
    for name, expected in hashes.items():
        _frozen_read(root/name, expected)
    context = _saved_classification_context(root)
    for name, expected in hashes.items():
        _frozen_read(root/name, expected)
    print(_encode(dict(context=context, evidence_sha256=hashes)).decode(), end='')


def _post_context(root: Path, config: dict, receipt: dict) -> tuple[dict, dict]:
    from . import system_guard as guard
    prepared = _safe_path(Path(config['root_directory']))
    if prepared != guard.PREPARED_ROOT:
        raise ValueError('fixed prepared root required for saved helper')
    inner = '/' + _safe_path(root).relative_to(prepared).as_posix()
    _helper_root(inner)  # lexical namespace check; existence is inside chroot
    hashes = {}
    for name in _CONTEXT_FILES:
        path = root/name
        hashes[name] = hashlib.sha256(_safe_path(path).read_bytes()).hexdigest()
        _frozen_read(path, hashes[name])
    request = _encode(dict(root=inner, evidence_sha256=hashes))
    argv = ['sudo','-n','chroot',str(prepared),'/usr/bin/env','--chdir=/workspace','PYTHONDONTWRITEBYTECODE=1',
            guard.INNER_PYTHON,'-B','-c',
            'from compute_metabolism.v0.campaign import _classification_helper; _classification_helper()']
    started = time.monotonic()
    administration = dict(measurement_role='ADMINISTRATION_ONLY', argv=argv, evidence_sha256=hashes)
    try:
        process = subprocess.run(argv, input=request, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 timeout=30, cwd=prepared/'workspace', check=False)
        administration.update(returncode=process.returncode, stdout_hex=process.stdout.hex(), stderr_hex=process.stderr.hex(),
            stdout_sha256=hashlib.sha256(process.stdout).hexdigest(), stderr_sha256=hashlib.sha256(process.stderr).hexdigest())
        for name, expected in hashes.items():
            _frozen_read(root/name, expected)
        if process.returncode != 0 or len(process.stdout) > 65536:
            raise ValueError('saved prepared helper failed')
        response = json.loads(process.stdout)
        context = response['context']
        from .profiles import APPROVED_V1_SOURCE_BINDING
        if (response['evidence_sha256'] != hashes
            or (context['run_id'],context['unit'],context['epoch']) != (receipt['run_id'],receipt['unit'],receipt['before']['epoch'])
            or context['profile'] != receipt['profile'] or context['source_binding'] != APPROVED_V1_SOURCE_BINDING
            or context['manifest_sha256'] != hashes['attempt.json']
            or context['environment_before_sha256'] != hashes['environment-before.json']
            or context['environment_after_sha256'] != hashes['environment-after.json']
            or context['upper_before_sha256'] != hashes['upper-ledger-before.json']
            or context['input_sha256'] != {name:hashes[name] for name in _INPUT_FILES}):
            raise ValueError('saved helper evidence/run/unit/epoch/source/environment binding mismatch')
    except Exception as exc:
        administration.update(wall_seconds=time.monotonic()-started, error=f'{type(exc).__name__}: {exc}')
        if isinstance(exc, subprocess.TimeoutExpired):
            administration.update(stdout_hex=(exc.stdout or b'').hex(), stderr_hex=(exc.stderr or b'').hex())
        raise HelperFailure(str(exc), administration) from exc
    administration['wall_seconds'] = time.monotonic()-started
    return context, administration


def run_next(config: dict, raw: bytes, run_id: str) -> dict:
    """Same owner/process: durable begin, exactly one actual guard, durable finish."""
    from . import system_guard as guard
    if re.fullmatch('[a-z0-9][a-z0-9-]{0,63}', run_id) is None:
        raise ValueError('bounded lower-case run identity required')
    state, history = _campaign_view(config, raw)
    try:
        host_dependencies_before = _bind_host_dependencies(config)
    except HostSourceInvalid as exc:
        _persist_host_source_stop(config,hashlib.sha256(raw).hexdigest(),exc.observations)
        raise
    if state.get('campaign_environment_stop'):
        return dict(state['campaign_environment_stop'])
    if state.get('campaign_finalization_unresolved'):
        return dict(state['campaign_finalization_unresolved'])
    item = next_attempt(history)
    if state['running'] is not None:
        raise UnresolvedPriorAttempt('prior RUNNING authority; no finalization/recovery')
    resource = _upper_resource_status(state,item is not None,Path(config['ledger_path']),
                                     hashlib.sha256(Path(config['ledger_path']).read_bytes()).hexdigest())
    if resource['campaign_stop']:
        ledger = CampaignLedger.open(Path(config['ledger_path']),CampaignLimits())
        final = _finalize_upper(ledger,config,run_id,item is not None,'PRELAUNCH')
        return dict(final,campaign_finalization=final)
    if state['start_refusals'] or item is None:
        policy = _policy_status(history)
        if policy['campaign_stop']:
            return policy
        raise ValueError('campaign STOP/complete/RUNNING; no next attempt authority')
    ledger = CampaignLedger.open(Path(config['ledger_path']), CampaignLimits())
    campaign = ledger.root/config['campaign_id']
    round_root = campaign/('warmup' if item['role'] == 'warm-up' else f"round-{item['round_index']:02d}")
    _create_durable_artifact_root(round_root)
    attempt = round_root/run_id
    root = Path(config['root_directory'])
    def inner(path):
        return '/' + path.relative_to(root).as_posix()
    attempt_config = dict(repo_root='/workspace', attempt_root=inner(attempt), ledger_path=inner(ledger.path),
                          campaign_id=config['campaign_id'], run_id=run_id, **item)
    for prefix, name in (('execution_environment','execution-environment.json'),
                         ('campaign_environment','campaign-environment.json'), ('reference','reference.json')):
        attempt_config[prefix+'_path'] = inner(campaign/name)
        attempt_config[prefix+'_sha256'] = config['inputs'][name]['sha256']
    attempt_raw = _encode(attempt_config)
    attempt_config_path = round_root/f'config-{run_id}.json'
    _exclusive_raw(attempt_config_path, attempt_raw)
    command = [guard.INNER_PYTHON, '-m', 'compute_metabolism.v0.run_v1', '--config',
               inner(attempt_config_path), '--config-sha256', hashlib.sha256(attempt_raw).hexdigest()]
    try:
        ledger.begin_attempt(config['campaign_id'], run_id, item['profile'], item['role'], item['round_index'])
    except CampaignResourceExhausted:
        # Begin includes fresh config/RUNNING metadata in its full-allowance
        # check. Preserve its durable refusal and issue no guard authority.
        final = _finalize_upper(ledger,config,run_id,True,'PRELAUNCH')
        return dict(final,campaign_finalization=final)
    try:
        topology = json.loads((campaign/'campaign-environment.json').read_bytes())['topology']
        receipt = guard.run_system_guard(get_profile(item['profile']), run_id=run_id, artifact_dir=attempt,
            command=command, topology=topology, root_directory=root, limits=CampaignLimits())
    except Exception as exc:
        partial = dict(outcome='UNRESOLVED_FAILURE', campaign_stop=True, guard_exception=f'{type(exc).__name__}: {exc}')
        ledger.record_unresolved(run_id, partial)
        return partial
    if receipt.get('terminal') is not True or receipt.get('launcher_reaped') is not True:
        partial = dict(outcome='UNRESOLVED_FAILURE', campaign_stop=True, guard_receipt=receipt)
        ledger.record_unresolved(run_id, partial)
        return partial
    report = dict(outcome='UNRESOLVED_FAILURE', raw_v1_result=None)
    administration = dict(measurement_role='ADMINISTRATION_ONLY', status='NOT_STARTED')
    try:
        admission_path = _safe_path(attempt/'v1/admission.json')
        admission_hash = hashlib.sha256(admission_path.read_bytes()).hexdigest()
        report = json.loads(_frozen_read(admission_path, admission_hash))
        # Original admission remains untouched; enrichment is a detached copy.
        context, administration = _post_context(attempt/'v1', config, receipt)
        report = dict(report, classification_context=context)
        context = report['classification_context']
        if (context['run_id'], context['campaign_id'], context['role'], context['round_index'], context['profile']) != (run_id, config['campaign_id'], item['role'], item['round_index'], item['profile']):
            raise ValueError('saved runner/campaign identity mismatch')
    except Exception as exc:
        if isinstance(exc, HelperFailure):
            administration = exc.administration
        report = dict(report, outcome='ENVIRONMENT_INVALID', context_error=f'{type(exc).__name__}: {exc}')
    identities_after = {}
    for name, identity in config['identities'].items():
        try:
            identities_after[name] = hashlib.sha256(_frozen_read(Path(identity['path']), identity['sha256'])).hexdigest()
        except Exception as exc:
            report = dict(report, outcome='ENVIRONMENT_INVALID', identity_error=f'{type(exc).__name__}: {exc}')
    try:
        host_dependencies_after = _bind_host_dependencies(config)
    except HostSourceInvalid as exc:
        host_dependencies_after = exc.observations
        report = dict(report,outcome='ENVIRONMENT_INVALID',host_identity_error=str(exc))
    try:
        receipt = dict(receipt, proof_locator=str(attempt/'guard-outer.json'),
                       proof_sha256=hashlib.sha256((attempt/'guard-outer.json').read_bytes()).hexdigest())
        quota_raw = (attempt/'writer_quota.txt').read_bytes()
        if re.fullmatch(b'[0-9]+', quota_raw) is None:
            raise ValueError('actual writer counter unavailable')
        reserved = int(quota_raw)
        retained = logical_tree_bytes(attempt)
        seen_sizes, padding_cycle = set(), False
        for _ in range(64):
            seen_sizes.add(retained)
            classified = classify_attempt(report, receipt, retained)
            if item['role'] == 'warm-up' and classified['wrapper_outcome'] != 'ACCEPT':
                classified.update(campaign_stop=True, campaign_outcome='STOP')
            execution = dict(schema='COMPUTE_METABOLISM_EXECUTION_V0', run_id=run_id,
                classification=classified, admission_report=report, guard_receipt=receipt,
                config_sha256=hashlib.sha256(attempt_raw).hexdigest(),
                identities_before=config['identities'], identities_after=identities_after,
                host_dependencies_before=host_dependencies_before,host_dependencies_after=host_dependencies_after,
                administration=administration,
                writer_reserved_bytes=reserved, retained_bytes=retained)
            if padding_cycle:
                execution['metadata_padding'] = ''
            payload = _encode(execution)
            current = logical_tree_bytes(attempt) + len(payload)
            if padding_cycle:
                if current > retained:
                    raise LedgerIntegrityError('EXECUTION_SIZING_NONCONVERGENCE; campaign STOP')
                execution['metadata_padding'] = ' '*(retained-current)
                payload = _encode(execution)
                if logical_tree_bytes(attempt)+len(payload) != retained:
                    raise LedgerIntegrityError('EXECUTION_SIZING_NONCONVERGENCE; campaign STOP')
                break
            if current == retained:
                break
            if current in seen_sizes:
                # Count a real JSON padding field, staying above all cycle values.
                retained, padding_cycle = max(seen_sizes)+64, True
            else:
                retained = current
        else:
            raise LedgerIntegrityError('EXECUTION_SIZING_NONCONVERGENCE; campaign STOP')
        _exclusive_raw(attempt/'execution.json', payload)
        if logical_tree_bytes(attempt) != retained:
            raise LedgerIntegrityError('execution retained observation changed; campaign STOP')
        # Classification is durable before FINISHED; an interrupted write never
        # permits missing classification to become scheduling authority.
        with ledger._authority():
            live = _read(ledger.path)
            record = ledger._running_record(live, run_id)
            record.update(classified)
            record['execution_locator'] = str(attempt/'execution.json')
            record['execution_sha256'] = hashlib.sha256(payload).hexdigest()
            ledger._write(live)
        cpu = classified.get('cpu_seconds')
        wall = receipt['wall_seconds']
        ledger.finish_attempt(run_id, wall, cpu, reserved, retained, classified['wrapper_outcome'])
        finished = CampaignLedger.read_snapshot(ledger.path)
        rows = [row for row in finished['attempts'] if row['campaign_id']==config['campaign_id']]
        final = _finalize_upper(ledger,config,run_id,next_attempt(rows) is not None,'POST_FINISH')
        return dict(execution,campaign_finalization=final,
                    campaign_outcome=final['campaign_outcome'] if final['campaign_stop'] else classified['campaign_outcome'],
                    campaign_stop=classified['campaign_stop'] or final['campaign_stop'])
    except Exception as exc:
        partial = dict(outcome='UNRESOLVED_FAILURE', campaign_stop=True, guard_receipt=receipt,
                       partial_error=f'{type(exc).__name__}: {exc}')
        if ledger._owned_run is not None:
            ledger.record_unresolved(run_id, partial)
        else:
            # Completed physical containment must never be put back into RUNNING.
            with ledger._authority():
                failed = _read(ledger.path)
                failed['campaign_finalization_unresolved'] = dict(run_id=run_id,**partial)
                ledger._write(failed)
        return partial


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='One-attempt Compute Metabolism V0 campaign')
    sub = parser.add_subparsers(dest='operation', required=True)
    for operation in ('init', 'status', 'run-next'):
        command = sub.add_parser(operation)
        command.add_argument('--config', type=Path, required=True)
        command.add_argument('--config-sha256', required=True)
        if operation == 'run-next':
            command.add_argument('--run-id', required=True)
    args = parser.parse_args(argv)
    try:
        config, raw, files = _configuration(args.config, args.config_sha256)
        if args.operation == 'init':
            result = initialize_campaign(config, raw, files)
        elif args.operation == 'status':
            state, rows = _campaign_view(config, raw)
            item = next_attempt(rows)
            resource = _upper_resource_status(state,item is not None,Path(config['ledger_path']),
                hashlib.sha256(Path(config['ledger_path']).read_bytes()).hexdigest())
            result = dict(upper=state, next_attempt=None if resource['campaign_stop'] else item,
                          **resource,
                          profiles={key:profile_decision(key, rows) for key in ('2c','1c','0p5c')})
            policy = _policy_status(rows)
            result['policy_status'] = policy
            if not result['campaign_stop'] and policy['campaign_stop']:
                result.update(campaign_stop=True,campaign_outcome=policy['campaign_outcome'],next_attempt=None)
            if not result['campaign_stop'] and (state['running'] is not None or state.get('campaign_finalization_unresolved') or any(row.get('campaign_stop') for row in rows)):
                result.update(campaign_stop=True,campaign_outcome='STOP',next_attempt=None)
            if state.get('campaign_environment_stop'):
                result.update(wrapper_outcome='ENVIRONMENT_INVALID',campaign_stop=True,campaign_outcome='STOP',next_attempt=None)
        else:
            result = run_next(config, raw, args.run_id)
        print(_encode(result).decode(), end='')
        classification = result.get('classification', result)
        return 2 if result.get('campaign_stop',classification.get('campaign_stop')) else 0
    except (ValueError, RuntimeError, KeyError, OSError, TypeError) as exc:
        result = dict(campaign_outcome='STOP',campaign_stop=True,error=f'{type(exc).__name__}: {exc}')
        if isinstance(exc,HostSourceInvalid):
            result.update(wrapper_outcome='ENVIRONMENT_INVALID',host_dependencies=exc.observations)
            if args.operation=='run-next':
                try:
                    _persist_host_source_stop(exc.config,args.config_sha256,exc.observations)
                except (ValueError,OSError) as write_exc:
                    result['source_stop_write_error'] = f'{type(write_exc).__name__}: {write_exc}'
        print(_encode(result).decode(), end='')
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
