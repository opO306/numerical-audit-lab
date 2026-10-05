# C1-B1 Independent Impulse V1 Reference Producer — 독립 구현 감사

**감사 기준일: 2026-10-05 (Asia/Seoul)**  
**대상: `opO306/numerical-audit-lab`, commit `d5475e23358cbf7f88018abfb67a8bfd192c5410`**

## 1. 최종 판정

```yaml
reference_producer_implementation: FAIL
independent_implementation_audit: FAIL
runtime_activation_allowed: false

V2_numerical_recheck: NOT_YET_APPROVED
J_status: J_NOT_VERIFIED
certification: NotCertified
```

**확정된 차단 원인은 `F-RESOURCE-ROUND-ADD` 한 가지다.** `rounding.nearest_even()`의 정수 증가 `floor + 1`이 승인된 자원 회계 경로를 통과하지 않는다. 작은 cap의 scalar 반례와 실제 reference producer의 whole-call 반례를 모두 재현했다.

이것은 **잘못된 J를 반환했다는 판정이 아니다.** 승인된 수학식, exact interval 합성, nearest-even의 수학적 cell 판정은 이번 감사에서 PASS다. 반면, 지정된 finite work budget을 준수한다는 구현 계약은 성립하지 않는다. 그 결과 I15와 I16은 같은 원인으로 FAIL이다. 두 항목의 FAIL을 서로 다른 두 결함으로 세지 않는다.

21개 PASS 항목 역시 해당 명제에만 적용된다. 전체 구현, 활성 runtime, V2 numerical agreement, 물리적 정확성 또는 trajectory를 승인하는 수단으로 사용할 수 없다.

## 2. 스냅샷·spec 고정과 검사 환경

| 항목 | 직접 확인한 값 |
|---|---|
| target | `d5475e23358cbf7f88018abfb67a8bfd192c5410` |
| direct parent | `bc6cf7a6312951ddefe4e066afa19bedfbeef695` |
| Git tree | `63df10c98a78818a930595db47677a0ba0238b76` |
| Arithmetic antecedent | `65d8fd29ae255529afead70289098d36b825b3b4` |
| impulse source count | 18 |
| source bundle SHA-256 | `a4bd12c92a4ad7f2a00503fa0ed249c8a96546d3999a68203fe4344f0c6554d7` |
| semantic SHA-256 | `3c3773b306700b0cf2dced1a618ae73ad81c7dd4abbf36764fc6ec3191ff2bc1` |
| package SHA-256 | `4a4cad78a192f72cf479cf16ceb971ea257d9bdf89acc5a7ca6e4fea3738219f` |
| 실행 환경 | Python 3.12.7, Windows 11, 64-bit |
| 감사 종료 시 Git status / diff | 둘 다 비어 있음 |

연결된 PC의 새 임시 디렉터리에 별도 clone을 만들고 target SHA를 detached checkout했다. 기존 개발 작업 폴더는 검사 사본으로 사용하지 않았다. `git show HEAD:path`의 실제 blob bytes와 작업 사본 bytes를 대조했다. author `source-identity.json`은 독립 계산 이후의 비교 자료로만 사용했다.

Source bundle digest의 정의는 18개 basename→SHA-256 매핑을 lexical key order, compact separators, ASCII JSON, terminal LF로 직렬화한 bytes의 SHA-256이다. 승인된 spec directory의 package, semantic, dependency, sidecar, canonical framing을 직접 검산했다. mutable branch의 나중 상태를 대상 대신 사용하지 않았다.

고정 spec 안에 남아 있는 과거의 `REVIEW PENDING` 등의 문구를 새 승인으로 덮어쓰지 않았다. 승인 antecedent는 이번 지시서의 bc6 revision을 기준으로 삼으며, 이번 감사는 그 spec 설계를 다시 승인하는 작업이 아니다. I2 PASS는 정확한 revision에 대한 binding PASS이지 모든 구현 의미의 준수 판정은 아니다.

증거: `evidence/raw/inventory.json`, `evidence/raw/independent-core/source-identity.json`, `evidence/raw/final-receipt.json`.

## 3. 확정 finding — F-RESOURCE-ROUND-ADD

### 3.1 원인과 요구 계약

위치: `independent_checker/c1b1/impulse/rounding.py`, `nearest_even()`, 특히 21–22행의 `floor + 1` 반환 경로.

```python
if twice > q.denominator:
    return floor + 1
return floor if floor % 2 == 0 else floor + 1
```

`c`가 전달되면 divmod는 `c.divmod`, 두 배 연산은 `c.multiply`로 청구한다. 하지만 이어지는 정수 덧셈은 `c.add`를 거치지 않는다.

승인된 `finite-policy.json`의 work schedule은 덧셈에 `max(A,B)+1`, 곱셈에 `(A+1)*(B+1)`, divmod에 `(A+1)*(B+1)**2`를 부과한다. `resource.py:ResourceAccount.add()`는 동일한 덧셈 공식을 적용하고 실제 덧셈 전에 `pre()`를 호출한다. 여기에서 work는 선언된 수학적 비용 단위이며, CPU cycle 수나 실제 실행 시간의 측정값이 아니다.

이 판단은 표본 실행 시간이나 allocator 모델의 실제 메모리 예측 정확성을 근거로 하지 않는다. 승인된 연산별 청구 계약과 해당 실제 연산의 누락을 근거로 한다. 앞선 divmod의 보수적인 비용 추정에 이후의 모든 덧셈까지 포함된다고 재해석할 별도 계약·증명은 확인되지 않았다.

