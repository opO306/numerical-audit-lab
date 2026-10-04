# C1-B1 Arithmetic V1: F-CLAIM-1 제한 독립 재감사

## 최종 판정

**Claim Adapter fix: PASS. Overall C1-B1 Arithmetic V1 submission: PASS.**

이 판정은 **65d8fd29ae255529afead70289098d36b825b3b4**에만 적용한다. 새 구현이 원래 반례를 정확하게 계산한 뒤 정의된 출력 표현 한도를 초과한 결과를 동일한 구조화된 거부로 처리함을 확인했다. 아래 R1–R10은 모두 PASS다.

```yaml
audited_commit: 65d8fd29ae255529afead70289098d36b825b3b4
parent: 433be43ee6aca31f3a4cb76094a19d50e2cbefa8
independent_review: PASS
exact_slow: DEFAULT
exact_fast: EXPERIMENTAL / OPT-IN
scope: ARITHMETIC_ONLY
impulse: J_NOT_VERIFIED
certification: NotCertified
```

역사적 `f806d8ce1ef86a0948b1a8abafe1a22c3058178b`의 **overall FAIL / F-CLAIM-1**은 변경하지 않는다. R2의 PASS는 그 결함의 *재현 성공*이지 과거 구현의 correctness PASS가 아니다. `433be43`의 당시 미감사 상태도 사후 변경하지 않는다. 이번에는 그 commit의 직접 delta와 불변성만 확인했다.

### 감사 방법 및 신뢰 경계

전체 산술 감사를 처음부터 반복하지 않았다. 고정 Git SHA의 실제 바이트가 보존된 기존 PASS를 선행 근거로 사용하고, 새 Claim Adapter delta에 집중했다. 작성자의 PASS 표시나 저장된 receipt를 correctness oracle로 사용하지 않았다.

1. Windows의 별도 임시 clone을 detached HEAD로 고정하고 Git tree, Git blob, checkout SHA-256과 세 회귀 suite를 직접 실행했다.
2. Python 3.13.5 Linux에서는 이전에 전달된 산술 snapshot과 새 adapter의 정확한 소스 snapshot을 독립 패키지로 로드해 별도 checker를 실행했다. 새 adapter는 GitHub가 반환한 Git blob `23cc7a26796e3b5324129e2b616af79385428910`과 재구성 blob hash가 일치하며, 실제 target Git blob/checkout의 SHA-256과도 일치한다.
3. 작은 정수 chunk에 의한 decimal oracle와 직접 Euclidean gcd를 사용했다. target serializer나 작성자 test fixture를 기대값 생성기로 쓰지 않았다.
4. 실험의 Python integer-string limit은 두 환경 모두 4300이었다. 이번 판정은 임의로 변경한 interpreter 설정을 모두 지원한다는 인증이 아니다. Kernel이나 adapter는 감사 중 수정하지 않았고, source mutation은 별도 사본에서만 했다. Commit/push는 하지 않았다.

## R1. Git / delta / source preservation: PASS

직접 parent는 `433be43ee6aca31f3a4cb76094a19d50e2cbefa8`이며, 그 parent는 원래 감사 대상 `f806d8c`다. GitHub commit API와 감사 clone의 `git rev-parse`가 일치했다.

| 비교 | 직접 확인 결과 |
|---|---|
| f806d8c tracked files | 1,943 |
| 433be43 tracked files | 1,944 |
| 65d8fd2 tracked files | 1,974 |
| f806d8c → 433be43 | 상태 문서 1개 추가, 기존 수정/삭제 0 |
| 433be43 → 65d8fd2 | 신규 30개, 기존 수정 1개, 삭제 0 |
| 기존 production 수정 | `independent_checker/c1b1/claim_adapter.py` 하나 |
| parent의 기존 파일 보존 | 1,943개 |
| 추가/수정 checkout 바이트와 Git blob 대조 | 31/31 일치 |
| 실행 전후 tracked 변경 | 없음 |

추가 30개는 새 tests 2개, `tools/` 검증 도구 1개, 수정 설명 문서 1개, 과거 감사 자료 복사본 7개, 보존·재현·회귀계측·검증 기록/보조 파일 19개다. 이 추가 파일을 production 산술 변경으로 혼동하지 않는다. 전체 경로 목록과 delta는 `remote_evidence/provenance.json`, `remote_evidence/adapter_delta.patch`에 있다.

