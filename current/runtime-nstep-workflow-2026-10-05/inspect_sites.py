import json
from pathlib import Path
r=Path('.')
a=[json.loads(l) for l in (r/'runtime_trace/regular_2step/artifacts/known-03/trace.jsonl').read_bytes().splitlines()]
b=[json.loads(l) for l in (r/'runtime_trace/regular_nstep/artifacts/native10-02/capture/trace.jsonl').read_bytes().splitlines()]
k={(x['module_sha256'],x['elf_address'],x['instruction_bytes']) for x in a if x.get('schema')=='gala-caller-transition-instruction-v2'}
u={}
for x in b:
 if x.get('schema')=='gala-caller-transition-instruction-v2' and (x['module_sha256'],x['elf_address'],x['instruction_bytes']) not in k:
  u[(x['module_sha256'],x['elf_address'],x['instruction_bytes'])]=(x['assembly'],x['occurrence'],x['seq'])
print(json.dumps(list(u.items()),indent=2))
