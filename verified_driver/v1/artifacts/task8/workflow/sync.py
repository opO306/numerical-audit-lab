"""Exact combined source copy to native filesystem; no evidence overwrites."""
from pathlib import Path
import hashlib,json,os,shutil,sys
ROOT=Path(__file__).resolve().parents[5];HERE=Path(__file__).resolve().parent.parent
MIRROR=Path('/home/otherside123/verified-driver-v1-test-mirror-2026-10-06');files={}
for base in ('runtime_trace','verified_driver','tests'):
    for folder,dirs,names in os.walk(ROOT/base):
        dirs[:]=[d for d in dirs if d not in ('artifacts','__pycache__')]
        for name in names:
            if name.endswith('.py'):
                p=Path(folder)/name;q=MIRROR/p.relative_to(ROOT);q.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,q)
                assert p.read_bytes()==q.read_bytes();files[p.relative_to(ROOT).as_posix()]=hashlib.sha256(p.read_bytes()).hexdigest()
with (HERE/('source-mirror-'+sys.argv[1]+'.json')).open('x') as f:json.dump({'files':files,'source_identical_combined':True},f,sort_keys=True,indent=2)
print({'files':len(files)})
