"""Load the frozen Gate 2B gala fixture with the standard library only (no numpy), verifying SHA-256."""
from __future__ import annotations

import gzip
import hashlib
import json
import struct
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "benchmarks" / "gate2b" / "fixtures" / "cloud-2026-10-01"


def manifest(fixture: Path = FIXTURE) -> dict:
    return json.loads((fixture / "manifest.json").read_text(encoding="utf-8"))


def load(name: str, fixture: Path = FIXTURE) -> list:
    """Rows of uint64 bit patterns, shape as recorded; refuses a file whose hash changed."""
    m = manifest(fixture)["files"][name]
    gz = (fixture / f"{name}.u64.gz").read_bytes()
    if hashlib.sha256(gz).hexdigest() != m["sha256_gz"]:
        raise RuntimeError(f"fixture {name} changed (gz hash)")
    raw = gzip.decompress(gz)
    if hashlib.sha256(raw).hexdigest() != m["sha256_raw"]:
        raise RuntimeError(f"fixture {name} changed (raw hash)")
    flat = struct.unpack(f"<{len(raw) // 8}Q", raw)
    rows, cols = m["shape"]
    return [list(flat[r * cols:(r + 1) * cols]) for r in range(rows)]


def fval(b: int) -> float:
    return struct.unpack("<d", struct.pack("<Q", b))[0]


def qval(b: int) -> Fraction:
    return Fraction(fval(b))
