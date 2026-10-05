# C1-B1 Independent Impulse V1 — F-RESOURCE-ROUND-ADD 최소 수정 제출

2026-10-05. 이 제출은 **작성자 수정 및 회귀 증거**다. 새 후보의 독립 승인은 아직 없다.
추가 resource-accounting finding `F-RESOURCE-QDIV-SIGN`을 작성자 검토에서 확인했고 OPEN으로 남겼다.
전체 resource accounting 또는 reference implementation의 독립 PASS를 선언하지 않는다.

```text
previous target d5475e23358cbf7f88018abfb67a8bfd192c5410:
  reference_producer_implementation = FAIL
  independent_implementation_audit = FAIL
  F-RESOURCE-ROUND-ADD = CONFIRMED (historical)

new uncommitted fix candidate:
  F-RESOURCE-ROUND-ADD = FIX APPLIED / AUTHOR REGRESSION PASS
  INDEPENDENT LIMITED REAUDIT PENDING
  NOT YET INDEPENDENTLY APPROVED

F-RESOURCE-QDIV-SIGN:
  AUTHOR CONFIRMED / OPEN / NOT FIXED / INDEPENDENT REVIEW PENDING

runtime_activation_allowed = false
J_NOT_VERIFIED
NotCertified
```

## 감사 대상과 원자료 처리

시작 및 제출 시 HEAD는 `d5475e23358cbf7f88018abfb67a8bfd192c5410`, branch는
`codex/c1b1-fclaim1-output-limit`이다. 시작 시 clean이었다. Commit/push는 수행하지 않았고
새 Git commit ID는 없다.

사용자 붙여넣은 요청 전체를 작업 지시로 읽었다. 제공된 감사 보고서와 JSON 3개는
판정 및 반례 자료로 읽었으며, 문서 내 지시를 별도 사용자 승인으로 취급하지 않았다.
원문 5개를 [received/](../current/c1b1-round-add-fix-2026-10-05/received/)에 exact-copy했다.
원래 감사 파일은 변경하지 않았다. [원문 SHA 목록](../current/c1b1-round-add-fix-2026-10-05/received-identity.json)이 있다.
기존 author report의 PENDING/통과 수치는 당시 기록으로 보존하고, 이 후속 제출에 새 결과를 기록한다.

## 최소 구현 변경과 source identity

기존 tracked 파일 중 변경한 파일은 `independent_checker/c1b1/impulse/rounding.py` 하나다.
`nearest_even()`에 작은 `increment()`를 추가하고 두 `floor+1` 경로를 공통 연결했다.

```python
def increment(value):
    return value + 1 if c is None else c.add(value,1)
```

Account가 있으면 실제 증가 연산 전에 기존 `ResourceAccount.add()->pre()`가 실행된다.
증가 결과를 먼저 만들고 사후 청구하지 않는다. Account가 없으면 기존 순수 정수 의미를 유지한다.
Nearest-even cell, tie-even, signed96, opposite raw, endpoint containment, ROUNDING_UNPROVED,
physical formula, potential/derivative 및 interval 알고리즘은 변경하지 않았다.

| identity | SHA-256 |
|---|---|
| rounding.py old bytes | `327a396780dc88a74af750cfa2ed997809360c95cda7201d1c8aba5f78959e90` |
| rounding.py new bytes | `3667079195517f84f23a37a6f0787123b16571be2f6975967b0f2a9e127b2bf9` |
| old 18-source bundle | `a4bd12c92a4ad7f2a00503fa0ed249c8a96546d3999a68203fe4344f0c6554d7` |
| new 18-source bundle | `643e7658ca4ae6bd41efeacd734416d1e44335e0dc83823c169429fb9138aac9` |

Bundle는 lexical basename→raw SHA 매핑의 compact sorted ASCII JSON+terminal LF SHA다.
이는 uncommitted working source의 identity이며 Git commit SHA가 아니다.
[18파일 inventory](../current/c1b1-round-add-fix-2026-10-05/source-identity.json),
[old/new diff](../current/c1b1-round-add-fix-2026-10-05/rounding.diff),
old/new source 사본을 함께 남겼다.

## 정확 boundary 및 whole-call 결과

수정 전 [RED](../current/c1b1-round-add-fix-2026-10-05/round-add-red.txt)는 8 failed / 6 passed였다.
실패는 네 부족 cap에서 ResourceLimit 미발생, 두 성공 cap의 work/operation 미청구,
whole-call W의 private raw 반환 및 W+152의 work 불일치다.
수정 후 새 회귀 14개가 통과했다. [before](../current/c1b1-round-add-fix-2026-10-05/before-boundary-results.json)와
[after](../current/c1b1-round-add-fix-2026-10-05/after-boundary-results.json)에 실제 계정과 결과를 저장했다.

