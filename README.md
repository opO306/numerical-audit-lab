# Numerical Audit Lab

"꿈을 향해 A"(`opO306/success-is-mother-of-failure`)의 계산기와 독립 채점기를 **복사해 와서** 외부 문제에 적용해 보는 실험장이다.
목적은 제품 개발이 아니다. "이 검증 방식이 외부 문제에서도 가치가 있는가"를 확인하는 것이다.

## 원칙

- **A 본진은 건드리지 않는다.** 코드는 import하지 않고 복사만 한다. 공용 라이브러리로 만들지도 않는다.
- 복사한 파일은 원본 커밋·경로·해시를 `PROVENANCE.json`에 기록한다. Lab에서 수정하면 그 사실도 같은 파일에 남긴다.
- AI(GPT/Claude)가 "맞습니다"라고 말한 것은 증거 0점이다. AI가 제안한 검사는 실제 checker로 옮겨 실행해야 증거가 된다.
- `미검증`·`REFUSED`를 숨기지 않는다.

## 단계

| Gate | 내용 | 상태 |
|---|---|---|
| **Gate 0** | 계산기·채점기 자체 검사 (Rump, Muller, GenDot-derived 동결 fixture) — [기준](docs/GATE0_CRITERIA.md) | **CLOSED / PASS** (2026-10-01) — [종료 기록](docs/GATE0_CLOSURE.md), [감사 기록](docs/AUDIT_POST_SEAL_ORACLE_TOLERANCE.md), [보고서](reports/cloud-container-2026-10-01/GATE0_REPORT.md) |
| **Gate 1** | 2D 두 원판 완전탄성충돌: 검사 11개 × 심은 버그 7개 × 시나리오 6개 — [계획(봉인)](docs/GATE1_PLAN.md), [해석](docs/GATE1_RESULT.md), [보고서](reports/cloud-container-2026-10-01/GATE1_REPORT.md) | **CLOSED / PASS** (2026-10-01) — 설계자 집 PC에서 digest `6adecd6c…2f03` 클라우드와 동일 확인. 시나리오·mutant 추가 금지 |
| Gate 2 | 정답을 모르는 공개 물리 계산 — [허용 오차 규칙 V1(봉인)](docs/BINARY64_TOLERANCE_RULE_V1.md), [후보 비교](docs/GATE2_CANDIDATES.md) | 대상: Hénon–Heiles (설계자 결정). FPUT·3체 보류 |
| **Gate 2A** | Published-model reproduction and multi-layer verification (외부 코드 감사 아님) — [계획(봉인)](docs/GATE2A_PLAN.md), [결과](docs/GATE2A_RESULT.md), [보고서](reports/cloud-container-2026-10-01/GATE2A_REPORT.md) | **CLOSED / PARTIAL** (2026-10-01) — 집 PC digest `644fc922…57e1` 동일 확인. G2A-5 부분 충족. 결과 봉인(수정 금지) |
| **V2** | 오차 상한 V2 시제품: affine 산술 + QR 기저 교체 — [계획(봉인)](docs/V2_ERROR_BOUND_PLAN.md), [결과](docs/V2_RESULT.md) | **V2 = AUDITED / PASS / FROZEN** → [BINARY64_TOLERANCE_RULE_V2](docs/BINARY64_TOLERANCE_RULE_V2.md)로 정식 승격 (2026-10-01). 독립 감사 P1–P15 PASS, 치명·주요·미결 0, 경미 5 → [V2.1_BACKLOG](docs/V2.1_BACKLOG.md). [provenance](docs/V2_PROVENANCE.md) |
| **Gate 2B** | 공개 제3자 Hénon–Heiles 구현 감사 — [계획(봉인)](docs/GATE2B_PLAN.md), [결과](docs/GATE2B_RESULT.md) | **PASS / 답 LIMITED** (클라우드 2026-10-01, 집 PC 분석 재현 확인 전). 대상 gala 1.12.0 Linux wheel (MIT, source commit `bebac7d7…`), [provenance](docs/GATE2B_PROVENANCE.md). W1 NOT_IDENTICAL(원인: `-Ofast`가 y 기울기 계산 순서를 바꿈, 기계어로 확인) → W2–W4 REFUSED. B3·B4 PASS. digest `6ccf3d5d…928d` |

각 Gate에서 추가 정보가 없거나 비용이 맞지 않으면 그 자리에서 중단한다.

## 실행

```bash
pip install -r requirements.txt     # mpmath
python run_gate0.py                 # reports/latest/ 에 보고서 생성 (--out 으로 위치 변경)
python run_gate1.py                 # Gate 1 검사표 (약 2초)
python run_gate2a.py                # Gate 2A (N=10^5, N1 전수 감사 포함 약 10–15분)
python tools/render_gate2a.py reports/latest   # JSON → GATE2A_REPORT.md
python run_v2.py                    # V2 오차 상한 시제품 (약 20–25분)
python run_gate2b.py                # Gate 2B 분석 (동결 gala fixture 입력, gala 불필요, 약 30초)
python -m pytest tests -q
```

## 구성

| 경로 | 내용 | 출처 |
|---|---|---|
| `numeric_core/` | 계산기 VM: FX, binary64(유한), EXACT 프로필. 연산은 + − × ÷ √ exp, SUM, DOT, CMP | A `a_numeric/` 복사(무수정) |
| `independent_checker/` | 독립 채점기: 반올림을 직접 계산하지 않고, 정답이 결과의 반올림 구간 안에 있는지만 본다 | A `audit/independent_numeric/` 복사(무수정) |
| `lab/verdict.py` | VALID / INVALID / REFUSED 판정 틀 | A `c1b1_replay/types.py`의 일부를 발췌·축약 |
| `lab/claim.py` | 최종값 주장 판정, 단계별 감사 | Lab 신규 |
| `benchmarks/gate0/` | Gate 0 벤치마크. `fixtures/gendot_n50_c1e25_v1.json`은 한 번 생성 후 동결(SHA-256 고정, 재생성 금지) | Lab 신규 |
| `benchmarks/gate2a/`, `lab/gate2a_*.py`, `run_gate2a.py` | Gate 2A: Hénon–Heiles velocity Verlet SUT(계산기 쪽), N1·규칙 V1 상한·K1–K5 검사(검사기 쪽) | Lab 신규 |
| `tests/test_ported_hard_cases.py` | A의 hard-case 시험과 반올림 결함 10종 주입 시험 | A `tests/test_audit_numeric_hard_cases.py`의 import 경로만 바꿈 |

## 알려진 한계

- 계산기에는 sin·cos·log가 없다. Gate 1 benchmark는 이 연산 범위 안에서 고르거나, Lab 쪽에서 연산을 추가하고 기록한다.
- 정확한 분수 계산을 파이썬으로 하므로 느리다. 큰 문제에는 맞지 않는다.
- CPU/GPU 동일성 실행기(`a_numeric_native/`)는 가져오지 않았다.

## 집 PC에서 G0-6 확인하는 법

```bash
pip install -r requirements.txt
python -m pytest -q
python run_gate0.py --out reports/home-pc-YYYY-MM-DD
```

출력의 `deterministic_digest`를 [클라우드 보고서](reports/cloud-container-2026-10-01/GATE0_REPORT.md)의 값과 비교한다.
같으면, 시간·메모리를 뺀 모든 판정과 값이 두 기계에서 같다는 뜻이다.
