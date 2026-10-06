"""Control-plane closeout after the bounded verifier exits and clocks are merged."""
from pathlib import Path
import hashlib
import json
import stat

ROOT = Path(__file__).resolve().parents[2]
ART = ROOT/'runtime_trace/regular_nstep/artifacts'
OUT = ROOT/'current/runtime-nstep-delivery-2026-10-05-final'
def load(path): return json.loads(path.read_bytes())
def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()
def save(path, data):
    with path.open('xb') as stream: stream.write(data)

verify = load(OUT/'verification.json')
assert verify['verdict'] == 'DELIVERY_VERIFICATION_PASS'
assert load(ART/'budget.running.json')['state'] == 'FINISHED'
controller = ART/'laptop-transfer/delivery-seal-job.json'
job = load(controller)
assert job['verdict'] == 'EXECUTED' and not job['resource_failure']
ledger = load(ART/'budget.json')
account = load(ART/'resource-accounting-final.json')
assert ledger['used_seconds'] == account['total_charged_wall_seconds'] <= 3600
assert any(x.get('receipt_path') == str(controller.relative_to(ROOT)).replace('\\','/') for x in ledger['jobs'])
for source, name in [(ART/'budget.json','budget-final.json'),
    (ART/'resource-accounting-final.json','resource-accounting-final.json'),
    (controller,'delivery-seal-job.json')]:
    save(OUT/name, source.read_bytes())

def logical_files(folder):
    total, count, links = 0, 0, []
    for path in folder.rglob('*'):
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            total += info.st_size
            links.append({'path':str(path.relative_to(folder)), 'logical_payload_bytes':info.st_size})
        elif stat.S_ISREG(info.st_mode):
            total += info.st_size
            count += 1
    return {'root':str(folder),'logical_file_bytes':total,'regular_file_count':count,'unfollowed_links':links}
candidate = logical_files(ROOT)
original = Path('D:/numerical-audit-lab-recovered-2026-10-01')
preflight = logical_files(original/'current/runtime-nstep-preflight-2026-10-05')
original_docs = [original/'docs/superpowers/plans/2026-10-05-regular-nstep-runtime-trace.md',
    original/'docs/superpowers/specs/2026-10-05-regular-nstep-runtime-trace.md']
preflight['logical_file_bytes'] += sum(p.stat().st_size for p in original_docs)
preflight['regular_file_count'] += len(original_docs)
preflight['additional_original_task_docs'] = [str(p) for p in original_docs]
external = load(ART/'external-proof-receipts/external-storage-inventory.json')
laptop = load(ART/'laptop-results/storage-observation-final.json')
prior_total = candidate['logical_file_bytes'] + preflight['logical_file_bytes'] + external['actual_file_bytes'] + laptop['file_bytes']
receipt = {'schema':'regular-nstep-final-closeout-v1','verdict':'CONDITIONAL_INTEGRATED_CANDIDATE_DELIVERED',
    'verification_sha256':sha(OUT/'verification.json'),
    'final_budget_sha256':sha(OUT/'budget-final.json'),
    'final_accounting_sha256':sha(OUT/'resource-accounting-final.json'),
    'final_guard_receipt_sha256':sha(OUT/'delivery-seal-job.json'),
    'fresh_review_sha256':verify['fresh_review_sha256'],
    'total_charged_wall_seconds':ledger['used_seconds'],'job_count':len(ledger['jobs']),
    'storage_basis':'logical file payload, including the entire isolated checkout and copied old assets; links lstat only, not physical allocation',
    'candidate_checkout_before_this_receipt':candidate,'original_own_preflight':preflight,
    'external_retained_proof':{'host':'desktop WSL','root':external['root'],'file_bytes':external['actual_file_bytes'],'file_count':external['file_count']},
    'laptop_retained':laptop,'prior_total_file_bytes':prior_total,
    'this_receipt_bytes':0,'final_total_file_bytes':prior_total,
    'time_ceiling_seconds':3600,'storage_ceiling_bytes':8589934592,
    'counted_metadata_jobs':'bounded inventory and final seal jobs included; control-plane reconciliation/static writing not timed',
    'requested10_complete':True,'requested100_complete':True,
    'init_to_step1':'UNTRACED','post_terminal_frontier':'UNTRACED',
    'external_audit_closure':False,'formal_certification':False,'verified_driver_implemented':False,
    'paid_resource_started':False,'commit_or_push_performed':False}
for _ in range(20):
    data = (json.dumps(receipt,sort_keys=True,indent=2)+'\n').encode()
    if receipt['this_receipt_bytes'] == len(data): break
    receipt['this_receipt_bytes'] = len(data)
    receipt['final_total_file_bytes'] = prior_total + len(data)
else: raise ValueError('storage receipt size did not converge')
assert receipt['final_total_file_bytes'] <= receipt['storage_ceiling_bytes']
save(OUT/'closeout.json', data)
assert (OUT/'closeout.json').stat().st_size == receipt['this_receipt_bytes']
print(json.dumps({'verdict':receipt['verdict'],'total_charged_wall_seconds':ledger['used_seconds'],
    'final_total_file_bytes':receipt['final_total_file_bytes'],'jobs':len(ledger['jobs'])}))
