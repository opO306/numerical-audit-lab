"""Collector source transformation and one parameterized original execution."""
import importlib
from pathlib import Path
import pytest


def api():
    try:
        return importlib.import_module('runtime_trace.regular_nstep.acquire')
    except ModuleNotFoundError:
        pytest.fail('generic actual acquisition API is absent')


ROOT = Path(__file__).resolve().parents[1]


def test_harness_changes_only_parameter_and_metadata_not_calculation():
    text, proof = api().harness_source(ROOT)
    assert proof['calculation_replacement'] == 'n_steps=1 -> n_steps=int(os.environ["RTN_STEPS"])'
    assert proof['external_gala_modified'] is False
    assert 'H.integrate_orbit(w0, dt=1/64,' in text
    with pytest.raises(ValueError):
        api().validate_n(True)
    with pytest.raises(ValueError):
        api().validate_n(101)


def test_collector_guard_adaptation_does_not_change_old_source():
    old = (ROOT / 'runtime_trace/gdb_capture.py').read_text()
    transformed, proof = api().collector_source(old, 'body')
    assert 'self.count >= 5000' not in transformed
    assert 'self.count >= 125000' in transformed
    assert proof['replacement_count'] == 1
    assert (ROOT / 'runtime_trace/gdb_capture.py').read_text() == old
    with pytest.raises(ValueError):
        api().collector_source(old.replace('self.count >= 5000', 'self.count >= 5001'), 'body')


def test_source_pinset_includes_reused_and_new_capture_inputs():
    pins = api().source_pinset(ROOT)
    assert 'runtime_trace/regular_nstep/gdb_acquire.py' in pins
    assert 'runtime_trace/gdb_capture.py' in pins
    assert 'runtime_trace/caller_transition/gdb_acquire_reads.py' in pins
    assert 'runtime_trace/harness.py' in pins


def test_missing_pending_receipt_is_explicit_refusal(tmp_path):
    assert api().read_pending(tmp_path, 10)['verdict'] == 'REFUSED'
