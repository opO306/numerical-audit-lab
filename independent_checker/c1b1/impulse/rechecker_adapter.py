"""Independent Lab binding parser and V2 data projection. Invocation disabled.

Uses approved specification data, stdlib JSON/int/hash semantics only.
No producer parser, identity, enclosure, rounding, executor or V2 imports.
PREPARED_ONLY is not a recheck verdict or authenticated acquisition.
"""
from dataclasses import dataclass
import hashlib,json,math,re
from pathlib import Path
from .spec import load_spec

CHECKER_SHA256='180d5a19bbea606594912e95b3c210b5a7739995afa39c5300959faef8b94d96'
HASH=re.compile(r'[0-9a-f]{64}\Z',re.ASCII)
INT=re.compile(r'(?:0|-?[1-9][0-9]*)\Z',re.ASCII)

class BindingRefusal(ValueError):pass

@dataclass(frozen=True)
class Preparation:
    legacy: tuple
    zero_axes: tuple
    state: str='PREPARED_ONLY'

def _canonical(obj):
    return (json.dumps(obj,sort_keys=True,separators=(',',':'),ensure_ascii=True)+'\n').encode('ascii')

def _read(data):
    if type(data) is not bytes or len(data)>1048576:raise BindingRefusal('wire bytes')
    depth=0;quoted=escape=False
    for byte in data:
        if quoted:
            if escape:escape=False
            elif byte==92:escape=True
            elif byte==34:quoted=False
        elif byte==34:quoted=True
        elif byte in (91,123):
            depth+=1
            if depth>7:raise BindingRefusal('wire depth')
        elif byte in (93,125):depth-=1
    def reject(_):raise BindingRefusal('numeric wire token')
    def pairs(items):
        result={}
        for k,v in items:
            if k in result:raise BindingRefusal('duplicate key')
            result[k]=v
        return result
    try:obj=json.loads(data.decode('ascii'),object_pairs_hook=pairs,parse_int=reject,parse_float=reject,parse_constant=reject)
    except (ValueError,UnicodeError,RecursionError):raise BindingRefusal('invalid wire') from None
    def shape(v):
        if type(v) is list:
            if len(v)>12:raise BindingRefusal('wire array')
            for x in v:shape(x)
        elif type(v) is dict:
            if len(v)>26:raise BindingRefusal('wire keys')
            for x in v.values():shape(x)
        elif v is not None and type(v) is not str:raise BindingRefusal('wire scalar')
    shape(obj)
    if _canonical(obj)!=data:raise BindingRefusal('noncanonical wire')
    return obj

def _int(value,minimum=None):
    if type(value) is not str or not INT.fullmatch(value) or len(value.lstrip('-'))>4096:
        raise BindingRefusal('integer syntax')
    try:result=int(value)
    except ValueError:raise BindingRefusal('HOST_SERIALIZATION_LIMIT') from None
    if minimum is not None and result<minimum:raise BindingRefusal('integer range')
    return result

def _lexeme(value,positive=False):
    if type(value) is not str or not INT.fullmatch(value) or len(value.lstrip('-'))>4096:
        raise BindingRefusal('integer syntax')
    if positive and (value=='0' or value.startswith('-')):raise BindingRefusal('positive integer syntax')

def _hash(value):
    if type(value) is not str or not HASH.fullmatch(value):raise BindingRefusal('hash')

def _digest(value,label=None):
    prefix=b'' if label is None else label.encode('ascii')+b'\0'
    return hashlib.sha256(prefix+_canonical(value)).hexdigest()

def verify_checker_source(path):
    sha=hashlib.sha256(Path(path).read_bytes()).hexdigest()
    if sha!=CHECKER_SHA256:raise BindingRefusal('checker source')
    return sha

