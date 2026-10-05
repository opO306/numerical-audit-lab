# Independent Impulse V1 reference producer — author implementation report

2026-10-05. 사용자 승인 범위: 중단된 WIP 재개, reference 구현과 author evidence. Commit/push 및 runtime activation 승인은 없음.

```text
IMPLEMENTED
AUTHOR CHECKS PASS
INDEPENDENT IMPLEMENTATION AUDIT PENDING
runtime_activation_allowed = false
J_NOT_VERIFIED
NotCertified
```

위 IMPLEMENTED는 author reference producer 범위다. Production policy instance, 인증된 acquisition, enforced OS worker, V2 whole-call preflight/수치 호출, executor integration 및 공개 point proof는 미구현 또는 미실행이다. 모든 결과는 private이며 runtime entry와 adapter invoke는 POLICY_UNBOUND로 정지한다.

## 승인 antecedent와 새 작업 revision

- 시작/종료 HEAD: `bc6cf7a6312951ddefe4e066afa19bedfbeef695`.
- branch: `codex/c1b1-fclaim1-output-limit`; 시작 clean, 종료 dirty/uncommitted.
- bc6cf7a의 독립 판정은 ATTEMPT-REASON-NULL 제한 spec/static PASS 및 WIP 35/35 byte preservation이다. Producer correctness 감사 PASS를 뜻하지 않는다.
- 승인 spec: `specs/c1b1-independent-impulse-v1-attempt-reason-null/`.
- semantic SHA-256: `3c3773b306700b0cf2dced1a618ae73ad81c7dd4abbf36764fc6ec3191ff2bc1`.
- package SHA-256: `4a4cad78a192f72cf479cf16ceb971ea257d9bdf89acc5a7ca6e4fea3738219f`.
- 새 working source bundle SHA-256: `a4bd12c92a4ad7f2a00503fa0ed249c8a96546d3999a68203fe4344f0c6554d7`. Sorted filename→raw SHA inventory의 canonical ASCII JSON+LF SHA다. 새 commit ID는 아직 없다.
- 이전 spec 19파일 및 새 승인 clarification spec의 bytes와 frozen pending/as-of metadata를 수정하지 않았다. 이 문서가 별도의 후속 상태 기록이다.
- 역사 판정 `f806d8c = FAIL / F-CLAIM-1`, 65d8 Arithmetic 제한 재감사 PASS, 4cb closure FAIL, 8e pre-implementation closure PASS, bc6 제한 clarification PASS를 덮어쓰지 않았다.

전체 dependency graph와 source18개 raw SHA는 [dependency graph](../current/c1b1-impulse-reference-resume-2026-10-05/dependency-graph.json), [source identity](../current/c1b1-impulse-reference-resume-2026-10-05/source-identity.json)에 있다.

## 이어서 완성한 구현

기존 exact rational primitives, nominal BO/REL/QED 식, analytic derivative와 producer WIP를 유지하고 누락된 계약 경계를 추가했다. Public arithmetic kernels는 수정하지 않았다.

