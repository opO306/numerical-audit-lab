"""Simulated guard outcomes isolate public source/completion gates, no native runs."""
import importlib
import json
from pathlib import Path
import pytest


def test_source_changed_during_job_blocks_public_success(tmp_path, monkeypatch):
    module = importlib.import_module('runtime_trace.regular_nstep.run')
    root = Path(__file__).resolve().parents[1]
    changed = False
    original_sha = module.sha
    def source_sha(path):
        if changed and str(path).endswith('machine_check.py'):
            return '1' * 64
        return original_sha(path)
    monkeypatch.setattr(module, 'sha', source_sha)
    calls = 0
    def fake_guard(command, limits, out, ledger, **kwargs):
        nonlocal calls, changed
        calls += 1
        out.mkdir(parents=True)
        (out / 'execution.json').write_text('{}')
        if calls == 2:
            derived = out.parent / 'derived'
            derived.mkdir()
            (derived / 'checker_report.json').write_text(json.dumps({'verdict': 'CHECKER_PASS',
                'requested_steps': 10, 'checked_steps': 10, 'requested_complete': True}))
        changed = calls == 3
        if calls == 3:
            (out.parent / 'fresh_checker_report.json').write_text(json.dumps({'verdict': 'CHECKER_PASS',
                'requested_steps': 10, 'checked_steps': 10, 'requested_complete': True}))
        return {'verdict': 'EXECUTED'}
    monkeypatch.setattr(module, 'run_guarded', fake_guard)
    report = module.run(10, tmp_path / 'run', tmp_path / 'budget.json', root)
    assert report['verdict'] == 'REFUSED'
    assert report['requested_complete'] is False
    assert not (tmp_path / 'run/run_result.json').exists()


@pytest.mark.parametrize('field,value', [('checked_steps', 1), ('checked_steps', True),
    ('requested_steps', True), ('requested_complete', False)])
def test_fresh_partial_report_never_publishes_success(tmp_path, monkeypatch, field, value):
    module = importlib.import_module('runtime_trace.regular_nstep.run')
    good = {'verdict': 'CHECKER_PASS', 'requested_steps': 10, 'checked_steps': 10, 'requested_complete': True}
    def guard(command, limits, out, ledger, **kwargs):
        out.mkdir(parents=True)
        (out / 'execution.json').write_text('{}')
        if out.name == 'derivation':
            (out.parent / 'derived').mkdir()
            (out.parent / 'derived/checker_report.json').write_text(json.dumps(good))
        if out.name == 'independent_check':
            (out.parent / 'fresh_checker_report.json').write_text(json.dumps({**good, field: value}))
        return {'verdict': 'EXECUTED'}
    monkeypatch.setattr(module, 'run_guarded', guard)
    report = module.run(10, tmp_path / 'run', tmp_path / 'budget.json', Path(__file__).resolve().parents[1])
    assert report['verdict'] == 'REFUSED'
    assert not (tmp_path / 'run/run_result.json').exists()


def test_fresh_refusal_frontier_overrides_staged_pass(tmp_path, monkeypatch):
    module = importlib.import_module('runtime_trace.regular_nstep.run')
    def guard(command, limits, out, ledger, **kwargs):
        out.mkdir(parents=True)
        (out / 'execution.json').write_text('{}')
        if out.name == 'derivation':
            (out.parent / 'derived').mkdir()
            (out.parent / 'derived/checker_report.json').write_text(json.dumps({'verdict':'CHECKER_PASS','checked_steps':10}))
        if out.name == 'independent_check':
            (out.parent / 'fresh_checker_report.json').write_text(json.dumps({'verdict':'REFUSED',
                'requested_steps':10, 'checked_steps':1, 'captured_steps':10,
                'requested_complete':False, 'last_verified_native_trace_seq':9000,
                'last_verified_v2_trace_seq':1900, 'failure_stage':'SEMANTIC'}))
        return {'verdict': 'FAILED' if out.name == 'independent_check' else 'EXECUTED'}
    monkeypatch.setattr(module, 'run_guarded', guard)
    report = module.run(10, tmp_path / 'run', tmp_path / 'budget.json', Path(__file__).resolve().parents[1])
    assert report['verdict'] == 'REFUSED' and report['checked_steps'] == 1
    assert report['last_verified_native_trace_seq'] == 9000
    assert report['failure_stage'] == 'SEMANTIC'


def test_malformed_fresh_report_preserves_refusal(tmp_path, monkeypatch):
    module = importlib.import_module('runtime_trace.regular_nstep.run')
    def guard(command, limits, out, ledger, **kwargs):
        out.mkdir(parents=True)
        (out / 'execution.json').write_text('{}')
        if out.name == 'independent_check':
            (out.parent / 'fresh_checker_report.json').write_text('{bad')
        return {'verdict': 'EXECUTED'}
    monkeypatch.setattr(module, 'run_guarded', guard)
    report = module.run(10, tmp_path / 'run', tmp_path / 'budget.json', Path(__file__).resolve().parents[1])
    assert report['verdict'] == 'REFUSED' and report['checked_steps'] == 0
    assert (tmp_path / 'run/run_refusal.json').exists()
    assert report['failure_stage'] == 'CHECKER_REPORT_UNAVAILABLE'