### 3.2 최소 scalar 반례

```python
from fractions import Fraction
from independent_checker.c1b1.impulse.resource import ResourceAccount, ResourceLimit
from independent_checker.c1b1.impulse.rounding import nearest_even

c = ResourceAccount(
    bit_max=100000,
    num_bit_max=100000,
    den_bit_max=100000,
    work_max=73,
)
assert nearest_even(Fraction(7, 4), c) == 2
assert (c.work, c.operations) == (73, 2)

# Target은 이미 위에서 같은 정수 덧셈 1+1을 수행했다.
try:
    c.add(1, 1)
except ResourceLimit as error:
    assert error.kind == "WORK"
else:
    raise AssertionError("declared work limit was not enforced")
```

정확한 비용 분해:

| 연산 | 승인된 청구량 |
|---|---:|
| `divmod(7,4)` | `(3+1)*(3+1)^2 = 64` |
| `2*3` | `(2+1)*(2+1) = 9` |
| `1+1` | `max(1,1)+1 = 2` |
| 합계 | **75** |

Target은 cap 73에서 최종 연산까지 수행하고 `2`를 반환한다. 수학적으로 `round_even(7/4)=2`인 것은 맞지만, 그 반환에 필요한 선언된 연산별 work가 모두 청구되지 않았다.

### 3.3 Whole-call 반례

실제 입력은 FX48에 정확히 놓인 `q=(5,3,-2)`다. 원자 i의 position은 `(0,0,0)`, j의 raw position은 다음과 같다.

```text
[1407374883553280, 844424930131968, -562949953421312]
```

전체 canonical Input은 `COUNTEREXAMPLE_INPUT.json`에 있다. 스키마·spec·domain·policy 일치 검사를 통과한다. 반례 Input bytes SHA-256:

```text
bab9520968c7e3b5be3e6d5c5e53627a06d066bbb950579c7cc8ec2b65dcfffd
```

원본의 work cap을 원본이 스스로 기록한 work와 정확히 같게 설정했다.

```text
W = 2605253326086889986
```

실제 rounding increment 두 건:

```text
 31271991804947823288592 + 1 →  31271991804947823288593 : 76 units
-20847994536631882192396 + 1 → -20847994536631882192395 : 76 units
총 누락 확인분: 152 units
```

| 같은 물리 입력에서의 시험 | work cap | 결과 |
|---|---:|---|
| 원본 계산/청구 | W | complete private raw/certificate 반환 |
| 수학은 그대로 두고, 누락된 두 덧셈의 청구만 audit interposition으로 추가 | W | `RESOURCE_CAP / WORK`, raw·opposite·certificate 없음 |
| 같은 추가 청구를 유지하고 한도를 152 늘림 | W+152 | 원본과 동일한 raw 반환 |

원본과 충분한 한도의 비교 실행에서 얻은 raw는 동일하다.

```text
J_raw = (
  52119986341579705480988,
  31271991804947823288593,
 -20847994536631882192395
)
```

추가 청구를 적용한 cap W 실행의 failure는 다음 상태다.

```text
phase = PUBLICATION
reason = RESOURCE_CAP
resource_kind = WORK
producer = RESOLVED
publication = NOT_PUBLISHED
execution = STOP
raw = None
opposite = None
certificate = None
```

중요한 구분: 이 failure의 producer가 `RESOLVED`인 것은 이상이 아니다. 수학적 cell 판정은 이미 끝났고, 완전한 private candidate의 구성 중 work cap이 관측된 경로다. 그래서 이를 임의로 `producer=UNPROVED`라고 기록하지 않았다. 이 결과는 오히려 관측된 resource failure를 raw 반환 없이 멈추는 경로가 작동함을 보인다. 문제는 원본 장부가 누락된 비용을 관측하지 못한다는 점이다.

`resource_repro.py`의 interposition은 원본 함수를 호출한 뒤 누락된 연산 비용의 영향을 분리하는 **감사용 실험**이다. 이것을 연산 전 precharge를 구현한 production 수정으로 제시하지 않는다. 원본 파일은 변경하지 않았다. `W+152`의 성공 역시 다른 모든 비용 또는 allocator majorant가 검증됐다는 뜻이 아니다. 152는 이번에 독립적으로 확인한 누락분이다.

심각도: **독립 구현 승인 차단 결함**. 실제 수치 오답, 메모리 폭발 또는 실행 시간 초과를 재현했다고 주장하지 않는다. 누락량의 크기가 작다는 이유로 exact finite-policy 계약의 위반을 면제할 수는 없다.

증거: `COUNTEREXAMPLE_RESULT.json`, `sources/resource_repro.py`, `logs/resource-repro.log`.

## 4. I1–I23 판정

