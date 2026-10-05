# C1-B1 Impulse — QDIV-SIGN / ROUND-ADD 독립 제한 재감사

**감사일: 2026-10-05 (한국시간)**  
**판정: 두 수정의 제한 재감사 PASS. R² 사전청구 누락 FAIL. 전역 resource accounting NOT PASS.**

이 문서는 제출된 작성자 보고서의 PASS를 옮긴 문서가 아니다. 연결된 Windows 저장소를 직접 읽고, 별도로 작성한 검사 코드로 경계값·비용·실행 경로를 재현한 결과다. 구현 코드와 Git 기록은 수정하지 않았다. 이 감사의 판정은 아래에 고정한 소스에만 적용한다.

## 1. 판정 범위와 상태

| 항목 | 이번 독립 판정 | 범위 |
|---|---|---|
| F-RESOURCE-ROUND-ADD | **PASS — 해당 finding 종결** | accounted increment 유지, 경계 및 역사적 누락 변형 검출 |
| F-RESOURCE-QDIV-SIGN | **PASS — 해당 finding 종결** | sign 곱셈의 precharge, 결과 보존, 경계 및 역사적 누락 변형 검출 |
| 작성자의 O-R2-TRUTH-PATH | **확정 FAIL로 구체화** | F-RESOURCE-R2-PRECHARGE / OPEN |
| 전역 resource accounting | **NOT PASS** | 적어도 하나의 실제 계약 위반이 남음 |
| Control/parameter 비용 배정 | OPEN / UNRESOLVED | 직접 문법만으로 일괄 FAIL 또는 면제하지 않음 |
| 직접 Fraction construction 범위 | OPEN / UNRESOLVED | 추상 normalization 의무와 생성 경계의 연결 필요 |
| Allocator majorant / hard worker / active instance | 미승인 | 이번 수학적 비용 검증과 별도 |
| Reference producer 구현 전체 | NOT YET INDEPENDENTLY APPROVED | 두 finding의 종결은 전체 구현 승인이 아님 |
| Adapter / V2 | PREPARED_ONLY / invoke blocked / 재검사 미승인 | 승인 상태를 변경하지 않음 |
| Runtime / J / certification | false / J_NOT_VERIFIED / NotCertified | 활성화·물리·궤적·인증을 승인하지 않음 |

역사적 `d5475e2`의 독립 구현 감사 FAIL과 `6a63798`의 당시 QDIV OPEN은 보존한다. 현재 후보에서 수정 finding을 종결한다고 과거 판정을 소급 변경하지 않는다. 저장소의 상태 파일도 이 감사에서 편집하지 않았다.

## 2. 실제 감사 대상과 제출 보고서의 Git 상태 차이

제출 메시지는 HEAD가 `6a63798...`이며 미커밋이라고 설명했다. 실제 읽은 로컬 상태는 다음과 같다.

```text
repository: D:\numerical-audit-lab-recovered-2026-10-01
branch: codex/c1b1-fclaim1-output-limit
HEAD: baba8ea942b896af64ceaa7ab41e2bc5db73112c
parent: 6a63798adbae7c119439683b356f19ff414ac239
commit author/committer time: 2026-10-05T13:33:07+09:00
subject: Account for signed division multiplications
working tree: clean
```

작성자 receipt의 기록 시각은 04:31:25 UTC이고 위 커밋 시각은 04:33:07 UTC다. 현재 상태와 receipt 작성 시점의 상태를 구분해야 한다. 누가 커밋을 승인했는지 또는 원격에 push했는지는 이번 검사로 판정하지 않는다. **이번 감사에서는 commit/push하지 않았다.**

소스는 제출 후보와 일치한다. 따라서 이 재감사는 `6a` 자체를 승인하는 것이 아니라, 아래 source bundle을 가진 `baba8ea` 후보에 대한 판정이다.

| 고정 대상 | SHA-256 |
|---|---|
| Impulse 18-source bundle | `e4ae7a0491c94a8a56a7029d08b70d7afd0c422ce0057a9027111bc45541d507` |
| resource.py | `c5e081ee2c3dc49db85271d588cc3fde6e54caa6ce6e005a36c00c25d167a7cd` |
| rounding.py | `3667079195517f84f23a37a6f0787123b16571be2f6975967b0f2a9e127b2bf9` |
| finite-policy.json | `7e2db07cb87bb0d81981c707949c1cd9fc129c01b645eb7a2447923360b9ab2e` |
| canonical-input.json | `bab9520968c7e3b5be3e6d5c5e53627a06d066bbb950579c7cc8ec2b65dcfffd` |

