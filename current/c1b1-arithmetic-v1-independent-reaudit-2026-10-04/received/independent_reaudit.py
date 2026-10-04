"""Limited F-CLAIM-1 re-audit. No author tests, reports, or serializers as oracles.

Run with Python's ordinary 4300-digit setting. Source packages are loaded from
byte-verified snapshots; source mutants exist only in separate local copies.
The independent decimal oracle uses small base-10**9 chunks, not full-int str().
"""
from pathlib import Path
from dataclasses import asdict
from fractions import Fraction
import argparse, ast, copy, hashlib, importlib, json, platform, shutil, sys, types

SPEC = '3217fc38aa798fff3ffea8072cecafaecac9f98be85589e9fa35a9dc6aa8119b'
OLD = 'f806d8ce1ef86a0948b1a8abafe1a22c3058178b'
TARGET = '65d8fd29ae255529afead70289098d36b825b3b4'
EXPECTED_FAILURE = dict(code='CLAIM_OUTPUT_LIMIT', phase='claim_output', atom='', component='',
    message='canonical computed integer exceeds Claim V1 4096 decimal digits',
    scope='ARITHMETIC_ONLY', j_status='J_NOT_VERIFIED', spec_sha256=SPEC)


def decimal_text(n):
    """Exact independent integer rendering, using at most nine-digit conversions."""
    negative = n < 0
    a = abs(n)
    chunks = []
    while a:
        a, low = divmod(a, 10**9)
        chunks.append(low)
    text = '0' if not chunks else str(chunks[-1]) + ''.join(str(x).zfill(9) for x in reversed(chunks[:-1]))
    return ('-' if negative else '') + text


def reduced(n, d):
    assert d > 0
    a, b = abs(n), d
    while b:
        a, b = b, a % b
    return n // a, d // a


def load_package(name, path):
    package = types.ModuleType(name)
    package.__path__ = [str(path)]
    sys.modules[name] = package
    return {key: importlib.import_module(name+'.'+key)
            for key in ('contracts','exact_slow','exact_fast','claim_adapter')}


def false_claim():
    x = 10**2150
    grid = dict(width=8,frac_bits=0,kind='signed_fx',rounding='nearest_even',overflow='refuse')
    flags = dict(scope='ARITHMETIC_ONLY', j_status='J_NOT_VERIFIED')
    z = dict(numerator='0',denominator='1')
    value = dict(type='DriftResult', **flags, spec_sha256=SPEC,
        displacement=[dict(z) for _ in range(6)], endpoint=[dict(z) for _ in range(6)],
        delta_i=['0']*3,delta_j=['0']*3,r_i=['0']*3,r_j=['0']*3,
        checked_order=['i.x','i.y','i.z','j.x','j.y','j.z'])
    return dict(schema='LAB_C1B1_CLAIM_V1',spec_sha256=SPEC,**flags,
        acquisition_id='INDEPENDENT-LIMITED-REAUDIT',record_id='ORIGINAL-F-CLAIM-1',
        phase_id='drift',operation='drift',input=dict(position_grid=dict(grid),momentum_grid=dict(grid),
        r_i=['0']*3,r_j=['0']*3,p_i=['1','0','0'],p_j=['0']*3,
        mass_i=dict(numerator=decimal_text(x+3),denominator='1'),mass_j=dict(numerator='1',denominator='1'),
        dt=dict(numerator='1',denominator=decimal_text(x+1))),
        claim=dict(type='Outcome',exception_type='',**flags,value=value))


