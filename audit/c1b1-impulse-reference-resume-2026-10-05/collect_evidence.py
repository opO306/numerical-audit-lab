"""Author evidence collector. Does not commit, push, activate or invoke V2."""
import ast,hashlib,json,pathlib,subprocess,sys,xml.etree.ElementTree as ET
from datetime import datetime,timezone

ROOT=pathlib.Path(__file__).resolve().parents[2]
OUT=ROOT/'current/c1b1-impulse-reference-resume-2026-10-05'
PROTECTED=['exact_slow.py','exact_fast.py','exact_geometry.py','compare.py','contracts.py',
           'claim_adapter.py','semantic_manifest_v1.json','semantic_manifest_v1.sha256']

def sha(data):return hashlib.sha256(data).hexdigest()
def save(name,value):(OUT/name).write_text(json.dumps(value,indent=2,ensure_ascii=True)+'\n',encoding='ascii')

def main():
    baseline=json.loads((OUT/'baseline.json').read_text(encoding='utf8'));old=baseline['tracked_raw_sha256']
    changed=[];missing=[];unchanged=0
    for p,h in old.items():
        path=ROOT/p
        if not path.exists():missing.append(p)
        elif sha(path.read_bytes())==h:unchanged+=1
        else:changed.append(p)
    protected={}
    for name in PROTECTED:
        p='independent_checker/c1b1/'+name
        git65=subprocess.check_output(['git','show','65d8fd29ae255529afead70289098d36b825b3b4:'+p],cwd=ROOT)
        actual=sha((ROOT/p).read_bytes());protected[p]=dict(raw_sha256=actual,
            equal_bc6=actual==old[p],equal_65d8=actual==sha(git65))
        if name in ('exact_slow.py','exact_fast.py','exact_geometry.py'):
            protected[p]['equal_f806']=actual==sha(subprocess.check_output(['git','show','f806d8ce1ef86a0948b1a8abafe1a22c3058178b:'+p],cwd=ROOT))
    earlier=json.loads((ROOT/'current/c1b1-impulse-reference-2026-10-05/receipt-before.json').read_text(encoding='utf8'))
    previous_hashes=earlier['tracked_raw_sha256']
    arithmetic_before=json.loads((ROOT/'current/c1b1-claim-output-fix-2026-10-04/preservation-before.json').read_text(encoding='utf8'))
    base1921=subprocess.check_output(['git','ls-tree','-r','--name-only','e976fa0fdeef16a27f112a0a4ee42494fe1e46b1'],cwd=ROOT).decode().splitlines()
    if len(base1921)!=1921:raise ValueError('wrong historical base inventory')
    historical1921={p:arithmetic_before['tracked_raw_sha256_before'][p] for p in base1921}
    prior_evidence=[p for p in old if p.startswith(('current/','audit/','docs/','specs/'))]
    save('preservation.json',dict(base_tracked=len(old),unchanged=unchanged,changed=changed,missing=missing,
        all_prior_evidence_byte_identical=all((ROOT/p).exists() and sha((ROOT/p).read_bytes())==old[p] for p in prior_evidence),
        prior_evidence_files=len(prior_evidence),protected=protected,
        all_approved_specs_byte_identical=all(sha((ROOT/p).read_bytes())==h for p,h in old.items() if p.startswith('specs/')),
        previous_2097_count=len(previous_hashes),previous_2097_preserved=sum(sha((ROOT/p).read_bytes())==h for p,h in previous_hashes.items()),
        historical_1921_count=len(historical1921),historical_1921_preserved=sum(sha((ROOT/p).read_bytes())==h for p,h in historical1921.items()),
        previous_receipt_preserved=sha((ROOT/'current/c1b1-impulse-reference-2026-10-05/receipt-before.json').read_bytes())==old['current/c1b1-impulse-reference-2026-10-05/receipt-before.json']))
    source=ROOT/'independent_checker/c1b1/impulse'
    hashes={p.name:sha(p.read_bytes()) for p in sorted(source.glob('*.py'))}
    imports={};forbidden=[]
    for p in sorted(source.glob('*.py')):
        tree=ast.parse(p.read_text(encoding='utf8'));items=[]
        for n in ast.walk(tree):
            if isinstance(n,ast.Import):items.extend(a.name for a in n.names)
            elif isinstance(n,ast.ImportFrom):items.append('.'*n.level+(n.module or ''))
            elif isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id in ('exec','eval','FunctionType'):
                forbidden.append(dict(file=p.name,line=n.lineno,call=n.func.id))
        imports[p.name]=sorted(set(items))
    source_bundle_sha=sha((json.dumps(hashes,sort_keys=True,separators=(',',':'),ensure_ascii=True)+'\n').encode('ascii'))
    save('source-identity.json',dict(files=hashes,source_bundle_sha256=source_bundle_sha,imports=imports,forbidden_dynamic_calls=forbidden))
    specdir=ROOT/'specs/c1b1-independent-impulse-v1-attempt-reason-null'
    package=json.loads((specdir/'package-manifest.json').read_text())
    save('dependency-graph.json',dict(spec_revision='ATTEMPT-REASON-NULL-2026-10-05',
        semantic_sha256=sha((specdir/'semantic-bundle.json').read_bytes()),
        package_sha256=sha((specdir/'package-manifest.json').read_bytes()),package=package,
        audit_target='bc6cf7a6312951ddefe4e066afa19bedfbeef695',audit_scope='LIMITED SPEC/STATIC; WIP BYTE PRESERVATION ONLY',
        spec_independent_recheck='PASS',implementation_independent_audit='PENDING'))
    cases=list(ET.parse(OUT/'logs/full-suite-after-review.xml').iter('testcase'));files={}
    for c in cases:
        d=files.setdefault(c.attrib['classname'],dict(tests=0,fail=0,error=0,skip=0))
        d['tests']+=1
        for key,node in [('fail','failure'),('error','error'),('skip','skipped')]:d[key]+=int(c.find(node) is not None)
    save('test-counts.json',dict(command='python -m pytest -q --junitxml=current/c1b1-impulse-reference-resume-2026-10-05/logs/full-suite-after-review.xml',
        total_regression_cases=len(cases),by_file=files,label='AUTHOR CHECKS; NO COUNT IS AN INDEPENDENT PROOF COUNT'))
    sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tests'))
    from impulse_reference_support import input_object,encoded,reference_policy
    from independent_checker.c1b1.impulse.producer import evaluate_reference,produce
    examples=OUT/'examples';examples.mkdir(exist_ok=True);summary=[]
    for name,q,changes in [('off-axis',(6,2,1),{}),('opposite',(-6,-2,-1),{}),
        ('zero-axis',(0,6,1),{}),('known-unproved',(0,6,1),dict(N0='1',P0='8',N_max='1',P_max='8',max_attempts='1',exp_order_max='1'))]:
        obj=input_object(q);obj['budget'].update(changes);data=encoded(obj)
        result=evaluate_reference(data,reference_policy(obj))
        (examples/(name+'-input.json')).write_bytes(data)
        if result.certificate:(examples/(name+'-private-certificate.json')).write_bytes(result.certificate)
        if result.failure:(examples/(name+'-failure.json')).write_bytes(result.failure)
        summary.append(dict(name=name,q=q,input_sha256=sha(data),layers=result.layers,raw=result.raw,
            opposite=result.opposite,account=result.account,failure=None if not result.failure else json.loads(result.failure),
            input_unchanged=data==encoded(obj),label='AUTHOR NUMERICAL EXAMPLE; PRIVATE; NOT A PHYSICAL PASS'))
    runtime=produce(encoded(input_object()));(examples/'runtime-unbound-failure.json').write_bytes(runtime.failure)
    save('producer-examples.json',dict(examples=summary,runtime_activation_allowed=False,
        runtime_failure=json.loads(runtime.failure),new_V2_numeric_calls=0,
        loaded_impulse_modules=sorted(n for n in sys.modules if n.startswith('independent_checker.c1b1.impulse')),
        forbidden_loaded_modules=sorted(n for n in sys.modules if any(token in n.lower() for token in ('mpmath','a_reference','exact_impulse_checker_v2')))))
    git={}
    for command in [['git','rev-parse','HEAD'],['git','branch','--show-current'],['git','status','--short'],['git','diff','--stat']]:
        r=subprocess.run(command,cwd=ROOT,capture_output=True)
        git[' '.join(command)]=dict(exit=r.returncode,stdout=r.stdout.decode('utf8',errors='replace'),stderr=r.stderr.decode('utf8',errors='replace'))
    save('git-state.json',git)
    save('receipt.json',dict(recorded_at_utc=datetime.now(timezone.utc).isoformat(),
        base_head='bc6cf7a6312951ddefe4e066afa19bedfbeef695',working_source_bundle_sha256=source_bundle_sha,
        status='IMPLEMENTED / AUTHOR CHECKS PASS / INDEPENDENT IMPLEMENTATION AUDIT PENDING',
        runtime_activation_allowed=False,j_status='J_NOT_VERIFIED',certification='NotCertified',
        commit_performed=False,push_performed=False,working_revision_has_no_commit_yet=True,
        author_report_sha256=sha((ROOT/'docs/C1B1_INDEPENDENT_IMPULSE_REFERENCE_AUTHOR_REPORT_2026-10-05.md').read_bytes()),
        audit_tool_sha256={p.name:sha(p.read_bytes()) for p in sorted(pathlib.Path(__file__).parent.glob('*.py'))},
        categories=['unit exact synthetic','author physical differential diagnostics','source semantic mutants',
                    'static spec checks','private numerical examples','adapter preparation only; V2 numeric NOT_RUN'],
        evidence_files={p.relative_to(OUT).as_posix():sha(p.read_bytes()) for p in sorted(OUT.rglob('*'))
                        if p.is_file() and p.name!='receipt.json'}))
    print('sources',len(hashes),'historical changed',len(changed),'preserved',unchanged,'missing',len(missing))
    print('protected8',all(r['equal_bc6'] and r['equal_65d8'] for r in protected.values()))
    print('examples',[(r['name'],r['layers']['producer']) for r in summary])

if __name__=='__main__':main()
