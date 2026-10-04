# Lab C1-B1 arithmetic V1 — 구현·검증·계측 기록

상태: **IMPLEMENTED / AUTHOR CHECKS PASS / INDEPENDENT REVIEW PENDING / NotCertified**.
Fast: **EXPERIMENTAL / OPT-IN**. 기본 claim 계산 경로: `exact_slow`.
범위: **ARITHMETIC_ONLY / J_NOT_VERIFIED**. 실제 C1-B1 물리 domain binding과 독립 impulse는 없다.
날짜: 2026-10-04. 작업 기준 Lab HEAD: `e976fa0fdeef16a27f112a0a4ee42494fe1e46b1`.

승인된 [설계 제안서](INDEPENDENT_CALCULATOR_FAST_ARITHMETIC_DESIGN.md)를 바탕으로 새 계층을
추가했다. 제안서는 당시 DESIGN ONLY 기록으로 그대로 보존했다. 기존 Regular 2-Step의
외부 감사 상태와 이번 새 계산기의 author 검증 상태를 결합하지 않는다.

## 채택 사양과 코드 경계

계산기 코드를 만들기 전에 [Lab-owned manifest](../independent_checker/c1b1/semantic_manifest_v1.json)를
생성했다. Raw UTF-8/LF 바이트 SHA-256:

```text
3217fc38aa798fff3ffea8072cecafaecac9f98be85589e9fa35a9dc6aa8119b
```

[SHA 기록](../independent_checker/c1b1/semantic_manifest_v1.sha256)과 `contracts.py`의 pinned
상수에 같은 값을 기록하고 import 시 실제 manifest 바이트를 확인한다. 사양에는 signed FX
범위, nearest-even, drift v2의 displacement rounding, exact displacement/endpoint, stored
position, J 부호, 성분별 range/거부 순서, segment/stored guard와 strict threshold 의미를 넣었다.
이 해시는 **Lab이 채택한 사양 데이터**의 해시다. 원본 함수·클래스·helper의 해시를
specification fingerprint로 재사용하지 않았다. 원본 specification 문서 해시는 별도 provenance다.

Canonical pos=(96,48), mom=(96,80)는 candidate binding 정보로 분리했다. Generic 산술 API는
W=2..4096, 0≤F<W의 signed FX를 지원하며 다른 kind/rounding/overflow 의미는 거부한다.
Signed/zero dt는 산술 시험 의미이며 물리 실행 승인이 아니다. 양의 mass와 threshold를 요구한다.
API 유리수는 비약분 pair도 허용하고, 외부 wire는 서로소 pair와 zero=(0,1)을 요구한다.

공유한 것은 immutable schema, 순수 validation/Failure 기록, 사양과 geometry다. Slow와 fast는
drift/kick 산술·rounding·operation range helper를 공유하지 않는다. 기존 `numeric_core`의
FixedPoint 변환도 oracle로 사용하지 않는다. 원본 C1-B1 source를 읽어 복제하거나 import하지
않았고, 원본 replay/fast impulse도 호출하지 않았다.

공통 신뢰 기반은 Python int/Fraction, parser/입력 검증, manifest, exact_geometry다.
두 경로의 agreement만으로 이 공통 기반의 정확성을 증명하지 않는다.

## 구현과 공개 API

| 파일 | 역할 |
|---|---|
| [contracts.py](../independent_checker/c1b1/contracts.py) | Grid/Ratio/요청/결과의 immutable 데이터, LabRefusal/Failure, 엄격한 입력 validation, spec SHA binding |
| [exact_slow.py](../independent_checker/c1b1/exact_slow.py) | Fraction decode와 직접 p·dt/m, Fraction 거리 비교 nearest-even, 별도 displacement/position range, Fraction kick |
| [exact_fast.py](../independent_checker/c1b1/exact_fast.py) | 비약분 N/D drift, signed floor quotient/remainder nearest-even, raw kick; per-call coefficient, persistent cache 없음 |
| [exact_geometry.py](../independent_checker/c1b1/exact_geometry.py) | exact segment minimum과 stored R², equality 허용, supplied threshold만 검증 |
| [compare.py](../independent_checker/c1b1/compare.py) | 유리수 cross multiplication, 결과·Failure·예외 type·순서·입력 변이 비교 |
| [claim_adapter.py](../independent_checker/c1b1/claim_adapter.py) | strict plain-data/JSON claim, acquisition/record/phase 보존, canonical artifact 비교, fast explicit opt-in |

산술 진입점은 두 경로 각각 `drift(DriftInput)`, `kick(KickInput)`,
`guarded_drift(DriftInput, Ratio)`다. `Grid`, `Ratio`와 vector tuple을 사용한다.
출력 exact 값은 slow의 Fraction과 fast의 Ratio로 다를 수 있으나 비교는 유리수 값으로 한다.
Fast도 exact endpoint를 보존하며 Fraction 생성은 guard/보관 경계에서만 필요하다.

