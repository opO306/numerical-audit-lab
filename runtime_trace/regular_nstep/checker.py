"""Reconstruct graph and Forms independently; never import producer/translator/V2."""
import argparse
import json
from pathlib import Path
from runtime_trace.regular_2step import checker as audited_checker
from . import raw_check
from .schema import FILES, boundary, canonical, completion, digest, load, namespaced, sha


def check(capture_dir, derived_dir, root):
    checked, stage = 0, 'ACQUISITION'
    requested, captured, frontier, last_v2 = None, 0, None, None
    try:
        diagnostic = load(Path(capture_dir) / 'capture.json')
        requested = diagnostic.get('requested_steps')
        captured = max(0, len(diagnostic.get('regions', [])) - 1)
        capture, rows, native = raw_check.validate(capture_dir, root)
        frontier = native['last_verified_trace_seq']
        stage = 'HASH'
        derived_dir = Path(derived_dir)
        blocks = load(derived_dir / 'blocks.json')
        supplied = load(derived_dir / 'completion.json')
        hashes = [{'path': name, 'sha256': sha(derived_dir / name)} for name in FILES]
        raw_check.require(supplied['ordered_component_hashes'] == hashes, 'component integrity')
        raw_check.require(supplied['completion_sha256'] == digest({k: v for k, v in supplied.items()
                        if k != 'completion_sha256'}), 'completion integrity')
        stage = 'SEMANTIC'
        raw_check.require(canonical(load(derived_dir / 'native_report.json')) == canonical(native), 'fresh native report')
        raw_check.require(type(blocks) is list and len(blocks) == len(capture['regions']), 'all N+1 graph blocks')
        prior, reconstructed = None, []
        for region, received in zip(capture['regions'], blocks):
            namespace = capture['acquisition_id'] + '/' + region['occurrence']
            # Retain actual global sequence IDs with a sparse view. Never copy
            # the whole growing transcript once per step.
            view = [None] * region['start_seq'] + rows[region['start_seq']:region['end_seq']]
            ops, values, state = audited_checker.graph(capture, view, [region], Path(root))
            ir = {'schema': 'regular-nstep-body-ir-v1', 'namespace': namespace,
                  'acquisition_id': capture['acquisition_id'], 'region': region,
                  'operations': namespaced(ops, namespace), 'values': namespaced(values, namespace)}
            raw_check.require(canonical(ir) == canonical(received['ir']), 'actual ordered complete IR graph')
            link = boundary(capture, region, prior)
            raw_check.require(canonical(link) == canonical(received['boundary']), 'immediate prior dynamic state/Form join')
            lanes = audited_checker.final_lanes({**capture, 'regions': [None, None, region]}, values, state, namespace)
            lanes = [{**e, 'occurrence': region['occurrence']} for e in lanes]
            v2, endpoint = audited_checker.expected_forms(ir, link, lanes, Path(root))
            raw_check.require(canonical(v2) == canonical(received['v2']), 'independent exact Form operation/state correspondence')
            raw_check.require(canonical(endpoint) == canonical(received['endpoint']), 'actual complete terminal provenance/Form')
            reconstructed.append({'ir': ir, 'boundary': link, 'v2': v2, 'endpoint': endpoint})
            prior = endpoint
            checked += region['occurrence'] != 'init'
            last_v2 = region['end_seq'] - 1
        expected = completion(capture, reconstructed, native, hashes)
        raw_check.require(canonical(supplied) == canonical(expected), 'honest requested-run completion/frontier')
        return {k: expected[k] for k in ('schema', 'verdict', 'requested_steps', 'checked_steps',
            'requested_complete', 'operation_count', 'carry_join_count', 'formal_certification',
            'init_to_step1', 'post_terminal_frontier', 'audit_status', 'completion_sha256')}
    except Exception as exc:
        return {'schema': 'regular-nstep-checker-report-v1', 'verdict': 'REFUSED',
                'requested_complete': False, 'checked_steps': checked,
                'requested_steps': requested, 'captured_steps': captured,
                'last_verified_native_trace_seq': frontier, 'last_verified_v2_trace_seq': last_v2,
                'failure_stage': stage, 'reason': str(exc)}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--capture', type=Path, required=True)
    p.add_argument('--derived', type=Path, required=True)
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--report', type=Path)
    a = p.parse_args()
    report = check(a.capture, a.derived, a.root)
    if a.report is not None:
        from .acquire import write
        write(a.report, report)
    print(json.dumps(report, sort_keys=True))
    return 0 if report['verdict'] == 'CHECKER_PASS' else 2


if __name__ == '__main__':
    raise SystemExit(main())
