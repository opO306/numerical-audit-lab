#!/usr/bin/env python3
"""Independent arithmetic/geometry/validation audit of target f806d8c.

The oracle uses a separately implemented normalized integer pair class, an
absolute-value nearest-integer search (no negative floor division), and a
cross-product squared-distance formula. Fraction is used ONLY to construct
arguments to the target slow rounding helper, not to compute expected answers.
No target arithmetic, geometry, validation, comparator, or serializer is used
as an oracle. Target modules are invoked solely as systems under test.
"""
import argparse, copy, dataclasses, hashlib, itertools, json, pathlib, random
import sys, time, traceback
from collections import Counter

P = argparse.ArgumentParser()
P.add_argument('--source-root', type=pathlib.Path, default=pathlib.Path(__file__).parent/'source')
P.add_argument('--out', type=pathlib.Path, default=pathlib.Path(__file__).parent/'independent_results.json')
ARGS = P.parse_args()
sys.path.insert(0, str(ARGS.source_root.resolve()))
from independent_checker.c1b1 import contracts as C
from independent_checker.c1b1 import exact_slow as S, exact_fast as F, exact_geometry as G
from independent_checker.c1b1 import claim_adapter as CA
from fractions import Fraction  # Target input adapter only.

TARGET = 'f806d8ce1ef86a0948b1a8abafe1a22c3058178b'
SPEC = '3217fc38aa798fff3ffea8072cecafaecac9f98be85589e9fa35a9dc6aa8119b'
ORDER = ('i.x','i.y','i.z','j.x','j.y','j.z')
META = {'scope':'ARITHMETIC_ONLY','j_status':'J_NOT_VERIFIED','spec_sha256':SPEC}
COUNTS = Counter()
RESULTS = {}

def gcd_own(a, b):
    a, b = abs(a), abs(b)
    while b:
        a, b = b, a % b
    return a

