"""Retain native TEST_ONLY evidence and measure storage; no numerical campaign."""
from pathlib import Path
import hashlib
import json
import os
import stat
import time
import zipfile
import sys
ROOT=Path(__file__).resolve().parents[4]
NATIVE=Path('/home/otherside123/verified-driver-v0-test-mirror-2026-10-05')
OUT=ROOT/'verified_driver/v0/artifacts'/('native-validation'+('-'+sys.argv[1] if len(sys.argv)>1 else ''))
OUT.mkdir(exist_ok=False)
began=time.perf_counter(); inventory={}
source=NATIVE/'verified_driver/v0/artifacts'
with zipfile.ZipFile(OUT/'test-evidence.zip','x',compression=zipfile.ZIP_DEFLATED,compresslevel=1) as archive:
    for base,dirs,files in os.walk(source):
        dirs[:]=[d for d in dirs if d!='__pycache__']
        for name in sorted(files):
            path=Path(base)/name; relative=str(path.relative_to(source))
            if path.is_symlink():
                raw=os.readlink(path).encode(); item=zipfile.ZipInfo(relative)
                item.create_system=3; item.external_attr=(stat.S_IFLNK|0o777)<<16
                archive.writestr(item,raw)
                inventory[relative]={'link_target':raw.decode(),'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}
            else:
                with path.open('rb') as stream: digest=hashlib.file_digest(stream,'sha256').hexdigest()
                inventory[relative]={'sha256':digest,'bytes':path.stat().st_size}
                archive.write(path,relative)
with zipfile.ZipFile(OUT/'test-evidence.zip') as archive:
    assert archive.testzip() is None
    for name,item in inventory.items():
        with archive.open(name) as stream: assert hashlib.file_digest(stream,'sha256').hexdigest()==item['sha256']
def size(root):
    count=0; total=0
    for base,_,files in os.walk(root):
        for name in files:
            p=Path(base)/name
            if not p.is_symlink(): total+=p.stat().st_size; count+=1
    return {'files':count,'logical_bytes':total}
payload={'schema':'DRIVER_V0_NATIVE_TEST_EXPORT_V1','role':'TEST_ONLY saved-evidence/storage/authority-fault tests; fresh original numerics separately authority-02 (pre-fix) and authority-03 (final)',
    'source':str(source),'files':inventory,'zip_bytes':(OUT/'test-evidence.zip').stat().st_size,
    'export_and_verify_seconds':time.perf_counter()-began,'all_zip_members_sha256_match':True,
    'storage':{'old_runtime_artifacts':size(ROOT/'runtime_trace/regular_nstep/artifacts'),
        'managed_driver_artifacts':size(ROOT/'verified_driver/v0/artifacts'),
        'native_mirror_all':size(NATIVE),'native_test_artifacts':size(source)}}
with (OUT/'manifest.json').open('x') as stream: json.dump(payload,stream,sort_keys=True,indent=2); stream.write('\n')
print(json.dumps({k:v for k,v in payload.items() if k!='files'}))
