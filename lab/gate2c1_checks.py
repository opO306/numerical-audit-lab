"""Checker side: four latent error forms, exact cross sums, independent Fraction map.

Does not import the calculator. Executor/structures are supplied by the runner.
V2 itself remains frozen; Gate 2C.1 has not received independent audit approval.
"""
import hashlib
import json
import math
from fractions import Fraction as Q
from pathlib import Path

from lab.gate2b_fixture import qval
from lab.v2_bound import rebase, step_forms, zero_forms

STATE=('x','y','vhx','vhy')
LATENT_OUT=('x1','y1','vhx1','vhy1')
OUTPUT=('x1','y1','vox','voy')
PLAN_SEAL_SHA256='d61dbaf1ab438ca2ac542e784edbb4b9656c4614cdf05116fdaedc56df783743'
METHOD_SEAL_SHA256='5be5e6f8541baf9c489a26a14007f77bca02da9f84019aca694ddc7f09a5974e'


def verify_seals(root=None):
    root=Path(root) if root else Path(__file__).resolve().parents[1]
    for name,h in [('plan',PLAN_SEAL_SHA256),('method',METHOD_SEAL_SHA256)]:
        p=root/f'audit/gate2c1/{name}_seal.json'
        if hashlib.sha256(p.read_bytes()).hexdigest()!=h:
            raise RuntimeError(f'{name} seal changed')
        d=json.loads(p.read_bytes())
        for path,expected in {**d['files'],**d.get('preserve_prior_raw_files',{})}.items():
            if hashlib.sha256((root/path).read_bytes()).hexdigest()!=expected:
                raise RuntimeError(f'sealed input changed: {path}')
    p=root/'audit/gate2c1/code_seal.json'
    if p.exists():
        for path,expected in json.loads(p.read_bytes())['files'].items():
            if hashlib.sha256((root/path).read_bytes()).hexdigest()!=expected:
                raise RuntimeError(f'sealed code changed: {path}')
    return {'plan_seal_sha256':PLAN_SEAL_SHA256,'method_seal_sha256':METHOD_SEAL_SHA256,'inputs':'UNCHANGED'}


def valid_forms(forms):
    return len(forms)==4 and all(len(f.coef)==4 and math.isfinite(f.box) and f.box>=0
                                and all(math.isfinite(v) for v in f.coef) for f in forms)


class BinBound:
    def __init__(self,init_structure,step_structure):
        from lab.gate2c1_contract import assert_machine_structure
        assert_machine_structure(init_structure,'init')
        assert_machine_structure(step_structure,'step')
        self.init_structure,self.step_structure=init_structure,step_structure
        self.forms=None

    def init(self,regs):
        f=step_forms(self.init_structure,regs,dict(zip(('x','y','vx','vy'),zero_forms())))
        forms,E=rebase([f[s] for s in STATE])
        if any(not math.isfinite(v) or v<0 for v in E) or not valid_forms(forms):
            raise ArithmeticError('nonfinite initial latent bound')
        self.forms=forms

    def step(self,regs):
        if self.forms is None:
            raise ValueError('BinBound requires init or explicit local zero forms')
        out=step_forms(self.step_structure,regs,dict(zip(STATE,self.forms)))
        E=[out[k].rad() for k in OUTPUT]
        self.forms,internal_E=rebase([out[k] for k in LATENT_OUT])
        if any(not math.isfinite(v) or v<0 for v in internal_E) or not valid_forms(self.forms):
            self.forms=None
            raise ArithmeticError('nonfinite latent bound')
        return E


def output_status(state_bits,bounds):
    if bounds is None or len(bounds)!=4 or len(state_bits)!=4:
        return 'REFUSED','bound unavailable'
    if any(not math.isfinite(v) or v<0 for v in bounds):
        return 'REFUSED','nonfinite output bound'
    try:
        scale=max(abs(qval(v)) for v in state_bits)
    except (ValueError,OverflowError):
        return 'REFUSED','nonfinite represented state'
    if max(Q(v) for v in bounds)>=scale:
        return 'REFUSED','bound >= represented state scale'
    return 'PASS','finite bound smaller than represented state scale'


def display_float(q):
    """Display only: exact decision values stay rational. None denotes display overflow."""
    try:
        v=float(q)
        return v if math.isfinite(v) else None
    except OverflowError:
        return None


