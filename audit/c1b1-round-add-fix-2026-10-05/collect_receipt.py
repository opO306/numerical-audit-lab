"""Verify evidence coherence and record an author receipt; no approval."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'current/c1b1-round-add-fix-2026-10-05'


def read(name):
    return json.loads((OUT / name).read_text(encoding='utf8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def xml_summary(name):
    tree = ET.parse(OUT / (name + '.xml'))
    cases = list(tree.iter('testcase'))
    return dict(tests=len(cases), failures=sum(c.find('failure') is not None for c in cases),
                errors=sum(c.find('error') is not None for c in cases),
                skipped=sum(c.find('skipped') is not None for c in cases),
                elapsed_seconds=sum(float(c.attrib.get('time', 0)) for c in cases))


if (OUT / 'receipt.json').exists():
    raise ValueError('refusing to overwrite receipt')
commands = {name: read(name + '-command.json') for name in
            ('targeted', 'impulse', 'spec', 'full', 'static', 'mutants', 'diff-check')}
assert all(v['exit'] == 0 and v['source_unchanged'] for v in commands.values())
tests = {name: xml_summary(name) for name in ('targeted', 'impulse', 'spec', 'full')}
assert all(v['failures'] == v['errors'] == v['skipped'] == 0 for v in tests.values())
assert {k: v['tests'] for k, v in tests.items()} == dict(targeted=19, impulse=720, spec=46, full=1113)
red = xml_summary('round-add-red')
assert (red['tests'], red['failures'], red['errors'], red['skipped']) == (14, 8, 0, 0)
mutants = read('mutants/results.json')['results']
assert len(mutants) == 17 and len({r['name'] for r in mutants}) == 17
for r in mutants:
    assert r['baseline']['exit'] == 0 and r['mutant']['exit'] == 1
    assert r['mutant']['failed'] and not r['mutant']['errors'] and not r['mutant']['skipped']
    assert r['verdict'] == 'DETECTED'
    assert sha(OUT / 'mutants' / r['name'] / 'source-before.py') == r['source_before_sha256']
    assert sha(OUT / 'mutants' / r['name'] / 'source-mutant.py') == r['mutant_source_sha256']
received = read('received-identity.json')
for name, identity in received.items():
    assert sha(OUT / 'received' / name) == identity['sha256'] == sha(Path(identity['original']))
assert sha(ROOT / 'tests/fixtures/impulse_round_add/COUNTEREXAMPLE_INPUT.json') == received['COUNTEREXAMPLE_INPUT.json']['sha256']
after = read('after-boundary-results.json')
assert after['whole_call'][0]['failure'] == read('received/COUNTEREXAMPLE_RESULT.json')['same_cap_with_only_declared_add_charges']['failure']
assert after['whole_call'][1]['raw'] == read('received/COUNTEREXAMPLE_RESULT.json')['with_exact_additional_work_room']['raw']
preservation = read('preservation.json')
assert preservation['changed'] == ['independent_checker/c1b1/impulse/rounding.py']
assert not preservation['missing'] and preservation['historical_byte_identical'] and preservation['approved_spec_byte_identical']
assert all(v['equal_target'] and v['equal_65d8'] for v in preservation['protected'].values())
source = read('source-identity.json')
base = read('baseline.json')['tracked_raw_sha256']
old_sources = {name: base['independent_checker/c1b1/impulse/' + name] for name in source['files']}
old_bundle = hashlib.sha256((json.dumps(old_sources, sort_keys=True, separators=(',', ':'), ensure_ascii=True) + '\n').encode('ascii')).hexdigest()
assert old_bundle == 'a4bd12c92a4ad7f2a00503fa0ed249c8a96546d3999a68203fe4344f0c6554d7'
for name, digest in source['files'].items():
    assert sha(ROOT / 'independent_checker/c1b1/impulse' / name) == digest
    if name != 'rounding.py':
        assert old_sources[name] == digest
assert all(v['source_after'] == source['files'] for v in commands.values())
review = read('resource-path-review.json')
assert len(review['actual_opcodes']) == 495
assert review['additional_finding']['whole_call_direct_sign_multiply_occurrences'] == 1590
report = ROOT / 'docs/C1B1_IMPULSE_ROUND_ADD_FIX_REPORT_2026-10-05.md'
receipt = dict(
    recorded_at_utc=datetime.now(timezone.utc).isoformat(),
    historical_target=preservation['target'], historical_reference_implementation='FAIL',
    historical_independent_implementation_audit='FAIL',
    candidate_source_bundle_sha256=source['source_bundle_sha256'],
    historical_source_bundle_sha256=old_bundle, new_git_commit_sha=None,
    findings={'F-RESOURCE-ROUND-ADD': 'FIX APPLIED / AUTHOR REGRESSION PASS / INDEPENDENT LIMITED REAUDIT PENDING',
              'F-RESOURCE-QDIV-SIGN': 'AUTHOR CONFIRMED / OPEN / NOT FIXED / INDEPENDENT REVIEW PENDING'},
    candidate_independent_approval='NOT YET INDEPENDENTLY APPROVED',
    global_resource_accounting_verified=False,
    runtime_activation_allowed=False, J_status='J_NOT_VERIFIED', certification='NotCertified',
    adapter='PREPARED_ONLY / INVOKE BLOCKED / INDEPENDENT SCHEDULE RECONSTRUCTION OPEN',
    commit_performed=False, push_performed=False,
    tests=tests, red_before_fix=red,
    source_mutants=dict(existing=16, new=1, baselines_pass=17, semantic_detected=17,
                        hash_only_detections=0, errors=0, skipped=0),
    static_spec_checks=155, source_report_sha256=sha(report),
    python=sys.version, commands={k: dict(command=v['command'], exit=v['exit'], elapsed_seconds=v['elapsed_seconds']) for k, v in commands.items()},
    git_status=subprocess.check_output(['git', 'status', '--short'], cwd=ROOT).decode('utf8'),
    scope='AUTHOR EVIDENCE ONLY; COUNTS OVERLAP AND ARE NOT INDEPENDENT PROOF COUNTS')
files = [p for p in OUT.rglob('*') if p.is_file() and p.name != 'receipt.json']
files += [report, ROOT / 'tests/test_impulse_round_add_accounting.py',
          ROOT / 'tests/fixtures/impulse_round_add/COUNTEREXAMPLE_INPUT.json']
files += list((ROOT / 'audit/c1b1-round-add-fix-2026-10-05').glob('*.py'))
receipt['evidence_files'] = {p.relative_to(ROOT).as_posix(): dict(sha256=sha(p), bytes=p.stat().st_size)
                             for p in sorted(files)}
(OUT / 'receipt.json').write_text(json.dumps(receipt, indent=2, ensure_ascii=True) + '\n', encoding='ascii')
print('AUTHOR RECEIPT VERIFIED', len(receipt['evidence_files']), 'files; no independent approval')
