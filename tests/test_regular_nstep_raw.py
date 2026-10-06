"""Actual captured 10-step semantic validation and repaired-transcript attacks."""
import copy
import importlib
import json
import os
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
CAPTURE = ROOT / os.environ.get('RTN_TEST_CAPTURE', 'runtime_trace/regular_nstep/artifacts/connected10-final2/capture')


def api():
    try:
        return importlib.import_module('runtime_trace.regular_nstep.raw_check')
    except ModuleNotFoundError:
        pytest.fail('independent generic raw checker is absent')


def test_actual_10step_complete_native_frontier():
    capture, rows, report = api().validate(CAPTURE, ROOT)
    assert report['checked_steps'] == 10
    assert report['carry_join_count'] == 9
    assert len(report['terminal_output_stores']) == 4
    assert report['init_to_step1'] == 'UNTRACED'
    assert report['post_terminal_frontier'] == 'UNTRACED'
    assert len(rows) == 9922


def test_actual_semantics_positive_separate_from_historical_source_pins():
    capture = json.loads((CAPTURE / 'capture.json').read_bytes())
    rows = [json.loads(line) for line in (CAPTURE / 'trace.jsonl').read_bytes().splitlines()]
    assert api().validate_semantics(capture, rows, ROOT)['checked_steps'] == 10


@pytest.mark.parametrize('attack', ['false-write-changed', 'inconsistent-bit-repr', 'wrong-owner'])
def test_record_redundancy_and_owner_contract_refuses(attack):
    capture = json.loads((CAPTURE / 'capture.json').read_bytes())
    rows = [json.loads(line) for line in (CAPTURE / 'trace.jsonl').read_bytes().splitlines()]
    if attack == 'wrong-owner':
        owner = [capture['process_identity']['pid'] + 1, 99, 0]
        for row in rows:
            row['ptid'] = owner
            if 'thread_ptid' in row:
                row['thread_ptid'] = owner
        for region in capture['regions']:
            region['ptid'] = owner
        for corridor in capture['caller_corridors']:
            corridor['owner_ptid'] = owner
    else:
        write = next(w for row in rows if row['occurrence'] == 'init'
                     for w in row['possible_memory_writes'] if w['before_hex'] != w['after_hex'])
        if attack == 'false-write-changed':
            write['value_changed'] = False
        else:
            value = int.from_bytes(bytes.fromhex(write['before_hex']), 'little') ^ 1
            write['before_bits'] = f"0x{value:0{write['size'] * 2}x}"
    with pytest.raises(ValueError):
        api().validate_semantics(capture, rows, ROOT)


@pytest.mark.parametrize('attack', ['body-write-omission', 'body-read-omission', 'body-callee-saved'])
def test_whole_body_machine_semantics_not_only_numeric_ir(attack):
    capture = json.loads((CAPTURE / 'capture.json').read_bytes())
    rows = [json.loads(line) for line in (CAPTURE / 'trace.jsonl').read_bytes().splitlines()]
    if attack.endswith('write-omission'):
        row = next(r for r in rows if r['occurrence'] == 'step2' and r['possible_memory_writes'])
        row['possible_memory_writes'] = []
    elif attack.endswith('read-omission'):
        row = next(r for r in rows if r['occurrence'] == 'step2' and r['pre_memory_observations'])
        row['pre_memory_observations'] = []
    else:
        row = next(r for r in rows if r['occurrence'] == 'step2' and r['kind'] == 'MUL')
        changed = f"0x{int(row['post']['gpr']['r13'], 16) + 1:016x}"
        row['post']['gpr']['r13'] = changed
        for following in rows[row['seq'] + 1:]:
            original_pre = following['pre']['gpr']['r13']
            following['pre']['gpr']['r13'] = changed
            if original_pre != following['post']['gpr']['r13']:
                break  # actual later POP restores it; all seams remain coherent
            following['post']['gpr']['r13'] = changed
    with pytest.raises(ValueError):
        api().validate_semantics(capture, rows, ROOT)


@pytest.mark.parametrize('attack', ['missing', 'duplicate', 'reorder', 'cross-process', 'arithmetic', 'false-N', 'gradient'])
def test_repaired_semantic_raw_attacks_refused(attack):
    capture = json.loads((CAPTURE / 'capture.json').read_bytes())
    rows = [json.loads(line) for line in (CAPTURE / 'trace.jsonl').read_bytes().splitlines()]
    if attack == 'missing':
        del rows[500]
    elif attack == 'duplicate':
        rows.insert(500, copy.deepcopy(rows[500]))
    elif attack == 'reorder':
        rows[500], rows[501] = rows[501], rows[500]
    elif attack == 'cross-process':
        rows[500]['pid'] += 1
    elif attack == 'arithmetic':
        row = next(r for r in rows if r.get('kind') == 'MUL')
        row['result_bits'] = '0x3ff0000000000000'
    elif attack == 'false-N':
        capture['requested_steps'] = 100
    else:
        capture['regions'][2]['start_state']['gradient'][0] = '0x3ff0000000000000'
    # No hashes are used by this semantic entry point. The attack cannot rely
    # on a stale hash to be rejected; all outer digests can be repaired.
    with pytest.raises(ValueError):
        api().validate_semantics(capture, rows, ROOT)