Bundle은 basename→파일 raw SHA-256 사전을 키 정렬·compact ASCII JSON·terminal LF로 직렬화한 뒤 해시한 것이다. 감사 시작과 종료의 HEAD, clean 상태, bundle이 같았다. 근거: `core_results.json`의 `identity_before/after`, `provenance_results.json`의 `source_identity`.

## 3. 독립성 및 실행 방식

실행 환경은 연결된 사용자 Windows의 CPython 3.12.7이다. 검사 스크립트는 Python REPL 메모리로 전달했고, 저장소 파일을 생성하거나 수정하지 않았다. `-B` 및 `sys.dont_write_bytecode=True`를 사용했다.

검사 대상 구현은 system under test로 import했다. 기대값은 구현의 비용 함수를 호출해서 얻지 않고, 승인된 work schedule을 별도 정수식으로 계산했다. QDIV의 수학적 답은 별도의 exact Fraction 나눗셈으로, rounding의 답은 floor/remainder와 tie-even 조건으로 계산했다. 실행 경로에서는 `sys.setprofile`로 precharge의 caller 피연산자를 읽어 별도의 비용식으로 다시 계산하고 ledger 증분과 비교했다.

QDIV와 ROUND-ADD의 역사적 누락 변형은 Git에 보존된 함수만 AST로 추출해 메모리에 로드했다. 소스 파일은 되돌리거나 덮어쓰지 않았다. QDIV before/after 비교에서 임시로 바꾼 Python 클래스 메서드는 `finally`로 복구했다. Profile/trace hook도 복구했다.

이번 검사 소스와 실제 구조화 실행 로그를 함께 제공한다. 테스트 개수와 추적 건수는 서로 다른 독립 증명의 개수로 합산하지 않는다. 유리수 표기가 정규화되므로 반복 입력이 존재한다.

## 4. F-RESOURCE-QDIV-SIGN — PASS

`resource.py:131`은 다음 경로를 사용한다.

```python
numerator = self.multiply(numerator, sign)
```

`multiply()`의 79행 `pre()`가 80행의 실제 `a * b`보다 먼저 실행된다.

정규화된 유리수 a, b(b≠0)에 대해 N=a.numerator×b.denominator, s=sign(b.numerator), D=a.denominator×abs(b.numerator)>0라 하면, 이전 수학적 값은 Fraction(N×s,D)이고 새 경로도 동일하다. 차이는 N×s를 실행하기 전에 resource check와 비용을 청구한다는 점이다. 충분한 cap에서 결과를 바꾸지 않고, 부족한 cap에서는 더 일찍 거부하도록 만든 수정이다.

`qdiv(1, ±1)`의 비용을 별도로 유도하면 세 multiply가 각각 4, normalization이 32이므로 총 44다.

| 입력 | cap | 독립 실행 결과 | work / operations |
|---|---:|---|---:|
| 1 / ±1 | 4 | WORK refusal | 4 / 1 |
| 1 / ±1 | 40, 43 | WORK refusal | 12 / 3 |
| 1 / ±1 | 44 | ±1 | 44 / 4 |

cap=4에서 별도 line trace도 실행했다. 첫 multiply만 실제 정수 곱셈 줄에 도달했고, 두 번째 sign multiply는 진입 후 WORK 예외를 냈다. 두 번째 실제 곱셈 줄에는 도달하지 않았다. 따라서 사후 청구가 아니라 사전 거부다.

추가로 작은 signed rational 입력군의 계산된 비용−1/비용 경계 **8,704회**를 검증했다. 원래 QDIV 누락 함수를 메모리에서 실행하면 cap40/43에서 ±1로 잘못 성공하여, 현재 후보와 구별된다. 네 구별 사례는 하나의 QDIV semantic defect variant에 대한 증거다.

근거: `core_results.json`의 `qdiv_scalar`, `qdiv_boundary_executions`, `mutants.qdiv`; `provenance_results.json`의 `qdiv_cap4_preoperation_trace`.

## 5. F-RESOURCE-ROUND-ADD — PASS 유지

