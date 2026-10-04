# C1-B1 exact impulse certificate · 독립 checker 사양 V1

**상태:** **S1〜S4 전부 승인(설계자 판정 2026-09-29, 5차). 독립 checker와 시험 T1〜T11 구현 완료(8절). checker 신뢰 승인(설계자 판정 2026-09-29, 7차, `e9b30eb`): T1〜T11과 독립 교차검증 근거 수용, parser robustness 보강은 현 단계에서 종료.** 남은 거대 문자열 O(N) 읽기는 checker가 아니라 runtime wrapper의 certificate 전체 바이트 크기 상한으로 막는다(wrapper 단계 과제). point prover generator·wrapper·Proof Cache는 미구현. A-EV 미해결, ④-Safety Conditional, ④ 전체 Certified/Frozen 아님.
**원칙(설계자 판정 문장):** *Operational limits affect availability, never truth.* 운영 한도는 "검증할 수 있었는가"만 바꾸며 "참인가 거짓인가"는 바꾸지 않는다. 한도 초과는 REFUSED이지 INVALID가 아니다.
**근거:** [Lemma A·B 감사](C1B1_ROUNDING_LIVENESS_LEMMAS_AB_AUDIT_V0.md)(accepted design basis, not frozen certificate), [Runtime Rounding Contract V1](C1B1_RUNTIME_ROUNDING_CONTRACT_V1_PROPOSAL.md) 1·4·7절, P1a/P1b 판정.
**현재 상태(변경 없음):** ④-Liveness NotCertified, ④-Safety Conditional(A-EV), 14/64·gap 81, ④ 미동결, ⑤ 미착수. 기존 shell 인증서는 삭제·무효화하지 않고 교차검증 자료로 쓴다.

## 0. 한 줄

checker는 certificate 하나를 받아 **VALID(m) / INVALID(이유) / REFUSED(운영 한도)** 중 하나만 돌려준다.
VALID(m)의 뜻: "동결 C1-A 모델의 정확한 충격량 성분 J_k를 FX(96,80)로 반올림한 raw는 m이다." 이 판정은 정수·유리수 산술만으로 내리며, 어떤 수치 평가기의 결과도 믿지 않는다.

## 1. checker가 보는 것 / 보지 않는 것

| 본다 | 보지 않는다 |
|---|---|
| certificate JSON(아래 2절) | 실행기 상태, run, J_cache, D_valid |
| checker 파일 안에 **직접 적은** 동결 모델 상수표(십진 문자열) | `a_reference`, `a_numeric`의 어떤 모듈(import 금지) |
| 표준 라이브러리 `fractions`, `hashlib`, `json`, `math`, `time`(시간 한도용. 사양 초안의 4개에 `time` 추가, 8절) | numpy·mpmath·sympy·부동소수점 |

**책임 분리:** checker는 **수학적 주장의 참/거짓**만 판정한다. certificate의 입력이 실행기가 실제로 계산한 입력과 같은지, 실행기·모델 소스와 profile·dt가 같은지(binding, 계약 V1 7절)는 **runtime wrapper·Proof Cache의 책임**이다. checker는 `runtime_binding`을 읽지 않는다.

## 2. certificate 형식 (`c1b1-exact-impulse-certificate-v1`)

유리수는 `"분자/분모"` 문자열, 정수는 십진 문자열로 쓴다. **모르는 키가 있으면 INVALID**다(형식 혼동 방지).

```json
{
  "format": "c1b1-exact-impulse-certificate-v1",
  "method": "rational-taylor-geomtail-v1",
  "model":  {"contract": "c1a-ar2-lang2024-v1",
             "parameter_fingerprint": "ada6153be05af3e582139fdc81b5697fffaf18d12f9f2de6e8d5ac2fdfe0839e",
             "retardation": true},
  "input":  {"position_frac_bits": 48, "dr_raw": ["…","…","…"], "component": 0, "dt_kick": "20/1"},
  "output": {"width": 96, "frac_bits": 80, "raw": "…"},
  "proof":  {"sqrt_bits": "N",
             "exp": [{"rate": "λ", "mode": "full" | "zero_floor", "order": "n"}, … 9개]},
  "runtime_binding": { … 계약 V1 7절 필드 + checker_sha256 … }
}
```