2026-10-04 11:48:44.648150 UTC의 마지막 직접 관측에서도 원격 `codex/c1b1-fclaim1-output-limit`은 target을 가리켰고, 감사 clone HEAD와 tracked-clean 상태가 유지됐다. 이 이후 branch 이동 여부와 무관하게 판정은 위 SHA에만 귀속된다.

### 직접 SHA-256 대조한 불변 파일

각 행은 **f806d8c / 433be43 / 65d8fd2 / 감사 checkout**에서 모두 같았다. 독립 checker에 사용한 snapshot의 해시도 같은 값과 대조했다.

| 파일 | 동일한 SHA-256 |
|---|---|
| `exact_slow.py` | `b36efc03abdcb760f294f009ea1aea8aafa6fcc05a53c7b3970291c90edf4c13` |
| `exact_fast.py` | `2190e099642b4bf440e4a2280b09d4b89984f637e6cee1b09dfa23411f0b4c0b` |
| `exact_geometry.py` | `b237cd00e45e2ed635bae54880cfef88c1126e98af57d74843b752d2ed27677e` |
| `compare.py` | `5ad6b3f0b03b240e559c955552f32eb9079d524fba55be47ab88329a7d0657b2` |
| `contracts.py` | `37acf394c9c252d5e401fdff06fcb28a0ab1202cc090f1456ecd4bb84fff47ed` |
| `semantic_manifest_v1.json` | `3217fc38aa798fff3ffea8072cecafaecac9f98be85589e9fa35a9dc6aa8119b` |
| `semantic_manifest_v1.sha256` | `ae8b89667a539b4252cac34b0f96786dda67c10747e66f2468482d94e5a6db79` |

변경 adapter의 SHA-256:

```text
old: 8e8894eb2abc0e1540f516418287b9e576e282c6140d7d83af9523788fd0d85e
new: 24b05ebf374728583ba725c83b8f9324f4b75b5515b03c5b1036339eef3e4899
```

기존 산술/geometry/validation/비교의 PASS는 위 실제 불변성을 근거로 보존된 선행 감사 판정으로 사용했다. 새 코드가 달라졌는데도 예전 PASS를 가져온 것은 아니다.

## R2. 원래 반례의 old target 재현: PASS

```text
x = 10**2150
position_grid = momentum_grid = Grid(8,0)
r_i = r_j = (0,0,0)
p_i = (1,0,0); p_j = (0,0,0)
mass_i = (x+3)/1; mass_j = 1/1
dt = 1/(x+1)
```

직접 기대값은 `d = 1/((x+1)(x+3))`다. 분모는

```text
10**4300 + 4*10**2150 + 3
```

으로, `10**4300 <= denominator < 10**4301`임을 정수 비교로 확인했다. 따라서 정확히 4301자리다. 각 큰 입력 정수는 2151자리이며 입력 제한을 넘지 않는다.

Old slow/fast kernel은 첫 displacement와 endpoint의 분자 1 및 위 분모를 그대로 반환했다. 나머지 exact lane과 stored displacement/position은 0이며, kernel request는 바뀌지 않았다. 하지만 old adapter는 dict / JSON text / bytes 각각에서 plain `ValueError`를 누출했다. **2경로 × 3형식 = 6/6 재현**이다. 오류를 만들기 위해 process-global limit을 바꾸지 않았다.

증거: `independent_reaudit.py`, `local_evidence/original_false_claim.json`, `local_evidence/independent_results.json`의 `original` old 행.

## R3. 수정본의 F-CLAIM-1 closure: PASS

같은 false-but-well-formed claim을 새 코드에 넣었다. 새 serializer로 claim을 만들지 않고, 작은 정수와 0/1을 사용해 형식을 직접 구성했다. 즉, claim 자체에 4301자리 값을 넣어 거부시킨 사례가 아니다.

새 kernel의 정확한 displacement/endpoint와 stored 값은 old와 동일했다. Default slow와 explicit opt-in fast 모두 다음의 구조화된 거부를 발생시켰다.

```yaml
exception: LabRefusal
code: CLAIM_OUTPUT_LIMIT
phase: claim_output
atom: ""
component: ""
message: canonical computed integer exceeds Claim V1 4096 decimal digits
scope: ARITHMETIC_ONLY
j_status: J_NOT_VERIFIED
spec_sha256: 3217fc38aa798fff3ffea8072cecafaecac9f98be85589e9fa35a9dc6aa8119b
```

**6/6 새 adapter 호출**에서 동일했다. Payload, kernel request, 전역 integer-string limit이 보존됐다. plain `ValueError`가 밖으로 나가지 않았으며 comparison/partial artifact도 반환하지 않았다. `LabRefusal` 자체가 ValueError의 subclass라는 점과 *일반 ValueError 누출*은 구분했다.