`rounding.py:18–19`의 increment는 account가 있을 때 `c.add(value,1)`로 연결된다. 해당 파일은 제출 후보와 같은 해시다.

| 입력 | cap | 독립 실행 결과 | work / operations |
|---|---:|---|---:|
| 7/4 | 73, 74 | WORK refusal | 73 / 2 |
| 7/4 | 75 | 2 | 75 / 3 |
| −5/2 | 42, 44 | WORK refusal | 42 / 2 |
| −5/2 | 45 | −2 | 45 / 3 |

별도 signed rational rounding 경계 검증 **8,128회**가 기대 결과와 일치했다. `d5475e2`의 역사적 함수는 위 부족 cap 네 경우에서 값을 반환하여 누락이 검출됐다. 이는 QDIV와 별개의 두 번째 semantic defect variant다.

본 PASS는 ROUND-ADD finding에 한정된다. nearest-even 함수의 모든 직접 비교·parity 표현까지 전역 accounting closure를 새로 승인한 것이 아니다.

## 6. Whole-call W2와 exact 결과 보존

Canonical q=(5,3,−2)를 사용했다. 각 cap에 맞춰 input budget과 ReferencePolicy를 함께 구성하여 binding mismatch로 얻은 가짜 refusal이 아니도록 했다.

성공 경로의 각 `pre()` caller 피연산자로부터 비용을 다시 계산한 결과:

```text
independently reconstructed wrapper work = 2605253326092204528
successful primitive precharges = 36826
QDIV sign multiply calls = 1590
QDIV sign multiply work = 5314390
```

| Primitive | 성공 precharge 수 |
|---|---:|
| shift | 79 |
| divmod | 129 |
| isqrt | 1 |
| multiply | 24056 |
| fraction | 6804 |
| add | 1683 |
| compare | 4074 |

이 합계는 ledger 내부의 정확성을 검증하지만, wrapper 밖의 연산이 없다는 증명이 아니다.

| cap | 독립 결과 |
|---|---|
| W = 2605253326086889986 | RESOURCE_CAP / WORK, raw·opposite·certificate 없음 |
| W+152 = 2605253326086890138 | RESOURCE_CAP / WORK, raw·opposite·certificate 없음 |
| W2−1 = 2605253326092204527 | RESOURCE_CAP / WORK, raw·opposite·certificate 없음 |
| W2 = 2605253326092204528 | 기존 raw 및 private candidate 구성, work=W2, operations=36826 |

세 refusal의 phase는 PUBLICATION이고 producer는 RESOLVED였다. 이는 수치 결과가 내부적으로 결정됐어도 반환할 raw/opposite/certificate를 내보내지 않았다는 뜻이다. W2에서의 private 성공도 `NOT_PUBLISHED / STOP`이며 rechecker는 실행되지 않았다.

수정 전후 같은 충분한 cap(10^24)의 입력으로 얻은 radius, V, V′, J의 exact endpoints, local exp orders 및 raw가 같았다. V diagnostic 계산은 별도 account를 사용하여 W2에 섞지 않았다.

```text
raw = (
  52119986341579705480988,
  31271991804947823288593,
 -20847994536631882192395
)
```

Old qdiv를 사용한 비교 실행의 work는 2605253326086890138이고 차이는 정확히 5314390이었다. 이 before/after는 변경의 수학 결과 보존 검사이지, potential/interval 수학 전체에 대한 새로운 독립 oracle 증명은 아니다. 전체 certificate byte equality 또는 역사적 source identity를 가진 certificate 재현도 주장하지 않는다.

근거: `core_results.json`의 `primitive_replay`, `before_after`, `whole_boundaries`.

## 7. F-RESOURCE-R2-PRECHARGE — 확정 FAIL / OPEN

작성자 closure 표가 남긴 O-R2-TRUTH-PATH를 직접 검증했다. 대상은 `producer.py:109`다.

```python
c = policy.account()
r2 = sum((x*x for x in parsed.q), Q(0))
```

### 정확한 반례

제출된 canonical input의 q=(5,3,−2)를 유지하고, budget과 ReferencePolicy 양쪽의 work cap만 1로 바꿨다. account가 생성된 뒤 첫 sqrt 진입까지 관측한 결과:

```text
Fraction multiply:   5 × 5
Fraction add:        0 + 25
Fraction multiply:   3 × 3
Fraction add:       25 + 9
Fraction multiply:  −2 × −2
Fraction add:       34 + 4

sqrt entry:
  r2 = 38
  work = 0
  operations = 0
  work_max = 1
```

