# Independent Impulse V1 — ATTEMPT-REASON-NULL clarification

- status: ATTEMPT-REASON-NULL clarification / INDEPENDENT RECHECK PENDING
- version: ATTEMPT-REASON-NULL-2026-10-05; 별도 규범 제안 revision
- dependencies: 승인 antecedent `8e5865964770b3752326d361276cbccd125c547a`, 그 semantic bundle 및 B4/B5/B8; [새 package](../specs/c1b1-independent-impulse-v1-attempt-reason-null/package-manifest.json)
- unresolved items: 이 정정과 closed compatibility table의 독립 재검토; producer의 해당 경계 이후 구현은 중단
- what this does NOT certify: Impulse 구현 완료·정확성·독립성, runtime activation, J verification, 물리/trajectory/replay/N-Step, certification

## 역사와 변경 범위

`8e5865964770b3752326d361276cbccd125c547a`의 **DESIGN / PRE-IMPLEMENTATION CLOSURE PASS / implementation_may_start=true / runtime_activation_allowed=false** 독립 판정은 역사적으로 보존한다. `4cb2910`의 CLOSURE REVISION REQUIRED/F-CLOSURE-1/F-CLOSURE-2도 그대로다. 이번 정정은 성공 attempt의 reason이 정의되지 않은 공백만 다룬다. 새 success reason token을 발급하지 않는다.

승인된 [원래 spec directory](../specs/c1b1-independent-impulse-v1/)의 bytes·sidecar·human 문서는 수정하지 않았다. 제안본은 [별도 directory](../specs/c1b1-independent-impulse-v1-attempt-reason-null/)로 발급했다. 물리 수식, primitive 방법, rounding, overflow, finite policy, identities, Failure schema, byte/digit cap은 그대로다. `proof-wire.json`의 attempt 규칙을 명확히 하고 전이 dependency ID와 새 package review/revision metadata만 갱신했다.

## Required canonical tuple

```text
exact keys = {t, N, P, producer, rechecker, reason}
```

`reason` key는 항상 존재한다. `producer`/`rechecker`는 결과 상태를 표현하고 `reason`은 비성공·거부·오류의 원인을 표현한다. 명시적 성공 두 조합에서만 reason은 **JSON null**이다. 문자열 `"null"`, missing key, SUCCESS/RESOLVED_SUCCESS/OK 등의 새 token은 허용하지 않는다.

기존 integer encoding을 유지하므로 t/N/P는 canonical decimal **string**이다. t>=0, N>=1, P>=8이며 기존 4096-digit pre-conversion guard를 받는다. 개념적 숫자 예시가 기존 JSON numeric token 금지를 바꾸지는 않는다.

```json
{"N":"128","P":"128","producer":"RESOLVED","reason":null,"rechecker":"NOT_RUN","t":"0"}
```

이 예시는 encoding fixture다. 승인된 production budget 숫자나 실제 실행 attempt를 발급한 것이 아니다.

## Closed producer/rechecker compatibility table

아래 table과 [wire의 machine-readable 25행](../specs/c1b1-independent-impulse-v1-attempt-reason-null/proof-wire.json)의 관계가 일치한다. `INVALID`는 어떤 reason도 허용하지 않는다. 나열되지 않은 status 또는 reason도 INVALID다.

| producer | NOT_RUN | ACCEPTED | REJECTED | NOT_PROVED | ERROR |
|---|---|---|---|---|---|
| NOT_STARTED | INVALID | INVALID | INVALID | INVALID | INVALID |
| RESOLVED | null | null | RECHECK_REJECTED | RECHECK_UNPROVED | PROGRAMMING_ANOMALY |
| UNPROVED | ROUNDING_UNPROVED 또는 RESOURCE_CAP | INVALID | INVALID | INVALID | INVALID |
| REFUSED | 아래 closed refusal set | INVALID | INVALID | INVALID | INVALID |
| ERROR | PROGRAMMING_ANOMALY | INVALID | INVALID | INVALID | INVALID |

REFUSED/NOT_RUN의 closed refusal set:

```text
SCHEMA_INVALID
BINDING_MISMATCH
POLICY_UNBOUND
SINGULAR_SEPARATION
PHYSICAL_DOMAIN
RAW_UNREPRESENTABLE
OPPOSITE_RAW_UNREPRESENTABLE
```

이 table은 표현의 compatibility만 정의한다. 기존 phase 선행·admission·policy 검사를 우회하거나 실제로 없었던 attempt를 만들 권한을 주지 않는다. schema/domain/policy가 실제 parameterized attempt 전에 중단되면 t/N/P를 꾸며 tuple을 추가하지 않고 H0 또는 실제 이전 attempt digest를 유지한다. NOT_STARTED의 tuple은 없다.

