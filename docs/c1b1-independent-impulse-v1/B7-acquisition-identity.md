# B7 — Acquisition / canonical identity

- status: DESIGN CONDITIONS ADDRESSED / IMPLEMENTATION STILL NOT STARTED / REVIEW PENDING
- version: 1, 2026-10-04; audited design snapshot `023b186c0e9d95c11399893e7f75772cfff6c3a7`의 후속 저자 사양
- dependencies: [identity data](../../specs/c1b1-independent-impulse-v1/acquisition-identity.json); B1/B2/B3/B4/B6/B8
- unresolved items: acquisition tool 및 실제 실행 획득 미구현; independent closure approval
- what this does NOT certify: production 구현, 모든 입력의 finite-budget 성공, 물리 정확성, J verification, integration/trajectory/replay/N-Step, certification.

기존 [감사 대상 설계](../C1B1_INDEPENDENT_IMPULSE_V1_DESIGN.md)는 역사적 snapshot으로 보존한다. 이 후속 사양은 지정한 항목에 한해 옛 제안/U1–U8을 대체하며, 독립 closure 재검토의 `IMPLEMENTATION MAY START` 판정 전 소스 구현을 허용하지 않는다.

## Hash와 canonical payload

파일/bundle SHA-256은 exact canonical bytes 그대로의 ordinary SHA-256이다. state/projection/math/occurrence/budget/acquisition **identity**는 `SHA256(ASCII domain label || NUL || canonical payload)`다. domain labels는 identity.json에 고정했고 self hash를 payload에 넣지 않는다. canonical input object hash도 ordinary SHA-256으로 Certificate에 연결한다. raw Git/source SHA는 source provenance이며 state/spec ID 대신 쓰지 않는다.

| identity | canonical payload와 binding |
|---|---|
| full_state | State 전체: atoms 순서 i,j; 각 atom_id/species/position3/momentum3; 정확 grid data. state equality에 momentum도 포함 |
| projection | spec/constants/domain hashes, atom ids와 i/j 역할, position raw6, species, position grid, full_dt=40/1, kick_fraction=1/2. momentum 및 외부 J 제외 |
| math_request | projection hash, method/version, proof-wire version, axis order xyz; 같은 수학적 문제의 key |
| budget | Budget 전체; mathematical truth와 availability policy 구분 |
| acquisition_record | `{"state":State,"acquisition":Acquisition}` 전체; immutable 외부 수집 payload. source/tool/id/phase/previous 포함 |
| occurrence | acquisition_record hash, acquisition/record ID, full_state/projection hash, phase/full-half, atom ids/roles, axis order, executor/tool hash, previous occurrence hash/null |

projection의 constants/domain hash는 승인한 bundle dependency와 일치한다. math method object의 exact keys는 producer_method, rechecker_method, precision_method, wire_version이고 값은 각각 LAB_POINT_PRODUCER_V1, PINNED_V2_SIGNIFICANT_DYADIC_POSITIVE_TAYLOR_FULL_V1, FINITE_N_P_DOUBLING_ORDER_SEARCH_V1, LAB_C1B1_IMPULSE_PROOF_WIRE_V1이다. occurrence payload exact keys는 acquisition_record_sha256, record_id, acquisition_id, full_state_sha256, projection_sha256, phase, full_half, atom_roles, axis_order, executor_source_sha256, acquisition_tool_sha256, previous_occurrence_sha256이다. atom_roles는 ordered object `{i:atom_id,j:atom_id}`, axis_order는 `["x","y","z"]`다. projection exact keys는 spec_sha256, constants_sha256, domain_sha256, atom_roles, position_raw(두3-vector), species(두Ar40), position_grid, full_dt, kick_fraction. math_request exact keys는 projection_sha256, methods, axis_order. Certificate Binding이 이 derived identity들을 정확히 재계산해 일치해야 한다.

## 실행 occurrence / J0와 J1

`FIRST_HALF_KICK`은 frozen start snapshot이며 previous_occurrence=null이다. `SECOND_HALF_KICK`은 drift 결과를 **새로 획득한 snapshot**이고 previous_occurrence가 직전 first-kick occurrence와 연결돼야 한다. atom identity/역할/spec/time continuity도 검사한다. first/second를 stage 문자열만 바꿔 꾸미거나 기존 result hash를 재사용하면 안 된다. 같은 position/raw bits여도 record/acquisition ID와 occurrence가 다른 실행을 별도 증거로 남긴다.

hash는 bytes equality의 수단이며 실제 실행에서 획득됐다는 사실을 홀로 증명하지 않는다. 수집 도구의 source pinning과 authenticated execution capture가 필요하다. 현재 tool/capture는 미구현이다. 외부 J numeric raw가 같아도 acquisition/record/spec/source/phase의 전체 binding이 없으면 `NOT_AVAILABLE / STOP`이다. 외부 raw를 producer request에 넣거나 정밀도 결정에 사용하지 않는다. comparator에만 별도로 입력한다.

## Cache 및 stale defense

V1 state-dependent mathematical cache와 execution occurrence cache는 **비활성**이다. constant immutable data만 참조할 수 있다. 후속 cache를 열려면 projection/spec/constants/domain/roles/axes/method/source/wire 전체 key를 매칭하고 proof를 다시 recheck해야 한다. occurrence record는 항상 새 acquisition에서 생성하고 prior record를 cache hit로 재출판하지 않는다. stale/missing/phase-swapped/acquisition-swapped/spec-swapped proof는 scalar raw가 같아도 거부한다.

기존 synthetic arithmetic benchmark의 supplied J를 두 kick에 사용한 것은 성능 workload의 사실이다. 이를 physical J0/J1 생성 규칙으로 옮기지 않는다. replay/trajectory authenticity는 이번 point identity contract의 승인 범위가 아니다.
