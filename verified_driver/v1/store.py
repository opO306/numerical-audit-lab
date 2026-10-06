"""New V1 append-only chain store; durable CURRENT is the authority boundary."""
from contextlib import contextmanager
import os
from pathlib import Path
import uuid
from .model import ChainState, canonical_bytes, strict_json, check_hash, digest_bytes, HARNESS_SHA

class ChainStore:
    def __init__(self,root:Path,*,_crash_hook=None):
        self.root=Path(root).absolute()
        if self.root.is_symlink(): raise ValueError('store root alias')
        self.root.mkdir(parents=True,exist_ok=True)
        self._crash_hook=_crash_hook
        for name in ('objects','receipts','replay_transitions'):
            p=self.root/name
            if p.is_symlink(): raise ValueError('store namespace alias')
            p.mkdir(exist_ok=True)

    @contextmanager
    def _lock(self):
        import fcntl
        p=self.root/'.lock'
        if p.is_symlink(): raise ValueError('lock alias')
        with p.open('a+b') as stream:
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
            if path.read_bytes()!=data: raise ValueError('immutable object bytes conflict')
        self._sync_dir(path.parent)

    def _pointer(self,identity):
        check_hash(identity)
        if (self.root/'CURRENT').is_symlink(): raise ValueError('CURRENT alias')
        tmp=self.root/('.CURRENT.'+uuid.uuid4().hex+'.tmp')
        self._exclusive(tmp,(identity+'\n').encode('ascii'))
        self._point('before_current_replace')
        os.replace(tmp,self.root/'CURRENT')
        self._point('after_current_replace')
        self._sync_dir(self.root)

    def _state(self,identity):
        check_hash(identity); p=self.root/'objects'/(identity+'.json')
        if p.is_symlink(): raise ValueError('object alias')
        try: data=p.read_bytes(); state=ChainState(**strict_json(data))
        except (OSError,TypeError) as exc: raise ValueError('unavailable certified object') from exc
        if state.content_hash!=identity or canonical_bytes(state)!=data: raise ValueError('certified object identity/canonical bytes')
        return state

    def _receipt(self,state,data):
        r=strict_json(data)
        if canonical_bytes(r)!=data or digest_bytes(data)!=state.acceptance_id: raise ValueError('acceptance bytes/identity')
        if r.get('schema')!='VERIFIED_CHAIN_ACCEPTANCE_V1' or r.get('verdict')!='ACCEPT': raise ValueError('only verified acceptance may publish')
        if r.get('candidate')!=strict_json(canonical_bytes(state.candidate_document())) or r.get('predecessor_id')!=state.predecessor_id:
            raise ValueError('exact candidate and predecessor acceptance binding')
        for key in ('checkpoint_id','edge_completion_sha256'): check_hash(r.get(key))
        if 'replay_transition_id' in r: check_hash(r['replay_transition_id'])

    def _historical_chain(self,state):
        chain=[state]
        while state.generation: state=self._state(state.predecessor_id); chain.append(state)
        return tuple(reversed(chain))

    def _transition(self,identity,parent):
        check_hash(identity); p=self.root/'replay_transitions'/(identity+'.json')
        if p.is_symlink() or p.parent.is_symlink(): raise ValueError('replay transition alias')
        if p.is_file() and p.stat().st_size>8388608: raise ValueError('bounded replay proof summary required')
        try: data=p.read_bytes(); document=strict_json(data)
        except (OSError,TypeError) as exc: raise ValueError('immutable replay transition unavailable') from exc
        if digest_bytes(data)!=identity or canonical_bytes(document)!=data: raise ValueError('replay transition immutable hash/canonical binding')
        from .replay import ReplayTransition
        return ReplayTransition.validate(document,self._historical_chain(parent))

    def add_replay_transition(self,document):
        from .replay import ReplayTransition
        with self._lock():
            _,parent=self._current()
            ReplayTransition.validate(document,self._historical_chain(parent))
            data=canonical_bytes(document); identity=digest_bytes(data)
            p=self.root/'replay_transitions'/(identity+'.json')
            self._exclusive(p,data); p.chmod(0o444)
            return identity

    def _link(self,parent,child,receipt=None):
        if parent.barrier_kind=='FINAL_TERMINAL' or child.generation!=parent.generation+1 or child.predecessor_id!=parent.content_hash or child.requested_steps!=parent.requested_steps:
            raise ValueError('certified lineage/request mismatch')
        if parent.generation:
            if receipt is not None and 'replay_transition_id' in receipt:
                # Only this first child may replace the historical process with
                # the fully replayed fresh anchor. Later links remain ordinary.
                parent=self._transition(receipt['replay_transition_id'],parent)
            if child.live_session_id!=parent.live_session_id or child.process_identity_digest!=parent.process_identity_digest:
                raise ValueError('live chain session/process mismatch')
            if child.trace_prefix_bytes<=parent.trace_prefix_bytes or child.verified_frontier<=parent.verified_frontier or child.source_binding!=parent.source_binding:
                raise ValueError('strict forward prefix/frontier/source required')
        elif receipt is not None and 'replay_transition_id' in receipt:
            raise ValueError('genesis cannot use replay transition')

    def _current(self):
        p=self.root/'CURRENT'
        if p.is_symlink(): raise ValueError('CURRENT alias')
        try: raw=p.read_bytes()
        except OSError as exc: raise ValueError('CURRENT unavailable') from exc
        if len(raw)!=65 or raw[-1:]!=b'\n': raise ValueError('CURRENT malformed')
        try: identity=raw[:-1].decode('ascii'); state=self._state(identity)
        except (UnicodeError,OSError) as exc: raise ValueError('CURRENT unresolved') from exc
        cursor=state
        while cursor.generation:
            p=self.root/'receipts'/(cursor.acceptance_id+'.json')
            if p.is_symlink(): raise ValueError('receipt alias')
            try: data=p.read_bytes()
            except OSError as exc: raise ValueError('acceptance unavailable') from exc
            self._receipt(cursor,data)
            parent=self._state(cursor.predecessor_id); self._link(parent,cursor,strict_json(data)); cursor=parent
        if cursor.source_binding!=HARNESS_SHA: raise ValueError('pinned genesis required')
        return identity,state

    def current(self):
        with self._lock(): return self._current()
    def recover(self): return self.current()
    def chain(self):
        with self._lock():
            _,s=self._current(); chain=[s]
            while s.generation: s=self._state(s.predecessor_id); chain.append(s)
            return tuple(reversed(chain))

    def initialize(self,genesis):
        if genesis.generation!=0: raise ValueError('genesis required')
        with self._lock():
            if (self.root/'CURRENT').is_symlink(): raise ValueError('CURRENT alias')
            if (self.root/'CURRENT').exists():
                if self.chain_unlocked_genesis().content_hash!=genesis.content_hash: raise ValueError('store already bound to another genesis')
                return genesis.content_hash
            self._exclusive(self.root/'objects'/(genesis.content_hash+'.json'),canonical_bytes(genesis))
            self._pointer(genesis.content_hash)
            return genesis.content_hash

    def chain_unlocked_genesis(self):
        _,s=self._current()
        while s.generation: s=self._state(s.predecessor_id)
        return s

    def publish(self,expected_state_id,state,acceptance_bytes):
        check_hash(expected_state_id)
        if state.generation==0: raise ValueError('cannot publish genesis candidate')
        self._receipt(state,acceptance_bytes)
        with self._lock():
            identity,parent=self._current()
            if identity==state.content_hash:
                if state.predecessor_id!=expected_state_id: raise ValueError('retry predecessor mismatch')
                return identity
            if identity!=expected_state_id: raise ValueError('CURRENT predecessor changed')
            self._link(parent,state,strict_json(acceptance_bytes))
            self._exclusive(self.root/'receipts'/(state.acceptance_id+'.json'),acceptance_bytes)
            self._exclusive(self.root/'objects'/(state.content_hash+'.json'),canonical_bytes(state))
            self._point('after_objects'); self._pointer(state.content_hash)
            return state.content_hash
