"""Actual captured second-body Numeric IR and unchanged frozen V2 producer."""
import argparse
import copy
import json
from pathlib import Path

from lab import v2_bound
from runtime_trace.numeric_ir.translator import _Dataflow, _ByteRef
from runtime_trace.numeric_ir.v2.adapter import _Execution, _verify_frozen, _load_pins
from runtime_trace.numeric_ir.v2.schema import form_document
from . import checker
from .schema import COMPONENTS, component_hashes, load, namespaced, sid, write


def build(capture_dir: Path, out: Path, root: Path) -> dict:
    """Exclusively create outputs, independently check staging, publish last."""
    capture_dir, out, root = Path(capture_dir), Path(out), Path(root)
    out.mkdir(parents=True, exist_ok=False)
    pending = out / '.pending'
    pending.mkdir()
    try:
        capture, rows, namespace, boundary, reports, identities = checker.context(capture_dir, root)
        frozen = _verify_frozen(root, _load_pins()['frozen_v2_lf_sha256'])
        region = copy.deepcopy(capture['regions'][2])
        region['phase'] = 'step2'
        for field in ('start_state', 'end_state'):
            region[field] = {name: '0x' + ''.join(x[2:] for x in reversed(lanes))
                             for name, lanes in region[field].items()}
        flow = _Dataflow(rows, capture, root)
        flow.start_region(region, {})
        # Task1 records fresh entry XMM roots with byte suffixes, unlike the
        # old one-step acquisition's register-wide origin tag. Preserve that
        # exact new acquisition contract without editing old translator code.
        for register in ('v0', 'v1'):
            for offset in range(8):
                key = ('r', register, offset)
                ref = flow.state[key]
                flow.state[key] = _ByteRef(ref.value_id, ref.offset, ref.origin_tag + ':' + str(offset))
        for row in rows[region['start_seq']:region['end_seq']]:
            flow.process_record(row)
        terminal = flow.end_region(region)
        ir = {'schema': 'regular-step2-numeric-ir-v1', 'namespace': namespace,
            'acquisition_id': capture['acquisition_id'], 'trace_sha256': capture['trace_sha256'],
            'region': capture['regions'][2], 'operations': namespaced(flow.operations, namespace),
            'values': namespaced(flow.values, namespace)}
        values = {v['value_id']: v for v in ir['values']}
        execution = _Execution(values, {op['output_value_id']: i for i, op in enumerate(ir['operations'])})
        for carry in boundary['carry']:
            vid = namespace + '/v:boundary:step2:' + carry['component']
            state = execution.bind(vid, carry['byte_offset'])
            form = v2_bound.Form([float.fromhex(c) for c in carry['form']['coef']], float.fromhex(carry['form']['box']))
            execution.forms[state] = form
            execution.bindings[state].update(form=form_document(form), binding_kind='CARRIED',
                source_state_id=carry['audited_endpoint']['form_source_state_id'])
        operations = []
        for i, op in enumerate(ir['operations']):
            a, b = execution.bind(op['input0_value_id'], 0, i), execution.bind(op['input1_value_id'], 0, i)
            result_state = sid(op['output_value_id'])
            kind = op['operation_kind'].removesuffix('_BINARY64')
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
                if any(r.value_id != ref.value_id or r.offset != ref.offset + k for k, r in enumerate(terminal[name][offset:offset+8])):
                    raise ValueError('mixed terminal lane')
                vid = namespace + '/' + ref.value_id
                state = execution.bind(vid, ref.offset)
                endpoint.append({'component': name, 'byte_offset': offset,
                    'center_bits': execution.bindings[state]['raw_center_bits'], 'value_id': vid,
                    'source_byte_offset': ref.offset, 'acquisition_id': capture['acquisition_id'],
                    'state_id': state, 'form': form_document(execution.forms[state])})
        v2 = {'schema': 'regular-step2-frozen-v2-v1', 'namespace': namespace, 'frozen_v2': frozen,
            'shared_form_basis': boundary['shared_form_basis'], 'operations': operations,
            'state_bindings': execution.serialized(), 'boundaries': boundaries}
        for name, content in zip(COMPONENTS, (ir, v2, endpoint, reports)):
            write(pending / name, content)
        chain = checker.chain_document(capture, boundary, identities, endpoint, component_hashes(pending))
        write(pending / 'chain.json', chain)
        report = checker.check(capture_dir, pending, root)
        write(pending / 'checker_report.json', report)
        if report['verdict'] != 'CHECKER_PASS':
            raise ValueError('independent staged check: ' + report['reason'])
        for name in (*COMPONENTS, 'checker_report.json', 'chain.json'):
            (pending / name).rename(out / name)
        pending.rmdir()
        return report
    except Exception as exc:
        write(out / 'failure.json', {'verdict': 'REFUSED', 'reason': str(exc)})
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    try:
        result = build(args.capture, args.out, args.root)
    except (ValueError, OSError, KeyError, AssertionError) as exc:
        print(json.dumps({'verdict': 'REFUSED', 'reason': str(exc)}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
