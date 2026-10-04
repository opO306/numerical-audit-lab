# B1 — Lab canonical semantic bundle

- status: DESIGN CONDITIONS ADDRESSED / IMPLEMENTATION STILL NOT STARTED / REVIEW PENDING
- version: 1, 2026-10-04; audited design snapshot `023b186c0e9d95c11399893e7f75772cfff6c3a7`의 후속 저자 사양
- dependencies: B2–B8; [canonical bundle](../../specs/c1b1-independent-impulse-v1/semantic-bundle.json)
- unresolved items: 독립 closure 승인; 새 구현 전사/soundness 검증
- what this does NOT certify: production 구현, 모든 입력의 finite-budget 성공, 물리 정확성, J verification, integration/trajectory/replay/N-Step, certification.

기존 [감사 대상 설계](../C1B1_INDEPENDENT_IMPULSE_V1_DESIGN.md)는 역사적 snapshot으로 보존한다. 이 후속 사양은 지정한 항목에 한해 옛 제안/U1–U8을 대체하며, 독립 closure 재검토의 `IMPLEMENTATION MAY START` 판정 전 소스 구현을 허용하지 않는다.

## 발급한 데이터와 ID

Lab-owned ID는 `lab-c1b1-independent-impulse-v1-retarded-ar40`다. immutable semantic data의 SHA-256은:

```text
a179dcfc065931d09ba4f364d159416ede4b9090a0924bf3fcc119815ed4266f
```

canonical bytes는 ASCII JSON, lexical key sort, compact `,`/`:` separator, `ensure_ascii` escape, 마지막 LF 한 개다. BOM/공백/중복 key/NaN/Infinity는 없다. 정수는 canonical decimal string, 분수는 `{"n":"…","d":"…"}`다. bundle 자체 hash는 자기 hash 필드를 넣지 않은 정확 bytes의 SHA-256이다. 원본 implementation SHA, legacy fingerprint, source Merkle proof와 구별한다. [manifest](../../specs/c1b1-independent-impulse-v1/package-manifest.json)는 8개 사양의 hash를 묶는다. human 문서의 규칙은 함께 심사하는 규범이며 이후 어느 규범 bytes가 바뀌면 package revision과 새 review target을 발급한다. 현재 canonical hash가 human 문서 전체를 자동으로 해시했다는 주장은 하지 않는다; 전체 파일 해시는 author receipt에 있다.

## 선택한 물리·수치 의미

Ar40 두 원자, nominal exact decimal Lang2024 BO+REL+QED, retardation ON을 선택한다. P0의 floating underflow/finite-loop 종료나 cutoff는 물리 의미에 포함하지 않는다. σ는 모델 불확도이며 nominal V/J에 더하지 않는다. constants source/hash/indices/units는 B2다.

```text
q = r_j - r_i; R² = Σ q_k²; R = sqrt(R²)
P_cj(R) = Σ_i a_cij R^i
T_ck(R) = exp(-η_c R) Σ_l=0..(2k+kadd_c) (η_c R)^l/l!
g(R) = N(R)/D(R)
N=1+Σ_m=1..5 A_m R^m; D=1+Σ_m=1..6 B_m R^m
g′=(N′D-ND′)/D²
D_ck = g-T (BO k=3), -T (REL k=2), 1-T (otherwise)
b_ck = η_c exp(-η_c R)(η_c R)^(2k+kadd_c)/(2k+kadd_c)!
D′_ck = b_ck + g′ (BO k=3), b_ck (otherwise)
V = Σ_c [Σ_j exp(-α_cj R)P_cj - Σ_k C_c,2k D_ck R^(-2k)]
V′ = Σ_c [Σ_j exp(-α_cj R)(P′_cj-α_cj P_cj)
           - Σ_k C_c,2k(D′_ck R^(-2k)-2k D_ck R^(-2k-1))]
J_j = -V′(R) q/R · full_dt · kick_fraction; J_i = -J_j
```

BO short i=-1의 미분은 -a/R²이다. REL leading에 1을 추가하지 않고 BO leading g′를 빠뜨리지 않는다. 질량/운동량은 고정 위치의 J식에 곱하거나 나누지 않는다.

position FX(96,48), momentum=impulse FX(96,80), full_dt=40 atomic time, kick_fraction=1/2, h=20 atomic time을 고정한다. 다른 profile/time/species는 새 bundle 없이는 지원하지 않는다. 물리 admission과 future drift guard 모두 B3의 exact r_min을 사용한다.

J_real,j,k·2^80을 전체식 평가 후 nearest-even으로 한 번만 반올림한다. 중간 R/F를 storage grid로 반올림하지 않는다. m이 짝수면 rounding cell 양끝 닫힘, 홀수면 열림이다. signed96 범위는 [-2^95,2^95-1]; saturate/wrap 금지다. 양쪽 원자의 impulse도 같은 grid에 표현할 수 있어야 하므로 m=-2^95의 반대 impulse +2^95는 `OPPOSITE_RAW_UNREPRESENTABLE`로 거부한다. 이는 새 point 계약의 보수적 availability 제한이며 기존 Arithmetic Kick의 wide intermediate semantics를 수정하지 않는다.

## 방법과 상태

producer는 absolute dyadic sqrt enclosure, positive-endpoint reciprocal, exact rational signed interval/power, range-reduced positive Taylor reciprocal exp 및 매 squaring의 outward absolute dyadic widening을 선택한다. precision은 B5의 finite N/P doubling 정책이다. rechecker는 B6의 지정된 V2 significant dyadic/direct Taylor `full` 방법이다. 방법이 다르므로 P의 숫자가 같은 절대 오차를 뜻하지 않는다.

`RESOLVED`는 mathematical raw cell을 증명했다는 private producer 상태다. `UNPROVED`는 허용된 finite policy에서 증명하지 못했다는 뜻이다. `STOP`은 실패/미증명/미승인 결과를 실행에 사용하지 않는 제어 결과다. `PUBLISHED`는 B4의 완전한 proof가 별도 recheck와 출력 한도를 통과한 상태이며 계산 성공과 다르다. 기존 Arithmetic의 `ARITHMETIC_ONLY / J_NOT_VERIFIED`를 수정하지 않는다.
