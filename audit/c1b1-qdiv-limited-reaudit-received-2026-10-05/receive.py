"""Receive supplied limited reaudit; author provenance checks, no code fix."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'current/c1b1-qdiv-limited-reaudit-received-2026-10-05'
INCOMING = Path('D:/감사/REPORT_KO(8)')
TARGET = 'baba8ea942b896af64ceaa7ab41e2bc5db73112c'
PARENT = '6a63798adbae7c119439683b356f19ff414ac239'
BUNDLE = 'e4ae7a0491c94a8a56a7029d08b70d7afd0c422ce0057a9027111bc45541d507'
FILES = ('AUDIT_REPORT_KO.md', 'NEXT_STEP_KO.md', 'core_results.pretty.json',
         'provenance_results.pretty.json')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def git(*args, input=None):
    return subprocess.check_output(['git', *args], cwd=ROOT, input=input)


def tree(ref):
    rows = git('ls-tree', '-rz', ref).split(b'\0')[:-1]
    return {row.split(b'\t', 1)[1].decode('utf8'): row.split(b'\t', 1)[0].split()[2].decode('ascii')
            for row in rows}


assert git('rev-parse', 'HEAD').decode().strip() == TARGET
assert git('rev-parse', 'HEAD^').decode().strip() == PARENT
assert not git('diff', '--name-only') and not git('diff', '--cached', '--name-only')
source = ROOT / 'independent_checker/c1b1/impulse'
sources = {p.name: digest(p.read_bytes()) for p in sorted(source.glob('*.py'))}
assert len(sources) == 18
bundle = digest((json.dumps(sources, sort_keys=True, separators=(',', ':'), ensure_ascii=True) + '\n').encode('ascii'))
assert bundle == BUNDLE
core = json.loads((INCOMING / 'core_results.pretty.json').read_text(encoding='utf8'))
provenance = json.loads((INCOMING / 'provenance_results.pretty.json').read_text(encoding='utf8'))
for identity in (core['identity_before'], core['identity_after']):
    assert identity == dict(bundle=BUNDLE, head=TARGET, status='')
assert provenance['head'] == TARGET and provenance['status_after'] == ''
assert provenance['source_identity']['files'] == sources
assert core['verdict']['ROUND_ADD'] == core['verdict']['QDIV_SIGN'] == 'PASS'
assert core['verdict']['R2_PRECHARGE'] == 'FAIL'
assert core['verdict']['GLOBAL_ACCOUNTING'] == 'NOT PASS'
assert core['verdict']['runtime_activation_allowed'] is False
assert core['primitive_replay']['derived_work'] == '2605253326092204528'
assert core['r2_bypass']['trace'][-1] == dict(cap=1, event='sqrt_entry', operations=0, r2='38', work=0)
previous = ROOT / 'current/c1b1-qdiv-sign-fix-2026-10-05/receipt.json'
receipt = json.loads(previous.read_text(encoding='utf8'))
assert digest(previous.read_bytes()) == provenance['receipt']['sha256']
for rel, expected in receipt['evidence_files'].items():
    path = ROOT / rel
    assert path.stat().st_size == expected['bytes'] and digest(path.read_bytes()) == expected['sha256'], rel
assert len(receipt['evidence_files']) == provenance['receipt']['file_count'] == 166
old, current = tree(PARENT), tree(TARGET)
changed = [p for p in old if old[p] != current.get(p)]
assert changed == ['independent_checker/c1b1/impulse/resource.py', 'tests/test_impulse_round_add_accounting.py']
historical = [p for p in old if p.startswith(('specs/', 'docs/', 'audit/', 'current/'))]
assert len(historical) == 718 and all(old[p] == current[p] for p in historical)
protected = {}
for rel, expected in provenance['protected_arithmetic_8'].items():
    raw = (ROOT / rel).read_bytes()
    assert digest(raw) == expected
    assert raw == git('show', PARENT + ':' + rel)
    assert raw == git('show', '65d8fd29ae255529afead70289098d36b825b3b4:' + rel)
    protected[rel] = expected
paths = list(current)
blobs = git('cat-file', '--batch', input=('\n'.join(TARGET + ':' + p for p in paths) + '\n').encode('utf8'))
pos = 0
eol = []
non_eol = []
working_hashes = {}
for rel in paths:
    end = blobs.index(b'\n', pos)
    size = int(blobs[pos:end].split()[2])
    blob = blobs[end + 1:end + 1 + size]
    pos = end + size + 2
    raw = (ROOT / rel).read_bytes()
    working_hashes[rel] = digest(raw)
    if raw != blob:
        if raw.replace(b'\r\n', b'\n') == blob.replace(b'\r\n', b'\n'):
            eol.append(rel)
        else:
            non_eol.append(rel)
assert not non_eol
OUT.mkdir(exist_ok=False)
received = OUT / 'received'
received.mkdir()
identities = {}
for name in FILES:
    original = INCOMING / name
    data = original.read_bytes()
    (received / name).write_bytes(data)
    identities[name] = dict(original=str(original), sha256=digest(data), bytes=len(data))
request = Path('C:/Users/zun24/.codex/attachments/9c6c2883-8e9d-417a-a6f7-4a4afe6afbb8/붙여넣은 텍스트.txt')
(received / 'user-request.txt').write_bytes(request.read_bytes())
identities['user-request.txt'] = dict(original=str(request), sha256=digest(request.read_bytes()), bytes=request.stat().st_size)
record = dict(
    schema='C1B1_LIMITED_REAUDIT_RECEIVED_AUTHOR_PROVENANCE_V1', recorded_at_utc=datetime.now(timezone.utc).isoformat(),
    target=TARGET, parent=PARENT, source_bundle_sha256=bundle, sources=sources, received_files=identities,
    received_independent_verdict=core['verdict'], original_requested_download_paths_missing=True,
    available_package_scope='Four supplied report/pretty-JSON files and pasted request only; ZIP, probes, canonical JSON and manifest not supplied',
    source_and_git_identity_verified=True, previous_receipt_verified=dict(files=166, sha256=digest(previous.read_bytes())),
    historical_git_preservation=dict(base=PARENT, base_tracked=len(old), changed_existing=changed,
                                     unchanged=len(old)-len(changed), historical_git_objects_unchanged=718),
    protected_arithmetic_8=protected, current_working_vs_HEAD=dict(tracked=len(paths), eol_only_count=len(eol),
        eol_only_paths=eol, non_eol_changes=non_eol), baseline_working_raw_sha256=working_hashes,
    author_reexecuted_independent_probes=False, author_reexecuted_full_pytest=False,
    implementation_changed=False, R2_fix_applied=False, commit_performed=False, push_performed=False,
    runtime_activation_allowed=False, J_status='J_NOT_VERIFIED', certification='NotCertified',
    role='AUTHOR RECEIPT / PROVENANCE CHECK; RECEIVED INDEPENDENT VERDICT IS NOT A NEW AUTHOR INDEPENDENT AUDIT')
(OUT / 'received-identity.json').write_text(json.dumps(record, indent=2, ensure_ascii=True) + '\n', encoding='ascii')
print('RECEIVED', len(identities), 'exact copies; HEAD/source match; previous receipt166 verified; historical Git718 preserved')
print('WORKING VS HEAD EOL ONLY', len(eol), '; implementation unchanged; no commit/push')
