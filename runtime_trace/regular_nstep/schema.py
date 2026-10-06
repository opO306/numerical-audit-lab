"""Finite N-step serialization and identity definitions; no evaluator."""
from runtime_trace.regular_2step.schema import canonical, digest, load, namespaced, sha, sid
from .acquire import write

FILES = ('blocks.json', 'native_report.json')


def basis(acq):
    return {'k': 4, 'namespace': acq + '/global-error-basis',
            'meaning': 'computed-minus-true', 'reseeded': False,
            'conditional_accepted_init_to_step1_gap': True}


def boundary(capture, region, prior):
    namespace = capture['acquisition_id'] + '/' + region['occurrence']
    carry = []
    if prior is not None:
        for e in prior:
            if e['component'] == 'gradient':
                continue
            carry.append({'component': e['component'], 'byte_offset': e['byte_offset'],
                'center_bits': e['center_bits'], 'form': e['form'],
                'entry_state_id': sid(namespace + '/v:boundary:' + region['occurrence'] + ':' + e['component'], e['byte_offset']),
                'audited_endpoint': {'form_source_state_id': e['state_id']},
                'from_occurrence': e['occurrence'], 'to_occurrence': region['occurrence'],
                'from_acquisition_id': e['acquisition_id'], 'to_acquisition_id': capture['acquisition_id'],
                'process_local_pointer': region['pointers'][e['component']]})
    return {'carry': carry, 'shared_form_basis': basis(capture['acquisition_id']),
            'gradient': 'actual reset zero; never reset carried q/full_v/latent Forms',
            'represented_t_dt': 'actual observed entry inputs; schedule generation error excluded'}


def completion(capture, blocks, native, hashes):
    n = capture['requested_steps']
    document = {'schema': 'REGULAR_NSTEP_COMPLETION_V1', 'verdict': 'CHECKER_PASS',
        'requested_steps': n, 'checked_steps': n, 'requested_complete': True,
        'acquisition_id': capture['acquisition_id'], 'process_identity': capture['process_identity'],
        'trace_sha256': capture['trace_sha256'], 'source_pinset_sha256': capture['source_pinset_sha256'],
        'ordered_component_hashes': hashes, 'final_endpoint': blocks[-1]['endpoint'],
        'operation_count': sum(len(b['ir']['operations']) for b in blocks),
        'carry_join_count': n - 1, 'native_terminal_frontier': native['last_verified_trace_seq'],
        'init_to_step1': 'UNTRACED', 'post_terminal_frontier': 'UNTRACED',
        'scope': 'finite observed native path; conditional accepted base and original harness tail',
        'formal_certification': False, 'audit_status': 'FRESH INDEPENDENT AUDIT PENDING'}
    document['completion_sha256'] = digest(document)
    return document
