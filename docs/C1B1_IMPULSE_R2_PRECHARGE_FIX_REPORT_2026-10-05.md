# C1-B1 Independent Impulse V1 — R² precharge 최소 수정 결과

2026-10-05. **F-RESOURCE-R2-PRECHARGE의 최소 수정과 author 회귀 검증을 완료했다.
전역 resource accounting은 여전히 NOT PASS이며, 새 R² 후보의 독립 재감사는 PENDING이다.**
Runtime, V2 numerical recheck, J verification 및 certification은 승인하지 않았다.
수정·증거 보고 단계이며 commit/push하지 않았다.

## 실제 기준과 새 감사 수령

현재 HEAD는 `baba8ea942b896af64ceaa7ab41e2bc5db73112c`, 직접 parent는
`6a63798adbae7c119439683b356f19ff414ac239`다. Branch는
`codex/c1b1-fclaim1-output-limit`이며 최초 확인 때 clean이었다.
이 작업 시작 이전에 이미 존재한 baba commit을 이번 작업자가 생성했다고 주장하지 않는다.
과거 receipt의 당시 미커밋 상태와 현재 HEAD를 구분하며 원격 push 여부는 이번에 조회하지 않았다.

지정된 Downloads 경로의 파일은 존재하지 않았고 실제 수령 자료는
`D:/감사/REPORT_KO(8)`에서 찾았다. AUDIT_REPORT_KO.md, NEXT_STEP_KO.md 및
두 pretty JSON 전체와 붙여넣은 요청 전체를 읽어 원본 bytes로 복사했다.
[수령 감사 보고서](../current/c1b1-qdiv-limited-reaudit-received-2026-10-05/received/AUDIT_REPORT_KO.md),
[source/Git/수령 identity](../current/c1b1-qdiv-limited-reaudit-received-2026-10-05/received-identity.json)를 남겼다.
원 감사 ZIP, probe source, canonical JSON 및 manifest는 이 네 파일과 함께 제공되지 않았다.
Pretty JSON을 원 실행 canonical JSON bytes 또는 완전한 감사 ZIP으로 대체해 부르지 않는다.

수령 감사는 baba의 18-source bundle
`e4ae7a0491c94a8a56a7029d08b70d7afd0c422ce0057a9027111bc45541d507`에 고정돼 있고
실제 source와 일치한다. ROUND-ADD 및 QDIV-SIGN finding은 해당 제한 재감사 PASS다.
O-R2-TRUTH-PATH는 F-RESOURCE-R2-PRECHARGE CONFIRMED FAIL로 구체화됐다.
역사적 d547 independent FAIL 및 6a 당시 QDIV OPEN은 소급 수정하지 않았다.

독립 경계 검사의 8704/8128회 및 감사자의 두 omission variant는 수령 로그의 실행 결과다.
이번 작성자가 그 독립 probe를 다시 실행한 것으로 표기하지 않는다.
수령 감사는 작성자의 과거 full1126 및 18-mutant 전체를 독립 재실행한 것이 아니라고 명시했다.
이번의 새 author 전체 실행은 아래에 별도로 기록한다.

NEXT_STEP 문서를 자동 구현 승인으로 취급하지 않았다. 작업 범위를 확인한 뒤 사용자가 채팅에서
R² 최소 수정·W3·요청 회귀를 명시적으로 승인했다. [승인 범위 기록](../current/c1b1-r2-precharge-fix-2026-10-05/AUTHORIZED_SCOPE_KO.md).

## 최소 소스 수정

Production 변경은 `producer.py:evaluate_reference()`의 R² compute 한 경로다.

```python
r2=c.fraction(0,1)
for x in parsed.q:
    r2=c.qadd(r2,c.qmul(x,x))
```

기존 x,y,z 순서와 `0+x²+y²+z²`의 exact 합산 순서를 유지한다.
초기 accumulator도 선언된 normalization 비용을 사전 청구한다.
각 qmul/qadd 내부의 미약분 integer 연산 및 normalization은 기존 wrapper가 사전 검사한다.
R² 값을 먼저 구한 뒤 비용을 한 번 더하는 사후 일괄 청구를 쓰지 않았다.
새 비용식이나 Fraction CPU instruction model을 도입하지 않았다.

ResourceAccount, rounding.py, sqrt, exp, potential, derivative, interval, domain,
attempt/digest, wire, certificate 및 adapter source는 target과 raw byte-identical이다.
물리식 R²=x²+y²+z²는 그대로다.

