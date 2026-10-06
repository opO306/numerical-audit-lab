"""Check final delivery metadata without numerical execution or Git index writes."""
from pathlib import Path
import hashlib
import json
import os
import stat
import subprocess
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / 'verified_driver/v0/artifacts/review'
ORIGINAL = Path('D:/numerical-audit-lab-recovered-2026-10-01')

def git(root, *args):
    return subprocess.check_output(['git', *args], cwd=root, text=True, encoding='utf-8')

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def logical_size(root):
    total = count = 0
    aliases = []
    for base, dirs, files in os.walk(root, followlinks=False):
        keep = []
        for name in dirs:
            path = Path(base) / name
            info = path.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
                aliases.append(str(path.relative_to(root)))
            else:
                keep.append(name)
        dirs[:] = keep
        for name in files:
            path = Path(base) / name
            info = path.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
                aliases.append(str(path.relative_to(root)))
            elif stat.S_ISREG(info.st_mode):
                total += info.st_size
                count += 1
    return {'logical_bytes': total, 'files': count, 'excluded_aliases': sorted(aliases)}

summary = json.loads((ROOT / 'verified_driver/v0/artifacts/final-summary.json').read_bytes())
inventory = json.loads((OUT / 'source-inventory.json').read_bytes())
for relative, expected in inventory['new_driver_review_files'].items():
    assert digest(ROOT / relative) == expected['sha256'], relative
for group in summary['source_hashes'].values():
    for relative, expected in group.items():
        assert digest(ROOT / relative) == expected, relative
assert len(inventory['new_driver_review_files']) == 15
assert inventory['tracked_diff_bytes'] == 0
assert not inventory['tracked_status']
base = '79a655f0848152aa765e1537b741518b2fa97acf'
for root in (ROOT, ORIGINAL):
    assert git(root, 'rev-parse', 'HEAD').strip() == base
    assert not git(root, 'diff', '--no-ext-diff')
    assert not git(root, 'diff', '--cached', '--no-ext-diff')
    assert not git(root, 'status', '--porcelain', '--untracked-files=no')
    assert not git(root, 'diff', '--check')
(OUT / 'original-git-status.txt').write_text(git(ORIGINAL, 'status', '--short'), encoding='utf-8')
assert (OUT / 'git-status.txt').read_text(encoding='utf-8') == git(ROOT, 'status', '--short')
preservation = json.loads((ROOT / 'verified_driver/v0/artifacts/preservation/after-final.json').read_bytes())
assert preservation['checked_files'] == 6892
assert not preservation['changed_or_missing']
junit = ROOT / 'verified_driver/v0/artifacts/final-review-green-junit.xml'
suites = ET.parse(junit).getroot()
counts = {key: sum(int(s.attrib.get(key, 0)) for s in suites.findall('testsuite'))
          for key in ('tests', 'failures', 'errors', 'skipped')}
assert counts == {'tests': 119, 'failures': 0, 'errors': 0, 'skipped': 0}
ledger = json.loads((ROOT / 'runtime_trace/regular_nstep/artifacts/budget.json').read_bytes())
assert ledger['used_seconds'] == summary['shared_ledger_used_seconds']
marker = json.loads((ROOT / 'runtime_trace/regular_nstep/artifacts/budget.running.json').read_bytes())
assert marker['state'] == 'FINISHED'
runtime = logical_size(ROOT / 'runtime_trace/regular_nstep/artifacts')
driver = logical_size(ROOT / 'verified_driver/v0/artifacts')
native = summary['storage']['native_mirror_all']
combined = runtime['logical_bytes'] + driver['logical_bytes'] + native['logical_bytes']
assert combined < 8 * 1024 ** 3
payload = {
    'schema': 'VERIFIED_DRIVER_V0_DELIVERY_CHECK_V1',
    'head': base,
    'source_inventory_files': len(inventory['new_driver_review_files']),
    'source_inventory_lines': sum(item['lines'] for item in inventory['new_driver_review_files'].values()),
    'tests': counts,
    'protected_checked_files': preservation['checked_files'],
    'protected_changes': 0,
    'production_sources_match_final_authority_run': True,
    'tracked_diff_bytes': 0,
    'staged_diff_bytes': 0,
    'managed_git_status_sha256': digest(OUT / 'git-status.txt'),
    'original_git_status_sha256': digest(OUT / 'original-git-status.txt'),
    'report_sha256': digest(ROOT / 'current/VERIFIED_DRIVER_V0_2026-10-05.md'),
    'source_inventory_sha256': digest(OUT / 'source-inventory.json'),
    'actual_untracked_git_patch_sha256': digest(OUT / 'untracked-source-git-diff.patch'),
    'junit_sha256': digest(junit),
    'shared_ledger_used_seconds': ledger['used_seconds'],
    'remaining_shared_seconds': summary['remaining_shared_seconds'],
    'runtime_artifacts': runtime,
    'driver_artifacts': driver,
    'native_mirror_all_export_snapshot': native,
    'combined_logical_bytes_before_this_receipt': combined,
    'storage_note': 'Native mirror retained export snapshot. Managed artifacts remeasured after final report/package; this small receipt and later UI/tool metadata excluded.',
    'commit_push': 'NOT PERFORMED',
}
(OUT / 'delivery-check.json').write_text(json.dumps(payload, sort_keys=True, indent=2) + '\n', encoding='utf-8')
print(json.dumps({key: payload[key] for key in (
    'tests', 'protected_checked_files', 'source_inventory_files', 'source_inventory_lines',
    'production_sources_match_final_authority_run', 'combined_logical_bytes_before_this_receipt',
    'remaining_shared_seconds', 'commit_push')}))
