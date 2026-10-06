"""Read-only final evidence checks and exclusive Task7 submission artifacts."""
from pathlib import Path
import collections,hashlib,json,subprocess,sys,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[5]; HERE=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from verified_driver.v1.model import content_id
from verified_driver.v1.live_chain.session import live_source_snapshot
from verified_driver.v0.gate import source_snapshot,APPROVED_RT_PINSET_SHA

def read(p):return json.loads(p.read_bytes())
def sha(p):
    with p.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def save(name,doc):
    with (HERE/name).open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(doc,stream,sort_keys=True,indent=2);stream.write('\n')
def checked_history(path):
    files=read(path)['files'];changed=[]
    for name,want in files.items():
        p=ROOT/name
        actual={'bytes':p.stat().st_size,'sha256':sha(p)} if p.is_file() else None
        if actual!=want:changed.append({'path':name,'before':want,'after':actual})
    return {'checked':len(files),'changed':changed}

history=checked_history(HERE/'history-before.json')
old=checked_history(ROOT/'verified_driver/v1/artifacts/namespace-compatibility/historical-before.json')
source_before=read(HERE/'source-before.json')
sources={p.relative_to(ROOT).as_posix():sha(p) for p in (ROOT/'verified_driver/v1').rglob('*.py')
         if 'artifacts' not in p.relative_to(ROOT/'verified_driver/v1').parts and '__pycache__' not in p.parts}
assert sources==source_before,'Task7 product source changed'
pins=live_source_snapshot(ROOT)
assert pins==read(ROOT/'verified_driver/v1/artifacts/task6-source-pinset.json')
relocated=['__init__.py','checker.py','checkpoint.py','gdb_live.py','harness.py','producer.py',
           'protocol.py','raw.py','schema.py','session.py','worker.py']
assert all('verified_driver/v1/live_chain/'+name in pins for name in relocated)
rt={name.replace('\\','/'):value for name,value in source_snapshot(ROOT)['runtime'].items()}
assert len(rt)==89 and content_id(rt)==APPROVED_RT_PINSET_SHA
assert not history['changed'] and not old['changed']
protected=read(ROOT/'verified_driver/v1/artifacts/preservation/task7-final.json')
assert protected['checked_files']==7232 and not protected['changed']
mirror=read(HERE/'source-mirror-green01.json')['files']
assert all(sha(ROOT/name)==value for name,value in mirror.items())

def junit(name):
    tree=ET.parse(HERE/(name+'-junit.xml'));suite=tree.getroot().find('testsuite')
    counts={field:int(suite.attrib[field]) for field in ('tests','failures','errors','skipped')}
    counts['passed']=counts['tests']-counts['failures']-counts['errors']-counts['skipped']
    counts['tests_by_module']=dict(collections.Counter(tc.attrib['classname'] for tc in tree.iter('testcase')))
    return counts
attacks=junit('task7-attacks-green01');combined=junit('task7-all-final')
assert attacks['passed']==54 and combined['passed']==318
assert all(combined[f]==0 and attacks[f]==0 for f in ('failures','errors','skipped'))
rows=read(HERE/'task7-all-final-attack-results.json')['rows']
assert len(rows)==54 and set(r['verdict'] for r in rows)<={'PASS','STOP','REFUSED'}
budget=read(ROOT/'runtime_trace/regular_nstep/artifacts/budget.json')
preflight=read(HERE/'preflight.json')
jobs=[j for j in budget['jobs'] if '/task7-' in j['path'].replace('\\','/')]
added=sum(j['wall_seconds'] for j in jobs)
assert abs(budget['used_seconds']-preflight['used_seconds']-added)<1e-9
remaining=3600-budget['used_seconds']
caps=read(ROOT/'verified_driver/v1/artifacts/execution-allocation.json')['guard_caps_seconds']
caps={name:value for name,value in caps.items() if name!='necessary_saved_N3_fixture'}
caps['final_regression']=120
allowance={'schema':'TASK8_ALLOWANCE_PLAN_NOT_LEDGER_V1','guard_caps_seconds':caps,
    'required_seconds':sum(caps.values()),'remaining_seconds':remaining,
    'shortfall_seconds':sum(caps.values())-remaining,'fits_existing_allowance':sum(caps.values())<=remaining,
    'heavy_runs_started':False,'new_ledger':False,'ceiling_changed':False,
    'interpretation':'Hard stop caps retained from the original allocation plus final-regression 120s cap; not measured Gala completion times or an ETA. No retry/review-fix reserve included.',
    'basis':'verified_driver/v1/artifacts/execution-allocation.json and task7/workflow/run.py',
    'decision':'STOP_ALLOWANCE_INSUFFICIENT; designer ceiling decision required before Task8 execution'}
