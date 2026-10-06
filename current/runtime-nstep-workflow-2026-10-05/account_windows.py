"""Merge separately recorded free Windows jobs only after every Linux job has stopped."""
from pathlib import Path
import hashlib
import json
ROOT = Path(__file__).resolve().parents[2]
ART = ROOT / 'runtime_trace/regular_nstep/artifacts'
ledger_path = ART / 'budget.json'
def load(p): return json.loads(p.read_bytes())
assert load(ART / 'budget.running.json')['state'] == 'FINISHED', 'Linux job still active'
ledger = load(ledger_path)
bootstrap = ledger['used_seconds'] - sum(j['wall_seconds'] for j in ledger['jobs'])
seen = {j.get('receipt_path') for j in ledger['jobs']}
added = []
for directory in ('laptop-results', 'laptop-transfer'):
    for path in sorted((ART / directory).glob('*.json')):
        record = load(path)
        relative = str(path.relative_to(ROOT)).replace('\\','/')
        if record.get('schema') != 'windows-nstep-checker-job-v1' or relative in seen: continue
        job = {'path':str(path),'receipt_path':relative,'host':record['host'],
            'return_code':record['exit_code'],'verdict':record['verdict'],'wall_seconds':record['wall_seconds']}
        ledger['jobs'].append(job)
        ledger['used_seconds'] += record['wall_seconds']
        added.append(job)
assert ledger['used_seconds'] <= 3600, 'conservative cumulative ceiling exceeded'
ledger_path.write_text(json.dumps(ledger,sort_keys=True)+'\n')
assert abs(ledger['used_seconds'] - bootstrap - sum(j['wall_seconds'] for j in ledger['jobs'])) < 1e-6
audit = {'schema':'cross-host-serial-ledger-reconciliation-v1','linux_finished_before_merge':True,
    'separate_windows_receipt_count':sum(bool(j.get('receipt_path')) for j in ledger['jobs']),
    'windows_guard_wall_seconds':sum(j['wall_seconds'] for j in ledger['jobs'] if j.get('receipt_path')),
    'bootstrap_extra_wall_seconds':bootstrap,'total_charged_wall_seconds':ledger['used_seconds'],
    'newly_added':added,'job_count':len(ledger['jobs'])}
out = ART / 'resource-accounting-final.json'
out.write_text(json.dumps(audit,sort_keys=True,indent=2)+'\n')
print(json.dumps(audit,sort_keys=True))
