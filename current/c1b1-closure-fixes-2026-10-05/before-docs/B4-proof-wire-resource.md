# B4 — Proof wire / bounded resource artifact

- status: DESIGN CONDITIONS ADDRESSED / IMPLEMENTATION STILL NOT STARTED / REVIEW PENDING
- version: 1, 2026-10-04; audited design snapshot `023b186c0e9d95c11399893e7f75772cfff6c3a7`의 후속 저자 사양
- dependencies: [wire data](../../specs/c1b1-independent-impulse-v1/proof-wire.json); B1/B3/B5/B6/B7/B8
- unresolved items: B4+B5 공동 독립 승인; parser/writer 및 hard resource 구현 검증
- what this does NOT certify: production 구현, 모든 입력의 finite-budget 성공, 물리 정확성, J verification, integration/trajectory/replay/N-Step, certification.

기존 [감사 대상 설계](../C1B1_INDEPENDENT_IMPULSE_V1_DESIGN.md)는 역사적 snapshot으로 보존한다. 이 후속 사양은 지정한 항목에 한해 옛 제안/U1–U8을 대체하며, 독립 closure 재검토의 `IMPLEMENTATION MAY START` 판정 전 소스 구현을 허용하지 않는다.

## 고정 encoding과 한도

ASCII canonical JSON: key lexical sort, compact separators, unicode는 escape, 마지막 LF 한 개. 입력 decode 시 duplicate/unknown key, bool/float/JSON numeric token/NaN/Infinity, -0/+, leading zero, invalid enum을 거부한다. nullable field만 null을 허용한다. runtime framework object/callable은 wire가 아니다.

| 항목 | 한도 / 선택 근거 |
|---|---|
| 모든 canonical integer | sign 제외 <=4096 decimal digits; 감사된 Claim V1 정수 범위 유지 |
| rational | exact coprime n/d, d>0, zero=0/1; n과 d 각각 4096 digits |
| input / certificate / 완전한 artifact | 각각 <=1,048,576 ASCII bytes, terminal LF 포함; Claim V1 envelope와 동일한 상한 |
| failure record | <=4096 bytes; 아래 fixed fields만, integer payload/exception text 없음 |
| 최대 container depth | 7; root object=1, object/array마다 1 증가 |
| arrays | atom=2, vector=3, raw state 합계12, exp plan=9; 어떤 array도12초과 금지 |
| hash 및 record/atom ID | lowercase hex 64자, 필드 개수는 closed schema로 고정 |
| free metadata / diagnostic | 0 bytes; 추가 자유 필드 금지 |
| serialized attempt history / intermediate interval | 0 entries; attempt digest와 성공 count만 compact record |

byte/structure 상한은 publication 정책이고 CPU/메모리 예산 숫자의 선정이 아니다. 실패 envelope는 위 정해진 길이의 hash/enum/null만 포함하므로 4096 bytes에 구조적으로 들어간다. 진단 interval/log가 필요해지면 별도 version과 size 정책의 검토 후 추가하며 현재 proof 출판 조건에는 포함하지 않는다.

이 한도는 runtime Input/Certificate/Artifact/Failure에 적용한다. 고정 source/constants/specification bundle은 별도 static schema와 승인된 bytes/hash로 읽으며, runtime request의 constants override나 무제한 embed로 전달하지 않는다.

## Closed schema

아래 표의 keys는 전부 required이고, 언급하지 않은 key는 금지한다. 숫자는 decimal string이다. `Hash`는 64 lowercase hex, `Int`/`PosInt`/`Rat`은 앞 encoding을 따른다. 모든 ID는 Hash syntax이며 의미 authenticity는 B7을 따로 검사한다. named object는 정해진 key 집합만 허용한다.