이어 sqrt의 첫 charged operation에서 WORK refusal이 발생했다. 반환 raw/opposite/certificate는 없었다. **그러나 뒤에서 정상 거부했다고 앞서 실행한 미청구 연산이 사전 청구된 것은 아니다.**

### 계약 위반의 근거

고정한 finite-policy의 rational 항목은 uncancelled cross-products, comparisons, gcd, normalizations를 모두 청구하도록 요구한다. preallocation 항목은 cross-product/gcd 등 이전의 검사 및 cap failure 시 연산을 시도하지 않는 동작을 요구한다.

이 R² 경로는 입력 검증 이전이 아니라 `evaluate_reference()` 내부 account 생성 이후의 실제 산술이다. 적어도 첫 5×5만 보아도 두 operand의 bit length는 각각 3이므로 multiply work=(3+1)(3+1)=16이며 cap1보다 크다. 그 연산을 포함한 세 rational multiplication과 세 addition이 ledger0인 채 완료됐다. `Fixed signed96/FX48 input bound` 주석은 비용 면제 근거가 아니다.

따라서 단순한 `%`, `abs()` 또는 loop syntax에 대한 추정이 아니라, **승인 비용 의무 + 실제 truth path + 사전 청구 부재**가 함께 확인된 finding이다. Fraction 내부 CPU instruction을 새 work unit으로 세는 판정도 아니다.

영향은 work/pre-operation accounting 계약 위반이다. 이 반례에서 잘못된 raw가 발행됐거나 물리 수식이 틀렸다고 주장하지 않는다. 현재 public `produce()`는 POLICY_UNBOUND로 막혀 있다.

결론: 두 이전 finding을 종결해도 전역 resource accounting은 여전히 NOT PASS다. W2를 global fully-accounted work 또는 production-approved budget으로 승격할 수 없다.

근거: `core_results.json`의 `r2_bypass`, `public_blocked`; `provenance_results.json`의 `finite_policy`, `source_locations`.

## 8. 제출 evidence와 보존 확인

작성자 receipt에 나열된 **166개 파일의 SHA-256과 크기를 전부 다시 계산**하여 일치함을 확인했다. 한국어 보고서 raw SHA도 일치했고, 보고서의 상대 링크 14개는 모두 존재했다. 파일이 존재하고 해시가 일치하는 것과 해당 테스트의 내용을 새로 실행한 것은 구분한다.

Git `6a → baba` 비교에서 기존 tracked 2,570개 중 바뀐 파일은 resource.py와 활성 ROUND-ADD 회귀 파일 2개뿐이다. 나머지 2,568개의 Git blob identity 및 기존 specs/docs/audit/current 718개의 Git blob identity가 보존됐다. Arithmetic 보호 8개는 작업 파일 raw bytes가 `6a`와 `65d8fd29ae255529afead70289098d36b825b3b4` 양쪽 Git blob bytes와 같았다.

**줄바꿈 주의:** 현재 작업 파일과 과거 `6a` Git blob의 raw bytes를 바로 비교하면 추가 78개가 다르다. 전수 대조 결과 모두 CRLF/LF 차이만 있고, 그 외 내용 차이는 위 두 수정 파일뿐이었다. 따라서 “과거 718개 Git 객체 보존”과 “Windows 작업 파일이 모든 과거 Git blob bytes와 동일”은 같은 주장이 아니다. 후자는 이번 관측으로 성립하지 않는다. 줄바꿈을 정규화해놓고 raw-byte identity라고 부르지 않는다.

`git diff --check`는 exit0이었고 감사 종료 작업 트리는 clean이다. 이 과정에서 파일의 줄바꿈을 변경하지 않았다.

## 9. 이번에 실행한 것과 실행하지 않은 것

새로 실행한 것은 위 scalar oracle boundary 검증, QDIV/ROUND-ADD 두 역사적 semantic variant, canonical before/after 및 work boundary, primitive 비용 재구성, R² trace, public POLICY_UNBOUND 확인, receipt/source/Git 보존 검사다.