- `dr_raw`: 상대 위치 raw 정수(r_j − r_i). dr = dr_raw·2^-48.
- `exp`: 아래 3.3의 **고정 순서** 9개. 각 rate는 checker 상수표의 정확한 유리수와 같아야 한다.
- certificate에는 **매개변수만** 담는다(N, 각 exp의 모드·차수). 중간값은 넣지 않는다. checker가 매개변수에서 결정적으로 다시 계산한다.

## 3. checker 절차 (규범)

모든 값은 정확한 유리수 닫힌 구간 [lo, hi]다. 반올림하지 않는다.

### 3.1 모델 binding
1. checker 내장 상수표로 `parameter_fingerprint`를 **C1-A와 같은 문자열 형식**으로 다시 계산한다. 형식은 `ar2_lang2024.parameter_fingerprint`의 구성과 같게 문서화해 옮긴다. SIGMA 상수도 해시에 들어가므로 함께 적는다.
2. 계산값 = checker 안의 동결 리터럴 `ada6153b…839e` = certificate의 값이어야 한다. 하나라도 다르면 INVALID(`model_binding`).
3. `contract == "c1a-ar2-lang2024-v1"`, `retardation == true`(v1은 ON만).

### 3.2 입력
4. `position_frac_bits == 48`, component ∈ {0,1,2}, dt_kick ≠ 0.
5. `dr_raw[k] == 0` → INVALID(`not_a_decision`). 실행기는 이 성분을 판정하지 않고 정확히 0을 낸다.
6. R² = Σ dr_i². R²·(529177210903/10¹²)² < (6/5)²이면 INVALID(`physics_domain`). 실행기에서는 판정 전 `PhysicsDomainExceeded`인 경우다.

### 3.3 √ 구간
7. N은 정수, 1 ≤ N ≤ N_MAX. a = isqrt(⌊R²·4^N⌋), r_lo = a/2^N, r_hi = (a+1)/2^N.
8. 확인: r_lo > 0, r_lo² ≤ R² ≤ r_hi²(정확 비교). R_iv = [r_lo, r_hi].

### 3.4 exp 구간 (Lemma B, 정정된 표현)
고정 순서: BO short 1(6.92639712), BO short 2(2.34781022), REL short 1(1.66833595), REL short 2(3.07137482), QED short 1(1.64936036), QED short 2(2.29848003), BO long η(3.65946625), REL long η(1.05249333), QED long η(3.91638946).

각 rate λ에 대해 x_lo = λ·r_lo, x_hi = λ·r_hi, n = order(0 ≤ n ≤ n_MAX)로 둔다.
S_n(y) = Σ_{k≤n} y^k/k!, t_{n+1}(y) = y^{n+1}/(n+1)!, U_n(y) = t_{n+1}(y)·(n+2)/(n+2−y)이다.

| 모드 | 조건 | E(λ) = e^{−λR} 구간 | 근거 |
|---|---|---|---|
| `full` | n+2 > x_hi | [1/(S_n(x_hi)+U_n(x_hi)), 1/S_n(x_lo)] | 0 ≤ e^y−S_n ≤ U_n(기하급수 꼬리), e^{−x} 감소 |
| `zero_floor` | 없음 | [0, 1/S_n(x_lo)] | e^{−x} > 0, S_n ≤ e^{x} |

조건을 어기면 INVALID(`exp_condition`)다. **Liveness 증명(Lemma B의 수렴)은 `full`만으로 성립한다.** `zero_floor`는 항상 건전한 운영 지름길이다. 큰 x에서 대부분의 항은 ulp보다 훨씬 작아 하한 0으로 충분하고, n이 작으면 1/S_n ≤ n!/x^n이 매우 작다. 예: x ≈ 7×10⁴이면 `full`은 수십만 항이 필요하다.

### 3.5 dV/dR 구간 (동결 `ar2_lang2024._component`, deriv=True, retardation ON과 같은 식)

구간 규칙: 덧셈·뺄셈은 끝점별, 곱셈은 네 곱의 min/max, 나눗셈은 **lo > 0인 구간으로만**(아니면 INVALID). R^m은 m ≥ 0이면 [r_lo^m, r_hi^m], m < 0이면 [r_hi^m, r_lo^m]. 유리수 상수 c와 곱할 때는 부호에 따라 끝점을 바꾼다.