| ID | 항목 | 판정 | 직접 근거와 적용 범위 |
|---|---|---|---|
| I1 | snapshot/source identity | **PASS** | target/parent/tree 및 18개 source의 실제 Git blob SHA-256 고정. source inventory와 작업 사본 일치. |
| I2 | approved spec binding | **PASS** | semantic/package 및 dependency/sidecar/canonical bytes 재계산 일치. 다른 revision의 대체 없음. |
| I3 | independence | **PASS** | 18개 AST/import 검사, 실제 reference 호출 74개 함수 경로 추적. executor/V2 수학 helper 또는 동적 추출을 계산 oracle로 사용하지 않음. |
| I4 | physical formula/sign | **PASS** | q=r_j-r_i, -V′q/R, half_dt=20, scale=2^80, common-J negation 및 질량 비개입을 독립 유도·시험. |
| I5 | potential/derivative | **PASS** | 공개 V 식의 generic forward AD와 exact enclosure로 BO/REL/QED 값·도함수 분기 대조. |
| I6 | interval primitives | **PASS** | add/sub/corner product/positive reciprocal/powers/outward widening의 포함 관계 유도 및 180개 혼합 부호 interval 쌍 시험. |
| I7 | sqrt | **PASS** | 정확한 제곱 부등식, dyadic square singleton, non-square, coarse zero lower, refinement를 확인. |
| I8 | exp | **PASS** | positive Taylor reciprocal의 수학적 상·하한 유도. 별도 alternating-series oracle 및 매 squaring widening 확인. |
| I9 | J composition | **PASS** | V′→-V′/R→q→20→2^80의 exact interval 합성. storage-grid 중간 반올림 없음. |
| I10 | nearest-even rounding | **PASS** | 수학적 cell 판정은 정확함. endpoint는 후보만 제안하고 두 끝점을 검사. 자원 청구 누락은 I15에서 별도 FAIL. |
| I11 | overflow/opposite raw | **PASS** | signed96 양끝 및 -2^95의 opposite 실패 확인. coarse 정상/overflow 혼합은 확정 overflow로 처리하지 않음. |
| I12 | domain/zero-axis | **PASS** | schema/spec→exact physical domain→zero lane 순서. r_min의 rational equality와 FX48 경계 분리. |
| I13 | attempt reason/digest | **PASS** | 독립 25-state table, 525개 reason 조합, 두 null 성공행, 실제 attempt 및 canonical raw32 digest 재구성. |
| I14 | parser/failure wire | **PASS** | later malformed/4096-digit early field/duplicate/extra/missing를 conversion spy로 공격. Failure 11 fields·17 nonnull reasons 확인. |
| I15 | resource accounting | **FAIL** | F-RESOURCE-ROUND-ADD: nearest_even의 floor+1이 ResourceAccount.add를 우회. scalar 및 whole-call 반례 확정. |
| I16 | finite-policy fail-closed | **FAIL** | I15와 같은 원인에서 파생. 누락된 청구를 제외한 장부 cap에서 완전한 private candidate를 반환하여 승인된 work 계약을 보장하지 못함. |
| I17 | whole-vector atomicity | **PASS** | 수치 UNPROVED/overflow·관측된 resource/publication 실패에서 partial raw/opposite/certificate 없음. 혼합 lane 우선순위 확인. |
| I18 | immutability | **PASS** | 성공·domain·resource·publication 실패에서 입력 bytes/object 보존. translation/momentum fixture의 nested alias도 보존. |
| I19 | certificate soundness boundary | **PASS** | compact binding/parameters/raw claim만 전달. final interval/transcript가 proof authority로 들어가지 않음. 7개 binding 독립 재구성. |
| I20 | adapter/prepared-only boundary | **PASS** | 구조·binding·zero lane·invoke 차단 범위만 PASS. order schedule 누락은 실제 재현되었으며 후속 Gate blocker로 OPEN. |
| I21 | independent tests/counterexamples | **PASS** | author test와 다른 exact oracle·fixtures·확정 resource 반례 및 실행 로그 확보. PASS는 전체 구현 PASS를 뜻하지 않음. |
| I22 | source mutants | **PASS** | 16개 실제 stored source edit/preimage 대조 후 독립 runner로 전부 semantic 검출. setup/hash mismatch를 검출로 세지 않음. |
| I23 | Arithmetic/history preservation | **PASS** | Arithmetic 8개는 65d8fd2와 byte-identical. bc6의 기존 specs/docs/audit/current에 수정·삭제 없음. |

I16을 별도 FAIL로 표시한 것은 같은 resource 결함의 finite-policy 결과까지 숨기지 않기 위해서다. 실제로 감지된 cap 이후의 exception 처리, 마지막 근사값 미수락, publication 실패의 atomicity는 통과했다. 반례는 그 이전의 청구 누락 때문에 “모든 cap이 실제로 지켜진다”는 end-to-end 명제가 성립하지 않음을 보인다.

## 5. 수학 경로의 독립 유도

### 5.1 물리식·방향·half-step

중심 pair potential을 승인된 함수 `V(R)`라고 두면 `q=r_j-r_i`, `R=sqrt(q·q)`이고, j 좌표에 대한 `R`의 기울기는 `q/R`이다. 따라서 j에 작용하는 force는 `-V′(R)q/R`이다. full dt가 정확히 40이고 kick fraction이 1/2이므로 half-kick impulse는 `-20 V′(R)q/R`이다. i는 그 음수를 받는다.

이 유도에는 원자의 질량이 들어가지 않는다. 질량은 momentum impulse를 force의 시간 적분으로 정의한 이 단계에 추가할 항이 아니다. 구현은 `-V′/R`, component, `20*2^80`의 순서로 exact rational interval을 합성한다. 세 성분 전체의 마지막 nearest-even 판정 외에 storage-grid 양자화는 없다.

