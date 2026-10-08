"""Non-authoritative replay and a hash-bound, single-link LIVE transition."""
from dataclasses import dataclass
from .model import ChainState, ChainResult, FormLane, FrozenDict, check_hash, canonical_bytes, strict_json, content_id, chain_genesis

@dataclass(frozen=True)
class ReplayObservation:
    step_index: int
    requested_steps: int
    barrier_kind: str
    public_bits: tuple
    q_bits: tuple
    full_v_bits: tuple
    latent_bits: tuple
    gradient_bits: tuple
    next_t_bits: str | None
    dt_bits: str
    forms: tuple
    basis_contract: dict
    source_binding: str
    live_basis_namespace: str
    live_session_id: str
    process_identity_digest: str
    trace_prefix_sha256: str
    trace_prefix_bytes: int
    verified_frontier: int
    fresh_predecessor_id: str
    stored_position_id: str
    stored_predecessor_id: str
    checkpoint_id: str
    checker_report_id: str

    def __post_init__(self):
        for name in ('public_bits','q_bits','full_v_bits','latent_bits','gradient_bits','forms'):
            object.__setattr__(self,name,tuple(getattr(self,name)))
        object.__setattr__(self,'basis_contract',FrozenDict(self.basis_contract))
        for name in ('source_binding','live_session_id','process_identity_digest',
                     'trace_prefix_sha256','fresh_predecessor_id','stored_position_id',
                     'stored_predecessor_id','checkpoint_id','checker_report_id'):
            check_hash(getattr(self,name))

    @classmethod
    def from_candidate(cls,candidate,*,stored_position_id,stored_predecessor_id,checkpoint_id,checker_report_id):
        if 'acceptance_id' in candidate: raise ValueError('replay observation has no acceptance authority')
        # Validate representation with a non-publishable placeholder; no receipt
        # or store write is created and the public observation omits authority.
        state=ChainState(**candidate,acceptance_id='0'*64)
        fields={name:getattr(state,name) for name in cls.__dataclass_fields__
                if name not in ('fresh_predecessor_id','stored_position_id','stored_predecessor_id',
                                'checkpoint_id','checker_report_id')}
        return cls(**fields,fresh_predecessor_id=state.predecessor_id,
                   stored_position_id=stored_position_id,stored_predecessor_id=stored_predecessor_id,
                   checkpoint_id=checkpoint_id,checker_report_id=checker_report_id)

    @property
    def may_transition_to_live(self):
        """Scope predicate only; it does not authorize a token or publication."""
        return self.barrier_kind=='NEXT_STEP_ENTRY' and self.step_index<self.requested_steps

class ReplayComparator:
    @staticmethod
    def _logical_source(form,session,step):
        source=form.source_state_id
        tagged=source.startswith('state:')
        value=source.removeprefix('state:')
        prefix=f'{session}/step{step}/'
        if not value.startswith(prefix) or not value[len(prefix):]:
            raise ValueError('replay Form source namespace/occurrence mismatch')
        # Generated Numeric IR IDs contain logical record/producer/byte
        # coordinates, not process-local addresses. Preserve those exactly.
        return ('state:' if tagged else '')+value[len(prefix):]
    @staticmethod
    def compare(stored,observed):
        if not isinstance(stored,ChainState) or not isinstance(observed,ReplayObservation) or stored.generation==0:
            raise ValueError('certified continuation and non-authoritative replay observation required')
        if observed.stored_position_id!=stored.content_hash or observed.stored_predecessor_id!=stored.predecessor_id:
            raise ValueError('replay must match the exact stored chain position and predecessor')
        for name in ('step_index','requested_steps','barrier_kind','public_bits','q_bits','full_v_bits',
                     'latent_bits','gradient_bits','next_t_bits','dt_bits','basis_contract','source_binding'):
            if getattr(stored,name)!=getattr(observed,name): raise ValueError('replay continuation mismatch: '+name)
        if len(stored.forms)!=len(observed.forms): raise ValueError('replay Form lane count')
        for want,actual in zip(stored.forms,observed.forms):
            if not isinstance(actual,FormLane): raise ValueError('replay Form representation')
            for name in ('component','byte_offset','center_bits','coefficients','box'):
                if getattr(want,name)!=getattr(actual,name): raise ValueError('replay Form mismatch: '+name)
            if ReplayComparator._logical_source(want,stored.live_session_id,stored.step_index)!=ReplayComparator._logical_source(actual,observed.live_session_id,observed.step_index):
                raise ValueError('replay Form logical source identity mismatch')
            if stored.live_basis_namespace!=observed.live_basis_namespace and any(float.fromhex(c)!=0 for c in actual.coefficients):
                raise ValueError('nonzero cross-process basis equivalence is unsupported')
        if observed.live_basis_namespace!=observed.live_session_id+'/global-error-basis':
            raise ValueError('fresh replay namespace/provenance mismatch')

