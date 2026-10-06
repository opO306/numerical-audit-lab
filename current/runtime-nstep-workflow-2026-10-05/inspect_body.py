import json
from collections import Counter
from pathlib import Path
r=[json.loads(x) for x in Path('runtime_trace/regular_nstep/artifacts/native10-02/capture/trace.jsonl').read_bytes().splitlines()]
print(Counter(x['opcode'] for x in r if x.get('occurrence')=='step1'))
for x in r:
 if x.get('occurrence')=='step1' and x['possible_memory_writes']:
  print(json.dumps(x['possible_memory_writes'][0]));break