## R4. 4096자리 출력 경계: PASS

최대 k자리인 정수의 조건은 부호를 제외하고 `abs(n) < 10**k`다. 0도 이 조건을 만족하며 출력 문자열은 한 자리 `0`이다. 따라서 k=4096에서 `L=10**4096`이면 `L-1`은 허용하고 `L`부터 거부해야 한다.

새 `claim_adapter.py`의 14–15행이 k와 L을 고정하고, 93–97행은 `abs(value) >= L`을 decimal 변환 전에 검사한다. 103–107행은 reduction 및 두 정수 검사를 끝낸 다음에야 `str(numerator)`와 `str(denominator)`를 호출한다. Raw int도 110–112행에서 검사 후 변환한다.

독립 oracle는 큰 정수를 통째로 `str()` 하지 않고, 절댓값을 `10**9`로 반복 나눠 작은 chunk 문자열을 이어붙여 정확한 decimal 표현을 만들었다. 기대 자리수와 값은 이 별도 방법으로 판정했다.

| 정수 크기 | 양/음 분자 | 양의 분모 | raw integer |
|---|---|---|---|
| 4095자리 | 허용 | 허용 | 허용 |
| 4096자리 | 허용 | 허용 | 허용 |
| 4097자리 | structured refusal | structured refusal | structured refusal |
| 5001자리 | str 이전 refusal | str 이전 refusal | str 이전 refusal |

부호 문자는 자리수에 포함하지 않는다. Ratio와 Fraction 모두 검사했다. `L-1 / L / L+1`, 4096자리의 최솟값, 4095자리의 최댓값 등도 포함했다.

실제 유효 drift 입력에서 **계산 결과의 canonical numerator만 4097자리**, 또는 **canonical denominator만 4097자리**인 경우를 각각 ±부호로 만들었다. 각 입력 정수는 wire 한도 이내이고 stored 값도 Grid(8,0)에 들어간다. 4097은 Python default cap 4300보다 작으므로 이 검사는 Python 자체의 예외가 아니라 새 Claim V1 guard가 작동함을 구분한다.

직접 canonical boundary/reduction 검사는 **98개: 허용 60, 구조화된 거부 38**이었다. End-to-end 추가 검사는 4096자리 성공 2개와 4097자리 거부 4개, 총 6개이며 각 case를 양쪽 경로에서 확인했다.

## R5. Reduction before limit: PASS

유효 kernel result는 양의 denominator를 갖는다. `g=gcd(n,d)>0`로 두고 `(n/g,d/g)`를 만든 뒤 각각 검사하므로 unreduced 표현 크기가 아닌 canonical 값의 표현 크기를 제한한다.

독립 기대값 reduction은 별도 Euclidean algorithm으로 계산했다. `G=10**6000+7`을 사용하여 다음을 검사했다.

```text
2G / 6G  →  1/3
-2G / 6G → -1/3
0 / G    →  0/1
```

또 canonical 값이 정확히 4096자리인 pair에 거대한 공통 인자를 곱한 경우는 허용하고, 약분한 뒤에도 4097자리이면 거부했다. 원본 Ratio의 분자/분모는 변하지 않았다. Fast의 zero lane에 큰 unreduced denominator가 남아 있어도 최종 0/1이 보존됐다.

`gcd(0,d)=d`이므로 zero의 0/1 정규화도 수학적으로 성립한다. Negative denominator, forged internal result와 같은 기존 kernel의 유효 결과가 아닌 입력까지 새 공개 지원 범위로 확대하지 않았다.

## R6. Slow / fast refusal 일치: PASS

두 경로의 전체 Failure field를 직접 정해 둔 기대 record와 비교했다. Code와 phase만 확인한 것이 아니라 message, atom, component, scope, J 상태, semantic SHA를 포함한다.

Original 4301자리 반례, 4097자리 canonical numerator overflow, denominator overflow 및 부호 반전에 대해 모두 같은 거부다. 정확히 4096자리 denominator를 가진 올바른 claim은 ±분자 모두 `ARITHMETIC_MATCH / COMPUTED`이며, 두 경로의 `computed_json`이 동일하다. 성공 결과도 `ARITHMETIC_ONLY / J_NOT_VERIFIED`를 유지한다.

## R7. Process-global workaround 없음: PASS

Production delta 전체와 adapter AST를 확인했다. `sys.set_int_max_str_digits`, dynamic import/eval/exec 또는 전역 numeric setting 변경 코드가 없다. 실행 중 builtin setter 호출도 관찰했고 0회였다. 검사 전후 값은 4300으로 동일했다.