```
dV/dR = Σ_{comp ∈ BO,REL,QED} [ Σ_{short (α, P)} E(α)·(P'(R) − α·P(R))
                                − Σ_{k ∈ C_comp} C_2k · ( dD_k·R^{−2k} − 2k·D_k·R^{−2k−1} ) ]

x = η_comp·R,   n_k = 2k + kadd_comp,   Σ_k = Σ_{i≤n_k} x^i/i!,   T_k = E(η_comp)·Σ_k
base_k = η_comp · E(η_comp) · x^{n_k}/n_k!
  BO,  k = 3 (kmin):  D_k = g(R) − T_k,   dD_k = base_k + g'(R)
  REL, k = 2 (kmin):  D_k = −T_k,          dD_k = base_k
  그 밖:              D_k = 1 − T_k,       dD_k = base_k
g = Nr/Dn,  Nr = 1 + Σ_{m=0..4} A_m R^{m+1},  Dn = 1 + Σ_{m=0..5} B_m R^{m+1}
g' = (Nr'·Dn − Nr·Dn') / (Dn·Dn)
kadd: BO 1, REL 0, QED 0.   kmin: BO 3, REL 2, QED 3(QED는 특수 분기 없음)
```

같은 R_iv·x·E(η)를 여러 번 쓰므로 구간이 과대평가된다(의존성). 그래도 건전하고, 입력 폭 → 0이면 폭 → 0이다.

### 3.6 충격량과 판정
9. G = −(dV/dR) × [1/r_hi, 1/r_lo], J = G × (dr_k·dt_kick)(스칼라, 부호에 따라 끝점 교환).
10. u = 2^-80, m = output.raw. **(m − ½)·u < J.lo 그리고 J.hi < (m + ½)·u**(엄격)이고 −2^95 ≤ m ≤ 2^95 − 1이면 **VALID(m)**.
    구간이 경계에 닿거나 걸치면 INVALID(`not_separated`), 다른 칸이면 INVALID(`raw_mismatch`), 범위 밖이면 INVALID(`out_of_range`)다.
    엄격 분리이므로 tie 규칙(half-even)은 판정에 쓰이지 않는다. tie 불가능은 Lemma A다.

### 3.7 운영 한도
N_MAX, n_MAX, 유리수 크기(비트) 상한, 시간 상한을 넘으면 계산을 멈추고 **REFUSED(`operational_limit`)**를 돌려준다. 이것은 참/거짓 판정이 아니다. **정수 문자열 크기 규칙(구현 뒤 추가, 아래 8.5):** 문법이 틀린 문자열(정규 십진 정수 형태가 아님)은 길이와 상관없이 **INVALID**. 문법이 맞지만 십진 자릿수가 `digits_max`(기본 4300)를 넘으면 변환하지 않고 **REFUSED(`integer_size_limit`)**. 프로세스의 Python `int()` 변환 한도가 더 엄격해 `ValueError`가 나는 경우도 같은 REFUSED다(자원 한도이지 certificate의 성질이 아니다). **보장 범위(좁게):** 지원되는 certificate 입력과, 시험한 적대적 입력(초대형 정수 문자열, 잘못된 크기의 리스트·딕셔너리)에서는 `int()` 변환 `ValueError`를 포함한 Python 예외가 checker 밖으로 나가지 않는다는 것을 시험했다. **모든 가능한 Python 예외에 대한 형식적 보장은 아니다.** `check_certificate`는 `_Invalid`, `_Refused`, `MemoryError`만 잡으며, 광역 `except Exception`은 일부러 넣지 않았다(프로그래밍 버그가 REFUSED로 숨어 독립 checker의 감사성이 떨어지므로. 시험 T11이 이를 고정한다).

**Operational limits affect availability, never truth.** 한도를 올리거나 내려서 바뀌는 것은 REFUSED ↔ VALID/INVALID뿐이며, VALID↔INVALID는 바뀌지 않는다(시험 T9). 예: 한도 4096에서 REFUSED, 8192에서 VALID(123)는 가능하지만 4096에서 INVALID는 불가. 기본값은 구현 단계에서 정해 결과에 기록한다(8절). Liveness의 정량 상한이 아니라 설계자 판정의 operational bound다.

## 4. 건전성과 완결성

