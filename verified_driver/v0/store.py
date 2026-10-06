"""Append-only accepted objects and receipts, locked atomic CURRENT publication."""
from contextlib import contextmanager
import os
from pathlib import Path
import uuid
from .model import CertifiedState, GENESIS_BITS, HARNESS_SHA, canonical_bytes, check_hash, digest_bytes, strict_json

class CertifiedStore:
    def __init__(self,root,*,_crash_hook=None):
        self.root=Path(root).resolve()
        self.root.mkdir(parents=True,exist_ok=True)
        self._crash_hook=_crash_hook
        for name in ('objects','receipts'):
            path=self.root/name
            if path.is_symlink(): raise ValueError('store namespace alias')
            path.mkdir(exist_ok=True)

    @contextmanager
    def _lock(self):
        import fcntl
        with (self.root/'.lock').open('a+b') as stream:
            fcntl.flock(stream,fcntl.LOCK_EX)
            yield

    def _point(self,name):
        if self._crash_hook: self._crash_hook(name)

    def _sync_dir(self,path):
        fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY)
        try: os.fsync(fd)
        finally: os.close(fd)

    def _exclusive(self,path,data):
        if path.is_symlink() or path.parent.is_symlink(): raise ValueError('store namespace alias')
        try:
            with path.open('xb') as stream:
                stream.write(data); stream.flush(); os.fsync(stream.fileno())
        except FileExistsError:
            if path.read_bytes()!=data: raise ValueError('content-addressed bytes differ')
        self._sync_dir(path.parent)

    def _pointer(self,identity):
        check_hash(identity)
        path=self.root/('.CURRENT.'+uuid.uuid4().hex+'.tmp')
        self._exclusive(path,(identity+'\n').encode())
        self._point('before_replace')
        os.replace(path,self.root/'CURRENT')
        self._point('after_replace')
        self._sync_dir(self.root)

    def _state(self,identity):
        check_hash(identity)
        path=self.root/'objects'/(identity+'.json')
        if path.is_symlink(): raise ValueError('object alias')
        try:
            data=path.read_bytes(); state=CertifiedState(**strict_json(data))
        except (OSError,TypeError) as exc: raise ValueError('unavailable certified object') from exc
        if state.content_hash!=identity or canonical_bytes(state)!=data:
            raise ValueError('certified object identity/canonical bytes')
        return state

    def _receipt(self,state,data):
        receipt=strict_json(data)
        if canonical_bytes(receipt)!=data or digest_bytes(data)!=state.acceptance_id:
            raise ValueError('acceptance bytes/identity')
        if receipt.get('schema')!='DRIVER_V0_ACCEPTANCE_V1' or receipt.get('verdict')!='ACCEPT':
            raise ValueError('only accepted receipts publish')
        n=receipt.get('requested_steps')
        if type(n) is not int or not 1<=n<=100 or type(receipt.get('checked_steps')) is not int or receipt['checked_steps']!=n or receipt.get('requested_complete') is not True:
            raise ValueError('incomplete acceptance receipt')
        for name in ('candidate_id','completion_sha256','acquisition_id','source_pinset_sha256'):
            check_hash(receipt.get(name))
        for name,want in [('transaction_id',state.transaction_id),('predecessor_id',state.predecessor_id),
            ('source_pinset_sha256',state.source_binding),('acquisition_id',state.run_id)]:
            if receipt.get(name)!=want: raise ValueError('state/acceptance binding')
        if tuple(receipt.get('output_bits',()))!=state.state_bits: raise ValueError('accepted output binding')
        return receipt

    def _current(self):
        pointer=self.root/'CURRENT'
        if pointer.is_symlink(): raise ValueError('CURRENT alias')
        try: raw=pointer.read_bytes()
        except OSError as exc: raise ValueError('CURRENT unavailable') from exc
        if len(raw)!=65 or raw[-1:]!=b'\n': raise ValueError('truncated CURRENT')
        try: identity=raw[:-1].decode('ascii'); check_hash(identity)
        except (UnicodeError,ValueError) as exc: raise ValueError('malformed CURRENT') from exc
        state=self._state(identity); previous=state
        while previous.generation:
            receipt_path=self.root/'receipts'/(previous.acceptance_id+'.json')
            if receipt_path.is_symlink(): raise ValueError('receipt alias')
            try: data=receipt_path.read_bytes()
            except OSError as exc: raise ValueError('acceptance unavailable') from exc
            self._receipt(previous,data)
            parent=self._state(previous.predecessor_id)
            if parent.generation+1!=previous.generation: raise ValueError('generation lineage')
            previous=parent
        if previous.state_bits!=GENESIS_BITS or previous.source_binding!=HARNESS_SHA:
            raise ValueError('unsupported genesis contract')
        return identity,state

    def current(self):
        with self._lock(): return self._current()

    def recover(self): return self.current()

    def initialize(self,genesis):
        if genesis.generation!=0 or genesis.state_bits!=GENESIS_BITS or genesis.source_binding!=HARNESS_SHA:
            raise ValueError('regular genesis required')
        with self._lock():
            if (self.root/'CURRENT').is_symlink(): raise ValueError('CURRENT alias')
            identity=genesis.content_hash
            self._exclusive(self.root/'objects'/(identity+'.json'),canonical_bytes(genesis))
            if (self.root/'CURRENT').exists(): self._current()
            else: self._pointer(identity)
            return identity

    def publish(self,expected_state_id,state,acceptance_bytes):
        check_hash(expected_state_id)
        if state.generation==0: raise ValueError('genesis is not a candidate')
        self._receipt(state,acceptance_bytes)
        with self._lock():
            current_id,current=self._current()
            if current_id==state.content_hash:
                if state.predecessor_id!=expected_state_id: raise ValueError('retry predecessor mismatch')
                return current_id
            if current_id!=expected_state_id or state.predecessor_id!=current_id or state.generation!=current.generation+1:
                raise ValueError('certified predecessor changed')
            self._exclusive(self.root/'receipts'/(state.acceptance_id+'.json'),acceptance_bytes)
            self._exclusive(self.root/'objects'/(state.content_hash+'.json'),canonical_bytes(state))
            self._point('after_objects')
            self._pointer(state.content_hash)
            return state.content_hash