def cross_check(a,b,e,f):
    if e is None or f is None or any(len(v)!=4 for v in (a,b,e,f)) or any(not math.isfinite(v) or v<0 for v in e+f):
        return {'verdict':'REFUSED','reason':'bound unavailable or nonfinite','raw_enclosure_violations':[], 'sum_bounds_q':None}
    try:
        qa,qb=[qval(x) for x in a],[qval(x) for x in b]
    except (ValueError,OverflowError):
        return {'verdict':'REFUSED','reason':'nonfinite represented state','raw_enclosure_violations':[], 'sum_bounds_q':None}
    sums=[Q(x)+Q(y) for x,y in zip(e,f)]
    residual=[abs(qval(x)-qval(y)) for x,y in zip(a,b)]
    bad=[i for i,(r,s) in enumerate(zip(residual,sums)) if r>s]
    scale=max(abs(qval(v)) for v in a+b)
    refused=max(sums)>=scale
    ratio=None if any(r and not s for r,s in zip(residual,sums)) else display_float(max((r/s if s else Q(0)) for r,s in zip(residual,sums)))
    return {'verdict':'FAIL' if bad else ('REFUSED' if refused else 'PASS'),
            'reason':'residual exceeds exact sum bound' if bad else ('sum bound >= represented state scale' if refused else 'residual contained in exact sum bound'),
            'raw_enclosure_violations':bad,'sum_bounds_q':[str(s) for s in sums],
            'max_residual':display_float(max(residual)), 'max_sum_bound':display_float(max(sums)),
            'max_residual_over_bound':ratio}


def replay_comparison(t,rows):
    initial=[rows[c][0] for c in range(4)]
    regs=t.init(*initial)
    st=(initial[0],initial[1],regs['vhx'],regs['vhy'])
    first=None
    for j in range(1,len(rows[0])):
        regs=t.step(*st)
        for c,k in enumerate(OUTPUT):
            if first is None and regs[k]!=rows[c][j]:
                first={'step':j,'component':c}
        st=tuple(regs[k] for k in LATENT_OUT)
    return {'first_mismatch':first,'steps_checked':len(rows[0])-1}


def exact_latent_step(s):
    """Independent exact mathematical map, with no replay program or V2 internals used."""
    x,y,u,v=s
    x,y=x+u/64,y+v/64
    gx,gy=x+2*x*y,y+x*x-y*y
    output=(x,y,u-gx/128,v-gy/128)
    return output,(x,y,u-gx/64,v-gy/64)


def exact_window(t,start,n=8):
    st=tuple(start)
    exact=tuple(qval(v) for v in st)
    b=BinBound(t.init_structure,t.step_structure)
    b.forms=zero_forms()
    violations=[]
    records=[]
    worst=Q(0)
    for j in range(1,n+1):
        previous=st
        regs=t.step(*st)
        E=b.step(regs)
        true,exact=exact_latent_step(exact)
        def ratio(v):return [hex(v.numerator),hex(v.denominator)]
        records.append({'step':j,'represented_input_latent':[f'{v:016x}' for v in previous],
                        'output':[f'{regs[k]:016x}' for k in OUTPUT],
                        'next_latent':[f'{regs[k]:016x}' for k in LATENT_OUT],
                        'exact_output':[ratio(v) for v in true], 'exact_internal':[ratio(v) for v in exact],
                        'output_bounds':[v.hex() for v in E],
                        'internal_bounds':[f.rad().hex() for f in b.forms]})
        for i,k in enumerate(OUTPUT):
            r=abs(qval(regs[k])-true[i])
            if r>Q(E[i]):
                violations.append({'step':j,'kind':'output','component':i})
            if E[i]:
                worst=max(worst,r/Q(E[i]))
        st=tuple(regs[k] for k in LATENT_OUT)
        for i,f in enumerate(b.forms):
            if abs(qval(st[i])-exact[i])>Q(f.rad()):
                violations.append({'step':j,'kind':'internal','component':i})
    return {'steps':n,'scope':'LOCAL_RESTART_FROM_REPRESENTED_LATENT_STATE',
            'violations':len(violations),'details':violations,'max_actual_over_bound':float(worst),'records':records}
