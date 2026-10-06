"""TEST_ONLY split saved original execution; never a live authority receipt."""
from dataclasses import asdict
from collections import Counter
import copy, hashlib, json
from pathlib import Path
from runtime_trace.live_chain.protocol import BarrierEvent
from runtime_trace.live_chain.checkpoint import CheckpointSealer, chain_hash
from runtime_trace.live_chain.session import live_source_snapshot
from verified_driver.v1.model import ChainState, canonical_bytes, content_id, digest_bytes
from tests.verified_driver_v1_support import ROOT
CASE=ROOT/'verified_driver/v1/artifacts/fixtures/n3/capture'

def checkpoint(base,pred,k):
    capture=json.loads((CASE/'capture.json').read_bytes())
    lines=(CASE/'trace.jsonl').read_bytes().splitlines(keepends=True)
    n=capture['requested_steps']; region=capture['regions'][k]
    final=k==n
    end=capture['terminal_corridor']['end_seq'] if final else capture['caller_corridors'][k-1]['end_seq']
    raw=b''.join(lines[:end]); following=copy.deepcopy(capture['regions'][k+1]) if not final else None
    if following:
        for name in ('end_seq','end_state'): following.pop(name)
        following['context']=json.loads(lines[end])['pre']
    state=following['start_state'] if following else {**region['end_state'],'gradient':region['start_state']['gradient']}
    snap={'q':state['q'],'full_v':state['full_v'],'latent':state['latent'],'gradient':state['gradient'],
      't_bits':following['t_bits'] if following else None,'dt_bits':region['dt_bits'],
      'next_entry':following,'paused_pc':following['entry_pc'] if following else json.loads(lines[end-1])['next_pc'],
      'body_count':k,'frontier':end-1}
    sources=live_source_snapshot(ROOT)
    acquisition=capture['acquisition_id']
    capture.update(schema='gala-live-prefix-v1',verdict='PAUSED',regions=capture['regions'][:k+1],
      caller_corridors=capture['caller_corridors'][:k if not final else k-1],
      terminal_corridor=capture['terminal_corridor'] if final else None,record_count=end,
      scalar_fp_count=sum(json.loads(line).get('kind') in ('ADD','SUB','MUL') for line in lines[:end]),
      opcode_histogram=dict(Counter(row.get('opcode') or row['assembly'].split()[0] for row in map(json.loads,lines[:end]))),
      trace_sha256=digest_bytes(raw),final_chain=json.loads(lines[end-1])['chain'],
      source_pinset_sha256=content_id(sources),harness_completed_normally=False,gdb_exit_event=None)
    metadata={'source_snapshot':sources,'source_binding':content_id(sources),'capture':capture,
      'evidence_role':'TEST_ONLY','fixture_original_capture_sha256':digest_bytes((CASE/'capture.json').read_bytes()),
      'retained_gaps':['init-return -> step1-entry','terminal frontier -> wrapper tail']}
    event=BarrierEvent(acquisition,k,k,'FINAL_TERMINAL' if final else 'NEXT_STEP_ENTRY',n,
      capture['process_identity'],len(raw),digest_bytes(raw),chain_hash(raw),pred.content_hash,snap)
    base=Path(base); base.mkdir(parents=True,exist_ok=False); master=base/'master.jsonl'; master.write_bytes(raw)
    out=base/'sealed'; identity=CheckpointSealer(base).seal(master,event,metadata,out)
    return out,identity,event

def observed_state(report):
    document=copy.deepcopy(report['candidate']); document['acceptance_id']='f'*64
    return ChainState(**document)

def rehash_derived(out):
    edge=json.loads((out/'edge.json').read_bytes()); (out/'edge.json').write_bytes(canonical_bytes(edge))
    done=json.loads((out/'completion.json').read_bytes()); done['edge_sha256']=digest_bytes((out/'edge.json').read_bytes())
    done['checkpoint_id']=edge['checkpoint_id']
    done.pop('completion_sha256'); done['completion_sha256']=content_id(done)
    (out/'completion.json').write_bytes(canonical_bytes(done))

def rehash_checkpoint(out):
    p=out/'checkpoint.json'; data=canonical_bytes(json.loads(p.read_bytes())); p.chmod(0o600); p.write_bytes(data)
    pointer=out/'CHECKPOINT'; pointer.chmod(0o600); pointer.write_text(digest_bytes(data)+'\n')