새 guard는 Python 전역 제한을 끄거나 높이는 대신 현재 결과의 representation boundary에서 fail-closed로 동작한다. 출력 문자열의 limit을 초과한 값을 자르거나 근삿값으로 대체하지 않는다.

Python 공식 문서는 integer-string conversion default cap 4300 및 조정 가능한 interpreter 설정을 설명한다. 이 감사의 실행 환경은 그 default 설정이다. 설정 자체를 감사 코드가 변경하지 않았다.

참고: https://docs.python.org/3.12/library/stdtypes.html#integer-string-conversion-length-limitation

## R8. 새 source mutant 방어: PASS

정상 source copy를 먼저 통과시킨 다음, 별도 사본에서 실제 source line을 다음과 같이 바꿨다.

```python
# baseline
if abs(value) >= _OUTPUT_INTEGER_LIMIT:
# mutant
if False:
```

변형 사본은 실제 compile/import/실행했다. Standalone detector는 작성자 test, author helper 또는 old/new serializer agreement에 기대지 않고, 위 exact Failure 계약을 직접 요구한다.

| 경로 | Baseline | 실제 guard-removal mutant |
|---|---|---|
| exact_slow default | PASS | DETECTED: plain ValueError 재발 |
| exact_fast opt-in | PASS | DETECTED: plain ValueError 재발 |

작성자 새 mutant harness도 별도로 다시 실행하여 양쪽 검출을 확인했다. 기존 16개 source mutants 역시 새 suite 실행에서 baseline PASS / DETECTED 16/16이었다. 저장된 과거 `mutants.json`의 PASS를 결과로 재사용하지 않았다.

독립 Linux mutant의 raw SHA-256은 `4d4d2899055769a6077833e445ef62c1ca114a9bfbeac6edfd420a5a0679d777`이다. Windows harness mutant는 CRLF로 저장되어 `6e2946ca939392d8dc82baff438f0be54279a1aed87120ac0d7f638391ab2c21`이다. 같은 source를 CRLF로 변환해 두 번째 hash를 직접 재계산하여 차이가 줄바꿈에서 생김을 확인했다. Production baseline은 두 환경 모두 동일한 LF 바이트다.

증거: `local_evidence/independent_results.json`, `local_evidence/guard_removal_mutant/`, `remote_evidence/output_45_new_mutant.json`, `remote_evidence/related_105_mutants.json`, `mutant_line_endings_check.json`.

## R9. 회귀 suite: PASS

Windows Python 3.12.7의 새 clone에서 직접 실행했다. 명령, 실행 시각, return code, JUnit summary와 실제 stdout SHA-256은 `remote_evidence/provenance.json`에 있다. 아래 시간은 pytest stdout의 표시값이다.

| 실행 묶음 | 실제 결과 | pytest 표시 시간 |
|---|---|---:|
| 기존 관련 suite | 105 passed | 4.56 s |
| 새 output boundary / mutant suite | 45 passed | 0.40 s |
| 저장소 전체 pytest | 393 passed | 35.26 s |

세 실행 모두 exit 0이며 failures/errors/skips 0이다. **105와 45는 393에 포함되는 재실행 집합이므로 합산해 고유 test 수로 부르지 않는다.** 이번에는 repository의 `pytest.ini`가 지정한 전체 tests 수집을 실제 실행했으므로 “해당 저장소 전체 pytest 393 passed”라고 말할 수 있다. 이것을 전체 C1-B1 물리 검증이나 formal certification으로 해석해서는 안 된다.

이 패키지는 세 raw stdout log와 JUnit의 읽어낸 summary를 포함한다. XML 원본은 아래 감사 디렉터리에 남아 있으며 이번 전송 묶음에는 포함하지 않았다. 재현 script는 새로운 XML을 다시 생성한다.

```text
C:\Users\zun24\AppData\Local\Temp\c1b1_reaudit_65d8fd2_2z1b9i6t
```

테스트 통과는 위 수학·순서·독립 반례 검사를 대신하는 유일한 근거가 아니다.

## R10. Manifest / wire-contract consistency: PASS

**산술 의미 변경이 아니라 외부 Claim V1 출력 표현/자원 경계의 명시화로 판정한다.**

근거는 다음과 같다.

