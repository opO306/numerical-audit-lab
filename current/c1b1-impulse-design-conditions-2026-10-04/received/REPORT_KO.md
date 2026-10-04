# C1-B1 Independent Impulse V1 독립 설계 감사

## 0. 판정과 대상

**DESIGN PASS WITH PRE-IMPLEMENTATION CONDITIONS**

**현재 구현 시작은 승인하지 않는다.** 이 판정은 수식·enclosure·rounding 전략이 구현 가능한 구조라는 조건부 설계 평가다. 아래 B1–B8을 닫기 전에는 Impulse V1 production 구현을 시작하지 않는다. 수학적으로 잘못된 핵심 식은 발견하지 않았지만, 신규 specification bundle, 유한 budget, proof wire, rechecker의 신뢰 경계가 아직 발급되지 않았다.

| 항목 | 고정 값 |
|---|---|
| 저장소 | `opO306/numerical-audit-lab` |
| 조회한 브랜치 | `codex/c1b1-fclaim1-output-limit` |
| 이번 설계 snapshot | `023b186c0e9d95c11399893e7f75772cfff6c3a7` |
| 직접 parent / 기존 Arithmetic 감사 대상 | `65d8fd29ae255529afead70289098d36b825b3b4` |
| 설계 파일 | `docs/C1B1_INDEPENDENT_IMPULSE_V1_DESIGN.md` |
| 설계 Git blob | `e9d25f90abe579781b74c0d1314527c1bd319412` |
| 상태 파일 Git blob | `c8c218ea2c6d2862e7be080debb4be3d667ca8fa` |
| 원본 사양 조회 ref | `opO306/success-is-mother-of-failure@0f7b744cf754450424a63c47f305e0327c5b37c1` |

사용자는 설계 파일을 지정했으나 새 설계 commit은 지정하지 않았다. GitHub에서 위 파일이 존재하는 브랜치의 commit을 확인하고 위 SHA로 고정했다. commit의 parent는 API에서 직접 확인했다. 이후 branch 이동은 판정을 변경하지 않는다. 설계 문서의 작성 당시 “commit/push하지 않았다”는 문구를 후속 commit의 존재와 모순으로 취급하지 않는다.

### 수행한 것과 수행하지 않은 것

설계 본문 §1–17을 읽고 원본 동결 사양·채택 판정, 공개 논문의 식·표, 기존 checker/Point Prover의 지정 소스 구간과 대조했다. 손으로 수학을 유도하고, 일부 정수 부등식과 과거 감사 바이트의 Git blob identity를 로컬에서 검산했다.

Impulse 구현, production 코드 변경, 기존/새 impulse test 실행, benchmark 실행, commit, push는 하지 않았다. 새 독립 impulse 구현의 정확성이나 실행 독립성을 PASS로 판정한 작업이 아니다. 이 보고서의 primitive PASS는 조건이 명시된 수학적 설계 전략에 대한 것이다.

### 증거 한계

P0 `S2_ar2_pot.f90`의 공개 표시 내용과 논문 식·표는 확인했으나, 사용자 PC의 원본 raw 파일은 장치 오프라인으로 읽지 못했다. 따라서 설계서의 P0 raw SHA-256을 이번 감사자가 재계산했다고 주장하지 않는다. 공개 페이지의 파싱 결과를 raw byte checksum으로 대체하지 않았다.

A-EV 지정 ref `27e48770ab5db666bcd78034d151ddbb04b6af54`의 A1 파일은 연결된 GitHub 조회에서 ref 없음으로 반환됐다. 이 A-EV 계보와 그 과거 표본/성능 주장은 독립 확인 완료로 세지 않는다. 다른 ref로 임의 대체하지 않았다. 원본 체크아웃이 작성 당시 clean이었다는 receipt도 이번에 재검증하지 않았다.

이 제한은 아래 B1/B2/B6의 승인 조건에 포함된다. 원본 executor의 코드 동작을 물리식의 권위 근거로 쓰지 않았다.

## 1. 기존 Arithmetic V1 선행 판정 보존

`65d8fd2`의 기존 제한 재감사 PASS를 전제로 유지한다. `f806d8c`의 역사적 overall FAIL / F-CLAIM-1을 바꾸지 않는다. 이번 설계는 기존 산술·geometry를 재감사하거나 fast를 default로 승격하지 않는다.

추가로 이전 감사 ZIP의 target source 8개 바이트에서 SHA-256 및 `SHA1("blob " + length + NUL + bytes)`를 계산했다. 이번 설계 commit의 GitHub contents API가 반환한 blob ID와 **8/8 일치**했다.

대상은 `exact_slow.py`, `exact_fast.py`, `exact_geometry.py`, `compare.py`, `contracts.py`, `semantic_manifest_v1.json`, sidecar, `claim_adapter.py`다. 이는 이전 감사 바이트와 고정한 Git 객체의 동일성 확인이다. 사용자 PC의 현재 worktree 전체가 깨끗하다고 보증하거나 새로운 산술 실행 증거를 만든 것은 아니다. 자세한 byte/hash는 `source_identity.json`에 있다.

## 2. 먼저 필요한 일인가: 더 싼 구조와 비용

목표를 “executor가 제공한 J를 다시 적용”에서 “동일한 state/spec으로부터 J 자체를 독립 판정”으로 바꾸는 것은 현재 ARITHMETIC_ONLY의 빈 부분을 채운다. 이 목적은 필요하다. 하지만 그 목적만으로 새로운 nonlinear 엔진을 두 개 더 작성해야 한다는 결론은 나오지 않는다.

기존 exact checker V1/V2가 executor와 다른 계산 계보라는 점은 중요하다. 목적이 기존 point claim의 독립 판정뿐이라면, 기존 checker 중 하나와 새 Lab-owned binding/comparison layer를 결합하는 안이 더 적은 구현량으로 목표에 도달할 수 있다. 기존 checker의 사양, 적용 범위, parser/출력 한도, trust antecedent를 새 layer에 정확히 결합해야 하며 기존 승인을 전체 Lab 물리 계산기로 확대할 수는 없다. 본 감사가 이 대안을 자동 채택하거나 구현을 승인하는 것은 아니다.

신규 reference를 유지한다면 그 이유를 U5에서 고정해야 한다. 예를 들어 Lab-owned data-only bundle, three-component 단위의 일관된 artifact, executor family와 분리된 유지보수 경계가 실제 요구인지 결정한다. 단지 “독립 경로 수가 많다”는 이유는 충분하지 않다.