- `spec.py`: 새 승인 semantic/package만 고정 로드하고 wire/identity 데이터도 immutable로 유지한다.
- 새 `attempt.py`: 승인된 25-row table 하나를 authority로 사용한다. 세 값의 조합을 검사하고, 항상 존재하는 reason key에 성공 두 상태만 JSON null을 허용한다. H0/raw32+canonical tuple LF digest를 검증한다.
- `resource.py`, `policy.py`: shift/cross-product/gcd/isqrt 전 bit/work 검사, whole-power result bound, parameterized predicted temporary/live accounting을 추가했다. Live ledger는 해제됐을 수도 있는 모든 연산 footprint를 계속 보유하는 보수적 방식이다. Author fixture의 layout/multiplier는 **미검증 allocation model**이며 production allocator majorant가 아니다.
- `interval.py`, `sqrt_enclosure.py`, `exp_enclosure.py`, `rounding.py`: exact operations와 outward enclosures를 유지하며 생성 시 endpoint 비교, extrema, 부호 변경, rounding 및 refinement의 교차곱도 context를 통해 사전 검사한다. Production truth 경로는 midpoint/storage-grid 중간 반올림을 하지 않는다.
- `contracts.py`, `wire.py`: 전체 closed shape와 모든 decimal syntax/digit bound를 먼저 검사한 뒤 int conversion을 수행한다. 7 container levels와 leaf depth를 구분하고 입력별 parse cap, 4096-digit pre-str, host serialization refusal, Failure4096 bytes/artifact1MiB cap을 유지한다. Process-global integer-string limit을 변경하지 않는다.
- `producer.py`: 실제 시작한 resource-interrupted attempt도 허용된 UNPROVED/RESOURCE_CAP tuple로 digest에 남긴다. Failure.reason은 closed required non-null이며 resource_kind도 enum/null 규칙을 검사한다. 하나의 axis라도 해결되지 않으면 raw/opposite/certificate를 반환하지 않는다.
- `certificate.py`: validated q_raw에서 zero lane을 직접 만들고 dummy lane helper를 제거했다. Local exp order와 V2 projected order는 별개다.
- 새 `rechecker_adapter.py`: producer parser/identity/primitive를 import하지 않는 별도 Lab input/certificate parser와 binding 재계산, zero lane 검사, pinned V2 data projection을 준비했다. Source antecedent bytes도 SHA로 확인했다. `invoke()`는 항상 차단된다.

수정 source12개: certificate, contracts, exp_enclosure, identity, interval, policy, producer, resource, rounding, spec, sqrt_enclosure, wire. 새 source2개: attempt, rechecker_adapter. 기존 derivative/potential/domain/__init__4개는 그대로다. 기존 fixture support1개를 새 spec과 author controls에 맞췄고 새 test6개, audit runner/collector2개를 추가했다.

## 검증 결과 — 서로 다른 증거 종류

시작 전 기존 92 tests를 새로 실행: 92 PASS, fail/error/skip0. 구현 완료 후 전체 저장소 회귀는 아래 표와 별도로 **1099 PASS, fail/error/skip0**이다. 이는 실행된 regression case 수이며 independent proof 수가 아니다.

| 증거 종류 | 새 실행 결과 | 의미와 한계 |
|---|---:|---|
| Runtime closed relation tests | 550 PASS: valid15/invalid535 | Producer/rechecker/reason 조합 검증; 감사 matrix 코드를 oracle로 재사용하지 않음 |
| 그 외 exact/synthetic/wire/binding unit tests | 86 PASS | primitive20, allocation4, 작은 guard1, model binding6, producer 경계14, 추가 경계11, review regressions13, attempt/digest 기타17 |
| Author physical differential tests | 6 PASS | 별도 mpmath potential 및 numerical differentiation diagnostic; enclosure soundness/physical accuracy 증명이 아님 |
| Independent-parser adapter preparation | 18 PASS | identity/projection/forged binding/zero/source 검사와 disabled invocation; V2 numerical ACCEPTED 아님 |
| Frozen spec regression | 46 PASS | 기존 spec tests를 변경하지 않고 재실행 |
| Static spec checks | 155 PASS | 승인 bytes/dependencies/25-pair/Failure separation; producer 수치 실행과 별도 |
| Actual source semantic mutants | baseline16/16 PASS, mutant16/16 DETECTED | 수정 전·리뷰 수정 후 각각 실행, 최종 수정 source 기준 결과 사용 |
| Private numerical examples | 3 RESOLVED, 1 UNPROVED | public result/certificate 출판 없음 |
| New pinned impulse V2 numerical comparison | NOT_RUN | whole-call preflight/worker/activation gate 미충족 |

최종 full suite에는 기존 Arithmetic 관련105 tests, output-boundary44와 F-CLAIM source-mutant1, 기존 Arithmetic mutants16도 포함되어 모두 통과했다. 기존 다른 gate/V2 이름의 regression은 이 새로운 pinned impulse V2 수치 호출을 뜻하지 않는다. 성능 benchmark 또는 성능 승격은 수행하지 않았다.

