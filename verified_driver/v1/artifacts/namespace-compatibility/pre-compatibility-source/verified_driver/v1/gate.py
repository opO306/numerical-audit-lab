"""Exact live acceptance assembled only after separate independent verification."""
from dataclasses import replace
import os, signal, subprocess, sys, time
from pathlib import Path
from .model import ChainState, canonical_bytes, content_id, digest_bytes, strict_json
from runtime_trace.live_chain.checkpoint import verify_checkpoint, no_alias, sealed_write

class V1Gate:
    def __init__(self): self.metrics={}
    def _worker(self,mode,cp,pred_path,out,root,report):
        cmd=[sys.executable,'-m','runtime_trace.live_chain.worker',mode,'--checkpoint',str(cp),
          '--predecessor',str(pred_path),'--out',str(out),'--root',str(root),'--report',str(report)]
        started=time.perf_counter()
        process=subprocess.Popen(cmd,cwd=root,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,start_new_session=True)
        try: raw,_=process.communicate(timeout=60)
        except BaseException:
            try: os.killpg(process.pid,signal.SIGKILL)
            except ProcessLookupError: pass
            process.wait(); raise
        self.metrics[mode+'_seconds']=time.perf_counter()-started
        sealed_write(out.with_name(out.name+'.'+mode+'.log'),raw)
        if process.returncode!=0: raise ValueError(mode+' worker refused: '+raw.decode('utf-8',errors='replace')[-1000:])
    def observe(self,checkpoint_id,checkpoint_dir,predecessor,derived_dir,repo_root):
        cp=no_alias(checkpoint_dir); out=no_alias(derived_dir); root=no_alias(repo_root)
        doc=verify_checkpoint(cp,checkpoint_id)
        if doc['metadata'].get('evidence_role')!='LIVE': raise ValueError('TEST_ONLY or missing LIVE acquisition role cannot certify')
        if doc['event']['predecessor_id']!=predecessor.content_hash: raise ValueError('gate immediate predecessor required')
        out.parent.mkdir(parents=True,exist_ok=True)
        pred_path=out.with_name(out.name+'.predecessor.json'); report=out.with_name(out.name+'.checker.json')
        sealed_write(pred_path,canonical_bytes(predecessor))
        self._worker('produce',cp,pred_path,out,root,report)
        self._worker('check',cp,pred_path,out,root,report)
        checked=strict_json(report.read_bytes())
        if checked.get('verdict')!='CHECKER_PASS' or checked.get('evidence_role')!='LIVE' or checked.get('checkpoint_id')!=checkpoint_id:
            raise ValueError('independent live edge acceptance unavailable')
        edge=strict_json((out/'edge.json').read_bytes())
        if edge['candidate']!=checked['candidate']: raise ValueError('candidate changed after independent check')
        return checked
    def evaluate(self,checkpoint_id,checkpoint_dir,predecessor,derived_dir,repo_root):
        checked=self.observe(checkpoint_id,checkpoint_dir,predecessor,derived_dir,repo_root)
        receipt=canonical_bytes({'schema':'VERIFIED_CHAIN_ACCEPTANCE_V1','verdict':'ACCEPT',
          'candidate':checked['candidate'],'predecessor_id':predecessor.content_hash,'checkpoint_id':checkpoint_id,
          'edge_completion_sha256':checked['completion_sha256'],'checker_report_sha256':content_id(checked)})
        state=ChainState(**checked['candidate'],acceptance_id=digest_bytes(receipt))
        return state,receipt
