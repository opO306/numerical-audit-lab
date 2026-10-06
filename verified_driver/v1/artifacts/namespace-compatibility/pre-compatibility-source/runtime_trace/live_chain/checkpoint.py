"""Exclusive immutable snapshots of exact live trace prefixes."""
from dataclasses import asdict
import hashlib, os
from pathlib import Path
from verified_driver.v1.model import canonical_bytes, strict_json, content_id, digest_bytes, check_hash

def no_alias(path):
    path=Path(path).absolute()
    for p in (path,*path.parents):
        if p.is_symlink(): raise ValueError('checkpoint path alias')
    return path

def chain_hash(raw):
    value=bytes(32)
    if not raw or raw[-1:]!=b'\n': raise ValueError('complete trace prefix required')
    for row in raw.splitlines(keepends=True): value=hashlib.sha256(value+row).digest()
    return value.hex()

def sync_dir(path):
    fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY)
    try: os.fsync(fd)
    finally: os.close(fd)

def sealed_write(path,data):
    # Share the existing job's pre-write allocation; small unit fixtures are
    # likewise launched under that quota by the workflow runner.
    from runtime_trace.regular_nstep.resources import reserve_writer
    reserve_writer(len(data))
    with Path(path).open('xb') as f: f.write(data); f.flush(); os.fsync(f.fileno())
    Path(path).chmod(0o444)

class CheckpointSealer:
    def __init__(self,root:Path): self.root=no_alias(root); self._prefixes=[]
    def assert_prefixes(self,master_trace):
        master=no_alias(master_trace)
        with master.open('rb') as f:
            for size,want in self._prefixes:
                f.seek(0)
                if digest_bytes(f.read(size))!=want: raise ValueError('sealed master prefix changed')
    def seal(self,master_trace,event,metadata,out):
        master=no_alias(master_trace); out=no_alias(out)
        if not master.is_relative_to(self.root) or not out.is_relative_to(self.root) or out==self.root:
            raise ValueError('checkpoint destination/source escapes run root')
        self.assert_prefixes(master)
        if not isinstance(metadata.get('source_snapshot'),dict) or not metadata['source_snapshot']:
            raise ValueError('bound source snapshot required')
        check_hash(metadata.get('source_binding'))
        with master.open('rb') as f:
            os.fsync(f.fileno()); raw=f.read(event.trace_prefix_bytes)
        if len(raw)!=event.trace_prefix_bytes or digest_bytes(raw)!=event.trace_prefix_sha256 or chain_hash(raw)!=event.trace_chain_hash:
            raise ValueError('declared trace prefix/chain mismatch')
        doc={'schema':'LIVE_CHECKPOINT_V1','event':asdict(event),'metadata':metadata}
        data=canonical_bytes(doc); identity=digest_bytes(data)
        out.mkdir(parents=True,exist_ok=False)
        sealed_write(out/'trace.jsonl',raw); sealed_write(out/'checkpoint.json',data)
        sealed_write(out/'CHECKPOINT',(identity+'\n').encode('ascii')); sync_dir(out)
        self._prefixes.append((event.trace_prefix_bytes,event.trace_prefix_sha256))
        return identity

def verify_checkpoint(out,identity=None,*,expected_event=None):
    out=no_alias(out)
    for name in ('CHECKPOINT','checkpoint.json','trace.jsonl'): no_alias(out/name)
    pointer=(out/'CHECKPOINT').read_bytes()
    if len(pointer)!=65 or pointer[-1:]!=b'\n': raise ValueError('checkpoint identity malformed')
    check_hash(pointer[:-1].decode('ascii'))
    if identity is not None and pointer!=(identity+'\n').encode('ascii'): raise ValueError('checkpoint substitution')
    data=(out/'checkpoint.json').read_bytes(); doc=strict_json(data)
    if canonical_bytes(doc)!=data or digest_bytes(data)!=pointer[:-1].decode('ascii') or doc.get('schema')!='LIVE_CHECKPOINT_V1':
        raise ValueError('sealed descriptor mismatch')
    from .protocol import BarrierEvent
    event=BarrierEvent(**doc['event'])
    if expected_event is not None and canonical_bytes(event)!=canonical_bytes(expected_event): raise ValueError('live event substitution')
    raw=(out/'trace.jsonl').read_bytes()
    if len(raw)!=event.trace_prefix_bytes or digest_bytes(raw)!=event.trace_prefix_sha256 or chain_hash(raw)!=event.trace_chain_hash:
        raise ValueError('sealed trace prefix/chain mismatch')
    return doc
