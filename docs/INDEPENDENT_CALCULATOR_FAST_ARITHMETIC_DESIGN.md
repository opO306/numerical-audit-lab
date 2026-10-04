# 새 C1-B1 독립 계산기 계층 — 범위·계약·연결 제안

**상태: PROPOSED / DESIGN ONLY / NOT IMPLEMENTED / NOT BENCHMARKED**

날짜: 2026-10-04. Lab 기준 HEAD: `e976fa0fdeef16a27f112a0a4ee42494fe1e46b1`.
이번 문서는 사용자의 후속 정정을 따른다. Lab에 기존 C1-B1 Drift/Kick exact oracle이
있다는 초기 전제는 철회됐다. 원본 `a_reference/c1b1_two_atom.py`를 최적화하는 요청도
아니다. 새 독립 계층의 설계를 제안하는 단계이며 구현·차등시험·벤치마크는 시작하지 않는다.

## 1. 먼저 공개할 범위와 한계

Lab에는 일반 numeric VM/독립 반올림 판정기와 Hénon–Heiles 감사가 있지만, C1-B1
Drift/Kick oracle, C1-B1 segment guard, 독립 C1-B1 impulse 계산기가 아직 없다.
따라서 `exact_slow`도 새로 만들어야 한다. 기존 Lab oracle과 봉인 자산은 그대로 보존한다.

1차 제안은 **두 원자·3D raw 상태의 Drift/Kick exact 산술 계층**이다.
`exact_slow`는 Fraction으로 기준값을 만들고, `exact_fast`는 Drift/Kick만 정수식으로
계산한다. Guard는 exact rational로 다루며 fast impulse는 범위 밖이다.

주어진 J로 전이를 재구성해도 J가 frozen 물리식의 올바른 충격량인지는 알 수 없다.
독립 impulse 검증이 없는 결과는 **ARITHMETIC_ONLY / J_NOT_VERIFIED**로 표시한다.
전체 C1-B1 replay의 VALID, REPLAY_VERIFIED, CONFIRMED, CERTIFIED 또는 물리 정확성으로
승격하지 않는다. 기존 Regular 2-Step/V2/Gate 감사 PASS도 새 계층의 감사가 아니다.

원본 문서는 현재 위치 FX(96,48), 운동량 FX(96,80), drift v2를 채택한 후보로 기록한다.
C1-B1 전체 동결은 완료돼 있지 않다. 확인된 수치 의미와 후보의 물리·영역·실행 승인
상태를 구분한다. 이번 설계가 새 dt/profile/domain/cutoff를 승인하지 않는다.

## 2. 제안하는 두 경로와 Lab 연결 위치

아래 파일명은 향후 구현 위치 제안이며 이번에 `.py` 파일을 만들지는 않는다.

```text
independent_checker/c1b1/
    contracts.py       # Lab 소유의 순수 데이터 계약·typed 결과/거부 기록
    exact_slow.py      # Fraction 계산, 별도 nearest-even 도출
    exact_fast.py      # raw integer Drift/Kick, 원본 helper와 코드 공유 없음
    exact_geometry.py  # 새 exact 선분/저장 위치 guard; 정수 쌍 guard 최적화 없음
    compare.py         # 결과·거부·순서·endpoint·변이 여부의 차등 판정
    claim_adapter.py   # 외부 plain-data claim의 산술 검증; J 미검증 표시

tests/                 # 신규 전용 계약·차등·결함·독립성 시험
tools/                 # 승인 후 계측 도구; checker의 proof oracle이 아님
```

`independent_checker/` 아래에 두면 기존 [독립성 경계](../lab/independence.py)의 checker-side
검사 대상에 들어간다. 기존 [oracle](../independent_checker/oracle.py),
[claim 계층](../lab/claim.py), [독립성 시험](../tests/test_independence.py)을 읽고 연결한다.
기존 `numeric_core/`, `lab/claim.py`, HH/Gala Runtime Trace/IR/V2/Caller 소스를 변경하는
설계가 아니다. 새 공개 API와 결과 schema를 별도로 둔다.

개발 중 기본은 `exact_slow`, fast는 **EXPERIMENTAL / OPT-IN**이다. 두 경로는 서로의
산술·rounding·range helper를 import하지 않는다. 프로필이라는 이유로 `numeric_core`의
복사된 `_div_round`, `FixedPoint.from_exact`, add/sub를 proof oracle로 쓰지 않는다.