Lab V1 순서: 모든 입력 검증 → i.x/y/z → j.x/y/z. Drift 각 성분에서는 rounding →
displacement range → stored-position range 순서다. 그 뒤 exact segment guard → stored guard →
최종 immutable 결과 반환이다. Kick은 i의 p−J, 다음 j의 p+J다. 실패는 partial 결과/state commit을
하지 않는다. 원본 undocumented 예외 우선순위의 재현은 주장하지 않는다.

Geometry 공개 `evaluate(q0,q1,stored_relative,r_min_squared)`는 순수 exact 유리수 입력을
받아 tau/min_R²/stored_R²와 두 intrusion flag를 돌려준다. `guarded_drift`는 segment 침범을
먼저 거부하고 stored 침범을 다음에 거부한다. 실제 `1.2 angstrom → bohr` binding은 PENDING이다.
이번 결과의 domain 표시는 **EXACT_THRESHOLD_ONLY**다.

외부 claim은 `LAB_C1B1_CLAIM_V1` envelope이며 plain input과 claimed Outcome을 받는다.
Raw/rational은 canonical decimal 문자열, grid W/F는 정수 metadata다. 중복/unknown key,
bool/float raw, 비정규 정수·유리수, 누락 ID 등을 거부한다. JSON byte cap은 1 MiB,
정수 문자열은 최대 4096 decimal digits다. `compare_claim(payload)`는 slow가 기본이다.
`compare_claim(payload, "exact_fast", opt_in=True)`로만 fast를 고른다.

Claim의 `ARITHMETIC_MATCH`는 계산/거부 기록이 맞다는 뜻이다. `calculation_status=REFUSED`면
거부가 일치한 것으로, 전이가 수락된 것이 아니다. 결과에 scope/J 미검증 표시를 유지하며
REPLAY_VERIFIED/CONFIRMED/CERTIFIED를 발행하지 않는다. 같은 bits의 서로 다른 record를 합치지 않는다.

## 실제 검증 순서와 결과

Slow 단독 → fast 단독 → differential → geometry 단독 → 실제 mutants → 외부 plain-data
comparison 순서로 실행한 뒤 benchmark/profile을 실행했다. 이후 검증을 보강해 최종 관련
suite를 재실행했다. **105 passed**: 새 전용 검증 98개, 기존 독립성/provenance 검증 7개.
이 숫자는 repository 전체 pytest 실행이나 원본 프로젝트 FULL 실행을 의미하지 않는다.

| 최종 묶음 | pytest 항목 수 / 주요 내용 |
|---|---|
| slow 자체 | 20: 손 계산, ±ties/neighbors, p·dt/m과 전 lane, separate rounding, range/refusal, 입력 불변 |
| fast 자체 | 20: signed floor rounding, endpoint 보존, raw kick, displacement/final 범위, kick/drift multi-fault 우선순위 |
| differential | 7: 8,399개 signed rational cell, 큰 common factor; 4 profile의 1,600 원 입력 + 1,600 동치 pair Drift 비교와 1,600 Kick 비교; 성공·거부 모두 포함 |
| geometry 자체 | 16: C=0, 양 끝/내부 최소, 유리수 최소, 독립 polynomial inequality, equality·양옆, rounded-only 침범 누락, stored guard와 거부 순서 |
| 실제 mutated source | 16: 승인된 12 결함군 + 조기 입력 write 변형 1개 + geometry 전용 변형 3개 |
| external plain-data | 14: 손으로 작성한 Drift/Kick/guard/거부 claim, exact endpoint discrepancy, IDs, strict wire, fast opt-in |
| 새 경계 검증 | 5: manifest 해시/변조, AST dependency, fresh-process 금지 import/원본 file access와 non-vacuity, metadata lookalike |
| 기존 경계 | 7: `tests/test_independence.py`, `tests/test_provenance.py` |

Mutant는 실제 소스 사본을 생성·변형·compile/import해 실행했다. 각 probe의 **정상 사본 PASS**를
먼저 요구하고 **mutant에서 probe 실패**가 발생해야 검출로 센다. 실제 변형과 SHA, 결과는
[mutants.json](c1b1-arithmetic-v1/mutants.json)에 있다. Production source/기존 evidence에
monkeypatch를 적용하지 않는다. 공통 geometry 변형은 slow/fast agreement에 의존하지 않고
hand-derived 기대값으로 검출한다. 검증된 결함 범위가 모든 가능한 버그를 포괄한다는 주장은 없다.

외부 plain-data 시험은 **HAND_DERIVED_TEST_ONLY** 입력이다. 실제 원본 executor를 새로
실행해 비교한 것이 아니다. 원본의 detailed exception priority/record envelope에 대한
**EXTERNAL COMPATIBILITY: NOT VERIFIED**를 유지한다. 불일치 발생 시 먼저 계약 의미를 비교한다.

재현 명령(저장소 root):

```powershell
python -m pytest -q tests/test_c1b1_slow.py tests/test_c1b1_fast.py tests/test_c1b1_differential.py tests/test_c1b1_geometry.py tests/test_c1b1_mutants.py tests/test_c1b1_claims.py tests/test_c1b1_boundary.py tests/test_independence.py tests/test_provenance.py
```

