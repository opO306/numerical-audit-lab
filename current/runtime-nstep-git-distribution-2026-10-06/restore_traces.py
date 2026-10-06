"""Verify/restore two historical trace files without overwriting existing files."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import tempfile

PACKAGE = Path(__file__).resolve().parent
PATHS = (
    'runtime_trace/regular_nstep/artifacts/connected100-01/capture/trace.jsonl',
    'runtime_trace/regular_nstep/artifacts/connected100-final/capture/trace.jsonl',
)


def sha256(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def verify_archive(package: Path, entry: dict, output=None) -> dict:
    archive = package / entry['gzip_file']
    if archive.resolve().parent != package.resolve():
        raise ValueError('Archive must be a direct child of the package')
    if archive.stat().st_size != entry['gzip_bytes'] or sha256(archive) != entry['gzip_sha256']:
        raise ValueError('Compressed archive bytes/hash mismatch')
    digest = hashlib.sha256()
    count = 0
    with gzip.open(archive, 'rb') as source:
        while chunk := source.read(1024 * 1024):
            count += len(chunk)
            if count > entry['original_bytes']:
                raise ValueError('Restored bytes exceed pinned size')
            digest.update(chunk)
            if output is not None:
                output.write(chunk)
    if count != entry['original_bytes'] or digest.hexdigest() != entry['original_sha256']:
        raise ValueError('Restored bytes/hash mismatch')
    return {'bytes': count, 'sha256': digest.hexdigest()}


def restore_one(package: Path, root: Path, entry: dict, restore: bool) -> str:
    if entry['original_path'] not in PATHS:
        raise ValueError('Unexpected original path')
    target = root / entry['original_path']
    if not target.resolve().is_relative_to(root.resolve()):
        raise ValueError('Target escapes repository root')
    if target.is_symlink():
        raise ValueError('Existing target is a symlink')
    if target.exists():
        verify_archive(package, entry)
        if target.stat().st_size != entry['original_bytes'] or sha256(target) != entry['original_sha256']:
            raise ValueError('Existing original differs; refusing to overwrite')
        return 'EXISTING_BYTES_VERIFIED'
    if not restore:
        verify_archive(package, entry)
        return 'ARCHIVE_VERIFIED_ORIGINAL_ABSENT'
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=target.parent, prefix='.restore-', suffix='.part') as temp:
        verify_archive(package, entry, temp)
        temp.flush()
        os.fsync(temp.fileno())
        # Exclusive publication: os.link refuses an existing destination on both OSes.
        os.link(temp.name, target)
    return 'RESTORED_EXACT_BYTES'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--restore', action='store_true', help='Restore missing raw traces')
    parser.add_argument('--repo-root', type=Path, default=PACKAGE.parents[1])
    args = parser.parse_args()
    manifest = json.loads((PACKAGE / 'manifest.json').read_bytes())
    entries = manifest['files']
    if manifest['schema'] != 'RUNTIME_TRACE_GIT_GZIP_DISTRIBUTION_V1':
        raise ValueError('Unexpected manifest schema')
    if len(entries) != 2 or {entry['original_path'] for entry in entries} != set(PATHS):
        raise ValueError('Unexpected trace inventory')
    results = {entry['original_path']: restore_one(PACKAGE, args.repo_root, entry, args.restore)
               for entry in entries}
    print(json.dumps(results, sort_keys=True))


if __name__ == '__main__':
    main()
