# 잔여 resource-accounting 범위의 계약 분류 기록

2026-10-05. Source bundle `4bd5cb0ef00c022689aa1a1dd4354deba08961ab4e1887b38d2f62f287a8cced` 기준.
새 arithmetic patch 없이 실제 source 표현을 승인 finite-policy의 의무와 연결했다.
전체 OPEN을 종결한 전수 closure 판정이 아니라, 다음 계약 검토 대상과 미결정 사항을 고정한 기록이다.

## 분류 기준

- ACCOUNTED: 승인 abstract operation이 선언 비용과 연산 전 wrapper 검사로 연결됨.
- EXPLICITLY OUTSIDE THIS WORK MODEL: 승인 계약에 구체적인 제외 근거가 있을 때만 사용.
- OPEN / UNRESOLVED: operation의 비용 의무 또는 validation/control/data 경계의 계약 배정이 미결정.

이번에 새로운 EXPLICITLY OUTSIDE 면제를 발급하지 않았다.
작은 index, parity, abs, unary sign, literal 또는 counter라는 이유로 무료라고 판단하지 않는다.
직접 Python 문법만으로 확정 결함으로 세지도 않는다. Fraction 내부 CPU instruction을 새 work unit으로 세지 않는다.

## 실제 경로와 승인 계약의 연결

승인 자료는 [finite-policy.json](../../specs/c1b1-independent-impulse-v1-attempt-reason-null/finite-policy.json)의
work_accounting, attempt_sequence, preallocation, rechecker_order_sequence, legacy_preflight다.
Spec bytes 및 source는 [관측 provenance](observed-provenance.json)의 baseline과 같은 Git target에 있다.

| ID / 범위 | 실제 source 경로 | 적용되는 계약 / 확인 사실 | 다음에 확정해야 할 배정 | 상태 |
|---|---|---|---|---|
| C-01 precision schedule | policy.py:38–46; N/P cap 검사와 n*=2,p*=2 | attempt_sequence는 N/P를 구성하기 전 bit/allocation/work bound 검사를 요구함. 현재 N/P max guard는 있으나 account 인자가 없는 직접 control 산술임 | schedule 산술의 abstract shift/multiply 비용과 사전 work 검사 경로를 계약상 연결해야 함. 이 특정 의무를 단순 counter 면제로 덮지 않음 | OPEN / UNRESOLVED |
| C-02 Taylor order/counter | exp_enclosure.py:14,17–20; s+=1, order_max+1, n+1,n+2 | work schedule에 add/multiply 등이 있으나 모든 loop/control expression의 별도 operation 배정 규칙이 명시된 것은 아님 | order 생성·counter·범위 산술 각각이 별도 비용인지, 이미 청구한 abstract operation에 포함되는지 근거 필요 | OPEN / UNRESOLVED |
| C-03 parity / unary exponent | interval.py:65,72; -n, n%2 | 실제 expression을 확인했지만 직접 문법만으로 bit-work 결함 또는 무료로 판정하지 않음 | 해당 parameter/control 동작의 abstract operation 또는 명시적 scope 근거 필요 | OPEN / UNRESOLVED |
| F-01 dynamic integer embedding | exp_enclosure.py:18–20; Q(n+1),Q(n+2) | rational 항목은 normalization을 청구하도록 요구함. Q(integer)가 이 모델의 별도 normalization인지에 관한 embedding 규칙은 미확정 | n+1/n+2의 integer 생성과 Fraction embedding을 구분하여 비용/범위 규칙 확정 | OPEN / UNRESOLVED |
| F-02 unit/literal construction | resource.py:144의 Q(1), exp_enclosure.py:11,16의 Q(1), interval.py:57–73의 Q(0)/Q(1) | 기존 rational wrapper 안의 arithmetic normalization과 직접 literal construction은 구별해야 함. R² seed만 명시적으로 c.fraction(0,1)로 해결됨 | 이미 정규화된 상수 데이터 사용과 새 object construction의 abstract 비용을 명확히 배정. R² 종결을 나머지 constructor로 일반화하지 않음 | OPEN / UNRESOLVED |
| F-03 point() branch | interval.py:21–24 | int일 때 Q(q)를 생성함. Fraction 입력 branch는 해당 Q constructor를 호출하지 않고 기존 값을 사용함 | int branch의 embedding/normalization 비용과 Interval allocation 의무를 구분. 함수 전체를 한꺼번에 면제하지 않음 | int construction OPEN; Fraction branch의 constructor 미호출은 source에서 확인 |
| A-01 allocation platform model | ResourceAccount / AUTHOR_ALLOCATION_BASIS | finite-policy는 platform/source-version 고정 majorant와 overlap 포함 사전 allocation 검증을 요구함. 현재 fixture model은 UNVALIDATED | 실제 승인 basis, allocator/source pins와 검증 majorant가 필요함 | OPEN / 미승인 |
| A-02 hard worker / instance | finite-policy legacy_preflight / policy_kind | 전체 V2 upper-bound DAG와 OS memory/CPU/wall enforcement 및 별도 active numeric instance가 요구됨 | 구현·검증·승인 없이 발급할 수 없음 | OPEN / 미승인 |
| R-01 adapter order reconstruction | rechecker_order_sequence / rechecker_adapter.py | n_R(t)=ceil(4*rate*r_guard+1)*2**t의 독립 재구성이 별도 Gate임. invoke는 계속 blocked | 독립 schedule 재구성과 caps/preflight 검증 필요 | OPEN / PREPARED_ONLY |

Line은 고정 source의 위치다. 위 C/F 표는 대표적인 실제 경로를 계약 의무에 연결한 제한 분류이며,
과거 597개 AST syntax 목록을 전부 새로 분류했다는 주장이나 새 확정 finding 목록이 아니다.
Wrapper 밖의 validation/binding/data-construction 경로도 blanket exclusion을 부여하지 않았다.

## 현재 종결된 finding과 남은 전역 상태

ROUND-ADD, QDIV-SIGN, R2-PRECHARGE는 수령한 제한 독립 재감사에서 PASS다.
이 표의 미결정 범위는 그대로 남는다. 전역 resource accounting은 NOT PASS다.
Reference producer 전체 승인, runtime, V2 numerical recheck, J verification 및 certification도 미승인이다.
