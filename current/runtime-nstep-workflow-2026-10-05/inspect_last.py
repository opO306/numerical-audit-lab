import json
from pathlib import Path
p=Path('runtime_trace/regular_nstep/artifacts/native10-02/capture')
c=json.loads((p/'capture.json').read_bytes());r=[json.loads(x) for x in (p/'trace.jsonl').read_bytes().splitlines()]
print(json.dumps(r[c['caller_corridors'][0]['end_seq']-1],indent=2))