class ReplayCarry:
    """Fresh checked carry at an existing historical position, not a generation."""
    def __init__(self,stored,candidate):
        self.stored=stored
        self._fresh=ChainState(**candidate,acceptance_id='0'*64)
        observation=ReplayObservation.from_candidate(candidate,stored_position_id=stored.content_hash,
            stored_predecessor_id=stored.predecessor_id,checkpoint_id='0'*64,checker_report_id='0'*64)
        ReplayComparator.compare(stored,observation)
    def __getattr__(self,name):
        if name=='acceptance_id': raise AttributeError('replay has no acceptance authority')
        return getattr(self._fresh,name)
    @property
    def content_hash(self): return self.stored.content_hash
    def document(self):
        return {'schema':'VERIFIED_REPLAY_CARRY_INPUT_V1','stored':strict_json(canonical_bytes(self.stored)),
                'candidate':self._fresh.candidate_document()}

def predecessor_document(pred):
    return pred.document() if isinstance(pred,ReplayCarry) else pred

def decode_predecessor(doc):
    if doc.get('schema')=='VERIFIED_REPLAY_CARRY_INPUT_V1':
        if set(doc)!={'schema','stored','candidate'}: raise ValueError('replay carry fields')
        return ReplayCarry(ChainState(**doc['stored']),doc['candidate'])
    return ChainState(**doc)

class ReplayTransition:
    @staticmethod
    def document(chain,proofs,sources):
        if not proofs: raise ValueError('complete replay proofs required')
        return strict_json(canonical_bytes({'schema':'VERIFIED_REPLAY_TRANSITION_V1',
            'historical_state_id':chain[-1].content_hash,'genesis_id':chain[0].content_hash,
            'historical_chain':[strict_json(canonical_bytes(state)) for state in chain],
            'replay_proofs':proofs,'source_snapshot':sources,'source_binding':content_id(sources),
            'fresh_anchor':proofs[-1]['checker_report']['candidate']}))

    @staticmethod
    def validate(document,chain):
        keys={'schema','historical_state_id','genesis_id','historical_chain','replay_proofs',
              'source_snapshot','source_binding','fresh_anchor'}
        if set(document)!=keys or document['schema']!='VERIFIED_REPLAY_TRANSITION_V1':
            raise ValueError('complete canonical replay transition schema required')
        parent=chain[-1]
        if parent.generation==0 or parent.barrier_kind!='NEXT_STEP_ENTRY':
            raise ValueError('only a historical nonterminal continuation may transition')
        if document['historical_state_id']!=parent.content_hash or document['genesis_id']!=chain[0].content_hash:
            raise ValueError('stale/wrong-parent replay transition')
        if document['historical_chain']!=[strict_json(canonical_bytes(state)) for state in chain]:
            raise ValueError('exact immutable historical lineage required')
        sources=document['source_snapshot']
        if not isinstance(sources,dict) or not sources or content_id(sources)!=document['source_binding'] or document['source_binding']!=parent.source_binding:
            raise ValueError('complete replay source snapshot binding')
        for name,value in sources.items():
            if not isinstance(name,str) or not name or name.startswith('/') or '..' in name.split('/'):
                raise ValueError('canonical replay source name')
            check_hash(value)
        proofs=document['replay_proofs']
        if not isinstance(proofs,list) or len(proofs)!=parent.generation:
            raise ValueError('complete genesis-to-parent replay proof sequence required')
        anchor=document['fresh_anchor']; carry=None; previous=None
        for stored,proof in zip(chain[1:],proofs):
            if set(proof)!={'checkpoint_id','checker_report','checker_report_sha256'}: raise ValueError('complete replay proof summary')
            check_hash(proof['checkpoint_id']); report=proof['checker_report']
            if content_id(report)!=proof['checker_report_sha256'] or report.get('checkpoint_id')!=proof['checkpoint_id']:
                raise ValueError('replay checkpoint/checker hash binding')
            check_hash(report.get('completion_sha256'))
            if report.get('schema')!='LIVE_EDGE_CHECK_V1' or report.get('verdict')!='CHECKER_PASS' or report.get('evidence_role')!='LIVE' or type(report.get('checked_step')) is not int or report.get('checked_step')!=stored.step_index:
                raise ValueError('independent complete replay edge report required')
            if report.get('formal_certification') is not False or report.get('init_to_step1')!='UNTRACED' or report.get('post_terminal_frontier')!='UNTRACED' or report.get('requested_complete') is not False:
                raise ValueError('retained replay verification scope')
            candidate=report['candidate']
            if candidate['predecessor_id']!=stored.predecessor_id: raise ValueError('replay edge lineage position')
            carry=ReplayCarry(stored,candidate)
            if carry.source_binding!=document['source_binding'] or carry.live_session_id!=anchor['live_session_id'] or carry.process_identity_digest!=anchor['process_identity_digest']:
                raise ValueError('one fresh replay session/process/source required')
            if previous is not None:
                if carry.trace_prefix_bytes<=previous.trace_prefix_bytes or carry.verified_frontier<=previous.verified_frontier:
                    raise ValueError('strict increasing fresh replay prefix/frontier')
            previous=carry
        if anchor!=proofs[-1]['checker_report']['candidate'] or carry.live_session_id==parent.live_session_id:
            raise ValueError('exact fresh anchor in a new replay namespace required')
        return carry

