"""Verify R2 author evidence coherence and seal a review receipt."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'current/c1b1-r2-precharge-fix-2026-10-05'
RECEIVED = ROOT / 'current/c1b1-qdiv-limited-reaudit-received-2026-10-05'
SOURCE = ROOT / 'independent_checker/c1b1/impulse'
TARGET = 'baba8ea942b896af64ceaa7ab41e2bc5db73112c'
PARENT = '6a63798adbae7c119439683b356f19ff414ac239'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(name):
    return json.loads((OUT / name).read_text(encoding='utf8'))


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


def bundle(files):
    return hashlib.sha256((json.dumps(files, sort_keys=True, separators=(',', ':'), ensure_ascii=True) + '\n').encode('ascii')).hexdigest()


def xml(path):
    cases = list(ET.parse(path).iter('testcase'))
    return dict(tests=len(cases), failures=sum(c.find('failure') is not None for c in cases),
                errors=sum(c.find('error') is not None for c in cases),
                skipped=sum(c.find('skipped') is not None for c in cases))


assert not (OUT / 'receipt.json').exists(), 'refusing overwrite'
assert git('rev-parse', 'HEAD').decode().strip() == TARGET
assert git('rev-parse', 'HEAD^').decode().strip() == PARENT
base = read('baseline.json')
assert base['target'] == TARGET and base['parent'] == PARENT
old = base['tracked_raw_sha256']
changed = [p for p, digest in old.items() if (ROOT / p).is_file() and sha(ROOT / p) != digest]
missing = [p for p in old if not (ROOT / p).is_file()]
assert len(old) == 2734 and not missing
assert changed == ['independent_checker/c1b1/impulse/producer.py', 'tests/test_impulse_round_add_accounting.py']
history = [p for p in old if p.startswith(('specs/', 'docs/', 'audit/', 'current/'))]
assert len(history) == 881 and all(sha(ROOT / p) == old[p] for p in history)
preserved = read('preservation.json')
assert preserved['changed'] == changed and preserved['missing'] == missing
assert preserved['unchanged'] == 2732 and preserved['historical_count'] == 881
assert preserved['resource_py_preserved'] and preserved['rounding_py_preserved'] and preserved['approved_specs_preserved']
source = read('source-identity.json')
live = {p.name: sha(p) for p in sorted(SOURCE.glob('*.py'))}
assert len(live) == 18 and live == source['files']
assert bundle(live) == source['source_bundle_sha256'] == '4bd5cb0ef00c022689aa1a1dd4354deba08961ab4e1887b38d2f62f287a8cced'
assert bundle(base['source_files']) == 'e4ae7a0491c94a8a56a7029d08b70d7afd0c422ce0057a9027111bc45541d507'
assert all(base['source_files'][p] == digest for p, digest in live.items() if p != 'producer.py')
assert source['new_git_commit_sha'] is None
assert sha(OUT / 'producer-before.py') == base['source_files']['producer.py']
assert sha(OUT / 'producer-after.py') == live['producer.py']
assert (OUT / 'producer.diff').read_bytes() == git('diff', '--', 'independent_checker/c1b1/impulse/producer.py')
assert sha(OUT / 'canonical-input.json') == sha(ROOT / 'tests/fixtures/impulse_round_add/COUNTEREXAMPLE_INPUT.json')
received = json.loads((RECEIVED / 'received-identity.json').read_text())
binding = read('received-audit-binding.json')
assert sha(RECEIVED / 'received-identity.json') == binding['sha256']
assert received['target'] == TARGET and received['source_bundle_sha256'] == bundle(base['source_files'])
for name, identity in received['received_files'].items():
    assert sha(RECEIVED / 'received' / name) == identity['sha256'] == sha(Path(identity['original']))
protected = {}
for path, digest in received['protected_arithmetic_8'].items():
    data = (ROOT / path).read_bytes()
    assert sha(ROOT / path) == digest
    assert data == git('show', TARGET + ':' + path) == git('show', PARENT + ':' + path)
    assert data == git('show', '65d8fd29ae255529afead70289098d36b825b3b4:' + path)
    protected[path] = digest
assert len(protected) == 8
previous_path = ROOT / 'current/c1b1-qdiv-sign-fix-2026-10-05/receipt.json'
previous = json.loads(previous_path.read_text())
assert sha(previous_path) == received['previous_receipt_verified']['sha256']
for path, identity in previous['evidence_files'].items():
    evidence = ROOT / path
    if path == 'tests/test_impulse_round_add_accounting.py':
        # This active regression is intentionally changed by the authorized R2 fix.
        # Preserve its historical bytes via the exact target Git blob, not by
        # rewriting either the old receipt or the current active test.
        evidence = OUT / 'round-add-test-target.py'
        assert sha(evidence) == old[path]
        assert evidence.read_bytes() == git('show', TARGET + ':' + path)
    assert sha(evidence) == identity['sha256'] and evidence.stat().st_size == identity['bytes']
assert len(previous['evidence_files']) == 166

commands = {name: read(name+'-command.json') for name in ('targeted', 'impulse', 'spec', 'full', 'static', 'mutants', 'diff-check')}
assert all(c['exit'] == 0 and c['source_unchanged'] and c['source_before'] == c['source_after'] == live for c in commands.values())
tests = {name: xml(OUT / (name+'.xml')) for name in ('targeted', 'impulse', 'spec', 'full')}
assert {name: x['tests'] for name, x in tests.items()} == dict(targeted=42, impulse=743, spec=46, full=1136)
assert all(x['failures'] == x['errors'] == x['skipped'] == 0 for x in tests.values())
red = {name: xml(OUT / (name+'.xml')) for name in ('r2-red', 'r2-preoperation-red')}
assert all(x == dict(tests=8, failures=8, errors=0, skipped=0) for x in red.values())
green = xml(OUT / 'r2-first-green.xml')
assert green == dict(tests=8, failures=0, errors=0, skipped=0)
static = read('static-spec-checks.json')
assert static['result'] == 'PASS' and static['check_count'] == len(static['checks']) == 155

old_mutants = json.loads((ROOT / 'current/c1b1-qdiv-sign-fix-2026-10-05/mutants/results.json').read_text())['results']
old_catalog = {x['name']: x for x in old_mutants}
mutants = read('mutants/results.json')['results']
catalog = {x['name']: x for x in mutants}
assert len(catalog) == len(mutants) == 19
assert set(catalog) == set(old_catalog) | {'R2-PRECHARGE-ACCOUNTING'}
for name, row in catalog.items():
    assert row['baseline']['exit'] == 0 and row['mutant']['exit'] == 1 and row['verdict'] == 'DETECTED'
    assert not row['baseline']['failed'] and row['mutant']['failed']
    for phase in ('baseline', 'mutant'):
        run = row[phase]
        actual = xml(OUT / 'mutants' / name / (phase+'.xml'))
        assert actual['tests'] == run['tests'] and actual['failures'] == len(run['failed'])
        assert actual['errors'] == len(run['errors']) == 0 and actual['skipped'] == len(run['skipped']) == 0
    assert sha(OUT / 'mutants' / name / 'source-before.py') == row['source_before_sha256'] == live[row['source']]
    assert sha(OUT / 'mutants' / name / 'source-mutant.py') == row['mutant_source_sha256'] != row['source_before_sha256']
    if name in old_catalog:
        assert row['actual_edit'] == old_catalog[name]['actual_edit'] and row['fixture'] == old_catalog[name]['fixture']
assert len(catalog['R2-PRECHARGE-ACCOUNTING']['mutant']['failed']) == 5

before, after = read('before-boundaries.json'), read('after-boundaries.json')
assert before['source_files'] == base['source_files'] and after['source_files'] == live
assert all(all(x.values()) for x in after['mathematics_before_after_equal'].values())
for old_case, new_case in zip(before['cases'], after['cases']):
    assert old_case['input_sha256'] == new_case['input_sha256'] and new_case['domain_admitted'] and new_case['input_unchanged']
    assert old_case['diagnostics'] == new_case['diagnostics']
    assert old_case['result']['J'] == new_case['result']['J'] and old_case['result']['raw'] == new_case['result']['raw']
    assert old_case['R2_entry']['r2'] == new_case['R2_entry']['r2']
    assert new_case['R2_entry']['work'] == int(new_case['expected_R2_work'])
    assert new_case['R2_entry']['operations'] == len(new_case['expected_abstract_schedule'])
w3 = read('W3.json')
assert int(w3['W3']) == int(after['observed_work']) == 2605253326092221245
assert int(w3['previous_W2']) == int(before['observed_work']) == 2605253326092204528
assert int(w3['observed_R2_work_delta']) == int(w3['W3'])-int(w3['previous_W2']) == 16717
assert w3['operations'] == 36851 and w3['R2_operations'] == 25
for row in after['low_cap_R2']:
    result, events = row['result'], row['actual_R2_trace']
    assert not any(e['event'] in ('_mul', '_add', 'sqrt_entry') for e in events)
    products = [e for e in events if e['event'] == 'integer_product']
    assert products == ([] if row['cap'] != 48 else [dict(event='integer_product', a=5, b=5, ledger=48, operations=2)])
    assert result['raw'] is result['opposite'] is result['certificate'] is result['account'] is None
    assert (result['failure']['phase'], result['failure']['reason'], result['failure']['resource_kind']) == ('COMPUTE', 'RESOURCE_CAP', 'WORK')
for row in after['whole_call']:
    result = row['result']
    assert result['layers']['producer'] == 'RESOLVED'
    assert result['layers']['publication'] == 'NOT_PUBLISHED' and result['layers']['execution'] == 'STOP'
    if int(row['cap']) != int(w3['W3']):
        assert result['raw'] is result['opposite'] is result['certificate'] is result['account'] is None
        assert (result['failure']['phase'], result['failure']['reason'], result['failure']['resource_kind']) == ('PUBLICATION', 'RESOURCE_CAP', 'WORK')
    else:
        assert result['failure'] is None and result['raw'] == w3['raw'] and result['certificate'] is not None
assert after['public_result']['failure']['reason'] == 'POLICY_UNBOUND'
replay = read('actual-work-reconstruction.json')
assert replay['source_files'] == live and replay['source_unchanged']
assert replay['W3'] == w3['W3'] and replay['primitive_operations'] == len(replay['actual_precharges']) == w3['operations']
assert sum(x['recomputed_work'] for x in replay['actual_precharges']) == int(w3['W3'])
assert all(x['declared_work'] == x['recomputed_work'] == x['work_after']-x['work_before'] for x in replay['actual_precharges'])
assert len(replay['actual_R2_precharges']) == replay['R2_entry']['operations'] == w3['R2_operations']
assert sum(x['recomputed_work'] for x in replay['actual_R2_precharges']) == replay['R2_entry']['work'] == int(w3['observed_R2_work_delta'])
assert replay['global_resource_accounting_pass'] is False and replay['runtime_activation_allowed'] is False

report = ROOT / 'docs/C1B1_IMPULSE_R2_PRECHARGE_FIX_REPORT_2026-10-05.md'
status = ROOT / 'current/C1B1_IMPULSE_RESOURCE_ACCOUNTING_STATUS_2026-10-05.md'
for path in [report, status, OUT / 'RESOURCE_ACCOUNTING_UPDATE_KO.md', OUT / 'AUTHORIZED_SCOPE_KO.md']:
    text = path.read_text(encoding='utf8')
    assert not re.search('[\u3040-\u30ff]', text), 'unintended Japanese text in Korean report'
    for target in re.findall(r'\]\(([^)]+)\)', text):
        resolved = (path.parent / target).resolve()
        assert resolved.exists() or resolved == OUT / 'receipt.json', (path, target)
assert not git('diff', '--check')
receipt = dict(
    schema='C1B1_R2_PRECHARGE_FIX_AUTHOR_RECEIPT_V1', recorded_at_utc=datetime.now(timezone.utc).isoformat(),
    target=TARGET, parent=PARENT, new_git_commit_sha=None, commit_performed=False, push_performed=False,
    candidate_source_bundle_sha256=source['source_bundle_sha256'], historical_baba_source_bundle_sha256=bundle(base['source_files']),
    received_limited_reaudit=dict(target=TARGET, source_bundle_sha256=bundle(base['source_files']),
                                  ROUND_ADD='PASS', QDIV_SIGN='PASS', R2_PRECHARGE='CONFIRMED FAIL AT AUDIT TIME'),
    R2_candidate='FIX APPLIED / AUTHOR REGRESSION PASS / INDEPENDENT REAUDIT PENDING',
    historical_d547='INDEPENDENT IMPLEMENTATION AUDIT FAIL', historical_6a='ROUND-ADD FIX CANDIDATE / QDIV OPEN AT THAT TIME',
    overall_resource_accounting='NOT PASS', remaining_open=replay['remaining_open'], global_resource_accounting_verified=False,
    reference_producer_implementation='NOT YET INDEPENDENTLY APPROVED', runtime_activation_allowed=False,
    J_status='J_NOT_VERIFIED', certification='NotCertified', adapter='PREPARED_ONLY / invoke blocked / independent reconstruction OPEN',
    V2_numerical_recheck='NOT APPROVED', W3=w3, mathematics_before_after_equal=after['mathematics_before_after_equal'],
    tests=tests, red_before_fix=red, initial_green=green, static_spec_checks=155,
    semantic_mutants=dict(existing=18, new=1, baselines_pass=19, semantic_detected=19, hash_only_detections=0, errors=0, skipped=0),
    preservation=preserved, protected_arithmetic_8=protected,
    previous_receipt_verification=dict(total=166, unchanged_current_files=165,
        authorized_active_test='tests/test_impulse_round_add_accounting.py',
        historical_test_evidence='round-add-test-target.py / exact target Git bytes equal prior receipt and recorded working baseline'),
    source_report_sha256=sha(report), python=sys.version,
    commands={name: dict(command=row['command'], exit=row['exit'], elapsed_seconds=row['elapsed_seconds']) for name, row in commands.items()},
    git_status=git('status', '--short').decode('utf8'), scope='AUTHOR EVIDENCE ONLY; COUNTS OVERLAP AND ARE NOT INDEPENDENT PROOF COUNTS')
files = {p for p in OUT.rglob('*') if p.is_file() and p.name != 'receipt.json'}
files.update(p for p in RECEIVED.rglob('*') if p.is_file())
files.update((ROOT / 'audit/c1b1-r2-precharge-fix-2026-10-05').glob('*.py'))
files.update((ROOT / 'audit/c1b1-qdiv-limited-reaudit-received-2026-10-05').glob('*.py'))
files.update([report, status, ROOT / 'tests/test_impulse_r2_precharge.py',
              ROOT / 'tests/test_impulse_round_add_accounting.py', SOURCE / 'producer.py', SOURCE / 'resource.py', SOURCE / 'rounding.py'])
receipt['evidence_files'] = {p.relative_to(ROOT).as_posix(): dict(sha256=sha(p), bytes=p.stat().st_size) for p in sorted(files)}
(OUT / 'receipt.json').write_text(json.dumps(receipt, indent=2, ensure_ascii=True)+'\n', encoding='ascii')
print('AUTHOR RECEIPT VERIFIED', len(receipt['evidence_files']), 'files; R2 independent reaudit PENDING; global accounting NOT PASS')
