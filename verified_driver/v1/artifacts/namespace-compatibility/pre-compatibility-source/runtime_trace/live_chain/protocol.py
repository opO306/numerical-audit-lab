"""Bounded private-pipe records and exact single-use resume authority."""
from dataclasses import dataclass, asdict
import os, secrets, select, time
from verified_driver.v1.model import canonical_bytes, strict_json, check_hash, FrozenDict

MAX_FRAME=65536
def freeze(value):
    if isinstance(value,dict): return FrozenDict({k:freeze(v) for k,v in value.items()})
    if isinstance(value,(list,tuple)): return tuple(freeze(v) for v in value)
    return value

@dataclass(frozen=True)
class BarrierEvent:
    session_id: str
    barrier_seq: int
    completed_step: int
    barrier_kind: str
    requested_steps: int
    process_identity: dict
    trace_prefix_bytes: int
    trace_prefix_sha256: str
    trace_chain_hash: str
    predecessor_id: str
    checkpoint_state: dict
    def __post_init__(self):
        for v in (self.session_id,self.trace_prefix_sha256,self.trace_chain_hash,self.predecessor_id): check_hash(v)
        for name in ('barrier_seq','completed_step','requested_steps','trace_prefix_bytes'):
            if type(getattr(self,name)) is not int: raise ValueError('strict barrier integer')
        if not 1<=self.completed_step<=self.requested_steps<=100 or self.barrier_seq!=self.completed_step or self.trace_prefix_bytes<=0:
            raise ValueError('ordered bounded barrier required')
        if self.barrier_kind!=('FINAL_TERMINAL' if self.completed_step==self.requested_steps else 'NEXT_STEP_ENTRY'):
            raise ValueError('barrier kind/scope mismatch')
        if not isinstance(self.process_identity,dict) or not self.process_identity: raise ValueError('live process identity required')
        if not isinstance(self.checkpoint_state,dict): raise ValueError('checkpoint snapshot required')
        object.__setattr__(self,'process_identity',freeze(self.process_identity))
        object.__setattr__(self,'checkpoint_state',freeze(self.checkpoint_state))

@dataclass(frozen=True)
class ResumeToken:
    session_id: str
    barrier_seq: int
    predecessor_generation: int
    candidate_generation: int
    checkpoint_id: str
    state_id: str
    nonce: str
    def __post_init__(self):
        for v in (self.session_id,self.checkpoint_id,self.state_id,self.nonce): check_hash(v)
        for name in ('barrier_seq','predecessor_generation','candidate_generation'):
            if type(getattr(self,name)) is not int: raise ValueError('strict token integer')
        if self.predecessor_generation<0 or self.candidate_generation!=self.predecessor_generation+1 or self.barrier_seq!=self.candidate_generation:
            raise ValueError('token generation/sequence mismatch')

class TokenLedger:
    def __init__(self): self._issued={}; self._consumed=set(); self._last={}
    def issue(self,*,current_state_id,**binding):
        if current_state_id!=binding.get('state_id'): raise ValueError('CURRENT must prove candidate before token issue')
        token=ResumeToken(**binding,nonce=secrets.token_hex(32))
        if token.barrier_seq!=self._last.get(token.session_id,0)+1: raise ValueError('skipped/stale/duplicate token issue')
        self._issued[token.nonce]=token; self._last[token.session_id]=token.barrier_seq
        return token
    def consume(self,token,**expected):
        if not isinstance(token,ResumeToken) or token.nonce in self._consumed or self._issued.get(token.nonce)!=token:
            raise ValueError('unissued/substituted/consumed token')
        actual=asdict(token); actual.pop('nonce')
        if actual!=expected: raise ValueError('exact live transaction token binding required')
        self._consumed.add(token.nonce)

def encode_record(record):
    raw=canonical_bytes(record)+b'\n'
    if len(raw)>MAX_FRAME or not isinstance(record,dict): raise ValueError('bounded object frame required')
    return raw

def decode_record(raw):
    if type(raw) is not bytes or len(raw)>MAX_FRAME or raw[-1:]!=b'\n' or b'\n' in raw[:-1]:
        raise ValueError('one bounded complete JSON-line frame required')
    record=strict_json(raw[:-1])
    if canonical_bytes(record)+b'\n'!=raw: raise ValueError('canonical IPC frame required')
    return record

def write_frame(fd,record):
    raw=encode_record(record)
    while raw:
        written=os.write(fd,raw)
        if written<=0: raise EOFError('authority pipe closed')
        raw=raw[written:]

def read_frame(fd,timeout):
    deadline=time.monotonic()+timeout; raw=bytearray()
    while len(raw)<MAX_FRAME:
        left=deadline-time.monotonic()
        if left<=0 or not select.select([fd],[],[],left)[0]: raise TimeoutError('authority pipe timeout')
        value=os.read(fd,1)
        if not value: raise EOFError('authority controller lost')
        raw.extend(value)
        if value==b'\n': return decode_record(bytes(raw))
    raise ValueError('IPC frame ceiling')
