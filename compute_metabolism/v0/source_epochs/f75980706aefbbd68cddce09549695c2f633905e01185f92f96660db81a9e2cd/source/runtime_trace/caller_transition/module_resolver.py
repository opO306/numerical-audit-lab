import hashlib
import json
from pathlib import Path


class ResolverRefused(ValueError):
    pass


def resolve_module(root, digest):
    root = Path(root).resolve()
    manifest_path = root / "runtime_trace/caller_transition/frozen_modules/manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    relative = manifest["modules"].get(digest)
    if relative is None:
        raise ResolverRefused(f"unregistered module SHA-256: {digest}")
    path = (manifest_path.parent / relative).resolve()
    if root not in path.parents:
        raise ResolverRefused("registered module escapes repository root")
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ResolverRefused(f"registered module unavailable: {path}") from exc
    if hashlib.sha256(raw).hexdigest() != digest:
        raise ResolverRefused("registered module raw hash mismatch")
    if not raw.startswith(b"\x7fELF"):
        raise ResolverRefused("registered module is not ELF")
    return path
