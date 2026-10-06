"""Read-only historical preservation, final costs, source identity and delivery inventory."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
import stat
ROOT = Path(__file__).resolve().parents[2]
ORIGINAL = Path('D:/numerical-audit-lab-recovered-2026-10-01')
ART = ROOT / 'runtime_trace/regular_nstep/artifacts'
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'current/runtime-nstep-delivery-2026-10-05'
OUT.mkdir(exist_ok=False)
def load(p): return json.loads(p.read_bytes())
def sha(p):
    with p.open('rb') as stream: return hashlib.file_digest(stream, 'sha256').hexdigest()
base = load(ORIGINAL / 'current/runtime-nstep-preflight-2026-10-05/baseline.json')
preserved = []
for label, folder, entries in [('original_history', ORIGINAL, base['protected_files']),
    ('worktree_history', ROOT, base['protected_files']), ('other_work', ORIGINAL, base['other_work_files'])]:
    changed = [e['path'] for e in entries if not (folder / e['path']).is_file() or
        (folder / e['path']).stat().st_size != e['bytes'] or sha(folder / e['path']) != e['sha256']]
    preserved.append({'set':label,'checked_files':len(entries),'changed_or_missing':changed})
sources = [load(ART / run / 'integration_source_pinset.json') for run in ('connected10-final2','connected100-final')]
assert sources[0] == sources[1], 'same-source identity'
costs = []
for n, name in [(10,'connected10-final2'),(100,'connected100-final')]:
    run = ART / name
    complete = load(run / 'run_result.json')
    assert complete['verdict'] == 'CHECKER_PASS' and complete['checked_steps'] == n and complete['requested_complete'] is True
    original = ART / 'original-baselines'
    raw = load(run / 'capture/capture.json')
    original_harness = load(original / f'output{n}/harness_output.json')
    captured_harness = load(run / 'capture/harness_output.json')
    assert original_harness['n_steps'] == captured_harness['n_steps'] == n
    assert original_harness['output_bits'] == captured_harness['output_bits']
    costs.append({'steps': n, 'run':name, 'completion':complete,
        'original_job':load(original / f'job{n}/execution.json'),
        'original_harness':original_harness, 'captured_harness':captured_harness,
        'original_vs_captured_output_bits_identical':True,
        'stage_jobs':{stage:load(run / stage / 'execution.json') for stage in ('acquisition','derivation','independent_check')},
        'internal_derivation_time_only':load(run / 'derived/stage_costs.json'),
        'raw_rows':raw['record_count'], 'raw_bytes':(run / 'capture/trace.jsonl').stat().st_size,
        'capture_file_bytes':sum(p.stat().st_size for p in (run/'capture').rglob('*') if p.is_file()),
        'derived_file_bytes':sum(p.stat().st_size for p in (run/'derived').rglob('*') if p.is_file()),
        'laptop_job':load(ART / 'laptop-results' / ('audit10-final-v2-job.json' if n == 10 else 'audit100-final-job.json')),
        'laptop_replay':load(ART / 'laptop-results' / ('audit10-final-v2-result.json' if n == 10 else 'audit100-final-result.json'))})
git = {str(folder): {'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=folder,text=True).strip(),
    'status':subprocess.check_output(['git','status','--short'],cwd=folder,text=True)} for folder in (ORIGINAL,ROOT)}
evidence, reparse = {}, []
for path in ART.rglob('*'):
    info = path.lstat()
    relative = str(path.relative_to(ROOT)).replace('\\','/')
    if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
        reparse.append({'path':relative, 'logical_payload_bytes':info.st_size,
            'method':'lstat only; WSL pytest current link retained and never followed'})
    elif stat.S_ISREG(info.st_mode):
        evidence[relative] = {'bytes':info.st_size,'sha256':sha(path)}
summary = {'schema':'regular-nstep-delivery-inventory-v1','preservation':preserved,'git':git,
    'same_integration_source':True,'integration_source_pinset_sha256':sha(ART/'connected10-final2/integration_source_pinset.json'),
    'costs':costs,'artifact_file_bytes':sum(v['bytes'] for v in evidence.values()),
    'budget':load(ART/'budget.json'),'evidence_files':evidence,'unfollowed_links':reparse,
    'external_portability_proof':load(ART/'external-proof-receipts/external-storage-inventory.json'),
    'laptop_storage':load(ART/'laptop-results/storage-observation-final.json')}
(OUT/'inventory.json').write_text(json.dumps(summary,sort_keys=True,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'preservation':preserved,'same_integration_source':True,'artifact_file_bytes':summary['artifact_file_bytes']}))
assert not any(x['changed_or_missing'] for x in preserved), 'historical preservation failed'