@dataclasses.dataclass(frozen=True, eq=False)
class Q:
    n: int
    d: int = 1
    def __post_init__(self):
        assert type(self.n) is int and type(self.d) is int and self.d != 0
        n, d = self.n, self.d
        if d < 0: n, d = -n, -d
        g = gcd_own(n,d)
        object.__setattr__(self,'n',n//g);object.__setattr__(self,'d',d//g)
    @staticmethod
    def lift(x):
        return x if isinstance(x,Q) else Q(x)
    def __add__(self,x):
        x=Q.lift(x); return Q(self.n*x.d+x.n*self.d,self.d*x.d)
    __radd__=__add__
    def __neg__(self): return Q(-self.n,self.d)
    def __sub__(self,x): return self + (-Q.lift(x))
    def __rsub__(self,x): return Q.lift(x) + (-self)
    def __mul__(self,x):
        x=Q.lift(x); return Q(self.n*x.n,self.d*x.d)
    __rmul__=__mul__
    def __truediv__(self,x):
        x=Q.lift(x); return Q(self.n*x.d,self.d*x.n)
    def __eq__(self,x):
        if not isinstance(x,(Q,int)):return False
        x=Q.lift(x); return self.n*x.d == x.n*self.d
    def __lt__(self,x):
        x=Q.lift(x); return self.n*x.d < x.n*self.d
    def __le__(self,x): return self < x or self == x

def nearest(n,d):
    """Use only nonnegative integer division and absolute distances."""
    assert d>0
    sign=-1 if n<0 else 1
    a=abs(n); k=a//d
    best=min((k,k+1),key=lambda j:(abs(a-j*d),j % 2))
    return sign*best

def eqratio(actual, expected):
    assert actual.denominator>0
    assert actual.numerator*expected.d==expected.n*actual.denominator, (actual,expected)

def metadata(x,with_spec=True):
    assert x.scope=='ARITHMETIC_ONLY' and x.j_status=='J_NOT_VERIFIED'
    if with_spec:assert x.spec_sha256==SPEC

def refusal(code,phase,atom='',component=''):
    return ('REFUSED',code,phase,atom,component)

MESSAGES={
'DISPLACEMENT_OVERFLOW':'stored displacement outside signed position grid',
'POSITION_OVERFLOW':'stored position outside signed position grid',
'MOMENTUM_OVERFLOW':'stored momentum outside signed momentum grid',
'SEGMENT_INTRUSION':'exact segment crosses supplied threshold',
'STORED_INTRUSION':'stored position crosses supplied threshold'}

def drift_oracle(req):
    scale=2**req.position_grid.frac_bits
    ps=2**req.momentum_grid.frac_bits
    lo=-(2**(req.position_grid.width-1));hi=-lo-1
    ds=[];ends=[];delta=[];raw=[]
    for atom,rs,ps_raw,m in [('i',req.r_i,req.p_i,req.mass_i),('j',req.r_j,req.p_j,req.mass_j)]:
        for axis,r,p in zip('xyz',rs,ps_raw):
            d=(Q(p,ps)*Q(req.dt.numerator,req.dt.denominator))/Q(m.numerator,m.denominator)
            z=nearest(d.n*scale,d.d)
            if not lo<=z<=hi:return refusal('DISPLACEMENT_OVERFLOW','drift',atom,axis)
            if not lo<=r+z<=hi:return refusal('POSITION_OVERFLOW','drift',atom,axis)
            ds.append(d);ends.append(Q(r,scale)+d);delta.append(z);raw.append(r+z)
    return ('DRIFT',ds,ends,tuple(delta[:3]),tuple(delta[3:]),tuple(raw[:3]),tuple(raw[3:]))

def kick_oracle(req):
    lo=-(2**(req.momentum_grid.width-1));hi=-lo-1
    ps=2**req.momentum_grid.frac_bits
    values=[];raws=[]
    for atom,pvec,sign in [('i',req.p_i,-1),('j',req.p_j,1)]:
        for axis,p,j in zip('xyz',pvec,req.J_raw):
            raw=p+sign*j
            if not lo<=raw<=hi:return refusal('MOMENTUM_OVERFLOW','kick',atom,axis)
            values.append(Q(raw,ps));raws.append(raw)
    return ('KICK',values,tuple(raws[:3]),tuple(raws[3:]))

def dot(x,y):return sum((a*b for a,b in zip(x,y)),Q(0))
def cross(x,y):return (x[1]*y[2]-x[2]*y[1],x[2]*y[0]-x[0]*y[2],x[0]*y[1]-x[1]*y[0])

def geometry_oracle(q0,q1,stored,threshold):
    """Endpoint derivative signs; interior distance from cross-product area."""
    q0=tuple(Q.lift(x) for x in q0);q1=tuple(Q.lift(x) for x in q1)
    stored=tuple(Q.lift(x) for x in stored);threshold=Q.lift(threshold)
    velocity=tuple(y-x for x,y in zip(q0,q1))
    length2=dot(velocity,velocity)
    derivative0=dot(q0,velocity);derivative1=dot(q1,velocity)
    if length2==0 or Q(0)<=derivative0:
        tau=Q(0);minimum=dot(q0,q0)
    elif derivative1<=0:
        tau=Q(1);minimum=dot(q1,q1)
    else:
        tau=-derivative0/length2
        area=cross(q0,q1)
        minimum=dot(area,area)/length2
    stored2=dot(stored,stored)
    return (tau,minimum,stored2,threshold,minimum<threshold,stored2<threshold)

def geometry_from_drift(req,out,threshold):
    s=2**req.position_grid.frac_bits
    q0=tuple(Q(a-b,s) for a,b in zip(req.r_i,req.r_j))
    q1=tuple(a-b for a,b in zip(out[2][:3],out[2][3:]))
    st=tuple(Q(a-b,s) for a,b in zip(out[5],out[6]))
    return geometry_oracle(q0,q1,st,Q(threshold.numerator,threshold.denominator))

def check_geometry_output(actual,expected):
    for field,e in zip(('tau','min_R2','stored_R2','threshold'),expected[:4]):eqratio(getattr(actual,field),e)
    assert actual.segment_intrusion is expected[4] and actual.stored_intrusion is expected[5]
    assert actual.domain=='EXACT_THRESHOLD_ONLY';metadata(actual)

def check_call(module,op,req,expected,*args):
    before=copy.deepcopy(req)
    COUNTS['target_calls']+=1
    try:out=getattr(module,op)(req,*args)
    except C.LabRefusal as e:
        assert expected[0]=='REFUSED',('unexpected_refusal',e.failure,expected,req)
        actual=('REFUSED',e.failure.code,e.failure.phase,e.failure.atom,e.failure.component)
        assert actual==expected,(actual,expected,req)
        if e.failure.code in MESSAGES:assert e.failure.message==MESSAGES[e.failure.code]
        metadata(e.failure);COUNTS[module.__name__.split('.')[-1]+':refused']+=1
        return None
    finally:
        assert req==before,('INPUT_MUTATION',op,req,before)
    assert expected[0]!='REFUSED',('missed_refusal',expected,out,req)
    metadata(out);COUNTS[module.__name__.split('.')[-1]+':computed']+=1
    if expected[0]=='GUARDED':
        check_geometry_output(out.geometry,expected[2]);out=out.drift;expected=expected[1]
    assert out.checked_order==ORDER
    assert type(out).__dataclass_params__.frozen
    if expected[0]=='DRIFT':
        for a,e in zip(out.displacement,expected[1]):eqratio(a,e)
        for a,e in zip(out.endpoint,expected[2]):eqratio(a,e)
        assert len(out.displacement)==6 and len(out.endpoint)==6
        assert (out.delta_i,out.delta_j,out.r_i,out.r_j)==tuple(expected[3:])
    else:
        for a,e in zip(out.exact_momentum,expected[1]):eqratio(a,e)
        assert len(out.exact_momentum)==6
        assert (out.p_i,out.p_j)==tuple(expected[2:])
    return out

def check_drift(req,group):
    expected=drift_oracle(req)
    for module in (S,F):check_call(module,'drift',req,expected)
    COUNTS[group]+=1
    return expected

def check_kick(req,group):
    expected=kick_oracle(req)
    for module in (S,F):check_call(module,'kick',req,expected)
    COUNTS[group]+=1
    return expected

def check_guard(req,t,group):
    d=drift_oracle(req)
    expected=d
    if d[0]=='DRIFT':
        ge=geometry_from_drift(req,d,t)
        expected=refusal('SEGMENT_INTRUSION','segment_guard') if ge[4] else (refusal('STORED_INTRUSION','stored_guard') if ge[5] else ('GUARDED',d,ge))
    for m in (S,F):check_call(m,'guarded_drift',req,expected,t)
    COUNTS[group]+=1
    return expected

def req0(**kw):
    r=C.DriftInput(C.Grid(8,0),C.Grid(8,0),(1,0,0),(0,0,0),(1,0,0),(0,0,0),C.Ratio(1,1),C.Ratio(1,1),C.Ratio(1,2))
    return dataclasses.replace(r,**kw)

def source_hashes():
    hashes={
'claim_adapter.py':'8e8894eb2abc0e1540f516418287b9e576e282c6140d7d83af9523788fd0d85e',
'compare.py':'5ad6b3f0b03b240e559c955552f32eb9079d524fba55be47ab88329a7d0657b2',
'contracts.py':'37acf394c9c252d5e401fdff06fcb28a0ab1202cc090f1456ecd4bb84fff47ed',
'exact_fast.py':'2190e099642b4bf440e4a2280b09d4b89984f637e6cee1b09dfa23411f0b4c0b',
'exact_geometry.py':'b237cd00e45e2ed635bae54880cfef88c1126e98af57d74843b752d2ed27677e',
'exact_slow.py':'b36efc03abdcb760f294f009ea1aea8aafa6fcc05a53c7b3970291c90edf4c13',
'semantic_manifest_v1.json':SPEC}
    for name,h in hashes.items():assert hashlib.sha256((ARGS.source_root/'independent_checker/c1b1'/name).read_bytes()).hexdigest()==h
    manifest=json.loads((ARGS.source_root/'independent_checker/c1b1/semantic_manifest_v1.json').read_text())
    assert manifest['component_order']==list(ORDER)
    assert manifest['scope']==META['scope'] and manifest['impulse_status']==META['j_status']
    assert manifest['drift']['round_sum_forbidden'] is True
    RESULTS['verified_target_source_sha256']=hashes

def rounding_tests():
    # The absolute-value oracle is itself checked by global integer enumeration.
    for n in range(-80,81):
        for d in range(1,21):
            brute=min(range(-82,83),key=lambda k:(abs(n-k*d),k%2))
            assert nearest(n,d)==brute
            COUNTS['oracle_rounding_brute_selfcheck']+=1
    for n in range(-1024,1025):
        for d in range(1,129):
            expected=nearest(n,d)
            assert F.nearest_even_ratio(n,d)==expected
            assert S.nearest_even(Fraction(n,d))==expected
            COUNTS['rounding_exhaustive_rational_cells']+=1
    for bit in (2,3,8,48,80,96,257,1024,4096):
        for lower in (-(1<<bit),-(1<<bit)+1,-3,-2,-1,0,1,2,3,(1<<bit)-1,1<<bit):
            for eps in (-1,0,1):
                den=2*(1<<20);num=(2*lower+1)*(1<<20)+eps
                for factor in (1,3,(1<<137)+13):
                    n,d=num*factor,den*factor;e=nearest(n,d)
                    assert F.nearest_even_ratio(n,d)==e
                    assert S.nearest_even(Fraction(n,d))==e
                    COUNTS['rounding_huge_ties_neighbors_unreduced']+=1

def drift_tests():
    zero=(0,0,0)
    for fp,fm,r,p,a,b,m in itertools.product(range(3),range(3),range(-4,4),range(-4,4),(-3,-1,0,1,3),(1,2,3),((1,1),(1,2),(2,1),(3,2))):
        req=C.DriftInput(C.Grid(3,fp),C.Grid(3,fm),(r,0,0),zero,(p,0,0),zero,C.Ratio(*m),C.Ratio(1,1),C.Ratio(a,b))
        check_drift(req,'drift_small_exhaustive')
    rng=random.Random(20261004)
    for index in range(2400):
        wp=rng.choice((2,3,5,8,16,32,96,128,257));wm=rng.choice((2,3,8,16,96,128,257))
        fp=rng.randrange(wp);fm=rng.randrange(wm)
        lp=1<<(wp-1);lm=1<<(wm-1)
        pv=lambda:tuple(rng.randrange(-lp,lp) for _ in range(3))
        mv=lambda:tuple(rng.randrange(-lm,lm) for _ in range(3))
        req=C.DriftInput(C.Grid(wp,fp),C.Grid(wm,fm),pv(),pv(),mv(),mv(),C.Ratio(rng.randrange(1,33),rng.randrange(1,33)),C.Ratio(rng.randrange(1,33),rng.randrange(1,33)),C.Ratio(rng.randrange(-16,17),rng.randrange(1,33)))
        expected=check_drift(req,'drift_random_full_lane')
        factor=(1<<103)+21
        equivalent=dataclasses.replace(req,mass_i=C.Ratio(req.mass_i.numerator*factor,req.mass_i.denominator*factor),mass_j=C.Ratio(req.mass_j.numerator*3,req.mass_j.denominator*3),dt=C.Ratio(req.dt.numerator*7,req.dt.denominator*7))
        assert drift_oracle(equivalent)==expected
        check_drift(equivalent,'drift_unreduced_equivalent')
        if index<400:check_guard(req,C.Ratio(rng.randrange(1,100),rng.randrange(1,20)),'guard_random_full_lane')
    for w in (2,3,4,8,96,4096):
        lim=1<<(w-1)
        for fp in sorted({0,w-1}):
            for delta in (-lim-1,-lim,-lim+1,-1,0,1,lim-1,lim,lim+1):
                for r in (-lim,0,lim-1):
                    req=req0(position_grid=C.Grid(w,fp),momentum_grid=C.Grid(w+1 if w<4096 else 4096,0),r_i=(r,0,0),p_i=(1,0,0),dt=C.Ratio(delta,1<<fp))
                    check_drift(req,'drift_range_edges')
    # Separate rounding differs at an odd integer origin and an exact half.
    for sign in (-1,1):
        req=req0(r_i=(sign,0,0),p_i=(sign,0,0))
        out=check_drift(req,'drift_round_sum_distinction')
        assert out[5][0]==sign and nearest(3*sign,2)==2*sign
    # First-failure ordering across all six lanes and position/displacement.
    for lane in range(6):
        r=[0]*6;p=[0]*6
        r[lane]=3;p[lane]=1
        for k in range(lane+1,6):p[k]=8
        req=req0(position_grid=C.Grid(3,0),r_i=tuple(r[:3]),r_j=tuple(r[3:]),p_i=tuple(p[:3]),p_j=tuple(p[3:]),dt=C.Ratio(1,1))
        e=check_drift(req,'drift_multifault_order')
        assert e==refusal('POSITION_OVERFLOW','drift','i' if lane<3 else 'j','xyz'[lane%3])

def kick_tests():
    for frac,pi,pj,j,axis in itertools.product(range(3),range(-4,4),range(-4,4),range(-4,4),range(3)):
        vec=lambda x:tuple(x if k==axis else 0 for k in range(3))
        req=C.KickInput(C.Grid(3,frac),C.Grid(3,frac),vec(pi),vec(pj),vec(j))
        check_kick(req,'kick_small_exhaustive')
    rng=random.Random(804)
    for _ in range(2400):
        w=rng.choice((2,3,8,16,32,96,128,257));f=rng.randrange(w);limit=1<<(w-1)
        v=lambda:tuple(rng.randrange(-limit,limit) for _ in range(3))
        check_kick(C.KickInput(C.Grid(w,f),C.Grid(w,f),v(),v(),v()),'kick_random_full_lane')
    for w in (2,3,8,96,4096):
        lim=1<<(w-1)
        for f in sorted({0,w-1}):
            for pi,pj,j in ((-lim,lim-1,0),(-lim,0,1),(lim-1,0,-1),(0,lim-1,1),(0,-lim,-1),(-lim+1,lim-2,1)):
                check_kick(C.KickInput(C.Grid(w,f),C.Grid(w,f),(pi,0,0),(pj,0,0),(j,0,0)),'kick_range_edges')
    for lane in range(6):
        pi=[0,0,0];pj=[0,0,0];j=[1,1,1]
        if lane<3:
            for k in range(lane,3):pi[k]=-4
            pj=[3,3,3]
        else:
            for k in range(lane-3,3):pj[k]=3
        req=C.KickInput(C.Grid(3,0),C.Grid(3,0),tuple(pi),tuple(pj),tuple(j))
        e=check_kick(req,'kick_multifault_order')
        assert e==refusal('MOMENTUM_OVERFLOW','kick','i' if lane<3 else 'j','xyz'[lane%3])

def geometry_tests():
    points=list(itertools.product(range(-1,2),repeat=3))
    for ix,(q0,q1,t) in enumerate(itertools.product(points,points,(Q(1,2),Q(1),Q(2)))):
        stored=points[(ix*17)%len(points)]
        expected=geometry_oracle(q0,q1,stored,t)
        out=G.evaluate(q0,q1,stored,C.Ratio(t.n,t.d));check_geometry_output(out,expected)
        COUNTS['geometry_integer_exhaustive']+=1
    rng=random.Random(505)
    for _ in range(1500):
        v=lambda:tuple(Q(rng.randrange(-20,21),rng.randrange(1,15)) for _ in range(3))
        q0,q1,stored=v(),v(),v()
        base=geometry_oracle(q0,q1,stored,Q(1));minimum=base[1]
        thresholds=[Q(rng.randrange(1,20),rng.randrange(1,20))]
        if Q(0)<minimum:thresholds += [minimum,minimum+Q(1,10**12),minimum-Q(1,10**12)]
        for t in thresholds:
            if not Q(0)<t:continue
            expected=geometry_oracle(q0,q1,stored,t)
            wire=lambda v:tuple(C.Ratio(x.n,x.d) for x in v)
            out=G.evaluate(wire(q0),wire(q1),wire(stored),C.Ratio(t.n,t.d))
            check_geometry_output(out,expected);COUNTS['geometry_rational_threshold_cells']+=1
    cases=[
        (req0(p_i=(-1,0,0),dt=C.Ratio(1,4)),C.Ratio(81,100),'SEGMENT_INTRUSION'),
        (req0(r_i=(2,0,0),p_i=(-4,0,0),dt=C.Ratio(1,5)),C.Ratio(121,100),'STORED_INTRUSION'),
        (req0(p_i=(-3,0,0),dt=C.Ratio(1,4)),C.Ratio(81,100),'SEGMENT_INTRUSION'),
        (req0(p_i=(0,0,0)),C.Ratio(1,1),None)]
    for req,t,code in cases:
        result=check_guard(req,t,'guard_hand_cases')
        assert (result[1] if result[0]=='REFUSED' else None)==code

def validation_tests():
    def invalid(req,code,op='drift',args=(),field=None):
        before=copy.deepcopy(req)
        for m in (S,F):
            try:getattr(m,op)(req,*args)
            except C.LabRefusal as e:
                assert e.failure.code==code,(e.failure,code)
                assert e.failure.phase=='input'
                if field:assert field in e.failure.message,(field,e.failure)
                metadata(e.failure)
            else:raise AssertionError(('invalid input accepted',req,code))
            assert req==before;COUNTS['validation_target_calls']+=1
        COUNTS['validation_cases']+=1
    invalid(None,'INPUT_SCHEMA')
    class DI(C.DriftInput):pass
    invalid(DI(**dataclasses.asdict(req0())),'INPUT_SCHEMA')
    class IntSubclass(int):pass
    class StrSubclass(str):pass
    class TupleSubclass(tuple):pass
    class GridSubclass(C.Grid):pass
    class RatioSubclass(C.Ratio):pass
    invalid(req0(spec_sha256='0'*64,position_grid=C.Grid(1,0)),'SPEC_MISMATCH')
    invalid(req0(spec_sha256=StrSubclass(SPEC)),'SPEC_MISMATCH')
    for field in ('position_grid','momentum_grid'):
        for grid in (None,GridSubclass(8,0)):
            invalid(req0(**{field:grid}),'INPUT_SCHEMA',field=field)
        for grid in (C.Grid(1,0),C.Grid(4097,0),C.Grid(True,0),C.Grid(8,True),C.Grid(8,-1),C.Grid(8,8),C.Grid(8,0,kind='float'),C.Grid(8,0,rounding='ties_away'),C.Grid(8,0,overflow='wrap'),C.Grid(8,0,kind=StrSubclass('signed_fx'))):
            invalid(req0(**{field:grid}),'PROFILE_UNSUPPORTED',field=field)
    for field in ('r_i','r_j','p_i','p_j'):
        for vec in ([0,0,0],(0,0),(0,0,0,0),TupleSubclass((0,0,0)),(True,0,0),(0.0,0,0),(IntSubclass(0),0,0)):
            invalid(req0(**{field:vec}),'INPUT_SCHEMA',field=field)
        for raw in (-129,128):invalid(req0(**{field:(raw,0,0)}),'RAW_RANGE',field=field)
    for field in ('mass_i','mass_j','dt'):
        for value in (None,RatioSubclass(1,1),C.Ratio(1,0),C.Ratio(1,-1),C.Ratio(True,1),C.Ratio(1,True),C.Ratio(1.0,1)):
            invalid(req0(**{field:value}),'RATIONAL_INVALID',field=field)
        if field!='dt':
            for n in (0,-1):invalid(req0(**{field:C.Ratio(n,1)}),'RATIONAL_NONPOSITIVE',field=field)
    invalid(req0(r_i=(128,0,0),mass_i=C.Ratio(0,1)),'RAW_RANGE',field='r_i')
    invalid(req0(p_i=(True,0,0),mass_i=C.Ratio(0,1)),'INPUT_SCHEMA',field='p_i')
    invalid(req0(mass_i=C.Ratio(0,1),mass_j=C.Ratio(1,0)),'RATIONAL_NONPOSITIVE',field='mass_i')
    invalid(req0(dt=C.Ratio(1000,1)),'RATIONAL_NONPOSITIVE','guarded_drift',(C.Ratio(0,1),),'r_min_squared')
    k=C.KickInput(C.Grid(8,0),C.Grid(8,0),(0,0,0),(0,0,0),(0,0,0))
    invalid(dataclasses.replace(k,impulse_grid=C.Grid(8,1),J_raw=(1000,0,0)),'GRID_MISMATCH','kick')
    for field in ('p_i','p_j','J_raw'):
        invalid(dataclasses.replace(k,**{field:(True,0,0)}),'INPUT_SCHEMA','kick',field=field)
        invalid(dataclasses.replace(k,**{field:(128,0,0)}),'RAW_RANGE','kick',field=field)
    for n in (-1,0,1):check_drift(req0(dt=C.Ratio(n,3)),'signed_zero_dt_valid')
    for field in (0,1,2):
        args=[(1,0,0),(2,0,0),(2,0,0),C.Ratio(1,1)];args[field]=[1,0,0]
        try:G.evaluate(*args)
        except C.LabRefusal as e:assert e.failure.code=='INPUT_SCHEMA'
        else:raise AssertionError('mutable geometry vector accepted')
    for threshold in (0,-1,True,1.0,C.Ratio(1,0)):
        try:G.evaluate((1,0,0),(2,0,0),(2,0,0),threshold)
        except C.LabRefusal:pass
        else:raise AssertionError('bad geometry threshold accepted')
        COUNTS['geometry_validation_cases']+=1

# Public artifact formatting below is specified independently, without importing
# target serializer/capture/comparator as an oracle.
def wire_q(q):return {'numerator':str(q.n),'denominator':str(q.d)}
def wire_grid(g):return {'width':g.width,'frac_bits':g.frac_bits,'kind':'signed_fx','rounding':'nearest_even','overflow':'refuse'}
def wire_v(v):return [str(x) for x in v]
def artifact(expected):
    if expected[0]=='REFUSED':
        _,code,phase,atom,axis=expected
        value={'type':'Failure','code':code,'phase':phase,'atom':atom,'component':axis,'message':MESSAGES[code],**META}
        exc='LabRefusal'
    else:
        exc=''
        if expected[0]=='DRIFT':
            _,ds,ends,di,dj,ri,rj=expected
            value={'type':'DriftResult','displacement':[wire_q(x) for x in ds],'endpoint':[wire_q(x) for x in ends],'delta_i':wire_v(di),'delta_j':wire_v(dj),'r_i':wire_v(ri),'r_j':wire_v(rj),'checked_order':list(ORDER),**META}
        elif expected[0]=='KICK':
            _,qs,pi,pj=expected
            value={'type':'KickResult','exact_momentum':[wire_q(x) for x in qs],'p_i':wire_v(pi),'p_j':wire_v(pj),'checked_order':list(ORDER),**META}
        else:raise AssertionError(expected[0])
    return {'type':'Outcome','value':value,'exception_type':exc,'scope':META['scope'],'j_status':META['j_status']}

def envelope(req,operation,expected):
    if operation=='drift':
        data={'position_grid':wire_grid(req.position_grid),'momentum_grid':wire_grid(req.momentum_grid),'r_i':wire_v(req.r_i),'r_j':wire_v(req.r_j),'p_i':wire_v(req.p_i),'p_j':wire_v(req.p_j),'mass_i':wire_q(Q(req.mass_i.numerator,req.mass_i.denominator)),'mass_j':wire_q(Q(req.mass_j.numerator,req.mass_j.denominator)),'dt':wire_q(Q(req.dt.numerator,req.dt.denominator))}
    else:
        data={'momentum_grid':wire_grid(req.momentum_grid),'impulse_grid':wire_grid(req.impulse_grid),'p_i':wire_v(req.p_i),'p_j':wire_v(req.p_j),'J_raw':wire_v(req.J_raw)}
    return {'schema':'LAB_C1B1_CLAIM_V1',**META,'acquisition_id':'independent-acquisition','record_id':'independent-record','phase_id':operation,'operation':operation,'input':data,'claim':artifact(expected)}

def claim_tests():
    inputs=[]
    for p in (-3,-1,0,1,3):
        for dt in ((1,2),(-1,2),(7,3)):
            req=req0(p_i=(p,0,0),dt=C.Ratio(*dt));inputs.append(envelope(req,'drift',drift_oracle(req)))
    for pi,pj,j in ((-128,0,1),(127,0,-1),(0,127,1),(0,-128,-1),(3,-4,1),(3,-4,-1),(3,-4,0)):
        req=C.KickInput(C.Grid(8,3),C.Grid(8,3),(pi,0,0),(pj,0,0),(j,0,0));inputs.append(envelope(req,'kick',kick_oracle(req)))
    for payload in inputs:
        before=copy.deepcopy(payload)
        for path in ('exact_slow','exact_fast'):
            out=CA.compare_claim(json.dumps(payload),path,opt_in=path=='exact_fast')
            assert out.status=='ARITHMETIC_MATCH' and out.path==path
            assert out.calculation_status==('REFUSED' if payload['claim']['exception_type'] else 'COMPUTED')
            assert out.external_compatibility=='NOT VERIFIED';metadata(out)
            assert json.loads(out.computed_json)==payload['claim']
            COUNTS['independent_claim_matches']+=1
        assert payload==before
    p=envelope(req0(),'drift',drift_oracle(req0()))
    bad=copy.deepcopy(p);bad['claim']['value']['endpoint'][0]['numerator']='4'
    assert CA.compare_claim(bad).status=='ARITHMETIC_MISMATCH'
    p2=copy.deepcopy(p);p2['record_id']='different-occurrence'
    assert CA.compare_claim(p2).record_id!=CA.compare_claim(p).record_id
    for key,val in (('scope','CERTIFIED'),('j_status','CONFIRMED'),('spec_sha256','0'*64)):
        bad=copy.deepcopy(p);bad[key]=val
        try:CA.compare_claim(bad)
        except C.LabRefusal:pass
        else:raise AssertionError('overclaim envelope accepted')
    bad=copy.deepcopy(p);bad['claim']['value']['scope']='CERTIFIED'
    out=CA.compare_claim(bad);assert out.status=='ARITHMETIC_MISMATCH';metadata(out)
    for value in (True,False,'true',1,None):
        if value is True:continue
        try:CA.compare_claim(p,'exact_fast',opt_in=value)
        except C.LabRefusal as e:assert e.failure.code=='FAST_OPTIN_REQUIRED'
        else:raise AssertionError('unapproved fast')
    variants=[]
    for raw in ('-0','00','+1','1.0',1,True):
        x=copy.deepcopy(p);x['input']['p_i'][0]=raw;variants.append(x)
    x=copy.deepcopy(p);x['input']['mass_i']={'numerator':'2','denominator':'2'};variants.append(x)
    x=copy.deepcopy(p);x['claim']['certified']=True;variants.append(x)
    for x in variants:
        try:CA.compare_claim(x)
        except C.LabRefusal:pass
        else:raise AssertionError(('bad wire accepted',x))
        COUNTS['claim_invalid_cases']+=1
    serialized=json.dumps(p)
    for text in ('{"schema":"x",'+serialized[1:],'NaN','x'*(1048577)):
        try:CA.compare_claim(text)
        except C.LabRefusal:pass
        else:raise AssertionError('bad JSON accepted')
        COUNTS['claim_invalid_cases']+=1

def known_boundary_counterexample():
    # Each input integer has only 2151 decimal digits, below the 4096 cap.
    # Actual exact displacement is 1 / ((10^2150+1)*(10^2150+3)).
    # The supplied claim uses only short canonical integers; it claims all-zero
    # exact displacements and is mathematically wrong, but schema-conforming.
    # A mismatch or structured refusal is acceptable; an uncaught ValueError is not.
    x=10**2150
    req=req0(r_i=(0,0,0),mass_i=C.Ratio(x+3,1),dt=C.Ratio(1,x+1))
    false_expected=drift_oracle(dataclasses.replace(req,dt=C.Ratio(0,1)))
    payload=envelope(req,'drift',false_expected)
    text=json.dumps(payload,separators=(',',':'))
    assert len(text.encode())<1048576
    assert len(payload['input']['mass_i']['numerator'])==2151
    oracle=drift_oracle(req);assert oracle[1][0]==Q(1,(x+1)*(x+3))
    rows=[]
    for module,path in ((S,'exact_slow'),(F,'exact_fast')):
        check_call(module,'drift',req,oracle)
        try:
            result=CA.compare_claim(text,path,opt_in=path=='exact_fast')
            rows.append({'path':path,'exception':None,'status':result.status})
        except Exception as e:
            rows.append({'path':path,'exception':type(e).__name__,'is_LabRefusal':isinstance(e,C.LabRefusal),'message':str(e),'traceback':traceback.format_exc()})
    (ARGS.out.parent/'counterexample_large_claim.json').write_text(text+'\n',encoding='utf-8')
    RESULTS['claim_serialization_counterexample']={'input_integer_digits':2151,'result_denominator_digits':4301,'json_bytes':len(text.encode()),'python_int_max_str_digits':sys.get_int_max_str_digits(),'observations':rows,'verdict':'FAIL' if any(r.get('exception') and not r.get('is_LabRefusal') for r in rows) else 'NOT_REPRODUCED'}
    assert RESULTS['claim_serialization_counterexample']['verdict']=='FAIL'


def run_group(name,fn):
    begin=time.perf_counter();before=dict(COUNTS)
    try:
        fn();result={'status':'PASS','seconds':time.perf_counter()-begin}
    except Exception:
        result={'status':'FAIL','seconds':time.perf_counter()-begin,'traceback':traceback.format_exc()}
    result['counts']={k:v-before.get(k,0) for k,v in COUNTS.items() if v!=before.get(k,0)}
    RESULTS[name]=result
    print(name,json.dumps(result),flush=True)

if __name__=='__main__':
    source_hashes()
    for name,fn in [('rounding',rounding_tests),('drift',drift_tests),('kick',kick_tests),('geometry',geometry_tests),('validation',validation_tests),('claims_core',claim_tests),('boundary_bug_reproduction',known_boundary_counterexample)]:run_group(name,fn)
    RESULTS['counts']=dict(COUNTS);RESULTS['target']=TARGET;RESULTS['python']=sys.version
    RESULTS['scope']='ARITHMETIC_ONLY';RESULTS['j_status']='J_NOT_VERIFIED'
    RESULTS['note']='boundary_bug_reproduction PASS means reproduction succeeded; the adapter defect itself is FAIL.'
    ARGS.out.write_text(json.dumps(RESULTS,indent=2)+'\n',encoding='utf-8')
    print('RESULTS',ARGS.out,flush=True)
    if any(isinstance(v, dict) and v.get('status') == 'FAIL' for v in RESULTS.values()):
        raise SystemExit(1)
