# B5 — Finite computation policy

- status: DESIGN CONDITIONS ADDRESSED / IMPLEMENTATION STILL NOT STARTED / REVIEW PENDING
- version: 1, 2026-10-04; audited design snapshot `023b186c0e9d95c11399893e7f75772cfff6c3a7`의 후속 저자 사양
- dependencies: [finite-policy data](../../specs/c1b1-independent-impulse-v1/finite-policy.json); B4 joint compatibility; B6 pinned V2
- unresolved items: parameterized policy의 독립 승인; 근거 있는 numeric instance 발급; 할당 전 bound/OS enforcement 구현 검증
- what this does NOT certify: production 구현, 모든 입력의 finite-budget 성공, 물리 정확성, J verification, integration/trajectory/replay/N-Step, certification.

기존 [감사 대상 설계](../C1B1_INDEPENDENT_IMPULSE_V1_DESIGN.md)는 역사적 snapshot으로 보존한다. 이 후속 사양은 지정한 항목에 한해 옛 제안/U1–U8을 대체하며, 독립 closure 재검토의 `IMPLEMENTATION MAY START` 판정 전 소스 구현을 허용하지 않는다.

## 이번에 결정한 것과 미발급한 것

정책은 **parameterized finite policy**로 고정한다. 모든 valid finite instance에서 횟수·order·bit·work·memory·time이 유한하며 실패 시 STOP한다. 아직 **active numeric budget instance는 없다**. 근거 없는 N0/P0/시간/메모리 기본값을 선정하지 않고 V2의 기존 defaults도 가져오지 않는다. 독립 closure 검토는 이 parameterized 형태를 허용할지, 첫 구현 승인 전에 어느 activation profile을 요구할지 명시적으로 판정해야 한다. `POLICY_UNBOUND`를 임의 기본값으로 우회하지 않는다.

Budget의 23 필수 positive integer는 N0, P0, N_max, P_max, max_attempts, exp_order_max, integer_bit_max, rational_num_bit_max, rational_den_bit_max, temporary_allocation_bytes, live_allocation_bytes, work_unit_max, hard_cpu_time_ms, hard_wall_time_ms, hard_memory_bytes, input_parse_bytes, private_certificate_bytes, legacy_sqrt_bits_max, legacy_work_bits_max, legacy_order_max, legacy_bits_max, legacy_seconds_max, legacy_digit_max이다. basis_record_sha256, issuer_sha256, profile_version도 필수다. 실제 instance는 숫자와 단위, 선정 근거/증거, 승인자를 별도 canonical basis record에 연결해야 한다. byte caps는 B4 한도를 초과하지 못한다. N0>=1, P0>=8, N_max>=N0, P_max>=P0, max_attempts>=1이다. 값이 없는 현재 상태에서 실행을 허용하지 않는다.

issuer/basis hash만 임의로 만들어 승인된 것으로 취급하지 않는다. explicit independent decision이 policy version, exact instance hash, source/platform/allocator/worker pins, basis-record hash를 승인한 경우에만 active instance로 등록한다. 미등록/승인 누락은 POLICY_UNBOUND다. 이 등록/activation도 현재 미발급 상태다.

## N/P/order의 의미와 attempt sequence

N은 producer의 absolute radius bits다. a=isqrt(floor(R²·2^(2N))); [a/2^N,(a+1)/2^N]로 포함하고 exact square가 증명되면 producer는 singleton을 쓸 수 있다. reciprocal에는 positive lower를 먼저 증명한다.

P는 producer exp의 **absolute dyadic outward widening bits**다. 임의 real endpoint를 `floor(v·2^P)/2^P`, `ceil(v·2^P)/2^P`로 바깥쪽 변환한다. rechecker의 P_R는 significant dyadic work_bits다. schedule상 P_R=P로 두지만 절대 오차 의미가 같다는 주장은 하지 않는다.

t=0..max_attempts-1에 N=N0·2^t, P=P0·2^t를 제안한다. 다음 값이 N_max/P_max/bit/allocation/work/order caps를 넘는지 **shift/pow 전에** 검사하고 첫 disallowed attempt에서 UNPROVED/STOP한다. 마지막 midpoint를 반올림하지 않는다.

producer exp(-x)는 x_hi/2^s<=1/2인 최소 s를 택한다. 각 exact endpoint y에서 S_n(y), t_(n+1)(y)=y^(n+1)/(n+1)!, U=t_(n+1)/(1-y/(n+2))를 사용한다. [1/(S_n(y_hi)+U(y_hi)),1/S_n(y_lo)]가 포함 구간이다. exact width<=2^-P를 만족하는 최소 local n을 bounded ascending search로 선택한다. exp_order_max 및 bit/work/allocation caps가 우선이다. reciprocal 뒤 한 번, 이후 s번의 **매 squaring 뒤** absolute dyadic outward widening한다. 모든 실제 폭이 final rounding decision에 반영된다. 고정 cutoff는 없다. sqrt/inverse/powers/derivative는 정확 rational composition이며 중간 storage-grid quantization을 하지 않는다.