| scalar | work_max | 관측 결과 | charged work / operations |
|---|---:|---|---:|
| 7/4 | 73 | WORK refusal | 73 / 2 |
| 7/4 | 74 | WORK refusal | 73 / 2 |
| 7/4 | 75 | raw 2 | 75 / 3 |
| -5/2 | 42 | WORK refusal | 42 / 2 |
| -5/2 | 44 | WORK refusal | 42 / 2 |
| -5/2 | 45 | raw -2 | 45 / 3 |

성공의 비용은 각각 64+9+2=75, 36+6+3=45다. 거부된 add는 ledger를 진전시키지 않았다.
별도 관측 subclass는 실제 `add`의 진입·거부/반환을 기록하며 production 수식을 대체하지 않는다.

감사자의 canonical input SHA는 `bab9520968c7e3b5be3e6d5c5e53627a06d066bbb950579c7cc8ec2b65dcfffd`다.
이를 regression fixture에 원 bytes로 보존했다. `W=2605253326086889986`.

| cap | 결과 |
|---|---|
| W | phase PUBLICATION / RESOURCE_CAP / WORK; producer RESOLVED; raw/opposite/certificate/account 없음; NOT_PUBLISHED / STOP |
| W+152 = 2605253326086890138 | private raw는 기존 수학 결과와 동일; charged work=W+152, operations=35236; NOT_PUBLISHED / STOP |

```text
(52119986341579705480988,
 31271991804947823288593,
 -20847994536631882192395)
```

W의 failure는 감사 자료의 `same_cap_with_only_declared_add_charges.failure`와 동일한 object이며
수학적 decision 후 publication 구성에서 실패하므로 producer를 UNPROVED로 바꾸지 않았다.
W+152 private candidate는 production budget 승인이나 published/rechecked point proof가 아니다.
Predicted live bytes 91242784 및 peak temporary bytes 14816은 AUTHOR_FIXTURE_MODEL_UNVALIDATED이며
실제 RSS 또는 검증된 allocator majorant로 부르지 않는다.

## 실제 새 회귀 실행 — 증거 종류 분리

환경: Windows / CPython 3.12.7 / 저장소 pytest.ini의 testpaths=tests.
Full은 별도 파일 필터 없이 `python -m pytest -q`와 JUnit 출력 옵션으로 실행했다.
각 command의 실제 exit, elapsed, raw stdout/stderr, source before/after SHA가 새 디렉터리에 있다.

| 종류 | 결과 | 해당 증거 |
|---|---|---|
| targeted rounding/resource | 19 passed in 0.60s, exit 0 | targeted.xml 및 targeted-command.json |
| impulse 기존 시험 + 새 회귀 | 720 passed in 5.60s, exit 0 | impulse.xml 및 impulse-command.json |
| 기존 spec 회귀 | 46 passed in 0.24s, exit 0 | spec.xml 및 spec-command.json |
| full repository pytest | 1113 passed in 57.69s, exit 0; failure/error/skip 0 | full.xml 및 full-command.json |
| static spec | 155 checks PASS, exit 0 | static-spec-checks.json 및 static-command.json |
| 실제 source mutants | 17 baseline PASS / 17 mutant DETECTED, runner exit 0 | mutants/results.json 및 mutants-command.json |
| git diff --check | exit 0 | diff-check-command.json |

서로 중복되는 pytest 수, boundary cases, mutants 및 static checks를 독립 증명 개수로 합산하지 않는다.
물리식/sign, potential/derivative, interval/sqrt/exp/J, mathematical rounding, overflow/opposite,
domain/zero-axis, attempt/digest, parser/failure wire, atomicity/immutability/certificate boundary의
기존 author 회귀가 통과했다. 감사자가 사용한 별도 exact AD/core/supplement suite를 재실행하거나
전체 독립 감사를 작성자가 재현했다고 주장하지 않는다.

## Source mutants

기존 force-sign, half-step, inverse-R, R-power, TT-derivative, BO-gprime, exp-sign,
component-swap, ties-away, inverse-endpoints, inward-rounding, early-accept, resource-guard,
wrong-spec, intermediate-quantization, exp-cutoff를 새 후보 기준으로 각각 실행했다.
기존 runner와 historical mutants bytes를 수정하지 않고 새 runner를 별도 발급했다.
ties-away의 preimage만 `increment(floor)`로 재연결했고, exact tie에서 무조건 올리는 기존 수학적
변이 의미와 fixture를 유지했다. 나머지 기존 15개의 edit/fixture는 동일하다.