첫 권고 구조는 **작은 certificate와 별도 재계산 checker**다. certificate에는 입력·사양·method parameters·결론을 고정하고 checker가 자신의 primitive로 다시 포함 구간을 구성한다. 가족별 derivative와 모든 attempt 중간 구간은 선택 진단 자료로 분리하는 안이 있다. 이것은 현재 §6의 필수 artifact 제안을 수정하는 설계 선택이므로 조용히 생략해서는 안 된다. 반대로 모든 primitive witness를 보내는 proof-trace 안을 선택하면 더 작은 checker가 가능하지만 wire와 parser의 비용이 커진다. 둘 중 무엇을 규범으로 삼을지 B4/B6에서 선택한다.

세 성분은 동일한 radial `G=-V′(R)/R`를 사용하므로 하나의 sound radial enclosure와 세 exact scalar `h*q_k`로 결합 가능하다. 이 공유는 동일 oracle 안의 계산 재사용이지 서로 독립된 세 표가 아니다.

정확한 rational endpoint의 반복 제곱은 비용 폭발 위험이 있다. 기약 endpoint의 분모가 `b>1`이면 s회 제곱 뒤 분모는 `b^(2^s)`다. 따라서 단순히 precision을 높일 수 있다는 것만으로 구현 가능 비용이 보장되지 않는다. 제안된 outward dyadic widening은 이를 완화할 수 있지만, 적용 위치·P의 의미·bit cap은 method contract에 고정해야 한다. 이번에는 시간을 측정하거나 새로운 speedup을 주장하지 않았다.

## 3. D1: 물리식, 부호, 단위의 독립 유도

S1의 frozen potential 정의와 S2 §4 D3–D6의 명시적 채택 계약을 근거로 한다. S2의 초기 추천이나 오래된 drift 식을 현재 Arithmetic V1의 계약으로 되돌려 쓰지 않는다.

`q=r_j-r_i`, `R=|q|`, `E(r_i,r_j)=V(R)`로 놓으면 R>0에서

\[
\nabla_jR=q/R,\qquad \nabla_iR=-q/R.
\]

따라서

\[
F_j=-V'(R)q/R,\qquad F_i=+V'(R)q/R.
\]

full step을 Δt, half stage를 `h=Δt/2`로 두면

\[
J_{j,k}=-hV'(R)q_k/R,\qquad J_i=-J_j.
\]

공통 stored J는 j에 더하고 i에서 뺀다. S2 D5와 기존 Arithmetic Kick convention에 맞는다. 이 식에 질량은 없다. 질량은 `drift=pΔt/m`와 상태/종 결합에 들어가며, 고정된 위치와 h에서 힘에 의한 운동량 증가에는 다시 나누거나 곱하지 않는다.

단위도 일관된다. `V′`의 단위는 hartree/bohr, q/R은 무차원, h는 atomic time이다. `E_h*(ħ/E_h)/a_0=ħ/a_0`이므로 J는 atomic momentum이다. α와 η 및 polynomial/long-range 계수의 길이 차원은 bohr 입력 규약과 함께 bundle에 고정해야 한다. 원본의 출처 고정 CODATA 값을 최신 값으로 임의 교체할 이유가 없다.

마지막 저장만

\[
J_{raw,k}=RN_{even}(2^{Fmom}J_{j,k})
\]

으로 한다. R, F, q/R을 먼저 storage grid로 반올림하면 다른 계산이다. 또한 이것은 동결된 위치에서 정의한 한 KDK stage의 수학적 impulse이지, 실제 연속 궤적에 대한 힘의 시간 적분과 항상 같은 값이라는 주장이 아니다.

### Potential 및 analytic derivative

공개 논문 Eq.17/18/20/22/28–31/37과 Table 2/3를 설계 §3의 family별 식·표와 대조했다. BO의 short exponent -1, BO damping order `2k+1`, REL/QED `2k`, retardation의 BO `g-T`, REL leading `-T`가 맞다. 공개표의 사용 계수들과 설계 표 사이에서 차이를 발견하지 않았다. 이것은 P0의 raw hash 재계산이나 미발급 Lab data bundle의 승인과는 다르다.

직접 유도하면 `T=e^-x Σ_(i=0..n)x^i/i!`에 대해

\[
T'(R)=-\eta e^{-x}x^n/n!,\quad x=\eta R.
\]

따라서 각 D의 derivative base는 `+ηe^-x x^n/n!`이며 BO 선도항에만 g′가 더해진다. 그리고

