"""Cross-check current author evidence and seal a receipt without approval."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'current/c1b1-qdiv-sign-fix-2026-10-05'
SOURCE = ROOT / 'independent_checker/c1b1/impulse'
TARGET = '6a63798adbae7c119439683b356f19ff414ac239'
PARENT = 'd5475e23358cbf7f88018abfb67a8bfd192c5410'
W = 2605253326086889986
W2 = 2605253326092204528
RAW = ['52119986341579705480988', '31271991804947823288593',
       '-20847994536631882192395']


def read(name):
    return json.loads((OUT / name).read_text(encoding='utf8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


def bundle(files):
    return hashlib.sha256((json.dumps(files, sort_keys=True, separators=(',', ':'),
                                    ensure_ascii=True) + '\n').encode('ascii')).hexdigest()


def xml_summary(path):
    cases = list(ET.parse(path).iter('testcase'))
    return dict(tests=len(cases), failures=sum(c.find('failure') is not None for c in cases),
                errors=sum(c.find('error') is not None for c in cases),
                skipped=sum(c.find('skipped') is not None for c in cases))


assert not (OUT / 'receipt.json').exists(), 'refusing to overwrite receipt'
assert git('rev-parse', 'HEAD').decode().strip() == TARGET
assert git('rev-parse', 'HEAD^').decode().strip() == PARENT
base = read('baseline.json')
assert base['target'] == TARGET and base['parent'] == PARENT
old = base['tracked_raw_sha256']
changed = [p for p, digest in old.items() if (ROOT / p).exists() and sha(ROOT / p) != digest]
missing = [p for p in old if not (ROOT / p).exists()]
assert changed == ['independent_checker/c1b1/impulse/resource.py',
                   'tests/test_impulse_round_add_accounting.py']
assert not missing and len(old) == 2570
preservation = read('preservation.json')
assert preservation['changed'] == changed and preservation['missing'] == missing
assert preservation['unchanged'] == 2568 and preservation['historical_count'] == 718
history = [p for p in old if p.startswith(('specs/', 'docs/', 'audit/', 'current/'))]
assert len(history) == 718 and all(sha(ROOT / p) == old[p] for p in history)
assert preservation['historical_byte_identical'] and preservation['approved_specs_preserved']
assert preservation['rounding_preserved']
assert len(preservation['protected']) == 8
for path, identity in preservation['protected'].items():
    data = (ROOT / path).read_bytes()
    assert sha(ROOT / path) == identity['sha256'] == old[path]
    assert data == git('show', TARGET + ':' + path)
    assert data == git('show', '65d8fd29ae255529afead70289098d36b825b3b4:' + path)
    assert identity['equal_target'] and identity['equal_65d8']

source = read('source-identity.json')
live_sources = {p.name: sha(p) for p in sorted(SOURCE.glob('*.py'))}
assert len(live_sources) == 18 and live_sources == source['files']
old_sources = {name: old['independent_checker/c1b1/impulse/' + name] for name in live_sources}
assert bundle(old_sources) == '643e7658ca4ae6bd41efeacd734416d1e44335e0dc83823c169429fb9138aac9'
assert bundle(live_sources) == source['source_bundle_sha256'] == 'e4ae7a0491c94a8a56a7029d08b70d7afd0c422ce0057a9027111bc45541d507'
assert source['new_git_commit_sha'] is None
assert all(old_sources[name] == digest for name, digest in live_sources.items() if name != 'resource.py')
assert sha(OUT / 'resource-before.py') == old_sources['resource.py']
assert sha(OUT / 'resource-after.py') == live_sources['resource.py']
assert (OUT / 'resource.diff').read_bytes() == git('diff', '--', 'independent_checker/c1b1/impulse/resource.py')
received = read('received-identity.json')
assert sha(OUT / 'user-request.txt') == received['request']['sha256'] == sha(Path(received['request']['original']))
assert sha(OUT / 'canonical-input.json') == received['canonical_input_sha256'] == sha(ROOT / 'tests/fixtures/impulse_round_add/COUNTEREXAMPLE_INPUT.json')

commands = {name: read(name + '-command.json') for name in
            ('targeted', 'impulse', 'spec', 'full', 'static', 'mutants', 'diff-check')}
assert all(row['exit'] == 0 and row['source_unchanged'] for row in commands.values())
assert all(row['source_before'] == row['source_after'] == live_sources for row in commands.values())
tests = {name: xml_summary(OUT / (name + '.xml')) for name in ('targeted', 'impulse', 'spec', 'full')}
assert {name: row['tests'] for name, row in tests.items()} == dict(targeted=32, impulse=733, spec=46, full=1126)
assert all(row['failures'] == row['errors'] == row['skipped'] == 0 for row in tests.values())
red = xml_summary(OUT / 'qdiv-red.xml')
assert red == dict(tests=11, failures=6, errors=0, skipped=0)
static = read('static-spec-checks.json')
assert static['result'] == 'PASS' and static['check_count'] == len(static['checks']) == 155
assert static['runtime_activation_allowed'] is False

mutants = read('mutants/results.json')['results']
previous_mutants = json.loads((ROOT / 'current/c1b1-round-add-fix-2026-10-05/mutants/results.json').read_text())['results']
old_catalog = {row['name']: row for row in previous_mutants}
catalog = {row['name']: row for row in mutants}
assert len(old_catalog) == 17 and len(catalog) == len(mutants) == 18
assert set(catalog) == set(old_catalog) | {'QDIV-SIGN-ACCOUNTING'}
for name, row in catalog.items():
    assert row['baseline']['exit'] == 0 and row['mutant']['exit'] == 1
    assert not row['baseline']['failed'] and not row['baseline']['errors'] and not row['baseline']['skipped']
    assert row['mutant']['failed'] and not row['mutant']['errors'] and not row['mutant']['skipped']
    assert row['verdict'] == 'DETECTED'
    assert sha(OUT / 'mutants' / name / 'source-before.py') == row['source_before_sha256'] == live_sources[row['source']]
    assert sha(OUT / 'mutants' / name / 'source-mutant.py') == row['mutant_source_sha256'] != row['source_before_sha256']
    for phase in ('baseline', 'mutant'):
        x = xml_summary(OUT / 'mutants' / name / (phase + '.xml'))
        run = row[phase]
        assert x['tests'] == run['tests'] and x['failures'] == len(run['failed'])
        assert x['errors'] == len(run['errors']) == 0 and x['skipped'] == len(run['skipped']) == 0
    if name in old_catalog:
        assert row['actual_edit'] == old_catalog[name]['actual_edit']
        assert row['fixture'] == old_catalog[name]['fixture']
qdiv_mutant = catalog['QDIV-SIGN-ACCOUNTING']
assert qdiv_mutant['actual_edit'] == dict(before='numerator = self.multiply(numerator, sign)',
                                        after='numerator = numerator * sign')
assert qdiv_mutant['mutant']['tests'] == len(qdiv_mutant['mutant']['failed']) == 4

before = read('before-boundaries.json')
after = read('after-boundaries.json')
assert before['source_files'] == old_sources and after['source_files'] == live_sources
assert int(before['observed_work']) == W + 152 and int(after['observed_work']) == W2
assert before['round_add'] == after['round_add']
expected_round = [('7/4', 73, None, 'WORK', 73, 2), ('7/4', 74, None, 'WORK', 73, 2),
                  ('7/4', 75, 2, None, 75, 3), ('-5/2', 42, None, 'WORK', 42, 2),
                  ('-5/2', 44, None, 'WORK', 42, 2), ('-5/2', 45, -2, None, 45, 3)]
assert [(r['q'], r['work_max'], r['result'], r['refusal'], r['charged_work'], r['operations'])
        for r in after['round_add']] == expected_round
for row in after['qdiv']:
    cap = row['work_max']
    if cap in (40, 43):
        assert (row['result'], row['refusal'], row['charged_work'], row['operations']) == (None, 'WORK', 12, 3)
    else:
        assert cap == 44 and (row['result'], row['refusal'], row['charged_work'], row['operations']) == (row['b'], None, 44, 4)
assert len(after['qdiv']) == 6
assert after['mathematics_before_after_equal'] == dict(raw=True, J_enclosure=True, V_and_derivative=True)
assert before['mathematical_diagnostics'] == after['mathematical_diagnostics']
high_before, high_after = before['sufficient_cap_result'], after['sufficient_cap_result']
assert high_before['input_sha256'] == high_after['input_sha256']
assert high_before['scaled_intervals'] == high_after['scaled_intervals']
assert high_before['raw'] == high_after['raw'] == RAW
assert high_after['account']['mathematical_work'] == W2 and high_after['account']['operations'] == 36826
assert int(after['additional_qdiv_account_work']) == W2 - W - 152 == 5314390
whole = {int(row['cap']): row for row in after['whole_call']}
assert set(whole) == {W, W + 152, W2 - 1, W2}
for cap, row in whole.items():
    assert row['input_unchanged'] and row['layers']['producer'] == 'RESOLVED'
    assert row['layers']['publication'] == 'NOT_PUBLISHED' and row['layers']['execution'] == 'STOP'
    if cap != W2:
        assert row['raw'] is row['opposite'] is row['certificate'] is row['account'] is None
        assert (row['failure']['phase'], row['failure']['reason'], row['failure']['resource_kind']) == ('PUBLICATION', 'RESOURCE_CAP', 'WORK')
    else:
        assert row['failure'] is None and row['raw'] == RAW
        assert row['opposite'] is not None and row['certificate'] is not None
        assert row['account']['mathematical_work'] == W2 and row['account']['operations'] == 36826
observed = read('W2.json')
assert int(observed['W2']) == W2 and observed['operations'] == 36826 and observed['mathematical_raw'] == RAW

review = read('resource-accounting-review.json')
assert review['source_unchanged'] and review['source_files'] == live_sources
finite = ROOT / 'specs/c1b1-independent-impulse-v1-attempt-reason-null/finite-policy.json'
assert review['finite_policy_sha256'] == sha(finite)
assert review['declared_schedule'] == json.loads(finite.read_text())['work_accounting']
assert len(review['closure_table']) == 6 and len(review['wrapper_routes']) == 86
assert len(review['direct_operation_inventory']) == 597
assert sum(review['direct_operation_categories'].values()) == 597
assert review['actual_precharge_count'] == len(review['actual_precharges']) == 36826
assert sum(row['declared_work'] for row in review['actual_precharges']) == int(review['measured_W2']) == W2
assert all(row['declared_work'] == row['charged_work'] == row['work_after'] - row['work_before']
           for row in review['actual_precharges'])
assert review['actual_sign_charge_count'] == len(review['actual_sign_charges']) == 1590
assert sum(row['declared_work'] for row in review['actual_sign_charges']) == int(review['sign_charge_work_delta']) == 5314390
assert all(row['declared_work'] == row['charged_work'] == row['work_after'] - row['work_before']
           for row in review['actual_sign_charges'])
assert high_after['account']['operations'] - high_before['account']['operations'] == 1590
assert review['first_sqrt_entry'] == [dict(work_before=0, operations_before=0, r2_numerator='38', r2_denominator='1')]
assert {r['id'] for r in review['remaining_open']} == {'O-R2-TRUTH-PATH', 'O-CONTROL-PARAMETERS',
                                                      'O-DIRECT-FRACTION-CONSTRUCTION', 'O-ALLOCATION-AND-WORKER'}
assert review['global_resource_accounting_pass'] is False and review['runtime_activation_allowed'] is False

report = ROOT / 'docs/C1B1_IMPULSE_QDIV_SIGN_FIX_REPORT_2026-10-05.md'
documents = [report, OUT / 'RESOURCE_ACCOUNTING_CLOSURE_KO.md', OUT / 'STATUS_KO.md']
for path in documents:
    for target in re.findall(r'\]\(([^)]+)\)', path.read_text(encoding='utf8')):
        resolved = (path.parent / target).resolve()
        assert resolved.exists() or resolved == OUT / 'receipt.json', target
assert not git('diff', '--check')
receipt = dict(
    schema='C1B1_QDIV_SIGN_FIX_AUTHOR_RECEIPT_V1', recorded_at_utc=datetime.now(timezone.utc).isoformat(),
    target=TARGET, parent=PARENT, historical_d547_independent_implementation_audit='FAIL',
    historical_6a=dict(round_add='FIX CANDIDATE', qdiv_sign='OPEN / NOT FIXED'),
    findings={name: 'FIX APPLIED / AUTHOR REGRESSION PASS / INDEPENDENT LIMITED REAUDIT PENDING'
              for name in ('F-RESOURCE-ROUND-ADD', 'F-RESOURCE-QDIV-SIGN')},
    resource_accounting_closure_author_review='COMPLETE', overall_resource_accounting='NOT PASS',
    remaining_open=review['remaining_open'], global_resource_accounting_verified=False,
    reference_producer_implementation='NOT YET INDEPENDENTLY APPROVED',
    runtime_activation_allowed=False, J_status='J_NOT_VERIFIED', certification='NotCertified',
    adapter='PREPARED_ONLY / INVOKE BLOCKED / INDEPENDENT SCHEDULE RECONSTRUCTION OPEN',
    V2_numerical_recheck='NOT APPROVED', candidate_source_bundle_sha256=source['source_bundle_sha256'],
    historical_source_bundle_sha256=bundle(old_sources), new_git_commit_sha=None,
    W2=str(W2), W2_scope='CURRENT AUTHOR WRAPPER LEDGER; NOT GLOBAL FULLY-ACCOUNTED OR PRODUCTION BUDGET',
    tests=tests, red_before_fix=red, mathematics_before_after_equal=after['mathematics_before_after_equal'],
    source_mutants=dict(existing=17, new=1, baselines_pass=18, semantic_detected=18,
                        hash_only_detections=0, errors=0, skipped=0),
    static_spec_checks=155, preservation=preservation, source_report_sha256=sha(report),
    commit_performed=False, push_performed=False, python=sys.version,
    commands={k: dict(command=v['command'], exit=v['exit'], elapsed_seconds=v['elapsed_seconds'])
              for k, v in commands.items()},
    git_status=git('status', '--short').decode('utf8'),
    scope='AUTHOR EVIDENCE ONLY; COUNTS OVERLAP AND ARE NOT INDEPENDENT PROOF COUNTS')
files = {p for p in OUT.rglob('*') if p.is_file() and p.name != 'receipt.json'}
files.update((ROOT / 'audit/c1b1-qdiv-sign-fix-2026-10-05').glob('*.py'))
files.update([report, ROOT / 'tests/test_impulse_qdiv_sign_accounting.py',
              ROOT / 'tests/test_impulse_round_add_accounting.py', SOURCE / 'resource.py', SOURCE / 'rounding.py'])
receipt['evidence_files'] = {p.relative_to(ROOT).as_posix(): dict(sha256=sha(p), bytes=p.stat().st_size)
                             for p in sorted(files)}
(OUT / 'receipt.json').write_text(json.dumps(receipt, indent=2, ensure_ascii=True) + '\n', encoding='ascii')
print('AUTHOR RECEIPT VERIFIED', len(receipt['evidence_files']), 'files; global accounting NOT PASS; independent approval pending')