실제 비대칭 벡터, 전체 부호 반전, 성분 permutation, 공통 translation, 변경된 momentum, zero-axis를 대조했다. 결과의 대칭성·불변성은 부록의 exact oracle 계산과 함께 확인했다. 이것은 승인 spec의 force/impulse를 구현했다는 검증이지 실험적 물리 정확도 또는 적분기 정확도의 검증이 아니다.

### 5.2 BO / REL / QED와 도함수

공개 값 식의 short part는 `exp(-alpha R) P(R)`이다. product rule에 의해 도함수는 `exp(-alpha R)[P′(R)-alpha P(R)]`이다. BO의 polynomial 시작이 i=-1이므로 해당 항 `a/R`의 도함수 `-a/R²`도 포함해야 한다. target의 loop와 지수가 이 관계를 만족한다.

`z=eta R`, `S_L(z)=sum_{ell=0}^L z^ell/ell!`, `T=e^-z S_L(z)`라 두면, 유한합의 연속된 차수가 상쇄되어

```text
T′(R) = -eta * exp(-eta R) * (eta R)^L / L!
```

이다. 따라서 `1-T`와 `-T`의 도함수는 모두 `+eta*exp(-eta R)*(eta R)^L/L!`이며, BO leading `g-T`에만 `g′`가 더해진다. BO는 L=2k+1, REL/QED는 L=2k다. REL leading의 값은 `-T`이지 `1-T`가 아니다. QED에는 BO의 retardation leading 대체를 적용하지 않는다.

`g=N/D`의 quotient rule은 `(N′D-ND′)/D²`이고, long-range 항 `-C Damping(R) R^-2k`의 도함수는

```text
-C * [Damping′(R) R^-2k - 2k Damping(R) R^(-2k-1)]
```

이다. 승인 constants의 양수 denominator coefficients와 양수 radius domain으로 retardation denominator가 0이 되는 경로는 배제된다.

검증 oracle은 이 analytic derivative를 target에서 복사하지 않았다. 별도의 `Dual(value,tangent)`에 generic add/product/inverse rules를 구현하고, **공개 potential 값 식만** 입력해 forward automatic differentiation했다. BO/REL/QED 각각에 대해 R=3, 13/2, 10, 50의 값과 derivative를 exact bracket으로 대조했다.

### 5.3 Exact interval primitives와 합성

덧셈·뺄셈은 endpoint의 단조성, 곱셈은 rectangle의 네 꼭짓점 extrema, 양수 reciprocal은 감소함수의 endpoint reversal로 포함 관계를 증명한다. 양의 정수 홀수 power는 단조이고, 짝수 power의 sign-crossing에서는 하한이 0이다. 음수 power는 양수 interval reciprocal 이후의 양수 power로 환원한다. Target의 수식이 이 경우 분할과 일치한다.

각 intermediate interval이 실제 값을 포함하면 이 연산들을 유한 번 합성한 V′와 J interval도 실제 값을 포함한다. 같은 R을 여러 번 쓰는 dependency 또는 cancellation 때문에 폭이 커질 수 있지만, 그것을 이유로 임의 narrowing할 수는 없다. Target에는 midpoint를 truth로 대체해 폭을 줄이는 경로가 없으며, narrowing 변이는 독립 oracle에 의해 검출됐다.

### 5.4 Sqrt

`r2=u/v`, `a=isqrt(floor(u*2^(2N)/v))`라 두면

```text
a² <= r2*2^(2N) < (a+1)²
```

이다. 따라서 `a/2^N`과 `(a+1)/2^N`은 sound enclosure다. `a²*v == u*2^(2N)`일 때에만 같은 endpoint로 축소할 수 있다. Target은 바로 이 정수 등식으로 singleton 여부를 결정한다.

600개의 seeded rational/precision 조합에 대해 실제 endpoint를 제곱한 exact 부등식을 검사했고, 별도로 4개의 exact dyadic square와 coarse lower=0인 nonzero case를 확인했다. Host float sqrt는 proof oracle로 사용하지 않았다. 일반 rational perfect square라도 현재 N의 dyadic grid에 표현되지 않으면 non-singleton이어도 sound하다. 필요한 조건은 “singleton이면 정확한 square”이지 “모든 rational square는 모든 N에서 singleton”이 아니다.

### 5.5 Exp

Target은 `exp(-x)`를 계산한다. `x_hi/2^s <= 1/2`가 되는 최소 s로 range reduction한 뒤 `y=x/2^s`의 양수 Taylor sum을 사용한다. n차 다음 항 `a_(n+1)` 이후 항의 비는 `y_hi/(n+2)` 이하이므로, ratio<1에서 remainder는

```text
a_(n+1)(y_hi) / [1-y_hi/(n+2)]
```

이하이다. 그러므로 interval의 두 endpoint를 고려하면

```text
1/[S_n(y_hi)+tail_hi] <= exp(-y) <= 1/S_n(y_lo)
```

이다. 양수 reciprocal이므로 방향이 바뀐다. 초기 absolute dyadic outward widening과 매 squaring 이후 widening은 각각 포함 관계를 보존한다. s번 제곱하면 `exp(-x)`를 포함한다. Instrumentation으로 초기 widening 한 번과 각 squaring의 widening 한 번씩, 총 s+1번을 실제 확인했다.