| source identity | SHA-256 |
|---|---|
| producer.py before | `54d3d94f1d8b77824ffa9d5acd6b4bd27ac0f93fd31491d34b8cb0508c0825e9` |
| producer.py after | `ba229aa50994c8409def1ca2f74c37df9dd33f563c0920719263c81e54d2b184` |
| preserved resource.py | `c5e081ee2c3dc49db85271d588cc3fde6e54caa6ce6e005a36c00c25d167a7cd` |
| preserved rounding.py | `3667079195517f84f23a37a6f0787123b16571be2f6975967b0f2a9e127b2bf9` |
| new 18-source bundle | `4bd5cb0ef00c022689aa1a1dd4354deba08961ab4e1887b38d2f62f287a8cced` |

Bundle 정의는 sorted basename→raw SHA의 compact ASCII JSON+terminal LF SHA다.
[producer old/new diff](../current/c1b1-r2-precharge-fix-2026-10-05/producer.diff) 및
[18-source identity](../current/c1b1-r2-precharge-fix-2026-10-05/source-identity.json)를 남겼다.
이는 working source bundle이며 새 Git commit SHA가 아니다.

## 실제 사전 거부 반례와 RED/GREEN

Canonical q=(5,3,-2)를 바꾸지 않았다. 수정 전 작성자 probe에서도 Fraction multiply/add가
각각 3회 실행되고 첫 sqrt entry의 R²=38, work=0, operations=0을 재현했다.
이후 WORK refusal이어도 앞선 산술의 사전 청구 의무가 충족되지는 않는다.

먼저 R² 회귀 8개를 실행해 **8 failed / error0 / skip0**를 보존했다.
실제 integer-product line 추적을 보강한 RED도 8 failed였다.
최소 수정 뒤 최초 GREEN은 8 passed였고, W3 회귀 추가 후 최종 targeted suite는 42 passed다.
[RED](../current/c1b1-r2-precharge-fix-2026-10-05/r2-preoperation-red.txt)와 JUnit XML,
최초 RED/GREEN 및 당시 테스트 source snapshot을 보존했다.

| cap | 마지막 시도 | refusal 직전 ledger | 실제 integer-product 실행 |
|---:|---|---:|---|
| 1, 31 | 초기 fraction(0,1)의 cost32 | 0 / operations0 | 없음; sqrt 진입 없음 |
| 32, 47 | 첫 numerator 5×5의 cost16 | 32 / operations1 | 5×5 실행 없음; sqrt 진입 없음 |
| 48 | denominator 1×1의 cost4 | 48 / operations2 | 허용된 5×5만 work48에서 실행; 다음 곱셈 없음 |

모든 낮은 cap에서 COMPUTE / RESOURCE_CAP / WORK와 no raw/opposite/certificate/account를 확인했다.
Profile hook은 실제 account return부터 첫 sqrt entry까지 관측하며,
line hook은 ResourceAccount.multiply의 실제 product 줄 도달 여부와 당시 ledger를 확인한다.
Production 함수를 대신 계산하는 stub을 사용하지 않았고 hook은 finally에서 복구했다.

## 실제 피연산자 비용 재구성과 W3

사용자의 16717/25 손계산은 예상치로 다루고 구현의 고정 정답으로 먼저 넣지 않았다.
승인 비용식을 별도로 구현해 **실제 pre() 호출자의 integer operand bit length**로 매 호출의
bits/work를 재계산한 뒤 pre 인자 및 ledger 증분과 대조했다.
[실제 operand/25 R² precharge/전체 재구성](../current/c1b1-r2-precharge-fix-2026-10-05/actual-work-reconstruction.json)에 있다.

| canonical R² 구간 | qmul work | qadd work | subtotal |
|---|---:|---:|---:|
| 초기 c.fraction(0,1) | — | — | 32 |
| x=5, 0+25 | 2612 | 2616 | 5228 |
| x=3, 25+9 | 1263 | 4834 | 6097 |
| x=-2, 34+4 | 525 | 4835 | 5360 |
| 실제 합계 | | | **16717** |

R² primitive는 multiply15 / add3 / fraction7 =25회다.
전체 성공 precharge 36851회의 별도 비용식 합계가 PrivateResult ledger와 정확히 일치했다.
기존 경로 비용 차이도 R²의 추가 비용과 일치했다.

```text
historical W2 = 2605253326092204528
new observed W3 = 2605253326092221245
W3 - W2 = 16717
whole-call operations = 36851 = 36826 + 25
```

| canonical work cap | 실제 결과 |
|---|---|
| W, W+152, historical W2 | PUBLICATION / RESOURCE_CAP / WORK; producer RESOLVED; no raw/opposite/certificate |
| W3−1 = 2605253326092221244 | 동일한 no-output WORK refusal |
| W3 = 2605253326092221245 | 기존 raw 반환, work W3 / operations36851, private candidate 구성 |