외부 3중 비교는 이후 다음처럼 구성한다.

```text
원본 fast_combined의 별도 실행 기록 (입력/사양/claim 데이터만 전달)
                  ↓ 외부 비교
Lab exact_fast    ↔    Lab exact_slow
```

원본 실행기는 checker 안에서 import하지 않는다. 외부 비교 도구가 원본을 별도 process에서
실행하거나 사용자가 준 기록을 읽는 일은 향후 승인된 범위에서만 한다. 동일 final raw만
비교하지 않고 입력 binding, 중간 phase, displacement, exact endpoint와 거부를 비교한다.

## 3. 공유 가능한 specification과 공유 금지 구현

| 구분 | 제안 |
|---|---|
| 공유 가능 | 수학식, 단위, 고정 decimal 상수의 정확 의미, signed FX 범위, nearest-even, drift v2의 rounding 위치, J 부호 규칙, exact guard 조건, 승인된 사양 데이터와 그 provenance |
| 원본에서 공유 금지 | executor/verifier의 함수·클래스·helper 구현, source 복사, runtime import, AST definition 추출, monkeypatch 또는 adapter로 원본 연산을 우회 호출하는 방식 |
| Lab 두 경로 사이 공유 가능 | immutable 입력/결과 schema, 사양 데이터, 순수 오류 record/container, wire parsing 정책; 별도 검증을 거친 exact geometry guard는 명시적 공통 신뢰 기반 |
| Lab 두 경로 사이 공유 금지 | drift/kick 산술 구현, rounding helper, prepared coefficients, 결과 cache, range 산술을 한쪽 oracle로 호출하는 방식 |
| 기존 Lab 자산 | 일반 독립 rounding-cell 판정기를 추가 확인 수단으로 사용 가능. 그 재사용을 새 exact_slow의 구현 독립성이나 물리 인증으로 과장하지 않음 |

특히 원본 `a_reference/c1b1_combined_arithmetic.py`, `c1b1_fast_impulse.py`,
`c1b1_impulse_primitives.py`와 `c1b1_two_atom.py`, 원본 replay/독립 감사 구현을
복사/import하지 않는다. `DriftConversionContract`, `prepare_drift`, `_div_round`,
`kick`, `CombinedRuntime`를 원본 helper로 호출하지 않는다. API 명칭도 별도로 정한다.

Spec 문서에 적힌 “원래 helper를 재사용”이라는 원본 최적화 방식은 Lab에서 채택하지 않는다.
같은 수학적 항등식을 독립적으로 구현하는 것만 허용한다. 코드가 다른 사실만으로 독립성이
완료되지는 않으며 dependency 검사와 fault injection, 별도 review가 필요하다.

## 4. 사양 근거와 동결할 경계

원본의 로컬 clean HEAD `0f7b744cf754450424a63c47f305e0327c5b37c1`에서 specification만
참고했다. AGENTS/RULES는 본문을 읽었고 CURRENT_STATE/REPO_MAP은 해당 C1-B1·계층·경로
부분만 읽었다. 전체 상태 문서를 전수 독해하거나 원본 구현을 읽어 감사한 것은 아니다.