| object | exact keys 및 값 |
|---|---|
| Input | schema=`LAB_C1B1_IMPULSE_INPUT_V1`, spec_sha256:Hash, state:State, acquisition:Acquisition, budget:Budget |
| State | position_grid:Grid, momentum_grid:Grid, atoms:Atom[2] |
| Grid | kind=`FX`, width:PosInt, frac_bits:Int; 각각 (96,48)/(96,80)과 정확 일치 |
| Atom | atom_id:Hash, species=`Ar40`, position_raw:Int[3], momentum_raw:Int[3]; 두 atom_id 서로 다름, 역할 순서 i,j, signed96 |
| Acquisition | record_id:Hash, acquisition_id:Hash, phase=`FIRST_HALF_KICK`/`SECOND_HALF_KICK`, full_half=`HALF_OF_FULL_DT`, executor_source_sha256:Hash, acquisition_tool_sha256:Hash, previous_occurrence_sha256:Hash/null |
| Budget | B5의 23 positive finite integer fields, basis_record_sha256:Hash, issuer_sha256:Hash, profile_version=`1`; instance canonical ID는 B7 domain hash |
| Certificate | schema=`LAB_C1B1_IMPULSE_CERT_V1`, spec_sha256:Hash, binding:Binding, producer_source_sha256:Hash, rechecker_source_sha256:Hash, method=`LAB_POINT_PRODUCER_V1_AND_PINNED_V2`, raw_J:Int[3], proof:Proof, attempt_count:PosInt, attempt_digest:Hash |
| Binding | input_sha256:Hash, full_state_sha256:Hash, projection_sha256:Hash, math_request_sha256:Hash, occurrence_sha256:Hash, acquisition_record_sha256:Hash, budget_sha256:Hash |
| Proof | sqrt_bits:PosInt, work_bits:PosInt, exp_plan:Exp[9], lane_kinds:LaneKind[3] |
| Exp | rate_id: 고정 enum, rate:Rat, mode=`FULL`, order:Int>=0; B6의 고정9 순서 및 exact constants와 일치 |
| LaneKind | `NONLINEAR_V2` 또는 `EXACT_ZERO_AXIS`; q_raw[k]=0 iff exact-zero; exact-zero raw_J[k]=0 |
| Artifact | schema=`LAB_C1B1_IMPULSE_ARTIFACT_V1`, input:Input, certificate:Certificate, status:Layers, publication_kind=`POINT_PROOF`/`COMPOSITION_RESULT` |
| Layers | producer, rechecker, executor_comparison, arithmetic, publication, execution: 각각 B8의 closed enum |
| Failure | schema=`LAB_C1B1_IMPULSE_FAILURE_V1`, status:Layers, phase:Phase, reason:Reason, resource_kind:ResourceKind/null, spec_sha256:Hash/null, state_sha256:Hash/null, occurrence_sha256:Hash/null, budget_sha256:Hash/null, attempt_count:null, attempt_digest:Hash/null |

영문 field 이름은 규범 식별자다. Phase enum은 PARSE, BINDING, PHYSICAL_DOMAIN, POLICY, COMPUTE, RECHECK, COMPARISON, ARITHMETIC, PUBLICATION이다. Reason enum은 SCHEMA_INVALID, BINDING_MISMATCH, POLICY_UNBOUND, SINGULAR_SEPARATION, PHYSICAL_DOMAIN, RAW_UNREPRESENTABLE, OPPOSITE_RAW_UNREPRESENTABLE, RESOURCE_CAP, ROUNDING_UNPROVED, RECHECK_UNPROVED, RECHECK_REJECTED, ACQUISITION_NOT_AVAILABLE, EXECUTOR_MISMATCH, ARITHMETIC_REFUSED, ARTIFACT_LIMIT, HOST_SERIALIZATION_LIMIT, PROGRAMMING_ANOMALY이다. Failure에는 literal error message나 offending integer/payload를 넣지 않는다. 모르는 hash는 null로 두고 만들어 채우지 않는다.