W3에서의 상태도 NOT_PUBLISHED / STOP이며 rechecker/adapter는 실행하지 않았다.
Public produce()는 POLICY_UNBOUND를 유지한다.
**W3는 현재 author wrapper ledger의 관측 경계다. Fully-accounted global work나
production-approved budget이 아니다.**
[W3 기록](../current/c1b1-r2-precharge-fix-2026-10-05/W3.json).

활성 회귀의 W2 성공 기대만 새 수정 후 WORK refusal로 바꾸었다.
W/W+152/W2의 과거 JSON·보고서·receipt·mutant 자료는 그대로 보존했다.
W3 literal 회귀는 실제 측정과 exact equality 확인 뒤 추가했다.

## 충분한 같은 입력의 exact 수학 결과

각 입력의 encoded bytes와 충분한 author budget을 수정 전후 동일하게 유지했다.
Budget과 ReferencePolicy를 함께 구성하여 binding mismatch를 resource refusal로 세지 않았다.

| admitted input q | exact R² | R² work / operations after |
|---|---|---:|
| (5,3,-2), 원 반례 | 38 | 16717 / 25 |
| (11/2,-3/2,0), noninteger dyadic + 0축 | 65/2 | 55376 / 25 |
| (0,-6,2), 부호 + 첫 0축 | 40 | 15121 / 25 |

세 입력 모두 실제 prepared()의 domain reason=None을 확인했고 FX48로 정확히 표현된다.
각 input payload, hash 및 domain 결과를
[before](../current/c1b1-r2-precharge-fix-2026-10-05/before-boundaries.json) /
[after](../current/c1b1-r2-precharge-fix-2026-10-05/after-boundaries.json)에 보존했다.
R², radius, V, V′, J exact endpoint의 reduced n/d, local exp orders 및 raw가 모두 같았다.
V/V′ 등의 diagnostic은 별도 ledger이며 whole-call W3에 더하지 않았다.
Certificate의 source identity/budget binding은 바뀌므로 전체 certificate byte equality는 주장하지 않는다.

Canonical raw는 기존 값과 같다.

```text
(52119986341579705480988,
 31271991804947823288593,
 -20847994536631882192395)
```

이는 author before/after 결과 보존이며 잠재 수학 전체의 새 독립 oracle 승인이 아니다.

## 새로 실행한 검증과 semantic mutants

Windows CPython 3.12.7. 각 최종 명령의 실제 exit/stdout/stderr/JUnit 및
18-source before/after map은 새 evidence 경로에 저장했다. 모두 source unchanged다.

| 새 author 실행 | 결과 |
|---|---|
| targeted R² / QDIV / ROUND-ADD / resource | 42 passed in 6.12s, exit0 |
| Impulse-related regression | 743 passed in 9.80s, exit0 |
| frozen spec regression | 46 passed in 0.80s, exit0 |
| full repository pytest | 1136 passed in 55.79s, exit0; failure/error/skip0 |
| semantic source mutants | 기존18 + R²1 =19 baseline PASS / 19 DETECTED; runner exit0 |
| static spec | 155 PASS, exit0 |
| git diff --check | exit0 |

새 R2-PRECHARGE-ACCOUNTING mutant는 위 3줄을 직접 `sum(x*x ...)`로 되돌린다.
Cap1/31/32/47/48의 실제 corridor에서 baseline은 허용되지 않은 연산 전에 멈추고,
mutant는 미청구 Fraction 산술과 sqrt entry를 관측하게 하므로 다섯 assertion failure로 검출된다.
기존 18개의 edit/fixture도 유지하여 격리된 실제 source edit로 모두 다시 실행했다.
Hash 차이만으로 DETECTED를 세지 않았다.
[19-mutant 결과와 각 source/XML/log](../current/c1b1-r2-precharge-fix-2026-10-05/mutants/results.json)를 남겼다.
검증 수치들은 독립 proof 개수로 합산하지 않는다.

## 보존과 줄바꿈 구분

Target tracked 2734개에서 변경은 producer.py 및 활성 ROUND-ADD whole-call 회귀 두 개,
삭제0개다. 나머지 2732개는 이번 baseline의 working raw bytes와 동일하다.
기존 specs/docs/audit/current 881개 모두 이번 baseline 대비 working raw bytes를 보존했다.
승인 spec과 ResourceAccount/rounding.py 및 Impulse source17개는 unchanged다.
[보존 기록](../current/c1b1-r2-precharge-fix-2026-10-05/preservation.json).

