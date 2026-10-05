# 후속 구현자에게 전달할 작업안 — R² precharge 최소 수정

이 문서는 후속 작업안이다. 아직 수행한 수정이나 승인된 새 accounting budget이 아니다.

## 기준

- 실제 확인한 HEAD: `baba8ea942b896af64ceaa7ab41e2bc5db73112c`
- 직접 parent: `6a63798adbae7c119439683b356f19ff414ac239`
- 감사 소스 bundle: `e4ae7a0491c94a8a56a7029d08b70d7afd0c422ce0057a9027111bc45541d507`
- 실행 전 현재 Git 상태와 위 target의 관계를 확인한다. 다른 동시 작업을 되돌리지 않는다.
- ROUND-ADD 및 QDIV-SIGN은 이 후보의 해당 finding 범위에서 독립 제한 재감사 PASS다. 이를 구현 전체 승인으로 해석하지 않는다.

## 확정 finding

`F-RESOURCE-R2-PRECHARGE`: `producer.py:109`의 직접 rational `sum(x*x ...)`가 account 생성 후 실행되지만 비용과 사전 검사를 우회한다.

canonical q=(5,3,−2), work cap=1에서 account 생성 이후 Fraction multiply 3회와 add 3회가 실행되고, sqrt 진입 시 R²=38, work=0, operations=0임을 독립 재현했다. 첫 5×5의 승인 multiply 비용만 16이므로 fixed bounded input이라는 이유로 허용할 수 없다.

## 수정과 회귀의 목표

1. 물리식·potential·derivative·sqrt/exp·rounding 수학을 변경하지 않고 R² 구성의 abstract rational multiply/add를 기존 accounted 경로에 연결한다. 사후 일괄 청구는 허용하지 않는다. 평가 순서와 exact 결과를 유지하고 시작 상수 construction의 scope는 별도로 명시한다.
2. 먼저 현재 반례를 실패하는 회귀로 보존한다. 최종 반환이 WORK refusal이라는 사실만 검사하지 말고, cap=1에서 허용되지 않은 첫 곱셈이 실행되기 전에 멈췄는지를 관측한다.
3. q=(5,3,−2) 외에 admitted domain 안의 비정수 dyadic 좌표와 부호/0축 사례를 추가한다. 실제 허용 domain과 입력 bytes를 제시하고 다른 초기값으로 원 반례를 대체하지 않는다.
4. 변경 전후 같은 충분한 budget에서 R², radius, V, V′, J enclosure, rounding raw가 exact equality임을 확인한다. 별도 diagnostic 비용을 whole-call 비용에 섞지 않는다.
5. 새 wrapper 관측 비용을 W3로 실제 측정하고 W3−1의 no raw/opposite/certificate refusal과 W3의 기존 raw equality를 검증한다. W, W+152, W2의 과거 의미와 evidence를 보존한다. W2의 새 성공을 고정 기대값으로 강요하지 않는다.
6. R² accounted 경로를 직접 Fraction 연산으로 되돌리는 semantic mutant를 추가한다. Baseline과 mutant를 hash 차이가 아니라 실제 pre-operation 동작으로 구별한다. 기존 18개를 유지한다면 총 19개이며, 이는 19개의 독립 수학 증명을 뜻하지 않는다.
7. 기존 source와 tests의 변경 범위를 고정하고, targeted/Impulse/spec/full tests 및 semantic mutants를 새로 실행해 소스 해시와 연결한다. 기존 author 로그 열람과 새 실행을 구분한다.

## Closure 및 승인 경계

R² 수정이 통과해도 controls/parameters, Fraction construction 등의 OPEN을 자동 종결하지 않는다. 승인된 각 abstract operation을 실제 비용/선청구 경로에 연결하거나, 명시적 scope 제외 근거를 제시한다. 작은 정수이므로 무료라는 추정도, stdlib 내부 모든 CPU instruction을 새 work unit으로 세는 확장도 피한다.

이 작업의 기대 보고 상태는 R² FIX APPLIED / AUTHOR REGRESSION PASS / INDEPENDENT REAUDIT PENDING이다. author가 자기 결과에 독립 PASS를 부여하지 않는다. 기존 d547/6a 역사적 판정과 현 후보의 독립 판정은 각각 보존한다.

`runtime_activation_allowed=false`, `J_NOT_VERIFIED`, `NotCertified`, adapter `PREPARED_ONLY / invoke blocked`, V2 numerical recheck 미승인을 유지한다. 승인된 production budget, allocator majorant, hard worker 또는 전체 구현 승인을 새로 발급하지 않는다.

수정과 증거를 먼저 보고하고, 별도 사용자 승인 없이 commit/push하지 않는다. 이 작업안 자체는 Git 쓰기 승인이나 runtime 활성화 승인이 아니다.
