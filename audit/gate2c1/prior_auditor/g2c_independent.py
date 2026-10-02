import sys, gzip, struct, math, time
from fractions import Fraction as Q
sys.path.insert(0,'/mnt/data/gate2c_audit/numerical-audit-lab-recovered-2026-10-01')
from lab.v2_bound import step_forms,rebase,zero_forms

ROOT='/mnt/data/gate2c_audit/numerical-audit-lab-recovered-2026-10-01'
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
    return [C('ADD','ax'+t,('gz',x)), C('MUL','xy'+t,(x,y)), C('ADD','dbl'+t,('xy'+t,'xy'+t)), C('ADD','gx'+t,('ax'+t,'dbl'+t)),
            C('MUL','xx'+t,(x,x)),C('MUL','yy'+t,(y,y)),C('SUB','diff'+t,('xx'+t,'yy'+t)),C('ADD','ay'+t,('gz',y)),C('ADD','gy'+t,('diff'+t,'ay'+t))]
def constants(): return [C('CONST','dt',(), '1/64'),C('CONST','half',(),'1/2'),C('CONST','gz',(),'0'),C('MUL','hhalf',('dt','half'))]
INIT=constants()+grad_actual('x','y','i')+[C('MUL','kx',('gxi','hhalf')),C('SUB','vhx',('vx','kx')),C('MUL','ky',('gyi','hhalf')),C('SUB','vhy',('vy','ky'))]
STEP=constants()+[C('MUL','dx',('dt','vhx')),C('ADD','x1',('x','dx')),C('MUL','dy',('dt','vhy')),C('ADD','y1',('y','dy'))]+grad_actual('x1','y1','s')+[C('MUL','kx',('gxs','hhalf')),C('SUB','vox',('vhx','kx')),C('MUL','gdx',('dt','gxs')),C('SUB','vhx1',('vhx','gdx')),C('MUL','ky',('gys','hhalf')),C('SUB','voy',('vhy','ky')),C('MUL','gdy',('dt','gys')),C('SUB','vhy1',('vhy','gdy'))]

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
def orbit(name,N=100000):
    rows=load(name); init_in={k:rows[i][0] for i,k in enumerate(('x','y','vx','vy'))}
    init=run_struct(INIT,init_in)
    st={k:init[k] if k in ('vhx','vhy') else init_in[k] for k in STATE}
    ff=step_forms(INIT,init,dict(zip(('x','y','vx','vy'),zero_forms())))
    forms,_=rebase([ff[k] for k in STATE])
    lst={k:rows[i][0] for i,k in enumerate(LAB_STATE)}; lf=zero_forms()
    first_h=None; first_cross=None; first_inf_bin=None; first_inf_lab=None; raw_bad=0; replay_mis=None
    marks={}
    t=time.time()
    for j in range(1,N+1):
        regs=run_struct(STEP,st)
        if replay_mis is None:
            for i,k in enumerate(OUT):
                if regs[k]!=rows[i][j]: replay_mis=(j,i,hex(regs[k]),hex(rows[i][j])); break
        fo=step_forms(STEP,regs,dict(zip(STATE,forms)))
        E=[fo[k].rad() for k in OUT]
        forms,IE=rebase([fo[k] for k in LAT])
        if first_inf_bin is None and (any(not math.isfinite(x) for x in E+IE)): first_inf_bin=j
        scale=maxscale([regs[k] for k in OUT])
        if first_h is None and (any(not math.isfinite(x) for x in E) or max(Q(x) for x in E)>=scale): first_h=j
        # lab
        lr=run_any(LAB,lst)
        lfo=step_forms(LAB,lr,dict(zip(LAB_STATE,lf)))
        F=[lfo[k].rad() for k in LAB_OUT]
        lf,IF=rebase([lfo[k] for k in LAB_OUT])
        if first_inf_lab is None and any(not math.isfinite(x) for x in F+IF): first_inf_lab=j
        a=[regs[k] for k in OUT]; b=[lr[k] for k in LAB_OUT]
        if all(math.isfinite(x) for x in E+F):
            sums=[Q(x)+Q(y) for x,y in zip(E,F)]; residual=[abs(q(x)-q(y)) for x,y in zip(a,b)]
            bad=[i for i,(r,s) in enumerate(zip(residual,sums)) if r>s]; raw_bad += len(bad)
            cscale=max(maxscale(a),maxscale(b))
            if first_cross is None and max(sums)>=cscale: first_cross=j
        elif first_cross is None: first_cross=j
        if j in (13661,13662,13663,13664,13905,13906,13907,13908,13734,13735,13952,13953,100000):
            marks[j]={'E':E,'F':F,'scale':str(scale),'out':[str(q(x)) for x in a]}
            if all(math.isfinite(x) for x in E+F):
                marks[j]['sum']=[str(Q(x)+Q(y)) for x,y in zip(E,F)]; marks[j]['res']=[str(abs(q(x)-q(y))) for x,y in zip(a,b)]; marks[j]['cscale']=str(max(maxscale(a),maxscale(b)))
        st=dict(zip(STATE,[regs[k] for k in LAT])); lst=dict(zip(LAB_STATE,[lr[k] for k in LAB_OUT]))
        if j%10000==0: print(name,j,'h',first_h,'cross',first_cross,'inf',first_inf_bin,first_inf_lab,'raw',raw_bad,'sec',round(time.time()-t,1),flush=True)
    return {'first_h':first_h,'first_cross':first_cross,'first_inf_bin':first_inf_bin,'first_inf_lab':first_inf_lab,'raw_bad':raw_bad,'replay_mis':replay_mis,'marks':marks}

if __name__=='__main__':
    import json
    r={}
    r['chaotic']=orbit('chaotic',15000)
    open('/tmp/g2c_independent_results.json','w').write(json.dumps(r,indent=2))
    print(json.dumps({k:{x:v[x] for x in ('first_h','first_cross','first_inf_bin','first_inf_lab','raw_bad','replay_mis')} for k,v in r.items()},indent=2))
