"""Gate 1 — Physics Multi-Angle Verification. Plan and predictions sealed in docs/GATE1_PLAN.md
and benchmarks/gate1/predictions.json before this file existed.

    python run_gate1.py [--out DIR]     -> DIR/gate1_report.json, DIR/GATE1_REPORT.md (default reports/latest)
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import platform
import sys
import time
from pathlib import Path

import mpmath

from benchmarks.gate1.collision import B64, EXACT, MUTANTS, rounding_defect_r1, run, sut
from benchmarks.gate1.scenarios import SCENARIOS
from lab.claim import audit_steps
from lab.gate1_checks import BOOST, CHECKS, ORACLE_FREE, SHIFT, reference_impulse, run_check
from lab.gate1_state import SutHalt, boost, reversed_after, rotate, swap, translate
from lab.independence import loaded_a_modules, static_violations

ROOT = Path(__file__).resolve().parent
BUGS = [m for m in MUTANTS if m != "M0"]
NAMES = {"M0": "기준(버그 없음)", "M1": "충격량 부호 반전", "M2": "질량 계수 오류", "M3": "x/y 축 혼동",
         "M4": "입자 1/2 비대칭", "M5": "절대좌표 의존", "M6": "갈릴레이 boost 의존", "M7": "운동에너지 계산 오류"}


CALLS = {"n": 0}


def _counted(f):
    def g(s):
        CALLS["n"] += 1
        return f(s)
    return g


def detection_map() -> dict:
    """mutant -> scenario -> check -> {detected, note}"""
    out = {}
    for m in MUTANTS:
        f = _counted(sut(m, EXACT))
        out[m] = {sc: {c: dict(zip(("detected", "note"), run_check(c, s, f))) for c in CHECKS}
                  for sc, s in SCENARIOS.items()}
    return out


def equivalence(m: str) -> dict:
    """Is the mutant's own output identical to the correct program's on each input?"""
    res = {}
    for sc, s in SCENARIOS.items():
        try:
            res[sc] = run(s, m, EXACT)[0] == run(s, "M0", EXACT)[0]
        except SutHalt:
            res[sc] = False
    return res


def minimal_oracle_free_covers(caught: dict) -> list:
    """Smallest sets of oracle-free checks that together catch every bug in at least one scenario."""
    for size in range(1, len(ORACLE_FREE) + 1):
        hits = [list(c) for c in itertools.combinations(ORACLE_FREE, size)
                if all(any(caught[b][x] for x in c) for b in BUGS)]
        if hits:
            return hits
    return []


def control_reference_on_transformed_inputs() -> dict:
    """POST-HOC control, not in the sealed plan: give the reference check (C1) the same extra
    inputs the metamorphic checks create. If it then catches everything, the metamorphic
    checks' advantage over references was input diversity, not different mathematics."""
    res = {}
    for b in BUGS:
        f = sut(b, EXACT)
        res[b] = {}
        for sc, s in SCENARIOS.items():
            try:
                o = f(s)
                inputs = [s, swap(s), translate(s, SHIFT), rotate(s), boost(s, BOOST), reversed_after(s, o)]
                res[b][sc] = any(f(x) != reference_impulse(x) for x in inputs)
            except SutHalt:
                res[b][sc] = True
    return res


def numeric_layer() -> dict:
    """N1: does the binary64 step audit see logic bugs? does it see a rounding defect?"""
    logic = {m: {sc: bool(audit_steps(B64, run(s, m, B64)[1].steps)) for sc, s in SCENARIOS.items()} for m in MUTANTS}
    with rounding_defect_r1():
        r1 = {sc: bool(audit_steps(B64, run(s, "M0", B64)[1].steps)) for sc, s in SCENARIOS.items()}
    # exact-equality physics checks applied to the CORRECT program run in binary64 (no tolerance defined)
    f64 = sut("M0", B64)
    false_alarms = {sc: [c for c in ORACLE_FREE if run_check(c, s, f64)[0]] for sc, s in SCENARIOS.items()}
    return {"N1_on_logic_bugs": logic, "N1_on_R1": r1,
            "binary64_correct_program_exact_equality_alarms": false_alarms}


def compare_predictions(dm: dict) -> list:
    pred = json.loads((ROOT / "benchmarks/gate1/predictions.json").read_text(encoding="utf-8"))
    miss = []
    for sc in ("S1", "S2"):
        for m in MUTANTS:
            for c in CHECKS:
                want, got = pred[sc][m][c], dm[m][sc][c]["detected"]
                if want != got:
                    miss.append({"scenario": sc, "mutant": m, "check": c, "predicted": want, "measured": got,
                                 "note": dm[m][sc][c]["note"] if got else "not detected"})
    return miss


