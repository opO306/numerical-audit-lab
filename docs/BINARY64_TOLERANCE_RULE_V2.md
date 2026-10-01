# binary64 물리 검사 허용 오차 규칙 V2 — 정식 승격 (2026-10-01)

**상태: V2 = AUDITED / PASS / FROZEN**

이 규칙은 아래 **SHA-256의 바이트 그대로** V2 시제품을 정식 규칙으로 승격한 것이다.
- 독립 감사가 확인한 대상은 이 바이트다. **구현을 고치면 이 승격은 그 구현에 적용되지 않는다.**
- 수정판(V2.1 등)은 별도 버전이며, 감사 PASS를 자동으로 이어받지 않는다.

## 승격 근거

| 항목 | 결과 |
|---|---|
| 계획 봉인 | `docs/V2_ERROR_BOUND_PLAN.md` (커밋 `4f443da`, 구현 전) |
| 시제품 판정 | PROTOTYPE PASS — 봉인 기준 S1–S3, U1–U2, C 전부 충족 ([결과](V2_RESULT.md)) |
| 재현성 | home-PC reproducibility PASS — 클라우드·설계자 집 PC digest `6b5a39dc4be4d1603ac3eb225b7767cc271851f1ee13668d5eeb636b60a16f7b` 동일 |
| 독립 감사 | **PASS** — P1–P15 전부 PASS, 치명 0, 주요 0, 미결 0, 경미 5 (설계자 보고, 2026-10-01). 감사 범위: [V2_AUDIT_CHARTER](V2_AUDIT_CHARTER.md). 자료 보존: [V2_PROVENANCE](V2_PROVENANCE.md) |
| 승격 결정 | 설계자 승인 (2026-10-01) |

## 감사된 바이트 (SHA-256, CRLF→LF 정규화)

| 파일 | SHA-256 |
|---|---|
| `lab/v2_bound.py` | `48b91d0c45fd7f62dd09df4db28756e6f82c6bd464a040dc60ac1c924ed99780` |
| `run_v2.py` | `0e7ab8522da11e67e335c85ef202d80849bd9b8d17555eb0603e0a41148d9cbe` |
| `tests/test_v2.py` | `80ca7b81ef376ce5adc5344e2d92ae24d0887803a7fc5f235bcf1f3e61eaa5d4` |
| `docs/V2_ERROR_BOUND_PLAN.md` | `03067ff693fcc887833d08940a98516052f76085715a6052b1708a505ac7ef84` |
| `docs/V2_RESULT.md` | `336c9161561df4181cde762c6cdd00f4567b3b1b50ea7ac07635d7022e6d9d56` |
| `docs/V2_AUDIT_CHARTER.md` | `53375183d8e01bf6ebded9e2aef6373ed480eb717d3a2711283cfe6911b0c598` |
| `reports/cloud-container-2026-10-01/v2_report.json` | `493585a312ae271fa65e24e2c4e3c0d9bb32eaad9f32bf58935962d263b59c6e` |

`tests/test_v2_sealed.py`가 이 해시를 강제한다. 독립 감사 PASS를 받은 저장소 상태는 커밋 `e825015`다.

## 규칙 내용

규칙 V1([BINARY64_TOLERANCE_RULE_V1](BINARY64_TOLERANCE_RULE_V1.md))의 판정 틀은 그대로 쓴다. 바뀌는 것은 상한 B를 계산하는 방법뿐이다.
- 판정식 `|R| ≤ B`, 판정 PASS / FAIL / REFUSED, 1종·2종 구분, 금지 사항은 V1과 같다.
- 상한 B는 **V2 방법**(`docs/V2_ERROR_BOUND_PLAN.md` 1절)으로 계산한다.
  - 한 step 안에서는 연산 단위 affine 산술을 쓴다.
  - step 사이에서는 QR 기저 교체를 하고, 역행렬은 정확한 유리수로 계산한다.
  - 계산 구현은 위 해시의 `lab/v2_bound.py`다.
- V1은 폐기하지 않는다. V1로 낸 기존 판정(Gate 1, Gate 2A)은 그대로 둔다.

## 적용 범위와 한계 (승격으로 넓어지지 않음)

- **분기 없는 직선형 프로그램**에서, 연산 ADD, SUB, MUL, NEG, CONST만 다룬다. 다른 연산(DIV, SQRT, EXP 등)이나 분기가 있으면 REFUSED다.
- **반올림 층(A)만 다룬다.** binary64 실행과 같은 이산 프로그램의 정확 산술 실행을 비교한다. 연속 물리(방법 층 B)는 인증하지 않는다.
- **연산 단위 실행 기록이 필요하다.** 레지스터 값과 연산 순서를 알 수 없는 외부 바이너리에는 바로 적용할 수 없다.
- 규칙 궤도에서도 상한이 실제 오차보다 수백~수십만 배 크다. 비관적이지만 건전하다.
- 경미 5건은 [V2.1_BACKLOG](V2.1_BACKLOG.md)에 있다. 건전성 결함이 아니다(설계자 판정).