- **건전성:** 3.3〜3.5의 각 구간은 참값을 포함한다(Lemma B의 부등식과 구간 산술의 포함 단조성). 따라서 J_k ∈ [J.lo, J.hi]이다. 10의 엄격 분리에서 정확한 반올림 결과는 m이다. 평가기를 믿지 않으며 A-EV에 의존하지 않는다.
- **완결성(정성):** R ≥ r_min이고 dr_k ≠ 0인 모든 입력에 대해 `full` 모드의 어떤 유한 (N, n₁…n₉)가 VALID를 만든다(Lemma A + B, 운영 한도 무시). 상한은 주지 않는다.
- **주의:** checker 식이 동결 모델과 다르게 옮겨지면 "다른 함수의 건전한 certificate"가 된다(감사 B1). 이것은 시험으로만 막는다(5절). 식 전사의 형식 증명은 없다.

## 5. 구현 단계 시험 의무 (3단계)

| # | 시험 | 잡아야 하는 것 |
|---|---|---|
| T1 | 정적 import 검사(AST): 표준 라이브러리 5개(`fractions`, `hashlib`, `json`, `math`, `time`) 외 import 0, `a_reference`·`a_numeric` 문자열 import 0 | P1b 독립성 위반 |
| T2 | 내장 상수표 지문 = `ar2_lang2024.parameter_fingerprint()`(시험에서만 import) | 상수 전사 오류 |
| T3 | **교차검증:** 실행기가 RESOLVED하는 입력 수천 개(안쪽 R 2.3〜20 3D, 바깥 shell 0〜26, x·y·z축, 기울어진 방향, 65 multi-output 점, shell 15〜18 hard-case 후보 표본, shell 24〜26 후보 3개). prover 대용 두 배 탐색으로 certificate를 만들고 checker VALID raw = 실행기 raw | 식·분기 불일치 |
| T4 | **식 결함 주입**(checker 사본 변형): short 계수 부호, α 한 자리, `kadd` 0/1 교환, BO/REL retardation 분기 교환(g−T ↔ 1−T ↔ −T), `2k` → `k`, `P'−αP` → `P'+αP`, g' 분자 부호, dt·성분 인수 누락 | T3에서 raw 불일치 또는 INVALID로 **반드시** 잡힘. 안 잡히는 변형이 있으면 그 변형을 잡는 입력을 T3에 추가 |
| T5 | exp 부등식 단위 시험(시험에서만 mpmath 고정밀): 다양한 (y, n)에서 1/(S_n+U_n) ≤ e^{−y} ≤ 1/S_n, `zero_floor` 상한. 변형 U_n의 (n+2)→(n+1), 꼬리 항 하나 빠뜨림, x_lo/x_hi 교환 | 나머지 상한·단조성 오류(교차검증에서 안 보일 수 있는 경계 근처 결함) |
| T6 | √ 변형: r_hi = r_lo, a−1 | 구간이 참값을 놓치는 결함 |
| T7 | 음성 시험: raw ±1, dr_k = 0, R < r_min, 모르는 키, 지문·rate·순서 변조, N 너무 작음(`not_separated`), full 조건 위반, 범위 밖 raw | 각각 의도한 이유로 INVALID |
| T8 | **rehearsal:** 실행기 cap을 128로 낮춰 STOP한 입력에서 두 배 탐색 → certificate VALID → raw = cap 16384 정상 실행 결과. 폭이 N·n 증가에 따라 줄어드는지 기록 | 수렴·재개 경로 |
| T9 | 운영 한도: 한도 초과는 REFUSED이고 VALID·INVALID가 아님 | 한도가 참/거짓을 오염시키지 않음 |
| T10 | 초대형 정수 문자열(4300/4301/10000자리 이상)을 모든 큰 정수 필드에 주입: 정의된 verdict만(시험한 입력에서 `int()` 변환 예외 유출 0; 모든 예외에 대한 보장은 아님). 문법 오류는 크기보다 먼저 INVALID | `int()` 자릿수 한도의 `ValueError` 유출(구현 뒤 검토에서 발견) |
| T11 | 형식이 이미 틀린 큰 certificate의 파서 작업량: `dr_raw`가 3개가 아니거나 `exp`가 9개가 아니거나 키가 너무 많으면 원소를 하나도 훑지 않고 즉시 INVALID(100만 개 리스트·딕셔너리, 순회 횟수 0). 광역 `except` 부재 고정 | 사전 통과가 틀린 크기의 리스트를 전부 순회하던 것(리뷰에서 발견), 시계(`ctx.tick`) 없는 O(N) 작업 |

