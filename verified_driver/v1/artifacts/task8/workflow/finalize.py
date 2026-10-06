"""Read-only validation and exclusive final submission; no ledger mutation."""
from pathlib import Path
import collections,hashlib,json,sys,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[5];HERE=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from verified_driver.v1.model import content_id
from verified_driver.v1.live_chain.session import live_source_snapshot
from verified_driver.v0.gate import source_snapshot,APPROVED_RT_PINSET_SHA
def read(p):return json.loads(p.read_bytes())
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def save(name,data):
    with (HERE/name).open('x',encoding='utf-8',newline='\n') as f:json.dump(data,f,sort_keys=True,indent=2);f.write('\n')
def history(path):
    data=read(path)['files'];changed=[]
    for name,want in data.items():
        p=ROOT/name;actual={'bytes':p.stat().st_size,'sha256':sha(p)} if p.is_file() else None
        if actual!=want:changed.append({'path':name,'before':want,'after':actual})
    assert not changed,(path,changed)
    return {'checked':len(data),'changed':changed}
manifest=read(HERE/'final-selection.json')
pins=live_source_snapshot(ROOT);binding=content_id(pins)
mirror=read(HERE/manifest['mirror'])['files'];assert all(sha(ROOT/n)==v for n,v in mirror.items())
relocated=['__init__.py','checker.py','checkpoint.py','gdb_live.py','harness.py','producer.py','protocol.py','raw.py','schema.py','session.py','worker.py']
assert len(pins)==40 and all('verified_driver/v1/live_chain/'+n in pins for n in relocated)
rt={n.replace('\\','/'):v for n,v in source_snapshot(ROOT)['runtime'].items()}
approved=ROOT/'runtime_trace/regular_nstep/artifacts/connected10-final2/integration_source_pinset.json'
assert len(rt)==89 and rt==read(approved) and sha(approved)==APPROVED_RT_PINSET_SHA
protected=read(ROOT/'verified_driver/v1/artifacts/preservation/task8-final.json');assert protected['checked_files']==7232 and not protected['changed']
histories={n:history(ROOT/p) for n,p in [('pre_task8','verified_driver/v1/artifacts/task8/history-before.json'),('pre_task7','verified_driver/v1/artifacts/task7/history-before.json'),('pre_compatibility','verified_driver/v1/artifacts/namespace-compatibility/historical-before.json')]}
runs={};evidence_files=0
for stage,name in manifest['runs'].items():
    summary=read(HERE/name/'SUMMARY.json');assert summary['verdict']=='PASS' and summary['source_binding']==binding
    assert read(HERE/name/'source-pinset.json')==pins
    exported=read(HERE/(name+'-export.json'))['files']
    assert all(sha(HERE/name/n)==v for n,v in exported.items())
    evidence_files+=len(exported);runs[stage]={'run':name,'summary':summary,'export_file_count':len(exported)}
for k in (1,2):
    p=HERE/manifest['runs']['positive'];publication=read(p/f'publication-{k}.json');resume=read(p/f'runs/actual/live/observed-resume-{k}.json')
    assert publication['CURRENT']==resume['CURRENT']==resume['token']['state_id'] and publication['paused_proved'] and publication['next_body_absent'] and resume['next_body_absent']
    assert publication['monotonic_ns']<resume['monotonic_ns']
tree=ET.parse(HERE/manifest['junit']);suite=tree.getroot().find('testsuite')
counts={k:int(suite.attrib[k]) for k in ('tests','failures','errors','skipped')};counts['passed']=counts['tests']-sum(counts[k] for k in ('failures','errors','skipped'))
assert counts['failures']==counts['errors']==counts['skipped']==0
counts['tests_by_module']=dict(collections.Counter(c.attrib['classname'] for c in tree.iter('testcase')))
budget=read(ROOT/'runtime_trace/regular_nstep/artifacts/budget.json');prior=read(HERE/'pre-ceiling-budget.snapshot.json')
assert budget['approved_total_seconds']==4200 and budget['jobs'][:len(prior['jobs'])]==prior['jobs']
jobs=budget['jobs'][len(prior['jobs']):];added=sum(j['wall_seconds'] for j in jobs)
assert abs(budget['used_seconds']-prior['used_seconds']-added)<1e-9 and budget['used_seconds']<=4200
assert read(ROOT/'runtime_trace/regular_nstep/artifacts/budget.running.json')['state']=='FINISHED'
before=read(HERE/'source-before.json');delta=[n for n in sorted(set(before)|set(pins)) if before.get(n)!=pins.get(n)]
review=read(HERE/manifest['review']);assert review['verdict']=='APPROVE'
save('source-pinset.json',pins)
save('final-inventory.json',{'schema':'TASK8_FINAL_EVIDENCE_SUBMISSION_V1','designer_completion_decision':'PENDING','formal_certification':False,'external_audit':'NOT_PERFORMED','source_binding':binding,'v1_pinset_files':len(pins),'relocated_live_chain_files_pinned':11,'source_delta_from_task7':delta,'combined_source_identical_files':len(mirror),'protected_files':7232,'protected_changed':[],'histories':histories,'v0_approved_pinset_files':89,'v0_approved_pinset_sha256':APPROVED_RT_PINSET_SHA,'regression':counts,'actual_runs':runs,'exported_evidence_files_verified':evidence_files,'fresh_internal_review':review,'prior_ledger_jobs_preserved':True,'prior_used_seconds':prior['used_seconds'],'ceiling_seconds':4200,'additional_guarded_wall_seconds':added,'used_seconds':budget['used_seconds'],'remaining_seconds':4200-budget['used_seconds'],'guarded_jobs':jobs})
print(json.dumps({'regression':counts['passed'],'source_binding':binding,'history_counts':{n:v['checked'] for n,v in histories.items()},'additional_guarded_wall_seconds':added,'used_seconds':budget['used_seconds'],'remaining_seconds':4200-budget['used_seconds']}))
