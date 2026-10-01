"""Gate 2B — audit of a public third-party Henon-Heiles implementation (gala 1.12.0).
Plan sealed in docs/GATE2B_PLAN.md (incl. amendment A) before gala was run.

Input is only the frozen fixture benchmarks/gate2b/fixtures/cloud-2026-10-01 (gala is NOT needed here).
The deterministic digest is the analysis-reproducibility check (amendment A1).

    python run_gate2b.py [--out DIR]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import struct
import sys
import time
from pathlib import Path

from benchmarks.gate2b.gala_replay import Replay
from lab.gate2b_checks import (b1_energy, b2_reversal, b3_mirror, b4_force_law, first_mismatch,
                               gradient_bit_agreement, host_leapfrog)
from lab.gate2b_fixture import FIXTURE, load, manifest
from lab.independence import loaded_a_modules, static_violations

ROOT = Path(__file__).resolve().parent
ORBITS = {"regular": (0.25, 0.125), "chaotic": (0.5, 0.25)}
LS = (100, 1000, 10000, 100000)
TAMPER_STEP = 50_000


def w1_replay(rows: list, n: int) -> dict:
    """Replay T step by step from the fixture's initial state; stop at the first output that differs."""
    T = Replay()
    x, y, vx, vy = (rows[c][0] for c in range(4))
    vh = T.init(x, y, vx, vy)
    s = {"x": x, "y": y, "vhx": vh["vhx"], "vhy": vh["vhy"]}
    for j in range(1, n + 1):
        o = T.step(s["x"], s["y"], s["vhx"], s["vhy"])
        got = (o["x1"], o["y1"], o["vox"], o["voy"])
        for c in range(4):
            if got[c] != rows[c][j]:
                return {"result": "NOT_IDENTICAL", "steps_identical": j - 1,
                        "first_mismatch": {"step": j, "component": "x y vx vy".split()[c],
                                           "bit_pattern_diff": got[c] - rows[c][j]}}
        s = {"x": o["x1"], "y": o["y1"], "vhx": o["vhx1"], "vhy": o["vhy1"]}
    return {"result": "BIT_IDENTICAL", "steps_identical": n, "first_mismatch": None}


def fv(b: int) -> float:
    return struct.unpack("<d", struct.pack("<Q", b))[0]


def diagnostic_machine_order(fwd, mir, ends, v0) -> dict:
    """Labelled diagnostic for the W1 cause: host-float leapfrog with the wheel's machine-code order."""
    n = len(fwd[0]) - 1
    out = {"forward_first_mismatch": first_mismatch(host_leapfrog(0.0, 0.0, *v0, n), fwd),
           "mirror_first_mismatch": first_mismatch(host_leapfrog(-0.0, 0.0, -v0[0], v0[1], n), mir),
           "reversal_ends_equal": []}
    for L, row in zip(LS, ends):
        r = host_leapfrog(fv(fwd[0][L]), fv(fwd[1][L]), -fv(fwd[2][L]), -fv(fwd[3][L]), L)
        out["reversal_ends_equal"].append({"L": L, "equal": [r[c][-1] for c in range(4)] == row})
    return out


def tamper(fwd, mir, v0, kind: str) -> dict:
    t = [list(r) for r in fwd]                       # in-memory copy; the frozen fixture is never touched
    if kind == "T1":
        t[0][TAMPER_STEP] += 1                       # x at step 50,000 moved by one bit pattern (1 ulp)
    else:
        for r in t:
            r[TAMPER_STEP], r[TAMPER_STEP + 1] = r[TAMPER_STEP + 1], r[TAMPER_STEP]
    w1 = w1_replay(t, len(t[0]) - 1)
    b3 = b3_mirror(t, mir)
    diag = first_mismatch(host_leapfrog(0.0, 0.0, *v0, len(t[0]) - 1), t)
    return {"predicted_detectors": ["W1", "W4"],
            "W1": w1, "W1_detected_tamper": w1["first_mismatch"] is not None and w1["first_mismatch"]["step"] == TAMPER_STEP,
            "W4": "REFUSED (W1 NOT_IDENTICAL on the untampered fixture)",
            "B3": b3, "B3_detected_tamper": b3["first_mismatch"] == TAMPER_STEP,
            "diagnostic_machine_order_first_mismatch": diag}


