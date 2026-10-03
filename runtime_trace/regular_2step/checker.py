"""Independent narrow two-step checker; no production propagation imports."""
import argparse
import copy
import hashlib
import json
from collections import Counter
from pathlib import Path

from runtime_trace import correspondence as raw_checker
from runtime_trace.numeric_ir import checker as graph_checker
from runtime_trace.caller_transition import checker as caller_checker
from . import structure
from .form_oracle import oracle, check_ieee, SOURCE_SHA
from .schema import (BASE, CASE_PINS, canonical, component_hashes, completion,
                     digest, load, namespaced, sha, sid)


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def graph(capture, rows, regions, root, *, prefix=False):
    """Reuse independent byte-storage reconstruction, never the translator."""
    selected = copy.deepcopy(regions)
    graph_rows = copy.deepcopy(rows)
    for region in selected:
        phase = 'step' if prefix and region['occurrence'] == 'step1' else region['occurrence']
        region['phase'] = phase
        for field in ('start_state', 'end_state'):
            region[field] = {name: '0x' + ''.join(x[2:] for x in reversed(lanes))
                             for name, lanes in region[field].items()}
        for row in graph_rows[region['start_seq']:region['end_seq']]:
            row['phase'] = phase
    subcapture = {**capture, 'regions': selected}
    body = [r for region in selected for r in graph_rows[region['start_seq']:region['end_seq']]]
    decoded = raw_checker.disassembly_for_rows(body, capture['modules'], root=root)
    raw_checker.verify_flow(graph_rows, subcapture, decoded, root=root)
    reconstruction = graph_checker._Reconstruction(graph_rows, subcapture, decoded)
    operations, values = reconstruction.run()
    for operation in operations:
        check_ieee(operation['operation_kind'], operation['input0_raw_bits'],
                   operation['input1_raw_bits'], operation['output_raw_bits'])
    return operations, values, reconstruction.state


def trusted_case(capture_dir, root, test_pins=None):
    capture = load(capture_dir / 'capture.json')
    pins = CASE_PINS.get(capture.get('case'))
    require(pins is not None, 'unknown accepted case')
    if test_pins is not None:
        require(test_pins.get('mode') == 'TEST_ONLY_REPIN', 'private test trust mode')
        require(test_pins['capture_directory'] == str(capture_dir.resolve()), 'private test path')
        expected_seal, expected_structure = test_pins['seal'], test_pins['structure']
    else:
        require(capture_dir.resolve() == (root / BASE / 'artifacts' / pins['directory']).resolve(), 'immutable capture path')
        expected_seal, expected_structure = pins['seal'], pins['structure']
        require(capture['acquisition_id'] == pins['acquisition_id'], 'immutable acquisition identity')
    require(sha(capture_dir / 'acquisition_seal.json') == expected_seal, 'immutable acquisition seal')
    require(sha(capture_dir / 'structure_report.json') == expected_structure, 'immutable structure receipt')
    return capture, pins


def prefix_structure(rows, region):
    """Cross-process structure with a bijection of nonnumeric routing bytes.

    Absolute heap routing addresses differ across acquisitions. Assign each
    observed byte its first-occurrence ordinal, preserving all observed alias
    relationships. Component/stack roles, opcodes, ELF bytes and control targets
    remain exact; numerical bits/roots are separately compared by full graph.
    """
    aliases, topology = {}, []
    for row in rows:
        operands = structure._operand_topology(row, region)
        for operand, raw_operand in zip(operands, row['operands']):
            role = operand[1]
            if 'constant_origin' in raw_operand:
                origin = raw_operand['constant_origin']
                operand[1] = ['elf-constant', origin['module_sha256'], origin['file_offset'], raw_operand['width']]
            elif role[0] == 'other':
                address, width = role[1:]
                operand[1] = ['routing-bytes', [aliases.setdefault(address + k, len(aliases)) for k in range(width)]]
        topology.append(operands)
    return {'instructions': [(r['module_sha256'], r['elf_address'], r['bytes'], r['opcode'], r['kind']) for r in rows],
        'control': [(i, structure._post_target(r)) for i, r in enumerate(rows) if r['kind'] == 'CONTROL'],
        'topology': topology}


