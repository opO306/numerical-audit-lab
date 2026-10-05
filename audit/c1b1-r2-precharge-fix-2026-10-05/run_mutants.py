"""Isolated actual source edits. Author semantic mutation evidence only."""
import hashlib,json,pathlib,shutil,subprocess,sys,tempfile,xml.etree.ElementTree as ET

ROOT=pathlib.Path(__file__).resolve().parents[2]
OUT=ROOT/'current/c1b1-r2-precharge-fix-2026-10-05'/'mutants'
PHYSICAL='tests/test_impulse_reference_producer.py::test_private_whole_vector_matches_diagnostic'
BRANCH='tests/test_impulse_reference_boundaries.py::test_tt_and_leading_branches_against_separate_exact_series'
CATALOG=[
 ('R2-PRECHARGE-ACCOUNTING','producer.py','r2=c.fraction(0,1)\n        for x in parsed.q:\n            r2=c.qadd(r2,c.qmul(x,x))','r2=sum((x*x for x in parsed.q),Q(0))','tests/test_impulse_r2_precharge.py::test_canonical_r2_stops_before_disallowed_operation','At low caps the direct Fraction R2 corridor executes uncharged products and reaches sqrt; accounted baseline stops before disallowed arithmetic'),
 ('force-sign','producer.py','mul(neg(vp),reciprocal(radius,c),c)','mul(vp,reciprocal(radius,c),c)',PHYSICAL,'Nonzero off-axis analytic diagnostic sign differs'),
 ('half-step','producer.py','point(Q(20*(1<<80)))','point(Q(40*(1<<80)))',PHYSICAL,'Full step doubles once-rounded impulse'),
 ('inverse-R','producer.py','mul(neg(vp),reciprocal(radius,c),c)','mul(neg(vp),point(1),c)',PHYSICAL,'Missing radial division changes nonunit radius impulse'),
 ('R-power','derivative.py','power(term.radius,-2*term.k-1,c)','power(term.radius,-2*term.k,c)','tests/test_impulse_reference_boundaries.py::test_exact_long_derivative_identity','Exact rational derivative 9/16 differs'),
 ('TT-derivative','potential.py','slope=mul(mul(eta,e,c),term,c)','slope=point(0)',BRANCH,'Independent exact TT last-term slope containment fails'),
 ('BO-gprime','potential.py','slope=add(slope,gp,c)','slope=slope',BRANCH,'Independent quotient derivative nonzero contribution absent'),
 ('exp-sign','exp_enclosure.py','ylo, yhi, s = x.lo, x.hi, 0','ylo, yhi, s = -x.hi, -x.lo, 0','tests/test_impulse_reference_primitives.py::test_exp_contains_independent_alternating_series','Positive exponential instead of negative fails independent alternating bracket'),
 ('component-swap','producer.py','for q in parsed.q)','for q in (parsed.q[1],parsed.q[0],parsed.q[2]))',PHYSICAL,'Distinct q axes mismatch independently computed impulses'),
 ('ties-away','rounding.py','return floor if floor % 2 == 0 else increment(floor)','return increment(floor)','tests/test_impulse_reference_primitives.py::test_even_odd_cell_and_negative_ties','Even exact tie 5/2 must map to 2; same old semantic mutation rebased onto checked increment'),
 ('ROUND-ADD-ACCOUNTING','rounding.py','return value + 1 if c is None else c.add(value,1)','return value + 1','tests/test_impulse_round_add_accounting.py::test_increment_refuses_before_add','Checked account omitted: baseline refuses both 7/4 and negative odd tie at below-add caps; mutant returns raw'),
 ('QDIV-SIGN-ACCOUNTING','resource.py','numerator = self.multiply(numerator, sign)','numerator = numerator * sign','tests/test_impulse_qdiv_sign_accounting.py::test_qdiv_sign_refuses_under_complete_cost','At cap40/43 baseline refuses before normalization; direct sign multiply returns unaccounted qdiv result'),
 ('inverse-endpoints','interval.py','return Interval(c.qdiv(Q(1), a.hi), c.qdiv(Q(1), a.lo),c)','return Interval(c.qdiv(Q(1), a.lo), c.qdiv(Q(1), a.hi),c)','tests/test_impulse_reference_primitives.py::test_positive_reciprocal_and_integer_power','Valid [2,4] inverse must enclose [1/4,1/2]'),
 ('inward-rounding','interval.py','lo, _ = scaled(a.lo)','lo, lo_rem = scaled(a.lo)\n    lo = c.add(lo,int(lo_rem != 0))','tests/test_impulse_reference_boundaries.py::test_negative_power_exact_and_outward_dyadic','Negative rational lower endpoint rounded inward'),
 ('early-accept','rounding.py','if not fits:','if not fits and False:','tests/test_impulse_reference_primitives.py::test_even_odd_cell_and_negative_ties','Ambiguous [0.49,0.51] must not resolve raw 0'),
 ('resource-guard','resource.py','if bits > self.bit_max:','if bits > self.bit_max and False:','tests/test_impulse_mutant_resource_probe.py::test_small_resource_guard','64-bit shift exceeds 32-bit cap before a small safe allocation'),
 ('wrong-spec','contracts.py',"if obj['spec_sha256']!=spec.sha256:","if obj['spec_sha256']!=spec.sha256 and False:",'tests/test_impulse_reference_boundaries.py::test_wrong_spec_refused_and_failure_path_immutable','Wrong request spec must yield binding refusal'),
 ('intermediate-quantization','producer.py','radius=sqrt_enclosure(r2,n,c)','radius=sqrt_enclosure(r2,n,c)\n            radius=point(Q(round(radius.lo*(1<<48)),1<<48))',PHYSICAL,'Irrational sqrt41 rounded to FX48 loses whole-expression containment'),
 ('exp-cutoff','exp_enclosure.py','if x.lo == x.hi == 0:','if x.lo>50:\n        return Interval(Q(0),Q(0)),0,0\n    if x.lo == x.hi == 0:','tests/test_impulse_reference_primitives.py::test_large_exp_no_cutoff_and_tail_order_limit','Exact exp(-100) positive; fixed zero cutoff fails')]

