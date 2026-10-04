"""Exact static witness: stored-endpoint guard != stored-segment guard.
No repository module, impulse evaluator, benchmark or production test is run.
"""
from fractions import Fraction as Q
from pathlib import Path
import json
S=1<<48
T=1<<80
M=Q('39.9623831237')/Q('5.485799090441e-4')
RMIN=Q(1200000000000,529177210903)
THRESHOLD=RMIN**2

def ceilq(x): return -((-x.numerator)//x.denominator)
def rn(x):
    s=-1 if x<0 else 1
    n,d=abs(x.numerator),x.denominator
    k,r=divmod(n,d)
    if 2*r>d or (2*r==d and k%2): k+=1
    return s*k

def dot(a,b): return sum((x*y for x,y in zip(a,b)),Q(0))
def segment(a,b):
    v=tuple(y-x for x,y in zip(a,b)); A=dot(a,a);B=dot(a,v);C=dot(v,v)
    if C==0 or B>=0:return Q(0),A
    if -B>=C:return Q(1),dot(b,b)
    return -B/C,A-B*B/C

def pair(q):q=Q(q);return {'n':str(q.numerator),'d':str(q.denominator)}

y=ceilq(RMIN*S)
# One raw momentum unit produces gamma raw-position units during a full drift.
gamma=Q(40,1)/(M*(1<<32))
pi_y=ceilq(Q(1,2)/gamma)
pj_y=pi_y-1
pj_x=rn(Q(-11)*M*T/40)
ri=(0,0,0);rj=(10*S,y,0);pi=(0,pi_y,0);pj=(pj_x,pj_y,0)
for vec in (ri,rj,pi,pj): assert all(-(1<<95)<=x<(1<<95) for x in vec)
assert Q(1,2)<pi_y*gamma<1 and 0<pj_y*gamma<Q(1,2)
di=tuple(Q(p,T)*40/M for p in pi);dj=tuple(Q(p,T)*40/M for p in pj)
idelta=tuple(rn(x*S) for x in di);jdelta=tuple(rn(x*S) for x in dj)
assert idelta==(0,1,0) and jdelta==(-11*S,0,0)
ri1=tuple(a+b for a,b in zip(ri,idelta));rj1=tuple(a+b for a,b in zip(rj,jdelta))
for vec in (idelta,jdelta,ri1,rj1): assert all(-(1<<95)<=x<(1<<95) for x in vec)
q0=tuple(Q(b-a,S) for a,b in zip(ri,rj))
q1=tuple(Q(b-a,S)+db-da for a,b,da,db in zip(ri,rj,di,dj))
qstored=tuple(Q(b-a,S) for a,b in zip(ri1,rj1))
te,me=segment(q0,q1);ts,ms=segment(q0,qstored);endpoint=dot(qstored,qstored)
assert me>THRESHOLD and endpoint>THRESHOLD and ms<THRESHOLD
out={'purpose':'STATIC EXACT GUARD-CONTRACT COUNTEREXAMPLE; NOT IMPULSE IMPLEMENTATION OR TRAJECTORY VALIDATION',
     'position_grid':[96,48],'momentum_grid':[96,80],'full_dt':pair(40),'mass':pair(M),
     'r_i_raw':[str(x) for x in ri],'r_j_raw':[str(x) for x in rj],
     'p_i_raw':[str(x) for x in pi],'p_j_raw':[str(x) for x in pj],
     'delta_i_raw':[str(x) for x in idelta],'delta_j_raw':[str(x) for x in jdelta],
     'r_i_new_raw':[str(x) for x in ri1],'r_j_new_raw':[str(x) for x in rj1],
     'r_min_squared':pair(THRESHOLD),'q0':[pair(x) for x in q0],
     'q1_exact':[pair(x) for x in q1],'q1_stored':[pair(x) for x in qstored],
     'exact_segment_tau':pair(te),'exact_segment_min':pair(me),
     'stored_segment_tau':pair(ts),'stored_segment_min':pair(ms),'stored_endpoint_R2':pair(endpoint),
     'exact_segment_minus_threshold':pair(me-THRESHOLD),
     'stored_segment_minus_threshold':pair(ms-THRESHOLD),
     'stored_endpoint_minus_threshold':pair(endpoint-THRESHOLD),
     'old_contract_accepts':True,'new_stored_segment_requirement_accepts':False,
     'D_valid_or_integrator_admission_claimed':False,
     'kernel_execution_performed':False,'impulse_calculation_performed':False}
p=Path(__file__).with_name('guard_contract_witness.json');p.write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({k:out[k] for k in ('r_i_raw','r_j_raw','p_i_raw','p_j_raw','delta_i_raw','delta_j_raw','old_contract_accepts','new_stored_segment_requirement_accepts')},indent=2))