save('task8-allowance.json',allowance)
save('source-pinset.json',pins)
save('source-final.json',{'product_sources':sources,'combined_tested_sources':mirror})
summary={'schema':'TASK7_FINAL_SUBMISSION_V1','status':'COMPLETE_UNIT_MARKER_SAVED_SCOPE',
    'combined_regression':combined,'standalone_attacks':attacks,'attack_count':len(rows),
    'attack_verdict_counts':dict(collections.Counter(r['verdict'] for r in rows)),
    'protected_files_checked':7232,'protected_changed':protected['changed'],
    'pre_task7_history':history,'pre_compatibility_history':old,
    'product_sources_unchanged':True,'v1_pinset_files':len(pins),'v1_pinset_sha256':content_id(pins),
    'relocated_live_chain_files_pinned':11,'approved_runtime_pinset_files':89,
    'approved_runtime_pinset_sha256':APPROVED_RT_PINSET_SHA,'combined_source_identical_files':len(mirror),
    'guarded_jobs':jobs,'additional_guarded_wall_seconds':added,'used_seconds':budget['used_seconds'],
    'remaining_task8_seconds':remaining,'task8_required_cap_seconds':allowance['required_seconds'],
    'task8_shortfall_seconds':allowance['shortfall_seconds'],'task8_started':False,
    'new_architecture_or_contract_conflict_found':False,'product_fixes':[],
    'red_history':'task7-attacks-01: 51 PASS / 3 FAIL; exact malformed-token constructor refusal occurred outside the original test assertion; only test assertion boundary corrected'}
save('final-inventory.json',summary)
lines=['# Task 7 attack and compatibility submission','',
 'Task 7 is complete in unit / real marker-process / saved TEST_ONLY evidence scope. Actual fresh Gala V1 N=3/N=4, replay and Gala controller-death remain unexecuted Task 8 work. No external audit or formal certification is claimed.',
 '',f"Combined final regression: **318 PASS / 0 FAIL / 0 ERROR / 0 SKIP**. Standalone attack rerun: **54 PASS**. New controls: {summary['attack_verdict_counts']}. Every expected attack was detected; STOP preserves the exact durable generation and the specified marker boundary.",
 '', 'The initial 51 PASS / 3 FAIL run is preserved. All three failures came from the new test failing to capture strict malformed-token constructor refusal, before resume. See red-01-root-cause.md and red-01-test-source.py. No product bytes/contracts changed and no new architecture conflict was found.',
 '',f"Protected baseline: 7,232 unchanged. Pre-Task7 V1 historical evidence: {history['checked']} unchanged. Pre-compatibility history: {old['checked']} unchanged. V0 approved 89-file pinset unchanged: `{APPROVED_RT_PINSET_SHA}`. Task 4 fixture remains historical TEST_ONLY.",
 '',f"Final V1 source pinset: {len(pins)} files, SHA256 `{content_id(pins)}`; all 11 relocated live-chain files plus supervisor, replay and containment are included. The 19 V1 implementation files and the entire 40-file pinset match Task 6 byte-for-byte. The tested combined mirror matches {len(mirror)} source files.",
 '',f"Additional shared guarded wall: **{added!r}s**. Ledger: **{budget['used_seconds']!r}/3600s**. Task 8 remainder: **{remaining!r}s**. Same ledger and ceiling; all RED/GREEN/final jobs charged.",
 '',f"Task 8 proposed hard-cap allowance: **{allowance['required_seconds']}s**, shortfall **{allowance['shortfall_seconds']!r}s**. No Task 8 execution. Caps are allocation ceilings, not measured Gala durations. Review/fix/retry reserve is additional and not included. See task8-allowance.json.",
 '', '## Per-attack results','', '| Attack/control | Actual verdict | Scope | CURRENT / markers |','|---|---|---|---|']
for r in rows:
    boundary=f"S{r['generation']} / {r.get('markers')}" if 'generation' in r else f"forbidden body {r.get('forbidden_body')} absent" if 'forbidden_body' in r else r.get('failure_stage','pointer unchanged; no fresh launch')
    lines.append(f"| {r['attack']} | {r['verdict']} | {r['scope']} | {boundary} |")
lines+=['','Saved numerical mutations use scratch derived copies and independently recompute correspondence after edge/completion hash repair. They retain TEST_ONLY status and confer no LIVE authority. Marker gate injection tests authority sequencing only. The full final suite also re-runs cross-session checkpoint splice, single-link replay attachments, immutable attachment substitution/reuse, prefix/frontier refusal, terminal replay, recovery and paused/active marker containment.',
 '', '## Task 8 hard caps','', '| Run | Seconds |','|---|---:|']
lines += [f'| {name} | {value} |' for name,value in caps.items()]
with (HERE/'report.md').open('x',encoding='utf-8',newline='\n') as stream:stream.write('\n'.join(lines)+'\n')
print(json.dumps({k:summary[k] for k in ('status','attack_count','v1_pinset_sha256','additional_guarded_wall_seconds','used_seconds','remaining_task8_seconds','task8_required_cap_seconds','task8_shortfall_seconds')}))