명령:

```powershell
python -m pytest -q tests/test_impulse_reference_primitives.py tests/test_impulse_reference_model.py tests/test_impulse_reference_producer.py tests/test_impulse_attempt_reason_spec.py
python audit/c1b1-attempt-reason-null-2026-10-05/check_spec.py --output current/c1b1-impulse-reference-resume-2026-10-05/static-spec-checks.json
python audit/c1b1-impulse-reference-resume-2026-10-05/run_mutants.py mutants-after-review
python -m pytest -q --junitxml=current/c1b1-impulse-reference-resume-2026-10-05/logs/full-suite-after-review.xml
python audit/c1b1-impulse-reference-resume-2026-10-05/collect_evidence.py
git diff --check
```

최종 full suite는 51.45초, exit0이었다. [파일별 test counts](../current/c1b1-impulse-reference-resume-2026-10-05/test-counts.json)와 [최종 stdout](../current/c1b1-impulse-reference-resume-2026-10-05/logs/full-suite-after-review.txt), XML을 보존했다.

## Actual source mutants

force sign, half-step, inverse-R, R power, TT derivative, BO g-prime, exp sign, component swap, ties-away, inverse endpoints, inward rounding, early accept, resource guard, wrong spec, intermediate quantization, fixed exp cutoff를 각각 별도 임시 package에서 실제 source bytes를 수정했다. 모든 fixture는 baseline PASS이고, mutant는 pytest assertion failure로 탐지됐으며 setup/import error와 source hash mismatch만을 DETECTED로 세지 않았다. Resource guard는 32-bit cap/64-bit shift의 작은 반례를 써서 위험한 거대 allocation을 수행하지 않았다.

각 mutant의 실제 edit, baseline/source-mutant bytes, SHA-256, fixture, semantic detection reason, stdout/XML은 [최종 mutant results](../current/c1b1-impulse-reference-resume-2026-10-05/mutants-after-review/results.json)에 있다. 첫 실행 evidence도 별도 `mutants/`에 그대로 남겼다.

## 별도 작성자 코드 리뷰와 수정

실행 skill의 마지막 fresh review는 read-only로 수행했다. 독립 구현 감사로 분류하지 않는다. Important2건을 RED→GREEN으로 수정했다.

1. Fraction 직접 비교가 계측을 우회했다. bit_max20 반례는 17-bit peak만 보고하면서 실제25-bit 교차곱을 만들었다. Context-bearing Interval 및 checked rounding/refinement 경로로 바꾸고 그 연산 전에 BIT로 중단하는 regression을 추가했다.
2. 뒤쪽 malformed schema/decimal이 앞선 int conversion 뒤에 발견됐다. Producer input와 별도 adapter 양쪽에 complete first-pass validation을 추가했으며 conversion-call spy가0인 regression을 추가했다.

Review regressions RED: 11 failed/2 passed. 수정 후 관련 suite88 PASS, 이후 full1099 PASS와 mutants16 DETECTED. 두 번째 리뷰를 했다고 주장하지 않는다.

**남긴 Minor:** adapter는 V2 orders의 closed syntax/상수/순서/cap을 검증하지만 `n_R(t)=ceil(4*rate*r_guard+1)*2**t`를 별도로 재구성하여 정확한 일정 일치를 확인하지 않는다. Cap 이하의 과소 order도 PREPARED_ONLY가 될 수 있다. Producer는 승인 일정을 구성하며 이 preparation은 proof 승인이나 ACCEPTED가 아니다. Adapter order 일정 독립 검증은 후속 rechecker 구현의 미완료 항목으로 남긴다.

[Author review](../current/c1b1-impulse-reference-resume-2026-10-05/author-review.md), [progress/rulings](../current/c1b1-impulse-reference-resume-2026-10-05/progress.md)에 판단과 비용을 기록했다. Latest request가 이전 plan의 allocation 제외를 대체하여 구조만 구현했고, 미검증 fixture allocation basis/OS guard를 production으로 발급하지 않았다. 사용자 no-commit/no-push 및 evidence 보존 지시는 skill의 commit/cleanup 절차보다 우선했다.