추가(선택, 증명 아님): 실행기 `_model` 구간과 checker 구간이 겹치는지 대조하는 A-EV spot-check. 겹침은 둘 다 참값을 포함하는 데 필요한 조건일 뿐이며 A-EV 증명이 아니다. ④-Safety Conditional은 그대로다.

## 6. 설계자 확인 요청

| # | 질문 | 구현자 의견 |
|---|---|---|
| S1 | `zero_floor` 모드를 v1에 포함할지 | **승인·포함.** 건전하고, 큰 R에서 `full`의 비용(수십만 항)을 없앤다. Liveness 증명은 `full`에만 의존한다고 명시한다 |
| S2 | certificate에 매개변수만 담고 checker가 재계산하는 방식 | **승인·채택.** 중간값을 담으면 크기만 커지고 checker는 어차피 다시 계산해야 한다 |
| S3 | checker 상수표를 checker 파일에 직접 적고, 지문 일치로 동결 상수와 묶는 방식 | **승인·채택.** T2는 필수(상수표·지문을 시험에서만 동결 원본과 만나게 함) 평가 코드 공유 없이 상수 동일성을 보장한다 |
| S4 | 운영 한도 기본값을 구현 단계에서 정해 기록 | **승인·채택.** 조건: 한도 초과 = REFUSED ≠ 증명 실패 ≠ 틀린 certificate. 변경은 결과 기록에 남긴다 |

## 7. 이번에 하지 않은 것

checker·prover·wrapper·Proof Cache 코드, 시험, Vast 사용. 기존 shell 인증서·coverage·실행기·D_valid 변경 없음.

## 8. 구현 결과 (2026-09-29)

**파일:** `a_reference/c1b1_exact_impulse_checker.py`(checker, 표준 라이브러리만), `a_reference/c1b1_exact_impulse_search.py`(매개변수 탐색, **시험 보조·신뢰 대상 아님**, point prover 아님),
`a_reference/c1b1_exact_impulse_crosscheck.py`(T3 캠페인 드라이버 + mpmath 세 번째 기준 구현), `tests/test_c1b1_exact_impulse_checker.py`(185개: 최초 구현 127개 + T10 35개 + T11 23개, 8.5·8.6). 실행기·C1-A 평가기·동결 fixture·기존 인증서 변경 0.

### 8.1 시험 T1〜T9 결과

| # | 결과 |
|---|---|
| T1 | AST로 import 집합이 {fractions, hashlib, json, math, time}와 정확히 같고 평가기 이름(`_model`, `enclosure`, `impulse`, `_decide` 등) 참조 0. 공유 import를 심으면 검사가 보는 것도 확인 |
| T2 | 상수표 전체(단·장거리·RET·SIGMA·상수)가 동결 원본과 Fraction 단위로 같고, `fingerprint()` = `L.parameter_fingerprint()` = 리터럴. 상수를 일부러 틀린 변이 6종은 전부 `model_binding`으로 거부 |
| T3 | **교차검증: 14,102건 판정에서 checker VALID raw = 실행기 raw, 불일치 0, INVALID/REFUSED 0.** 내용은 아래 8.2 |
| T4 | 식 결함 주입 **40종**(부호, α, kadd, retardation 분기·g′·계수, 2k, 거듭제곱, 슬롯, dt, 성분, 단위 등 + 고차 항에만 걸리는 국소 변이 5종) 전부 잡힘. 전부 `raw_mismatch`(값이 실제로 달라짐)로 잡혔고, `R squared unit`만 `exp_condition`으로 잡힘. 엉뚱한 예외로 "잡힌" 경우는 없다 |
| T5 | exp 구간이 mpmath 450자리 기준 참값을 포함(7개 x 구간 × 3개 차수, 위반 0), 차수와 함께 폭이 줄어듦. zero_floor 건전·양수. 결함 주입 5종(꼬리 삭제, 기하 인수 삭제, 양끝 뒤바뀜 2종, 급수 한 항 부족) 전부 잡힘. 조건(n+2 > x) 완화 변이는 두 군데를 모두 없애야 통과하며 기대한 INVALID를 못 냄 |
| T6 | √ 구간이 근을 포함하고 폭 = 2^-N(엄밀). 변이 3종 잡힘. 구간 산술 포함성(add/sub/mul/div/scale) 변이 4종 잡힘. 경계에 닿는 구간은 절대 VALID가 아님(엄격 부등호를 `<=`로 바꾸면 접촉 구간을 받아들임을 확인) |
| T7 | 음성 27종 + 미지·누락 키, 슬롯 뒤바뀜, 너무 거친 N, 잘못된 차수 전부 의도한 이유로 INVALID. 잘못된 exp 차수로는 틀린 raw가 VALID되지 않음 |
| T8 | **rehearsal 두 종.** (a) 실행기를 cap 128로 낮추면 near-tie 입력이 `ReferenceUndecided`로 멈추고, certificate가 full-cap 실행기와 같은 raw를 증명. 필요한 √ 비트가 경계에 가까울수록 커짐(단조 비감소), 너무 작은 N은 INVALID. (b) 실제 궤적(e=9 De, b=Re/2, 200 step)에서 cap 128이 거부한 충격량 전부를 certificate가 full-cap raw로 증명 |
| T9 | 한도 4종(√ 비트, 차수, 크기, 시간) → REFUSED, 한 단계 느슨하면 수학적 판정. 한도 사다리에서 VALID↔INVALID 전환 0. 구조가 틀린 certificate는 한도와 무관하게 INVALID |

