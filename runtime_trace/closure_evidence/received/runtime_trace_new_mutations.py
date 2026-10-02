from pathlib import Path
from copy import deepcopy
from collections import Counter
import json,hashlib,shutil,subprocess,sys
ROOT=Path('/tmp/runtime_trace_audit'); SRC=ROOT/'runtime_trace/artifacts/attempt-05'; DST=ROOT/'runtime_trace/artifacts/audit-mut'
CHECK='/mnt/data/runtime_trace_independent_audit.py'

def load():
 c=json.loads((SRC/'capture.json').read_text()); r=[json.loads(x) for x in (SRC/'trace.jsonl').read_text().splitlines()]; return c,r

def save(c,rows):
 if DST.exists():shutil.rmtree(DST)
 shutil.copytree(SRC,DST)
 chain='0'*64
 for i,row in enumerate(rows):
  row['seq']=i; row.pop('chain',None)
  chain=hashlib.sha256(bytes.fromhex(chain)+json.dumps(row,sort_keys=True,separators=(',',':')).encode()).hexdigest();row['chain']=chain
 stream=''.join(json.dumps(x,separators=(',',':'))+'\n' for x in rows).encode()
 c['trace_sha256']=hashlib.sha256(stream).hexdigest();c['final_chain']=chain;c['record_count']=len(rows);c['scalar_fp_count']=sum(x['opcode'] in {'addsd','subsd','mulsd'} for x in rows);c['opcode_histogram']=dict(Counter(x['opcode'] for x in rows))
 (DST/'trace.jsonl').write_bytes(stream);(DST/'capture.json').write_text(json.dumps(c))

def run(name,mut):
 c,r=load();mut(c,r);save(c,r)
 p=subprocess.run([sys.executable,CHECK,str(ROOT),'--attempt','audit-mut'],text=True,capture_output=True)
 data=json.loads(p.stdout)
 return {'mutation':name,'returncode':p.returncode,'verdict':data['verdict'],'errors':data['errors'],'checks':data['checks']}

def m_kind(c,r):
 x=next(x for x in r if x['opcode']=='mulsd' and x['phase']=='step');x['kind']='ROUTING'

def m_loadbias(c,r):
 x=next(x for x in r if x['opcode']=='mulsd' and x['phase']=='step');x['module_load_base']+=0x1000;x['elf_address']-=0x1000

def m_control(c,r):
 i=next(i for i,x in enumerate(r) if x['opcode']=='je' and x['phase']=='step')
 x=r[i];fake=x['post_pc']+1;x['post_pc']=fake;x['post']['gpr']['rip']=hex(fake)
 if i+1<len(r):r[i+1]['runtime_pc']=fake;r[i+1]['pre']['gpr']['rip']=hex(fake)

def m_upperlane(c,r):
 x=next(x for x in r if x['opcode']=='mulsd' and x['phase']=='step');v=int(x['post']['xmm'][x['operands'][1]['register']],16);v ^= 1<<80;x['post']['xmm'][x['operands'][1]['register']]=f'0x{v:032x}'
 # preserve linkage into next row so only scalar-lane rule / later byte-flow can catch it
 i=x['seq'];r[i+1]['pre']['xmm'][x['operands'][1]['register']]=f'0x{v:032x}'

out=[run('scalar-kind-cloak-with-rehash',m_kind),run('paired-load-bias-shift-with-rehash',m_loadbias),run('linkage-consistent-control-target-shift-with-rehash',m_control),run('scalar-upper-lane-mutation-with-rehash',m_upperlane)]
Path('/mnt/data/runtime_trace_new_mutation_results.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out,indent=2))
