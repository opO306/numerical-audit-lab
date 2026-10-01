# V2 provenance: 감사 자료 연결 (2026-10-01)

V2 결과와 독립 감사 결과를 하나로 묶어 동결한다. 아래 표의 "상태" 칸은 **이 저장소에 실제로 들어 있는지**를 뜻한다.

| 자료 | 위치 | 상태 |
|---|---|---|
| 감사된 V2 바이트와 SHA-256 | [BINARY64_TOLERANCE_RULE_V2](BINARY64_TOLERANCE_RULE_V2.md), `tests/test_v2_sealed.py` | **보존됨** |
| V2 계획, 결과, 실행 보고서 | `docs/V2_ERROR_BOUND_PLAN.md`, `docs/V2_RESULT.md`, `reports/cloud-container-2026-10-01/v2_report.json` | **보존됨** (해시 봉인) |
| V2_AUDIT_CHARTER (감사 범위 문서) | `docs/V2_AUDIT_CHARTER.md` | **보존됨** (해시 봉인) |
| V2_INDEPENDENT_AUDIT_REPORT | `audit/v2_independent/V2_INDEPENDENT_AUDIT_REPORT.md` | **보존됨** (2026-10-01 수령). SHA-256 `8746d58cfbcf013550c0226f0cf9db9d657e268ddb1e14d10bc21382180a130d`. 설계자가 준 값과 구현자가 다시 계산한 값이 같다. `tests/test_v2_audit_report_sealed.py`가 고정 |
| 독립 감사 evidence / reproduction code | `audit/v2_independent/evidence/` (예정) | **미수령.** 보고서가 이름을 언급한 `v2_boundary_audit.py`, `v2_primitive_independent_check.py`, `v2_rebase_independent_check.py` 등의 실제 파일을 받지 못했다 |
| P1–P15 판정 | 보고서 "P1–P15" 표 | **보존됨** (보고서 원문) |
| F-SELF-1 증명 | 보고서 "F-SELF-1 독립 판정" | **보존됨** (보고서 원문. 증명 + 자동 공격 31 + 71,825 + 120,000건) |
| Minor 1–5 | [V2.1_BACKLOG](V2.1_BACKLOG.md), 보고서 "발견 사항" | **보존됨.** 원문 번호와 내용 그대로 반영 |

## 설계자 보고 요약 (2026-10-01)

| 항목 | 결과 |
|---|---|
| P1–P15 | 전부 PASS |
| 치명 / 주요 / 미결 | 0 / 0 / 0 |
| 경미 | 5 |
| F-SELF-1 | 현재 구현에서 sound함이 독립 증명됨 |
| rebase 계수 반올림 mutant | 기존 단위 시험이 잡지 못함 → 시험 범위(커버리지) 결함. 현재 V2 구현 결함은 아님 |
| 감사 판정 | 감사 범위 문서 6절의 PASS 조건 충족 |

**주의:**
- 이 요약은 원본 감사 보고서를 이 저장소에서 대조한 것이 아니다. 설계자가 전달한 결론이다.
- 원본 파일이 들어오면 위 "미수령" 칸을 갱신한다. 원본과 요약이 다르면 원본을 따른다.
- 원본 보고서를 실제로 열람하고 판단한 사람은 설계자다. 구현자는 원본을 보지 못했다.

## 보고서 원문에서 확인한 감사 범위 메모 (2026-10-01)

- 감사자는 `.git`이 없는 ZIP을 받았다. 그래서 커밋·HEAD는 검증하지 못했고, 대신 `tests/test_v2_sealed.py`의 7개 SHA-256을 직접 다시 계산해 전부 일치함을 확인했다(보고서 원문).
  따라서 감사된 대상의 식별자는 **커밋이 아니라 7개 파일 해시**다.
- 보고서의 결론은 위 "설계자 보고 요약"과 같다: P1–P15 PASS, 치명·주요·미결 0, 경미 5, 최종 PASS.