독립 oracle은 이 알고리즘을 복제하지 않았다. `m=ceil(x)`, `u=x/m`으로 0<u<=1에 놓고 alternating Taylor의 odd partial sum S63와 even partial sum S64로 exp(-u)를 감싼 뒤 exact interval integer power로 복원했다. 모든 비교는 Fraction이다. `math.exp`와 mpmath point value는 이 독립 증거에서 사용하지 않았다.

x=0, 매우 작은 양수, 1/2 및 그 직후, 1, 3, 20, 100, 1000에 대해 P=8,32,80,128을 검사했다. 채택된 order보다 하나 작은 cap에서 ORDER refusal을 확인했다. 추가로 폭이 있는 argument interval을 넣어, 목표 폭을 달성할 수 없으면 finite refusal을 하고 임의 narrowing을 하지 않는지 확인했다.

이 포함 관계와 고정 입력에서의 refinement 가능성은 “모든 admissible input이 고정 finite budget 안에서 성공”한다는 명제를 만들지 않는다. 내부 수렴, rounding-cell 분리 가능성, finite configured success, proof publication feasibility는 각각 다른 조건이다. 이번 source의 runtime 활성화도 이 수학적 유도만으로 승인되지 않는다.

### 5.6 Rounding과 overflow

Nearest-even은 정수 m이 짝수일 때 `[m-1/2,m+1/2]`, 홀수일 때 `(m-1/2,m+1/2)`가 cell이다. Target은 lower endpoint에서 후보를 얻지만 양끝점 모두 그 cell에 들어가는지 따로 검사한다. midpoint의 대표값만으로 확정하지 않는다.

독립 oracle은 유리수와 인접 정수의 exact distance를 비교하고 동률이면 짝수를 택한다. 반올림 함수의 단조성을 이용해 interval 두 끝점의 결과가 같은지 검사했다. 총 13,392개의 closed interval 조합을 대조했고, 별도 `-2^95` opposite assertion을 추가했다. Signed96 상한의 half tie, 하한의 even tie, 음수 tie, 0 근방 및 여러 cell을 가로지르는 경우가 포함된다.

`J_raw=-2^95` 자체는 표현되지만 opposite은 `+2^95`이므로 거부되어야 한다. 이 경로는 정상 거부된다. 한편 정상 raw와 overflow가 함께 가능한 coarse interval은 전부 overflow라고 단정하지 않는다. 이번 resource finding은 이 수학적 판정의 정확성과 구분한다.

## 6. Domain, parser, attempt, failure와 atomicity

Physical domain은 `R²`를 정확히 비교한다. `r_min=1200000000000/529177210903`이며, `R=0`을 먼저 singular로 분류한다. Below-min은 거부하고 equality는 admitted다. 이 equality는 rational-domain 테스트에서 직접 확인했다. 분모에 홀수 인수가 있으므로 해당 정확한 equality는 FX48 position lattice에서 실현되지 않는다는 점을 구분했고, 실제 lattice에서는 r_min 바로 위 첫 점을 별도로 실행했다.

Parser 시험은 큰 early decimal과 뒤쪽의 malformed field를 함께 넣고 integer conversion 함수를 spy했다. Shape·key·array·decimal syntax 오류에서 conversion 호출이 0회인 것을 확인했다. Duplicate key, extra/missing key, 잘못된 LF framing, depth, numeric JSON token, 4097 digits 및 late malformed cases를 검사했다. 테스트 프로세스에만 낮은 host integer conversion limit을 일시 적용했고, `HOST_SERIALIZATION_LIMIT / PARSE / HOST_DECIMAL`로 bounded failure가 반환됨을 확인한 뒤 원래 값을 복구했다. Production 코드에서 전역 제한 setter를 추가하거나 호출하지 않았다.

Adapter에는 Input과 Certificate를 함께 공격했다. 앞쪽 Input에 4096-digit decimal을 두고, 뒤쪽 certificate의 마지막 order/rate/raw/lane-kind를 잘못 만들었다. 독립 `_int` spy로 두 문서의 schema/syntax validation이 끝나기 전에 conversion이 실행되지 않는지 6가지 경우에서 확인했다.

Attempt reason은 독립적으로 25개 producer/rechecker 상태쌍을 만들고, null·전체 closed reason enum·문자열 null/SUCCESS/unknown의 525개 조합으로 확인했다. Success-null은 `RESOLVED/NOT_RUN/null`과 `RESOLVED/ACCEPTED/null` 두 행뿐이다. Missing reason, unknown state, extra field는 거부된다.

독립 canonical tuple bytes 예:

```json
{"N":"128","P":"128","producer":"RESOLVED","reason":null,"rechecker":"NOT_RUN","t":"0"}
```

위 JSON 뒤에는 terminal LF가 정확히 한 개 있다. 해시 계산은 hex 문자열을 이어 붙이는 것이 아니라 raw 32-byte 이전 digest를 사용한다.

```text
H0 = 71440aac921a3a7ccda50b94757d27b25b8d1479f074cdabbcf80d37e62bb0cb
H1 = 4127e8735c008c88f0e9105fe8e895d60bc7776a778277763bf8d6bb940aa41e
```

실제 producer 실행에서 관측한 attempt tuple을 따로 저장하고 마지막 digest와 count도 재구성했다. Digest는 diagnostic binding이며 nonlinear correctness의 독립 증명이 아니다.

Failure는 정확히 11개 closed fields, non-null reason enum, resource-kind 분리, 4096-byte envelope, nullable hash와 null attempt_count 규칙을 따른다. 17개 reason을 직접 구성했고 Failure.reason의 null 허용은 없음을 확인했다. Attempt의 성공-null 규칙이 Failure로 전파되지 않았다.