작성자가 보고한 전체 pytest 1126, Impulse733, spec46, targeted32, 18-mutant 전체 및 static155를 **이번 독립 실행 횟수로 재표기하지 않는다.** 관련 파일의 hash/size는 확인했지만 이 전체 suite를 이 재감사에서 다시 실행하지 않았다. 나머지 16개 semantic mutants도 이번에 독립 재실행한 것으로 세지 않는다.

I1–I14/I17–I23, V2, adapter order 독립 reconstruction, allocator platform majorant, OS hard worker, all-input liveness, 물리 정확도 및 trajectory는 이번 감사에서 새로 승인하지 않았다.

## 10. 감사 helper 중단 기록

이 감사에도 두 초기 중단이 있었다. 숨기지 않고 `helper_failures.json`에 구분해 기록했다.

첫 번째는 compressed source 전달의 zlib decoding 오류로, 전달 스크립트 자체가 실행되기 전에 끝났다. 두 번째 `independent_probe.py` 초기판은 source pin 및 receipt 검증 뒤, Windows working bytes와 Git blob bytes가 동일할 것이라는 잘못된 보존 검사 가정 때문에 assertion으로 종료됐다. 이는 위 CRLF/LF 차이였다. 이 초기 실행은 scalar 검증까지 진행하지 않았다.

원인을 전수 확인한 뒤 provenance 검사와 core 수학 검사를 분리했다. 최종 `core_probe.py`와 `provenance_probe.py`는 실제 실행하여 모든 assertion을 완료했고, 전달된 JSON은 해당 실행에서 나온 bytes를 checksum 대조하여 보존했다. 초기 실패 소스는 `helpers/initial_failed_probe.py`로 포함한다. 이를 통과한 검사 소스라고 부르지 않는다.

## 11. 다음 작업의 경계

다음은 R² 비용 누락을 accounted rational operation 경로로 연결하고, 정확한 R²·후속 enclosure·raw를 유지하는 최소 수정이다. 사후 lump-sum 청구로 바꾸면 사전 검사 의무를 해결하지 못한다. 새 비용은 다시 측정하여 W3로 기록하고 W3−1/W3 경계를 검증해야 한다. W2를 새 성공 고정값으로 유지하거나 과거 evidence를 덮어쓰지 않는다.

R²를 고친 뒤에도 control/parameter 및 Fraction construction의 모델 배정을 완료하기 전에는 전역 closure PASS를 부여하지 않는다. 작은 연산이므로 면제한다거나 모든 Python expression을 CPU instruction 단위로 세는 두 극단 모두 승인하지 않는다. 각 추상 연산을 승인된 비용 또는 명시적 scope 근거에 연결해야 한다.

추가 구현, commit/push, adapter invocation 또는 runtime 활성화는 이 감사에서 수행하지 않았다.

## 12. 재현 파일

```powershell
python -B core_probe.py "D:\numerical-audit-lab-recovered-2026-10-01" > core_replay.log
python -B provenance_probe.py "D:\numerical-audit-lab-recovered-2026-10-01" > provenance_replay.log
```

스크립트는 현재 고정 후보를 검증한다. 저장소가 수정된 뒤 실행하면 source pin 또는 예상 경계가 맞지 않아 거부할 수 있다. `core_probe.py` 실행은 구현 전체가 PASS라는 뜻이 아니다. 그 스크립트는 R² 결함을 예상대로 재현했는지도 assertion으로 검사하므로, 스크립트 exit0과 전역 accounting PASS를 혼동하면 안 된다.

- `core_probe.py`: 실제 실행한 독립 scalar/whole-call/R² 검사 소스.
- `core_results.json`: 실행 시 canonical JSON bytes. SHA-256 `bc796ad14bc5b46a4ba26ffbe1c657e4cbc112e8728bc570dc30691ffcaca869`.
- `core_results.pretty.json`: 위 JSON의 읽기용 표현.
- `provenance_probe.py`: 실제 실행한 receipt/Git/source/pre-operation trace 검사 소스.
- `provenance_results.json`: 실행 시 canonical JSON bytes. SHA-256 `bdae7ef68dd645ac15a069b69a0aa4003e729e182f070bc750dfcb8b0e0c58fe`.
- `helper_failures.json`, `helpers/initial_failed_probe.py`: 초기 감사 도구 중단의 범위와 원인.
- `MANIFEST.sha256`: 이 전달 패키지 구성 파일 해시. 원 저장소 전체나 작성자 evidence 166개를 ZIP에 복제한 것은 아니다.
