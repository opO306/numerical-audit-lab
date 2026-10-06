"""Immutable canonical records; certification is conditional on the RT contract."""
from dataclasses import asdict, dataclass, is_dataclass
import hashlib
import json
from pathlib import Path
import re

HARNESS_SHA = '4928f88e4c6255cfbc3f68798648b543146fb5b13327490d331814f778a9fc26'
GENESIS_BITS = ('0x0000000000000000','0x0000000000000000','0x3fd0000000000000','0x3fc0000000000000')

def canonical_bytes(value):
    if is_dataclass(value): value=asdict(value)
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode('ascii')

def content_id(value): return hashlib.sha256(canonical_bytes(value)).hexdigest()

def digest_bytes(data): return hashlib.sha256(data).hexdigest()

def strict_json(data):
    def pairs(items):
        result={}
        for key,value in items:
            if key in result: raise ValueError('duplicate JSON key')
            result[key]=value
        return result
    def nonfinite(value): raise ValueError('nonfinite JSON')
    result=json.loads(data,object_pairs_hook=pairs,parse_constant=nonfinite)
    if not isinstance(result,dict): raise ValueError('JSON object required')
    canonical_bytes(result)
    return result

def check_hash(value):
    if type(value) is not str or re.fullmatch('[0-9a-f]{64}',value) is None:
        raise ValueError('canonical content identity required')

def check_transaction(value):
    if type(value) is not str or re.fullmatch('[A-Za-z0-9][A-Za-z0-9_-]{0,79}',value) is None:
        raise ValueError('safe transaction identity required')

def check_bits(bits):
    if len(bits)!=4: raise ValueError('exact four state lanes required')
    for value in bits:
        if type(value) is not str or re.fullmatch('0x[0-9a-f]{16}',value) is None:
            raise ValueError('canonical binary64 bits required')
        if (int(value,16)>>52)&0x7ff == 0x7ff: raise ValueError('finite state required')

@dataclass(frozen=True)
class CertifiedState:
    generation: int
    state_bits: tuple[str,...]
    source_binding: str
    predecessor_id: str|None=None
    acceptance_id: str|None=None
    transaction_id: str|None=None
    run_id: str|None=None

    def __post_init__(self):
        if type(self.generation) is not int or self.generation<0: raise ValueError('strict generation')
        object.__setattr__(self,'state_bits',tuple(self.state_bits)); check_bits(self.state_bits)
        check_hash(self.source_binding)
        if self.generation==0:
            if any(v is not None for v in (self.predecessor_id,self.acceptance_id,self.transaction_id,self.run_id)):
                raise ValueError('genesis cannot carry acceptance')
        else:
            check_hash(self.predecessor_id); check_hash(self.acceptance_id); check_hash(self.run_id)
            check_transaction(self.transaction_id)

    @property
    def content_hash(self): return content_id(self)

@dataclass(frozen=True)
class CandidateState:
    transaction_id: str
    predecessor_id: str
    evidence_dir: str
    state_bits: tuple[str,...]
    binding_bytes: bytes

    def __post_init__(self):
        check_transaction(self.transaction_id); check_hash(self.predecessor_id)
        object.__setattr__(self,'state_bits',tuple(self.state_bits)); check_bits(self.state_bits)
        if type(self.binding_bytes) is not bytes: raise ValueError('immutable observed binding required')

    @property
    def content_hash(self):
        return content_id({'transaction_id':self.transaction_id,'predecessor_id':self.predecessor_id,
            'evidence_dir':self.evidence_dir,'state_bits':self.state_bits,'binding_sha256':digest_bytes(self.binding_bytes)})

@dataclass(frozen=True)
class GateDecision:
    verdict: str
    reason: str
    acceptance_bytes: bytes|None=None

@dataclass(frozen=True)
class DriverResult:
    verdict: str
    transaction_id: str
    state_id: str
    generation: int
    reason: str
    candidate_id: str|None=None
    driver_seconds: float=0.
    runtime_seconds: float=0.

def regular_genesis(repo_root):
    data=(Path(repo_root)/'runtime_trace/harness.py').read_bytes()
    if digest_bytes(data)!=HARNESS_SHA: raise ValueError('pinned regular harness mismatch')
    return CertifiedState(0,GENESIS_BITS,HARNESS_SHA)
