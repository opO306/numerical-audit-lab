"""Preserve the successful unchanged legacy relocation proof outside the repo."""
from pathlib import Path
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from runtime_trace.regular_nstep.resources import reserve_writer

proof = Path('/home/otherside123/runtime-nstep-portability-proof-2026-10-05')
out = ROOT / 'runtime_trace/regular_nstep/artifacts/external-proof-receipts'
out.mkdir(exist_ok=False)
inventory = {}
for path in sorted(proof.rglob('*')):
    if path.is_file():
        with path.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        inventory[str(path.relative_to(proof))] = {'bytes': path.stat().st_size, 'sha256': digest}
assert inventory and sum(x['bytes'] for x in inventory.values()) <= 1073741824
receipts = list(proof.rglob('public-checker-receipt.json'))
assert len(receipts) == 1
receipt = json.loads(receipts[0].read_bytes())
assert receipt['exit_code'] == 0
report = json.loads(receipt['stdout'])
assert report['verdict'] == 'CHECKER_PASS' and report['test_trust_mode'] is False
audit = receipts[0].parent / 'audit.jsonl'
assert audit.is_file()
events = [json.loads(line) for line in audit.read_text().splitlines()]
assert not any(x['event'].startswith('DENIED') for x in events)
def save(name, data):
    reserve_writer(len(data))
    with (out / name).open('xb') as stream:
        stream.write(data)
save('public-checker-receipt.json', receipts[0].read_bytes())
save('audit.jsonl', audit.read_bytes())
save('external-storage-inventory.json', (json.dumps({
    'schema': 'external-unchanged-portability-proof-inventory-v1',
    'host': 'desktop WSL Ubuntu-24.04', 'root': str(proof),
    'retained': True, 'pre_job_reserved_ceiling_bytes': 1073741824,
    'actual_file_bytes': sum(x['bytes'] for x in inventory.values()),
    'file_count': len(inventory), 'files': inventory,
    'unchanged_public_checker': report, 'audit_denied_event_count': 0,
}, sort_keys=True, indent=2) + '\n').encode())
print(json.dumps({'verdict': 'UNCHANGED_RELOCATED_CHECKER_PASS',
    'retained_file_bytes': sum(x['bytes'] for x in inventory.values()), 'files': len(inventory)}))
