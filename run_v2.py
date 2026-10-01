"""V2 error-bound prototype (docs/V2_ERROR_BOUND_PLAN.md, sealed before this file existed).

    python run_v2.py [--out DIR] [--n N]      (default N = 100000)

Reuses Gate 2A's SUT and V1 audit read-only; Gate 2A files are hash-sealed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
import time
from fractions import Fraction
from pathlib import Path

import mpmath

from benchmarks.gate2a.henon_heiles import OUT, STATE, Binary64Stepper, bits, exact_steps, structure
from lab.gate2a_audit import StepAudit, verdict
from lab.independence import loaded_a_modules, static_violations
from lab.v2_bound import Form, rebase, step_forms, zero_forms
from run_gate2a import fv, peak_rss_bytes, q

ROOT = Path(__file__).resolve().parent
MAIN = {"regular": (0.25, 0.125), "chaotic": (0.5, 0.25)}
HOLDOUT = {"holdout_regular_1": (0.125, 0.25), "holdout_regular_2": (0.25, 0.0),
           "holdout_chaotic_1": (0.4375, 0.3125), "holdout_chaotic_2": (0.5625, 0.125)}
MARKS = (10, 100, 1000, 10000, 50000, 100000)
V1_HORIZON_REGULAR = 1779                      # Gate 2A, sealed
LS = (100, 1000, 10000, 100000)
WINDOW = 8


def _v1_bound_only(audit: StepAudit, regs: dict, e: dict) -> dict:
    """The V1 bound does not depend on N1 judging, which the V2 plan does not ask for. Swap the judge
    out of the (sealed, unmodified) Gate 2A module for the duration of this one call, then restore it."""
    import lab.gate2a_audit as g2a
    saved, g2a.judge = g2a.judge, (lambda exact, b: None)
    try:
        return audit.run(regs, e)["e_out"]
    finally:
        g2a.judge = saved


class V2Run:
    def __init__(self, defect=None, with_v1=False, with_estimate=False):
        self.stepper = Binary64Stepper(defect)
        self.struct = structure(defect)
        self.v1 = StepAudit(self.struct) if with_v1 else None

        self.est = with_estimate

    def go(self, start: dict, n: int, forms=None, keep=(), marks=()):
        st = dict(start)
        forms = forms or zero_forms()
        e1 = {s: 0.0 for s in STATE}
        E = [0.0] * 4
        h2 = h1 = None
        rows, kept, viol = [], {}, []
        if self.est:
            mp_ctx = mpmath.mp.clone() if hasattr(mpmath.mp, "clone") else None
            with mpmath.workdps(120):
                m = [mpmath.mpf(fv(st[s])) for s in STATE]
                hh_, hstep = mpmath.mpf(1) / 128, mpmath.mpf(1) / 64
        for i in range(1, n + 1):
            regs = self.stepper.step(st)
            out = step_forms(self.struct, regs, dict(zip(STATE, forms)))
            forms, E = rebase([out[OUT[s]] for s in STATE])
            if self.v1:
                e1 = _v1_bound_only(self.v1, regs, e1)
            st = {s: regs[OUT[s]] for s in STATE}
            if self.est:
                with mpmath.workdps(120):
                    x, y, px, py = m
                    pxh, pyh = px + hh_ * (-x - 2 * x * y), py + hh_ * (-y - x * x + y * y)
                    x1, y1 = x + hstep * pxh, y + hstep * pyh
                    m = [x1, y1, pxh + hh_ * (-x1 - 2 * x1 * y1), pyh + hh_ * (-y1 - x1 * x1 + y1 * y1)]
            smax = max(abs(fv(st[s])) for s in STATE)
            if h2 is None and max(E) >= smax:
                h2 = i
            if self.v1 and h1 is None and max(e1.values()) >= smax:
                h1 = i
            if i in keep:
                kept[i] = (dict(st), [Form(list(f.coef), f.box) for f in forms], list(E))
            if i in marks:
                row = {"step": i, "v2_bound_max": max(E), "max_abs_state": smax}
                if self.v1:
                    row["v1_bound_max"] = max(e1.values())
                if self.est:
                    with mpmath.workdps(120):
                        act = [float(abs(mpmath.mpf(fv(st[s])) - m[k])) for k, s in enumerate(STATE)]
                    row["estimated_actual_max"] = max(act)
                    bad = [s for k, s in enumerate(STATE) if act[k] > E[k]]
                    if bad:
                        viol.append({"step": i, "components": bad})
                rows.append(row)
        return st, forms, E, {"rows": rows, "v2_horizon": h2, "v1_horizon": h1, "s3_violations": viol}, kept


def start_of(p0):
    return {"x": bits(0.0), "y": bits(0.0), "px": bits(p0[0]), "py": bits(p0[1])}


def reversal_v2(defect, kept_entry, L, start) -> dict:
    st, forms, _ = kept_entry
    rev = {"x": st["x"], "y": st["y"], "px": st["px"] ^ (1 << 63), "py": st["py"] ^ (1 << 63)}
    sign = (1, 1, -1, -1)
    rf = [Form([sg * c for c in f.coef], f.box) for f, sg in zip(forms, sign)]
    fin, _, E, _, _ = V2Run(defect).go(rev, L, forms=rf)
    target = {"x": q(start["x"]), "y": q(start["y"]), "px": -q(start["px"]), "py": -q(start["py"])}
    R = [q(fin[s]) - target[s] for s in STATE]
    v, why = verdict(R, E, max(abs(t) for t in target.values()))
    return {"L": L, "verdict": v, "reason": why, "max_residual": float(max(abs(r) for r in R)), "max_bound": max(E)}


def window_v2(kept_entry) -> dict:
    st, _, _ = kept_entry
    exact = exact_steps({s: q(st[s]) for s in STATE}, WINDOW)
    cur, forms, viol, worst = dict(st), zero_forms(), 0, 0.0
    r = V2Run()
    for k in range(WINDOW):
        cur, forms, E, _, _ = r.go(cur, 1, forms=forms)
        for idx, s in enumerate(STATE):
            act = abs(q(cur[s]) - exact[k][s])
            viol += act > Fraction(E[idx])
            if E[idx] > 0:
                worst = max(worst, float(act) / E[idx])
    return {"violations": viol, "max_actual_over_bound": worst}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="reports/latest")
    ap.add_argument("--n", type=int, default=100000)
    a = ap.parse_args(argv)
    t0 = time.perf_counter()
    marks = tuple(m for m in MARKS if m <= a.n)
    Ls = tuple(L for L in LS if L <= a.n)
    n0s = sorted({0, a.n // 2, a.n - WINDOW})
    det = {"plan": "docs/V2_ERROR_BOUND_PLAN.md", "N": a.n, "orbits": {}}
    costs = {}
    for name, p0 in {**MAIN, **HOLDOUT}.items():
        tt = time.perf_counter()
        main_orbit = name in MAIN
        start = start_of(p0)
        keep = set(Ls) | set(n0s) if main_orbit else set()
        r = V2Run(with_v1=True, with_estimate=True)
        _, _, _, info, kept = r.go(start, a.n, keep=keep, marks=marks)
        if 0 in n0s and main_orbit:
            kept[0] = (dict(start), zero_forms(), [0.0] * 4)
        o = {"initial_momentum": list(p0), **info}
        if main_orbit:
            o["S2_exact_windows"] = {n0: window_v2(kept[n0]) for n0 in n0s}
            o["aux_K1_reversal_v2"] = [reversal_v2(None, kept[L], L, start) for L in Ls]
        det["orbits"][name] = o
        costs[name] = time.perf_counter() - tt
        print(name, f"{costs[name]:.0f}s", "V2 horizon", info["v2_horizon"], "V1 horizon", info["v1_horizon"],
              "S3 violations", len(info["s3_violations"]), flush=True)
    td = time.perf_counter()
    dstart = start_of((0.25, 0.125))
    _, _, _, _, dk = V2Run("D2").go(dstart, 1000, keep={1000})
    det["aux_D2_reversal_L1000_v2"] = reversal_v2("D2", dk[1000], 1000, dstart)
    costs["D2"] = time.perf_counter() - td
    # criteria (plan section 3); S1 is the unit-test suite, recorded by the test run
    reg, cha = det["orbits"]["regular"], det["orbits"]["chaotic"]
    s2 = all(w["violations"] == 0 for o in (reg, cha) for w in o["S2_exact_windows"].values())
    s3 = all(not o["s3_violations"] for o in det["orbits"].values())
    hr = reg["v2_horizon"] or (a.n + 1)
    hc = cha["v2_horizon"] or (a.n + 1)
    u1 = hr >= 10 * V1_HORIZON_REGULAR
    u2 = (reg["v2_horizon"] is None and cha["v2_horizon"] is not None) or hr >= 10 * hc
    total = time.perf_counter() - t0
    det["criteria"] = {"V2-S2": s2, "V2-S3": s3, "V2-U1": u1, "V2-U2": u2,
                       "V2-U1_detail": f"regular V2 horizon {reg['v2_horizon'] or 'none within N'} vs bar {10 * V1_HORIZON_REGULAR}",
                       "V2-U2_detail": f"regular {reg['v2_horizon'] or 'none'} vs chaotic {cha['v2_horizon'] or 'none'}"}
    det["independence"] = {"static_violations": static_violations(), "A_modules_loaded": loaded_a_modules()}
    digest = hashlib.sha256(json.dumps(det, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    rep = {"deterministic_digest": digest, "deterministic": det, "costs_seconds": costs, "total_wall_seconds": total,
           "V2-C_under_60_min": total <= 3600, "peak_rss_bytes": peak_rss_bytes(),
           "machine": {"system": platform.system(), "machine": platform.machine(), "python": platform.python_version()}}
    out = ROOT / a.out
    out.mkdir(parents=True, exist_ok=True)
    (out / "v2_report.json").write_text(json.dumps(rep, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(det["criteria"]), f"\nV2-C {total:.0f}s", f"\ndeterministic_digest {digest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
