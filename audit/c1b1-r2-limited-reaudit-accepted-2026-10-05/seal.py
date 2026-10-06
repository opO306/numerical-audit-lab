"""Seal additive audit acceptance documents while preserving prior evidence."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT/'current/c1b1-r2-limited-reaudit-accepted-2026-10-05'
AUDIT = ROOT/'audit/c1b1-r2-limited-reaudit-accepted-2026-10-05'
REPORT = ROOT/'docs/C1B1_IMPULSE_R2_LIMITED_REAUDIT_ADDENDUM_2026-10-05.md'
STATUS = ROOT/'current/C1B1_IMPULSE_RESOURCE_ACCOUNTING_LATEST_2026-10-05.md'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf8'))


assert not (OUT/'receipt.json').exists(), 'refusing overwrite'
observed = read(OUT/'observed-provenance.json')
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip() == observed['target']
for rel, digest in observed['baseline_working_sha256'].items():
    assert sha(ROOT/rel) == digest, rel
sources = {p.name:sha(p) for p in sorted((ROOT/'independent_checker/c1b1/impulse').glob('*.py'))}
assert sources == observed['source_files']
old = read(ROOT/observed['author_receipt_verification']['path'])
assert sha(ROOT/observed['author_receipt_verification']['path']) == observed['author_receipt_verification']['sha256']
for rel, identity in old['evidence_files'].items():
    assert sha(ROOT/rel) == identity['sha256'] and (ROOT/rel).stat().st_size == identity['bytes'],rel
assert len(old['evidence_files']) == 185
links = []
for path in [REPORT, STATUS, OUT/'OPEN_SCOPE_CONTRACT_REGISTER_KO.md']:
    text = path.read_text(encoding='utf8')
    for target in re.findall(r'\]\(([^)]+)\)',text):
        assert (path.parent/target).resolve().exists(),(path,target)
        links.append(dict(file=path.relative_to(ROOT).as_posix(),target=target))
run = subprocess.run(['git','diff','--check'],cwd=ROOT,capture_output=True)
assert run.returncode == 0 and not run.stdout and not run.stderr
remote = subprocess.run(['git','ls-remote','--heads','origin','refs/heads/'+observed['branch']],cwd=ROOT,capture_output=True)
assert remote.returncode == 0
assert remote.stdout.decode().split() == [observed['target'],'refs/heads/'+observed['branch']]
files = {p for p in OUT.rglob('*') if p.is_file() and p.name!='receipt.json'}
files.update(AUDIT.glob('*.py'))
files.update([REPORT,STATUS])
receipt = dict(
    schema='C1B1_R2_LIMITED_REAUDIT_ACCEPTANCE_AUTHOR_RECEIPT_V1',
    recorded_at_utc=datetime.now(timezone.utc).isoformat(), target=observed['target'],parent=observed['parent'],
    source_bundle_sha256=observed['source_bundle_sha256'],
    accepted_findings=dict(ROUND_ADD='LIMITED INDEPENDENT REAUDIT PASS',QDIV_SIGN='LIMITED INDEPENDENT REAUDIT PASS',
                           R2_PRECHARGE='LIMITED INDEPENDENT REAUDIT PASS / FINDING CLOSED'),
    accepted_verdict_source='User-supplied independent audit text; not a new author numerical audit',
    historical_receipt_files_preserved=185, tracked_working_files_preserved=len(observed['baseline_working_sha256']),
    global_resource_accounting='NOT PASS',remaining_open=['O-CONTROL-PARAMETERS','O-DIRECT-FRACTION-CONSTRUCTION',
                                                         'O-ALLOCATION-AND-WORKER','ADAPTER-SCHEDULE-RECONSTRUCTION'],
    reference_producer_implementation='NOT YET INDEPENDENTLY APPROVED',runtime_activation_allowed=False,
    J_status='J_NOT_VERIFIED',certification='NotCertified',V2_numerical_recheck='NOT APPROVED',
    new_arithmetic_patch=False,new_tests_or_numeric_execution=False,commit_performed_this_turn=False,push_performed_this_turn=False,
    commit_push_actor='UNRESOLVED',authorization_path='UNRESOLVED',exact_push_time='UNRESOLVED',
    previous_author_turn_completion_kst=observed['previous_author_turn']['completed_at_kst'],
    commit_recorded_time=observed['commit_recorded_time'],timing=observed['timing'],
    final_ls_remote=dict(command=['git','ls-remote','--heads','origin','refs/heads/'+observed['branch']],
                         exit=remote.returncode,stdout=remote.stdout.decode(),stderr=remote.stderr.decode()),
    final_diff_check=dict(exit=run.returncode,stdout=run.stdout.decode(),stderr=run.stderr.decode()),
    document_links=links,git_status=subprocess.check_output(['git','status','--short'],cwd=ROOT).decode('utf8'),
    evidence_files={p.relative_to(ROOT).as_posix():dict(sha256=sha(p),bytes=p.stat().st_size) for p in sorted(files)})
(OUT/'receipt.json').write_text(json.dumps(receipt,indent=2,ensure_ascii=True)+'\n',encoding='ascii')
print('SEALED',len(files),'new evidence files;',len(observed['baseline_working_sha256']),'tracked files unchanged; old receipt185 preserved')
print('R2 limited finding CLOSED; global accounting NOT PASS; current remote target confirmed; no commit/push this turn')
