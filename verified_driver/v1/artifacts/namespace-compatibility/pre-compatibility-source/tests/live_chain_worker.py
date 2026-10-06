"""TEST_ONLY actual pipe/process transport; markers replace expensive Gala."""
import hashlib, json, os
from pathlib import Path
from runtime_trace.live_chain.protocol import BarrierEvent, read_frame, write_frame
from runtime_trace.live_chain.checkpoint import chain_hash
from verified_driver.v1.model import canonical_bytes, content_id
root=Path(os.environ['RT_OUTPUT']); n=int(os.environ['RTN_STEPS'])
readfd=int(os.environ['V1_COMMAND_FD']); writefd=int(os.environ['V1_EVENT_FD'])
session=os.environ['V1_SESSION']; pred=os.environ['V1_PREDECESSOR']
for k in range(1,n+1):
    (root/f'body{k}').write_text('TEST_ONLY')
    master=root/'trace.jsonl'
    with master.open('ab') as f: f.write(canonical_bytes({'seq':k-1})+b'\n')
    raw=master.read_bytes()
    event=BarrierEvent(session,k,k,'FINAL_TERMINAL' if k==n else 'NEXT_STEP_ENTRY',n,{'pid':os.getpid()},
      len(raw),hashlib.sha256(raw).hexdigest(),chain_hash(raw),pred,{'TEST_ONLY':True,'paused_pc':k})
    metadata={'source_snapshot':{'runtime_trace/harness.py':'d'*64},'source_binding':'e'*64,'capture':{'TEST_ONLY':True}}
    write_frame(writefd,{'type':'BARRIER','event':__import__('dataclasses').asdict(event),'metadata':metadata})
    while True:
        command=read_frame(readfd,10)
        if command['type']=='PING':
            write_frame(writefd,{'type':'PAUSED','event_id':content_id(event)})
        elif command['type']=='BIND':
            write_frame(writefd,{'type':'BOUND','checkpoint_id':command['checkpoint_id']})
        elif command['type']=='RESUME':
            pred=command['token']['state_id']; break
        elif command['type']=='FINISH':
            write_frame(writefd,{'type':'FINISHED','normal_exit':True}); raise SystemExit(0)
        else: raise ValueError('unexpected authority command')