수령 단계에서 기존 receipt166개 hash/size를 새로 대조했다.
이번 승인 범위에서 활성 ROUND-ADD test를 W2 거부로 바꾼 뒤에는 그 한 경로의 현재 bytes가
옛 receipt와 달라진다. 최종 수집은 나머지165개 current 파일과
[옛 test의 exact baba Git bytes](../current/c1b1-r2-precharge-fix-2026-10-05/round-add-test-target.py)를 각각 대조한다.
이 test snapshot의 SHA는 옛 receipt 및 이번 working baseline SHA와 정확히 같다.
옛 receipt를 새 test hash로 재작성하지 않았다.
6a→baba의 기존 역사 파일718개 Git blob identity와 Arithmetic 보호8개의
6a/65d8 양쪽 Git blob 대비 raw byte equality도 실제 확인했다.

수령 감사의 **78개 줄바꿈 차이는 working files 대 과거 6a Git blob 비교**다.
이번 시작 시점 working files 대 현재 baba Git blob의 전수 비교에서는 **160개 EOL-only 차이**였다.
비줄바꿈 차이는 0이었고 Git 상태는 clean이었다. 대상·시점이 다른 수치를 섞지 않는다.
줄바꿈을 정규화해 raw identity라고 부르거나 증거 파일을 정규화해 덮어쓰지 않았다.
새 source snapshot도 원본 raw bytes로 보존했다.

## 여전히 OPEN / 미승인

[Accounting 경로 제한 갱신 표](../current/c1b1-r2-precharge-fix-2026-10-05/RESOURCE_ACCOUNTING_UPDATE_KO.md)를 작성했다.
O-CONTROL-PARAMETERS, O-DIRECT-FRACTION-CONSTRUCTION 전체 및
O-ALLOCATION-AND-WORKER를 자동 종결하지 않았다.
초기 accumulator construction을 청구했다는 사실만으로 다른 direct Fraction construction의
배정 문제를 해결했다고 주장하지 않는다.
Domain admission이나 모든 작은 integer/control syntax를 이번 범위에서 재설계·면제하지 않았다.

기존 adapter `n_R(t)=ceil(4*rate*r_guard+1)*2**t` 독립 재구성은 OPEN이다.
PREPARED_ONLY / invoke blocked / V2 numerical recheck NOT APPROVED를 유지한다.
Allocator footprint는 AUTHOR_FIXTURE_MODEL_UNVALIDATED이며 RSS/검증 majorant가 아니다.

```text
received ROUND-ADD / QDIV-SIGN limited reaudit on baba: PASS
new R2 candidate: FIX APPLIED / AUTHOR REGRESSION PASS / INDEPENDENT REAUDIT PENDING
GLOBAL RESOURCE ACCOUNTING: NOT PASS
reference_producer_implementation: NOT YET INDEPENDENTLY APPROVED
runtime_activation_allowed = false
J_NOT_VERIFIED
NotCertified
```

두 선행 finding의 독립 PASS를 새 bundle 전체 승인으로 자동 옮기지 않는다.
현재 [우선 상태 기록](../current/C1B1_IMPULSE_RESOURCE_ACCOUNTING_STATUS_2026-10-05.md)과
[최종 author receipt](../current/c1b1-r2-precharge-fix-2026-10-05/receipt.json)를 함께 읽는다.

읽기 범위는 수령 네 파일·붙여넣은 요청 전체, 사용자의 추가 채팅 승인 전체,
승인 finite-policy JSON/B5 전체와 producer/resource/domain/policy/sqrt 및 관련 회귀·mutant source다.
나머지 기존 수학 source17개는 변경 보존 SHA와 새 회귀로 확인했고 새 전체 독립 감사로 읽지 않는다.
기존 과거 보고서를 수정하거나 새 independent PASS/production instance를 발급하지 않았다.
최종 HEAD는 baba 그대로이며 commit/push하지 않았다.

## 수집 helper의 초기 중단 기록

최초 receipt collector는 옛 receipt의 모든 경로를 현재 파일과 그대로 비교하여 exit1로 중단했다.
원인은 위에서 승인 범위로 변경한 활성 test 한 개였다. 나머지165개는 그대로였고,
옛 test는 정확한 target Git bytes와 baseline/receipt SHA 대조로 보존했다.
[초기 helper 실패 기록](../current/c1b1-r2-precharge-fix-2026-10-05/receipt-first-helper-failure.json)을 남겼다.
Helper 검증을 수정했으며 production source나 옛 receipt를 고치지 않았다.

두 번째 수집은 한국어 상태 파일의 남은 일본어 링크 label 두 개를 언어 검사에서 감지하여
exit1로 중단했다. 진단 print는 cp949 stdout의 UnicodeEncodeError로 끝났고,
PowerShell로 파일을 읽어 label을 한국어로 수정했다.
[두 번째 helper 실패 기록](../current/c1b1-r2-precharge-fix-2026-10-05/receipt-second-helper-failure.json)을 보존했다.
이는 문서 검증 문제이며 production 수학 source는 변경하지 않았다.
