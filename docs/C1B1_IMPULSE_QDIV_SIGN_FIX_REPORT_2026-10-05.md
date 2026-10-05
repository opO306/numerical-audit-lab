# C1-B1 Independent Impulse V1 — QDIV-SIGN 최소 수정 및 accounting closure 검토

2026-10-05. **두 finding의 author 회귀는 통과했지만 전역 resource accounting은 NOT PASS다.**
Closure의 작성자 검토와 경로 분류는 완료했고, 남은 OPEN/UNRESOLVED를 아래에 명시했다.
새 후보는 **NOT YET INDEPENDENTLY APPROVED / INDEPENDENT LIMITED REAUDIT PENDING**이다.

```text
Historical d5475e23358cbf7f88018abfb67a8bfd192c5410:
  INDEPENDENT IMPLEMENTATION AUDIT FAIL

Historical 6a63798adbae7c119439683b356f19ff414ac239:
  F-RESOURCE-ROUND-ADD fix candidate
  F-RESOURCE-QDIV-SIGN still OPEN

new uncommitted candidate:
  F-RESOURCE-ROUND-ADD FIX APPLIED / AUTHOR REGRESSION PASS
  F-RESOURCE-QDIV-SIGN FIX APPLIED / AUTHOR REGRESSION PASS
  RESOURCE ACCOUNTING CLOSURE AUTHOR REVIEW COMPLETE
  remaining OPEN paths present; overall resource accounting NOT PASS
  INDEPENDENT LIMITED REAUDIT PENDING
  reference_producer_implementation: NOT YET INDEPENDENTLY APPROVED

runtime_activation_allowed = false
J_NOT_VERIFIED
NotCertified
```

## 기준과 변경

실제 HEAD는 `6a63798adbae7c119439683b356f19ff414ac239`, 직접 parent는
`d5475e23358cbf7f88018abfb67a8bfd192c5410`로 요청과 일치했다.
Branch는 `codex/c1b1-fclaim1-output-limit`이며 작업 시작 시 clean이었다.
사용자 [요청 원문](../current/c1b1-qdiv-sign-fix-2026-10-05/user-request.txt)을 전체 읽고 exact-copy했다.
새 Git commit은 없으며 commit/push하지 않았다.

Reference source 변경은 `resource.py:ResourceAccount.qdiv()` 한 곳이다.

```python
numerator = self.multiply(a.numerator, b.denominator)
numerator = self.multiply(numerator, sign)
denominator = self.multiply(a.denominator, abs(b.numerator))
return self.fraction(numerator, denominator)
```

두 번째 곱셈에도 기존 `multiply()->pre()`가 실제 곱셈 전에 실행된다.
Sign 결과를 먼저 계산한 뒤 사후 청구하지 않았다.
`rounding.py`는 target과 raw byte-identical이며 기존 ROUND-ADD 사전 청구 경로를 유지했다.
물리식, potential/derivative, interval/sqrt/exp 알고리즘, rounding-cell 수학 및 normative spec은 변경하지 않았다.

| identity | SHA-256 |
|---|---|
| resource.py before | `7cf03263c0e3461adf09e22ff56882dcbc3f5c12691d1e348f5a80a6a885a9c6` |
| resource.py after | `c5e081ee2c3dc49db85271d588cc3fde6e54caa6ce6e005a36c00c25d167a7cd` |
| unchanged rounding.py | `3667079195517f84f23a37a6f0787123b16571be2f6975967b0f2a9e127b2bf9` |
| target 18-source bundle | `643e7658ca4ae6bd41efeacd734416d1e44335e0dc83823c169429fb9138aac9` |
| new 18-source bundle | `e4ae7a0491c94a8a56a7029d08b70d7afd0c422ce0057a9027111bc45541d507` |

