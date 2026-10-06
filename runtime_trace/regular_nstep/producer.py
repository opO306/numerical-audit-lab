"""Actual acquisition -> generic per-body Numeric IR -> unchanged frozen V2."""
import argparse
import copy
import json
import gc
import time
from pathlib import Path
from lab import v2_bound
from runtime_trace.numeric_ir.translator import _Dataflow, _ByteRef
from runtime_trace.numeric_ir.v2.adapter import _Execution, _verify_frozen, _load_pins
from runtime_trace.numeric_ir.v2.schema import form_document
from . import raw_check, checker
from .schema import FILES, boundary, completion, namespaced, sha, sid, write


def block(capture, rows, original, prior, root):
    region = copy.deepcopy(original)
    region['phase'] = region['occurrence']
    for field in ('start_state', 'end_state'):
        region[field] = {name: '0x' + ''.join(x[2:] for x in reversed(lanes))
                         for name, lanes in region[field].items()}
    flow = _Dataflow(rows, capture, root)
    flow.start_region(region, {})
    for register in ('v0', 'v1'):
        for k in range(8):
            ref = flow.state['r', register, k]
            flow.state['r', register, k] = _ByteRef(ref.value_id, ref.offset, ref.origin_tag + ':' + str(k))
    for row in rows[region['start_seq']:region['end_seq']]:
        flow.process_record(row)
    terminal = flow.end_region(region)
    namespace = capture['acquisition_id'] + '/' + region['occurrence']
    ir = {'schema': 'regular-nstep-body-ir-v1', 'namespace': namespace,
          'acquisition_id': capture['acquisition_id'], 'region': original,
          'operations': namespaced(flow.operations, namespace), 'values': namespaced(flow.values, namespace)}
    link = boundary(capture, original, prior)
    execution = _Execution({v['value_id']: v for v in ir['values']},
                           {op['output_value_id']: i for i, op in enumerate(ir['operations'])})
    for carry in link['carry']:
        state = execution.bind(carry['entry_state_id'].removeprefix('state:').rsplit(':byte:', 1)[0], carry['byte_offset'])
        form = v2_bound.Form([float.fromhex(c) for c in carry['form']['coef']], float.fromhex(carry['form']['box']))
        execution.forms[state] = form
        execution.bindings[state].update(form=form_document(form), binding_kind='CARRIED',
            source_state_id=carry['audited_endpoint']['form_source_state_id'])
    operations = []
    for i, op in enumerate(ir['operations']):
        a, b = execution.bind(op['input0_value_id'], 0, i), execution.bind(op['input1_value_id'], 0, i)
        result_state, kind = sid(op['output_value_id']), op['operation_kind'].removesuffix('_BINARY64')
        result = v2_bound.step_forms([(kind, result_state, [a, b], None)],
            {a: int(op['input0_raw_bits'], 16), b: int(op['input1_raw_bits'], 16), result_state: int(op['output_raw_bits'], 16)},
            {a: execution.forms[a], b: execution.forms[b]})[result_state]
        execution.record_result(op['output_value_id'], result, i)
        operations.append({**op, 'v2_sequence': i, 'v2_operation_kind': kind,
            'input0_state_id': a, 'input1_state_id': b, 'output_state_id': result_state,
            'input0_form': form_document(execution.forms[a]), 'input1_form': form_document(execution.forms[b]),
            'output_form': form_document(result)})
    boundaries = [{'value_id': v['value_id'], 'boundary': v['producer']['boundary'],
        'state_ids': [execution.bind(v['value_id'], k) for k in range(0, v['width'], 8)]}
        for v in ir['values'] if v['producer']['role'] == 'boundary']
    endpoint = []
    for name in ('q', 'full_v', 'latent', 'gradient'):
        for offset in (0, 8):
            ref = terminal[name][offset]
            if any(r.value_id != ref.value_id or r.offset != ref.offset + k
                   for k, r in enumerate(terminal[name][offset:offset+8])):
                raise ValueError('mixed terminal scalar provenance')
            vid = namespace + '/' + ref.value_id
            state = execution.bind(vid, ref.offset)
            endpoint.append({'component': name, 'byte_offset': offset,
                'center_bits': execution.bindings[state]['raw_center_bits'], 'value_id': vid,
                'source_byte_offset': ref.offset, 'acquisition_id': capture['acquisition_id'],
                'occurrence': region['occurrence'], 'state_id': state, 'form': form_document(execution.forms[state])})
    frozen = _verify_frozen(root, _load_pins()['frozen_v2_lf_sha256'])
    v2 = {'schema': 'regular-step2-frozen-v2-v1', 'namespace': namespace, 'frozen_v2': frozen,
          'shared_form_basis': link['shared_form_basis'], 'operations': operations,
          'state_bindings': execution.serialized(), 'boundaries': boundaries}
    return {'ir': ir, 'boundary': link, 'v2': v2, 'endpoint': endpoint}


def build(capture_dir, out, root):
    capture_dir, out, root = Path(capture_dir), Path(out), Path(root)
    out.mkdir(parents=True, exist_ok=False)
    pending = out / '.pending'
    pending.mkdir()
    report = None
    native, capture, failure_stage = None, None, 'ACQUISITION'
    stage_times = {}
    try:
        clock = time.perf_counter()
        capture, rows, native = raw_check.validate(capture_dir, root)
        failure_stage = 'DERIVATION'
        stage_times['raw_semantic_validation_seconds'] = time.perf_counter() - clock
        clock = time.perf_counter()
        blocks, prior = [], None
        for region in capture['regions']:
            current = block(capture, rows, region, prior, root)
            blocks.append(current)
            prior = current['endpoint']
        stage_times['automatic_ir_and_frozen_v2_seconds'] = time.perf_counter() - clock
        # Release the acquired transcript before independent reloading. Keeping
        # both full transcripts would consume the same 4 GiB job allowance.
        del rows
        gc.collect()
        write(pending / 'blocks.json', blocks)
        write(pending / 'native_report.json', native)
        hashes = [{'path': name, 'sha256': sha(pending / name)} for name in FILES]
        document = completion(capture, blocks, native, hashes)
        write(pending / 'completion.json', document)
        clock = time.perf_counter()
        report = checker.check(capture_dir, pending, root)
        failure_stage = 'STAGED_INDEPENDENT_CHECK'
        stage_times['staged_independent_check_seconds'] = time.perf_counter() - clock
        write(out / 'stage_costs.json', stage_times)
        write(pending / 'checker_report.json', report)
        if report['verdict'] != 'CHECKER_PASS':
            raise ValueError('independent staged check refused: ' + report['reason'])
        # Completion is the last published file. Partial files never constitute success.
        for name in (*FILES, 'checker_report.json', 'completion.json'):
            (pending / name).rename(out / name)
        pending.rmdir()
        return report
    except Exception as exc:
        failure = {'requested_steps': capture['requested_steps'] if capture else None,
            'captured_steps': len(capture['regions']) - 1 if capture else 0,
            'checked_steps': 0, 'last_verified_v2_trace_seq': None,
            'last_verified_native_trace_seq': native['last_verified_trace_seq'] if native else None,
            'failure_stage': failure_stage}
        if report:
            failure.update(report)
        failure.update(verdict='REFUSED', requested_complete=False, reason=str(exc))
        write(out / 'failure.json', failure)
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--capture', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    try:
        report = build(args.capture, args.out, args.root)
    except Exception as exc:
        print(json.dumps({'verdict': 'REFUSED', 'requested_complete': False, 'reason': str(exc)}))
        return 2
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
