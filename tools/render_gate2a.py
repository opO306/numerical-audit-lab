"""Render reports/<dir>/gate2a_report.json as GATE2A_REPORT.md (no recomputation).

    python tools/render_gate2a.py reports/cloud-container-2026-10-01
"""
import json
import sys
from pathlib import Path


def e(v):
    if isinstance(v, float):
        return "∞" if v == float("inf") else f"{v:.2e}"
    return str(v)


def main(d: str) -> None:
    rep = json.loads((Path(d) / "gate2a_report.json").read_text(encoding="utf-8"))
    D, C = rep["deterministic"], rep["costs"]
    L = ["# Gate 2A 결과 보고서 — Hénon–Heiles (published-model reproduction, 외부 코드 감사 아님)", "",
         f"- deterministic_digest: `{rep['deterministic_digest']}`",
         f"- N = {D['N']} step, h = {D['h']}, 실행 환경 {rep['machine']}",
         f"- 총 시간 {rep['total_wall_seconds']:.0f}초, 최대 RSS {rep['peak_rss_bytes'] / 2**20:.0f} MiB" if rep["peak_rss_bytes"] else "",
         "", "**인증 범위:** 아래의 PASS는 'binary64 실행 ↔ 같은 이산 프로그램의 정확 산술'(반올림 층 A)에 대한 것이다. "
         "연속 Hénon–Heiles 궤적(방법 층 B)은 인증하지 않는다.", "", "## 궤도 분류 (계획 3절 규칙)", "",
         "| 목록 | (p_x, p_y) | 쌍둥이 궤적 최대 분리 | 분류 |", "|---|---|---|---|"]
    for k, rows in D["classification"].items():
        L += [f"| {k} | ({r['px']}, {r['py']}) | {r['max_separation']:.2e} | {r['label']} |" for r in rows]
    L += ["", f"선택: {D['selected']}", ""]
    for name, o in D["orbits"].items():
        if isinstance(o, str):
            L += [f"## {name}: {o}", ""]
            continue
        c = C["orbits"][name]
        L += [f"## {name} 궤도 — 초기 운동량 {tuple(o['initial_momentum'])}, 에너지 {o['energy']:.5f}", "",
              f"- **N1 전수 감사:** {o['N1']['ops_audited']:,}개 연산, 잘못 반올림 {o['N1']['incorrectly_rounded']}개",
              f"- **상태 인증 한계(HORIZON):** {o['state_horizon'] if o['state_horizon'] else 'N까지 유지'} step",
              f"- **K2 거울 대칭:** {o['K2_mirror']['verdict']} ({o['K2_mirror']['reason']}); 기록 지점 중 비트 단위로 정확한 거울상 {o['K2_mirror']['checkpoints_exactly_mirrored']}",
              f"- **K3 국소 힘 법칙:** {o['K3_force_law']['checks']:,}회 중 실패 {o['K3_force_law']['failed']}회, 최대 잔차/상한 {o['K3_force_law']['max_residual_over_bound']:.3f}",
              f"- **K5 host float 비트 동일성:** 불일치 step {o['K5_host_float_bit_identity']['mismatch_steps']}",
              f"- **M1 에너지:** {o['M1_energy']['verdict']} — {o['M1_energy']['reason']}",
              f"- 비용: 전진 {c['forward_seconds']:.0f}초, 역전 {c['reversal_seconds']:.0f}초, 거울 {c['mirror_seconds']:.0f}초, "
              f"정확 구간 {c['windows_seconds']:.1f}초, 합계 {c['total_seconds']:.0f}초, 실행 step {c['steps_executed']:,}", "",
              "| step | 오차 상한(최대) | 상태 크기(최대) | 실제 오차 추정 (사후, 120자리, 상한 아님) | 에너지 변화 H(ŝ)−H(s₀) | 반올림 몫 상한 |",
              "|---|---|---|---|---|---|"]
        est = {r["step"]: r["estimated_actual_error"] for r in o["POSTHOC_ESTIMATE_actual_error_120_digits"]}
        m1 = {r["step"]: r for r in o["M1_energy"]["rows"]}
        for g in o["bound_growth"]:
            s = g["step"]
            L.append(f"| {s} | {e(g['max_bound'])} | {g['max_abs_state']:.3f} | {e(est.get(s, '—'))} | "
                     f"{e(m1[s]['energy_change'])} | {e(m1[s]['rounding_part_bound'])} |")
        L += ["", "| K1 시간 역전 L | 판정 | 이유 | 최대 잔차 | 최대 상한 |", "|---|---|---|---|---|"]
        L += [f"| {k['L']} | {k['verdict']} | {k['reason']} | {e(k['max_residual'])} | {e(k['max_bound'])} |"
              for k in o["K1_time_reversal"]]
        L += ["", "| K4 정확 구간 (SAMPLED) n₀ | step | 상한 위반 | 최대 실제/상한 |", "|---|---|---|---|"]
        L += [f"| {w['n0']} | {w['steps']} | {w['bound_violations']} | {w['max_actual_over_bound']:.3f} |"
              for w in o["K4_exact_windows_SAMPLED"]]
        L.append("")
    L += ["## 심은 결함 (10³ step, 규칙 궤도 출발)", "",
          "| 결함 | N1 오반올림 | K1 (L=1000) | K1 (L=100, 사후) | K2 | K3 실패 | K5 불일치 step | 잡은 검사 |",
          "|---|---|---|---|---|---|---|---|"]
    for d_, r in D["planted_defects"].items():
        L.append(f"| {d_} | {r['N1_incorrectly_rounded']} | {r['K1']} | {r.get('POSTHOC_K1_L100', '—')} | {r['K2']} | "
                 f"{r['K3_failed']} | {r['K5_mismatch_steps']} | {r['detected_by']} |")
    L += ["", f"독립성: `{D['independence']}`", ""]
    (Path(d) / "GATE2A_REPORT.md").write_text("\n".join(x for x in L if x is not None), encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "reports/cloud-container-2026-10-01")