def audit_orbit(name: str, v0: tuple) -> tuple:
    c, t0 = {}, time.perf_counter()
    fwd, mir = load(f"{name}_forward"), load(f"{name}_mirror")
    grad, ends = load(f"{name}_gradient"), load(f"{name}_reversal_ends")
    n = len(fwd[0]) - 1
    d = {"N": n}
    t = time.perf_counter(); d["W1_forward"] = w1_replay(fwd, n); d["W1_mirror"] = w1_replay(mir, n)
    c["W1_seconds"] = time.perf_counter() - t
    identical = d["W1_forward"]["result"] == "BIT_IDENTICAL"
    if identical:
        raise SystemExit("W1 BIT_IDENTICAL: the W2-W4 path of the plan must be implemented before reporting")
    refused = "REFUSED: W1 NOT_IDENTICAL (plan section 3)"
    d["W2"], d["W3"], d["W4"] = refused, refused, refused
    d["G2B_3_exact_windows"] = "not applicable: W2 was not applied"
    t = time.perf_counter(); d["B1_energy"] = b1_energy(fwd); c["B1_seconds"] = time.perf_counter() - t
    d["B2_reversal"] = b2_reversal(fwd, ends, LS)
    t = time.perf_counter(); d["B3_mirror"] = b3_mirror(fwd, mir); c["B3_seconds"] = time.perf_counter() - t
    t = time.perf_counter(); d["B4_force_law"] = b4_force_law(fwd, grad); c["B4_seconds"] = time.perf_counter() - t
    t = time.perf_counter()
    d["diagnostic_W1_cause"] = {"label": "DIAGNOSTIC ONLY - not a verdict, not a replacement for T",
                                "gradient_bit_agreement": gradient_bit_agreement(fwd, grad),
                                "machine_order_replay": diagnostic_machine_order(fwd, mir, ends, v0)}
    c["diagnostic_seconds"] = time.perf_counter() - t
    t = time.perf_counter()
    d["tamper"] = {k: tamper(fwd, mir, v0, k) for k in ("T1", "T2")}
    c["tamper_seconds"] = time.perf_counter() - t
    c["total_seconds"] = time.perf_counter() - t0
    return d, c


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="reports/latest")
    args = ap.parse_args(argv)
    t0 = time.perf_counter()
    m = manifest()
    det = {"plan": "docs/GATE2B_PLAN.md (incl. amendment A)", "fixture": FIXTURE.name,
           "fixture_manifest_sha256": hashlib.sha256((FIXTURE / "manifest.json").read_bytes().replace(b"\r\n", b"\n")).hexdigest(),
           "gala_version": m["gala_version"], "dt_hex": m["dt_hex"], "orbits": {}}
    costs = {}
    for name, v0 in ORBITS.items():
        d, c = audit_orbit(name, v0)
        det["orbits"][name], costs[name] = d, c
        print(name, f"{c['total_seconds']:.0f}s", "W1", d["W1_forward"]["result"], d["W1_forward"]["first_mismatch"],
              "B3", d["B3_mirror"]["verdict"], "B4", d["B4_force_law"]["verdict"],
              "B2", [r["verdict"] for r in d["B2_reversal"]], flush=True)
    det["independence"] = {"static_violations": static_violations(), "A_modules_loaded": loaded_a_modules()}
    digest = hashlib.sha256(json.dumps(det, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    rep = {"deterministic_digest": digest, "deterministic": det, "costs": costs,
           "machine": {"system": platform.system(), "machine": platform.machine(), "python": platform.python_version()},
           "total_wall_seconds": time.perf_counter() - t0}
    out = ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)
    (out / "gate2b_report.json").write_text(json.dumps(rep, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"deterministic_digest {digest}\ntotal {rep['total_wall_seconds']:.0f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
