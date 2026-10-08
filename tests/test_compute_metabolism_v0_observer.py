"""Bounded native observation is evidence, never a V1 execution permit."""
from pathlib import Path
import hashlib
import importlib
import json
import shutil
import sys

import pytest


def observer():
    # Missing implementation earns an assertion failure in the recorded RED.
    try:
        return importlib.import_module('compute_metabolism.v0.observer')
    except ModuleNotFoundError:
        pytest.fail('bounded isolated observer has not been implemented')


def live_fingerprint():
    from compute_metabolism.v0.adaptive import elf_build_id
    libc = Path('/lib/x86_64-linux-gnu/libc.so.6').resolve()
    python = Path(sys.executable).resolve()
    def item(path):
        raw = path.read_bytes()
        return dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest(), build_id=elf_build_id(raw))
    return dict(schema='COMPUTE_METABOLISM_FINGERPRINT_V1', cpu_arch='x86_64',
        cpu_features=[], libc=item(libc), runtime=item(python),
        gala=dict(path='UNEXECUTED_TEST_FIXTURE', sha256='0'*64, build_id='00'),
        v1_source_binding='0'*64, evidence_scope='TEST_ONLY_NATIVE_OBSERVER')


@pytest.mark.parametrize('kwargs', [dict(length=4097), dict(length=-1),
    dict(length=True), dict(value=256), dict(max_steps=0), dict(max_steps=4097),
    dict(timeout_seconds=61), dict(max_output_bytes=16777217)])
def test_invalid_bounds_fail_before_process_or_artifact(tmp_path, kwargs):
    with pytest.raises(ValueError):
        observer().observe_memset({}, tmp_path/'observation.raw.json', **kwargs)
    assert list(tmp_path.iterdir()) == []


def test_fingerprint_drift_is_refused_before_process_or_artifact(tmp_path):
    fp = live_fingerprint()
    fp['libc']['sha256'] = '0'*64
    with pytest.raises(ValueError, match='libc'):
        observer().observe_memset(fp, tmp_path/'observation.raw.json')
    assert list(tmp_path.iterdir()) == []


def test_output_is_exclusive_and_aliases_are_refused(tmp_path):
    out = tmp_path/'observation.raw.json'
    out.write_bytes(b'historical evidence\n')
    with pytest.raises(FileExistsError):
        observer().observe_memset(live_fingerprint(), out)
    assert out.read_bytes() == b'historical evidence\n'
    alias = tmp_path/'alias'
    alias.symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(ValueError, match='alias'):
        observer().observe_memset(live_fingerprint(), alias/'observation.raw.json')


def test_real_libc_ifunc_observation_has_native_trace_and_preserves_unknowns(tmp_path):
    assert shutil.which('gdb'), 'prepared GDB is required; no silent test skip'
    fp = live_fingerprint()
    out = tmp_path/'observation.raw.json'
    raw = observer().observe_memset(fp, out, length=64, value=0)
    assert json.loads(out.read_bytes()) == raw
    assert raw['mode'] == 'OBSERVATION'
    assert raw['certified_state_progress'] is False
    assert raw['promotion_allowed'] is False
    assert raw['terminal']['status'] == 'OBSERVED_RETURN'
    assert raw['terminal']['inferior_exit_code'] == 0
    assert raw['call_origin']['kind'] == 'SYNTHETIC_PYTHON_CTYPES'
    assert raw['call_origin']['authorized_gala_call'] is False
    assert len(raw['call_origin']['native_caller']['sha256']) == 64
    assert raw['library']['sha256'] == fp['libc']['sha256']
    assert raw['library']['build_id'] == fp['libc']['build_id']
    assert raw['entry'] == raw['trace'][0]['pc']
    assert raw['trace'][0]['before']['registers']['rdi'] == raw['input']['destination']
    assert raw['trace'][0]['before']['registers']['rsi'] == 0
    assert raw['trace'][0]['before']['registers']['rdx'] == 64
    assert raw['observed_result']['destination_hex'] == '00'*64
    assert raw['observed_result']['return_value'] == raw['input']['destination']
    assert raw['observed_result']['sentinels_unchanged'] is True
    assert raw['effect_coverage']['complete'] is False
    assert raw['effect_coverage']['outside_window'] == 'UNKNOWN'
    assert raw['trace'] and any(row['writes'] for row in raw['trace'])
    for row in raw['trace']:
        assert row['instruction_bytes'] and row['assembly']
        assert 'registers' in row['before'] and 'registers' in row['after']
        assert row['memory_effects_complete'] is False
        assert row['unknown_effects']
        assert row['bytes'] == row['instruction_bytes']
    assert raw['trace'][0]['before']['vectors']
    # A zero broadcast may preserve an already-zero vector. Require the exact
    # actual PRE/POST difference report, including a truthful empty report.
    for row in raw['trace']:
        expected=[name for name,value in row['before']['vectors'].items()
            if row['after']['vectors'].get(name)!=value]
        assert row['changed_vectors']==expected
    assert any(row['reads'] for row in raw['trace'])
    assert 'ACCEPT' not in out.read_text()


def test_step_cap_keeps_partial_trace_without_claiming_return(tmp_path):
    raw = observer().observe_memset(live_fingerprint(), tmp_path/'observation.raw.json',
        length=64, max_steps=1)
    assert len(raw['trace']) == 1
    assert raw['terminal']['status'] == 'STOP_STEP_LIMIT'
    assert raw['terminal']['complete'] is False
    assert raw['certified_state_progress'] is False


@pytest.mark.parametrize('length,value', [(0,0), (1,255), (31,7), (65,165)])
def test_real_native_sample_preserves_byte_value_and_destination_boundaries(tmp_path,length,value):
    raw = observer().observe_memset(live_fingerprint(),tmp_path/'observation.raw.json',
        length=length,value=value)
    assert raw['terminal']['status'] == 'OBSERVED_RETURN'
    assert raw['observed_result']['destination_hex'] == format(value,'02x')*length
    assert raw['observed_result']['sentinels_unchanged'] is True
    assert raw['observed_result']['return_value'] == raw['input']['destination']
    assert raw['effect_coverage']['outside_window'] == 'UNKNOWN'
    differences=[]
    for row in raw['trace']:
        expected=[name for name,prior in row['before']['vectors'].items()
            if row['after']['vectors'].get(name)!=prior]
        assert row['changed_vectors']==expected
        differences.extend(expected)
    if (length,value)==(31,7):
        # This positive detection control must actually change sampled bits.
        # No skip or conditional escape is allowed if its actual input fails.
        assert differences


def test_wrong_declared_ifunc_entry_is_a_terminal_stop(tmp_path):
    fp = live_fingerprint()
    fp['libc']['memset_elf_entry'] = 0
    raw = observer().observe_memset(fp,tmp_path/'observation.raw.json')
    assert raw['terminal']['status'] == 'STOP_ENTRY_DRIFT'
    assert raw['terminal']['complete'] is False
    assert raw['certified_state_progress'] is False


def test_hash_bound_cli_refuses_unbound_fingerprint(tmp_path):
    fp = tmp_path/'fp.json'
    fp.write_text(json.dumps(live_fingerprint()))
    with pytest.raises(ValueError, match='fingerprint'):
        observer().main(['--fingerprint', str(fp), '--fingerprint-sha256', '0'*64,
            '--output', str(tmp_path/'observation.raw.json')])
    assert not (tmp_path/'observation.raw.json').exists()
