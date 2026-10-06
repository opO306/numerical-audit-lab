"""Isolated original-runtime proposal, fresh gate, then atomic publication."""
from dataclasses import asdict
import os
from pathlib import Path
import sys
import time
import uuid
from .fallback import FallbackRegistry
from .gate import candidate_from_evidence,evaluate_candidate,file_json,file_sha,source_snapshot,STAGES
from .model import CertifiedState,DriverResult,canonical_bytes,check_transaction,digest_bytes,regular_genesis,strict_json

def _write(path,value,*,reserve=None,newline=False):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    data=canonical_bytes(value)+(b'\n' if newline else b'')
    if len(data)>1048576: raise ValueError('bounded Driver metadata required')
    if reserve: reserve(len(data))
    with path.open('xb') as stream:
        stream.write(data); stream.flush(); os.fsync(stream.fileno())

def _isolated(path,store_root):
    raw=Path(path)
    if raw.is_symlink(): raise ValueError('pending alias')
    path=raw.resolve()
    if path==store_root or path.is_relative_to(store_root) or store_root.is_relative_to(path):
        raise ValueError('pending/certified namespaces overlap')
    return path

class VerifiedDriver:
    def __init__(self,repo_root,store,pending_root,ledger,fallback=None):
        self.repo_root=Path(repo_root).resolve(); self.store=store
        self.pending_root=_isolated(pending_root,store.root)
        self.ledger=Path(ledger).resolve(); self.fallback=fallback or FallbackRegistry()
        self._owned_budgets={}
        self.store.initialize(regular_genesis(self.repo_root))
        self._observed={}; self._runtime_seconds=0.; self._active=None

    def _request(self,steps):
        if type(steps) is not int or not 1<=steps<=100: raise ValueError('strict supported integer request 1..100')

    def _validate_paths(self,out):
        from runtime_trace.regular_nstep.resources import ResourceRefused
        approved=self.repo_root/'runtime_trace/regular_nstep/artifacts/budget.json'
        if approved.resolve()!=approved or self.ledger!=approved or not self.ledger.is_file():
            raise ResourceRefused('existing approved ledger required; no reset/new budget')
        if not Path(out).resolve().is_relative_to(self.repo_root/'verified_driver/v0/artifacts'):
            raise ResourceRefused('accounted Driver evidence namespace required')

    def _size(self,root):
        return sum((Path(base)/name).lstat().st_size for base,_,files in os.walk(root) for name in files)

    def _reserved(self): return sum(b['remaining'] for b in self._owned_budgets.values())

    def _admit_segment(self,out):
        from runtime_trace.regular_nstep.resources import Limits,ResourceRefused
        self._validate_paths(out)
        if out.exists(): raise FileExistsError('exclusive pending transaction directory required')
        limits=Limits(); prior=file_json(self.ledger); used=prior.get('used_seconds')
        if type(used) not in (int,float) or not 0<=used<limits.total_seconds or limits.total_seconds-used<3:
            raise ResourceRefused('cumulative execution allowance exhausted')
        marker=self.ledger.with_suffix('.running.json')
        if marker.exists() and file_json(marker).get('state')!='FINISHED':
            raise ResourceRefused('unreconciled prior job prohibits transaction admission')
        artifact_root=self.repo_root/'verified_driver/v0/artifacts'
        roots=[self.ledger.parent,artifact_root]
        if not self.store.root.is_relative_to(artifact_root): roots.append(self.store.root)
        total=sum(self._size(root) for root in roots)
        # Reserve every bounded Driver JSON/object/receipt/pointer write and RT jobs.
        metadata=8*1048576
        if total+self._reserved()+metadata+1073741824+2*67108864+3*1048576>limits.storage_bytes:
            raise ResourceRefused('combined Runtime Trace/Driver storage allowance exhausted')
        return {'remaining':metadata}

    def _reserve(self,out,count):
        budget=self._owned_budgets.get(Path(out).resolve())
        if budget is None or count<0 or count>budget['remaining']:
            raise ValueError('owned reserved Driver metadata allowance required')
        budget['remaining']-=count

    def _write_owned(self,out,relative,value,*,newline=False):
        path=Path(out)/relative
        if path.is_symlink() or not path.resolve().is_relative_to(Path(out).resolve()):
            raise ValueError('owned metadata namespace alias')
        _write(path,value,reserve=lambda count:self._reserve(out,count),newline=newline)

    def _collect(self,steps,tx,pred,out):
        if self._active is None or (tx,steps,pred.content_hash)!=self._active[:3]:
            raise ValueError('active transaction/input binding required')
        start=strict_json(self._active[3])
        if canonical_bytes(source_snapshot(self.repo_root))!=self._active[3]:
            raise ValueError('pretransaction source changed before candidate/fallback')
        out=_isolated(out,self.store.root)
        budget=self._admit_segment(out)
        out.mkdir(parents=True,exist_ok=False)
        self._owned_budgets[out]=budget
        self._write_owned(out,'transaction.json',{'schema':'DRIVER_V0_TRANSACTION_V1','transaction_id':tx,
            'predecessor_id':pred.content_hash,'predecessor_bits':list(pred.state_bits),
            'requested_steps':steps,'source_start':start})
        began=time.perf_counter()
        try: observed=self._run_segment(steps,out)
        finally: self._runtime_seconds+=time.perf_counter()-began
        # Freeze the actual trusted controller response before reading candidate files.
        observed=strict_json(canonical_bytes(observed))
        if observed.get('verdict')!='CHECKER_PASS': raise ValueError('runtime/checker did not pass: '+str(observed))
        binding={'schema':'DRIVER_V0_RUN_BINDING_V1','transaction_id':tx,
            'predecessor_id':pred.content_hash,'predecessor_bits':list(pred.state_bits),
            'evidence_dir':str(out),'requested_steps':steps,'source_start':start,
            'observed_report':observed,'fresh_report_sha256':file_sha(out/'fresh_checker_report.json'),
            'run_result_sha256':file_sha(out/'run_result.json')}
        self._write_owned(out,'driver_binding.json',binding)
        candidate=candidate_from_evidence(tx,pred.content_hash,out)
        expected=canonical_bytes(binding)
        if candidate.binding_bytes!=expected: raise ValueError('private controller observation differs')
        self._observed[candidate.content_hash]=expected
        return candidate

    def _publish_candidate(self,candidate,pred):
        if self._observed.get(candidate.content_hash)!=candidate.binding_bytes:
            raise ValueError('candidate lacks fresh private controller observation')
        binding=strict_json(candidate.binding_bytes)
        if self._active is None or (candidate.transaction_id,binding['requested_steps'],pred.content_hash)!=self._active[:3] or canonical_bytes(binding['source_start'])!=self._active[3]:
            raise ValueError('active publication transaction/input/source binding required')
        decision=evaluate_candidate(candidate,pred,self.repo_root)
        if decision.verdict!='ACCEPT' or decision.acceptance_bytes is None:
            raise ValueError('gate refused: '+decision.reason)
        receipt=strict_json(decision.acceptance_bytes)
        if receipt.get('candidate_id')!=candidate.content_hash or receipt.get('controller_binding_sha256')!=digest_bytes(candidate.binding_bytes):
            raise ValueError('gate acceptance candidate mismatch')
        state=CertifiedState(pred.generation+1,candidate.state_bits,receipt['source_pinset_sha256'],
            pred.content_hash,digest_bytes(decision.acceptance_bytes),candidate.transaction_id,receipt['acquisition_id'])
        self._reserve(candidate.evidence_dir,len(decision.acceptance_bytes)+len(canonical_bytes(state))+130)
        identity=self.store.publish(pred.content_hash,state,decision.acceptance_bytes)
        return identity,state

    def transact(self,steps,transaction_id=None):
        self._request(steps); tx=transaction_id or uuid.uuid4().hex; check_transaction(tx)
        began=time.perf_counter(); self._runtime_seconds=0.; self._observed={}; self._owned_budgets={}
        before,pred=self.store.recover(); candidate=None; reason=''
        self._active=(tx,steps,before,canonical_bytes(source_snapshot(self.repo_root)))
        if pred.transaction_id==tx:
            receipt=file_json(self.store.root/'receipts'/(pred.acceptance_id+'.json'))
            if receipt['requested_steps']!=steps:
                return DriverResult('STOP',tx,before,pred.generation,'completed transaction request mismatch')
            return DriverResult('ACCEPT',tx,before,pred.generation,'already fully committed')
        if pred.generation!=0:
            return DriverResult('STOP',tx,before,pred.generation,'V0 has no arbitrary-state Gala continuation')
        out=self.pending_root/tx
        try:
            candidate=self._collect(steps,tx,pred,out)
            identity,state=self._publish_candidate(candidate,pred)
        except Exception as exc:
            reason=str(exc)
            # A crash/exception after replace may already have published a valid generation.
            identity,state=self.store.recover()
            if state.transaction_id!=tx and out in self._owned_budgets:
                try:
                    fallback=self.fallback.resolve(reason,{'transaction_id':tx,'predecessor':pred,
                        'fallback_dir':out/'fallback',
                        'validate_segment':lambda path:self._collect(steps,tx,pred,path)})
                    if fallback is not None:
                        candidate=fallback; identity,state=self._publish_candidate(candidate,pred)
                except Exception as fallback_error: reason+='; fallback refused: '+str(fallback_error)
        identity,state=self.store.recover()
        accepted=state.transaction_id==tx and state.generation==pred.generation+1
        result=DriverResult('ACCEPT' if accepted else 'STOP',tx,identity,state.generation,
            'exact fresh candidate committed' if accepted else reason,
            candidate.content_hash if candidate else None,
            time.perf_counter()-began-self._runtime_seconds,self._runtime_seconds)
        if out in self._owned_budgets and not (out/'driver_result.json').exists():
            self._write_owned(out,'driver_result.json',asdict(result))
        return result

    def audit_only(self,steps,out):
        self._request(steps); _,pred=self.store.recover()
        if pred.generation!=0: raise ValueError('regular genesis required for audit-only run')
        tx='audit-'+uuid.uuid4().hex
        self._owned_budgets={}; self._observed={}
        self._active=(tx,steps,pred.content_hash,canonical_bytes(source_snapshot(self.repo_root)))
        return self._collect(steps,tx,pred,out)

    def _run_segment(self,steps,out):
        # Adapter consumes unchanged CLIs; no evaluator is imported into the gate.
        from runtime_trace.regular_nstep.resources import Limits,run_guarded
        self._validate_paths(out)
        if Path(out).resolve() not in self._owned_budgets:
            raise ValueError('reserved transaction admission required before runtime')
        limits=Limits(); sources=source_snapshot(self.repo_root)['runtime']
        # Byte serialization equals the existing public integration pinset.
        self._write_owned(out,'integration_source_pinset.json',sources,newline=True)
        commands=[
            [sys.executable,'-m','runtime_trace.regular_nstep.acquire','--steps',str(steps),'--out',str(out/'capture')],
            [sys.executable,'-m','runtime_trace.regular_nstep.producer','--capture',str(out/'capture'),'--out',str(out/'derived'),'--root',str(self.repo_root)],
            [sys.executable,'-m','runtime_trace.regular_nstep.checker','--capture',str(out/'capture'),'--derived',str(out/'derived'),'--root',str(self.repo_root),'--report',str(out/'fresh_checker_report.json')]]
        for stage,command in zip(STAGES,commands):
            # Existing guard scans its original root. Deduct current Driver files
            # and unspent metadata reservations so child writers/logs cannot grow
            # outside the same aggregate8GiB ceiling.
            artifact_root=self.repo_root/'verified_driver/v0/artifacts'
            outside=self._size(self.store.root) if not self.store.root.is_relative_to(artifact_root) else 0
            available=limits.storage_bytes-self._size(artifact_root)-outside-self._reserved()
            stage_limits=Limits(**{**asdict(limits),'storage_bytes':available})
            receipt=run_guarded(command,stage_limits,out/stage,self.ledger,cwd=self.repo_root,
                artifact_allowance=1073741824 if stage=='acquisition' else 67108864)
            if receipt['verdict']!='EXECUTED':
                self._write_owned(out,'run_refusal.json',{'verdict':'REFUSED','reason':stage+' '+receipt['verdict'],
                    'requested_steps':steps,'requested_complete':False})
                raise ValueError(stage+' '+receipt['verdict'])
        report=file_json(out/'fresh_checker_report.json')
        self._write_owned(out,'run_result.json',{**report,'schema':'regular-nstep-guarded-run-v1',
            'integration_source_pinset_sha256':file_sha(out/'integration_source_pinset.json'),
            'stage_receipts':[file_sha(out/stage/'execution.json') for stage in STAGES]})
        return report