\[
\frac{d}{dR}[-C D(R)R^{-2k}]
=-C[D'(R)R^{-2k}-2kD(R)R^{-2k-1}].
\]

short term은 `e^-αR(P′-αP)`, BO의 i=-1 항은 `-a_-1 R^-2`로 미분된다. REL leading damping은 음수이므로 모든 damping factor가 [0,1]이라는 공통 가정을 넣으면 안 된다. 새 의무 I17에 포함한다.

## 4. Specification provenance 분류

다음은 원본의 지위와 Lab의 지위를 나눈다. 원본 ADOPTED/FROZEN이 곧 Lab 신규 bundle 승인이라는 뜻은 아니다.

| 항목 | 직접 근거 | 원본 지위 | 새 Lab 지위 |
|---|---|---|---|
| V(R), retardation ON | S1 §1; 공개 Eq.17/20/22/28–31 | FROZEN | CANDIDATE: bundle 미발급 |
| V′ 및 radial force -V′ | S1 §1, S2 §4 D5, 식 직접 미분 | FROZEN 정의 / ADOPTED 합성 | CANDIDATE |
| q 방향·exact R²·unrounded R | S2 §4 D3/D4 | ADOPTED | CANDIDATE |
| same J, i−/j+ | S2 §4 D5 | ADOPTED | CANDIDATE |
| 거리·에너지·힘 단위 | S1 §1 | FROZEN | CANDIDATE: unit labels/data 결합 필요 |
| 명목 exact decimal coefficients | S1 §1; P0 공개표시; 공개 Table 2/3 | FROZEN | UNRESOLVED: data bundle 및 raw P0 결합 |
| species/mass | S2 §4 D1/D2 | ADOPTED | CANDIDATE: impulse와 drift의 역할 구분 |
| full dt=40, half=1/2 | S2 §4 D5/D6, §6 | ADOPTED, 원본 지원 범위 한정 | CANDIDATE; 다른 dt 자동 허용 아님 |
| position/momentum/impulse grid | S2 현재 판정, S4 §2/§3.6, 기존 Lab arithmetic | ADOPTED 후보/해당 point 계약 | CANDIDATE: 96/48, 96/80 조합 승인 전 |
| nearest-even once-rounding | S2 §4 D5; 기존 audited Arithmetic | ADOPTED | ADOPTED 산술 의미, physical wiring은 CANDIDATE |
| overflow 거부 | S1 거부 원칙, 기존 Arithmetic; 설계 §8 | ADOPTED | CANDIDATE: impulse status/schema 발급 전 |
| sqrt/exp/inverse/powers의 실수 의미 | 공개 V 정의 및 S4 | FROZEN 모델 의미 | CANDIDATE 신규 numerical method |
| precision escalation | S4 운영 한도 원칙; 설계 §9 | ADOPTED 원칙 | UNRESOLVED finite policy |
| STOP / UNPROVED | S4 availability/truth 분리; 설계 §9 | ADOPTED 원칙 | CANDIDATE code/phase/우선순위 |
| r_min=1.2 Å 및 출처 변환 | S1 §1; S2 §4 D7 | FROZEN 원본 하한 | UNRESOLVED Lab physical binding |
| 전체 domain/trajectory | S2 현재 문서 | 전체 C1-B1 freeze 보류 | UNRESOLVED / 이번 범위 밖 |

Source table의 각 경로/hash receipt는 탐색 출발점이지 수학적 진실의 증거가 아니다. 이 보고서의 source coverage는 아래 부록에 기록했다. 특히 raw CRLF와 Git LF SHA를 혼동하지 않는다.

단순 문서 SHA 모음은 충분하지 않다. Lab-owned bundle은 우선 적용할 규범을 추출한 exact semantic data여야 한다. physical equation version, unit convention, 각 계수/지수/index/retardation 분기, nominal uncertainty 분리, species label/mass 연결, position/grid, full/half dt, admission, rounding/overflow, primitive contracts, method version, wire schema와 status 의미가 필요하다. 원본 implementation fingerprint를 승인된 수학적 의미의 유일한 ID로 쓰지 않는다. Compatibility fingerprint에 σ가 들어간다는 사실과 J의 식에 σ를 사용한다는 것은 다르다.

## 5. Primitive enclosure: 수학적 전략 PASS

### 5.1 Sqrt와 유리수 interval 연산

s≥0와 정수 N≥0에서 `a=isqrt(floor(s*2^(2N)))`이면 `a²≤s*2^(2N)<(a+1)²`다. 따라서 `[a/2^N,(a+1)/2^N]`은 √s를 포함한다. equality를 정확히 입증한 경우 singleton이 가능하다. 실제 R=0의 거부와 coarse lower bound가 0인 경우의 정밀화를 구별해야 한다.

0<l≤R≤u이면 `1/u≤1/R≤1/l`; 양의 R에 대한 정수 powers는 지수의 부호에 따른 단조성을 사용한다. 일반 signed multiplication은 네 endpoint product의 min/max이고 subtraction은 교차 끝점이다. 연산 전 interval ordering 및 양의 denominator 조건이 필요하다.

g의 denominator는 다른 분모다. 설계 표의 모든 B_m>0이고 R≥0이므로 `D_g(R)=1+ΣB_mR^m≥1`. 따라서 승인할 모델에는 이 부분의 pole이 없다. 이 증명과 계수 positivity 검사도 I5/I17에 명시해야 한다. R>0 하나만 적고 모든 분모 검사가 끝났다고 해서는 안 된다.

### 5.2 Exp의 참값 포함

x≥0에서 exact comparison으로 s를 골라 x=2^s y, 0≤y≤1/2로 둔다. n≥0에 대해 첫 미포함 항이 `t_(n+1)=y^(n+1)/(n+1)!`이며 이후 항의 연속 비율은 `y/(n+2)` 이하이다. 따라서

\[
0\le e^y-S_n(y)\le \frac{t_{n+1}(y)}{1-y/(n+2)}=U_n(y).
\]

양의 두 끝점을 역수로 뒤집으면

\[
\frac{1}{S_n+U_n}\le e^{-y}\le\frac1{S_n}.
\]

양의 interval을 s회 제곱하면 e^-x를 포함한다. x가 interval이면 감소성에 따라 lower는 x_hi, upper는 x_lo에서 얻는다. `floor(lower*2^P)/2^P`, `ceil(upper*2^P)/2^P`는 outward이므로 포함을 깨지 않는다. 값이 두 precision에서 안정적이거나 Decimal/mpmath가 높은 정밀도라는 사실은 이 증명에 사용하지 않았다.

local 폭이 2^-P 이하라는 것과 최종 J 폭이 같다는 주장은 다르다. 반복 제곱에서는 폭이 확대되고, derivative는 큰 항들의 cancellation을 포함한다. 설계가 실제 최종 J interval만으로 판단하도록 한 것은 맞다.

### 5.3 수렴과 tail의 제한된 결론

고정된 admitted input에서 R>0이고 모든 분모가 0에서 떨어져 있으면, radius enclosure 폭과 primitive proof widening이 0으로 가는 한 유한 식의 합성 폭도 0으로 간다. local exp의 tail은 n 증가로 0에 접근한다. 그러나 floating-point underflow 규칙을 exact exp=0으로 이식할 수는 없다. `[0,epsilon]`은 포함 상한이 증명된 경우 허용되는 enclosure이며 physical cutoff와 다르다.

참 scaled J가 midpoint와 떨어져 있으면 충분히 좁은 포함 구간이 한 cell 안에 들어간다. exact midpoint는 singleton equality proof 또는 한쪽 포함 증거가 없으면 계속 걸칠 수 있다. no-exact-tie 정리를 무검토 전역 적용하지 않고 STOP을 허용한 설계가 적절하다. finite budget 안의 성공률, 전체 domain liveness, 제한 wire 안의 최종 artifact 출판 가능성은 각각 별도 의무다.

## 6. Exact rounding과 overflow: PASS

scaled y=2^Fmom J에 대해 m이 짝수면 cell은 `[m−1/2,m+1/2]`, 홀수면 `(m−1/2,m+1/2)`이다. 음수에도 parity는 동일하다. true value를 포함한 `[L,U]` 전체가 해당 cell에 들어갈 때만 m을 확정한다.

따라서 “boundary에 닿으면 항상 escalation”은 정확한 최종 규칙이 아니다. 짝수 cell이 소유하는 boundary를 포함하되 구간 전체가 그 cell에 포함되면 결정 가능하다. 홀수 cell 경계는 strict이고 양쪽 cell에 걸치면 결정할 수 없다. interval midpoint를 대표값으로 반올림하는 방식은 허용되지 않는다.

W≥2에서 `m_min=-2^(W−1)`은 짝수, `m_max=2^(W−1)−1`은 홀수다. representable cells의 합집합은

\[
[m_{min}-1/2,\;m_{max}+1/2).
\]

그래서 lower overflow는 `U<m_min−1/2`, upper overflow는 `L≥m_max+1/2`로 증명한다. 양끝이 overflow라도 [-huge,+huge]라면 중간의 정상 값들을 포함하므로 overflow 확정 근거가 아니다. 별도 equality/overflow bit-width 경계 검사 계획도 타당하다.

동일 J를 i,j에 적용할 때 min raw의 부호 반전이 같은 signed grid에 들어가지 않을 수 있다. 설계는 -J를 별도의 valid-grid impulse로 강제하지 않고 wide exact update와 final momentum check로 처리하므로 기존 Arithmetic 계약과 충돌하지 않는다.

## 7. r_min: C, impulse와 guard 둘 모두 필요

S1은 r_min을 퍼텐셜 적용 하한으로 정했고 S2 D7은 drift segment guard에도 이를 사용한다. 따라서 physical impulse oracle은 이미 하한 아래인 상태를 먼저 거부해야 한다. zero component나 출력 raw0이 domain 검사를 대신하지 못한다.

원본 후보 값 자체는 미지수가 아니다.

\[
r_{min}=\frac{6/5}{529177210903/10^{12}}=\frac{1200000000000}{529177210903}\;\mathrm{bohr}.
\]

미정인 것은 Lab의 명시적 채택·단위 provenance·physical threshold ID다. 이를 최종 승인된 Lab binding으로 바꾸지는 않았다.

r_min 없이도 일반적인 positive-input sqrt/exp 같은 범용 수학 primitive의 설계·정리는 가능하다. 하지만 physical C1-B1 impulse oracle의 admission과 외부 성공 결론은 닫히지 않는다. 이번 사용자의 구현 금지 및 전체 시작 Gate를 우회해 범용 kernel 구현을 시작하지 않는다.

추가 exact 검산: 위 r_min²의 기약 분모는 홀수인 `280028520539078142075409`다. fixed-point 좌표에서 얻은 R²는 dyadic rational이므로 이 값과 정확히 같을 수 없다. equality 허용 규칙은 계속 필요하지만, baseline FX lattice에서 존재하지 않는 equality input을 찾으려 해서는 안 된다. rational-domain 단위 검사와 실제 lattice 양옆 admission 검사를 구분한다.

## 8. Proof wire와 finite budget을 함께 고정할 이유

설계 §6은 canonical 4096자리 한도를 첫 검토안으로 둔다. 이는 아직 최종 wire 승인값이 아니다. 이를 채택한다면 약분된 dyadic `n/2^P`의 n이 홀수일 때 분모를 그대로 decimal로 출력해야 하므로

\[
2^{13606}<10^{4096}\le2^{13607}
\]

이다. 즉 P=13607부터 그 분모는 4096자리 wire 밖이다. P=16384인 분모 `2^16384`는 정확히 4933자리다. 두 부등식은 float log가 아니라 exact integer comparison으로 확인했다. 이 숫자는 새 precision budget을 고른 것이 아니라 표현 호환성의 반례다. 약분이 되거나 다른 encoding을 채택하면 결과가 달라지며, 일반 합성 유리수는 더 일찍 wire 한도를 넘을 수도 있다.

따라서 N/P/order/bit/work cap과 proof schema는 공동 승인 대상이다. 무한 정밀도에서의 내부 수렴을 고정된 finite wire에서의 RESOLVED 보장으로 확대하지 않는다. output failure는 정확한 계산 결과가 틀렸다는 판정이 아니라 증거 출판 불가다.

필요한 경계는 다음과 같다.

- input total bytes, 배열 수·중첩·문자열 길이, metadata 및 exponent 자체의 한도는 expensive int/pow/gcd/파싱 전에 검사한다.
- canonical rational은 exact reduction 뒤 numerator/denominator를 검사하고, decimal 변환 전에 정확 정수 비교를 한다. process-global integer limit은 바꾸지 않는다. 지원 interpreter의 limit이 wire 정책보다 낮을 때의 resource 처리도 새 wire에 정의한다.
- term/attempt/transcript가 늘어날 때의 누적 byte/work cap을 포함한다. failure record는 거대한 값을 다시 stringify하거나 원본 payload 전체를 복사하지 않는 bounded representation이어야 한다.
- mathematical decision, producer result, rechecker acceptance, 완성된 artifact publish를 구별한다. 부분 성공 raw만 내보내면서 proof 부족을 숨기면 안 된다.
- programming fault는 원인을 보존한 별도 STOP이다. 모든 예외를 정상 REFUSED로 뭉개는 것도 금지한다. hard deadline은 단일 큰 정수 연산의 사후 clock 검사만으로 보장되지 않는다.

budget 기본값은 이번에 결정하지 않았다. 승인에는 지원 입력의 bit bound, 각 primitive의 worst-case allocation 상한, 결정적 work accounting, 사전 승인 fixture panel과 비용/UNPROVED 허용 기준, hard deadline 정책이 필요하다. 구현 후 calibration은 정식 policy 갱신 대상으로 둔다. “측정 전이니 무제한”도 “아무 숫자나 골라 승인”도 허용되지 않는다.

## 9. 독립성과 rechecker 계보

현재 지정 소스에서 exact checker V1/V2의 표준 라이브러리 import와 각자의 상수/interval 코드를 확인했다. 특히 Point Prover는 실제 `K2` import, `_enclosure`의 `K2.enclosure` 호출, 마지막 `K2.check_certificate` 호출을 사용한다. 이것은 runtime 없이 정적 경로로 확인한 사실이다. Prover+V2를 서로 독립된 두 oracle로 세지 않는다.

원본 checker의 과거 trust 승인과 그 승인 범위는 S4 및 S5 §9.7에서 확인했다. S5 머리말의 pending과 후반 approval은 시간축을 구별한다. 그 승인을 신규 Lab 구현, 전체 liveness, trajectory로 자동 이전하지 않는다. A-EV 지정 소스는 위 접근 한계 때문에 확인 완료로 세지 않았다.

| 자산 | 설계상의 공유 판정 |
|---|---|
| 공개 수학식·정확 계수·단위·입력 snapshot | 공유 가능. 공통 source 오류와 data 전사 위험은 별도 ledger |
| Python int/Fraction 및 exact 연산 의미 | 공통 TCB로 명시 가능. formal 인증 아님 |
| Taylor theorem, squared sqrt inequality | 같은 정리 사용 가능. 서로 다른 algorithm이 무조건 필요한 것은 아님 |
| producer primitive/enclosure/rounding helper | 이를 rechecker가 그대로 import/copy하면 별도 독립 nonlinear 판단으로 세지 않음 |
| certificate schema | 공유 가능. executable parser를 공유한다면 parser는 명시된 공통 TCB이며 서로 parser를 독립 검증했다고 부르지 않음 |
| executor model/helper/source-exec/FunctionType/숨은 subprocess oracle | 신규 독립 oracle의 참값 경로에서는 금지 |
| data digest나 immutable cache | 수학적 입력·method·source binding이 같다는 조건에서만. 실행 occurrence와 결합은 별도 |

독립 rechecker에 반드시 다른 수학 정리를 강제하지 않는다. 같은 공개 정리의 독립 구현과 직접 inequality 검증은 가능하다. 다만 producer가 계산한 interval을 입력으로 받아 cell 포함만 확인하는 rechecker는 nonlinear 부분을 검증한 것이 아니다. 원래 입력과 승인된 spec으로 enclosure를 재구성하거나, 모든 primitive witness의 정당성과 최종 합성이 그 입력의 J를 포함함을 검증해야 한다.

또한 두 enclosure가 서로 겹친다는 사실은 참값 포함 증명이 아니다. 별도 알고리즘의 point value와 가까워도 proof는 아니다. 틀린 좁은 interval, 바뀐 상수, 누락 derivative term을 담은 valid-looking certificate를 거부하는 공격 시험을 추가해야 한다.

## 10. Arithmetic composition

기존 audited code를 수정할 필요가 없다. 별도 composition이 physical state/spec binding과 independent J evidence를 받은 뒤 `KickInput`으로 전달할 수 있다. core oracle가 기존 arithmetic을 참값 oracle로 호출할 이유도 없다.

후속 KDK에서는 J0의 frozen start snapshot과 J1의 drift 후 새 snapshot이 다르다. 기존 supplied-J benchmark에서 같은 J를 재사용한 사실을 여기의 physical J1 생성 규칙으로 복사하면 안 된다. J0→Kick→Drift/두 guard→새 snapshot의 J1→Kick을 모두 local로 계산하고 전체 성공 뒤 공개해야 한다.

기존 exact_geometry의 guard는 내부 상대좌표를 `r_i-r_j`로 구성하지만 새 impulse 식은 `q=r_j-r_i`다. 이는 거리제곱과 선분 최소거리에서는 모순이 아니다. 선분 전체를 부호 반전해도 norm squared가 같기 때문이다. 그러나 그 상대벡터를 force 방향으로 그대로 재사용하면 J 부호가 뒤집힌다. 따라서 composition은 impulse의 q convention을 독립적으로 고정해야 한다. 이 확인은 기존 geometry를 다시 판정한 것이 아니라 연결 해석의 확인이다.

수학적 J 증거, 외부 J 일치, arithmetic update 성공, physical admission, trajectory 정확성은 서로 다른 필드/판정이다. 기존 결과의 ARITHMETIC_ONLY/J_NOT_VERIFIED를 고쳐 쓰지 말고 새 composition evidence에만 해당 입력의 독립 결론을 추가하는 방향은 적절하다. missing/stale acquisition binding을 숫자 raw 일치로 덮어서는 안 된다.

## 11. 항목별 D1–D16 판정

아래 PASS는 이 설계에서 명시된 전략·관계·계획을 검토한 판정이다. 새 implementation, 실제 J 또는 전체 물리 계산의 PASS가 아니다.

| 항목 | 주제 | 판정 | 근거 |
|---|---|---|---|
| D1 | formula / sign | PASS | S1·S2 §4와 설계 §3 대조; gradient, half-step, 무질량 인자, common J 부호 직접 유도. |
| D2 | specification provenance | UNRESOLVED | 원본 동결·채택과 Lab 신규 승인을 구별. Lab canonical bundle 미발급; P0 raw checksum과 A-EV 지정 commit의 독립 확인 미완료. |
| D3 | units / constants | UNRESOLVED | 단위 차원 및 공개 Table 2/3와 설계 숫자는 일치. 정확 십진 전사 데이터·단위 ID·물리 binding의 Lab 승인 전. |
| D4 | nonlinear primitive enclosure | PASS | 명시된 조건에서 sqrt, reciprocal, powers, exp geometric remainder, outward conversion의 포함 전략을 직접 유도. 실제 구현 판정 아님. |
| D5 | rounding proof strategy | PASS | 짝수 닫힌 cell, 홀수 열린 cell, signed range union과 양쪽 비대칭 overflow 부등식 검토. |
| D6 | precision escalation / STOP | UNRESOLVED | 추측 금지와 finite exhaustion STOP 원칙은 타당. 유한 policy 값·work accounting·오류 우선순위 미발급. |
| D7 | proof wire / resource boundary | UNRESOLVED | 약분 후 pre-str 한도 원칙 타당. 총 bytes·중첩·metadata·failure envelope 및 precision-wire 호환성 미확정. |
| D8 | r_min / domain relation | PASS | C: impulse admission과 drift guard 둘 모두 필요. 원본 수치가 알려져 있다는 것과 Lab 승인 완료는 별개. |
| D9 | implementation independence | PASS | 설계의 executor 금지 경계 및 기존 Point Prover→K2 공유 관계 확인. 새 구현의 실제 독립성은 아직 판정하지 않음. |
| D10 | rechecker lineage | UNRESOLVED | U5의 선택 및 parser/primitive/rounding trusted boundary, 최종 proof acceptance 조건 미확정. |
| D11 | Arithmetic V1 composition | PASS | 새 composition layer로 기존 KickInput 연결 가능. core 8개 파일의 Git blob ID와 이전 감사 바이트가 일치. |
| D12 | validation plan | PASS | V1–V17은 서로 다른 층을 분리. 실제 fixture/수치 실행의 PASS가 아니라 계획 평가. |
| D13 | mutation plan | PASS | M1–M17이 독립 failure mode를 공격. 아래 obligation mapping 및 비퇴화 fixture 조건을 적용해야 함; 실행 결과 없음. |
| D14 | I1–I16 review | UNRESOLVED | 각 의무를 평가·분리했으나 I1/I10/I12/I13 등 pre-implementation blocker가 남음. |
| D15 | missing obligations | PASS | I17–I22 추가 의무 제안 및 필요한 사전 조건을 명시. 이들의 구현 완료를 뜻하지 않음. |
| D16 | implementation readiness | UNRESOLVED | B1–B8 완료 전 구현 시작 불허. 무조건 구현 착수 승인 아님. |

## 12. I1–I16 개별 설계 평가와 현재 상태

`READY FOR IMPLEMENTATION`은 해당 의무의 국소 수학/알고리즘 서술이 충분하다는 뜻이다. **전체 B Gate를 해제하지 않으며 지금 코드 착수를 허용하지 않는다.** 실제 전사·실행·mutation 증거는 새 코드가 생긴 뒤에만 만들 수 있다.

| 의무 | 설계 평가 | 현재 상태 | 근거 |
|---|---|---|---|
| I1 | MISSING PRECONDITION | BLOCKED | 승인된 Lab bundle, exact data 전사, authority/version/hash 미발급. B1–B3. |
| I2 | VALID AS WRITTEN | IMPLEMENTATION-DEPENDENT | raw→q→R² 규칙은 명확. 실제 parser·전사·acquisition 동치의 증거는 구현 후 필요. |
| I3 | VALID AS WRITTEN | READY FOR IMPLEMENTATION | 공개 V의 retardation 재조립과 모든 family index는 식 수준에서 확인. B1/B2 승인과 실제 코드 전사는 별도. |
| I4 | VALID AS WRITTEN | READY FOR IMPLEMENTATION | T′, BO i=-1, g′, force·h·mass 의미의 수학적 유도 확인. |
| I5 | MISSING PRECONDITION | OPEN | R>0뿐 아니라 g의 denominator 양수, 유효 N/P·ordered interval·0 포함 분모의 행동을 명시해야 함. I17로 보완. |
| I6 | VALID AS WRITTEN | READY FOR IMPLEMENTATION | Taylor tail 조건, range reduction, outward squaring의 soundness 전략 충분. method별 widening 위치는 B1/B5에서 고정. |
| I7 | VALID AS WRITTEN | READY FOR IMPLEMENTATION | 포함 구간의 합성은 sound. 같은 R 의존성과 cancellation은 폭/비용 문제이며 midpoint 채택 이유가 되지 않음. |
| I8 | VALID AS WRITTEN | READY FOR IMPLEMENTATION | nearest-even cell과 비대칭 signed overflow 정의 타당. synthetic decision 검사와 실제 Lang state를 구별. |
| I9 | VALID AS WRITTEN | READY FOR IMPLEMENTATION | spec/domain 검사 후 zero shortcut 및 same J 공유가 명시됨. R=0 우회 금지. |
| I10 | INSUFFICIENT | BLOCKED | 원칙만으로 total allocation/serialization 실패 계약이 닫히지 않음. bounded diagnostic, metadata/work/byte cap과 publish point 필요. |
| I11 | NEEDS REVISION | OPEN | 내부 enclosure 수렴, cell 결정 가능성, finite budget 성공, 제한된 wire 출판 가능성을 네 명제로 분리. no-tie 전체 정리는 필수 아님. |
| I12 | INSUFFICIENT | BLOCKED | executor와의 경계는 명확하나 새 producer/rechecker의 실제 source/primitive/parser 계보는 U5. 실제 검사 항목도 별도 필요. |
| I13 | MISSING PRECONDITION | BLOCKED | canonical acquisition/state/phase binding schema 및 mismatch/refusal 결정 규칙을 먼저 고정. B7/B8. |
| I14 | VALID AS WRITTEN | IMPLEMENTATION-DEPENDENT | 기존 code 보존과 J0/J1 snapshot 분리 적절. point oracle의 최초 구현과 후속 KDK composition gate를 분리. |
| I15 | NEEDS REVISION | IMPLEMENTATION-DEPENDENT | 각 semantic mutant의 비퇴화 fixture와 독립 expected·위조 certificate 거부 조건 추가. hash-only 검출과 분리. |
| I16 | VALID AS WRITTEN | IMPLEMENTATION-DEPENDENT | 코드·dependency·proof·author/independent evidence의 실제 고정은 구현/감사 후에만 확인 가능. |

구현 전에 닫을 것은 authority·단위/계수·domain·rounding·primitive proof의 전제·유한 STOP 정책·wire/independence boundary다. 실제 source 독립성, 구현된 interval 포함, mutant 검출, runtime precision behavior, certificate/rechecker 실행 일치 및 성능은 구현 후 검증한다. 그 구분 없이 모든 의무를 OPEN 또는 PASS로 몰지 않는다.

## 13. 누락/분산된 의무의 추가 제안 I17–I22

기존 문서에 원칙이 일부 언급된 주제라도 독립된 acceptance condition이 없거나 여러 의무 사이에 흩어져 있으면 아래처럼 추적 가능하게 묶는다. 이미 존재하는 zero/exp-tail 원칙을 완전히 빠진 것으로 오기하지 않는다.

| 추가 의무 | 주제 | 완료 기준 |
|---|---|---|
| I17 | 전역 정의역과 모든 분모의 정칙성 | R>0, 양의 rates, g denominator≥1, exp-tail denominator>0, coarse inverse lower=0의 refine/refuse를 개별 정리로 결합. |
| I18 | budget와 proof representation의 공동 계약 | 연산 전 bit/allocation, parser·metadata·history·총 bytes·writer limits, 약분 후 출판 범위, 제한된 오류 record. 내부 수렴≠출판 가능. |
| I19 | certificate→rechecker acceptance의 전체 soundness | producer가 적은 구간을 신뢰하지 않음. 같은 입력/모델의 모든 primitive와 마지막 cell까지 proof dependency가 닫혀야 함. 위조 proof mutants 추가. |
| I20 | 정밀화 불일치와 결정론 | nonnested sound enclosure 허용; empty intersection/상이한 proved raw는 anomaly STOP. wall time 포함 receipt와 deterministic math certificate를 분리. |
| I21 | canonical identity와 cache/occurrence 분리 | canonical encoding, version/hash domain separation, whole state→projection 연결, phase/atom/axis 순서 및 stale certificate 방어. 수학 cache와 실행 record cache 분리. |
| I22 | whole-vector 결정과 publish의 순서 계약 | i/j convention, 3성분 순서, 한 lane overflow와 다른 lane UNPROVED가 겹칠 때 우선순위, partial vector/partial artifact 금지, trusted check 전후 status 구분. |

## 14. Mutation plan과 proof obligation 연결

아래는 실행 결과가 아니다. M 번호는 17개지만 여러 행에 서로 다른 edit가 있으므로 실제 source mutant 총수가 17개라고 단정하지 않는다. 매 edit마다 baseline PASS, 실제 변형 소스·hash, 비퇴화 fixture, semantic detection reason이 필요하다. Hash 불일치만으로 멈춘 경우는 trust-control 검사이지 semantic mutant 검출이 아니다.

| 변이 | 결함 | 공격 의무 | 필요한 검출 조건 |
|---|---|---|---|
| M1 | force sign flip | I4/I7/I8 | 인증된 nonzero rounded J를 쓰고 sign 반전이 서로 다른 cell로 가는 사례. 실제 힘이 0에 가깝다는 진단만으로 부족. |
| M2 | i/j kick sign swap | I9/I14 | 원자별 서로 다른 momentum과 nonzero J; common J 양쪽 적용 결과를 따로 비교. |
| M3 | half-step factor 제거/full-step 사용 | I4/I13 | h=dt/2와 다른 scalar가 동일 raw로 반올림되지 않는 fixture. 두 edit를 별도 mutant로 기록. |
| M4 | 1/R 제거 | I4/I7 | R≠1만으로 부족. 올바른 값과 변형 값의 cell이 분리되는 axis/off-axis fixture. |
| M5 | R power 오류 | I3/I4/I7 | 각 long term/derivative term의 독립 enclosure 또는 분리된 J cell; R=1 퇴화 회피. |
| M6 | short derivative/TT slope 누락 | I4/I7 | 빠진 항의 영향이 독립 증거로 관찰되는 term-level fixture; 거친 총 J 구간 일치만으로 검사하지 않음. |
| M7 | BO g′ 누락/REL leading 1−T | I3/I4 | 두 source edits를 분리. 각각 retarded BO, REL term identity 및 J 포함을 공격. |
| M8 | exp sign/rate 오류 | I6/I7 | x>0의 증명된 exp 구간 및 x=0 아닌 case. exp(+x), exp(−2x)는 별도 mutant. |
| M9 | component swap | I2/I7/I13 | 서로 다른 크기의 비영 q 성분으로 lane별 expected가 다르게 구성. |
| M10 | ties-away | I8 | 합성 scaled y의 양·음 even tie. 실제 Lang state에서 exact tie를 만들었다고 주장하지 않음. |
| M11 | inverse/division endpoint swap | I5/I7 | 양수 폭이 있는 분모와 signed numerator, exact rational containment로 검출. |
| M12 | corner 삭제/inward rounding | I5/I6/I7 | 누락 corner가 실제 extremum인 mixed-sign interval과 dyadic 경계. 두 결함군 분리. |
| M13 | early precision accept | I8/I10/I11 | midpoint를 가로지르는 sound interval이 false RESOLVED로 바뀌는지 검사. |
| M14 | overflow/operational refusal 제거 | I8/I10/I11 | lower/upper asymmetric threshold, 양끝 overflow이나 0을 포함한 coarse interval, budget 만료 각각 분리. |
| M15 | wrong spec/profile forced accept | I1/I2/I12/I13 | 다른 spec·grid·half/full binding을 valid-looking data와 함께 제시. 숫자 raw 일치로 통과시키면 실패. |
| M16 | intermediate R/F quantization | I4/I7/I8 | whole-expression once-rounding과 두 번 반올림의 결과가 다른 독립 증거가 필요. |
| M17 | fixed exp cutoff/output guard 제거 | I6/I10 | tail의 참값>0인 primitive 포함 반례와 output resource boundary 반례를 별도로 검사. |

추가로 producer의 잘못된 좁은 enclosure, interval reversal, certificate의 다른 state/spec/phase 재사용, proof term 누락, 과대 metadata 및 stale cache를 공격하는 certificate/rechecker mutants를 요구한다(I18–I22). 위조 raw와 위조 nonlinear proof가 같은 parser/helper 결함으로 함께 통과하는지 검사해야 한다.

## 15. 구현 시작의 필수 조건 B1–B8

| Gate | 완료 조건 | 연결 |
|---|---|---|
| **B1 Lab-owned semantic bundle** | 물리식/retardation·grid·full/half dt·admission·numeric method·wire를 규범으로 고정한 canonical bytes, version, hash 및 승인 기록. 원본 문서 hash 모음만으로 대체하지 않음 | U1, I1/I3/I4/I8 |
| **B2 unit/constant provenance** | 공개 원자료의 byte binding을 재현 가능하게 확보하고 exact decimal 전사/계수·index·단위를 별도 검산. nominal model와 σ/측정 불확도 분리. 새 CODATA 값으로 교체하지 않음 | U1, I1/I3/I17 |
| **B3 physical r_min/domain** | 출처 고정 유리수, equality 허용, R=0/below-bound admission 및 geometry 전달 방식을 명시적으로 승인. 기존 generic threshold PASS로 대체하지 않음 | U2, I1/I9/I14/I17 |
| **B4 proof wire/resource** | encoding·canonical form·digits/total bytes/metadata/list/depth·누적 history cap·host-limit behavior·bounded failure envelope·publish atomicity 확정. precision policy와 공동 검토 | U4, I10/I18/I19/I22 |
| **B5 finite computation policy** | N/P의 정의와 유효 범위·시도/exp-order/bit/work/시간 정책을 근거와 함께 발급. 연산 전 한도 확인과 모호함·overflow·resource·programming fault의 STOP 규칙. 숫자는 이번에 선택하지 않음 | U3/U6, I5/I6/I10/I11/I18/I20 |
| **B6 independent rechecker** | 기존 checker 사용 또는 새 계보 선택, 공유 TCB와 금지 helper/parser 경계, certificate 완전성 및 rechecker acceptance 의미, 실제 독립 감사 계획 고정. 확인 불가한 A-EV commit을 trusted antecedent로 쓰지 않음 | U5, I12/I16/I19 |
| **B7 acquisition/identity** | state·spec·atom/axis·phase·record canonical hash/encoding 및 획득 도구/source pinning 고정. core input은 external J를 받지 않으며 수학 cache와 occurrence binding을 구분 | U7, I2/I13/I21 |
| **B8 status/composition boundary** | producer/rechecker/comparator/Arithmetic 결과의 성공·오류·UNPROVED·refusal 우선순위와 공개 시점 고정. J0/J1 snapshot 분리, 기존 audited status 불변. full executor exception compatibility는 계속 범위 밖으로 명시 | U8, I10/I13/I14/I22 |

이 조건들의 명세는 구현 전에 필요하다. 실제 source/test/성능 증거는 구현 후 제출한다. B7/B8에서 후속 KDK 코드를 미리 구현할 필요는 없지만, point oracle의 certificate identity와 성공 의미를 나중에 소급 변경하도록 비워 두어서는 안 된다. 후속 KDK 배선의 실제 구현은 별도 승인 단계다.

U6의 전체 no-exact-tie/finite-domain completeness 증명을 구현 시작의 무조건 필수 요건으로 추가하지 않는다. V1이 soundness와 fail-closed STOP만 주장한다면, 성공하지 못하는 입력의 존재를 허용할 수 있다. 대신 이것이 계약상 명시되어야 한다. 전체 유효 domain에서 finite budget 성공을 주장하는 순간 별도 정량 증명이 필요하다.

## 16. 최종 상태

```yaml
audit_type: INDEPENDENT_DESIGN_REVIEW_ONLY
design_commit: 023b186c0e9d95c11399893e7f75772cfff6c3a7
design_result: DESIGN PASS WITH PRE-IMPLEMENTATION CONDITIONS
implementation_may_start_now: false

C1-B1 Arithmetic V1:
  audited_commit: 65d8fd29ae255529afead70289098d36b825b3b4
  independent_review: PASS
  scope: ARITHMETIC_ONLY
  exact_slow: DEFAULT
  exact_fast: EXPERIMENTAL / OPT-IN

Independent Impulse V1:
  state: DESIGN ONLY / NOT IMPLEMENTED
  design_review: CONDITIONAL PASS
  implementation_review: NOT PERFORMED

Overall physical C1-B1:
  impulse: J_NOT_VERIFIED
  certification: NotCertified
```

이번 조건부 설계 통과는 J_VERIFIED, replay PASS, physical correctness, trajectory, whole domain liveness, Certified를 발급하지 않는다. 불변한 Arithmetic V1 선행 PASS를 유지하면서 다음 설계 단계의 승인 조건을 명확히 한 판정이다.

## 부록 A. 원자료와 실제 확인 범위

아래 고정 경로는 근거 위치이며, 모든 참조 문서를 처음부터 끝까지 구현 감사했다는 뜻이 아니다.

| 근거 | 위치·확인 범위 |
|---|---|
| 요청서 | 사용자 첨부 `붙여넣은 텍스트(1)(5).txt`, 설계 감사 범위·I/D 평가 형식·구현 금지 |
| 설계 본문 | Lab@023b186c, `docs/C1B1_INDEPENDENT_IMPULSE_V1_DESIGN.md`, §1–17 전체를 구간별 읽기 |
| 현재 상태 | 같은 ref, `docs/C1B1_ARITHMETIC_V1_INDEPENDENT_REAUDIT_STATUS_2026-10-04.md` |
| source receipt | 같은 ref, `current/c1b1-arithmetic-v1-independent-reaudit-2026-10-04/specification-source-provenance.json`; 경로·ID 조사용이며 내용 전체를 재검증한 receipt가 아님 |
| S1 | original@0f7b744, `docs/frozen/C1A_AR2_FREEZE_V1.md`, 전체 §1–4 |
| S2 | 같은 ref, `docs/active/A_MICRO_V6_C1B1_TWO_ATOM_DYNAMICS_DESIGN_V1.md`, 현재 판정, §4 채택 표, §6 dt 판정, 관련 인접 구간. 모든 과거 측정 재검산 아님 |
| S4 | 같은 ref, `docs/active/C1B1_EXACT_IMPULSE_CERTIFICATE_SPEC_V1.md`, 머리말·§0–3.7 및 보이는 관련 내용; 수학적 checker와 runtime binding 책임 분리 |
| S5 | 같은 ref, `docs/active/C1B1_EXACT_IMPULSE_CHECKER_V2_DESIGN.md`, §0–4, §9.6/9.7의 trust 승인 범위 |
| L1 | 같은 ref, `a_reference/c1b1_exact_impulse_checker.py`, source 1–55행 imports·상수와 계약 설명 |
| L2 | 같은 ref, `a_reference/c1b1_exact_impulse_checker_v2.py`, source 1–65행 imports·상수와 방법 설명 |
| L3 | 같은 ref, `a_reference/c1b1_point_prover.py`, source 1–180 및 415–515행의 import, K2 enclosure/checker 호출 |
| 기존 Arithmetic 바이트 | 이전 전달된 `c1b1_fclaim1_limited_reaudit_65d8fd2.zip`의 target 8개 파일. 이번 GitHub fixed-ref contents OID와 직접 비교 |
| 공개 논문 | Lang, Przybytek, Lesiuk, arXiv:2304.14719v2, 2024-04-09 판 HTML. Eq.17/18/20/22/28–31/37 및 Table 2/3 |
| P0 | arXiv v2 supplemental `S2_ar2_pot.f90`의 공개 파싱 내용 및 논문 표 대조. 사용자 PC raw 바이트 checksum 독립 검증은 미완료 |
| A1/A2 | author receipt가 지목한 27e48770 ref. 원격 ref 조회 실패; 신뢰 antecedent로 채택하지 않음 |

S3/S6/S7/S8/S9/S10 전체 원문과 모든 legacy checker 내부를 독립 재감사했다고 주장하지 않는다. 이들의 design source table 설명이 있는 것은 확인했지만, 직접 판정의 load-bearing authority는 위 실제 확인한 S1/S2/S4/S5 및 공개 식이다. 참고 자산의 과거 PASS·성능 수치는 새 Impulse proof로 이전하지 않았다.

## 부록 B. 동봉 증거

- `source_identity.json`: 이전 감사 target 8파일의 actual byte SHA-256 / computed Git blob OID / 새 snapshot API OID 비교.
- `exact_design_checks.json`: r_min 후보의 기약성·non-dyadic equality, 4096-digit/precision 호환성, relative raw bit 길이의 exact 정수 검사.
- `verdicts.json`: D1–D16, I1–I16, M1–M17 mapping, I17–I22와 최종 범위.
- `request.txt`: 원래 첨부된 설계 감사 요청의 바이트 복사.
- `sources.json`: 고정 source 위치와 접근 한계. 문서 전체 raw mirror가 아님.

새 impulse calculator/checker 소스·실행 로그는 없다. 이번 요청이 구현 감사를 금지했으므로 그런 파일을 만들거나 실행했다고 주장하지 않는다.
