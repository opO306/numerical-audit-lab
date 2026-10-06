"""Fresh original authority proof; later copies are explicitly TEST_ONLY controls."""
from dataclasses import asdict
import json
import os
from pathlib import Path
import platform
import resource
import shutil
import subprocess
import sys
import time
ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT))
from verified_driver.v0.driver import VerifiedDriver,_write
from verified_driver.v0.store import CertifiedStore
from verified_driver.v0.gate import source_snapshot,file_sha,file_json,STAGES
from verified_driver.v0.model import regular_genesis,canonical_bytes
from runtime_trace.regular_nstep.resources import Limits

OUT=ROOT/'verified_driver/v0/artifacts'/sys.argv[1]
OUT.mkdir(parents=True,exist_ok=False)
LEDGER=ROOT/'runtime_trace/regular_nstep/artifacts/budget.json'
used=file_json(LEDGER)['used_seconds']
if 3600-used<120: raise SystemExit('REFUSED_RESOURCE: insufficient remaining shared budget')
resource.setrlimit(resource.RLIMIT_AS,(4294967296,4294967296))
wheel=ROOT/'audit/gate2c1/vendor/gala-1.12.0-cp312-cp312-manylinux_2_24_x86_64.manylinux_2_28_x86_64.whl'
git_env={**os.environ,'GIT_DIR':'/mnt/d/numerical-audit-lab-recovered-2026-10-01/.git/worktrees/numerical-audit-lab-recovered-2026-10-01','GIT_WORK_TREE':str(ROOT)}
_write(OUT/'pre.json',{'schema':'DRIVER_V0_FRESH_PRE_V1','host':platform.node(),'platform':platform.platform(),
    'python':platform.python_version(),'source':source_snapshot(ROOT),'ledger_before':file_json(LEDGER),
    'remaining_seconds':3600-used,'limits':asdict(Limits()),'controller_virtual_memory_max':4294967296,
    'wheel_sha256':file_sha(wheel),'spec_sha256':file_sha(ROOT/'docs/superpowers/specs/2026-10-05-verified-driver-v0-design.md'),
    'plan_sha256':file_sha(ROOT/'docs/superpowers/plans/2026-10-05-verified-driver-v0.md'),
    'protected_inventory_sha256':file_sha(ROOT/'verified_driver/v0/artifacts/preservation/before.json'),
    'git_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,env=git_env,text=True).strip(),
    'git_status':subprocess.check_output(['git','status','--short'],cwd=ROOT,env=git_env,text=True),
    'role':'FRESH actual original Gala/collector/producer/independent-checker authority path'})
store=CertifiedStore(OUT/'certified'); store.initialize(regular_genesis(ROOT))
before=store.current(); events=[]
def observe(point):
    pointer=(store.root/'CURRENT').read_text().strip()
    if point in ('after_objects','before_replace'): assert pointer==before[0]
    events.append({'point':point,'current_id':pointer,'independent_checker_pass':file_json(OUT/'pending/real/fresh_checker_report.json')['verdict']=='CHECKER_PASS',
        'receipts_present':len(list((store.root/'receipts').glob('*.json')))})
store._crash_hook=observe
driver=VerifiedDriver(ROOT,store,OUT/'pending',LEDGER)
started=time.perf_counter(); result=driver.transact(1,'real'); elapsed=time.perf_counter()-started
store._crash_hook=None
_write(OUT/'actual-result.json',{'result':asdict(result),'total_seconds':elapsed,'publication_events':events})
assert result.verdict=='ACCEPT',result.reason
identity,state=store.current(); bits=file_json(OUT/'pending/real/capture/harness_output.json')['output_bits']
assert state.generation==1 and list(state.state_bits)==bits and identity==result.state_id
restarted=VerifiedDriver(ROOT,CertifiedStore(store.root),OUT/'restart-pending',LEDGER)
retry=restarted.transact(1,'real'); assert retry.state_id==identity and retry.generation==1
unsupported=restarted.transact(1,'no-arbitrary-restart')
assert unsupported.verdict=='STOP' and restarted.store.current()==(identity,state)

def saved_control(out,mutant=False):
    """TEST_ONLY copied real-one evidence; does not execute an independent checker anew."""
    source=OUT/'pending/real'
    for name in ['run_result.json','integration_source_pinset.json','fresh_checker_report.json','capture/harness_output.json','derived/completion.json']+[s+'/execution.json' for s in STAGES]:
        target=out/name; target.parent.mkdir(parents=True,exist_ok=True); shutil.copyfile(source/name,target)
    for stage in STAGES:
        p=out/stage/'execution.json'; v=file_json(p)
        v['command']=[str(x).replace(str(source),str(out)) for x in v['command']]
        v['TEST_ONLY_saved_control']=True; p.write_bytes(canonical_bytes(v))
    run=file_json(out/'run_result.json'); run['stage_receipts']=[file_sha(out/s/'execution.json') for s in STAGES]
    (out/'run_result.json').write_bytes(canonical_bytes(run))
    observed=file_json(out/'fresh_checker_report.json')
    if mutant:
        h=file_json(out/'capture/harness_output.json'); h['output_bits'][0]=f"0x{int(h['output_bits'][0],16)+1:016x}"
        (out/'capture/harness_output.json').write_bytes(canonical_bytes(h))
    return observed

bad=VerifiedDriver(ROOT,CertifiedStore(OUT/'refusal-certified'),OUT/'refusal-pending',LEDGER)
old=bad.store.current(); bad._run_segment=lambda n,out:saved_control(out,True)
refusal=bad.transact(1,'mutated'); assert refusal.verdict=='STOP' and bad.store.current()==old
_write(OUT/'authority-proof.json',{'schema':'DRIVER_V0_AUTHORITY_PROOF_V1','actual_result':asdict(result),
    'certified_state':asdict(state),'exact_terminal_bits':bits,'retry':asdict(retry),'unsupported_restart':asdict(unsupported),
    'controlled_refusal':asdict(refusal),'refusal_role':'TEST_ONLY saved real-one evidence plus1ulp; no fresh numerical rerun',
    'prior_refusal_state_id':old[0],'after_refusal_state_id':bad.store.current()[0],
    'ledger_after':file_json(LEDGER),'driver_controller_peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
    'controller_memory_note':'RLIMIT_AS cap; numerical child trees independently enforced by existing cgroup guard',
    'manual_work':'test evidence locators rebound by script; no original numerical formula transcribed'})
print(json.dumps({'verdict':result.verdict,'generation':state.generation,'bits':bits,'driver_seconds':result.driver_seconds,
    'runtime_adapter_seconds':result.runtime_seconds,'controlled_refusal':refusal.verdict,'path':str(OUT)}))