V2는 range reduction 없이 full x의 Taylor를 계산하므로 producer local n을 V2 order로 보내지 않는다. 각 fixed rate에 대해 r_guard=producer radius_hi+2^-N, `n_R(t)=ceil(4·rate·r_guard+1)·2^t`를 선택한다. 이것도 caps를 먼저 검사한다. positive z, P_R>=8에서 V2 `up(z,P_R)<2z`; rate와 multiplication 두 outward upper 적용 후 x_hi<4·rate·legacy_radius_hi이고 r_guard가 legacy의 항상-next-dyadic upper도 덮는다. 따라서 n_R+2>x_hi를 보수적으로 만족시킨다. 이 부등식은 기하 tail의 정의역을 위한 것이며 cell separation 보장은 아니다. rechecker는 자기 source로 모든 조건을 다시 확인한다. NOT_PROVED이면 남은 budget 안에서 다음 정해진 attempt로 이동할 수 있고 model/raw REJECTED는 중단한다.

## Pre-allocation / work accounting

A,B는 operand의 exact bit-length다. conservative mathematical work charge는 add/compare=max(A,B)+1, multiply=(A+1)(B+1), divmod=(A+1)(B+1)^2, gcd=(2max(A,B)+2)·divmod(max,max), isqrt=(A+1)^3, shift=input_bits+shift+1이다. 이는 CPU instruction count나 성능 측정이 아니다. rational cross-multiplication/gcd/normalization 및 비교의 unreduced temporary를 모두 charge한다. Python object overhead를 포함한 allocator-specific byte majorant는 platform/source-version에 고정된 basis record가 필요하다; arbitrary bytes-per-bit 값을 만들어 쓰지 않는다.

각 operation은 예상 결과 bit-length와 아직 살아 있는 피연산자/새 temporary의 합계를 연산 **전에** 확인한다. fraction reduction을 한다고 큰 미약분 cross-product가 없었던 것으로 처리하지 않는다. raw relative 좌표는 abs(q_raw)<=2^96-1이며 Σq_raw²의 numerator bit-length<=194다. sqrt scaled input은 <=194+2N 비트이고 이를 scaling 전에 검사한다. 작업 charge 자체의 누적 integer도 cap 상태를 안전하게 비교한다; 큰 charge를 실제 allocation한 뒤 검사하지 않는다.

V2 `_Ctx.note`는 일부 allocation **후**, tick은 cooperative loop 검사다. 그대로 hard-preflight 보장으로 승인하지 않는다. V2를 수정하지 않는 선택 B에서는 source에 묶인 **whole-call upper-bound DAG**(loop counts, exponent/denominator growth, 모든 intermediates, 원본 stats의 float conversion 포함)를 wrapper가 사전 계산/charge하고 isolated worker의 OS memory/CPU/wall hard caps를 강제해야 한다. 이 majorant와 enforcement의 구현/검증은 아직 없다. 과거 default Limits(65536/200000/4000000/600 등)를 신뢰 budget으로 채택하지 않는다. 예측할 수 없는 Python/worker 오류는 bounded ERROR/STOP이고 시스템 전체 global 설정을 바꾸지 않는다.

B4는 compact reconstruction proof이므로 내부 2^P denominator를 전부 wire로 내보내지 않는다. N/P/order parameter 자체도 4096-digit pre-str limit, certificate byte cap을 받는다. 내부 계산을 cell-resolved해도 wire를 못 만들면 NOT_PUBLISHED/STOP이다.

## 네 명제와 실패 우선순위

| 명제 | 채택 범위 |
|---|---|
| I11a internal convergence | fixed admitted input에서 정밀도/order를 무한 증가시키는 method containment/shrinking 논증; 실제 구현 증명 아님 |
| I11b rounding-cell decidability | 엄격 분리된 J에는 충분한 precision에서 결정 가능할 수 있음; no-exact-tie 전체 정리 없음; V2 strict cell은 even tie도 NOT_PROVED 가능 |
| I11c finite-budget success | 모든 admissible input의 성공 보장 없음; finite exhaustion은 UNPROVED/STOP으로 허용 |
| I11d proof publication feasibility | bounded complete certificate + independent recheck + atomic whole-vector publication의 별도 의무 |

soundness를 최우선 의무로 두지만 **아직 미구현 방법의 soundness가 인증됐다고 쓰지 않는다**. programming anomaly는 ERROR/STOP. 검증 단계의 schema/spec/domain 실패가 뒤 단계보다 먼저다. 관측된 proved overflow는 ambiguous component보다 우선; resource cap은 즉시 작업을 끝내며 마지막 approximation을 채택하지 않는다. 세부 layer/priority는 B8이다. wall-time interruption은 actual receipt에 남기며 timing 결정론을 주장하지 않는다. timeout/refusal이 늘더라도 mathematical raw truth를 바꾸지 않는다.
