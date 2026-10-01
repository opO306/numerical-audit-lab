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
| **Gate 0** | 계산기·채점기 자체 검사 (Rump, Muller, GenDot 동결 fixture) — [기준](docs/GATE0_CRITERIA.md) | **INCOMPLETE** — 자동 조건 G0-1〜5 PASS(클라우드). 남은 일: G0-6 집 PC digest 대조, GenDot 생성기 원문 대조([선정 기록](docs/BENCHMARK3_SELECTION.md)). 봉인 후 변경 [감사 기록](docs/AUDIT_POST_SEAL_ORACLE_TOLERANCE.md). [클라우드 보고서](reports/cloud-container-2026-10-01/GATE0_REPORT.md) |
| Gate 1 | 작은 물리 benchmark 하나를 서로 다른 실패 원인을 잡는 여러 검사로 검증 | Gate 0 통과 후 |
| Gate 2 | 공개 논문/시뮬레이션 재검증 → 공개 보고서 | Gate 0·1 통과 후 |

각 Gate에서 추가 정보가 없거나 비용이 맞지 않으면 그 자리에서 중단한다.

## 실행

```bash
pip install -r requirements.txt     # mpmath
python run_gate0.py                 # reports/latest/ 에 보고서 생성 (--out 으로 위치 변경)
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
