"""Windows metadata scan avoids slow WSL mount traversal; no numerical work."""
from pathlib import Path
import json, os, stat, sys
ROOT=Path(__file__).resolve().parents[4]
used=0; count=0
for folder in ('runtime_trace/regular_nstep/artifacts','verified_driver/v1/artifacts'):
    for base,dirs,files in os.walk(ROOT/folder):
        dirs[:]=[d for d in dirs if not ((Path(base)/d).lstat().st_file_attributes & 0x400)]
        for name in files:
            p=Path(base)/name; info=p.lstat()
            if info.st_file_attributes & 0x400: continue
            if stat.S_ISREG(info.st_mode): used+=info.st_size; count+=1
print(json.dumps({'actual_storage_bytes':used,'files':count,'host':'desktop Windows metadata',
 'scope':'existing batch artifacts plus new V1 evidence; reparse aliases not double-counted'}))