| 자료 | 읽은 부분 / 이 설계의 근거 |
|---|---|
| [A Numeric 의미](https://github.com/opO306/success-is-mother-of-failure/blob/0f7b744cf754450424a63c47f305e0327c5b37c1/docs/reference/A_NUMERIC_EXECUTION_STACK_V1.md) | §3.1–3.5 중심: exact represented input, FX signed 범위·nearest-even·overflow halt. 전체 문서의 구현 보고는 이번 증거로 사용하지 않음 |
| [C1-B1 동역학 결정 기록](https://github.com/opO306/success-is-mother-of-failure/blob/0f7b744cf754450424a63c47f305e0327c5b37c1/docs/active/A_MICRO_V6_C1B1_TWO_ATOM_DYNAMICS_DESIGN_V1.md) | §1/4의 상태·J 부호·exact guard, §10의 drift v2, §12/14의 profile 결정, 서두의 전체 미동결 구분. 역사적 v1 rounding을 현재 v2로 혼동하지 않음 |
| [정수 항등식 논증](https://github.com/opO306/success-is-mother-of-failure/blob/0f7b744cf754450424a63c47f305e0327c5b37c1/docs/active/C1B1_PILOT2_EXACT_ARITHMETIC_ARGUMENT_V1.md) | 본문 전체: unreduced ratio, separate displacement/add checks, i-before-j, exact guard. 원본 helper 재사용 지침은 제외 |
| [원본 replay specification](https://github.com/opO306/success-is-mother-of-failure/blob/0f7b744cf754450424a63c47f305e0327c5b37c1/docs/active/C1B1_PRODUCTION_REPLAY_VERIFIER_V1.md) | 전이·wire·검증·신뢰 기반 절: 12 raw 상태, supplied J와 independently verified J의 차이, unrounded guard, fingerprint/승인 분리. 구현·성능 기록을 새 Lab의 결과로 사용하지 않음 |

해당 문서들의 실제 raw-byte SHA-256은 순서대로 다음과 같다. 문서 해시는 수령 내용의
동일성을 기록할 뿐, 그 전체가 frozen 계약이거나 수학적으로 증명됐다는 뜻은 아니다.

```text
Numeric:    0c289146d6b87ce95c530f3730bd311a96e1345a6fc5ff4a129b344e6142175e
Dynamics:   fdbd97108ad00013795983c10b30c0c7b5825ae6e92e7d2e088578861f757115
Arithmetic: 794fed764f4a1b3affb78122cdd936de7f4627f7f0f9586aa355f33b9a08a656
Replay:     848ae992452399196603f1b9068509ce1f138972f394f1ad3add2f898d12d66b
```

향후 구현 전에 이 문서에서 채택할 순수 사양만 **Lab 소유의 versioned semantic manifest**로
정리하고 설계 검토를 받는다. 원본 implementation/dependency fingerprint를 Lab의 승인으로
재사용하지 않는다. Lab의 새 spec/implementation fingerprint는 아직 PENDING이다.

## 5. 입력 계약 제안

외부 입력은 원본 클래스 객체가 아닌 plain data다. 엄격한 wire decoder는 중복 key,
float/bool, 예상 밖 field, 비정규 정수 문자열, 잘못된 vector 길이를 거부한다.
In-memory API도 `bool`을 raw int로 받아들이지 않는다.

| 필드 | 의미 / 검증 |
|---|---|
| `spec_id` / `scope` | 신규 Lab 사양 판과 `ARITHMETIC_ONLY`; 기존 replay fingerprint와 혼용하지 않음 |
| `position_grid`, `momentum_grid` | signed FX, W/F 정수, 2≤W 및 0≤F<W, nearest-even, overflow refusal, drift v2를 명시하는 immutable 값. `name`만 같은 object/duck typing은 거부 |
| `r_i`, `r_j` | 각 3개 signed raw position integer, 해당 position grid 범위 |
| `p_i`, `p_j` | 각 3개 signed raw momentum integer, 해당 momentum grid 범위 |
| `mass_i`, `mass_j` | 양의 exact rational, 단위와 source/binding을 명시. dt/m을 미리 반올림하지 않음 |
| `dt` | exact rational. 산술 kernel의 zero/negative dt 시험과 정방향 C1-B1 실행의 admissibility를 분리 |
| `J_raw`, `impulse_grid` | kick은 3개 signed raw J 및 grid identity를 요구. 각 J도 momentum grid의 signed 범위 안이어야 하며, 두 momentum 및 J의 W/F/rounding/overflow 의미가 동일해야 함 |
| `r_min_squared` / `domain_binding` | guard를 쓰는 paired drift에서는 필수인 양의 exact threshold와 사양 binding. 무근거 임의 threshold로 C1-B1 물리 domain을 선언하지 않음 |
| acquisition/record/phase IDs | 외부 claim과 비교할 때 필수. 같은 bits의 서로 다른 기록을 병합하지 않음 |

연산별 입력은 구분한다. Drift에는 r/p/mass/dt, Kick에는 p/J만 필요하며, paired guard에는
추가 domain binding이 필요하다. 사용하지 않는 물리 field를 임의 default로 채우지 않는다.

Rational wire 제안은 canonical signed numerator/positive denominator이며 서로소인 pair,
zero는 `(0,1)`로 한정하고 input boundary에서 한 번 검증한다.
Raw wire는 canonical decimal signed 문자열(leading zero/plus/`-0` 금지),
내부는 exact integer다. 정규화가 필요하면 그 비용도 계측한다. Fast 중간 비약분 pair의
표현을 wire canonical input 정책과 혼동하지 않는다.

**두 지원 수준:** generic signed-FX 산술 kernel은 검토된 W/F를 parameter로 받고,
C1-B1 canonical binding 후보는 pos=(96,48), mom=(96,80), drift v2로 별도 기록한다.
Small/wide synthetic profile은 명시적인 TEST_ONLY 산술 입력이다. 이것이 임의 physical
profile 승인은 아니다. 다른 rounding/profile kind는 첫 fast 경로에서 REFUSED한다.

같은 momentum grid가 아닌 kick은 임의 변환하지 않고 REFUSED한다. 첫 구현은 automatic
fallback도 두지 않는 안을 제안한다. 나중에 허용할 때만 explicit slow 선택과 기록을 둔다.
Range는 `[-2^(W-1), 2^(W-1)-1]`이며 wrap/saturation은 없다.

Ar40 mass의 specification은 `39.9623831237 u / 0.0005485799090441 u`라는 두 명목값의
정확한 몫이다. 이 상수를 source와 함께 manifest에 전사하는 것은 공유 가능한 사양이다.
측정 불확도는 수치 rounding error에 넣지 않는다. 물리 guard의 1.2 angstrom을 bohr로
옮기는 정확한 단위 상수/binding은 별도 spec extraction 때 확정해야 한다. 그 전에는
`r_min_squared`를 받은 수학적 guard만 정의하며 C1-B1 domain 일치 완료를 주장하지 않는다.
dt=40도 원본의 현재 후보/전이 binding 사실이며 이 Lab의 새 실행을 자동 선택하지 않는다.

## 6. 출력·거부·state mutation 계약 제안

순수 함수가 immutable 결과를 반환하고 입력 state를 전혀 변경하지 않는 구조를 제안한다.
새 Lab은 세계 state를 commit하는 실행기가 아니다. 외부 claim의 판정도 별도 record다.

| 연산 | 성공 결과 |
|---|---|
| pair Drift | 6개 exact displacement, 6개 exact endpoint, 6개 stored displacement raw, 6개 stored position raw, input/spec binding, 검사된 component 순서 |
| pair Kick | 6개 updated momentum raw, exact p±J 의미, momentum/J grid binding, 검사된 component 순서 |
| guarded Drift | 위 결과 + exact segment minimum R² 및 stored relative R²와 threshold 비교; 계산과 domain verdict를 분리 |
| claimed transition 비교 | raw/mathematical equality 또는 discrepancy 기록; scope=ARITHMETIC_ONLY 및 J_NOT_VERIFIED를 항상 표시 |

Fast는 exact 값을 `(N,D), D>0`로, slow는 Fraction으로 유지할 수 있다. 비교에서는
cross multiplication으로 유리수 값을 정확히 비교한다. 비약분 pair와 Fraction의 내부
표현 차이를 실패로 처리하지 않는다. 보관용 canonical serialization은 마지막 경계에서
약분할 수 있고, 그 변환 비용과 hash의 schema도 명시한다. 같은 public canonical artifact를
원하면 둘 다 그 경계를 거쳐야 한다. Endpoint를 float로 내보내지 않는다.

거부는 Lab 소유의 typed record/exception으로 설계한다. 예를 들어 category, stable code,
phase, atom slot, component, message를 가진다. 두 경로는 동일 class/code/context/message를
내야 한다. 원본 예외 클래스를 import해 맞추지 않는다. 외부 비교 시 category mapping은
명시적 contract로 검토하고 원본 class와 동일하다고 주장하지 않는다.

첫 제안의 순서는 다음과 같다. 이는 신규 Lab API의 제안이며, 문서에 없는 원본의 상세
예외 우선순위까지 재현했다고 주장하지 않는다. Upstream 호환성은 별도 OPEN 항목이다.

1. schema/spec/profile identity 및 모든 raw/rational/shape 검증.
2. atom i의 x/y/z, 다음 atom j의 x/y/z 순서로 산술 검사.
3. Drift 성분마다 nearest-even displacement → displacement range → r_raw+delta → position range.
4. Guarded pair Drift에서는 모든 산술 range 검사 뒤 exact segment guard, 다음 stored-position guard.
5. 모든 검사가 끝난 뒤 결과 publication. 실패 시 partial result/state commit 없음.

Kick도 i.x/y/z의 p−J, 다음 j.x/y/z의 p+J 순서다. Input validation과 operation failure의
우선순위, guard와 overflow가 동시에 발생하는 경우는 multi-fault 계약 시험으로 고정한다.
수학적으로 최종 위치가 범위 안이어도 displacement 자체가 범위를 넘으면 먼저 거부한다.

## 7. `exact_slow`: 새 기준 oracle의 제안

Stored r/p를 Fraction으로 decode하고 각 성분에서 `d=(p*dt)/mass`를 직접 계산한다.
Prepared coefficient나 fast의 pair/rounding helper를 호출하지 않는다. Exact endpoint는
`r+d`, stored 값은 아래 계약대로 계산한다.

```text
u = d * 2^Fpos
L = floor(u), H = L + 1
u와 L/H의 exact Fraction 거리를 비교
동점이면 L/H 중 even integer 선택
delta_raw range 확인, r_raw + delta_raw range 확인
```

Kick은 decode한 p와 J의 Fraction 합/차를 계산한 뒤 해당 FX grid로 다시 encode한다.
그 결과가 정수 격자 위에 있더라도 slow는 fast raw add/sub 구현을 호출하지 않는다.
기존 independent `judge_fx`는 별도의 rounding-cell 검산으로 사용할 수 있지만,
fast 결과를 `judge_fx`에 통과시킨 것을 slow 결과 생성의 대체물로 쓰지 않는다.

이 oracle은 fast가 도입돼도 삭제하지 않는다. Fast와의 동일성이 나오기 전에 oracle
자체를 손 계산·rounding cell·경계 사례와 결함 주입으로 먼저 검증해야 한다.

## 8. `exact_fast`: Drift/Kick 독립 유도

### Drift

`p=p_raw/2^Fmom`, `dt=a/b`, `mass=c/e`, b/c/e>0에서:

```text
N = p_raw * a * e
D = 2^Fmom * b * c
d = N/D
U = N * 2^Fpos
```

Python exact integer이므로 중간 overflow/wrap은 없다. Stored conversion/range를 별도로
검사한다. Gcd reduction 없이도 N/D의 의미는 같다. Fast rounding은 원본의 signed-abs
helper를 가져오지 않고, **signed floor quotient**와 nonnegative remainder에서 유도한다.

```text
U = qD + r, 0 ≤ r < D
2r < D: delta_raw=q
2r > D: delta_raw=q+1
2r = D: q가 even이면 q, odd이면 q+1
```

이 규칙은 음수 U에서도 floor q를 사용하므로 nearest-even이다. 양의 common factor g를
N/D에 곱하면 quotient는 같고 remainder와 denominator 모두 g배라 비교와 even parity가
불변이다. Zero, signed midpoint, adjacent rational에서도 약분 여부가 raw를 바꾸지 않는다.

Stored position은 **r_raw + delta_raw**다. r_raw=1, u=1/2라면 저장 결과는 1이며
round(1+1/2)=2로 바꾸면 계약 위반이다. Exact endpoint는 별도로
`r_raw/2^Fpos + N/D`를 유지한다.

첫 후보는 per-call immutable parameter에서 atom별 coefficient를 만들고 global cache나
run 사이의 prepared reuse를 하지 않는다. 미래 cache는 mass/dt/profile/spec 전체 binding을
검증하는 별도 설계다. 이번 설계가 stale prepared object의 재사용을 승인하지 않는다.

### Kick

같은 grid에서 p_i−J 및 p_j+J의 exact 값에 2^Fmom을 곱하면 각각 `p_i_raw−J_raw`,
`p_j_raw+J_raw`라는 정수다. 따라서 rounding은 identity이고 raw add/sub와 prescribed range
check로 충분하다. J를 atom별로 별도 반올림하거나 부호를 바꾸지 않는다. 모든 검사 후
immutable 6-lane 결과를 반환한다.

## 9. Exact guard와 산술 계층의 경계

새 `exact_geometry`는 원본 guard 코드를 가져오지 않고 specification에서 독립 작성하는
안이다. 이 guard는 slow/fast의 공통 내부 dependency가 될 수 있으므로 독립성 위험을
명시하고 별도로 시험한다. Fast guard 자체를 (N,D) 비교로 최적화하는 일은 이번 범위 밖이다.
Fast는 guard의 최종 호출 경계에서만 필요 Fraction을 생성한다.

q0를 initial exact relative position, q1을 **exact drift endpoints의** relative position,
v=q1−q0라 할 때:

```text
A = q0·q0, B = q0·v, C = v·v
C=0: segment minimum = A
C>0: tau = clamp(-B/C, 0, 1)
segment minimum = (q0 + tau*v)·(q0 + tau*v)
```

모든 계산은 exact rational이다. `< r_min_squared`일 때 침범, equality는 이 strict 조건의
침범이 아니다. Stored relative R²는 두 stored endpoint raw를 exact decode해 별도로
검사한다. 둘 중 하나를 생략하지 않는다. 위 tau의 clamp는 닫힌 선분에서 최솟값을 찾는
수학적 정의이며, 판정 뒤 state를 clamp·반사하거나 새 cutoff로 보정하지 않는다.

이 guard에 rounded endpoint를 전달하면 final raw가 같더라도 실패다. Slow/fast가 같은
guard를 공유한다면 둘의 agreement만으로 guard soundness가 증명되지 않는다. Hand-derived
endpoint/interior minimum 사례, threshold equality·양옆 사례, independent inequality 검사와
guard 자체 결함 주입을 별도로 요구한다.

## 10. 외부 claim/replay의 연결 제안

1차 연결은 단일 Drift/Kick의 plain-data claim 비교를 제안한다. 기존 `lab/claim.py`의
Profile/결과를 C1-B1 의미로 재해석하지 않고 별도 schema를 사용한다. 후속 연결 후보로
supplied J0/J1과 입력 raw를 받아 K–D–K 산술·guard를 재구성할 수 있다. 이 경우 각 phase와
실제 component occurrence를 보존하고 claimed intermediate/final raw를 비교한다.
Supplied J를 그대로 쓰므로 이름은 **arithmetic transition comparison**이다.
원본의 J가 맞다는 검증도, 새 independent impulse 구현도 아직 없다.

전체 C1-B1 audit step을 만들려면 먼저 독립 exact impulse, initial admission·unit/potential
binding, precision/refusal 및 record provenance 계약이 필요하다. 이들은 별도 설계/승인
범위다. Raw J를 신뢰했다고 full-step PASS를 내는 연결은 금지한다. New Layer를 existing
Regular 2-Step/Gala chain에 끼워 넣거나 그 PASS에 결합하지 않는다.

원본과의 외부 비교는 향후 동일 spec/raw/mass/dt/J 및 범위가 명시된 데이터로 한다.
원본 class identity는 입력이 아니며 원본 함수는 oracle이 아니다. Physical J가 검증되지
않은 comparison result는 scope marker를 끝까지 유지한다.

## 11. 향후 검증 계획 — 이번 실행 결과 아님

| 묶음 | 요구할 검증 |
|---|---|
| oracle 자체 | 손 계산, 별도 rounding-cell 판정, positive/negative/zero, even/odd signed ties와 exact neighbors |
| Drift differential | exact displacement/endpoint의 rational equality, stored displacement/position, min/max와 output overflow 직전/overflow, 큰 common factor, 다양한 dt/positive mass |
| profile/input | canonical 96/48·96/80, 작은 FX와 넓은 synthetic FX, bool/float/out-of-range raw, profile kind/semantic mismatch·fake object 거부 |
| Kick differential | signed/zero J, exact limits와 overflow ±1, 두 atom 전 component, 검사 순서·예외 context·입력 mutation 없음 |
| guard | exact endpoint 전달, interior minimum, rounded-only가 놓치는 침범, equality·neighbor, stored guard 분리 |
| independence | 금지 import AST 검사, clean process의 sys.modules, runtime file-access/definition extraction 우회 점검; slow/fast helper import 경계 확인 |
| external compatibility | approved data envelope에서 원본의 result/exception category/context/order를 비교. 지금은 UNVERIFIED |

다음 12종은 명단만 작성하는 것으로 끝내지 않고, 향후 mutant 실제 생성·실행·거부 결과를
남겨야 한다. Baseline PASS와 mutant detection을 구분하며 양쪽이 같은 wrong output으로
통과하면 실패다.

| # | 주입 결함 | 검출할 구분 |
|---|---|---|
| 1 | ties-away | signed even/odd midpoint |
| 2 | numerator factor 누락 | mass/dt 서로 다른 유리수, exact endpoint |
| 3 | denominator 2^Fmom 누락 | 서로 다른 Fpos/Fmom |
| 4 | mass numerator/denominator swap | nonunit positive rational mass |
| 5 | dt numerator/denominator swap | nonunit rational dt |
| 6 | round(r+d) | odd r_raw + exact midpoint |
| 7 | guard에 rounded endpoint | same stored raw에서도 exact segment 비교 |
| 8 | kick sign swap | 두 atom 및 양·음 J |
| 9 | range check 제거 | delta/final/p 범위, exact limit ±1 |
| 10 | 순서 변경 또는 early write | multi-fault first-failure context + 입력 전체 불변 |
| 11 | stale prepared coefficient | 서로 다른 mass/dt/spec의 연속 호출; 결함 cache는 production 무캐시와 별도 injected mutant |
| 12 | 다른 grid/profile 강제 fast | momentum/J mismatch 및 unsupported semantics |

## 12. 계측과 승격

지금의 실측 성능은 **NOT MEASURED**다. 원본의 Fraction/gcd 감소율·step/trajectory 속도는
새 Lab의 예상치나 benchmark 결과로 쓰지 않는다.

향후 correctness 후 동일 입력과 출력/guard 모드로 warm-up 및 실행 순서 교대 계측을 한다.
Instrumented count run과 uninstrumented wall/CPU run은 분리한다. Fraction construction,
gcd, integer multiplication/division/rounding의 **실제 관측 범위**를 기록한다. Fraction 내부
정수 연산까지 세지 못하면 direct raw 연산 count와 구분하고 불완전 total은 UNAVAILABLE로
남긴다. 정적 식에서 센 수를 실제 profiler count라고 부르지 않는다.

Micro Drift/Kick 다음에는 보존된 실제 audit 입력의 산술 전이 workload를 비교할 수 있다.
이것도 J 미검증이면 full audit workload가 아니다. 독립 impulse를 포함한 전체 audit step은
현재 **NOT AVAILABLE**이므로 full-step wall/CPU 개선 조건은 아직 충족할 수 없다.
Source/input/환경/hash, output/guard 비용, profiler overhead, 실패 결과와 분산을 함께 남긴다.

Fast 기본 승격은 다음이 모두 채워져야 한다: 유도 문서, oracle 자체 검증, differential,
midpoint/refusal/overflow, 12 mutant 검출, 기존 자산 보존, 실제 목표 audit workload 성능 이득,
별도 independent review 및 설계자 결정. 그 전에는 EXPERIMENTAL / OPT-IN을 유지한다.
기존 외부 PASS와 새 author review를 새 independent audit 완료로 간주하지 않는다.

## 13. 남은 독립성 위험과 검토할 결정

| 항목 | 제안 / 상태 |
|---|---|
| 공유 specification 자체가 틀릴 가능성 | 별도 사양 검토·provenance 필요. 다른 코드만으로 제거되지 않음 |
| Python int/Fraction 및 공통 decoder/geometry | 명시적 신뢰 기반. 두 산술 경로의 agreement만으로 공통 dependency 검증 불가 |
| 신규 Lab API의 순서·거부 class/message | §6의 제안. Source 상세 동작 호환은 OPEN이며 조용히 동일하다고 가정하지 않음 |
| generic FX와 canonical physics binding | 구분 유지. Manifest의 단위/r_min·종/parameter 전사 및 fingerprint는 PENDING |
| 기존 독립 impulse 부재 | 새로 필요한 별도 작업. 이번에는 impulse 구현/fast impulse를 시작하지 않음 |
| 성능 및 full-step workload | NOT MEASURED / NOT AVAILABLE. Benchmark만으로 승격 금지 |
| 외부 리뷰·새 구현의 인증 | PENDING / NotCertified |

추천하는 첫 구현 범위는 새 Fraction oracle + integer Drift/Kick + exact geometry의 독립
검증 + 차등/결함 시험이다. 새 사양과 phase/refusal ordering을 검토한 뒤 별도 구현 결정을
받는다. Full impulse/replay/trajectory, native/GPU, approximation/cutoff 및 기존 감사 자산의
수정은 이 문서 승인에 자동 포함되지 않는다.

이번 산출물은 **설계 제안서 한 파일**이다. 새로운 계산기 source, 테스트, benchmark,
performance claim, commit/push는 이번 단계에서 수행하지 않는다. 사용자의 최신
“바로 구현부터 시작하지 말고 먼저 … 설계 문서로 제안” 지시에 따른 범위다.