def structured_call(c, fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except Exception as exc:
        assert type(exc) is c.LabRefusal, 'ordinary exception escaped: '+type(exc).__name__
        data = asdict(exc.failure)
        assert data == EXPECTED_FAILURE, data
        return data
    raise AssertionError('expected structured output refusal, but a value was published')


def call_claim(a, payload, path):
    # Omit path entirely for the default-path test.
    return a.compare_claim(payload) if path == 'exact_slow' else a.compare_claim(payload,path,opt_in=True)


def run(old_path, target_path, out):
    out.mkdir(parents=True,exist_ok=True)
    before_limit = sys.get_int_max_str_digits()
    assert before_limit == 4300, 'Run in the ordinary default environment; do not alter process settings.'
    setters = []
    old_profile = sys.getprofile()
    def profile(frame,event,arg):
        if event == 'c_call' and arg is sys.set_int_max_str_digits:
            setters.append(frame.f_code.co_filename)
    sys.setprofile(profile)
    old = load_package('_limited_old',old_path)
    new = load_package('_limited_new',target_path)
    report = {'old_commit':OLD,'target_commit':TARGET,'python':sys.version,'platform':platform.platform(),
              'initial_integer_string_limit':before_limit,'original':[],'boundaries':[],'end_to_end':[],
              'mutants':[], 'source_sha256':{}}
    for version,path in [('old',old_path),('target',target_path)]:
        report['source_sha256'][version] = {p.name:hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(path.iterdir()) if p.suffix in ('.py','.json','.sha256')}
    payload = false_claim()
    (out/'original_false_claim.json').write_text(json.dumps(payload,indent=2)+'\n',encoding='utf-8')
    x = 10**2150
    d = (x+1)*(x+3)
    assert 10**4300 <= d < 10**4301
    assert len(payload['input']['mass_i']['numerator']) == 2151
    assert len(payload['input']['dt']['denominator']) == 2151
    assert len(json.dumps(payload).encode()) < 1048576
    for version, mods in [('old',old),('target',new)]:
        c, a = mods['contracts'], mods['claim_adapter']
        request = c.DriftInput(c.Grid(8,0),c.Grid(8,0),(0,0,0),(0,0,0),(1,0,0),(0,0,0),
                              c.Ratio(x+3,1),c.Ratio(1,1),c.Ratio(1,x+1))
        request_before = copy.deepcopy(request)
        for path in ('exact_slow','exact_fast'):
            result = mods[path].drift(request)
            for values in (result.displacement,result.endpoint):
                assert values[0].numerator == 1 and values[0].denominator == d
                assert all(v.numerator == 0 for v in values[1:])
            assert all(getattr(result,k)==(0,0,0) for k in ('delta_i','delta_j','r_i','r_j'))
            assert request == request_before
            for form in ('dict','text','bytes'):
                argument = copy.deepcopy(payload)
                if form != 'dict':
                    argument = json.dumps(argument,separators=(',',':'))
                    if form == 'bytes': argument = argument.encode()
                saved = copy.deepcopy(argument)
                row = dict(version=version,path=path,form=form,kernel_exact=True)
                if version == 'old':
                    try: call_claim(a,argument,path)
                    except Exception as exc:
                        assert type(exc) is ValueError and not isinstance(exc,c.LabRefusal)
                        row.update(exception=type(exc).__name__,message=str(exc),historical_failure_reproduced=True)
                    else: raise AssertionError('historical defect was not reproduced')
                else:
                    row['failure'] = structured_call(c,call_claim,a,argument,path)
                assert argument == saved and request == request_before
                assert sys.get_int_max_str_digits() == before_limit
                report['original'].append(row)
    c, a = new['contracts'], new['claim_adapter']

    def boundary(label, value, n, den=None):
        untouched = copy.deepcopy(value)
        n,d0 = (n,1) if den is None else reduced(n,den)
        ns, ds = decimal_text(n), decimal_text(d0)
        nd, dd = len(ns.lstrip('-')), len(ds)
        accept = max(nd,dd) <= 4096
        if accept:
            expected = ns if den is None else dict(numerator=ns,denominator=ds)
            assert a.canonical_data(value) == expected, label
        else:
            structured_call(c,a.canonical_data,value)
        assert value == untouched
        assert sys.get_int_max_str_digits() == before_limit
        report['boundaries'].append(dict(label=label,canonical_n_digits=nd,canonical_d_digits=dd,
                                         result='ACCEPT' if accept else 'CLAIM_OUTPUT_LIMIT'))

    magnitudes=[0,10**4094,10**4095-1,10**4095,10**4096-1,10**4096,10**4096+1,10**5000+1]
    for i, magnitude in enumerate(magnitudes):
        for sign in (1,-1):
            n = sign*magnitude
            boundary('raw_%d_%d'%(i,sign),n,n)
            for kind in (c.Ratio,Fraction):
                boundary(kind.__name__+'_numerator_%d_%d'%(i,sign),kind(n,1),n,1)
                if magnitude:
                    boundary(kind.__name__+'_denominator_%d_%d'%(i,sign),kind(sign,magnitude),sign,magnitude)
    g, lim = 10**6000+7, 10**4096
    pairs=[(0,g),(2*g,6*g),(-2*g,6*g),((lim-1)*g,g),((1-lim)*g,g),
           (g,(lim-1)*g),(-g,(lim-1)*g),(lim*g,g),(-lim*g,g),(g,lim*g),(-g,lim*g)]
    for i,(n,den) in enumerate(pairs):
        for kind in (c.Ratio,Fraction): boundary(kind.__name__+'_huge_reduction_%d'%i,kind(n,den),n,den)

    # Successful exact output on the allowed 4096-digit denominator boundary.
    for sign in (1,-1):
        p = false_claim()
        p['input']['mass_i'] = dict(numerator='1',denominator='1')
        p['input']['dt'] = dict(numerator=str(sign),denominator='9'*4096)
        for field in ('displacement','endpoint'):
            p['claim']['value'][field][0] = dict(numerator=str(sign),denominator='9'*4096)
        saved=copy.deepcopy(p)
        results=[call_claim(a,p,path) for path in ('exact_slow','exact_fast')]
        assert all(r.status=='ARITHMETIC_MATCH' and r.calculation_status=='COMPUTED' for r in results)
        assert all(r.scope=='ARITHMETIC_ONLY' and r.j_status=='J_NOT_VERIFIED' for r in results)
        assert results[0].computed_json==results[1].computed_json and p==saved
        report['end_to_end'].append(dict(case='4096_digit_match',sign=sign,result='ARITHMETIC_MATCH'))

    # Valid inputs whose output only has 4097 digits, below Python's 4300 cap.
    y=10**2048
    for sign in (1,-1):
        for field in ('numerator','denominator'):
            p=false_claim()
            if field=='denominator':
                p['input']['mass_i']=dict(numerator=decimal_text(y+3),denominator='1')
                p['input']['dt']=dict(numerator=str(sign),denominator=decimal_text(y+1))
                n,den=sign,(y+1)*(y+3)
            else:
                p['input']['mass_i']=dict(numerator='1',denominator=decimal_text(y+3))
                p['input']['dt']=dict(numerator=decimal_text(sign*(y+1)),denominator='1'+'0'*4095)
                n,den=sign*(y+1)*(y+3),10**4095
            saved=copy.deepcopy(p)
            inp=p['input']
            rq=c.DriftInput(c.Grid(8,0),c.Grid(8,0),(0,0,0),(0,0,0),(1,0,0),(0,0,0),
                c.Ratio(int(inp['mass_i']['numerator']),int(inp['mass_i']['denominator'])),c.Ratio(1,1),
                c.Ratio(int(inp['dt']['numerator']),int(inp['dt']['denominator'])))
            rq0=copy.deepcopy(rq)
            failures=[]
            for path in ('exact_slow','exact_fast'):
                r=new[path].drift(rq)
                assert r.displacement[0].numerator*den == n*r.displacement[0].denominator
                assert rq==rq0
                failures.append(structured_call(c,call_claim,a,p,path))
            assert failures[0]==failures[1] and p==saved
            report['end_to_end'].append(dict(case='4097_digit_'+field,sign=sign,result='CLAIM_OUTPUT_LIMIT',
                kernel_exact=True,refusal=failures[0]))

    # An actual source edit, not a patched callable and not an assumed test result.
    mutant_dir=out/'guard_removal_mutant'
    shutil.copytree(target_path,mutant_dir,dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__'))
    fp=mutant_dir/'claim_adapter.py'
    src=fp.read_text(encoding='utf-8')
    needle='if abs(value) >= _OUTPUT_INTEGER_LIMIT:'
    assert src.count(needle)==1
    fp.write_text(src.replace(needle,'if False:'),encoding='utf-8',newline='\n')
    compile(fp.read_text(),str(fp),'exec')
    mutant=load_package('_limited_mutant',mutant_dir)
    for path in ('exact_slow','exact_fast'):
        structured_call(c,call_claim,a,false_claim(),path)
        try:
            structured_call(mutant['contracts'],call_claim,mutant['claim_adapter'],false_claim(),path)
        except AssertionError as exc:
            assert 'ordinary exception escaped: ValueError' in str(exc)
            report['mutants'].append(dict(path=path,baseline='PASS',mutant='DETECTED',cause=str(exc)))
        else: raise AssertionError('guard removal was not detected')
    report['mutant_sha256']=hashlib.sha256(fp.read_bytes()).hexdigest()
    report['mutant_edit']=[needle,'if False:']

    target_tree=ast.parse((target_path/'claim_adapter.py').read_text())
    forbidden_calls=[]
    for node in ast.walk(target_tree):
        if isinstance(node,ast.Call):
            f=node.func
            if isinstance(f,ast.Attribute) and f.attr=='set_int_max_str_digits': forbidden_calls.append(node.lineno)
            if isinstance(f,ast.Name) and f.id in ('eval','exec','__import__'): forbidden_calls.append(node.lineno)
    assert not forbidden_calls and not setters
    assert sys.get_int_max_str_digits()==before_limit
    sys.setprofile(old_profile)
    report['final_integer_string_limit']=sys.get_int_max_str_digits()
    report['process_limit_setter_calls']=setters
    report['ast_forbidden_calls']=forbidden_calls
    report['summary']={'original_old_calls':6,'original_fixed_calls':6,'boundary_cases':len(report['boundaries']),
                       'end_to_end_cases':len(report['end_to_end']),'mutant_paths_detected':len(report['mutants']),
                       'status':'PASS'}
    (out/'independent_results.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report['summary'],indent=2))
    return report

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--old',type=Path,required=True)
    parser.add_argument('--target',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    run(args.old.resolve(),args.target.resolve(),args.out.resolve())
