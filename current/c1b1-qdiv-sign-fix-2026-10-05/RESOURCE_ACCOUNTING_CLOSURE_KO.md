# Resource accounting closure — 작성자 검토 완료, 전역 closure OPEN

검토 기준은 승인된 `specs/c1b1-independent-impulse-v1-attempt-reason-null/finite-policy.json`의
`work_accounting`, `preallocation`, `attempt_sequence`, `rechecker_order_sequence`다.
Human B5의 Pre-allocation / work accounting도 읽었다. 역사적 pending metadata는 수정하지 않았다.

**RESOURCE ACCOUNTING CLOSURE AUTHOR REVIEW COMPLETE**는 검토와 분류를 완료했다는 뜻이다.
아래 OPEN이 남아 있으므로 **overall resource accounting = NOT PASS**다.
새 독립 재감사, production budget, CPU instruction accounting 또는 검증된 allocator majorant를 발급하지 않는다.

## 승인 비용, wrapper, 실제 경로

A,B는 해당 정수 operand의 bit length, M=max(A,B)다. 표의 site는 source의 실제 경로 이름이다.
[기계 판독 JSON](resource-accounting-review.json)의 `closure_table`에는 file/function/line 단위
wrapper route가 있으며 `actual_wrapper_call_sites`는 canonical 실행에서 실제 관측한 호출이다.
Composite q-operation의 inclusive 비용을 primitive 비용에 다시 더하지 않는다.

| operation class | declared work formula | implementation wrapper | actual call sites | direct bypass found? | status |
|---|---|---|---|---|---|
| add / compare | max(A,B)+1 | add / compare / qadd | qadd의 uncancelled numerator sum; interval constructor/extrema/reciprocal/power; exp width/tail; rounding cell; check_refinements; certificate guard/ceil | ROUND-ADD increment 수정 보존. Input/control comparisons의 모델 배정은 OPEN | 해당 wrapper 경로 ACCOUNTED; source-wide closure OPEN |
| multiply | (A+1)(B+1) | multiply / qmul / qneg / qdiv / qpower | qadd/qmul/qdiv/compare cross products; sqrt square/equality; widen scaling; potential/derivative/J의 interval composition | QDIV의 sign multiply FIX APPLIED. 직접 compute R² 구성은 OPEN candidate | wrapper composition ACCOUNTED; source-wide closure OPEN |
| shift | input_bits+shift+1 | shift | sqrt radicand/denominator; exp tolerance/widen; certificate precision/order | 실제 endpoint/order shifts는 wrapper. Parameter/control shift/doubling의 work 모델 범위 OPEN | wrapper 경로 ACCOUNTED; parameter scope OPEN |
| divmod | (A+1)(B+1)^2 | divmod | sqrt scaled division; widen floor/ceil; nearest_even; certificate ceiling | 해당 division은 wrapper. 직접 parity `%2`, bound/control `//`는 자동 결함으로 세지 않고 OPEN | wrapper 경로 ACCOUNTED; control assignment OPEN |
| isqrt | (A+1)^3 | isqrt | sqrt_enclosure → c.isqrt(floor) | 이 abstract isqrt의 직접 우회 없음 | ACCOUNTED |
| rational normalization / gcd | gcd=(2M+2)*divmod(M,M); fraction에서는 (2M+2)(M+1)^3 | fraction; qadd/qmul/qdiv/qneg/qpower | 미약분 integer 결과 생성 → fraction precharge → Q(n,d); normalized numerator/denominator bit caps | Core normalization은 wrapper. 직접 Q/literal/input construction과 R² 합성의 모델 배정 OPEN | core ACCOUNTED; source-wide closure OPEN |

`compare`의 `(u>v)-(u<v)`는 하나의 선청구한 abstract comparison을 구현하는 결과 구성이다.
이를 CPU expression 개수로 다시 세어 별도 3연산 비용을 발급하지 않았다.
`fraction(n,d)`는 선언된 normalization/gcd upper bound를 먼저 청구하고 stdlib Fraction을 호출한다.
Python Fraction 내부의 모든 CPU instruction을 새 work unit으로 재모델링하지 않았다.

## 실제 계정 추적

Canonical q=(5,3,-2)를 충분한 author cap에서 실제 `evaluate_reference()`로 실행했다.
Production 함수를 대체하지 않고 `sys.setprofile`로 primitive `pre()` 및 QDIV sign multiply의
진입/반환 계정을 관측했다. Profile hook은 이 별도 프로세스에서 이전 상태로 복구했다.

| 관측 | 정확한 결과 |
|---|---:|
| 실제 성공 primitive precharge | 36826건 |
| 그 declared work 합계 | 2605253326092204528 |
| PrivateResult.account.mathematical_work | 2605253326092204528 |
| 새 sign multiply precharge | 1590건 |
| 새 sign multiply work 합계 | 5314390 |
| 수정 전후 whole-call ledger 차이 | 5314390 |

