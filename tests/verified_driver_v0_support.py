"""TEST_ONLY controlled runner: saved evidence tests authority/storage, not fresh numerics."""
import hashlib
import json
import os
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[1]
CASE=ROOT/'runtime_trace/regular_nstep/artifacts/connected10-final2'
BITS=('0x3fa3eaff7788ac22','0x3f93eacc1b020e3a','0x3fcf9999a5c32ae6','0x3fbf984cad4b103f')
def dump(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False))
def load(path): return json.loads(path.read_bytes())
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def digest(value): return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def snapshot(root=ROOT):
    runtime={}
    for base,dirs,files in os.walk(root/'runtime_trace'):
        dirs[:]=[d for d in dirs if d not in ('artifacts','__pycache__')]
        for name in files:
            if name.endswith('.py'):
                p=Path(base)/name; runtime[str(p.relative_to(root))]=sha(p)
    for relative in ('lab/v2_bound.py','independent_checker/oracle.py'): runtime[relative]=sha(root/relative)
    driver={str(p.relative_to(root)):sha(p) for p in (root/'verified_driver').glob('*.py')}
    driver.update({str(p.relative_to(root)):sha(p) for p in (root/'verified_driver/v0').glob('*.py')})
    return {'runtime':runtime,'driver':driver}

def copy_control(out):
    out=Path(out); out.mkdir(parents=True,exist_ok=True)
    files=['run_result.json','integration_source_pinset.json','fresh_checker_report.json',
        'capture/harness_output.json','derived/completion.json']
    for stage in ('acquisition','derivation','independent_check'): files.append(stage+'/execution.json')
    for name in files:
        target=out/name; target.parent.mkdir(parents=True,exist_ok=True); shutil.copyfile(CASE/name,target)
    for stage in ('acquisition','derivation','independent_check'):
        path=out/stage/'execution.json'; record=load(path)
        record['command']=[str(x).replace(str(CASE),str(out)) for x in record['command']]
        # Historical capture was on the mounted worktree; rebuild only fixture locators.
        old='/mnt/c/Users/zun24/.codex/worktrees/runtime-nstep/numerical-audit-lab-recovered-2026-10-01/runtime_trace/regular_nstep/artifacts/connected10-final2'
        record['command']=[str(x).replace(old,str(out)) for x in record['command']]
        if '--root' in record['command']:
            record['command'][record['command'].index('--root')+1]=str(ROOT)
        record['cwd']=str(ROOT); record['TEST_ONLY_saved_resource_fixture']=True
        dump(path,record)
    run=load(out/'run_result.json')
    run['stage_receipts']=[sha(out/stage/'execution.json') for stage in ('acquisition','derivation','independent_check')]
    dump(out/'run_result.json',run)
    return load(out/'fresh_checker_report.json')

def bind_control(out,tx,pred,root=ROOT,observed=None):
    out=Path(out).resolve()
    binding={'schema':'DRIVER_V0_RUN_BINDING_V1','transaction_id':tx,'predecessor_id':pred.content_hash,
        'predecessor_bits':list(pred.state_bits),'evidence_dir':str(out),'requested_steps':10,
        'source_start':snapshot(root),'observed_report':observed or load(out/'fresh_checker_report.json'),
        'fresh_report_sha256':sha(out/'fresh_checker_report.json'),'run_result_sha256':sha(out/'run_result.json'),
        'role':'TEST_ONLY stored-evidence fixture; no fresh numerical execution'}
    dump(out/'driver_binding.json',binding)
    return binding

def control(out,tx,pred):
    copy_control(out); bind_control(out,tx,pred)
    return out

def rehash_completion(out):
    document=load(out/'derived/completion.json'); document.pop('completion_sha256')
    document['completion_sha256']=digest(document); dump(out/'derived/completion.json',document)

def test_runner(driver,mutate=None,inspect=None):
    def runner(n,out):
        assert n==10
        if inspect: inspect()
        observed=copy_control(out)
        if mutate: mutate(out)
        return observed
    driver._run_segment=runner
    return driver