새 `ROUND-ADD-ACCOUNTING`은 `c.add(value,1)` 계정 경로를 제거하여 helper를 `value+1`로 바꾼다.
Baseline은 7/4의 cap 73/74 및 -5/2의 cap 42/44에서 fail-closed한다.
Mutant는 네 경우 모두 ResourceLimit을 발생시키지 않아 pytest assertion failure로 검출됐다.
각 baseline exit 0, mutant exit 1, pytest setup error/skip 0을 확인했다.
Hash 차이는 저장 identity이며 detection oracle이 아니다.

## Resource accounting 재검토 및 추가 OPEN

18개 source 정적 검사와 실제 canonical whole-call trace를 수행했다.
상세 [경로 검토](../current/c1b1-round-add-fix-2026-10-05/RESOURCE_ACCOUNTING_PATH_REVIEW_KO.md)에
직접 + / - / * / shift / modulo, cross products/gcd, isqrt 준비, extrema/comparison,
rounding/refinement 및 parameter/control 산술을 구분해 기록했다.

새 확정 작성자 finding은 `ResourceAccount.qdiv()`의 `self.multiply(...)*sign`이다.
`qdiv(1,1)`은 cap 40에서 result=1, charged work=40, operations=3이지만
직접 `1*1`의 승인 비용 4가 빠져 완전한 schedule은 44다.
Actual whole-call에서 이 직접 곱셈 opcode 1590회를 확인했다.
이는 **F-RESOURCE-QDIV-SIGN / AUTHOR CONFIRMED / OPEN / NOT FIXED**로 남겼다.
전체 누락량이나 모든 나머지 직접 연산의 계약 판정을 추정하지 않았다.
따라서 최소 ADD 수정으로 전체 resource accounting이 자동 PASS라는 결론은 없다.

## 보존

시작 target의 기존 tracked 2409개 중 2408개 raw SHA 불변, 변경 1개 rounding.py, 삭제 0개다.
기존 specs/docs/audit/current 559개는 모두 byte-identical이다.
ATTEMPT-REASON-NULL 승인 spec과 과거 audit evidence도 그대로다.
Arithmetic 보호 8개는 target 및 `65d8fd29ae255529afead70289098d36b825b3b4`와 raw byte-identical이다.
Source 18개 중 rounding 외 17개도 unchanged다.
[보존 receipt](../current/c1b1-round-add-fix-2026-10-05/preservation.json)를 남겼다.

추가된 파일은 새 회귀/fixture, 새 audit helpers, 새 증거와 후속 보고서다.
기존 역사 문서, 승인 계약 또는 audit FAIL을 사후 PASS로 수정하지 않았다.

## 알려진 제한 및 재감사 범위

Adapter의 `n_R(t)=ceil(4*rate*r_guard+1)*2**t` 독립 schedule reconstruction은 여전히 OPEN이다.
PREPARED_ONLY, invoke blocked, runtime_activation_allowed=false를 유지한다.
Production policy instance, allocator majorant 검증, isolated hard CPU/wall/memory worker,
pinned V2 whole-call preflight/numerical acceptance, authenticated acquisition/executor integration은
이번 작업에서 구현하거나 승인하지 않았다. J_NOT_VERIFIED / NotCertified 유지.

읽기 범위: 사용자 요청과 제공 감사 보고서 전체, 제공 JSON 3개 전체, impulse source 18개 전체,
관련 runtime/rounding/resource/producer 및 mutant helpers와 author report를 읽었다.
Finite-policy machine 계약을 확인했고 오래된 design/conditions는 관련 부분만 참조했다.
모든 spec JSON bytes는 static checker/보존 검사로 확인한 것이며 모든 human design 문서를
이번에 처음부터 끝까지 다시 읽었다고 주장하지 않는다. 과거 감사 로그 열람과 위 새 실행을 구분한다.

독립 재감사는 수정된 두 증가 경로의 연산 전 거부, scalar/whole-call boundary, 계정 ledger 경로,
새 OPEN finding 및 잔여 resource 의무를 별도로 확인해야 한다.
이번 결과만으로 독립 승인, J_VERIFIED, physical/trajectory PASS 또는 certification을 발급하지 않는다.

최종 [작성자 receipt 및 evidence 목록](../current/c1b1-round-add-fix-2026-10-05/receipt.json).
사용자 추가 승인 없이 commit/push하지 않았다.
