"""Immutable full continuation records, distinct from V0 public outputs."""
from dataclasses import asdict, dataclass
import math
from pathlib import Path
import re
from verified_driver.v0.model import (HARNESS_SHA, GENESIS_BITS, canonical_bytes,
    content_id, digest_bytes, strict_json, check_hash)

ZERO='0x0000000000000000'
DT='0x3f90000000000000'
BASIS={'k':4,'meaning':'computed-minus-true','reseeded':False}

class FrozenDict(dict):
    def _no(self,*a,**k): raise TypeError('immutable continuation mapping')
    __setitem__=__delitem__=clear=pop=popitem=setdefault=update=__ior__=_no
    def __deepcopy__(self,memo): return self

def bits(value):
    if type(value) is not str or re.fullmatch(r'0x[0-9a-f]{16}',value) is None:
        raise ValueError('canonical binary64 bits required')
    if (int(value,16)>>52)&0x7ff==0x7ff: raise ValueError('finite binary64 required')

def lanes(value,count):
    result=tuple(value)
    if len(result)!=count: raise ValueError('exact lane count required')
    for v in result: bits(v)
    return result

def hexfloat(value,*,box=False):
    if type(value) is not str: raise ValueError('canonical Form hex string required')
    try: number=float.fromhex(value)
    except (ValueError,OverflowError) as exc: raise ValueError('invalid Form number') from exc
    if not math.isfinite(number) or number.hex()!=value or box and number<0:
        raise ValueError('finite canonical Form coefficient/nonnegative box required')

@dataclass(frozen=True)
class FormLane:
    center_bits: str
    coefficients: tuple[str,str,str,str]
    box: str
    source_state_id: str
    component: str
    byte_offset: int
    def __post_init__(self):
        bits(self.center_bits)
        object.__setattr__(self,'coefficients',tuple(self.coefficients))
        if len(self.coefficients)!=4: raise ValueError('K=4 coefficient count required')
        for v in self.coefficients: hexfloat(v)
        hexfloat(self.box,box=True)
        if type(self.source_state_id) is not str or not self.source_state_id or len(self.source_state_id)>512:
            raise ValueError('exact source state identity required')
        if self.component not in ('q','full_v','latent') or type(self.byte_offset) is not int or self.byte_offset not in (0,8):
            raise ValueError('supported logical continuation role required')

@dataclass(frozen=True)
class ChainState:
    generation: int
    step_index: int
    requested_steps: int
    barrier_kind: str
    public_bits: tuple[str,...]
    q_bits: tuple[str,...]
    full_v_bits: tuple[str,...]
    latent_bits: tuple[str,...]
    gradient_bits: tuple[str,...]
    next_t_bits: str|None
    dt_bits: str
    forms: tuple[FormLane,...]
    basis_contract: dict
    live_basis_namespace: str|None
    source_binding: str
    trace_prefix_sha256: str|None
    trace_prefix_bytes: int
    verified_frontier: int
    predecessor_id: str|None
    acceptance_id: str|None
    live_session_id: str|None
    process_identity_digest: str|None
    barrier_seq: int

    def __post_init__(self):
        for name in ('generation','step_index','requested_steps','trace_prefix_bytes','verified_frontier','barrier_seq'):
            if type(getattr(self,name)) is not int: raise ValueError('strict integer '+name)
        if not 1<=self.requested_steps<=100 or not 0<=self.generation<=self.requested_steps:
            raise ValueError('bounded requested scope required')
        if self.generation!=self.step_index or self.barrier_seq!=self.step_index: raise ValueError('generation/step/barrier sequence')
        for name,count in [('public_bits',4),('q_bits',2),('full_v_bits',2),('latent_bits',2),('gradient_bits',2)]:
            object.__setattr__(self,name,lanes(getattr(self,name),count))
        if self.gradient_bits!=(ZERO,ZERO): raise ValueError('observed exact-zero gradient reset required')
        bits(self.dt_bits)
        if self.dt_bits!=DT: raise ValueError('only represented dt=1/64 supported')
        if self.next_t_bits is not None: bits(self.next_t_bits)
        if dict(self.basis_contract)!=BASIS: raise ValueError('K=4 computed-minus-true no-reseed contract required')
        object.__setattr__(self,'basis_contract',FrozenDict(self.basis_contract))
        object.__setattr__(self,'forms',tuple(f if isinstance(f,FormLane) else FormLane(**f) for f in self.forms))
        check_hash(self.source_binding)
        if self.generation==0:
            if self.barrier_kind!='GENESIS' or self.public_bits!=GENESIS_BITS or self.q_bits!=GENESIS_BITS[:2] or self.full_v_bits!=GENESIS_BITS[2:] or self.latent_bits!=GENESIS_BITS[2:]:
                raise ValueError('pinned regular genesis required')
            if self.source_binding!=HARNESS_SHA or self.forms or self.trace_prefix_bytes!=0 or self.verified_frontier!=-1 or self.next_t_bits!=ZERO:
                raise ValueError('genesis contract')
            if any(v is not None for v in (self.predecessor_id,self.acceptance_id,self.live_session_id,self.process_identity_digest,self.trace_prefix_sha256,self.live_basis_namespace)):
                raise ValueError('genesis cannot claim acquired acceptance')
            return
        if self.barrier_kind!=('FINAL_TERMINAL' if self.step_index==self.requested_steps else 'NEXT_STEP_ENTRY'):
            raise ValueError('entry or final terminal must match requested scope')
        if self.barrier_kind=='NEXT_STEP_ENTRY' and self.next_t_bits is None: raise ValueError('next entry t required')
        if self.barrier_kind=='FINAL_TERMINAL' and self.next_t_bits is not None: raise ValueError('terminal has no successor t')
        if self.public_bits!=self.q_bits+self.full_v_bits: raise ValueError('public and full continuation q/v disagree')
        for v in (self.predecessor_id,self.acceptance_id,self.live_session_id,self.process_identity_digest,self.trace_prefix_sha256): check_hash(v)
        if self.live_basis_namespace!=self.live_session_id+'/global-error-basis': raise ValueError('strict live basis namespace')
        if self.trace_prefix_bytes<=0 or self.verified_frontier<0: raise ValueError('verified acquired prefix/frontier required')
        roles=[(f.component,f.byte_offset) for f in self.forms]
        if roles!=[(name,offset) for name in ('q','full_v','latent') for offset in (0,8)]: raise ValueError('exact six ordered carry lanes')
        for f in self.forms:
            if f.center_bits!=getattr(self,f.component+'_bits')[f.byte_offset//8]: raise ValueError('Form center/continuation lane mismatch')

    @property
    def content_hash(self): return content_id(self)

    def candidate_document(self):
        result=asdict(self); result.pop('acceptance_id')
        return result

@dataclass(frozen=True)
class ChainResult:
    verdict: str
    run_id: str
    state_id: str|None
    generation: int|None
    step_index: int|None
    reason: str

def chain_genesis(repo_root:Path,requested_steps:int)->ChainState:
    if digest_bytes((Path(repo_root)/'runtime_trace/harness.py').read_bytes())!=HARNESS_SHA:
        raise ValueError('pinned regular harness mismatch')
    return ChainState(0,0,requested_steps,'GENESIS',GENESIS_BITS,GENESIS_BITS[:2],GENESIS_BITS[2:],GENESIS_BITS[2:],
        (ZERO,ZERO),ZERO,DT,(),BASIS,None,HARNESS_SHA,None,0,-1,None,None,None,None,0)