비선형 producer가 RESOLVED인 뒤 rechecker가 ERROR가 된 경우에는 producer의 수학 상태를 유지하면서 rechecker ERROR/PROGRAMMING_ANOMALY를 기록한다. 전체 제어는 기존 규칙대로 STOP이다. rechecker NOT_PROVED/REJECTED도 producer의 성공 상태를 임의로 바꾸거나 새 성공 reason을 만들지 않는다.

Comparison/arithmetic/acquisition/publication failure는 그 기존 layer/Failure에 남긴다. 성공 producer/rechecker attempt에 EXECUTOR_MISMATCH, ARITHMETIC_REFUSED, ARTIFACT_LIMIT 등을 성공 reason처럼 채우지 않는다.

## Failure는 별도 계약이며 변경하지 않음

승인된 11개 Failure keys와 primary/secondary closed 목록, 기존 reason/resource_kind enum, resource_kind required enum/null 규칙, failure attempt_count=null, 4096-byte 한도를 그대로 유지한다.

**Failure.reason은 required non-null closed enum이다.** Attempt의 null 허용을 Failure에 적용하지 않는다. Failure의 null reason, missing reason, 문자열 success token은 여전히 거부된다.

## Rolling digest 유지

```text
H0 = SHA256(ASCII "LAB_C1B1_ATTEMPTS_V1" || NUL)
Hnext = SHA256(previous raw digest32 || canonical tuple bytes)
```

기존 ASCII JSON, lexical key sort, compact separators, ensure_ascii escape, terminal LF 한 개를 유지한다. `reason:null`과 reason key 생략은 서로 다른 bytes/hash다. Rolling step은 전체 tuple이 허용되는 관계인지 확인한 경우에만 정의된다. 불완전한 tuple의 digest를 만들지 않는다. 이 digest는 diagnostic binding이며 독립 nonlinear proof가 아니다.

## Hash 재발급과 작성자 정적 검증

[Hash rebinding receipt](../current/c1b1-attempt-reason-null-2026-10-05/hash-rebinding.json)에 승인 antecedent와 제안본 hash를 분리했다. `constants.json`, `physical-domain.json` 및 각 sidecar는 승인 bytes와 동일하다. 나머지 7개 JSON 및 sidecar는 wire clarification 또는 전이 dependency/package ID 갱신이다. dependency identifier를 제외한 finite-policy, acquisition, status, lineage, semantic-bundle 의미는 보존했다.

[Static checker](../audit/c1b1-attempt-reason-null-2026-10-05/check_spec.py)는 producer/V2를 import하거나 실행하지 않는다. [Spec tests](../tests/test_impulse_attempt_reason_spec.py)도 이 정적 도구와 규범 data만 사용한다.

```text
python audit/c1b1-attempt-reason-null-2026-10-05/check_spec.py --output current/c1b1-attempt-reason-null-2026-10-05/static-checks.json
python -m pytest tests/test_impulse_attempt_reason_spec.py -q
```

실제 결과: [155 static checks PASS](../current/c1b1-attempt-reason-null-2026-10-05/static-checks.json), [46 spec tests PASS](../current/c1b1-attempt-reason-null-2026-10-05/logs/02-spec-green.txt). 25 status pair 각각에서 null·기존 reason 17개·금지/unknown token 4개, 총 550 reason 관계를 검사했다. 요청한 6개 핵심 case, missing/extra/type/limit, canonical null digest, unchanged Failure도 검사했다. [초기 RED 46 failures](../current/c1b1-attempt-reason-null-2026-10-05/logs/01-spec-red.txt)는 제안 spec/checker 미발급 상태에서의 실패로 보존했다.

[보존 receipt](../current/c1b1-attempt-reason-null-2026-10-05/receipt-after.json)에 기존 tracked bytes, 보호 Arithmetic 8개와 `65d8fd2` antecedent의 동일성, 중단 시점에 있던 reference WIP 35파일의 불변성을 기록한다. 앞 단계 author primitive/model 29개 PASS는 과거 검사 기록이고, 이번에는 재실행하지 않았다. Producer 시험의 RED 기록과 아직 author 검증되지 않은 draft code도 보존한다. Reference producer 구현 완료를 주장하지 않는다.

```text
ATTEMPT-REASON-NULL clarification
AUTHOR STATIC SPEC CHECKS PASS
INDEPENDENT RECHECK PENDING

producer boundary continuation_allowed = false
runtime_activation_allowed = false
reference producer = WIP / STOPPED / NOT COMPLETED

Arithmetic V1 = INDEPENDENT REVIEW PASS
physical C1-B1 = J_NOT_VERIFIED / NotCertified
commit/push = NOT PERFORMED
```
