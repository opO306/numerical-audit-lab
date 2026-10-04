import hashlib, json, subprocess
from pathlib import Path
ROOT=Path(r"D:\regular2step-independent-audit-retry-2026-10-04\repo")
V=ROOT/"runtime_trace"/"regular_2step"/"artifacts"/"validation"

def sha(p):
 h=hashlib.sha256()
 with p.open("rb") as f:
  for b in iter(lambda:f.read(1<<20),b""): h.update(b)
 return h.hexdigest()

m=json.loads((V/"source_test_map.json").read_text(encoding="utf-8"))
bad=[]
for section in ("production","tests","documentation"):
 for x in m[section]:
  p=ROOT/x["path"]
  actual={"bytes":p.stat().st_size,"physical_lines":len(p.read_bytes().splitlines()),"sha256":sha(p)}
  for key in ("bytes","physical_lines","sha256"):
   if actual[key]!=x[key]: bad.append((section,x["path"],key,actual[key],x[key]))
print("SOURCE_MAP_ENTRIES",sum(len(m[x]) for x in ("production","tests","documentation")))
print("SOURCE_MAP_BAD",bad)

def tree(commit):
 out=subprocess.check_output(["git","-C",str(ROOT),"ls-tree","-r",commit],text=True)
 d={}
 for line in out.splitlines():
  meta,path=line.split("\t",1)
  mode,typ,obj=meta.split()
  d[path]=(mode,typ,obj)
 return d
base=tree("43f1e9b21a014520facb5a545846d648eb67b288")
head=tree("e69119e259b862a7d8462c8d61333782ee2747fd")
common=set(base)&set(head)
changed=sorted(p for p in common if base[p]!=head[p])
deleted=sorted(set(base)-set(head))
added=sorted(set(head)-set(base))
print("BASE_FILES",len(base))
print("HEAD_FILES",len(head))
print("COMMON",len(common))
print("UNCHANGED_COMMON",sum(base[p]==head[p] for p in common))
print("CHANGED_COMMON",changed)
print("DELETED",deleted)
print("ADDED_COUNT",len(added))
print("ADDED_REGULAR2STEP",sum(p.startswith("runtime_trace/regular_2step/") for p in added))