Whole-vector fixture는 resolved/ambiguous/resolved, overflow/ambiguous/resolved, opposite-overflow 조합을 사용했다. 수학적 ambiguity, 관측된 resource refusal, certificate size limit 등의 실패에서는 partial raw/opposite/certificate가 없다. 입력 object와 canonical bytes는 성공과 실패에서 보존됐다. 성공 fixture 중 nested momentum array alias를 공유한 입력도 보존됐다. 실제 `produce()`는 domain admission 후 `POLICY_UNBOUND`를 반환하고 nonlinear 함수 호출 전에 멈춘다.

## 7. Certificate와 adapter의 정확한 승인 경계

생성된 compact certificate에는 approved binding, source identity, method parameters, raw claims, attempt binding이 있으며, final interval이나 producer interval transcript는 없다. `PrivateResult.scaled_intervals`는 감사용 내부 결과이지 normative proof wire의 authority가 아니다. 별도의 재계산 없이는 certificate의 raw claim을 truth로 취급할 수 없다.

Input/full state/projection/math request/occurrence/acquisition record/budget의 7개 hash를 공개 payload schema에서 독립적으로 다시 구성해 대조했다. Certificate의 N/P doubling과 9개 legacy order schedule도 producer helper를 사용하지 않고 검산했다.

**Known limitation은 실제로 존재한다.** q=(5,0,3)의 정상 certificate에서 첫 `BO_ALPHA_1` order는 **163**이다. 이 값을 **1**로 바꾸되 syntax와 cap을 유지하면 `prepare()`는 여전히 `PREPARED_ONLY`를 반환한다. 따라서 adapter가 `n_R(t)=ceil(4*rate*r_guard+1)*2^t`를 독립 재구성한다는 주장은 승인할 수 없다.

다만 정상 preparation과 변조 preparation 모두 `invoke()`가 차단되어 있다. 이 limitation이 현재 reference producer의 J 계산을 바꾸거나 numerical acceptance를 발급하는 경로는 확인되지 않았다. 따라서 I20은 **준비 단계의 구조·fail-closed 경계만 PASS**, schedule 검증은 **후속 rechecker/runtime Gate의 OPEN blocker**로 분류한다. `PREPARED_ONLY`를 `ACCEPTED`와 동의어로 사용하면 안 된다.

추가로 zero-axis에 raw=1을 넣는 변조, certificate extra/missing field는 거부됐다. Acquisition hash 일치는 acquisition의 외부 진위나 provenance 인증을 의미하지 않는다. 그 외부 인증은 이번 reference implementation의 승인 범위 밖이다.

## 8. 독립 실행 결과와 author suite의 구분

| 실제 실행 | 결과 | 해석 |
|---|---|---|
| 독립 core suite | 18,445 assertions, exit 0 | arithmetic/schema/digest/guard 등의 검사. Resource group의 PASS는 별도 finding이 없다는 뜻이 아님. |
| 독립 physical oracle | 12개 물리 상태 + 12개 family/radius 조합, 208 assertions, exit 0 | exact bracket containment 및 raw 일치. |
| 독립 supplement | 138 assertions, exit 0 | 7 bindings, Failure 17 reasons, adapter parser와 wide-exp 추가 검사. |
| 확정 resource 반례 | scalar + whole-call, exit 0 | **결함을 재현하는 감사 코드가 성공했다는 뜻**. Target이 정상이라는 뜻이 아님. |
| 독립 source-mutant runner | 16/16 semantic detection, exit 0 | 각 mutant 실행은 실패하고 baseline은 성공. |
| 기존 전체 pytest | **1,099 passed in 52.44s**, exit 0 | 보조 regression evidence만 사용. |

Core+physics+supplement의 직접 assertion 합계는 **18,791**이다. 이것을 18,791개의 수학적 정리 또는 전 입력 검증으로 환산하지 않는다. 전 범위 soundness 판단에는 앞 절의 식 유도와 소스 경로 검토가 함께 필요하다.

Author가 언급한 runtime relations 550, spec regression 46, static checks 155, adapter 18이라는 세부 suite 숫자는 각각 별도 author command로 재발급하지 않았다. 실제 실행한 author command는 전체 pytest 한 번이며, 독립 표·parser·adapter·mutant 검사는 이 감사의 새 코드로 수행했다. 이 구분을 숨기지 않는다.

최초 mutant 실행 사본에는 package initializer가 필요로 하는 `independent_checker.audit`가 빠져 import failure가 발생했다. 이 실행은 mutant detection으로 세지 않았다. 전체 `independent_checker` 패키지를 복사하도록 **감사 harness만** 보완한 뒤 final output directory에서 baseline부터 16개 모두 다시 실행했다. Production snapshot에는 해당 수정이 없다.

## 9. 16개 실제 source mutants의 독립 검사

저장된 `mutants-after-review/<name>/source-before.py`를 target bytes와, 저장된 `source-mutant.py`를 독립 runner가 만든 실제 replacement bytes와 비교했다. 모든 preimage/edit가 일치했다. 이후 각 mutant를 새 임시 복사본에 적용하고, author pytest node 대신 이번 exact oracle 또는 계약 시험을 실행했다. Baseline은 oracle 종류별로 먼저 실행해 exit 0을 확인했다. Source hash 변화 자체는 detection oracle로 사용하지 않았다.

