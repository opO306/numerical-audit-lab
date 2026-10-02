exec(open('/tmp/g2c_independent.py').read().split("if __name__=='__main__':")[0])
import json, math

def exact_step(s):
    x,y,u,v=s
    x1=x+Q(1,64)*u; y1=y+Q(1,64)*v
    gx=x1+2*x1*y1; gy=x1*x1-y1*y1+y1
    out=(x1,y1,u-Q(1,128)*gx,v-Q(1,128)*gy)
    lat=(x1,y1,u-Q(1,64)*gx,v-Q(1,64)*gy)
    return out,lat

def window(st,n=8):
    exact=tuple(q(st[k]) for k in STATE); forms=zero_forms(); bad=[]; worst=Q(0)
    for j in range(1,n+1):
        regs=run_struct(STEP,st); fo=step_forms(STEP,regs,dict(zip(STATE,forms)))
        E=[fo[k].rad() for k in OUT]; forms,IE=rebase([fo[k] for k in LAT])
        true, exact=exact_step(exact)
        for i,k in enumerate(OUT):
            r=abs(q(regs[k])-true[i]);
            if r>Q(E[i]): bad.append((j,'out',i,str(r),str(Q(E[i]))))
            if E[i]: worst=max(worst,r/Q(E[i]))
        nst=dict(zip(STATE,[regs[k] for k in LAT]))
        for i,k in enumerate(STATE):
            r=abs(q(nst[k])-exact[i]); b=Q(forms[i].rad())
            if r>b: bad.append((j,'internal',i,str(r),str(b)))
        st=nst
    return len(bad),str(worst),bad

def do(name):
 rows=load(name); init_in={k:rows[i][0] for i,k in enumerate(('x','y','vx','vy'))}; init=run_struct(INIT,init_in)
 st={k:init[k] if k in ('vhx','vhy') else init_in[k] for k in STATE}
 keep={0:dict(st)}
 for j in range(1,100001):
   regs=run_struct(STEP,st); st=dict(zip(STATE,[regs[k] for k in LAT]))
   if j in (50000,99992): keep[j]=dict(st)
 # full-state anchor check from fixture and supplied anchors
 anchor=json.load(open(f'{ROOT}/audit/gate2c_independent/payload/anchors/{name}_frozen_full_state_anchors.json'))
 for n0 in (0,50000,99992):
   print(name,n0,window(keep[n0]))
for n in ('regular','chaotic'): do(n)