from .live_chain.protocol import TokenLedger, ResumeToken

class ReplayTokenLedger(TokenLedger):
    def issue_replay(self,store,expected_current,stored,observation,**binding):
        """Stored ancestor authority permits replay only; token binding stays exact."""
        import secrets
        if store.recover()[0]!=expected_current or not any(s.content_hash==stored.content_hash for s in store.chain()):
            raise ValueError('stable CURRENT and its verified historical ancestor required')
        ReplayComparator.compare(stored,observation)
        token=ResumeToken(**binding,nonce=secrets.token_hex(32))
        if token.state_id!=stored.content_hash or token.candidate_generation!=stored.generation or token.session_id!=observation.live_session_id or token.checkpoint_id!=observation.checkpoint_id or token.barrier_seq!=self._last.get(token.session_id,0)+1:
            raise ValueError('exact stored-position/fresh-checkpoint replay token required')
        self._issued[token.nonce]=token; self._last[token.session_id]=token.barrier_seq
        return token

class ReplayEngine:
    def __init__(self,driver_factory,store): self.driver_factory=driver_factory; self.store=store
    def recover(self,requested_steps,run_id,*,continue_live=True):
        import re,time
        from .live_chain.checkpoint import CheckpointSealer,sealed_write
        from .live_chain.session import live_source_snapshot
        from runtime_trace.regular_nstep.acquire import validate_n
        n=validate_n(requested_steps)
        if not isinstance(run_id,str) or re.fullmatch(r'[a-z0-9][a-z0-9-]{0,63}',run_id) is None: raise ValueError('bounded recovery run identity')
        driver=self.driver_factory()
        if driver.store.root!=self.store.root: raise ValueError('replay driver/store mismatch')
        chain=self.store.chain(); target=chain[-1]; original=target.content_hash
        if chain[0]!=chain_genesis(driver.repo_root,n): raise ValueError('replay original pinned genesis/scope required')
        if target.generation==0:
            if not continue_live:
                return ChainResult('REPLAYED',run_id,original,0,0,'pinned genesis matched; replay-only creates no process or generation')
            return driver.run(n,run_id)
        out=driver.run_root/run_id; started=time.perf_counter()
        try:
            out.mkdir(parents=True,exist_ok=False); sealer=CheckpointSealer(out); tokens=ReplayTokenLedger()
            driver.session=driver._make_session(driver.repo_root,out/'live',n,driver.ledger)
            event=driver.session.start(); pred=chain[0]; proofs=[]
            for stored in chain[1:]:
                if self.store.recover()[0]!=original: raise ValueError('CURRENT changed during replay')
                driver._event(event,pred); cp=out/f'replay-checkpoint-{stored.step_index}'
                cid=sealer.seal(driver.session.master_trace,event,driver.session.metadata,cp)
                report=driver._gate.observe(cid,cp,pred,out/f'replay-edge-{stored.step_index}',driver.repo_root)
                if report.get('verdict')!='CHECKER_PASS' or report.get('checkpoint_id')!=cid or report.get('evidence_role')!='LIVE':
                    raise ValueError('independent fresh replay edge refused')
                observed=ReplayObservation.from_candidate(report['candidate'],stored_position_id=stored.content_hash,
                    stored_predecessor_id=stored.predecessor_id,checkpoint_id=cid,checker_report_id=content_id(report))
                ReplayComparator.compare(stored,observed); pred=ReplayCarry(stored,report['candidate'])
                proofs.append({'checkpoint_id':cid,'checker_report':report,'checker_report_sha256':content_id(report)})
                driver._paused(event)
                sealer.assert_prefixes(driver.session.master_trace)
                if stored.barrier_kind=='FINAL_TERMINAL':
                    driver.session.finish(); break
                if stored.generation==target.generation: break
                driver.session.bind_checkpoint(cid,cp,stored.content_hash,stored.generation-1)
                binding=dict(session_id=event.session_id,barrier_seq=event.barrier_seq,
                    predecessor_generation=stored.generation-1,candidate_generation=stored.generation,
                    checkpoint_id=cid,state_id=stored.content_hash)
                token=tokens.issue_replay(self.store,original,stored,observed,**binding)
                tokens.consume(token,**binding); driver._paused(event)
                if self.store.recover()[0]!=original: raise ValueError('CURRENT changed before replay resume')
                sealer.assert_prefixes(driver.session.master_trace)
                event=driver.session.resume(token)
            if self.store.recover()[0]!=original: raise ValueError('CURRENT changed after replay')
            sealed_write(out/'replay-proof.json',canonical_bytes({'historical_state_id':original,'proofs':proofs,
                'publication_during_replay':False,'replay_seconds':time.perf_counter()-started}))
            if target.barrier_kind=='FINAL_TERMINAL' or not continue_live:
                driver.session.terminate('replay verified without new numerical generation')
                verdict='ACCEPT' if target.barrier_kind=='FINAL_TERMINAL' else 'REPLAYED'
                return ChainResult(verdict,run_id,original,target.generation,target.step_index,'fresh replay matched existing certified chain; no publication')
            document=ReplayTransition.document(chain,proofs,driver.session.sources)
            ReplayTransition.validate(document,chain); transition_id=self.store.add_replay_transition(document)
            driver._paused(event); driver.session.bind_checkpoint(cid,cp,original,target.generation-1)
            binding=dict(session_id=event.session_id,barrier_seq=event.barrier_seq,
                predecessor_generation=target.generation-1,candidate_generation=target.generation,
                checkpoint_id=cid,state_id=original)
            token=tokens.issue(current_state_id=self.store.recover()[0],**binding)
            tokens.consume(token,**binding); driver._paused(event)
            if self.store.recover()[0]!=original: raise ValueError('CURRENT changed before LIVE transition resume')
            sealer.assert_prefixes(driver.session.master_trace)
            event=driver.session.resume(token)
            while event is not None:
                event,pred=driver._advance(event,pred,out,sealer,tokens,transition_id=transition_id)
                transition_id=None
            driver.session.terminate('recovered requested chain complete')
            result=ChainResult('ACCEPT',run_id,pred.content_hash,pred.generation,pred.step_index,'replay then strict live continuation complete; wrapper tail UNTRACED')
            sealed_write(out/'result.json',canonical_bytes(result)); return result
        except Exception as exc:
            result=driver._stop(run_id,type(exc).__name__+': '+str(exc))
            if out.is_dir() and not (out/'result.json').exists(): sealed_write(out/'result.json',canonical_bytes(result))
            return result