def prepare(input_bytes,certificate_bytes,*,expected_producer_sha256):
    spec=load_spec();keys=spec.wire['closed_object_keys']
    def closed(obj,kind):
        if type(obj) is not dict or set(obj)!=set(keys[kind]):raise BindingRefusal('closed '+kind)
    obj=_read(input_bytes);cert=_read(certificate_bytes);closed(obj,'Input');closed(cert,'Certificate')
    # Independent first pass over BOTH input and certificate. Producer parser
    # is not shared, and no _int call occurs during this pass.
    state=obj['state'];closed(state,'State')
    for name,frac in [('position_grid','48'),('momentum_grid','80')]:
        closed(state[name],'Grid')
        if state[name]!={'kind':'FX','width':'96','frac_bits':frac}:raise BindingRefusal('grid')
    if type(state['atoms']) is not list or len(state['atoms'])!=2:raise BindingRefusal('atoms')
    for atom in state['atoms']:
        closed(atom,'Atom');_hash(atom['atom_id'])
        if atom['species']!='Ar40':raise BindingRefusal('species')
        for name in ('position_raw','momentum_raw'):
            if type(atom[name]) is not list or len(atom[name])!=3:raise BindingRefusal('raw vector')
            for v in atom[name]:_lexeme(v)
    acq=obj['acquisition'];closed(acq,'Acquisition')
    for k in ('record_id','acquisition_id','executor_source_sha256','acquisition_tool_sha256'):_hash(acq[k])
    if acq['full_half']!='HALF_OF_FULL_DT':raise BindingRefusal('half kick')
    if acq['phase']=='FIRST_HALF_KICK':
        if acq['previous_occurrence_sha256'] is not None:raise BindingRefusal('previous occurrence')
    elif acq['phase']=='SECOND_HALF_KICK':_hash(acq['previous_occurrence_sha256'])
    else:raise BindingRefusal('phase')
    closed(obj['budget'],'Budget')
    for k in keys['Budget']:
        if k in ('issuer_sha256','basis_record_sha256'):_hash(obj['budget'][k])
        elif k=='profile_version':
            if obj['budget'][k]!='1':raise BindingRefusal('profile')
        else:_lexeme(obj['budget'][k],positive=True)
    closed(cert['binding'],'Binding')
    for v in cert['binding'].values():_hash(v)
    for k in ('spec_sha256','producer_source_sha256','rechecker_source_sha256','attempt_digest'):_hash(cert[k])
    _lexeme(cert['attempt_count'],positive=True)
    proof=cert['proof'];closed(proof,'Proof')
    _lexeme(proof['sqrt_bits'],positive=True);_lexeme(proof['work_bits'],positive=True)
    if type(proof['exp_plan']) is not list or len(proof['exp_plan'])!=9:raise BindingRefusal('plan')
    for entry,rate_id in zip(proof['exp_plan'],spec.wire['rate_order']):
        closed(entry,'Exp')
        if entry['rate_id']!=rate_id or entry['mode']!='FULL':raise BindingRefusal('rate order/mode')
        if type(entry['rate']) is not dict or set(entry['rate'])!={'n','d'}:raise BindingRefusal('rate keys')
        _lexeme(entry['rate']['n']);_lexeme(entry['rate']['d'],positive=True);_lexeme(entry['order'])
        if entry['order'].startswith('-'):raise BindingRefusal('order syntax')
    for field in ('raw_J',):
        if type(cert[field]) is not list or len(cert[field])!=3:raise BindingRefusal('raw lanes')
        for value in cert[field]:_lexeme(value)
    if type(proof['lane_kinds']) is not list or len(proof['lane_kinds'])!=3 or any(
            k not in ('EXACT_ZERO_AXIS','NONLINEAR_V2') for k in proof['lane_kinds']):raise BindingRefusal('lane kinds')
    # Only the second pass may convert canonical integers.
    if obj['schema']!='LAB_C1B1_IMPULSE_INPUT_V1' or cert['schema']!='LAB_C1B1_IMPULSE_CERT_V1':raise BindingRefusal('schema')
    if obj['spec_sha256']!=spec.sha256 or cert['spec_sha256']!=spec.sha256:raise BindingRefusal('spec')
    _hash(expected_producer_sha256)
    if cert['producer_source_sha256']!=expected_producer_sha256 or cert['rechecker_source_sha256']!=CHECKER_SHA256:
        raise BindingRefusal('source binding')
    if cert['method']!='LAB_POINT_PRODUCER_V1_AND_PINNED_V2':raise BindingRefusal('method')
    state=obj['state'];closed(state,'State')
    for name,frac in [('position_grid','48'),('momentum_grid','80')]:
        closed(state[name],'Grid')
        if state[name]!={'kind':'FX','width':'96','frac_bits':frac}:raise BindingRefusal('grid')
    atoms=state['atoms']
    if type(atoms) is not list or len(atoms)!=2:raise BindingRefusal('atoms')
    positions=[]
    for atom in atoms:
        closed(atom,'Atom');_hash(atom['atom_id'])
        if atom['species']!='Ar40':raise BindingRefusal('species')
        for field in ('position_raw','momentum_raw'):
            if type(atom[field]) is not list or len(atom[field])!=3:raise BindingRefusal('vector')
            values=tuple(_int(v) for v in atom[field])
            if any(v<-(1<<95) or v>=(1<<95) for v in values):raise BindingRefusal('signed96')
            if field=='position_raw':positions.append(values)
    if atoms[0]['atom_id']==atoms[1]['atom_id']:raise BindingRefusal('atom roles')
    q=tuple(b-a for a,b in zip(*positions));r2raw=sum(v*v for v in q)
    threshold=spec.r_min_squared
    if r2raw==0 or r2raw*threshold.denominator<threshold.numerator*(1<<96):raise BindingRefusal('domain')
    acq=obj['acquisition'];closed(acq,'Acquisition')
    for k in ('record_id','acquisition_id','executor_source_sha256','acquisition_tool_sha256'):_hash(acq[k])
    if acq['full_half']!='HALF_OF_FULL_DT':raise BindingRefusal('half kick')
    if acq['phase']=='FIRST_HALF_KICK':
        if acq['previous_occurrence_sha256'] is not None:raise BindingRefusal('previous occurrence')
    elif acq['phase']=='SECOND_HALF_KICK':_hash(acq['previous_occurrence_sha256'])
    else:raise BindingRefusal('phase')
    budget=obj['budget'];closed(budget,'Budget');controls={}
    for k in keys['Budget']:
        if k in ('issuer_sha256','basis_record_sha256'):_hash(budget[k])
        elif k=='profile_version':
            if budget[k]!='1':raise BindingRefusal('profile')
        else:controls[k]=_int(budget[k],1)
    if controls['P0']<8 or controls['N0']>controls['N_max'] or controls['P0']>controls['P_max']:raise BindingRefusal('schedule')
    if not len(input_bytes)<=controls['input_parse_bytes']<=1048576 or not len(certificate_bytes)<=controls['private_certificate_bytes']<=1048576:
        raise BindingRefusal('byte controls')
    roles=dict(i=atoms[0]['atom_id'],j=atoms[1]['atom_id'])
    projection=dict(spec_sha256=spec.sha256,constants_sha256=spec.hashes['constants.json'],
        domain_sha256=spec.hashes['physical-domain.json'],atom_roles=roles,
        position_raw=[a['position_raw'] for a in atoms],species=[a['species'] for a in atoms],
        position_grid=state['position_grid'],full_dt=dict(n='40',d='1'),kick_fraction=dict(n='1',d='2'))
    full=_digest(state,'LAB_C1B1_FULL_STATE_V1');proj=_digest(projection,'LAB_C1B1_IMPULSE_PROJECTION_V1')
    acquisition=_digest(dict(state=state,acquisition=acq),'LAB_C1B1_ACQUISITION_RECORD_V1')
    occurrence=dict(acq);occurrence.update(acquisition_record_sha256=acquisition,full_state_sha256=full,
        projection_sha256=proj,atom_roles=roles,axis_order=['x','y','z'])
    binding=dict(input_sha256=_digest(obj),full_state_sha256=full,projection_sha256=proj,
        math_request_sha256=_digest(dict(projection_sha256=proj,methods=dict(spec.identity['payload_schemas']['methods']),axis_order=['x','y','z']),'LAB_C1B1_MATH_REQUEST_V1'),
        occurrence_sha256=_digest(occurrence,'LAB_C1B1_OCCURRENCE_V1'),acquisition_record_sha256=acquisition,
        budget_sha256=_digest(budget,'LAB_C1B1_BUDGET_V1'))
    closed(cert['binding'],'Binding')
    if cert['binding']!=binding:raise BindingRefusal('identity mismatch')
    count=_int(cert['attempt_count'],1);_hash(cert['attempt_digest'])
    if count>controls['max_attempts']:raise BindingRefusal('attempt count')
    proof=cert['proof'];closed(proof,'Proof');n=_int(proof['sqrt_bits'],1);p=_int(proof['work_bits'],8)
    t=count-1
    if t>min(n.bit_length(),p.bit_length()) or n!=controls['N0']<<t or p!=controls['P0']<<t:
        raise BindingRefusal('precision sequence')
    if n>min(controls['N_max'],controls['legacy_sqrt_bits_max']) or p>min(controls['P_max'],controls['legacy_work_bits_max']):
        raise BindingRefusal('precision cap')
    plan=proof['exp_plan']
    if type(plan) is not list or len(plan)!=9:raise BindingRefusal('plan')
    legacy_plan=[]
    for entry,rate_id in zip(plan,spec.wire['rate_order']):
        closed(entry,'Exp')
        if entry['rate_id']!=rate_id or entry['mode']!='FULL':raise BindingRefusal('rate order/mode')
        rate=entry['rate']
        if type(rate) is not dict or set(rate)!={'n','d'}:raise BindingRefusal('rate keys')
        numerator=_int(rate['n']);denominator=_int(rate['d'],1)
        if math.gcd(abs(numerator),denominator)!=1:raise BindingRefusal('noncanonical rate')
        if rate_id.endswith('_ETA'):key='eta_'+rate_id[:-4]
        else:
            family,_,idx=rate_id.split('_');key=f'alpha_{family}_{idx}'
        wanted=spec.constants[key]
        if (numerator,denominator)!=(wanted.numerator,wanted.denominator):raise BindingRefusal('rate constant')
        order=_int(entry['order'],0)
        if order>controls['legacy_order_max']:raise BindingRefusal('order cap')
        legacy_plan.append(dict(rate=rate['n']+'/'+rate['d'],mode='full',order=entry['order']))
    raw=cert['raw_J'];lanes=proof['lane_kinds']
    if type(raw) is not list or len(raw)!=3 or type(lanes) is not list or len(lanes)!=3:raise BindingRefusal('lanes')
    legacy=[];zero=[]
    for axis,(raw_string,kind) in enumerate(zip(raw,lanes)):
        value=_int(raw_string)
        if not -(1<<95)<value<(1<<95):raise BindingRefusal('raw/opposite range')
        is_zero=q[axis]==0;zero.append(is_zero)
        if kind!=('EXACT_ZERO_AXIS' if is_zero else 'NONLINEAR_V2') or (is_zero and value!=0):raise BindingRefusal('zero lane')
        if is_zero:legacy.append(None);continue
        legacy.append(dict(format='c1b1-exact-impulse-certificate-v2',method='dyadic-outward-taylor-v2',
            model=dict(contract='c1a-ar2-lang2024-v1',parameter_fingerprint='ada6153be05af3e582139fdc81b5697fffaf18d12f9f2de6e8d5ac2fdfe0839e',retardation=True),
            input=dict(position_frac_bits=48,dr_raw=[str(v) for v in q],component=axis,dt_kick='20/1'),
            output=dict(width=96,frac_bits=80,raw=raw_string),
            proof=dict(sqrt_bits=proof['sqrt_bits'],work_bits=proof['work_bits'],exp=legacy_plan)))
    return Preparation(tuple(legacy),tuple(zero))

def invoke(preparation):
    # No active instance, whole-call V2 majorant or enforced worker exists.
    raise RuntimeError('POLICY_UNBOUND: runtime_activation_allowed=false')
