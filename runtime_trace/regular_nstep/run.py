"""Bounded one-source public integration path for finite 1..100-step requests."""
import argparse
import json
from pathlib import Path
import sys
from .acquire import validate_n, write
from .resources import Limits, run_guarded, EvidenceBudget
from .schema import canonical, load, sha


def run(steps, out, ledger, root):
    n = validate_n(steps)
    out, ledger, root = Path(out).resolve(), Path(ledger).resolve(), Path(root).resolve()
    if ledger.parent not in out.parents or out.exists():
        raise ValueError('exclusive run must be inside accounted evidence root')
    out.mkdir(parents=True)
    def publish(path, value):
        EvidenceBudget(ledger.parent, Limits().storage_bytes).write(
            str(path.relative_to(ledger.parent)), canonical(value) + b'\n')
    def sources():
        paths = [p for p in (root / 'runtime_trace').rglob('*.py') if 'artifacts' not in p.parts]
        paths.extend([root / 'lab/v2_bound.py', root / 'independent_checker/oracle.py'])
        return {str(p.relative_to(root)): sha(p) for p in sorted(paths)}
    source = sources()
    publish(out / 'integration_source_pinset.json', source)
    receipts = []
    try:
        commands = [
            [sys.executable, '-m', 'runtime_trace.regular_nstep.acquire', '--steps', str(n), '--out', str(out / 'capture')],
            [sys.executable, '-m', 'runtime_trace.regular_nstep.producer', '--capture', str(out / 'capture'),
                '--out', str(out / 'derived'), '--root', str(root)],
            [sys.executable, '-m', 'runtime_trace.regular_nstep.checker', '--capture', str(out / 'capture'),
                '--derived', str(out / 'derived'), '--root', str(root),
                '--report', str(out / 'fresh_checker_report.json')]]
        for stage, command in zip(('acquisition', 'derivation', 'independent_check'), commands):
            receipt = run_guarded(command, Limits(), out / stage, ledger, cwd=root,
                artifact_allowance=1073741824 if stage == 'acquisition' else 67108864)
            receipts.append(receipt)
            if receipt['verdict'] != 'EXECUTED':
                raise ValueError(stage + ' did not complete within guarded contract')
        report = load(out / 'fresh_checker_report.json')
        if (report.get('verdict') != 'CHECKER_PASS'
            or type(report.get('requested_steps')) is not int or report['requested_steps'] != n
            or type(report.get('checked_steps')) is not int or report['checked_steps'] != n
            or report.get('requested_complete') is not True):
            raise ValueError('requested run not fully checked')
        if sources() != source:
            raise ValueError('source file set/bytes changed during requested run')
        publish(out / 'run_result.json', {**report, 'schema': 'regular-nstep-guarded-run-v1',
            'integration_source_pinset_sha256': sha(out / 'integration_source_pinset.json'),
            'stage_receipts': [sha(out / s / 'execution.json') for s in ('acquisition', 'derivation', 'independent_check')]})
        return report
    except Exception as exc:
        report = {'verdict': 'REFUSED', 'requested_steps': n, 'requested_complete': False,
                  'checked_steps': 0, 'reason': str(exc), 'completed_resource_stages': len(receipts)}
        for checked_path in (out / 'fresh_checker_report.json', out / 'derived/checker_report.json', out / 'derived/.pending/checker_report.json',
                             out / 'derived/failure.json'):
            if checked_path.exists():
                try:
                    previous = load(checked_path)
                    if type(previous) is not dict:
                        raise ValueError('checker report object required')
                except Exception as invalid_report:
                    report.update(failure_stage='CHECKER_REPORT_UNAVAILABLE',
                        reason=report['reason'] + '; unreadable latest report: ' + str(invalid_report))
                    break
                report.update({k: previous[k] for k in ('checked_steps', 'last_verified_native_trace_seq',
                    'last_verified_v2_trace_seq', 'captured_steps', 'failure_stage') if k in previous})
                break
        publish(out / 'run_refusal.json', report)
        return report


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--steps', type=int, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--ledger', type=Path, required=True)
    a = p.parse_args()
    root = Path(__file__).resolve().parents[2]
    report = run(a.steps, a.out, a.ledger, root)
    print(json.dumps(report, sort_keys=True))
    return 0 if report['verdict'] == 'CHECKER_PASS' else 2


if __name__ == '__main__':
    raise SystemExit(main())
