# Gate 0 종료 기록 — CLOSED / PASS (2026-10-01)

| 조건 | 결과 | 근거 |
|---|---|---|
| G0-1 알려진 함정 탐지 | PASS | Rump(2변형), Muller, GenDot-derived naive: binary64 결과 전부 INVALID |
| G0-2 exact 재현 | PASS | EXACT 프로필 결과 = oracle (Muller는 n ≤ 30 전 구간 닫힌 식과 일치) |
| G0-3 올바른 결과 accept | PASS | 올바르게 반올림한 oracle, 모든 단계 결과, 계산기 DOT(명세상 정답) 전부 VALID. 옮겨 온 hard-case 시험 통과 |
| G0-4 일부러 넣은 오답 reject | PASS | 반올림 결함 10종 전부 탐지. 최종값 ±1 ulp, 단계별 ±1 단위(Rump 100 + Muller 242 + GenDot 600 = 942건), oracle 불일치 3종 전부 거부 |
| G0-5 A 없이 독립 실행 | PASS | 정적 import 검사·실행 중 로드 모듈 검사 모두 위반 0 |
| **G0-6 로컬 PC 완주** | **PASS** | **설계자 보고:** 집 PC에서 커밋 `d0e45c5` 실행, digest `2d05505d…aa98`가 클라우드와 **동일**, 15.5초 |
| G0-7 비용 기록 | 기록됨 | 클라우드 약 19초, 집 PC 15.5초 |

## 종료 전에 정리한 두 항목

1. **Muller post-seal audit:** [감사 기록](AUDIT_POST_SEAL_ORACLE_TOLERANCE.md) 7절에 수정 전/후 숫자를 적었다. `tests/test_post_seal_audit.py` 13개가 고정한다.
2. **GenDot 원문 대조:** 원문에 접근하지 못해 15줄 중 3항목만 원문 문자열로 확인했다. 그래서 이름을 **GenDot-derived fixture**로 기록했다.
   - fixture SHA-256은 유지했고, 다시 생성하지 않았다.
   - 자세한 내용: [선정 기록](BENCHMARK3_SELECTION.md)

## digest와 종료 표시 변경의 관계

- 종료하면서 보고서의 표시 문자열 두 개(`benchmark_3`, `open_items`)를 바꿨으므로 현재 digest는 `27094d05…714a`다.
- `tools/gate0_digest_equivalence.py`는 이 두 필드를 옛 문자열로 되돌리면 집 PC digest `2d05505d…`가 그대로 나온다는 것을 보인다.
- 즉 **계산값·판정은 집 PC에서 재현된 것과 비트 단위로 같다.** `tests/test_gate0_closure.py`가 이를 고정한다.
- 런너는 집 PC 결과를 스스로 판정할 수 없으므로, 보고서 안의 G0-6 칸은 계속 `NOT_JUDGED_HERE`로 표시된다. PASS 판정의 근거는 이 문서다.

## 한계 (그대로 남음)

- G0-6의 근거는 설계자가 보고한 digest와 시간이다. 집 PC의 원본 로그는 이 저장소에 없다.
- GenDot 이름은 보수적으로 붙였다. 원문과 글자 단위로 대조해야 올릴 수 있다.
- Gate 0은 "계산기와 채점기가 제대로 작동한다"는 장비 검사다. 물리 검증 체계가 특별하다는 증거가 아니다.

**Gate 0에는 benchmark를 더 추가하지 않는다** (설계자 결정).