## ARITHMETIC-ONLY workload benchmark

원본의 성능 숫자는 사용하지 않았다. [실측 JSON](c1b1-arithmetic-v1/benchmark.json)에 입력 panel,
환경/source hash, 모든 표본, 실제 operation count와 관측 범위를 보존했다.
[계측 harness](../tests/c1b1_benchmark.py)는 별도 instrumentation 사본과 ordinary timing을 분리한다.
계측 사본의 모든 중간/guard 결과가 ordinary 결과와 같고, 해당 workload의 slow/fast 결과도
같음을 먼저 확인한다.

입력은 8개의 **synthetic, successful, 두 원자 3D 산술 사례**다. Candidate numeric grid만
사용하며 mass/dt/threshold는 시험용이다. Paired 전이는 supplied J로 K–D–K를 수행하고
exact segment/stored guard와 validation 비용을 포함한다. 독립 impulse, 실제 물리 binding,
실제 sealed C1-B1 audit workload는 포함하지 않는다.

20 warm-up sweeps 뒤 순서를 번갈아 9회 측정했다. 각 연산의 공통 batch는 빠른 경로 기준
250ms를 목표로 calibration했다. 실제 batch 길이는 panel 실행 속도에 따라 달라진다.
Wall/CPU는 profiler 없이 측정했으며 아래 값은 **호출 한 번(두 원자 6성분)의 중앙값**이다.

| workload | slow wall µs | fast wall µs | slow/fast wall | slow/fast CPU |
|---|---:|---:|---:|---:|
| Drift | 84.04 | 14.38 | 5.85× | 5.71× |
| Kick | 45.42 | 7.47 | 6.08× | 6.00× |
| Paired arithmetic K–D–K + guards | 262.45 | 115.60 | 2.27× | 2.25× |

실제 계측 count는 8-input sweep 전체다. `Fraction.__new__`뿐 아니라 로컬 Python 3.12의
`_from_coprime_ints` allocation route도 포함했다. Gcd는 실제 `math.gcd` C call,
정수 연산은 새 6개 모듈과 stdlib Fraction의 실행된 explicit AST 연산을 센다.

| workload/path | Fraction 생성 | gcd call | integer multiply | floor division | divmod | rounding call |
|---|---:|---:|---:|---:|---:|---:|
| slow Drift | 792 | 792 | 1,080 | 748 | 0 | 48 |
| fast Drift | 0 | 0 | 336 | 0 | 48 | 48 |
| slow Kick | 408 | 360 | 624 | 384 | 0 | 48 |
| fast Kick | 0 | 0 | 0 | 0 | 0 | 0 |
| slow paired | 2,072 | 2,128 | 3,296 | 2,008 | 0 | 144 |
| fast paired | 512 | 664 | 1,296 | 478 | 48 | 48 |

Modulo/true integer division도 JSON에 기록했으며 이 panel에서는 0이었다.
Native bignum/pow/shift 내부, 대상 밖 library, 기계 전체의 모든 정수 연산 수는 **UNAVAILABLE**다.
정적 식의 연산 수를 실측 count로 대신하지 않았다. Pair fast에 남는 Fraction/gcd는
공통 exact guard 경계의 비용이며, fast impulse로 줄인 결과가 아니다.

최초 1,600-invocation batch에서는 Windows GetProcessTimes의 CPU 양자화가 두드러졌고,
fast에 0인 CPU sample도 있었다. 최초 기록을
`D:\numerical-audit-lab-fast-arithmetic-preflight-2026-10-04\benchmark-initial-short-batch-v1.json`
에 보존했고, 위 표는 batch를 늘린 재측정 값이다. CPU granularity는 여전히 측정 제약이다.
이 샘플 규모와 실행 환경의 관측이며, 장기 처리량·다른 환경·물리 audit에 일반화하지 않는다.

재현 예:

```powershell
python tests/c1b1_benchmark.py <new-report.json> <new-instrumentation-directory>
```

## 未解決・未実施と保全

- 실제 `r_min`의 1.2 angstrom→bohr binding/provenance: PENDING separate specification gate.
- 독립 impulse, full C1-B1 audit speedup, 물리 correctness, formal certification: NOT AVAILABLE.
- 원본 executor의 detailed exception/record compatibility: NOT VERIFIED.
- 별도 reviewer의 independent review: PENDING. Fast의 기본 승격은 하지 않았다.
- 기존 Regular 2-Step PASS를 새 계산기의 PASS로 이전하지 않았다.

기존 추적 1,921개 파일과 승인된 설계 제안서의 raw bytes, 원본 repository/사양 자료의
보전을 최종 receipt로 확인한다. Receipt는
`D:\numerical-audit-lab-fast-arithmetic-preflight-2026-10-04\implementation-preservation-v1.json`。
기존 Lab source/audit/sealed evidence는 변경하지 않는다. 이번 변경은 신규 파일뿐이다.
Commit/push는 수행하지 않았다.
