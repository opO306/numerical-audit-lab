"""Gate 0 — Numeric Core Self-Test. Criteria: docs/GATE0_CRITERIA.md (sealed before this file existed).

    python run_gate0.py [--out DIR]   -> DIR/gate0_report.json, DIR/GATE0_REPORT.md (default reports/latest)

The report has a `deterministic_digest` over everything except costs and the
machine description. Two machines that run the same commit must print the
same digest; comparing the designer's home-PC digest with the cloud digest is
part of G0-6.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import time
from fractions import Fraction
from pathlib import Path

import mpmath

from benchmarks.gate0 import gendot, muller, rump
from benchmarks.gate0.harness import execute, make_profile
from independent_checker.oracle import to_bits
from lab.claim import Profile, audit_steps, decode, judge_claim, judge_step, settle_oracle
from lab.independence import loaded_a_modules, static_violations
from lab.verdict import Refused, Verdict

ROOT = Path(__file__).resolve().parent
B64, EXACT = Profile("binary64"), Profile("exact")
EXTRA_PROFILES = [Profile("fx", 64, 32), Profile("fx", 128, 96), Profile("fx", 256, 64), Profile("fx", 256, 192)]
TINY = Fraction(1, 10 ** 40)
# Each program is either a known trap (an ordinary binary64 run must be INVALID: G0-1) or
# correct by specification (the calculator's DOT is exact-then-round-once, so it must be VALID: G0-3).
TRAP, BY_SPEC = "trap", "correct_by_spec"
BENCHMARKS = {
    "rump": (rump, {"sequential": (rump.program("sequential"), TRAP), "sum": (rump.program("sum"), TRAP)}),
    "muller": (muller, {"recurrence": (muller.program(), TRAP)}),
    "gendot": (gendot, {"naive": (gendot.program("naive"), TRAP), "vm_dot": (gendot.program("vm_dot"), BY_SPEC)}),
}
POST_SEAL_CHANGES = ["docs/AUDIT_POST_SEAL_ORACLE_TOLERANCE.md: oracle cross-check tolerance rule replaced after a "
                     "REFUSED on Muller; Rump restored to the original rule; regression tests in "
                     "tests/test_post_seal_audit.py"]


def show(x: Fraction | None) -> str | None:
    if x is None:
        return None
    with mpmath.workdps(30):
        return mpmath.nstr(mpmath.mpf(x.numerator) / x.denominator, 17)


def run_one(prog, p: Profile, out: str, oracle: Fraction) -> tuple:
    e = execute(prog, p, out)
    verdict, reason = judge_claim(oracle, p, e.final)
    bad = audit_steps(p, e.steps)
    row = {"profile": p.label, "value": show(None if e.final is None else decode(p, e.final)),
           "halt": list(e.halt) if e.halt else None, "verdict": verdict.value, "reason": reason,
           "steps_audited": len(e.steps), "steps_rejected": len(bad)}
    cost = {"profile": p.label, "wall_seconds": e.wall_seconds, "peak_python_heap_bytes": e.peak_python_heap_bytes,
            "op_count": e.op_count}
    return e, row, cost


def injections(oracle: Fraction, exact_inputs: dict, mp_angle: tuple, b64_run, exact_run) -> list:
    rows = []

    def add(name, expected, got):
        rows.append({"name": name, "expected": expected, "got": got, "ok": expected == got})

    host = to_bits(float(oracle))                                  # Fraction -> float is correctly rounded
    core = make_profile(B64).from_exact(oracle)                    # the calculator's own rounding
    add("host and calculator round the oracle to the same binary64", True, host == core)
    add("claim: correctly rounded oracle", "VALID", judge_claim(oracle, B64, f"{host:016x}")[0].value)
    add("claim: oracle + 1 ulp", "INVALID", judge_claim(oracle, B64, f"{host + 1:016x}")[0].value)
    add("claim: oracle - 1 ulp", "INVALID", judge_claim(oracle, B64, f"{host - 1:016x}")[0].value)
    add("claim: exact oracle", "VALID", judge_claim(oracle, EXACT, f"{oracle.numerator}/{oracle.denominator}")[0].value)
    wrong = oracle + TINY
    add("claim: exact oracle + 1e-40", "INVALID",
        judge_claim(oracle, EXACT, f"{wrong.numerator}/{wrong.denominator}")[0].value)
    add("claim: halted run (no value)", "REFUSED", judge_claim(oracle, B64, None)[0].value)

    def refused(fn) -> str:
        try:
            fn()
            return "SETTLED"
        except Refused:
            return "REFUSED"

    k0 = next(iter(exact_inputs))
    shifted = dict(exact_inputs, **{k0: exact_inputs[k0] + TINY})
    add(f"oracle: '{k0}' shifted by 1e-40", "REFUSED", refused(lambda: settle_oracle(shifted, mp_angle)))
    name, val, agree = mp_angle
    with mpmath.workdps(agree + 40):
        nudged = (name, val * (1 + mpmath.mpf(10) ** -100), agree)
    add("oracle: high-precision angle shifted by 1e-100 relative", "REFUSED",
        refused(lambda: settle_oracle(exact_inputs, nudged)))
    add("oracle: only one exact derivation", "REFUSED",
        refused(lambda: settle_oracle({k0: exact_inputs[k0]}, mp_angle)))

    # every single step, nudged by one unit, must be rejected
    for label, prof, run_, nudge in (
            ("binary64", B64, b64_run, lambda r, d: f"{int(r, 16) + d:016x}"),
            ("exact", EXACT, exact_run, lambda r, d: str(Fraction(r) + d * TINY))):
        total = caught = 0
        for op, args, res in run_.steps:
            for d in (1, -1):
                if prof is B64 and (int(res, 16) & ~(1 << 63)) == 0 and d == -1:
                    continue                                       # no magnitude below zero
                total += 1
                caught += judge_step(prof, op, args, nudge(res, d)) is not None
        add(f"{label} steps: every step nudged +-1 unit is rejected ({caught}/{total})", True, caught == total)
    return rows


def ported_hard_case_test() -> dict:
    cmd = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests/test_ported_hard_cases.py"]
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    # keep only counts: timing and warning lines differ between machines and would break the digest
    counts = {k: int(n) for n, k in re.findall(r"(\d+) (passed|failed|errors?|skipped|xfailed|xpassed)", p.stdout)}
    return {"command": " ".join(cmd[1:]), "returncode": p.returncode, "counts": counts}


def informational(name: str, mod, oracle: Fraction, exact_run, b64_run) -> dict:
    info = {}
    if name == "rump":
        sweep = {}
        for bits in (24, 53, 64, 113, 128):
            v = rump.mp_eval(bits)
            sweep[f"{bits}_bits"] = mpmath.nstr(v, 17)
        info["mpmath_precision_sweep (same evaluation order)"] = sweep
    if name == "muller":
        exact_ok = all(Fraction(exact_run.registers[f"x{n}"]) == muller.closed_form(n) for n in range(muller.N + 1))
        info["exact run equals closed form at every n <= 30"] = exact_ok
        first = None
        for n in range(muller.N + 1):
            if abs(decode(B64, b64_run.registers[f"x{n}"]) - muller.closed_form(n)) > Fraction(1, 1000):
                first = n
                break
        info["binary64 first n with |error| > 1e-3"] = first
        info["binary64 x_n at n = 10, 15, 20, 25, 30"] = {
            n: show(decode(B64, b64_run.registers[f"x{n}"])) for n in (10, 15, 20, 25, 30)}
        sweep = {}
        for bits in (53, 113, 200, 300):
            sweep[f"{bits}_bits"] = mpmath.nstr(muller.mp_iteration(bits)[muller.N], 17)
        info["mpmath x_30 by precision"] = sweep
    if name == "gendot":
        fx = gendot.load()
        info["fixture_sha256"] = gendot.FIXTURE_SHA256
        info["exact condition number C = 2*sum|x_i*y_i| / |x.y|"] = mpmath.nstr(
            mpmath.mpf(gendot.condition_number().numerator) / gendot.condition_number().denominator, 6)
        info["generator-reported condition number"] = fx["generator_condition_number"]
        info["generator d judged against the Lab's exact oracle"] = (
            judge_claim(oracle, B64, fx["generator_d_bits"])[0].value)
        info["host float64 naive loop bit-identical to calculator binary64 naive"] = (
            gendot.hardware_naive_bits() == execute(gendot.program("naive"), B64, gendot.OUT).final)
        info["product exponent span (bits)"] = gendot.term_exponent_span()
    return info


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="reports/latest", help="report directory (relative to the repo)")
    args = ap.parse_args(argv)
    started = time.perf_counter()
    det = {"criteria_document": "docs/GATE0_CRITERIA.md", "benchmarks": {}}
    costs = {}
    ok = {k: True for k in ("G0-1", "G0-2", "G0-3", "G0-4")}
    for name, (mod, programs) in BENCHMARKS.items():
        t0 = time.perf_counter()
        exact_inputs, mp_angle = mod.oracle_inputs()
        oracle = settle_oracle(exact_inputs, mp_angle)
        oracle_seconds = time.perf_counter() - t0
        b = {"oracle": {"value": f"{oracle.value.numerator}/{oracle.value.denominator}", "approx": show(oracle.value),
                        "angles": oracle.angles}, "programs": {}}
        costs[name] = {"oracle_seconds": oracle_seconds, "programs": {}}
        for pname, (prog, kind) in programs.items():
            rows, prow_costs, runs = [], [], {}
            for p in [B64, EXACT] + EXTRA_PROFILES:
                e, row, cost = run_one(prog, p, mod.OUT, oracle.value)
                row["counts_for_criteria"] = p in (B64, EXACT)
                rows.append(row)
                prow_costs.append(cost)
                runs[p.label] = e
            b64, ex = runs["binary64"], runs["exact"]
            inj = injections(oracle.value, exact_inputs, mp_angle, b64, ex)
            b["programs"][pname] = {"kind": kind, "runs": rows, "injections": inj,
                                    "informational": informational(name, mod, oracle.value, ex, b64)}
            costs[name]["programs"][pname] = prow_costs
            r = {row["profile"]: row for row in rows}
            if kind == TRAP:
                ok["G0-1"] &= r["binary64"]["verdict"] == "INVALID"
            else:
                ok["G0-3"] &= r["binary64"]["verdict"] == "VALID"
            ok["G0-2"] &= r["exact"]["verdict"] == "VALID"
            ok["G0-3"] &= (r["binary64"]["steps_rejected"] == 0 and r["exact"]["steps_rejected"] == 0
                           and next(i for i in inj if i["name"] == "claim: correctly rounded oracle")["ok"]
                           and next(i for i in inj if i["name"] == "claim: exact oracle")["ok"])
            ok["G0-4"] &= all(i["ok"] for i in inj)
            if name == "muller":
                ok["G0-2"] &= b["programs"][pname]["informational"]["exact run equals closed form at every n <= 30"]
        det["benchmarks"][name] = b

    ported = ported_hard_case_test()
    det["ported_hard_case_and_mutant_test"] = ported
    ok["G0-3"] &= ported["returncode"] == 0
    ok["G0-4"] &= ported["returncode"] == 0

    static = static_violations()
    loaded = loaded_a_modules()
    det["independence"] = {"static_violations": static, "A_modules_loaded_at_runtime": loaded}
    ok["G0-5"] = not static and not loaded

    criteria = {k: ("PASS" if v else "FAIL") for k, v in ok.items()}
    criteria["G0-6"] = "NOT_JUDGED_HERE (designer's home-PC run decides; compare deterministic_digest)"
    criteria["G0-7"] = "RECORDED (not a pass/fail criterion)"
    det["criteria"] = criteria
    det["benchmark_3"] = ("gendot_n50_c1e25_v1: frozen fixture generated once by the published GenDot algorithm "
                          "(Ogita-Rump-Oishi 2005, Alg. 6.1), designer-approved 2026-10-01")
    det["post_seal_changes"] = POST_SEAL_CHANGES
    det["open_items"] = ["G0-6: designer's home-PC run with matching deterministic_digest",
                         "GenDot generator is the implementer's reconstruction (paper unreachable from the build "
                         "environment); designer to diff against Algorithm 6.1. Affects the fixture's name only, "
                         "not its oracle or verdicts"]
    automated_fail = any(v == "FAIL" for v in criteria.values())
    det["gate0_overall"] = "FAIL" if automated_fail else "INCOMPLETE (open items below)"

    digest = hashlib.sha256(json.dumps(det, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    report = {"deterministic_digest": digest, "deterministic": det, "costs": costs,
              "machine": {"system": platform.system(), "release": platform.release(), "machine": platform.machine(),
                          "python": platform.python_version(), "mpmath": mpmath.__version__,
                          "cpu_count": os.cpu_count()},
              "total_wall_seconds": time.perf_counter() - started}
    out = ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)
    (out / "gate0_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (out / "GATE0_REPORT.md").write_text(markdown(report), encoding="utf-8")
    print(f"Gate 0: {det['gate0_overall']}")
    for k, v in criteria.items():
        print(f"  {k}: {v}")
    print(f"deterministic_digest {digest}")
    print(f"total {report['total_wall_seconds']:.1f} s")
    return 1 if automated_fail else 0


def markdown(rep: dict) -> str:
    d = rep["deterministic"]
    L = ["# Gate 0 결과 보고서", "",
         f"- 전체 판정: **{d['gate0_overall']}**",
         f"- deterministic_digest: `{rep['deterministic_digest']}`",
         f"- 실행 환경: {rep['machine']}",
         f"- 총 시간: {rep['total_wall_seconds']:.1f}초", "",
         "## 합격 조건", "", "| 조건 | 결과 |", "|---|---|"]
    L += [f"| {k} | {v} |" for k, v in d["criteria"].items()]
    L += ["", f"벤치마크 3: {d['benchmark_3']}", "", "남은 일:", ""]
    L += [f"- {x}" for x in d["open_items"]]
    L += ["", "봉인 이후 변경(감사 기록):", ""]
    L += [f"- {x}" for x in d["post_seal_changes"]]
    L += [""]
    for name, b in d["benchmarks"].items():
        L += [f"## {name}", "", f"oracle = `{b['oracle']['value']}` ≈ {b['oracle']['approx']}", "",
              "oracle을 정한 서로 다른 방법:", ""]
        L += [f"- {k}: `{v}`" for k, v in b["oracle"]["angles"].items()]
        for pname, pr in b["programs"].items():
            L += ["", f"### {name} / {pname} ({'알려진 함정' if pr['kind'] == TRAP else '명세상 정답이어야 함'})", "",
                  "| 프로필 | 기준 대상 | 값 | 멈춤 | 판정 | 단계 감사(거부/전체) |", "|---|---|---|---|---|---|"]
            for r in pr["runs"]:
                L.append(f"| {r['profile']} | {'예' if r['counts_for_criteria'] else '참고'} | {r['value']} | "
                         f"{r['halt']} | {r['verdict']} | {r['steps_rejected']}/{r['steps_audited']} |")
            L += ["", "일부러 넣은 오답·불일치:", "", "| 주입 | 기대 | 결과 | OK |", "|---|---|---|---|"]
            L += [f"| {i['name']} | {i['expected']} | {i['got']} | {'✔' if i['ok'] else '✘'} |" for i in pr["injections"]]
            if pr["informational"]:
                L += ["", "참고 정보:", "", "```", json.dumps(pr["informational"], indent=2, ensure_ascii=False), "```"]
    L += ["", "## A에서 옮겨 온 hard-case·mutant 시험", "", f"`{d['ported_hard_case_and_mutant_test']}`", "",
          "## 독립성", "", f"`{d['independence']}`", "", "## 비용 (기록만, 합격 기준 아님)", "",
          "| 벤치마크 | 프로그램 | 프로필 | 시간(초) | Python 힙 peak(바이트) | 연산 수 |", "|---|---|---|---|---|---|"]
    for name, c in rep["costs"].items():
        for pname, rows in c["programs"].items():
            for r in rows:
                L.append(f"| {name} | {pname} | {r['profile']} | {r['wall_seconds']:.4f} | "
                         f"{r['peak_python_heap_bytes']} | {sum(r['op_count'].values())} |")
        L.append(f"| {name} | (oracle 확정) | — | {c['oracle_seconds']:.4f} | — | — |")
    L += ["", "Python 힙 peak는 tracemalloc 값이다. 프로세스 전체 메모리(RSS)가 아니다.", ""]
    return "\n".join(L)


if __name__ == "__main__":
    sys.exit(main())