Bundle 정의는 sorted basename→raw SHA의 canonical compact ASCII JSON+terminal LF SHA다.
[18 source inventory](../current/c1b1-qdiv-sign-fix-2026-10-05/source-identity.json),
[resource old/new diff](../current/c1b1-qdiv-sign-fix-2026-10-05/resource.diff) 및 source 사본을 남겼다.
이는 working source SHA-256이며 새 commit SHA가 아니다.

## Scalar boundary 및 ROUND-ADD 유지

수정 전 QDIV 회귀는 **6 failed / 5 passed**였다. 부족 cap 네 경우에서 refusal이 없고,
exact cap 두 경우는 40/3만 청구되어 실패했다. [RED stdout/XML](../current/c1b1-qdiv-sign-fix-2026-10-05/qdiv-red.txt)을 보존했다.
수정 후 QDIV 회귀 11개가 통과했고 모든 boundary는 새로 실행했다.

| qdiv 입력 | cap | 실제 결과 | charged work / operations |
|---|---:|---|---:|
| 1 / 1 | 40, 43 | WORK refusal | 12 / 3 |
| 1 / 1 | 44 | Fraction(1,1) | 44 / 4 |
| 1 / -1 | 40, 43 | WORK refusal | 12 / 3 |
| 1 / -1 | 44 | Fraction(-1,1) | 44 / 4 |

세 곱셈의 4+4+4 청구 후, 32 normalization이 cap을 넘으면 생성 전에 거부된다.
Python Fraction의 denominator는 정규화되어 양수이며 음수 fixture는 나누는 값 b의 numerator가 음수인 경우다.
Zero divisor에서 연산을 시작하지 않는 것과 추가 signed rational 예제도 확인했다.

| rounding 입력 | cap | 결과 |
|---|---|---|
| 7/4 | 73, 74 | WORK refusal / work73 / operations2 |
| 7/4 | 75 | 2 / work75 / operations3 |
| -5/2 | 42, 44 | WORK refusal / work42 / operations2 |
| -5/2 | 45 | -2 / work45 / operations3 |

실제 [수정 전 경계](../current/c1b1-qdiv-sign-fix-2026-10-05/before-boundaries.json)와
[수정 후 경계](../current/c1b1-qdiv-sign-fix-2026-10-05/after-boundaries.json)에 cap, ledger, failure,
raw/opposite/certificate 및 exact interval을 저장했다.

## Whole-call W2와 수학 결과

Canonical q=(5,3,-2), 원본 input bytes는 기존 regression fixture와 동일하다.
동일한 충분한 author cap 입력을 수정 전후 각각 실행했다.
새 관측 값은 다음과 같다.

```text
W                         = 2605253326086889986
historical ROUND-ADD-only  = W+152 = 2605253326086890138
QDIV-SIGN added charge     = 5314390
W2                        = 2605253326092204528
operations at W2          = 36826
```

실제 sign multiply 1590건의 declared work 합계가 5314390이며,
수정 전후 whole-call work 증가와 정확히 일치했다.
Primitive precharge 36826건의 work 합계도 PrivateResult ledger의 W2와 일치했다.
이것은 wrapper ledger의 관측 증거이며, OPEN 경로가 남은 전역 fully-accounted work 증명이 아니다.
W2를 production-approved budget으로 발급하지 않았다.

| cap | 실제 결과 |
|---|---|
| W | PUBLICATION / RESOURCE_CAP / WORK; producer RESOLVED; no raw/opposite/certificate |
| W+152 | PUBLICATION / RESOURCE_CAP / WORK; producer RESOLVED; no raw/opposite/certificate |
| W2-1 = 2605253326092204527 | PUBLICATION / RESOURCE_CAP / WORK; producer RESOLVED; no raw/opposite/certificate |
| W2 | producer RESOLVED; private raw/opposite/certificate 구성; work=W2, operations36826; NOT_PUBLISHED / STOP |

성공 시 raw는 기존 값과 동일하다.

```text
(52119986341579705480988,
 31271991804947823288593,
 -20847994536631882192395)
```

