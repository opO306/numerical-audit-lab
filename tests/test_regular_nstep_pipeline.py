from pathlib import Path
import importlib
import os
import pytest

ROOT = Path(__file__).resolve().parents[1]
CAPTURE = ROOT / os.environ.get('RTN_TEST_CAPTURE', 'runtime_trace/regular_nstep/artifacts/connected10-final2/capture')


def test_connected_10step_actual_ir_v2_and_completion(tmp_path):
    try:
        producer = importlib.import_module('runtime_trace.regular_nstep.producer')
        checker = importlib.import_module('runtime_trace.regular_nstep.checker')
    except ModuleNotFoundError:
        pytest.fail('connected N-step producer/checker absent')
    out = tmp_path / 'derived'
    report = producer.build(CAPTURE, out, ROOT)
    assert report['verdict'] == 'CHECKER_PASS'
    assert report['requested_complete'] is True
    assert report['checked_steps'] == 10
    assert report['operation_count'] == 14 + 10 * 22
    assert report['carry_join_count'] == 9
    assert report['formal_certification'] is False
    assert checker.check(CAPTURE, out, ROOT) == report


def test_missing_capture_never_publishes_completion(tmp_path):
    try:
        producer = importlib.import_module('runtime_trace.regular_nstep.producer')
    except ModuleNotFoundError:
        pytest.fail('connected producer absent')
    out = tmp_path / 'rejected'
    with pytest.raises((ValueError, OSError)):
        producer.build(tmp_path / 'missing', out, ROOT)
    assert not (out / 'completion.json').exists()
    assert (out / 'failure.json').exists()


def test_derivation_failure_preserves_native_frontier(tmp_path, monkeypatch):
    import json
    producer = importlib.import_module('runtime_trace.regular_nstep.producer')
    cap = {'requested_steps': 10, 'regions': [{}] * 11}
    monkeypatch.setattr(producer.raw_check, 'validate', lambda *args: (cap, [], {'last_verified_trace_seq': 9921}))
    def refuse(*args):
        raise ValueError('injected unsupported derivation')
    monkeypatch.setattr(producer, 'block', refuse)
    out = tmp_path / 'derived'
    with pytest.raises(ValueError):
        producer.build(tmp_path / 'cap', out, ROOT)
    report = json.loads((out / 'failure.json').read_text())
    assert report['captured_steps'] == 10 and report['checked_steps'] == 0
    assert report['last_verified_native_trace_seq'] == 9921
    assert report['last_verified_v2_trace_seq'] is None
    assert report['failure_stage'] == 'DERIVATION'
    assert not (out / 'completion.json').exists()
