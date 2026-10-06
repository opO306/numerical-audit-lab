"""Observable boundaries: limits, exclusive evidence, descendants and timeout."""
import importlib
import sys

import pytest


def api():
    try:
        return importlib.import_module('runtime_trace.regular_nstep.resources')
    except ModuleNotFoundError:
        pytest.fail('new guarded execution API is absent')


def test_boolean_budget_is_refused():
    with pytest.raises(ValueError):
        api().Limits(total_seconds=True)


def test_invalid_and_increased_limits_refused():
    for kw in ({'total_seconds': 0}, {'job_seconds': 601},
               {'memory_bytes': 4294967297}, {'storage_bytes': 8589934593}):
        with pytest.raises(ValueError):
            api().Limits(**kw)


def test_storage_reserves_before_write_and_preserves_failure(tmp_path):
    a = api()
    budget = a.EvidenceBudget(tmp_path, 12)
    budget.write('first', b'12345678')
    with pytest.raises(a.ResourceRefused):
        budget.write('second', b'12345')
    assert (tmp_path / 'first').read_bytes() == b'12345678'
    assert not (tmp_path / 'second').exists()


def test_exclusive_and_traversal_writes_refused(tmp_path):
    a = api()
    budget = a.EvidenceBudget(tmp_path, 1024)
    budget.write('first', b'old')
    with pytest.raises(FileExistsError):
        budget.write('first', b'new')
    with pytest.raises(ValueError):
        budget.write('../outside', b'x')
    assert (tmp_path / 'first').read_bytes() == b'old'


def test_guarded_subprocess_checks_memory_controller_and_records_identity(tmp_path):
    a = api()
    receipt = a.run_guarded([sys.executable, '-c', 'print(17)'],
        a.Limits(job_seconds=10), tmp_path / 'run', tmp_path / 'ledger.json')
    assert receipt['return_code'] == 0
    assert receipt['enforced_memory_bytes'] == 4294967296
    assert receipt['enforced_swap_bytes'] == 0
    assert receipt['host']
    assert receipt['peak_tree_memory_bytes'] > 0
    assert (tmp_path / 'run' / 'stdout.log').read_text().strip() == '17'


def test_timeout_kills_entire_guarded_job_and_cannot_report_success(tmp_path):
    a = api()
    receipt = a.run_guarded([sys.executable, '-c', 'import time; time.sleep(20)'],
        a.Limits(job_seconds=1), tmp_path / 'run', tmp_path / 'ledger.json')
    assert receipt['return_code'] != 0
    assert receipt['verdict'] == 'REFUSED_RESOURCE'
    assert receipt['requested_complete'] is False


def test_cumulative_budget_refuses_before_child_exec(tmp_path):
    a = api()
    ledger = tmp_path / 'ledger.json'
    ledger.write_text('{"used_seconds":3600.0,"jobs":[]}')
    with pytest.raises(a.ResourceRefused):
        a.run_guarded([sys.executable, '-c', 'print(99)'],
                      a.Limits(), tmp_path / 'run', ledger)
    assert not (tmp_path / 'run').exists()


def test_descendant_memory_is_limited_and_no_success_is_returned(tmp_path):
    a = api()
    code = 'import subprocess,sys; subprocess.run([sys.executable,"-c","x=bytearray(268435456)"])'
    receipt = a.run_guarded([sys.executable, '-c', code],
        a.Limits(job_seconds=10, memory_bytes=67108864), tmp_path / 'run', tmp_path / 'ledger.json')
    assert receipt['verdict'] == 'REFUSED_RESOURCE'
    assert receipt['requested_complete'] is False


def test_shared_writer_quota_cannot_spend_same_allocation_twice(tmp_path):
    a = api()
    assert hasattr(a, 'WriterQuota'), 'guard allocation does not reach evidence writers'
    q1 = a.WriterQuota(tmp_path / 'quota.json', 12)
    q2 = a.WriterQuota(tmp_path / 'quota.json', 12)
    q1.reserve(8)
    with pytest.raises(a.ResourceRefused):
        q2.reserve(5)
    q2.reserve(4)
    with pytest.raises(a.ResourceRefused):
        q1.reserve(1)


def test_controller_read_error_cannot_erase_already_spent_budget(tmp_path, monkeypatch):
    a = api()
    def broken(unit):
        raise OSError('injected controller read error')
    monkeypatch.setattr(a, '_show', broken)
    ledger = tmp_path / 'ledger.json'
    receipt = a.run_guarded([sys.executable, '-c', 'print(19)'],
        a.Limits(job_seconds=10), tmp_path / 'run', ledger)
    assert receipt['verdict'] == 'REFUSED_RESOURCE'
    assert a._strict_load(ledger)['used_seconds'] > 0


def test_unreconciled_job_blocks_next_execution(tmp_path):
    a = api()
    ledger = tmp_path / 'ledger.json'
    ledger.write_text('{"used_seconds":0,"jobs":[]}')
    ledger.with_suffix('.running.json').write_text('{"state":"RUNNING"}')
    with pytest.raises(a.ResourceRefused):
        a.run_guarded([sys.executable, '-c', 'print(99)'], a.Limits(), tmp_path / 'next', ledger)
    assert not (tmp_path / 'next').exists()