ResourceKind는 BIT, RATIONAL_BIT, TEMP_ALLOCATION, LIVE_ALLOCATION, WORK, ATTEMPTS, ORDER, CPU_DEADLINE, WALL_DEADLINE, HARD_MEMORY, PARSE_BYTES, ARTIFACT_BYTES, HOST_DECIMAL이고 resource 실패 이외에는 null이다. 실제 hard interruption 종류를 남기되 실행하지 않은 elapsed time을 만들지 않는다. attempt digest는 H0=SHA256(`LAB_C1B1_ATTEMPTS_V1` ASCII+NUL), H_next=SHA256(previous raw digest32+canonical `{t,N,P,producer,rechecker,reason}`)로 고정한다. 이 compact tuple도 pre-str/byte guard를 받고 status/reason은 closed enum이다. count는 success의 actual attempt 수이고 실패 count는 항상 null이다. digest는 진단 binding이며 producer/rechecker soundness를 대신하는 proof가 아니다.

## Parser와 writer 순서

parse 전에 byte cap을 확인한다. streaming 구조 검사로 nesting/array/key count와 token digit length를 정수 변환보다 먼저 제한한다. exact raw/profile/spec/domain 검증, 유한 budget 검증 후 수학 계산에 들어간다. 임의 object를 먼저 JSON 변환해서 cap을 재는 방식도 금지한다. runtime memory는 B5의 parse/live/allocation guard를 적용한다.

입력의 int conversion도 더 낮은 host integer-string limit을 만날 수 있다. 이는 PARSE 단계의 bounded HOST_SERIALIZATION_LIMIT/resource_kind HOST_DECIMAL로 처리하며 일반 ValueError를 밖으로 흘리지 않는다. 입력 canonical 규칙 위반과 host conversion refusal은 별도 reason이다.

writer는 exact canonical reduction → **정수 비교** `abs(n)<10**4096`, `0<d<10**4096` → decimal conversion → 전체 bytes 검사 순서다. gcd/reduction의 uncancelled temporary도 B5 caps 안에서 수행한다. process-global integer-string limit을 바꾸지 않는다. 더 낮은 host digit limit으로 conversion이 실패하면 bounded `HOST_SERIALIZATION_LIMIT / NOT_PUBLISHED / STOP`으로 매핑한다. 모든 wire integer는 이 pre-str 검사를 받는다.

private complete certificate를 먼저 만들고 byte cap을 확인한 뒤 독립 recheck에 제공한다. 3축 전부 ACCEPTED이고 artifact 전체 한도가 만족될 때 atomic하게 공개한다. certificate에는 재구성할 original input/spec과 method parameters/raw claim이 있다. producer의 final interval, family derivative, attempt transcript는 **필수 proof에서 제거**했다. 감사된 옛 설계 §6의 긴 intermediate artifact는 이제 선택 진단 후보일 뿐이다. 사라진 증명 의무를 rechecker의 원입력 nonlinear 재구성으로 대체한다.

## B4+B5 호환성

Compact proof는 N/P/n_R을 parameter integer로 기록하고 내부 dyadic endpoint/2^P 분모를 직렬화하지 않는다. 그래서 큰 P만으로 wire가 자동 실패하지는 않지만 내부 bit/work/allocation caps는 여전히 필요하다. reduced rational을 별도 출판하는 경우 반드시 실제 약분된 n,d를 검사한다. 홀수 numerator와 denominator=2^P이면 `2^13606<10^4096<=2^13607`; P>=13607이면 denominator가 이 wire 한도를 초과한다. `P<=13606`을 계산 정책에 임의로 고정하거나 높은 precision을 성공으로 가장하지 않는다.

이 문서와 B5의 hash를 **하나의 compatibility review** 대상으로 승인한다. `RESOLVED + ARTIFACT_LIMIT`은 계산은 증명됐으나 `NOT_PUBLISHED/STOP`이다. partial J나 축별 성공 certificate를 먼저 공개하는 경로는 없다.