충분한 같은 입력에서 V interval, V′ interval, radius, local exp orders와 모든 J scaled endpoint의
정확한 reduced n/d가 수정 전후 동일했다. Nearest-even raw도 동일하다.
V/V′는 별도의 diagnostic ledger로 계산했고 whole-call W2에 그 추가 진단 비용을 섞지 않았다.
같은 model의 author before/after equality이며 새 독립 oracle 검증으로 부르지 않는다.
Certificate source identity와 budget binding은 필요한 대로 달라지므로 전체 certificate bytes가 동일하다고 주장하지 않는다.

활성 회귀에서 W+152를 새 성공 고정값으로 요구하던 기대를 거부 확인으로 바꾸고
W2-1/W2의 새 literal boundary 회귀를 추가했다.
6a의 과거 `ROUND-ADD-only additional work=152`와 성공 evidence는 수정하지 않았다.

## Accounting closure 검토

승인 work 식의 여섯 class를 wrapper, static call sites, 실제 call sites, bypass/scope gap 및
ACCOUNTED / EXPLICITLY OUTSIDE THIS WORK MODEL / OPEN으로 분류했다.
상세 [한국어 closure 표](../current/c1b1-qdiv-sign-fix-2026-10-05/RESOURCE_ACCOUNTING_CLOSURE_KO.md)와
[source inventory / 실제 precharge JSON](../current/c1b1-qdiv-sign-fix-2026-10-05/resource-accounting-review.json)에 있다.

다음 OPEN은 해제하지 않았다.

- **O-R2-TRUTH-PATH:** compute의 직접 rational R² 구성은 첫 sqrt entry의 ledger가 0인 상태로 실행된다.
  Rational cost 의무와 연결되는 finding 후보다. Fixed input bound를 work 면제로 추정하지 않았다.
- **O-CONTROL-PARAMETERS:** counter/precision/order, parity, abs, unary/range/control 연산의 abstract operation 배정.
  Source syntax만으로 확정 결함이나 비용 면제를 발급하지 않았다.
- **O-DIRECT-FRACTION-CONSTRUCTION:** point/literal/input/constants construction이 charged normalization인지에 대한 범위 근거.
- **O-ALLOCATION-AND-WORKER:** 검증된 allocator majorant, active policy instance, isolated hard worker와 V2 preflight의 별도 Gate.

Path join과 raw bytes32 digest concat만 non-integer/rational 계약 근거로 EXPLICITLY OUTSIDE를 사용했다.
싸거나 작다는 이유의 integer 산술 면제는 추가하지 않았다.
따라서 AUTHOR REVIEW COMPLETE와 OVERALL ACCOUNTING PASS는 서로 다른 상태다. 후자는 **NOT PASS**다.

## 새로 실행한 author 검증

Windows / CPython 3.12.7. Full 명령은 파일 필터 없는 `python -m pytest -q`와 JUnit 옵션이다.
모든 명령의 실제 exit/stdout/stderr, source before/after SHA를 새 디렉터리에 남겼다.

| 증거 종류 | 새 실행 결과 |
|---|---|
| targeted QDIV/ROUND-ADD/resource | 32 passed in 0.96s, exit0 |
| impulse-related regression | 733 passed in 5.86s, exit0 |
| frozen spec regression | 46 passed in 0.33s, exit0 |
| full repository pytest | 1126 passed in 46.79s, exit0; failure/error/skip0 |
| source semantic mutants | 기존17 + QDIV1 = 18 baseline PASS / 18 DETECTED, runner exit0 |
| static spec | 155 PASS, exit0 |
| git diff --check | exit0 |

새 mutant는 `numerator=self.multiply(numerator,sign)`를 `numerator=numerator*sign`으로 바꾼다.
Baseline은 cap40/43, 양수/음수 divisor 네 경우에서 WORK refusal이고 mutant는 잘못 성공한다.
네 pytest assertion failure로 검출됐으며 hash 차이만으로 DETECTED로 세지 않았다.
기존 17개의 edit와 fixture도 모두 유지하여 실제 임시 package에서 재실행했다.
각 mutant의 before/mutant source bytes, SHA, baseline/mutant stdout/XML 및 결과를
[mutants/results.json](../current/c1b1-qdiv-sign-fix-2026-10-05/mutants/results.json)에 남겼다.