### 8.2 교차검증 캠페인 (survey_only, 로컬 5 워커, 1,123초, Vast 미사용)

`runs/c1b1_exact_impulse_crosscheck_20260929/{records.jsonl, summary.json, campaign.log}`. 10,191개 입력 → 14,102개 성분 판정:
안쪽 R 2.27〜20(3D) 2,999 · 축/대각 방향 R 2.27〜10⁴ 1,200 · 바깥 R 20〜10,240 2,100 · 먼 점(최대 2^40 bohr) 18 · multi-output 65점 65 · hard-case 후보 shell 18/17/16 **전부** 109/827/6,581 · shell 24〜26 후보 3 · **near-tie 200개 × 성분 1 = 200(경계에서 2^-10, 2^-30, 2^-60, 2^-100, 2^-140 ulp, 위/아래 각각)**.
결과는 **14,102/14,102 일치**, 불일치·INVALID·REFUSED 0. `sqrt_bits`는 128비트 14,023건, 256비트 79건이다. 256비트가 필요했던 것은 **전부 near-tie**이다(경계 2^-60에서 8/40, 2^-100에서 31/40, 2^-140에서 40/40). 안쪽·바깥·hard-case·65점은 전부 128비트로 충분했다.
가장 큰 정수는 1,030,452 bit(R≈20 안쪽), 단일 certificate 비용은 안쪽 평균 약 1.0초, 축 약 0.6초, 바깥 약 0.5초, hard-case 약 0.02초, near-tie 2^-100/2^-140 약 5.7초.
비고: shell 25에는 후보가 없다(3개 = shell 24의 2 + shell 26의 1). hard-case 후보 7,517건은 실제로 경계에 가깝지 않은 **거짓 후보**라 분리 능력을 시험하지 못한다. 분리 능력은 near-tie 표본이 시험한다.

### 8.3 운영 한도 기본값 (S4, 구현 시 기록)

`sqrt_bits_max=4096`, `order_max=20000`, `bits_max=8,000,000`(최대 관측 정수 크기의 약 8배), `seconds_max=300`, `digits_max=4300`(정수 문자열 자릿수. CPython 기본 변환 한도와 같은 값이며, 프로세스 한도가 더 엄격하면 그것도 REFUSED로 처리, 8.5). 관측은 위 캠페인뿐이며 신성한 상수가 아니다. 바꿔도 VALID/INVALID 의미는 변하지 않는다.

### 8.4 사양과 달라진 점, 그리고 남은 한계 (먼저 공개)

