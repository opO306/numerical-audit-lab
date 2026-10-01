"""Gate 2A — Published-model reproduction and multi-layer verification (Henon-Heiles).
Plan sealed in docs/GATE2A_PLAN.md before this file existed.

    python run_gate2a.py [--out DIR] [--n N]     (default N = 100000, about 10 minutes)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import struct
import sys
import time
from fractions import Fraction
from pathlib import Path

import mpmath

from benchmarks.gate2a.henon_heiles import OUT, STATE, Binary64Stepper, bits, exact_steps, structure
from lab.gate2a_audit import H, StepAudit, energy_rounding_part, verdict
from lab.gate2a_hostfloat import classify, step as host_step
from lab.independence import loaded_a_modules, static_violations

ROOT = Path(__file__).resolve().parent
R_CANDIDATES = [(0.25, 0.125), (0.125, 0.25), (0.25, 0.0)]
C_CANDIDATES = [(0.5, 0.25), (0.4375, 0.3125), (0.5625, 0.125)]
K4_WINDOW = 8
DEFECT_N = 1000


def fv(b: int) -> float:
    return struct.unpack(">d", struct.pack(">Q", b))[0]


def q(b: int) -> Fraction:
    return Fraction(fv(b))


def peak_rss_bytes():
    try:
        import resource
        r = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return r if platform.system() == "Darwin" else r * 1024
    except ImportError:
        try:
            import ctypes
            from ctypes import wintypes

            class PMC(ctypes.Structure):
                _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
                    (n, ctypes.c_size_t) for n in ("PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage",
                                                   "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage",
                                                   "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage")]
            c = PMC(); c.cb = ctypes.sizeof(PMC)
            ctypes.windll.psapi.GetProcessMemoryInfo(ctypes.windll.kernel32.GetCurrentProcess(), ctypes.byref(c), c.cb)
            return c.PeakWorkingSetSize
        except Exception:
            return None


class Runner:
    def __init__(self, defect=None):
        self.stepper = Binary64Stepper(defect)
        self.audit = StepAudit(structure(defect))
        self.defect = defect
        self.n1_ops = 0
        self.n1_bad = 0

    def go(self, start: dict, n: int, e0: dict, keep=(), lockstep=False):
        """Run n steps. Returns final (state, e), dict of kept {step: (state, e)}, and extra stats."""
        st, e = dict(start), dict(e0)
        kept = {0: (dict(st), dict(e))} if 0 in keep else {}
        hf = tuple(fv(st[s]) for s in STATE) if lockstep else None
        k5_mismatch, k5_first = 0, None
        k3_fail, k3_ratio = 0, 0.0
        horizon, growth = None, {}
        ops_per_step = len(self.audit.structure)
        for i in range(1, n + 1):
            regs = self.stepper.step(st)
            res = self.audit.run(regs, e)
            self.n1_ops += ops_per_step
            self.n1_bad += len(res["n1_bad"])
            e = res["e_out"]
            st = {s: regs[OUT[s]] for s in STATE}
            for name, ok, r, b in res["force"]:
                k3_fail += not ok
                if b > 0:
                    k3_ratio = max(k3_ratio, r / b)
            if lockstep:
                hf = host_step(*hf)
                if tuple(bits(v) for v in hf) != tuple(st[s] for s in STATE):
                    k5_mismatch += 1
                    k5_first = k5_first or i
                    hf = tuple(fv(st[s]) for s in STATE)                  # resync so later steps stay comparable
            if horizon is None and max(e.values()) >= max(abs(fv(st[s])) for s in STATE):
                horizon = i
            if i in keep:
                kept[i] = (dict(st), dict(e))
        return (st, e), kept, {"k5_mismatch_steps": k5_mismatch, "k5_first_mismatch": k5_first,
                               "k3_failed_checks": k3_fail, "k3_max_residual_over_bound": k3_ratio,
                               "state_horizon": horizon}


def reversal(runner: Runner, kept: dict, L: int, start: dict) -> dict:
    st, e = kept[L]
    rev = {"x": st["x"], "y": st["y"], "px": st["px"] ^ (1 << 63), "py": st["py"] ^ (1 << 63)}
    (fin, efin), _, _ = runner.go(rev, L, e)
    target = {"x": q(start["x"]), "y": q(start["y"]), "px": -q(start["px"]), "py": -q(start["py"])}
    R = [q(fin[s]) - target[s] for s in STATE]
    B = [efin[s] for s in STATE]
    scale = max(abs(t) for t in target.values())
    v, why = verdict(R, B, scale)
    return {"L": L, "verdict": v, "reason": why, "max_residual": float(max(abs(r) for r in R)), "max_bound": max(B)}


def mirror(runner: Runner, start: dict, n: int, base_kept: dict, checkpoints) -> dict:
    m0 = {"x": start["x"] ^ (1 << 63), "y": start["y"], "px": start["px"] ^ (1 << 63), "py": start["py"]}
    _, mk, _ = runner.go(m0, n, {s: 0.0 for s in STATE}, keep=checkpoints)
    worst, identical = ("PASS", ""), 0
    rows = []
    for c in sorted(checkpoints):
        (bs, be), (ms, me) = base_kept[c], mk[c]
        sign = {"x": -1, "y": 1, "px": -1, "py": 1}
        R = [q(ms[s]) - sign[s] * q(bs[s]) for s in STATE]
        B = [me[s] + be[s] for s in STATE]
        scale = max(abs(q(bs[s])) for s in STATE)
        v, why = verdict(R, B, scale) if c else ("PASS", "start")
        identical += all(r == 0 for r in R)
        rows.append({"step": c, "verdict": v, "max_residual": float(max(abs(r) for r in R))})
        if v != "PASS" and worst[0] == "PASS":
            worst = (v, f"step {c}: {why}")
    return {"verdict": worst[0], "reason": worst[1] or "all checkpoints within bound",
            "checkpoints_exactly_mirrored": f"{identical}/{len(rows)}", "rows": rows}


def window(n0: int, kept: dict) -> dict:
    st, _ = kept[n0]
    exact = exact_steps({s: q(st[s]) for s in STATE}, K4_WINDOW)
    r = Runner()
    cur, e, worst, viol = dict(st), {s: 0.0 for s in STATE}, 0.0, 0
    for k in range(K4_WINDOW):
        (cur, e), _, _ = r.go(cur, 1, e)
        for s in STATE:
            act = abs(q(cur[s]) - exact[k][s])
            if act > Fraction(e[s]):
                viol += 1
            if e[s] > 0:
                worst = max(worst, float(act) / e[s])
    return {"n0": n0, "steps": K4_WINDOW, "bound_violations": viol, "max_actual_over_bound": worst,
            "final_bound": max(e.values())}


def energy_rows(kept: dict, start: dict) -> list:
    h0 = H(*(q(start[s]) for s in STATE))
    rows = []
    for c in sorted(kept):
        st, e = kept[c]
        vals = {s: q(st[s]) for s in STATE}
        dH = H(vals["x"], vals["y"], vals["px"], vals["py"]) - h0
        rpart = energy_rounding_part(vals, e)
        rows.append({"step": c, "energy_change": float(dH), "rounding_part_bound": float(rpart),
                     "explained_by_rounding": abs(dH) <= rpart, "H": float(h0 + dH)})
    return rows


def audit_orbit(name: str, p0: tuple, n: int) -> tuple:
    t0 = time.perf_counter()
    start = {"x": bits(0.0), "y": bits(0.0), "px": bits(p0[0]), "py": bits(p0[1])}
    checkpoints = {c for c in (0, 10, 100, 1000, 10000, 50000, 100000) if c <= n}
    Ls = [L for L in (100, 1000, 10000, 100000) if L <= n]
    n0s = sorted({0, n // 2, n - K4_WINDOW})
    r = Runner()
    tf = time.perf_counter()
    (_, _), kept, stats = r.go(start, n, {s: 0.0 for s in STATE}, keep=checkpoints | set(Ls) | set(n0s), lockstep=True)
    t_forward = time.perf_counter() - tf
    tr = time.perf_counter()
    k1 = [reversal(r, kept, L, start) for L in Ls]
    t_rev = time.perf_counter() - tr
    tm = time.perf_counter()
    k2 = mirror(r, start, n, kept, checkpoints)
    t_mir = time.perf_counter() - tm
    tw = time.perf_counter()
    k4 = [window(n0, kept) for n0 in n0s]
    t_win = time.perf_counter() - tw
    growth = [{"step": c, "max_bound": max(kept[c][1].values()),
               "max_abs_state": max(abs(fv(kept[c][0][s])) for s in STATE)} for c in sorted(checkpoints)]
    m1 = energy_rows({c: kept[c] for c in checkpoints}, start)
    det = {"initial_momentum": list(p0), "energy": float(H(0, 0, Fraction(p0[0]), Fraction(p0[1]))),
           "N1": {"ops_audited": r.n1_ops, "incorrectly_rounded": r.n1_bad},
           "bound_growth": growth, "state_horizon": stats["state_horizon"],
           "K1_time_reversal": k1, "K2_mirror": k2,
           "K3_force_law": {"checks": n * 4, "failed": stats["k3_failed_checks"],
                            "max_residual_over_bound": stats["k3_max_residual_over_bound"]},
           "K4_exact_windows_SAMPLED": k4,
           "K5_host_float_bit_identity": {"mismatch_steps": stats["k5_mismatch_steps"],
                                          "first_mismatch": stats["k5_first_mismatch"]},
           "M1_energy": {"verdict": "REFUSED",
                         "reason": "class II: no rigorous method-error (layer B) bound; values are information only",
                         "rows": m1},
           "POSTHOC_ESTIMATE_actual_error_120_digits": posthoc_actual_error_estimate(p0, n),
           "M2_bounded": {"max_abs_state": max(g["max_abs_state"] for g in growth),
                          "energy_stays_below_escape_1_6": all(row["H"] < 1 / 6 for row in m1)}}
    cost = {"forward_seconds": t_forward, "reversal_seconds": t_rev, "mirror_seconds": t_mir,
            "windows_seconds": t_win, "total_seconds": time.perf_counter() - t0, "steps_executed":
            n + sum(Ls) + n + len(n0s) * K4_WINDOW * 2}
    return det, cost


def posthoc_actual_error_estimate(p0: tuple, n: int, digits: int = 120) -> list:
    """POST-HOC, NOT IN THE SEALED PLAN, and NOT a bound: the same discrete program at 120 digits
    (mpmath) as a stand-in for exact arithmetic, to show how far the actual binary64 error sits
    below the rule-V1 bound. Labelled ESTIMATE (rule V1 section 8)."""
    marks = sorted({c for c in (10, 100, 1000, 10000, 50000, 100000) if c <= n})
    rows = []
    with mpmath.workdps(digits):
        h, hh = mpmath.mpf(1) / 64, mpmath.mpf(1) / 128
        m = [mpmath.mpf(0), mpmath.mpf(0), mpmath.mpf(p0[0]), mpmath.mpf(p0[1])]
        f = (0.0, 0.0, p0[0], p0[1])
        for i in range(1, n + 1):
            x, y, px, py = m
            ax, ay = -x - 2 * x * y, -y - x * x + y * y
            pxh, pyh = px + hh * ax, py + hh * ay
            x1, y1 = x + h * pxh, y + h * pyh
            m = [x1, y1, pxh + hh * (-x1 - 2 * x1 * y1), pyh + hh * (-y1 - x1 * x1 + y1 * y1)]
            f = host_step(*f)
            if i in marks:
                rows.append({"step": i, "estimated_actual_error": float(max(abs(mpmath.mpf(a) - b) for a, b in zip(f, m)))})
    return rows


def defects() -> dict:
    out = {}
    for d in ("D1", "D2", "D3"):
        start = {"x": bits(0.0), "y": bits(0.0), "px": bits(0.25), "py": bits(0.125)}
        r = Runner(d)
        _, kept, stats = r.go(start, DEFECT_N, {s: 0.0 for s in STATE}, keep={0, 10, 100, DEFECT_N}, lockstep=True)
        k1 = reversal(r, kept, DEFECT_N, start)
        k1_short = reversal(r, kept, 100, start)       # POSTHOC: not in the sealed plan (L = 100, inside the horizon)
        k2 = mirror(r, start, DEFECT_N, kept, {0, 10, 100, DEFECT_N})
        out[d] = {"N1_incorrectly_rounded": r.n1_bad, "K1": k1["verdict"], "K2": k2["verdict"],
                  "POSTHOC_K1_L100": k1_short["verdict"],
                  "K3_failed": stats["k3_failed_checks"], "K5_mismatch_steps": stats["k5_mismatch_steps"],
                  "detected_by": [c for c, hit in (("N1", r.n1_bad > 0), ("K1", k1["verdict"] == "FAIL"),
                                                   ("K2", k2["verdict"] == "FAIL"), ("K3", stats["k3_failed_checks"] > 0),
                                                   ("K5", stats["k5_mismatch_steps"] > 0)) if hit]}
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="reports/latest")
    ap.add_argument("--n", type=int, default=100000)
    args = ap.parse_args(argv)
    t0 = time.perf_counter()
    tc = time.perf_counter()
    cls = {"R": [dict(zip(("px", "py"), p), **classify(*p, args.n)) for p in R_CANDIDATES],
           "C": [dict(zip(("px", "py"), p), **classify(*p, args.n)) for p in C_CANDIDATES]}
    t_cls = time.perf_counter() - tc
    pick = {"regular": next(((c["px"], c["py"]) for c in cls["R"] if c["label"] == "regular"), None),
            "chaotic": next(((c["px"], c["py"]) for c in cls["C"] if c["label"] == "chaotic"), None)}
    print("classification:", json.dumps(cls), "\npicked:", pick, flush=True)
    det = {"plan": "docs/GATE2A_PLAN.md", "N": args.n, "h": "1/64", "classification": cls, "selected": pick,
           "orbits": {}}
    costs = {"classification_seconds": t_cls, "orbits": {}}
    for name, p0 in pick.items():
        if p0 is None:
            det["orbits"][name] = "no candidate met the pre-registered criterion"
            continue
        d, c = audit_orbit(name, p0, args.n)
        det["orbits"][name], costs["orbits"][name] = d, c
        print(name, "done", f"{c['total_seconds']:.0f}s", "horizon", d["state_horizon"],
              "K1", [k["verdict"] for k in d["K1_time_reversal"]], flush=True)
    td = time.perf_counter()
    det["planted_defects"] = defects()
    costs["defects_seconds"] = time.perf_counter() - td
    det["independence"] = {"static_violations": static_violations(), "A_modules_loaded": loaded_a_modules()}
    digest = hashlib.sha256(json.dumps(det, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    rep = {"deterministic_digest": digest, "deterministic": det, "costs": costs, "peak_rss_bytes": peak_rss_bytes(),
           "machine": {"system": platform.system(), "machine": platform.machine(),
                       "python": platform.python_version(), "mpmath": mpmath.__version__},
           "total_wall_seconds": time.perf_counter() - t0}
    out = ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)
    (out / "gate2a_report.json").write_text(json.dumps(rep, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"deterministic_digest {digest}\ntotal {rep['total_wall_seconds']:.0f} s, peak RSS {rep['peak_rss_bytes']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
