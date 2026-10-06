"""Transfer only the five selected finite-run evidence files, no repository export."""
import argparse
import hashlib
import json
from pathlib import Path
import time
import zipfile

p = argparse.ArgumentParser()
p.add_argument('--run', type=Path, required=True)
p.add_argument('--out', type=Path, required=True)
a = p.parse_args()
items = [(a.run / 'capture' / name) for name in ('capture.json', 'trace.jsonl', 'harness_output.json')]
items += [(a.run / 'derived' / name) for name in ('blocks.json', 'completion.json')]
size = sum(f.stat().st_size for f in items)
if size > 536870912 or a.out.exists():
    raise ValueError('exclusive bounded evidence package')
a.out.parent.mkdir(parents=True, exist_ok=True)
began = time.perf_counter()
with zipfile.ZipFile(a.out, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=1) as package:
    for item in items:
        package.write(item, item.name)
record = {'files': {f.name: hashlib.file_digest(f.open('rb'), 'sha256').hexdigest() for f in items},
          'package_sha256': hashlib.file_digest(a.out.open('rb'), 'sha256').hexdigest(),
          'package_bytes': a.out.stat().st_size, 'input_bytes': size,
          'package_seconds': time.perf_counter() - began}
a.out.with_suffix('.manifest.json').write_text(json.dumps(record, sort_keys=True) + '\n')
print(json.dumps(record, sort_keys=True))