def run(root,node,log,xml):
    command=[sys.executable,'-m','pytest','-q',node,'--junitxml='+str(xml)]
    r=subprocess.run(command,cwd=root,capture_output=True,timeout=60)
    log.write_bytes(r.stdout+r.stderr)
    tree=ET.parse(xml);cases=list(tree.iter('testcase'))
    return dict(command=command,exit=r.returncode,tests=len(cases),
        failed=[c.attrib['name'] for c in cases if c.find('failure') is not None],
        errors=[c.attrib['name'] for c in cases if c.find('error') is not None],
        skipped=[c.attrib['name'] for c in cases if c.find('skipped') is not None])

def main():
    OUT.mkdir(exist_ok=False);results=[]
    for name,file,before,after,node,meaning in CATALOG:
        item=OUT/name;item.mkdir()
        with tempfile.TemporaryDirectory(prefix='impulse-mutant-') as tmp:
            shadow=pathlib.Path(tmp)
            shutil.copytree(ROOT/'independent_checker',shadow/'independent_checker',ignore=shutil.ignore_patterns('__pycache__'))
            shutil.copytree(ROOT/'specs',shadow/'specs')
            shutil.copytree(ROOT/'tests',shadow/'tests',ignore=shutil.ignore_patterns('__pycache__'))
            shutil.copyfile(ROOT/'pytest.ini',shadow/'pytest.ini')
            source=shadow/'independent_checker/c1b1/impulse'/file
            original=source.read_bytes();newline=b'\r\n' if b'\r\n' in original else b'\n'
            old=before.encode().replace(b'\n',newline);new=after.encode().replace(b'\n',newline)
            if original.count(old)!=1:raise RuntimeError('nonunique actual mutation '+name)
            baseline=run(shadow,node,item/'baseline.txt',item/'baseline.xml')
            if baseline['exit']!=0 or baseline['skipped']:raise RuntimeError('baseline failed '+name)
            changed=original.replace(old,new);source.write_bytes(changed)
            # Ensure the second process cannot reuse an mtime/size-matched pyc.
            for cache in (shadow/'independent_checker/c1b1/impulse').glob('__pycache__/*.pyc'):cache.unlink()
            mutant=run(shadow,node,item/'mutant.txt',item/'mutant.xml')
            (item/'source-before.py').write_bytes(original);(item/'source-mutant.py').write_bytes(changed)
            detected=mutant['exit']==1 and bool(mutant['failed']) and not mutant['errors'] and not mutant['skipped']
            result=dict(name=name,source=file,source_before_sha256=hashlib.sha256(original).hexdigest(),
                mutant_source_sha256=hashlib.sha256(changed).hexdigest(),actual_edit=dict(before=before,after=after),
                fixture=node,semantic_detection=meaning,baseline=baseline,mutant=mutant,
                verdict='DETECTED' if detected else 'NOT_DETECTED')
            results.append(result);print(name,result['verdict'],flush=True)
    (OUT/'results.json').write_text(json.dumps(dict(scope='AUTHOR SOURCE SEMANTIC MUTANTS; NOT INDEPENDENT AUDIT',
        results=results),indent=2)+'\n')
    if any(r['verdict']!='DETECTED' for r in results):raise SystemExit(1)

if __name__=='__main__':main()