def context(capture_dir, root, test_pins=None):
    """Validate unchanged lower blocks, full new trace and all external joins."""
    capture_dir, root = Path(capture_dir).resolve(), Path(root).resolve()
    capture, pins = trusted_case(capture_dir, root, test_pins)
    old = caller_checker._PRODUCTION_CASE_PINS[pins['caller']]
    require(capture['antecedent_binding']['antecedent_capture_path'] == old.capture_directory + '/capture.json', 'selected caller lineage (stale or mixed evidence)')
    structural = structure.compare(capture_dir, root)
    rows = [json.loads(line) for line in (capture_dir / 'trace.jsonl').read_bytes().splitlines()]
    caller_report = caller_checker.check_transition(root / old.capture_directory, root / old.transition_path, root=root)
    transition = load(root / old.transition_path)
    old_ir = load(root / old.ir_path)
    old_trace_dir = root / 'runtime_trace/artifacts' / old.label
    old_ir_report = graph_checker.check(old_ir, old_trace_dir, root=root)
    o = oracle(root)
    _, old_v2_report = o.reconstruct(old.label, root / old.ir_path, root / old.correspondence_path)
    old_capture = load(old_trace_dir / 'capture.json')
    old_rows = [json.loads(line) for line in (old_trace_dir / 'trace.jsonl').read_bytes().splitlines()]
    prefix_ops, prefix_values, _ = graph(capture, rows, capture['regions'][:2], root, prefix=True)
    require(prefix_ops == old_ir['operations'], 'prefix ordered operations/bits differ from audited block')
    require(prefix_values == old_ir['values'], 'prefix complete graph/roots differ from audited block')
    prefix_receipts = []
    for new_region, old_region in zip(capture['regions'][:2], old_capture['regions']):
        new_rows = rows[new_region['start_seq']:new_region['end_seq']]
        prior_rows = old_rows[old_region['start_seq']:old_region['end_seq']]
        new_structure, prior_structure = prefix_structure(new_rows, new_region), prefix_structure(prior_rows, old_region)
        require(new_structure == prior_structure, 'prefix normalized instruction/control/storage structure mismatch')
        prefix_receipts.append({'occurrence': new_region['occurrence'], 'row_count': len(new_rows),
                                'normalized_structure_sha256': digest(new_structure)})
    acq = capture['acquisition_id']
    namespace = acq + '/step2'
    carry = []
    for prior in transition['bindings']['carry']:
        name, offset = prior['component'], prior['byte_offset']
        bits = capture['regions'][2]['start_state'][name][offset // 8]
        require(bits == prior['center_bits'], 'carried center role mismatch')
        carry.append({'component': name, 'byte_offset': offset, 'center_bits': bits,
            'form': prior['form'], 'audited_endpoint': prior,
            'new_step1_terminal_id': acq + '/step1/' + prior['endpoint_memory_value_id'],
            'new_step1_copy_source_id': acq + '/step1/' + prior['copy_source_value_id'],
            'entry_state_id': sid(namespace + '/v:boundary:step2:' + name, offset),
            'from_acquisition_id': acq, 'to_acquisition_id': acq,
            'process_local_pointer': capture['regions'][2]['pointers'][name],
            'caller_range': [capture['caller_corridor']['start_seq'], capture['caller_corridor']['end_seq']]})
    boundary = {'carry': carry, 'shared_form_basis': transition['shared_form_basis'],
        'gradient': {**transition['bindings']['gradient'],
            'entry_state_ids': [sid(namespace + '/v:boundary:step2:gradient', k) for k in (0, 8)]},
        'time': {**transition['bindings']['time'], 'actual_new_source': capture['caller_corridor']['argument_sources']['t'],
                 'entry_state_id': sid(namespace + '/v:boundary:step2:xmm0')},
        'dt': {**transition['bindings']['dt'], 'actual_new_source': capture['caller_corridor']['argument_sources']['dt'],
               'entry_state_id': sid(namespace + '/v:boundary:step2:xmm1')},
        'process_identity': capture['process_identity'], 'acquisition_id': acq}
    reports = {'schema': 'regular-2step-lower-components-v1', 'structure': structural,
        'old_ir': old_ir_report, 'old_v2_independent': old_v2_report, 'old_caller': caller_report,
        'prefix_structure': prefix_receipts, 'prefix_graph_sha256': digest({'operations': prefix_ops, 'values': prefix_values}),
        'independent_form_source_sha256': SOURCE_SHA,
        'caller_instantiation_scope': 'internal new-process instantiation; external PASS limited to old acquisitions',
        'init_return_to_step1_entry': 'UNTRACED: reused old accepted one-step boundary contract'}
    identities = [
        {'role': 'step1_correspondence', 'path': old.correspondence_path, 'sha256': old.correspondence_sha256},
        {'role': 'caller_transition', 'path': old.transition_path, 'sha256': old.transition_sha256},
        {'role': 'step2_trace', 'acquisition_id': acq, 'sha256': capture['trace_sha256']}]
    return capture, rows, namespace, boundary, reports, identities


def expected_forms(ir, boundary, endpoints, root):
    """Independently traverse COPY lanes and propagate exact-rational Forms."""
    o = oracle(root)
    frozen_hash = hashlib.sha256((Path(root) / 'lab/v2_bound.py').read_bytes().replace(b'\r\n', b'\n')).hexdigest()
    require(frozen_hash == o.FROZEN, 'frozen V2 source identity')
    frozen = {'module': 'lab.v2_bound', 'operator': 'step_forms', 'k': 4,
              'lf_sha256': frozen_hash, 'imported_lf_sha256': frozen_hash, 'requested_lf_sha256': frozen_hash}
    by = {v['value_id']: v for v in ir['values']}
    require(len(by) == len(ir['values']), 'duplicate graph IDs')
    carries = {c['entry_state_id']: c for c in boundary['carry']}
    result_index = {v['output_value_id']: i for i, v in enumerate(ir['operations'])}
    states, forms, active = {}, {}, set()

    def bind(vid, offset=0):
        key = sid(vid, offset)
        if key in states:
            return key
        require(key not in active, 'state graph cycle')
        active.add(key)
        v = by[vid]
        bits = o.lane_bits(v, offset)
        kind, source, producer_index = v['producer_kind'], None, None
        if key in carries:
            carried = carries[key]
            form = o.Form([float.fromhex(c) for c in carried['form']['coef']], float.fromhex(carried['form']['box']))
            binding_kind, source = 'CARRIED', carried['audited_endpoint']['form_source_state_id']
        elif kind in ('LOAD_BITS', 'CONST_BITS', 'ZERO_BITS'):
            form, binding_kind = o.Form([0.] * 4, 0.), kind.removesuffix('_BITS')
        elif kind == 'COPY_BITS':
            matches = [e for e in v['source_slices'] if e['destination_offset'] <= offset and offset + 8 <= e['destination_offset'] + e['width']]
            require(len(matches) == 1, 'mixed/incomplete COPY scalar')
            edge = matches[0]
            source = bind(edge['value_id'], edge['source_offset'] + offset - edge['destination_offset'])
            require(states[source]['raw_center_bits'] == bits, 'COPY bits mismatch')
            form, binding_kind = forms[source], 'COPY'
        elif kind == 'ARITHMETIC_RESULT':
            require(key in forms, 'forward arithmetic dependency')
            form, binding_kind, producer_index = forms[key], kind, result_index[vid]
        else:
            raise ValueError('unsupported Form producer')
        forms[key] = form
        states[key] = {'state_id': key, 'value_id': vid, 'byte_offset': offset, 'width': 8,
            'raw_center_bits': bits, 'form': o.fdoc(form), 'binding_kind': binding_kind,
            'source_state_id': source, 'producer_ir_sequence': producer_index,
            'phase': v['producer']['phase'], 'trace_sequence': v['producer']['trace_sequence']}
        active.remove(key)
        return key

    operations = []
    for i, operation in enumerate(ir['operations']):
        a, b = bind(operation['input0_value_id']), bind(operation['input1_value_id'])
        result = o.compute_form(operation['operation_kind'], operation['output_raw_bits'],
                                operation['input0_raw_bits'], operation['input1_raw_bits'], forms[a], forms[b])
        output = sid(operation['output_value_id'])
        forms[output] = result
        bind(operation['output_value_id'])
        operations.append({**operation, 'v2_sequence': i,
            'v2_operation_kind': operation['operation_kind'].removesuffix('_BINARY64'),
            'input0_state_id': a, 'input1_state_id': b, 'output_state_id': output,
            'input0_form': o.fdoc(forms[a]), 'input1_form': o.fdoc(forms[b]), 'output_form': o.fdoc(result)})
    boundaries = []
    for v in ir['values']:
        if v['producer']['role'] == 'boundary':
            state_ids = [bind(v['value_id'], k) for k in range(0, v['width'], 8)]
            boundaries.append({'value_id': v['value_id'], 'state_ids': state_ids,
                               'boundary': v['producer']['boundary']})
    endpoint = []
    for entry in endpoints:
        state = bind(entry['value_id'], entry['source_byte_offset'])
        endpoint.append({**entry, 'state_id': state, 'form': o.fdoc(forms[state])})
    return {'schema': 'regular-step2-frozen-v2-v1', 'namespace': ir['namespace'], 'frozen_v2': frozen,
        'shared_form_basis': boundary['shared_form_basis'], 'operations': operations,
        'state_bindings': sorted(states.values(), key=lambda s: (s['value_id'], s['byte_offset'])),
        'boundaries': boundaries}, endpoint


def final_lanes(capture, values, state, namespace):
    by = {v['value_id']: v for v in values}
    endpoint = []
    for name in ('q', 'full_v', 'latent', 'gradient'):
        pointer = capture['regions'][2]['pointers'][name]
        for offset in (0, 8):
            refs = [state['m', pointer + offset + k] for k in range(8)]
            vid, start = refs[0]
            require(refs == [(vid, start + k) for k in range(8)], 'terminal state mixed provenance')
            bits = '0x' + int.from_bytes(int(by[vid]['raw_bits'], 16).to_bytes(by[vid]['width'], 'little')[start:start+8], 'little').to_bytes(8, 'big').hex()
            require(bits == capture['regions'][2]['end_state'][name][offset // 8], 'terminal bits mismatch')
            endpoint.append({'component': name, 'byte_offset': offset, 'center_bits': bits,
                'value_id': namespace + '/' + vid, 'source_byte_offset': start,
                'acquisition_id': capture['acquisition_id']})
    return endpoint


def chain_document(capture, boundary, identities, endpoint, hashes):
    chain = {'schema': 'REGULAR_2STEP_CHAIN_V1', 'audit_status': 'INDEPENDENT AUDIT PENDING',
        'case': capture['case'], 'acquisition_id': capture['acquisition_id'],
        'process_identity': capture['process_identity'],
        'identities': identities + [{'role': 'step2_ir', **hashes[0]}, {'role': 'step2_v2', **hashes[1]}],
        'initial_boundary': capture['regions'][0]['start_state'],
        'intermediate_boundary': boundary, 'final_boundary': endpoint,
        'ordered_component_hashes': hashes,
        'scope': 'regular init + complete 2-step; no N-step or physical certification',
        'init_return_to_step1_entry': 'UNTRACED: reused old accepted one-step boundary contract'}
    chain['completion_sha256'] = completion(chain)
    return chain


def _check(capture_dir, derived_dir, root, test_pins=None):
    capture_dir, derived_dir, root = Path(capture_dir).resolve(), Path(derived_dir).resolve(), Path(root).resolve()
    stage = 'TRUST'
    try:
        trusted_case(capture_dir, root, test_pins)
        stage = 'HASH'
        ir, v2, endpoint, components = [load(derived_dir / f) for f in ('numeric_ir.json', 'v2_correspondence.json', 'endpoint.json', 'components.json')]
        chain = load(derived_dir / 'chain.json')
        hashes = component_hashes(derived_dir)
        require(chain['completion_sha256'] == completion(chain), 'completion hash mismatch')
        require(chain['ordered_component_hashes'] == hashes, 'ordered component hash mismatch')
        stage = 'SEMANTIC'
        capture, rows, namespace, boundary, reports, identities = context(capture_dir, root, test_pins)
        operations, values, state = graph(capture, rows, [capture['regions'][2]], root)
        expected_ir = {'schema': 'regular-step2-numeric-ir-v1', 'namespace': namespace,
            'acquisition_id': capture['acquisition_id'], 'trace_sha256': capture['trace_sha256'],
            'region': capture['regions'][2], 'operations': namespaced(operations, namespace),
            'values': namespaced(values, namespace)}
        require(canonical(ir) == canonical(expected_ir), 'step2 complete graph reconstruction mismatch (order/identity/bits/storage)')
        lanes = final_lanes(capture, values, state, namespace)
        expected_v2, expected_endpoint = expected_forms(ir, boundary, lanes, root)
        require(canonical(v2) == canonical(expected_v2), 'independent Form/state/operation/boundary correspondence mismatch')
        require(canonical(endpoint) == canonical(expected_endpoint), 'final endpoint provenance/Form mismatch')
        require(canonical(components) == canonical(reports), 'lower component semantic receipt mismatch')
        require(canonical(chain) == canonical(chain_document(capture, boundary, identities, endpoint, hashes)), 'semantic chain join/identity/handoff mismatch')
        return {'schema': 'regular-2step-checker-report-v1', 'verdict': 'CHECKER_PASS',
            'acquisition_id': capture['acquisition_id'], 'completion_sha256': chain['completion_sha256'],
            'operation_count': len(operations), 'operation_counts': dict(Counter(o['operation_kind'] for o in operations)),
            'value_count': len(values), 'state_count': len(v2['state_bindings']), 'carry_count': 6,
            'audit_status': 'INDEPENDENT AUDIT PENDING', 'test_trust_mode': test_pins is not None}
    except (ValueError, TypeError, KeyError, IndexError, OSError, AssertionError, OverflowError, AttributeError, RecursionError) as exc:
        return {'schema': 'regular-2step-checker-report-v1', 'verdict': 'REFUSED',
                'stage': stage, 'reason': str(exc), 'test_trust_mode': test_pins is not None}


def check(capture_dir: Path, derived_dir: Path, root: Path) -> dict:
    return _check(capture_dir, derived_dir, root)


def _TEST_ONLY_REPIN_check(capture_dir, derived_dir, root, pins):
    """Private local numerical fixture testing only; never reachable by CLI."""
    return _check(capture_dir, derived_dir, root, pins)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture', type=Path, required=True)
    parser.add_argument('--derived', type=Path, required=True)
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    result = check(args.capture, args.derived, args.root)
    print(json.dumps(result, sort_keys=True))
    return 0 if result['verdict'] == 'CHECKER_PASS' else 2


if __name__ == '__main__':
    raise SystemExit(main())