각 성공 precharge의 declared work와 ledger 증가가 일치했다.
이 추적은 **취득한 wrapper ledger 내부의 합계 일치**다. Wrapper 밖의 연산까지 포함됐다는
전역 completeness 증명으로 사용하지 않는다. Canonical 한 whole-call은 모든 branch coverage가 아니다.
음수 divisor, odd tie, overflow/refinement 등은 별도 regression 결과와 구분한다.

## Source 전수 목록과 세 분류의 의미

Impulse 18개 source를 AST로 전수 조사했다. 직접 binary/unary/augmented expression,
comparison 및 관련 builtin construction 597개와 account wrapper route 86개를 목록화했다.
중첩 expression/조건문/문자열·path 연산도 있는 **소스 syntax 목록**이며
597개가 실제 mathematical operations 또는 확정 결함이라는 뜻이 아니다.
개별 file/scope/line/expression/classification/basis는 JSON에 남겼다.

`ACCOUNTED`는 승인된 abstract operation이 사전 청구 wrapper로 연결됐다는 범위다.
원시 wrapper의 `return a+b`, `return a*b`, `return a<<n` 등은 wrapper 내부의 prepaid operation이다.
이 syntax를 다시 wrapper bypass로 세지 않는다.

`EXPLICITLY OUTSIDE THIS WORK MODEL`은 검토된 operand가 **Path join**이거나
proof-wire attempt digest의 **raw bytes32 concat**인 경우에만 적용했다.
이는 승인 wire/hash/source identity 계약의 연산이고 integer/rational work schedule의
피연산자가 아니다. 작은 integer, counter, abs/parity가 싸다는 이유로 OUTSIDE를 발급하지 않았다.

`OPEN / UNRESOLVED`는 해당 syntax가 어떤 approved abstract operation인지 또는
validation/control/data-construction 경계에 속하는지 확정하지 못한 경우다.
자동 확정 결함이나 미실행 상태와 동의어가 아니다. Source 전체 목록은 wrapper route와
분기/메타데이터를 분리하고 이 보수적 배정의 잔여 항목을 숨기지 않는다.

## 남은 OPEN / UNRESOLVED

| ID | 경로 | 확인한 사실 | 미종결 의무 |
|---|---|---|---|
| O-R2-TRUTH-PATH | producer의 `r2=sum(x*x for x in parsed.q)` | account 생성 후 직접 rational multiply/sum을 실행한다. 첫 sqrt entry에서 r2=38/1, ledger work=0, operations=0을 실제 관측했다 | finite-policy의 rational products/normalization 청구 요구와 연결되는 finding 후보. Fixed signed96 bound라는 주석은 work 면제 근거가 아니다. 승인된 exclusion 또는 해당 abstract charge 경로가 확정되지 않아 OPEN |
| O-CONTROL-PARAMETERS | loop/precision/order 산술, parity, abs, unary sign, range/control comparisons | source에 직접 연산이 존재하며 데이터·bound·control 문맥을 목록화했다 | 직접 `%`, unary `-`, 작은 index/loop라는 이유만으로 FAIL도 OUTSIDE도 발급하지 않는다. 승인 schedule의 abstract operation 배정/포함 majorant 근거가 필요 |
| O-DIRECT-FRACTION-CONSTRUCTION | point(q), Q(n+1), unit/literal/input/constants의 Fraction construction | account.fraction 밖의 construction이 존재한다 | 각 construction이 비용이 요구되는 abstract normalization인지, pinned data인지, validation인지 분류 근거 필요. Stdlib 내부 CPU instruction 수를 세는 해결은 허용하지 않음 |
| O-ALLOCATION-AND-WORKER | allocator majorant / active instance / hard worker / pinned V2 preflight | 기존 spec이 별도 activation 의무로 명시하며 이번에 발급하지 않았다 | 수학적 work ledger와 별도의 미완료 Gate |

Input/domain 수학의 일부는 finite-policy activation보다 앞선 validation 단계지만,
그 순서만으로 모든 integer/rational 비용 면제를 추정하지 않았다.
특히 compute에서 반복 구성하는 R²는 current truth path에서 관측한 별도 OPEN 후보다.
QDIV의 최소 수정 외에 물리식이나 알고리즘을 재작성하지 않았다.

따라서 W2는 **두 수정 후 현재 author wrapper/accounting model의 관측 경계**다.
`fully-accounted global work`, `RESOURCE ACCOUNTING PASS`, `production-approved budget`으로 부르지 않는다.
이 문서는 다음 검토에서 이미 발견한 OPEN 경로를 놓치지 않도록 source 근거와 실제 관측을 남긴 것이다.