Pytest count, boundary, precharge, mutants 및 static checks는 독립 proof 개수로 합산하지 않았다.
원 독립 감사의 I1–I14/I17–I23 판정을 새 author PASS로 다시 발급하지 않는다.
보호된 수학 source는 unchanged이며 기존 해당 author regressions가 통과했다.

## 실패 기록과 보존

초기 after probe의 equality helper는 exp order의 in-memory tuple과 JSON list를 직접 비교해
AssertionError로 중단했다. 확인 시 radius/V/V′는 같았고 canonical JSON도 동일했다.
Helper만 list 형식으로 정규화하여 재실행했고 모든 exact 수학 값의 동등성을 확인했다.
[최초 helper 실패 자료](../current/c1b1-qdiv-sign-fix-2026-10-05/after-probe-first-helper-failure.json)를 보존했다.
이는 production 수학 결과 차이나 새로운 numerical finding이 아니며 실패를 삭제하지 않았다.

최초 receipt 수집도 sign charge 합계의 Python int와 JSON decimal-string을 직접 비교해
AssertionError(exit1)로 중단했다. 실제 합계와 저장 값은 모두 5314390이었다.
Receipt helper의 비교에서 int 변환을 적용했고
[최초 receipt helper 실패](../current/c1b1-qdiv-sign-fix-2026-10-05/receipt-first-helper-failure.json)를 남겼다.
그 다음 수집은 아직 생성 전인 `receipt.json`의 상대 링크를 검사하다 exit1로 중단했다.
예외를 정확한 생성 예정 receipt 경로에만 적용하도록 수정하고
[두 번째 receipt helper 실패](../current/c1b1-qdiv-sign-fix-2026-10-05/receipt-second-helper-failure.json)를 남겼다.
Receipt 생성 후에는 모든 링크를 다시 확인한다. 이 helper repair들은 production source를 변경하지 않았다.

Target tracked 2570개 중 변경은 resource.py와 활성 whole-call 회귀 파일 두 개, 삭제0개다.
나머지 2568개 raw bytes가 보존됐다. 기존 specs/docs/audit/current 718개 모두 byte-identical이다.
Arithmetic 보호8개는 target과 65d8fd2 antecedent에 byte-identical이고 승인 spec 및 과거 evidence도 그대로다.
Impulse source18개 중 resource.py 외17개, 특히 rounding.py는 unchanged다.
[보존 receipt](../current/c1b1-qdiv-sign-fix-2026-10-05/preservation.json)를 남겼다.

## 유지한 제한

Adapter의 `n_R(t)=ceil(4*rate*r_guard+1)*2**t` 독립 reconstruction은 OPEN이다.
PREPARED_ONLY / invoke blocked / V2 numerical recheck NOT APPROVED를 유지한다.
Runtime activation, J verification, physical/trajectory PASS 및 certification을 승인하지 않았다.
Allocator footprint는 AUTHOR_FIXTURE_MODEL_UNVALIDATED이며 실제 RSS/검증 majorant로 해석하지 않는다.

이번 읽기 범위는 사용자 요청 전체, 승인 finite-policy JSON와 Human B5 전체, 관련 source 및
현재 ROUND-ADD/QDIV 회귀와 mutant helpers다. Source18개 전체는 이번 AST inventory와 보존 SHA로
확인했고, 나머지 source의 상세 독해는 직전 검토와 현재 truth path 관련 재독해를 구분한다.
새 full/spec/static/mutant 실행은 위 결과이고 과거 로그 열람과 합산하지 않는다.

최종 [작성자 receipt 및 evidence 목록](../current/c1b1-qdiv-sign-fix-2026-10-05/receipt.json).
HEAD는 시작 target 그대로이고 새 commit/push하지 않았다.
