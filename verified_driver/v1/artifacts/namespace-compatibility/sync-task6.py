from pathlib import Path
import os,shutil,hashlib,json,sys
ROOT=Path(__file__).resolve().parents[4]
MIRROR=Path('/home/otherside123/verified-driver-v1-test-mirror-2026-10-06')
files={}
for base in ('verified_driver','runtime_trace','tests'):
    for folder,dirs,names in os.walk(ROOT/base):
        dirs[:]=[d for d in dirs if d not in ('artifacts','__pycache__')]
        for name in names:
            if not name.endswith('.py'): continue
            p=Path(folder)/name; target=MIRROR/p.relative_to(ROOT)
            target.parent.mkdir(parents=True,exist_ok=True); shutil.copyfile(p,target)
            assert p.read_bytes()==target.read_bytes()
            files[p.relative_to(ROOT).as_posix()]=hashlib.sha256(p.read_bytes()).hexdigest()
out=ROOT/'verified_driver/v1/artifacts'/('task6-source-'+sys.argv[1]+'.json')
with out.open('x') as f: json.dump({'combined_product_source_identical':True,'files':files},f,sort_keys=True,indent=2)
print(json.dumps({'files':len(files),'report':str(out)}))