| mutant | baseline exit | mutant exit | 독립 semantic failure |
|---|---:|---:|---|
| `force-sign` | 0 | 1 | 세 성분의 부호가 exact AD oracle과 반대. |
| `half-step` | 0 | 1 | full dt 40을 사용하여 raw가 half-step oracle과 불일치. |
| `inverse-R` | 0 | 1 | 1/R 누락으로 raw 불일치. |
| `R-power` | 0 | 1 | 도함수 R 지수 변경으로 raw 불일치. |
| `TT-derivative` | 0 | 1 | damping derivative 삭제로 raw 불일치. |
| `BO-gprime` | 0 | 1 | BO leading g′ 삭제로 raw 불일치. |
| `exp-sign` | 0 | 1 | 계산된 interval의 순서가 역전되어 mathematical invariant 실패. |
| `component-swap` | 0 | 1 | 비대칭 비영벡터 (5,3,-2)에서 x/y 결과 불일치. |
| `ties-away` | 0 | 1 | tie-even oracle 위반. 작성자 label은 ties-away지만 실제 edit는 tie에서 floor+1 강제. |
| `inverse-endpoints` | 0 | 1 | 양수 reciprocal의 끝점 역전 규칙 위반으로 unordered interval. |
| `inward-rounding` | 0 | 1 | 독립 exact lower/upper의 포함 관계를 잃음. |
| `early-accept` | 0 | 1 | 여러 cell을 가로지르는 interval을 수락하여 cell oracle 위반. |
| `resource-guard` | 0 | 1 | 작은 bit cap에서 연산 전 ResourceLimit이 발생하지 않음. |
| `wrong-spec` | 0 | 1 | 잘못된 spec hash 입력에 private raw가 반환되어 binding refusal 계약 위반. |
| `intermediate-quantization` | 0 | 1 | 반경의 FX48 중간 반올림으로 exact raw 불일치. |
| `exp-cutoff` | 0 | 1 | x=100에서 [0,0]을 반환하여 독립 exp(-100) bracket을 포함하지 못함. |

`exp-sign`과 `inverse-endpoints`의 `unordered interval`은 import/setup 실패가 아니다. 실제 mathematical operation이 실행된 뒤 exact interval invariant를 위반하여 structured 결과와 traceback을 남긴 경우다. 두 반례를 rounding/원시식의 실패와 구분해 기록했다.

부호·half-step·1/R·component swap 시험은 `(5,3,-2)`를 사용한다. 모든 성분이 0이 아니고 서로 다르며, radius가 1이 아니어서 변이가 우연히 지워지는 degenerate fixture가 아니다. BO g′·TT·R-power 변이도 실제 raw mismatch를 남겼다.

## 10. 보존 검사

직접 parent의 tracked file 수는 2,163개였다. target diff에서 기존 specs/docs/audit/current 파일의 수정·삭제는 없었다. 추가된 기록은 이전 기록을 사후 수정한 것으로 취급하지 않는다. 따라서 parent에 있던 approved spec, 8e closure PASS history, ATTEMPT-REASON-NULL evidence를 target에서 다시 쓰지 않았다는 보존 범위가 확인됐다. 과거 감사의 수학적 결론 자체를 이번에 다시 증명한 것은 아니다.

다음 8개는 `65d8fd2`와 직접 bytes 비교했다.

| Arithmetic 파일 | target SHA-256 | antecedent 비교 |
|---|---|---|
| `claim_adapter.py` | `24b05ebf374728583ba725c83b8f9324f4b75b5515b03c5b1036339eef3e4899` | 일치 |
| `compare.py` | `5ad6b3f0b03b240e559c955552f32eb9079d524fba55be47ab88329a7d0657b2` | 일치 |
| `contracts.py` | `37acf394c9c252d5e401fdff06fcb28a0ab1202cc090f1456ecd4bb84fff47ed` | 일치 |
| `exact_slow.py` | `b36efc03abdcb760f294f009ea1aea8aafa6fcc05a53c7b3970291c90edf4c13` | 일치 |
| `exact_fast.py` | `2190e099642b4bf440e4a2280b09d4b89984f637e6cee1b09dfa23411f0b4c0b` | 일치 |
| `exact_geometry.py` | `b237cd00e45e2ed635bae54880cfef88c1126e98af57d74843b752d2ed27677e` | 일치 |
| `semantic_manifest_v1.json` | `3217fc38aa798fff3ffea8072cecafaecac9f98be85589e9fa35a9dc6aa8119b` | 일치 |
| `semantic_manifest_v1.sha256` | `ae8b89667a539b4252cac34b0f96786dda67c10747e66f2468482d94e5a6db79` | 일치 |

감사 종료 시 모든 impulse source hash는 시작과 같고 `git status --porcelain`, `git diff --stat`은 비어 있다. Production 변경, commit, push, runtime activation은 수행하지 않았다. 변이 소스 수정은 독립 runner가 만든 폐기 가능한 별도 복사본에만 적용했다.

## 11. 승인하지 않은 것과 후속 재감사 조건

이번 결과는 V2 numerical acceptance, executor integration, J verification, physical C1-B1 PASS, trajectory PASS, NotCertified 해제를 승인하지 않는다. 적용 가능한 모든 입력에서 finite budget success를 보장한다고 해석해서도 안 된다.

