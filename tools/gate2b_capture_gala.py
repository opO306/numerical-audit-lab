"""Gate 2B: run the UNMODIFIED gala wheel and freeze its raw binary64 outputs (docs/GATE2B_PLAN.md).

Run with a Python that has gala 1.12.0 installed (Python >= 3.12):
    <venv312>/bin/python tools/gate2b_capture_gala.py --out benchmarks/gate2b/fixtures/<run-id>

Rules (G2B-0): this script only CALLS gala. It never assigns to gala objects, never
monkeypatches, never imports Lab code. tests/test_gate2b_adapter.py checks this statically.
Every array is stored as little-endian uint64 bit patterns, gzip-compressed, with SHA-256 in the manifest.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import platform
import struct
import sys
from importlib import metadata
from pathlib import Path

import numpy as np

import gala
import gala.dynamics as gd
import gala.integrate as gi
import gala.potential as gp
import gala.units as gu

DT = 1.0 / 64.0
N = 100_000
ORBITS = {"regular": (0.25, 0.125), "chaotic": (0.5, 0.25)}
LS = (100, 1000, 10000, 100000)


def run(H, x, y, vx, vy, n):
    w0 = gd.PhaseSpacePosition(pos=np.array([x, y]), vel=np.array([vx, vy]))
    orbit = H.integrate_orbit(w0, dt=DT, n_steps=n, Integrator=gi.LeapfrogIntegrator, cython_if_possible=True)
    pos = np.asarray(orbit.xyz.value, dtype=np.float64)       # shape (2, n+1)
    vel = np.asarray(orbit.v_xyz.value, dtype=np.float64)
    t = np.asarray(orbit.t.value, dtype=np.float64)
    return pos, vel, t


def bits(a: np.ndarray) -> bytes:
    return np.ascontiguousarray(a, dtype="<f8").view("<u8").tobytes()


def save(out: Path, name: str, arr: np.ndarray, manifest: dict) -> None:
    raw = bits(arr)
    gz = gzip.compress(raw, mtime=0)
    (out / f"{name}.u64.gz").write_bytes(gz)
    manifest["files"][name] = {"shape": list(arr.shape), "sha256_raw": hashlib.sha256(raw).hexdigest(),
                               "sha256_gz": hashlib.sha256(gz).hexdigest()}


def cpu_flags() -> list:
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("flags"):
                f = set(line.split(":", 1)[1].split())
                return sorted(f & {"fma", "avx", "avx2", "avx512f", "sse2"})
    except OSError:
        pass
    return []


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=False)                    # never overwrite a frozen fixture
    pot = gp.HenonHeilesPotential(units=gu.dimensionless)
    H = gp.Hamiltonian(pot)
    manifest = {
        "plan": "docs/GATE2B_PLAN.md (incl. amendment A)",
        "gala_version": gala.__version__, "numpy": np.__version__, "python": platform.python_version(),
        "platform": platform.platform(), "machine": platform.machine(), "cpu_flags": cpu_flags(),
        "distribution_files_sha256": {},
        "dt": DT, "dt_hex": DT.hex(), "n_steps": N, "integrator": "gala.integrate.LeapfrogIntegrator (cython)",
        "units": repr(pot.units), "orbits": {k: list(v) for k, v in ORBITS.items()}, "Ls": list(LS), "files": {},
    }
    try:
        dist = metadata.distribution("gala")
        rec = [f for f in (dist.files or []) if str(f).endswith((".so", ".pyd"))]
        manifest["distribution_files_sha256"] = {str(f): hashlib.sha256(Path(dist.locate_file(f)).read_bytes()).hexdigest()
                                                 for f in sorted(rec, key=str)}
    except Exception as e:                                     # record, do not hide
        manifest["distribution_files_sha256"] = f"unavailable: {e!r}"
    for name, (vx0, vy0) in ORBITS.items():
        pos, vel, t = run(H, 0.0, 0.0, vx0, vy0, N)
        manifest.setdefault("time_checks", {})[name] = {"t0_hex": float(t[0]).hex(), "t1_minus_t0_hex": float(t[1] - t[0]).hex(),
                                                         "t_last_hex": float(t[-1]).hex()}
        save(out, f"{name}_forward", np.vstack([pos, vel]), manifest)                   # rows x, y, vx, vy
        mpos, mvel, _ = run(H, -0.0, 0.0, -vx0, vy0, N)
        save(out, f"{name}_mirror", np.vstack([mpos, mvel]), manifest)
        grad = np.asarray(pot.gradient(pos).value, dtype=np.float64)                     # gala's own gradient at its positions
        save(out, f"{name}_gradient", grad, manifest)
        ends = []
        for L in LS:
            rpos, rvel, _ = run(H, pos[0, L], pos[1, L], -vel[0, L], -vel[1, L], L)
            ends.append([rpos[0, -1], rpos[1, -1], rvel[0, -1], rvel[1, -1]])
        save(out, f"{name}_reversal_ends", np.array(ends), manifest)                     # rows per L
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({k: manifest[k] for k in ("gala_version", "python", "cpu_flags", "dt_hex", "time_checks")}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
