# Resource accounting 경로 — 작성자 정적·동적 검토

2026-10-05. **GLOBAL RESOURCE ACCOUNTING PASS를 발급하지 않는다.**
`F-RESOURCE-ROUND-ADD` 최소 수정은 통과했지만, 아래 추가 finding은 OPEN이다.
이 검토는 작성자 검토이며 새로운 외부 독립 감사가 아니다.

## 실제 확인 범위

Impulse source 18개 전체를 읽고 AST의 직접 binary/unary/augmented 연산과 비교를 목록화했다.
별도로 canonical q=(5,3,-2), cap=W+152를 실제 `evaluate_reference()`로 실행하면서
Python opcode와 함수 호출을 취득했다. 78개 함수 위치의 호출과 495개 opcode 위치의
발생 횟수가 [JSON](resource-path-review.json)에 있다. 목록의 CALL·문자열·경로 연산까지
모두 정수 산술로 세지 않는다. 이 숫자는 독립 증명 수나 전 분기 coverage가 아니다.
동적 검토 입력은 한 whole-call이며, retry/tie/early refusal 등은 이 trace만으로 전수 확인되지 않는다.
별도 pytest와 scalar boundary 결과는 다른 종류의 증거다.

첫 계측에서는 Python 3.12.7의 opcode 활성화 시점 때문에 함수 호출만 취득되고 opcode는 0개였다.
그 출력은 [first-opcode-unavailable](resource-path-review-first-opcode-unavailable.json)로 보존했다.
`settrace()` 전에 현재 frame의 opcode flag를 활성화하고 나중에 복구하도록 감사 helper만 정정한 후
495개 opcode 위치를 실제 재취득했다. 최초 출력을 성공한 opcode 검사로 사용하지 않는다.

## 추가 finding: F-RESOURCE-QDIV-SIGN

상태: **AUTHOR CONFIRMED / OPEN / NOT FIXED / INDEPENDENT REVIEW PENDING**.

위치: `independent_checker/c1b1/impulse/resource.py`, `ResourceAccount.qdiv()`.

```python
return self.fraction(self.multiply(a.numerator, b.denominator)*sign,
                     self.multiply(a.denominator, abs(b.numerator)))
```

첫 `self.multiply(...)`는 청구되지만 그 반환값에 대한 `* sign`은 직접 Python 정수 곱셈이다.
Canonical whole-call에서는 이 직접 곱셈의 실제 opcode 발생이 **1,590회**였다.
그 횟수만으로 총 누락 work를 추정하지 않았다. 각 피연산자의 bit length가 다르다.

별도 정확 반례:

```python
c = ResourceAccount(bit_max=100000, num_bit_max=100000,
                    den_bit_max=100000, work_max=40)
c.qdiv(Fraction(1), Fraction(1))  # 현재 1 반환, work=40, operations=3
```

| 실제 연산 | 승인된 work |
|---|---:|
| 첫 account multiply(1,1) | 4 |
| 직접 1*sign, sign=1 | 4 — 미청구 |
| 둘째 account multiply(1,1) | 4 |
| fraction(1,1)의 사전 normalization/gcd bound | 32 |
| 완전한 schedule | 44 |

Cap 40에서 1을 반환하는 것은 그 실제 `* sign`의 declared multiply 비용을 청구하지 않은 결과다.
그 곱셈이 수학적으로 값 1을 유지한다는 사실은 실제 수행된 곱셈의 비용을 면제하지 않는다.
이 진단은 사후 청구를 production 수정으로 제시한 것이 아니다.
요청된 최소 수정 대상인 두 rounding 증가 경로 외의 변경은 수행하지 않았다.
따라서 W+152 성공 역시 이 추가 누락까지 해결됐다는 뜻이 아니다.

## 계열별 검토와 남은 경계

| 경로 | 소스 및 실제 호출에서 확인한 구조 | 범위/남은 검토 |
|---|---|---|
| integer add/multiply/shift/divmod/isqrt | `ResourceAccount` 메서드가 실제 결과 연산 전에 `pre()` 호출 | 이 구조를 wrapper 밖의 연산까지 자동 확장하지 않음 |
| rational cross products/gcd | `qadd/qmul/qdiv/compare`의 교차곱은 wrapper 사용; `fraction()`이 Fraction 생성 전에 uncancelled bit/gcd/work bound 청구 | `qdiv * sign`은 위의 별도 OPEN finding. Python Fraction 내부의 각 opcode를 전수 계측한 증거는 아님 |
| sqrt preparation | radicand shift, divmod, isqrt, square, equality 곱셈, next endpoint add가 wrapper 사용 | 직접 `2*bits`는 parameter 산술로 AST/trace에 남김; 모든 parameter 연산의 accounting 의무까지 닫지 않음 |
| interval comparison/extrema | context-bearing constructor, extrema, reciprocal, endpoint 비교가 `c.compare`의 교차곱과 comparison precharge 사용 | unaccounted pure helper 경로와 구분. 내부 Fraction equality는 ordering cross product와 같다고 가정하지 않음 |
| rounding | account가 있으면 floor increment를 `c.add`로 선청구; cell endpoint는 qadd/compare 사용 | 직접 parity `%2`, range용 `-m`도 목록에 남김. 이번 ADD 수정으로 이 별도 연산의 계약 문제가 닫혔다고 하지 않음 |
| refinement | `check_refinements`가 account 비교와 rounding helper 사용; primitive/outward widening은 wrapper 사용 | 실제 retry 전 분기 coverage는 canonical trace로 확보하지 않음 |
| exp/power/polynomial schedule | mathematical endpoint 연산은 account wrapper 사용 | `s+=1`, `n+1/n+2`, exponent parity/negation, fixed small indices, policy의 `n*=2/p*=2`, certificate의 `t+1`·right shift는 직접 parameter/control 산술. 비용 의무/포함 majorant의 전역 closure 미완료 |
| exact input/domain/R² | parser의 b-a, domain의 q² 합 및 compute 시작의 `r2=sum(x*x)`는 직접 연산 | fixed signed96/FX48 범위라는 코드 주석은 bound 주장이다. 이 직접 연산들의 모든 청구 의무가 면제된다는 독립 근거로 취급하지 않고 후속 검토 대상으로 남김 |
| opposite raw | `opposite_vector`는 직접 unary negation | representability 회귀는 통과했으나 이것으로 비용 ledger completeness를 증명하지 않음 |
| binding/serialization/adapter | bounded parse/hash/decimal 처리는 수학 account와 다른 선행/출력 경로; adapter는 invoke disabled | byte bounds와 math work를 합산하지 않음. PREPARED_ONLY와 schedule reconstruction OPEN 유지 |

직접 연산의 존재, 기존 bounds, 누락된 청구의 확정 반례를 구분했다.
위 표의 미종결 검토 항목에 별도의 확정 FAIL이나 PASS를 임의 부여하지 않았다.
승인된 work 식에 직접 대응하며 실제 피연산자와 비용까지 확인한 추가 확정 finding은
이번 검토에서 `F-RESOURCE-QDIV-SIGN` 한 건이다. 모든 자원 계약 준수 또는 전 입력 finite success를 주장하지 않는다.
