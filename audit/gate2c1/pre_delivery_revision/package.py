"""Create the complete ZIP first, then bind its final bytes in delivery documents."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import zipfile

ROOT=Path(__file__).resolve().parents[1]
WHEEL='gala-1.12.0-cp312-cp312-manylinux_2_24_x86_64.manylinux_2_28_x86_64.whl'
SO=['gala/potential/potential/builtin/cybuiltin.cpython-312-x86_64-linux-gnu.so',
    'gala/integrate/cyintegrators/leapfrog.cpython-312-x86_64-linux-gnu.so']
P='reports/gate2c1-measured-2026-10-02'
I='reports/gate2c1-independent-2026-10-02'
REQUIRED=['audit/gate2c1/vendor/'+WHEEL]+['audit/gate2c1/vendor/'+p for p in SO]+[
    'benchmarks/gate2b/fixtures/cloud-2026-10-01/manifest.json',
    'benchmarks/gate2b/evidence/disassembly.txt','audit/gate2c1/evidence/c_gradient.txt',
    'audit/gate2c1/machine_mapping.json','benchmarks/gate2c1/binary_replay.py',
    'lab/gate2c1_checks.py','audit/gate2c1/independent/checker.py',
    'docs/GATE2C1_PLAN.md','docs/GATE2C1_VERIFICATION_METHOD.md','docs/GATE2C1_RESULT.md',
    'docs/GATE2C1_AUDIT_CHARTER.md','audit/gate2c1/plan_seal.json','audit/gate2c1/method_seal.json',
    'audit/gate2c1/code_seal.json','audit/gate2c1/result_seal.json',
    P+'/gate2c1_report.json',I+'/independent_report.json','git/gate2c1.bundle']
for orbit in ('regular','chaotic'):
    REQUIRED += [P+'/evidence/traces/'+orbit+'_init.json',P+'/evidence/traces/'+orbit+'_step1.json']
    REQUIRED += [P+f'/evidence/exact/{orbit}_{n}_8step.json' for n in (0,50000,99992)]
    REQUIRED += [I+f'/exact/{orbit}_{n}_8step.json' for n in (0,50000,99992)]
    REQUIRED += [P+f'/evidence/segments/{orbit}/{n:06d}.json' for n in range(1000,100001,1000)]
    REQUIRED += [I+f'/segments/{orbit}/{n:06d}.json' for n in range(1000,100001,1000)]
    REQUIRED += [f'benchmarks/gate2b/fixtures/cloud-2026-10-01/{orbit}_{k}.u64.gz'
                 for k in ('forward','gradient','mirror','reversal_ends')]

def sha(b):return hashlib.sha256(b).hexdigest()

def validate_evidence(contents):
    producer=json.loads(contents[P+'/gate2c1_report.json'])['deterministic']
    independent=json.loads(contents[I+'/independent_report.json'])
    if producer['N']!=100000 or independent['N']!=100000 or independent['verification_verdict']!='PASS' or independent['failure']:
        raise ValueError('full reproduction evidence incomplete or failed')
    for orbit in ('regular','chaotic'):
        po=producer['orbits'][orbit];io=independent['orbits'][orbit]
        if po['steps_measured']!=100000 or io['steps_recomputed']!=100000 or len(po['segments'])!=100 or len(io['connections'])!=100:
            raise ValueError('full segment coverage missing')
        previous_end=previous_hash=None
        for j,(advertised,connection) in enumerate(zip(po['segments'],io['connections']),1):
            coverage=[(j-1)*1000+1,j*1000]
            rel=f'segments/{orbit}/{j*1000:06d}.json'
            if advertised['path']!=rel or advertised['coverage']!=coverage or connection['coverage']!=coverage:
                raise ValueError('advertised coverage/path mismatch')
            raw=contents[P+'/evidence/'+rel];block=json.loads(raw)
            evidence=json.loads(contents[I+'/'+rel])
            digest=sha(raw)
            if advertised['sha256']!=digest or evidence['producer_segment_sha256']!=digest:
                raise ValueError('segment hash not bound to report and independent evidence')
            if block['coverage']!=coverage or evidence['coverage']!=coverage or block['previous_segment_sha256']!=previous_hash or evidence['previous_segment_sha256']!=previous_hash:
                raise ValueError('segment hash chain/coverage mismatch')
            if previous_end is not None and block['start']!=previous_end:
                raise ValueError('segment endpoint connection mismatch')
            if evidence['start']!=block['start'] or evidence['end']!=block['end'] or evidence['decision_digest']!=block['decision_digest'] or not connection['recomputed_endpoint_equal'] or not connection['decision_digest_equal']:
                raise ValueError('independent segment evidence mismatch')
            previous_end=block['end'];previous_hash=digest

def validate_members(path,manifest,required):
    with zipfile.ZipFile(path) as z:
        names=z.namelist()
        if len(names)!=len(set(names)) or z.testzip() is not None:raise ValueError('duplicate/CRC failure')
        if any(p not in names for p in required):raise ValueError('advertised member missing')
        if any(p not in names or sha(z.read(p))!=h for p,h in manifest.items()):raise ValueError('member hash mismatch')
        if set(names)!=set(manifest)|{'PACKAGE_MANIFEST.json'} and 'PACKAGE_MANIFEST.json' in names:
            raise ValueError('unmanifested member')
        if P+'/gate2c1_report.json' in names and I+'/independent_report.json' in names:
            validate_evidence({p:z.read(p) for p in manifest})
    return len(manifest)

def verify_delivery(directory):
    directory=Path(directory)
    record=json.loads((directory/'delivery_receipt.json').read_bytes())
    filename=record['zip_file']
    if Path(filename).name!=filename:raise ValueError('delivery filename must be basename')
    digest=sha((directory/filename).read_bytes())
    if digest!=record['zip_sha256']:raise ValueError('actual ZIP / receipt mismatch')
    doc=(directory/'DELIVERY.md').read_text(encoding='utf-8')
    hashes=re.findall(r'SHA-256: `([0-9a-f]{64})`',doc)
    if hashes!=[digest] or filename not in doc:raise ValueError('document package hash mismatch')
    if (directory/(filename+'.sha256')).read_text().strip()!=f'{digest}  {filename}':
        raise ValueError('sidecar package hash mismatch')
    return digest

def build(out):
    out=Path(out)
    if out.exists():raise ValueError('new delivery directory required')
    if subprocess.check_output(['git','status','--porcelain'],cwd=ROOT):raise ValueError('clean committed HEAD required')
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip()
    paths=subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode().split('\0')
    contents={p:(ROOT/p).read_bytes() for p in paths if p}
    missing=[p for p in REQUIRED if p not in contents and p!='git/gate2c1.bundle']
    if missing:raise ValueError('required tracked inputs absent: '+str(missing))
    validate_evidence(contents)
    if sha(contents['audit/gate2c1/vendor/'+WHEEL])!='cc5f0cf3bc63a966a3c130b93f6c05026271fe7178492a02c6266c243b5fc2f0':
        raise ValueError('wrong wheel bytes')
    manifest=json.loads(contents['benchmarks/gate2b/fixtures/cloud-2026-10-01/manifest.json'])
    with zipfile.ZipFile(io.BytesIO(contents['audit/gate2c1/vendor/'+WHEEL])) as wheel:
        for p in SO:
            b=contents['audit/gate2c1/vendor/'+p]
            if wheel.read(p)!=b or sha(b)!=manifest['distribution_files_sha256'][p]:
                raise ValueError('original .so binding mismatch')
    out.mkdir(parents=True)
    bundle=out/'gate2c1.bundle'
    subprocess.run(['git','bundle','create',str(bundle),'--all','HEAD'],cwd=ROOT,check=True)
    subprocess.run(['git','bundle','verify',str(bundle)],cwd=ROOT,check=True,capture_output=True)
    contents['git/gate2c1.bundle']=bundle.read_bytes()
    hashes={p:sha(b) for p,b in sorted(contents.items())}
    d={'schema':'gate2c1-complete-audit-package-v1','git_head':head,'required_members':REQUIRED,
       'files':hashes,'zip_hash_location':'external delivery_receipt.json / DELIVERY.md / .sha256',
       'fresh_independent_final_audit':'PENDING'}
    filename='gate2c1-complete-audit-2026-10-02.zip'
    target=out/filename
    with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p,b in sorted(contents.items()):z.writestr(p,b)
        z.writestr('PACKAGE_MANIFEST.json',(json.dumps(d,indent=2)+'\n').encode())
    validate_members(target,hashes,REQUIRED)
    digest=sha(target.read_bytes())  # ZIP is already closed/final here
    receipt={'schema':'gate2c1-final-delivery-receipt-v1','zip_file':filename,'zip_sha256':digest,
             'zip_bytes':target.stat().st_size,'git_head':head,'file_manifest_count':len(hashes),
             'wheel_bytes_present':True,'original_so_bytes_present':True,'required_presence_and_hash_test':'PASS',
             'fresh_independent_final_audit':'PENDING'}
    (out/'delivery_receipt.json').write_bytes((json.dumps(receipt,indent=2)+'\n').encode())
    (out/'DELIVERY.md').write_text(f'# Gate 2C.1 감사 전달 파일\n\n이 파일 하나를 전달합니다: `{filename}`\n\nSHA-256: `{digest}`\n\nGit HEAD: `{head}`\n\nwheel/.so 원본 bytes, fixtures, trace, exact checks, plan/method/result/charter, bundle과 manifest가 포함됩니다.\n\nGate 2C는 PROVISIONAL / CONDITIONAL. Gate 2C.1 새 최종 독립 감사 PENDING.\n',encoding='utf-8')
    (out/(filename+'.sha256')).write_text(f'{digest}  {filename}\n',encoding='ascii')
    verify_delivery(out)
    print(json.dumps(receipt,indent=2))

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--out',required=True);ap.add_argument('--verify',action='store_true');a=ap.parse_args()
    if a.verify:print(verify_delivery(a.out))
    else:build(a.out)