## 실패 실행과 알려진 UNPROVED

의도된 TDD 실패와 개발 중 발견된 실패도 삭제하지 않았다. Boundary RED570 failed/1 passed; 첫 수정 run9 failed/608 passed는 immutable MappingProxy의 identity serialization 결함을 발견했고 다음617 PASS로 수정됐다. 추가 RED3 failed/8 passed는 container depth/input cap과 exact-series fixture WORK 부족을 드러냈고 다음11 PASS였다. Adapter RED18 failed 후18 PASS. Static checker 최초 호출은 필수 --output 누락으로 usage exit1였고 정정 후155 PASS. Collector 첫 호출의 historical receipt 파일명 오류를 정정하고 성공 재실행했다. 이러한 실행은 독립 감사가 아니다.

알려진 fixture: q=(0,6,1), N=P=1/8, maxima1/8, max_attempts1, exp_order_max1. 실제 결과는 COMPUTE/RESOURCE_CAP/ORDER, producer UNPROVED, raw/opposite/certificate 없음이다. [입력과 bounded failure](../current/c1b1-impulse-reference-resume-2026-10-05/examples/known-unproved-failure.json), digest를 보존했다. 모든 admissible input의 finite-policy 성공이나 convergence를 주장하지 않는다.

## 보존·독립성·제한

- Arithmetic 보호8개는 bc6 및65d8와8/8 raw byte-identical. 산술 kernels3개는 f806와도 byte-identical.
- 기준 e976의 기존1921개는1921/1921, 구현 중단 전8e의2097개는2097/2097 raw byte-identical.
- 이번 시작 bc6 tracked2163개 중2150개 그대로, 변경13개는 허용된 impulse source12개와 fixture support1개, 삭제0. 기존 docs/spec/audit/current321파일은 모두 그대로다.
- 받은 audit JSON4개와 요청 원문을 새 전용 folder에 exact-copy했고 SHA를 기록했다. Historical receipt/로그/원문을 사후 수정하지 않았다.
- Producer fresh-process module inventory와 AST import/call inspection에 executor/V2 primitive, mpmath, exec/eval/FunctionType truth 경로는 없었다. 공유되는 것은 pinned 공개 식/상수/units/state와 stdlib exact integer/Fraction 의미다.
- Input/certificate hashes는 authenticity를 증명하지 않는다. 실제 J0/J1 취득, executor comparison, whole-vector independent numerical recheck와 publication은 NOT_RUN/NOT_PUBLISHED/STOP이다.
- Drift future guard의 기존 exact unrounded closed segment minimum AND stored final point 계약 bytes를 변경하지 않았다. Stored rounded 전체 segment guard, trajectory, replay, N-Step, fast impulse를 추가하지 않았다.
- Runtime numeric instance/production budget, verified allocator basis, hard CPU/wall/memory worker, V2 whole-call conservative preflight는 미발급/미구현 gate다. Reference fixture는 승인 production 설정이 아니다.

[Preservation receipt](../current/c1b1-impulse-reference-resume-2026-10-05/preservation.json), [Git state](../current/c1b1-impulse-reference-resume-2026-10-05/git-state.json), [전체 author receipt](../current/c1b1-impulse-reference-resume-2026-10-05/receipt.json).

읽기 범위: 사용자 붙여넣은 요청 전체; 제공 JSON4개를 파싱하고 판정·550관계 통계/메타데이터 확인; pinned machine spec9개 전체 hash/canonical JSON 검사; WIP source16개와 새 source2개 및 관련 tests 전체; human B4/B5는 해당 계약 부분을 참조했다. 550 rows를 이용한 새 외부 감사나 remote 측정, 제공된 auditor script 재실행을 한 것으로 표시하지 않는다.

Commit/push, runtime activation, physical PASS, J_VERIFIED, Certified 승격은 수행하지 않았다.