- Manifest에는 `wire_integer_max_decimal_digits=4096`이 이미 존재한다. 외부 claimed artifact의 정수도 `_claim_shape` → `_integer`에서 이 길이 제한을 받는다. 동일 canonical 값을 만드는 computed 쪽에 같은 상한을 적용하는 것은 wire 제한과 일관된다.
- Drift, kick, rounding 위치, 정확한 displacement/endpoint, FX overflow, geometry, guard equality 및 산술 refusal 순서는 바뀌지 않았다. 변경되는 것은 계산을 마친 결과를 wire 문자열로 표현하려는 후속 단계다.
- Manifest는 모든 failure code/phase의 닫힌 목록을 열거하지 않는다. 따라서 새로운 adapter resource refusal이 기존 열거형 계약을 위반하는 상황이 아니다.
- `CLAIM_OUTPUT_LIMIT`은 kernel을 감싼 `capture()` 이후, `canonical_data(computed)`에서 발생한다. 이를 drift/kick 실패나 물리 domain 실패로 바꿔 기록하지 않는다.
- 새 code/phase/message/처리 순서는 fix 문서에 명시되고, 구현 revision은 이 감사의 commit SHA 및 adapter source SHA-256으로 식별된다.

**중요한 경계:** manifest를 그대로 두는 것은 적절하지만, 그렇다고 같은 manifest hash가 old/fixed adapter의 모든 외부 관찰 가능 동작까지 동일하다고 증명하는 것은 아니다. Old는 일반 ValueError를 누출했고 새 코드는 정의된 refusal을 추가했다. 따라서 semantic SHA 하나만으로 F-CLAIM-1 수정 여부를 식별하지 말고 **target commit 또는 adapter source SHA**를 함께 고정해야 한다.

정확히 4097자리 결과를 예전 구현이 문자열로 만들 수 있었던 환경에서도 이제 Claim V1은 거부한다. 이는 kernel의 수치를 바꾸는 것이 아니라 canonical wire 상한을 적용하는 명시적 representation 선택이다. Byte-identical manifest를 “과거 구현도 원래 안전했다”는 근거로 해석하지 않는다.

## 성능 처리: 회귀 검산만, 승격 없음

기존 Drift/Kick/supplied-J K–D–K 산술 benchmark는 과거 snapshot에 대한 역사적 PASS로만 둔다. 이번에 그 수치를 다시 측정하거나 수정본의 성능 향상으로 승격하지 않았다.

새 claim regression JSON의 4행 × 9 raw sample을 직접 정렬하여 다섯 번째 값을 중앙값으로 재계산했다. Script와 old/new adapter source hash도 대조했다.

| 저장된 단일 synthetic claim 회귀 관측 | Old median | Fix median |
|---|---:|---:|
| slow 경로 | 193.119000 µs | 200.504750 µs |
| fast 경로 | 136.606750 µs | 138.789000 µs |

이 값은 **저장된 표본의 독립 재계산**이다. 이번 재감사의 새 timing 실행값이 아니며, 단일 fixture의 작고 국소적인 관측이므로 장기 성능 회귀나 향상을 확정하지 않는다. `REGRESSION ONLY / NO PERFORMANCE PROMOTION`을 유지한다.

증거: `remote_evidence/saved_regression/`, `remote_evidence/saved_claim_regression_check.json`.

## 최종 범위와 미해결

Claim Adapter fix와 overall Arithmetic V1 제출물 모두 **65d8fd2에 한해 INDEPENDENT REVIEW PASS**다. `exact_fast`의 default 승격은 하지 않는다.

아래 항목은 그대로 범위 밖이며 이번 PASS로 닫지 않는다.

```text
physical r_min binding
independent impulse
J physical correctness
external executor detailed compatibility
full C1-B1 replay
trajectory correctness
whole physical domain
formal certification
```

유지 상태: **ARITHMETIC_ONLY / J_NOT_VERIFIED / NotCertified**.

## 재현 및 증거 무결성

`README_KO.md`의 명령으로 standalone 재감사와 원격 Git/regression 검사를 재실행할 수 있다. `verify_packet.py`는 패키지 파일 SHA-256, snapshot과 원격 Git 해시, stdout 해시, 역사적 FAIL 보존 및 새 verdict 범위를 검사한다.

Remote evidence를 복사할 때 사용한 lossless UTF-8 JSON/XZ packet의 SHA-256은 `7d0b140fabd3f789e04015a659831eca12bea13f37a66e2e91e968605c22c767`이었다. 복원 후 모든 실제 stdout log의 SHA-256이 원격 실행 receipt와 일치하고, local snapshot source SHA도 원격 Git/checkout 값과 일치함을 다시 확인했다.