1. **표준 라이브러리에 `time` 추가.** 시간 한도(REFUSED)를 위한 것이다. 시간 한도는 결과가 실행 속도에 의존하는 유일한 지점이며 가용성만 바꾼다.
2. **보조 함수 분리:** `_sqrt_interval`, `_decide_raw`를 함수로 뺐다(T6·경계 접촉 의미를 직접 시험하려고). 판정 로직 변경은 없다.
3. **수 표현:** 작은 구조 값(position_frac_bits, component, width, frac_bits)은 JSON 정수, 큰 값(dr_raw, raw, dt_kick, sqrt_bits, order, rate)은 문자열이다. `component: true`처럼 bool은 거부한다.
4. **exp 조건 확인이 두 곳**(`_check`와 `_exp_interval`). 한 곳만 없애는 변이는 다른 곳이 잡으므로 T5는 두 곳을 함께 없앤다.
5. **상수 오류에 대한 두 겹의 방어와 그 한계.** 지문을 우회해도 교차검증만으로 상수 오류 19건 중 18건이 R=2.5에서 잡혔다(2^-80 출력 격자라 안쪽에서는 모든 항이 raw에 보임). **예외 하나:** 마지막 자리를 바꾼 `RET_B[5]`(8.77e-15, retardation 분모의 R⁶ 계수)는 R≤450의 어떤 표본에서도 안 보인다. 이 상수는 **지문(과 T2 표 동등성)만이 막는다.** 시험으로 고정했다.
6. **식 전사 충실도는 시험으로만 보장한다.** 형식 증명은 없다. 40종 변이가 전부 잡혔지만, 목록에 없는 종류의 오류가 없다는 증명이 아니다. 실행기와 mpmath 두 다른 구현과 14,102건이 일치한 것이 근거다. 세 구현은 같은 상수표(T2로 원본과 묶음)를 쓴다.
7. **A-EV는 그대로다.** checker는 실행기 enclosure의 참값 포함성을 증명하지 않는다. ④-Safety는 Conditional이다. 이 결과는 실행기 enclosure와 독립 구간이 모순 없이 같은 raw를 준다는 14,102건의 관측적 대조일 뿐이며 A-EV의 증명이 아니다.
8. **정성 Liveness(Lemma A+B)는 checker가 아니라 수학적 논거에 기댄다.** 캠페인의 모든 입력이 `sqrt_bits ≤ 256`에서 VALID였다는 것은 수렴 논거와 일치하는 관측이며, 필요한 정밀도의 상한이 아니다.
9. **point prover generator·wrapper·Proof Cache는 미구현.** 매개변수 탐색기는 부동소수점 추정으로 차수를 고르는 시험 보조이고 checker가 판정한다(잘못 고르면 INVALID일 뿐).
10. **VMHalt 정리(예외 분류)와 trajectory-completion은 이번 범위 밖**(각각 ④ 동결 전 정리, Q4 분리).

### 8.5 초대형 정수 문자열 수정 (2026-09-29, `e6a377d` 뒤 검토 지적)

**결함:** 4301자리 이상의 십진 문자열이 `raw`, `dr_raw`, `sqrt_bits`, `order`, `dt_kick`(그리고 `rate`)에 있으면 Python `int()`의 변환 한도(기본 4300자리) 때문에 `ValueError`가 checker 밖으로 새어 나갔다. 4300자리 이하는 정의된 결과였다. 재현으로 확인했다(다섯 필드 × 4301·10000자리 모두 유출). 이전 시험(T7·T9)에는 이 경우가 없었다.
**수정:** 정수 파싱을 구문 검사(`_int_syntax`)와 변환(`_big_int`)으로 나눴다. 구문 오류는 INVALID, 구문이 맞고 자릿수 > `digits_max`이면 REFUSED(`integer_size_limit`), 구문 검사 뒤 `int()`가 `ValueError`를 내면(프로세스 한도가 더 엄격한 경우) 그것도 REFUSED. 변환 전에 모든 필드의 구문·키 구조를 먼저 훑는 사전 통과(`_prepass`)를 넣어 **구문 오류는 크기 한도에 가려지지 않는다.**
**분류 규칙(요약):**

