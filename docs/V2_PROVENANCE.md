# V2 provenance: 감사 자료 연결 (2026-10-01)

V2 결과와 독립 감사 결과를 하나로 묶어 동결한다. 아래 표의 "상태" 칸은 **이 저장소에 실제로 들어 있는지**를 뜻한다.

| 자료 | 위치 | 상태 |
|---|---|---|
| 감사된 V2 바이트와 SHA-256 | [BINARY64_TOLERANCE_RULE_V2](BINARY64_TOLERANCE_RULE_V2.md), `tests/test_v2_sealed.py` | **보존됨** |
| V2 계획, 결과, 실행 보고서 | `docs/V2_ERROR_BOUND_PLAN.md`, `docs/V2_RESULT.md`, `reports/cloud-container-2026-10-01/v2_report.json` | **보존됨** (해시 봉인) |
| V2_AUDIT_CHARTER (감사 범위 문서) | `docs/V2_AUDIT_CHARTER.md` | **보존됨** (해시 봉인) |
| V2_INDEPENDENT_AUDIT_REPORT | `audit/v2_independent/` (예정) | **미수령.** 구현자는 원본 파일을 받지 못했다. 설계자가 파일을 넣으면 해시를 기록하고 봉인 시험에 추가한다 |
| 독립 감사 evidence / reproduction code | `audit/v2_independent/evidence/` (예정) | **미수령** (위와 같음) |
| P1–P15 판정 | 아래 표 | 설계자 보고 요약만 있음 (항목별 근거는 원본 보고서에 있음) |
| F-SELF-1 증명 | 원본 보고서 | **미수령.** 결론(현재 구현에서 sound)만 설계자 보고로 기록 |
| Minor 1–5 | [V2.1_BACKLOG](V2.1_BACKLOG.md) | 2건만 내용이 전달됨. 3건은 내용 미수령 |

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