def build() -> tuple:
    t0 = time.perf_counter()
    dm = detection_map()
    map_seconds = time.perf_counter() - t0
    caught = {b: {c: any(dm[b][sc][c]["detected"] for sc in SCENARIOS) for c in CHECKS} for b in BUGS}
    counts = {m: {c: sum(dm[m][sc][c]["detected"] for sc in SCENARIOS) for c in CHECKS} for m in MUTANTS}
    false_alarms = [(sc, c) for sc in SCENARIOS for c in CHECKS if dm["M0"][sc][c]["detected"]]
    per_scenario_union = {b: {sc: sorted(c for c in ORACLE_FREE if dm[b][sc][c]["detected"]) for sc in SCENARIOS}
                          for b in BUGS}
    refs_missed_but_oracle_free_caught = [
        {"mutant": b, "scenario": sc, "caught_by": per_scenario_union[b][sc]}
        for b in BUGS for sc in SCENARIOS
        if not dm[b][sc]["C1"]["detected"] and not dm[b][sc]["C2"]["detected"] and per_scenario_union[b][sc]]
    single = {c: sum(caught[b][c] for b in BUGS) for c in ORACLE_FREE}
    t1 = time.perf_counter()
    num = numeric_layer()
    numeric_seconds = time.perf_counter() - t1
    det = {
        "plan": "docs/GATE1_PLAN.md", "predictions": "benchmarks/gate1/predictions.json",
        "scenarios": list(SCENARIOS), "checks": list(CHECKS), "oracle_free_checks": list(ORACLE_FREE),
        "matrix": {m: {sc: {c: dm[m][sc][c]["detected"] for c in CHECKS} for sc in SCENARIOS} for m in MUTANTS},
        "notes": {m: {sc: {c: dm[m][sc][c]["note"] for c in CHECKS if dm[m][sc][c]["detected"]} for sc in SCENARIOS}
                  for m in MUTANTS},
        "scenario_count_per_mutant_and_check": counts,
        "baseline_false_alarms": false_alarms,
        "equivalent_on_input": {b: equivalence(b) for b in BUGS},
        "every_bug_caught_somewhere_by_oracle_free_checks": all(any(caught[b][c] for c in ORACLE_FREE) for b in BUGS),
        "bugs_caught_by_each_oracle_free_check (any scenario, of 7)": single,
        "any_single_oracle_free_check_catches_all_7": any(v == len(BUGS) for v in single.values()),
        "minimal_oracle_free_check_sets_covering_all_7": minimal_oracle_free_covers(caught),
        "oracle_free_checks_per_bug_per_scenario": per_scenario_union,
        "references_missed_but_oracle_free_checks_caught": refs_missed_but_oracle_free_caught,
        "prediction_mismatches_S1_S2": compare_predictions(dm),
        "POSTHOC_control_C1_on_the_transformed_inputs": control_reference_on_transformed_inputs(),
        "numeric_layer": num,
        "independence": {"static_violations": static_violations(), "A_modules_loaded": loaded_a_modules()},
    }
    costs = {"detection_map_seconds": map_seconds, "numeric_layer_seconds": numeric_seconds,
             "sut_calls_in_detection_map": CALLS["n"]}
    return det, costs


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="reports/latest")
    args = ap.parse_args(argv)
    started = time.perf_counter()
    det, costs = build()
    digest = hashlib.sha256(json.dumps(det, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    rep = {"deterministic_digest": digest, "deterministic": det, "costs": costs,
           "machine": {"system": platform.system(), "machine": platform.machine(),
                       "python": platform.python_version(), "mpmath": mpmath.__version__},
           "total_wall_seconds": time.perf_counter() - started}
    out = ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)
    (out / "gate1_report.json").write_text(json.dumps(rep, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (out / "GATE1_REPORT.md").write_text(markdown(rep), encoding="utf-8")
    print(f"baseline false alarms: {len(det['baseline_false_alarms'])}")
    print(f"prediction mismatches (S1,S2): {len(det['prediction_mismatches_S1_S2'])}")
    print(f"single oracle-free check catching all 7: {det['any_single_oracle_free_check_catches_all_7']}")
    print(f"minimal covers: {det['minimal_oracle_free_check_sets_covering_all_7']}")
    print(f"deterministic_digest {digest}")
    print(f"total {rep['total_wall_seconds']:.1f} s")
    return 1 if det["baseline_false_alarms"] or det["independence"]["static_violations"] else 0


def markdown(rep: dict) -> str:
    d = rep["deterministic"]
    C, S = d["checks"], d["scenarios"]
    L = ["# Gate 1 결과 보고서 — 2D 두 원판 완전탄성충돌", "",
         f"- deterministic_digest: `{rep['deterministic_digest']}`",
         f"- 실행 환경: {rep['machine']}, 총 {rep['total_wall_seconds']:.1f}초", "",
         "## 1. 버그 × 검사: 탐지된 시나리오 수 (6개 중)", "",
         "C1·C2는 정답을 직접 계산하는 참조 검사, C3–C10·C4b는 정답 없이 하는 검사다.", "",
         "| 버그 | " + " | ".join(C) + " |", "|---" * (len(C) + 1) + "|"]
    for m, row in d["scenario_count_per_mutant_and_check"].items():
        L.append(f"| {m} {NAMES[m]} | " + " | ".join(str(row[c]) if row[c] else "·" for c in C) + " |")
    L += ["", f"기준(M0) 오경보: **{len(d['baseline_false_alarms'])}건**", "", "## 2. 시나리오별 상세 (Y = 탐지)", ""]
    for sc in S:
        L += [f"**{sc}**", "", "| 버그 | " + " | ".join(C) + " | 이 입력에서 올바른 코드와 출력 동일? |",
              "|---" * (len(C) + 2) + "|"]
        for m in MUTANTS:
            eq = "—" if m == "M0" else ("**예 (구별 불가)**" if d["equivalent_on_input"][m][sc] else "아니오")
            L.append(f"| {m} | " + " | ".join("Y" if d["matrix"][m][sc][c] else "·" for c in C) + f" | {eq} |")
        L.append("")
    L += ["## 3. 정답 없는 검사의 능력", "",
          f"- 정답 없는 검사만으로 7개 버그가 모두 어딘가에서 잡히는가: **{d['every_bug_caught_somewhere_by_oracle_free_checks']}**",
          f"- 정답 없는 검사 하나가 7개를 모두 잡는가: **{d['any_single_oracle_free_check_catches_all_7']}**",
          f"- 각 검사가 잡은 버그 수(7개 중): `{d['bugs_caught_by_each_oracle_free_check (any scenario, of 7)']}`",
          f"- 7개를 모두 덮는 최소 검사 조합: `{d['minimal_oracle_free_check_sets_covering_all_7']}`", "",
          "**참조 계산(C1·C2)은 놓쳤지만 정답 없는 검사가 잡은 경우:**", ""]
    L += [f"- {x['mutant']} / {x['scenario']}: {x['caught_by']}" for x in d["references_missed_but_oracle_free_checks_caught"]]
    ctl = d["POSTHOC_control_C1_on_the_transformed_inputs"]
    L += ["", "**사후 대조(봉인 계획에 없던 분석):** 참조 계산 C1에 변환 검사들이 만든 것과 같은 추가 입력을 줬을 때 잡은 시나리오 수:", ""]
    L += [f"- {b}: C1 단독 {d['scenario_count_per_mutant_and_check'][b]['C1']}/6 → 추가 입력 포함 {sum(v.values())}/6"
          for b, v in ctl.items()]
    L += ["", "## 4. 봉인한 예측과 다른 칸 (S1, S2)", "", "| 시나리오 | 버그 | 검사 | 예측 | 실측 | 기록 |", "|---|---|---|---|---|---|"]
    L += [f"| {x['scenario']} | {x['mutant']} | {x['check']} | {'Y' if x['predicted'] else 'N'} | "
          f"{'Y' if x['measured'] else 'N'} | {x['note']} |" for x in d["prediction_mismatches_S1_S2"]]
    n = d["numeric_layer"]
    L += ["", "## 5. 수치 층 (binary64)", "",
          "| 버그 | N1(단계 반올림 감사)이 잡은 시나리오 수 |", "|---|---|"]
    L += [f"| {m} | {sum(v.values())}/6 |" for m, v in n["N1_on_logic_bugs"].items()]
    L += [f"| R1 반올림 결함 | {sum(n['N1_on_R1'].values())}/6 |", "",
          "올바른 프로그램(M0)을 binary64로 돌려 정확 등식 검사에 넣었을 때 울린 검사(허용 오차를 정의하지 않았으므로 버그가 아님):", ""]
    L += [f"- {sc}: {v}" for sc, v in n["binary64_correct_program_exact_equality_alarms"].items()]
    L += ["", "## 6. 독립성", "", f"`{d['independence']}`", "", "## 7. 비용", "", f"`{rep['costs']}`", ""]
    return "\n".join(L)


if __name__ == "__main__":
    sys.exit(main())
