"""Fresh read-only source/evidence/result gates; no numerical run or evaluator."""
from collections import Counter
from pathlib import Path
import hashlib
import json
import stat
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
ART = ROOT / 'runtime_trace/regular_nstep/artifacts'
OUT = ROOT / 'current/runtime-nstep-delivery-2026-10-05-final'
OUT.mkdir(exist_ok=False)
def load(path): return json.loads(path.read_bytes())
def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

pin = load(ART / 'connected10-final2/integration_source_pinset.json')
assert pin == load(ART / 'connected100-final/integration_source_pinset.json')
actual = {str(p.relative_to(ROOT)).replace('\\', '/'): sha(p)
    for p in (ROOT/'runtime_trace').rglob('*.py') if 'artifacts' not in p.parts}
for path in ('lab/v2_bound.py', 'independent_checker/oracle.py'):
    actual[path] = sha(ROOT / path)
assert actual == pin
prior_path = ROOT / 'current/runtime-nstep-delivery-2026-10-05-03/inventory.json'
prior = load(prior_path)
assert not any(x['changed_or_missing'] for x in prior['preservation'])

def cases(path):
    result = {}
    for case in ET.parse(path).findall('.//testcase'):
        key = (case.attrib['classname'], case.attrib['name'])
        assert key not in result
        result[key] = {'failure':case.find('failure') is not None,
            'error':case.find('error') is not None, 'skip':case.find('skipped') is not None}
    return result
initial = cases(ART/'integration-regression-junit.xml')
retry = cases(ART/'portability-retry02-junit.xml')
assert len(initial) == 211 and len(retry) == 1
assert set(retry) <= set(initial)
assert sum(v['failure'] for v in initial.values()) == 1
latest = {**initial, **retry}
assert not any(any(v.values()) for v in latest.values())

attack = load(ART/'attack-supplements02/final_attack_report.json')
assert attack['verdict'] == 'TARGETED_ATTACK_SUITE_PASS'
assert Counter(x['category'] for x in attack['attacks']) == {
    'SEMANTIC':22, 'HASH_CONTROL':1, 'TRUST_CONTROL':1}
for item in attack['attacks']:
    result = item['report']
    assert result['verdict'] == 'REFUSED' and result['requested_complete'] is False
    if item['category'] == 'SEMANTIC':
        assert item['outer_hashes_repaired'] is True and result['failure_stage'] != 'HASH'

review = ROOT/'current/runtime-nstep-audit-2026-10-05/fresh-review-final.md'
assert review.is_file(), 'fresh review receipt required'
selected = [prior_path, review, ROOT/'current/RUNTIME_NSTEP_INTEGRATED_CANDIDATE_2026-10-05.md',
    ROOT/'runtime_trace/regular_nstep/README.md',
    ART/'attack-supplements02/final_attack_report.json',
    ART/'integration-regression-junit.xml', ART/'portability-retry02-junit.xml',
    ART/'external-proof-receipts/external-storage-inventory.json',
    ART/'external-proof-receipts/public-checker-receipt.json', ART/'external-proof-receipts/audit.jsonl']
for n, name, laptop in [(10,'connected10-final2','audit10-final-v2'),(100,'connected100-final','audit100-final')]:
    run = ART/name
    result = load(run/'run_result.json')
    fresh = load(run/'fresh_checker_report.json')
    assert result['verdict'] == fresh['verdict'] == 'CHECKER_PASS'
    assert result['requested_steps'] == result['checked_steps'] == n
    assert result['requested_complete'] is fresh['requested_complete'] is True
    original = load(ART/f'original-baselines/output{n}/harness_output.json')
    captured = load(run/'capture/harness_output.json')
    assert original['output_bits'] == captured['output_bits']
    for relative, record in prior['evidence_files'].items():
        if relative.startswith('runtime_trace/regular_nstep/artifacts/'+name+'/'):
            path = ROOT/relative
            assert path.stat().st_size == record['bytes'] and sha(path) == record['sha256']
            selected.append(path)
    replay = load(ART/f'laptop-results/{laptop}-result.json')
    job = load(ART/f'laptop-results/{laptop}-job.json')
    assert replay['verdict'] == 'INDEPENDENT_NUMERICAL_REPLAY_PASS'
    assert replay['checked_steps'] == n and replay['requested_steps'] == n
    assert job['verdict'] == 'EXECUTED' and not job['resource_failure']
    assert replay['script_sha256'] == sha(ROOT/'current/runtime-nstep-audit-2026-10-05/laptop_independent.py')
    for self_attack in replay['self_attacks']:
        assert self_attack['verdict'] == 'REFUSED' and self_attack['hashes_used_by_semantic_attack'] is False
    package_name = 'package10-final2' if n == 10 else 'package100-final'
    assert replay['package_sha256'] == sha(ART/f'laptop-transfer/{package_name}.zip')
    selected.extend([ART/f'laptop-results/{laptop}-result.json', ART/f'laptop-results/{laptop}-job.json',
        ART/f'original-baselines/output{n}/harness_output.json', ART/f'original-baselines/job{n}/execution.json'])
for directory in ('current/runtime-nstep-audit-2026-10-05', 'current/runtime-nstep-workflow-2026-10-05'):
    selected.extend(p for p in (ROOT/directory).glob('*') if p.is_file())
selected.extend(ROOT/p for p in pin)
selected.extend((ROOT/'tests').glob('test_regular_nstep_*.py'))
selected.extend([ROOT/'docs/superpowers/plans/2026-10-05-regular-nstep-runtime-trace.md',
    ROOT/'docs/superpowers/specs/2026-10-05-regular-nstep-runtime-trace.md'])
manifest = {str(path.relative_to(ROOT)).replace('\\', '/'):
    {'bytes':path.stat().st_size, 'sha256':sha(path)} for path in sorted(set(selected))}
result = {'schema':'regular-nstep-delivery-verification-v1','verdict':'DELIVERY_VERIFICATION_PASS',
    'same_current_core_files':len(pin),'integration_source_pinset_sha256':sha(ART/'connected10-final2/integration_source_pinset.json'),
    'latest_distinct_tests':len(latest),'latest_failure_error_skip_count':0,
    'single_full_suite_green':False,'first_full_suite_pass':210,'first_full_suite_failure':1,
    'unchanged_failed_test_retry_pass':1,'semantic_attacks':22,'separate_controls':2,
    'source_or_numerical_implementation_changed_after_final10_100':False,
    'fresh_review_sha256':sha(review),'prior_preservation_inventory_sha256':sha(prior_path),
    'files':manifest,'external_audit_closure':False,'formal_certification':False,
    'budget_snapshot_before_this_metadata_job':load(ART/'budget.json'),
    'post_job_accounting':'Final job receipt is merged only after child exit; mutable ledger excluded from immutable file manifest.'}
(OUT/'verification.json').write_text(json.dumps(result, sort_keys=True, indent=2)+'\n', encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k not in ('files','budget_snapshot_before_this_metadata_job')}))
