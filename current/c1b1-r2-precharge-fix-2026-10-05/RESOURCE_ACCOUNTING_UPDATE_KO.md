# R² accounting 경로의 제한 수정 및 잔여 OPEN

승인된 finite-policy work schedule은 변경하지 않았다.
[실제 pre() 호출자 피연산자의 비용 재구성](actual-work-reconstruction.json)을 기준으로 한다.
이 검토는 R² 최소 수정의 author 검토이며 새로운 전역 closure 또는 독립 감사를 발급하지 않는다.

| operation class | declared work formula | R²의 wrapper와 실제 경로 | direct bypass / scope gap | status |
|---|---|---|---|---|
| add / compare | max(A,B)+1 | qadd의 두 numerator cross-product 뒤 add; R²에서 add 3회 | 직접 R² Fraction add 제거; 기존 control/comparison 배정 미종결 | R² ACCOUNTED / 전체 OPEN |
| multiply | (A+1)(B+1) | qmul의 numerator/denominator, qadd의 cross-products; R²에서 multiply 15회 | 직접 R² Fraction multiply 제거; 나머지 parameter/control 배정 미종결 | R² ACCOUNTED / 전체 OPEN |
| shift | input_bits+shift+1 | 기존 sqrt/widen/certificate shift wrapper 유지; R² 구성에서는 없음 | 기존 parameter shift 범위 OPEN 유지 | 기존 wrapper 보존 / 전체 OPEN |
| divmod | (A+1)(B+1)^2 | 기존 sqrt/widen/rounding/certificate division 유지; R² 구성에서는 없음 | parity/control division 배정 OPEN 유지 | 기존 wrapper 보존 / 전체 OPEN |
| isqrt | (A+1)^3 | sqrt_enclosure → ResourceAccount.isqrt 그대로 | 이번 수정으로 새로운 우회 또는 면제 없음 | 기존 ACCOUNTED 경로 보존 |
| rational normalization / gcd | (2M+2)*divmod(M,M) = (2M+2)(M+1)^3 | 초기 c.fraction(0,1) 및 qmul/qadd의 fraction; R²에서 fraction 7회 | 이 초기 accumulator만 명시적으로 청구; point/literal/input/constants 등 전체 construction 배정은 OPEN | R² ACCOUNTED / 전체 OPEN |

A,B는 실제 integer operand의 bit length, M=max(A,B)다.
Composite q-operation을 primitive 비용에 다시 더하지 않는다.
Stdlib Fraction 내부 CPU instruction을 새로운 work unit으로 세지 않는다.
작거나 싸다는 이유의 비용 면제를 새로 도입하지 않았다.

첫 sqrt 진입 시 R²=38, work=16717, operations=25를 실제 관측했다.
실제 caller의 피연산자별 비용 계산과 ledger의 각 증가가 일치했다.
R²의 primitive 분포는 multiply15 / add3 / fraction7이다.
이 수치 및 W3는 현재 wrapper ledger의 관측이며 전역 완전성·production budget 증명이 아니다.

## 상태와 미종결 의무

- F-RESOURCE-R2-PRECHARGE: FIX APPLIED / AUTHOR REGRESSION PASS / INDEPENDENT REAUDIT PENDING.
- O-CONTROL-PARAMETERS: approved abstract operation의 비용 또는 명시적 scope 배정 OPEN / UNRESOLVED.
- O-DIRECT-FRACTION-CONSTRUCTION: R² 초기 accumulator 외 construction의 배정 OPEN / UNRESOLVED.
- O-ALLOCATION-AND-WORKER: allocator majorant / active instance / hard worker / V2 preflight Gate OPEN.
- Adapter n_R(t)의 독립 재구성 OPEN; PREPARED_ONLY / invoke blocked.

Domain admission의 직접 계산을 이번에 account 경로로 옮기거나 무료라고 승인하지 않았다.
수정 범위는 account 생성 이후의 producer R² compute 경로다.

**GLOBAL RESOURCE ACCOUNTING = NOT PASS**.
Reference producer 전체는 NOT YET INDEPENDENTLY APPROVED다.
runtime_activation_allowed=false / J_NOT_VERIFIED / NotCertified를 유지한다.