| 입력 | 결과 |
|---|---|
| 정규 십진 정수 형태가 아님(길이 무관: 문자, 공백, 부호 중복, 선행 0, 비ASCII 숫자, 분모 0 등), 키 구조 오류 | INVALID(`bad_integer:*`, `bad_rational:*`, `keys:*`) — 항상 크기 판정보다 먼저 |
| 구문이 맞고 자릿수 ≤ `digits_max` | 종전과 같이 수학적 판정(범위 밖 raw는 INVALID `out_of_range` 등). 이 수정이 VALID/INVALID의 의미를 바꾸지 않는다(4300자리 결과가 수정 전과 같음을 시험으로 고정) |
| 구문이 맞고 자릿수 > `digits_max`, 또는 프로세스 `int()` 한도 초과 | REFUSED(`integer_size_limit`) — 가용성 한도이며 참/거짓에 대한 말이 아님 |
| Python `int`가 문자열 대신 들어온 경우, 작은 필드(component 등)에 큰 Python 정수 | INVALID |

**의도적 선택(먼저 공개):** `raw`와 `dr_raw`는 30자리만 넘어도 범위 밖이라 INVALID임을 자릿수만으로 알 수 있지만, 규칙을 하나로 유지하려고 자릿수가 `digits_max`를 넘으면 REFUSED로 답한다. 한도를 넉넉히 올리면 INVALID가 된다(REFUSED ↔ INVALID는 허용되는 변화). 어느 쪽도 VALID로 바뀌지 않는다.
**남은 한계:** `digits_max` 이하의 큰 `dt_kick`(수천 자리)은 실제로 계산하며(계산 비용은 `bits_max`·`seconds_max`가 REFUSED로 막는다), `digits_max`는 관측 없이 CPython 기본값을 따른 것이다. 크기 관련 다른 경로(`sqrt_bits`, `order`, 정수 크기)는 기존 한도가 그대로 막는다.

### 8.6 파서 작업량 보강 (2026-09-29, `1215b9c` 뒤 검토 지적)

**결함(재현 확인):** 사전 통과(`_prepass`)가 `dr_raw`와 `proof.exp`를 길이 확인 없이 먼저 전부 순회하고, 길이 검사(3개, 9개)는 그 뒤 본 검사에서 했다. 그래서 길이가 틀려 INVALID가 확정된 100만 원소 리스트도 100만 개를 모두 훑었다(각각 0.3초, 1.1초). 같은 종류로, 키 검사(`set(d)`)도 키가 100만 개인 딕셔너리를 전부 훑었다. 사전 통과에는 `ctx.tick()`도 없다. 수학적 soundness 문제는 아니다(VALID를 잘못 내지는 않는다). 가용성·작업량 문제다.
**수정:** 모양을 내용보다 먼저 본다. `dr_raw`는 리스트가 아니거나 길이가 3이 아니면(`input`), `exp`는 리스트가 아니거나 길이가 9가 아니면(`exp_list`), 딕셔너리는 키 개수가 요구+선택 키 수를 넘으면(`keys:*`) 원소를 보지 않고 INVALID. 그 뒤에야 최대 3+9개 항목의 문자열 구문을 본다. 사전 통과의 작업량은 형식(고정 크기)이 정하고 malformed certificate의 크기가 정하지 않는다(문자열 자체를 한 번 읽는 비용 제외). 100만 원소에서 순회 0회, 즉시 INVALID를 계수 컨테이너로 시험한다.
**부수 효과:** 여러 문제가 한 certificate에 겹칠 때 보고되는 이유가 바뀔 수 있다(모양 오류가 `model_binding` 등보다 먼저). 판정 자체(INVALID)와 VALID/INVALID의 수학적 의미는 바뀌지 않는다.
**문구 정정:** 8.5절 수정 때 사양 3.7절에 적었던 "어떤 Python 예외도 checker 밖으로 나가지 않는다"는 코드가 보장하는 것보다 강한 표현이어서 위 보장 범위로 좁혔다. 광역 `except Exception`을 넣지 않은 것은 의도적이다(T11에서 AST로 고정: 잡는 것은 `_Invalid`, `_Refused`, `MemoryError`와, 구문 검사 직후의 `int()` 변환 가드 `ValueError` 하나뿐).
**남은 한계:** 문자열 원소 하나가 극단적으로 길면(예: 수억 자) 그 문자열을 한 번 읽는 O(길이) 작업은 남는다(입력이 이미 메모리에 있다). `digits_max` 초과 여부는 한 번의 `isdigit` 뒤에 판정하므로 사전 통과는 시계로 끊지 않는다.

