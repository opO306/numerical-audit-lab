"""Copy native actual evidence exclusively, preserving hashes and failures."""
from pathlib import Path
import hashlib,json,shutil,sys
ROOT=Path(__file__).resolve().parents[5];HERE=Path(__file__).resolve().parent.parent
SOURCE=Path('/home/otherside123/verified-driver-v1-test-mirror-2026-10-06/verified_driver/v1/artifacts/task8')
name=sys.argv[1];source=SOURCE/name;dest=HERE/name;assert source.is_dir() and not dest.exists()
shutil.copytree(source,dest);files={}
for p in source.rglob('*'):
    if p.is_file():
        q=dest/p.relative_to(source);assert p.read_bytes()==q.read_bytes();files[p.relative_to(source).as_posix()]=hashlib.sha256(q.read_bytes()).hexdigest()
with (HERE/(name+'-export.json')).open('x') as f:json.dump({'source':str(source),'destination':str(dest),'exact_byte_copy':True,'files':files},f,sort_keys=True,indent=2)
print({'run':name,'files':len(files),'summary':json.loads((dest/'SUMMARY.json').read_bytes()) if (dest/'SUMMARY.json').exists() else None})
