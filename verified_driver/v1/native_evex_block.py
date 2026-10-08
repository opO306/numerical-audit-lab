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
from runtime_trace.regular_nstep.schema import FILES, boundary, completion, namespaced, sha, sid, write


from .native_evex_graph_producer import NativeEvexDataflow

def block(capture, rows, original, prior, root, *, verified_spans):
    region = copy.deepcopy(original)
    region['phase'] = region['occurrence']
    for field in ('start_state', 'end_state'):
        region[field] = {name: '0x' + ''.join(x[2:] for x in reversed(lanes))
                         for name, lanes in region[field].items()}
    flow = NativeEvexDataflow(rows, capture, root, verified_spans=verified_spans)
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

