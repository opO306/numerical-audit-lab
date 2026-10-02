"""Auditor-origin reproduction, author-ported for 2C.1; not a fresh auditor verdict."""
import sys, gzip, struct, math, time
from fractions import Fraction as Q
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from lab.v2_bound import step_forms,rebase,zero_forms

# ROOT binding only; original artifacts remain unchanged
STATE=('x','y','vhx','vhy'); OUT=('x1','y1','vox','voy'); LAT=('x1','y1','vhx1','vhy1')
def bits(x): return struct.unpack('>Q',struct.pack('>d',x))[0]
def f(u): return struct.unpack('>d',struct.pack('>Q',u))[0]
def q(u): return Q.from_float(f(u))
def load(name):
    p=f'{ROOT}/benchmarks/gate2b/fixtures/cloud-2026-10-01/{name}_forward.u64.gz'
    raw=gzip.open(p,'rb').read(); vals=struct.unpack('<'+('Q'*(len(raw)//8)),raw)
    n=100001
    return [list(vals[i*n:(i+1)*n]) for i in range(4)]

def C(op,dst,args=(),lit=None): return (op,dst,args,lit)
# Actual machine order from frozen disassembly / Gate2B machine diagnostic: gx=(0+x)+2*(x*y)
def grad_actual(x,y,t):
    # Independently transcribed N=1 scalar-loop occurrences 1cb85..1cbb0.
    return [C('MUL','xy'+t,(y,x)),C('ADD','ax'+t,('gz',x)),C('MUL','xx'+t,(x,x)),
            C('ADD','dbl'+t,('xy'+t,'xy'+t)),C('ADD','gx'+t,('dbl'+t,'ax'+t)),
            C('MUL','yy'+t,(y,y)),C('ADD','ay'+t,(y,'gz')),
            C('SUB','diff'+t,('xx'+t,'yy'+t)),C('ADD','gy'+t,('diff'+t,'ay'+t))]
def constants():return [C('CONST','dt',(),'1/64'),C('CONST','half',(),'1/2'),C('CONST','gz',(),'0')]
INIT=constants()+grad_actual('x','y','i')+[C('MUL','hhalf',('dt','half')),
    C('MUL','kx',('gxi','hhalf')),C('SUB','vhx',('vx','kx')),C('MUL','ky',('gyi','hhalf')),C('SUB','vhy',('vy','ky'))]
STEP=constants()+[C('MUL','dx',('dt','vhx')),C('ADD','x1',('dx','x')),C('MUL','dy',('dt','vhy')),C('ADD','y1',('dy','y'))]+grad_actual('x1','y1','s')+[
    C('MUL','hhalf',('dt','half')),C('MUL','kx',('gxs','hhalf')),C('SUB','vox',('vhx','kx')),C('MUL','gdx',('dt','gxs')),C('SUB','vhx1',('vhx','gdx')),
    C('MUL','ky',('gys','hhalf')),C('SUB','voy',('vhy','ky')),C('MUL','gdy',('dt','gys')),C('SUB','vhy1',('vhy','gdy'))]

def run_struct(S,inputs):
    v={k:f(x) for k,x in inputs.items()}
    regs={k:x for k,x in inputs.items()}
    for op,dst,args,lit in S:
        if op=='CONST': z=float(Q(lit))
        else:
            a,b=v[args[0]],v[args[1]]
            if op=='ADD': z=a+b
            elif op=='SUB': z=a-b
            elif op=='MUL': z=a*b
            else: raise ValueError(op)
        v[dst]=z; regs[dst]=bits(z)
    return regs
# independent Lab velocity-Verlet program mirroring explicit source op order, no imports from gate2a
LAB_STATE=('x','y','px','py'); LAB_OUT=('x1','y1','px1','py1')
def force(sx,sy,t):
    return [C('MUL','xy'+t,(sx,sy)),C('MUL','txy'+t,('two','xy'+t)),C('NEG','nx'+t,(sx,)),C('SUB','ax'+t,('nx'+t,'txy'+t)),C('MUL','xx'+t,(sx,sx)),C('MUL','yy'+t,(sy,sy)),C('NEG','ny'+t,(sy,)),C('SUB','u'+t,('ny'+t,'xx'+t)),C('ADD','ay'+t,('u'+t,'yy'+t))]
LAB=[C('CONST','h',(),'1/64'),C('CONST','hh',(),'1/128'),C('CONST','two',(),'2')]+force('x','y','0')+[C('MUL','kx',('hh','ax0')),C('ADD','pxh',('px','kx')),C('MUL','ky',('hh','ay0')),C('ADD','pyh',('py','ky')),C('MUL','dx',('h','pxh')),C('ADD','x1',('x','dx')),C('MUL','dy',('h','pyh')),C('ADD','y1',('y','dy'))]+force('x1','y1','1')+[C('MUL','kx1',('hh','ax1')),C('ADD','px1',('pxh','kx1')),C('MUL','ky1',('hh','ay1')),C('ADD','py1',('pyh','ky1'))]
# support NEG in runner
def run_any(S,inputs):
    v={k:f(x) for k,x in inputs.items()}; regs=dict(inputs)
    for op,dst,args,lit in S:
        if op=='CONST': z=float(Q(lit))
        elif op=='NEG': z=-v[args[0]]
        else:
            a,b=v[args[0]],v[args[1]]
            z=a+b if op=='ADD' else a-b if op=='SUB' else a*b
        v[dst]=z; regs[dst]=bits(z)
    return regs

def maxscale(arr): return max(abs(q(x)) for x in arr)

import argparse
import hashlib
import json

def enc(d):
    return (json.dumps(d,sort_keys=True,ensure_ascii=False,allow_nan=False)+'\n').encode()

def bf(fs):
    return None if fs is None else [{'coefficients':[f'{bits(v):016x}' for v in z.coef],
                                    'box':f'{bits(z.box):016x}'} for z in fs]

def state(j,st,lst,forms,lf,fh,fc,bd,ld):
    return {'step':j,'bin_state':[f'{st[k]:016x}' for k in STATE],
            'lab_state':[f'{lst[k]:016x}' for k in LAB_STATE],
            'bin_forms':bf(forms),'lab_forms':bf(lf),'first_bin':fh,'first_cross':fc,
            'bin_dead':bd,'lab_dead':ld}

def write_new(path,d):
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():raise ValueError('refuse to overwrite independent evidence')
    path.write_bytes(enc(d))

def exact_step(s):
    x,y,u,v=s
    x=x+u/64;y=y+v/64
    gx=x+2*x*y;gy=x*x-y*y+y
    return (x,y,u-gx/128,v-gy/128),(x,y,u-gx/64,v-gy/64)

def local_check(st,n=8):
    exact=tuple(q(st[k]) for k in STATE);fs=zero_forms();bad=[];records=[]
    for j in range(1,n+1):
        regs=run_struct(STEP,st)
        fo=step_forms(STEP,regs,dict(zip(STATE,fs)))
        E=[fo[k].rad() for k in OUT];fs,_=rebase([fo[k] for k in LAT])
        out,exact=exact_step(exact)
        nxt=dict(zip(STATE,[regs[k] for k in LAT]))
        for i,k in enumerate(OUT):
            if not math.isfinite(E[i]) or abs(q(regs[k])-out[i])>Q(E[i]):bad.append([j,'output',i])
        for i,k in enumerate(STATE):
            if not math.isfinite(fs[i].rad()) or abs(q(nxt[k])-exact[i])>Q(fs[i].rad()):bad.append([j,'internal',i])
        records.append({'step':j,'input_latent':[f'{st[k]:016x}' for k in STATE],
                        'output':[f'{regs[k]:016x}' for k in OUT],
                        'internal':[f'{nxt[k]:016x}' for k in STATE],
                        'exact_output':[[hex(x.numerator),hex(x.denominator)] for x in out],
                        'exact_internal':[[hex(x.numerator),hex(x.denominator)] for x in exact]})
        st=nxt
    return {'violations':bad,'records':records}

def check_link(previous_end,current_start,expected_step):
    if previous_end!=current_start or current_start['step']!=expected_step:
        raise ValueError('endpoint set not identical to next segment input or coverage gap')

def compare_trace(path,program,regs):
    d=json.loads(path.read_bytes())
    if len(d['operations'])!=len(program):raise ValueError('trace length mismatch')
    for row,(op,dst,args,lit) in zip(d['operations'],program):
        if [row['op'],row['dst'],row['args'],row['literal']]!=[op,dst,list(args),lit]:
            raise ValueError('trace operation order/operand/literal mismatch')
        if row['result_bits']!=f'{regs[dst]:016x}' or row['operand_bits']!=[f'{regs[a]:016x}' for a in args]:
            raise ValueError('trace intermediate value mismatch')

def verify_orbit(name,n,producer_dir,out,deadline):
    rows=load(name)
    initial={k:rows[i][0] for i,k in enumerate(('x','y','vx','vy'))}
    init=run_struct(INIT,initial)
    compare_trace(producer_dir/'evidence/traces'/f'{name}_init.json',INIT,init)
    st={k:init[k] if k in ('vhx','vhy') else initial[k] for k in STATE}
    ff=step_forms(INIT,init,dict(zip(('x','y','vx','vy'),zero_forms())))
    fs,_=rebase([ff[k] for k in STATE])
    lst={k:rows[i][0] for i,k in enumerate(LAB_STATE)};lf=zero_forms()
    fh=fc=bd=ld=None;raw=0;mis=[];connections=[];boundary={}
    previous=None;pending=set();seen_start=state(0,st,lst,fs,lf,fh,fc,bd,ld)
    segment_start=seen_start;previous_hash=None;dh=hashlib.sha256()
    windows={0:dict(st)};done=0
    for j in range(1,n+1):
        if time.perf_counter()>=deadline:raise TimeoutError(f'budget exceeded at {name}:{j}')
        regs=run_struct(STEP,st);lr=run_any(LAB,lst)
        if j==1:compare_trace(producer_dir/'evidence/traces'/f'{name}_step1.json',STEP,regs)
        a=[regs[k] for k in OUT];b=[lr[k] for k in LAB_OUT]
        if any(a[i]!=rows[i][j] for i in range(4)):mis.append(j)
        E=F=None
        if bd is None:
            try:
                fo=step_forms(STEP,regs,dict(zip(STATE,fs)))
                E=[fo[k].rad() for k in OUT]
                fs,IE=rebase([fo[k] for k in LAT])
                if any(not math.isfinite(v) or v<0 for v in IE):
                    fs=None;raise ArithmeticError('nonfinite latent bound')
            except (ArithmeticError,ValueError,StopIteration,IndexError) as exc:
                bd={'step':j,'reason':f'{type(exc).__name__}: {exc}'};E=None
        if ld is None:
            try:
                lfo=step_forms(LAB,lr,dict(zip(LAB_STATE,lf)))
                F=[lfo[k].rad() for k in LAB_OUT]
                lf,IE=rebase([lfo[k] for k in LAB_OUT])
                if any(not math.isfinite(v) or v<0 for v in F+IE):
                    ld={'step':j,'reason':'nonfinite Lab bound'};F=None
            except (ArithmeticError,ValueError,StopIteration,IndexError) as exc:
                ld={'step':j,'reason':f'{type(exc).__name__}: {exc}'};F=None
        valid=E is not None and all(math.isfinite(v) and v>=0 for v in E)
        vp='PASS' if valid and max(Q(x) for x in E)<maxscale(a) and not mis else 'REFUSED'
        old_fh,old_fc=fh,fc
        if vp=='REFUSED' and fh is None:
            reason=bd['reason'] if bd else ('replay does not match frozen external execution' if mis else 'bound >= represented state scale')
            fh={'step':j,'reason':reason}
        sums=res=None
        cp='REFUSED';cr='bound unavailable or nonfinite'
        if E is not None and F is not None and all(math.isfinite(v) and v>=0 for v in E+F):
            sums=[Q(x)+Q(y) for x,y in zip(E,F)];res=[abs(q(x)-q(y)) for x,y in zip(a,b)]
            bad=[i for i in range(4) if res[i]>sums[i]];raw+=len(bad)
            if bad:cp='FAIL';cr='residual exceeds exact sum bound'
            elif max(sums)<max(maxscale(a),maxscale(b)):cp='PASS';cr='residual contained in exact sum bound'
            else:cr='sum bound >= represented state scale'
        if mis:cp='REFUSED';cr='external execution replay mismatch'
        if cp=='REFUSED' and fc is None:fc={'step':j,'reason':cr}
        current={'step':j,'E':[v.hex() for v in E] if E else None,
                 'F':[v.hex() for v in F] if F else None,'scale':str(maxscale(a)),
                 'cross_scale':str(max(maxscale(a),maxscale(b))),
                 'sum':[str(v) for v in sums] if sums else None,
                 'residual':[str(v) for v in res] if res else None,
                 'output':[f'{v:016x}' for v in a],'v2_verdict':vp,'cross_verdict':cp}
        if (old_fh is None and fh) or (old_fc is None and fc):
            if previous:boundary[str(j-1)]=previous
            boundary[str(j)]=current;pending.add(j+1)
        if j in pending:boundary[str(j)]=current
        previous=current
        dh.update(enc({'step':j,'bin':a,'lab':b,'E':[v.hex() for v in E] if E else None,
                       'F':[v.hex() for v in F] if F else None,'v2':vp,'cross':cp}))
        st=dict(zip(STATE,[regs[k] for k in LAT]));lst=dict(zip(LAB_STATE,b));done=j
        if j in (50000,99992):windows[j]=dict(st)
        if j%1000==0 or j==n:
            end=state(j,st,lst,fs,lf,fh,fc,bd,ld)
            path=producer_dir/'evidence/segments'/name/f'{j:06d}.json'
            blob=path.read_bytes();block=json.loads(blob)
            check_link(segment_start,block['start'],segment_start['step'])
            if block['end']!=end or block['decision_digest']!=dh.hexdigest():
                raise ValueError(f'independent recomputation mismatch at {name}:{j}')
            if block['coverage']!=[segment_start['step']+1,j] or block['previous_segment_sha256']!=previous_hash:
                raise ValueError('coverage or hash chain mismatch')
            digest=hashlib.sha256(blob).hexdigest()
            entry={'start':segment_start,'end':end,'coverage':block['coverage'],
                   'decision_digest':dh.hexdigest(),'producer_segment_sha256':digest,
                   'previous_segment_sha256':previous_hash,'connection':'RECOMPUTED_EQUAL_SETS'}
            write_new(out/'segments'/name/f'{j:06d}.json',entry)
            connections.append({'coverage':block['coverage'],'recomputed_endpoint_equal':True,'decision_digest_equal':True})
            previous_hash=digest;segment_start=end;dh=hashlib.sha256()
            if j%10000==0:print(f'independent {name} {j}/{n} first_h={fh} first_cross={fc}',flush=True)
    local={}
    for n0 in (0,50000,99992):
        if n0+8<=done and n0 in windows:
            d=local_check(windows[n0]);write_new(out/'exact'/f'{name}_{n0}_8step.json',d)
            # producer records must represent exactly the same local discrete inputs and outputs.
            p=json.loads((producer_dir/'evidence/exact'/f'{name}_{n0}_8step.json').read_bytes())
            if p['start_latent']!=[f'{windows[n0][k]:016x}' for k in STATE]:raise ValueError('local seed mismatch')
            for a,b in zip(p['records'],d['records']):
                if any(a[k]!=b[k2] for k,k2 in [('output','output'),('next_latent','internal'),('exact_output','exact_output'),('exact_internal','exact_internal')]):
                    raise ValueError('local exact discrete program mismatch')
            local[str(n0)]={'violations':len(d['violations']),'steps':8}
    return {'steps_recomputed':done,'certified_prefix':max(0,fh['step']-1) if fh else done,
            'first_refused':fh,'cross_first_refused':fc,'bin_dead':bd,'lab_dead':ld,
            'raw_violation_count':raw,'replay_mismatch_count':len(mis),
            'connections':connections,'boundary_evidence':boundary,'exact_local_windows':local}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--n',type=int,default=100000);ap.add_argument('--producer',required=True)
    ap.add_argument('--out',required=True);a=ap.parse_args()
    out=Path(a.out)
    if out.exists():ap.error('output path exists')
    if not 1<=a.n<=100000:ap.error('n must be 1..100000')
    # Independent raw-seal validation, without importing producer adapters.
    for name,h in [('plan','d61dbaf1ab438ca2ac542e784edbb4b9656c4614cdf05116fdaedc56df783743'),
                   ('method','5be5e6f8541baf9c489a26a14007f77bca02da9f84019aca694ddc7f09a5974e')]:
        p=ROOT/f'audit/gate2c1/{name}_seal.json'
        if hashlib.sha256(p.read_bytes()).hexdigest()!=h:raise ValueError('independent seal failure')
        d=json.loads(p.read_bytes())
        for path,expected in {**d['files'],**d.get('preserve_prior_raw_files',{})}.items():
            if hashlib.sha256((ROOT/path).read_bytes()).hexdigest()!=expected:raise ValueError(f'changed input {path}')
    def code_check():
        p=ROOT/'audit/gate2c1/code_seal.json'
        if a.n==100000 and not p.exists():raise ValueError('full independent run requires code seal')
        if p.exists():
            for path,expected in json.loads(p.read_bytes())['files'].items():
                if hashlib.sha256((ROOT/path).read_bytes()).hexdigest()!=expected:raise ValueError(f'code seal failure {path}')
    code_check()
    start=time.perf_counter();results={};failure=None
    try:
        for name in ('regular','chaotic'):
            results[name]=verify_orbit(name,a.n,Path(a.producer),out,start+3600)
        code_check()
    except Exception as exc:
        failure=f'{type(exc).__name__}: {exc}'
    d={'schema':'gate2c1-auditor-origin-reproduction-v1',
       'role':'AUTHOR_PORTED_AUDITOR_PATH_NOT_FRESH_FINAL_AUDIT','orbits':results,'failure':failure,
       'N':a.n,'wall_seconds':time.perf_counter()-start,
       'audit_status':'PENDING','source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    write_new(out/'independent_report.json',d)
    print(json.dumps({k: {x:v[x] for x in ('steps_recomputed','certified_prefix','first_refused','cross_first_refused','raw_violation_count','exact_local_windows')} for k,v in results.items()},indent=2))
    if failure:print(failure)
    return 1 if failure else 0

if __name__=='__main__':sys.exit(main())