Allocator footprint는 `AUTHOR_FIXTURE_MODEL_UNVALIDATED`로 표시된 모델이다. Ledger의 predicted live bytes를 실제 peak RSS나 검증된 allocator majorant로 바꾸어 부르지 않았다. 플랫폼·allocator별 majorant, pinned V2 whole-call preflight, 격리 worker의 hard memory/CPU/wall enforcement 및 active policy instance/hash의 독립 승인은 여전히 별도 Gate다.

현재 finding의 제한 재감사에서는 최소한 다음을 재현해야 한다. 먼저 두 `floor+1` 분기 모두에서 **실제 연산 전에** account 경로로 거부될 수 있어야 한다. Scalar 7/4 및 음수·odd tie fixture, whole-vector rounding, resource cap을 work 경계 바로 아래/위로 둔 경우를 검사해야 한다. 그 다음 resource ledger 경로를 재검토하여 이 두 줄의 수정만으로 다른 누락까지 고쳤다고 추정하지 않아야 한다. 수학적 J와 cell 판정은 기존 exact oracle을 유지해 회귀를 확인할 수 있다.

이번 감사에서는 그 수정이나 activation을 수행하지 않았다. 전체 구현 판정은 현재 target에 대해 **FAIL**이다.

## 12. Source identity 전수 목록

아래의 18개 SHA-256은 actual target bytes로부터 다시 계산했다.

| source | SHA-256 |
|---|---|
| `__init__.py` | `7ba075ea0e3610c058c6ef048bd1bc2a5aaf771e3ad0392816d8200e6f655b56` |
| `attempt.py` | `9475c5d0c6329a4d0e8d61551528a4f86f14dad594fb5357cca51e94588e8950` |
| `certificate.py` | `12902c7b981374d613f3080921926f7fffabc36b1583a524bc412cf3a51d3044` |
| `contracts.py` | `9319b533d6ff8230cfa2f45225f5a00a08281ba350ed0648037c3fa4b3848f1b` |
| `derivative.py` | `d090e765d103451e54eadc73638f20ac6f2e7065e455d60745ba774ae21f1f33` |
| `domain.py` | `ac0dec4522377467a2397976d409d5a4da09bd5ff53f43f3adb889eb9b20f746` |
| `exp_enclosure.py` | `032123fcd0f9d2d486c8fa5fd3fd9ca13995fe1a91f98ddb2e53d31e1c9cb2e1` |
| `identity.py` | `4487192289e05d3824a9aa29907cd7c63f21cae6e2f47b2673089e41eeddb98e` |
| `interval.py` | `421b2fdb0ec1bb095d48347eb3892ca7da95e86240d87ba572dfa450da462834` |
| `policy.py` | `7ee389e22e36200cc5318fc8c27a5e592a2760626a4937b38bd96a4b5baf0724` |
| `potential.py` | `5add6bb8c26f399882a6d79d185b2f4d7bb0265f25009da90b04400eec84f9c4` |
| `producer.py` | `54d3d94f1d8b77824ffa9d5acd6b4bd27ac0f93fd31491d34b8cb0508c0825e9` |
| `rechecker_adapter.py` | `eda48be7b1d80b503e5ecb64b3b422cfa7e84321895d7fe638bb2c33da1fda23` |
| `resource.py` | `7cf03263c0e3461adf09e22ff56882dcbc3f5c12691d1e348f5a80a6a885a9c6` |
| `rounding.py` | `327a396780dc88a74af750cfa2ed997809360c95cda7201d1c8aba5f78959e90` |
| `spec.py` | `99f20976c15b18a3955b7c61136c3c19dd043a554d71d53d35ac88cf62f52a49` |
| `sqrt_enclosure.py` | `fb7ad0a3ddacc712e294294f6db219dd4429e327aca12631a5536fca897c5994` |
| `wire.py` | `3b63ae10402ce73ecedc810db35f4c966cdc317ae932cf1906204af75cb416c2` |

## 13. 재현 자료 안내

`README_KO.md`에 명령과 결과 파일의 구분이 있다. `sources/`의 6개 Python 파일은 실제 원격 감사에서 실행한 소스와 SHA-256이 모두 일치한다. `evidence/raw/`의 43개 파일은 원격 출력으로부터 tar.xz로 전송하고 SHA-256을 대조해 확보한 원본 bytes다. PowerShell 로그 일부가 UTF-16이므로 편의를 위해 `logs/`에 UTF-8 읽기용 사본도 만들었다. 원본과 사본을 같은 bytes라고 주장하지 않는다.

Evidence transport archive SHA-256:

```text
4a54896f15860e38fc71fe8b19643007596dd43527b2fab8ae60b67fed30d540
```

Complete 원격 evidence archive(125 files, author JUnit XML·개별 mutant source copy·추가 input/certificate 포함)는 검사 PC의 감사 임시 폴더에 보존되어 있다. 전달 ZIP은 43개 핵심 원본 evidence, 모든 독립 검사 소스, 상세 판정 및 반례 Input/Result를 포함한다. Target 저장소 전체를 다시 배포하는 standalone snapshot ZIP은 아니다.

모든 상대 evidence 경로는 이 패키지의 `evidence/raw/`를 기준으로 한다. 코드·spec의 원본 기준은 이 문서 맨 위의 정확한 Git commit이며, 구현 주장과 감사 결과가 충돌할 때 author PASS나 mutant 숫자로 finding을 무효화해서는 안 된다.
