# Numeric IR → frozen V2 regular init + 1-step 구현 보고 — 2026-10-03

**IMPLEMENTED / CHECKER PASS / INDEPENDENT AUDIT PENDING.**

이번 결과는 감사된 두 Numeric IR의 산술 occurrence를 동결된 V2 operation layer에
연결한 prototype이다. V2는 IR이 제공한 represented center bits를 받아 error Form을
전파한다. V2가 binary64 결과 center를 독립 재계산했다는 뜻은 아니다.
Boundary의 Form 전달도 선언된 IR 상태 연결에 한정하며, 캡처 밖 caller의 실제 copy
명령·산술·rounding이나 전체 caller의 error continuity를 증명하지 않는다.
외부 독립 감사가 끝나기 전에는 이 층을 CLOSED / PASS로 올리지 않는다.

## 선행 감사와 변경 범위

Runtime Trace → Numeric IR regular init + 1-step은 수령한 외부 독립 감사에서
A1–A12 PASS, Critical/Major/Minor/UNRESOLVED 0, Final PASS를 받았다.
그 **CLOSED / PASS** 범위와 원본 감사 파일은 [현재 상태](../../../current/STATUS.md)에
기록했다. 선행 PASS는 frozen Gala 1.12.0의 해당 regular 실행으로 한정된다.

새 구현은 이 디렉터리의 adapter, 별도로 작성한 checker, normalization, data contract,
테스트와 새 evidence다. Adapter는 Numeric IR만 읽으며 machine_mapping, old T_bin,
예상 disassembly, Gate expected graph나 이전 V2 결과를 생성 근거로 사용하지 않는다.
새 x86 decoder도 추가하지 않았다. Checker는 adapter 핵심 translation/validation/lane
resolver를 호출하거나 공유하지 않고, IR에서 전체 대응과 상태를 별도로 재구성한다.
두 구현은 이미 동결·감사된 V2 operator를 각각 호출한다. 이는 adapter 검사이며 V2
수학 자체의 새 증명이나 재감사가 아니다.

기존 Runtime Trace, Numeric IR, frozen V2 및 계약을 수정하지 않았다.
시작점에서 `current/STATUS.md`와 `.gitattributes`를 제외한 기존 tracked 파일 **759개**의
원본 SHA-256과 크기를 보호 대상으로 정했고, [보존 검사](artifacts/protected-after.json)에서
변경 0을 확인했다. 두 제외 파일은 요청된 상태 기록과 새 evidence의 raw-byte 보존 설정을
위해 수정했다.

## 입력과 실제 실행

최초 입력은 [attempt-05 Numeric IR](../artifacts/attempt-05/numeric_ir.json)이다.
저장된 출력 bytes와 completion hash를 확인하고 독립 checker PASS를 얻은 뒤,
[closure-fresh-01 Numeric IR](../artifacts/closure-fresh-01/numeric_ir.json)을 별도로 생성·검사했다.
이번 작업에서 새 GDB acquisition은 실행하지 않았다.

| 입력 | 원본 Numeric IR SHA-256 |
|---|---|
| attempt-05 | `bbb912c041cb47cf2f3814d416a298c3c6469c35a47c9b7cda629c11415586ba` |
| closure-fresh-01 | `c34576f87bd4abc5bdc5fc2f67e68251ec30d5659776ade984fd15ab2bcb5296` |

두 파일의 common normalized IR SHA-256은
`1ba19c48b8f812ad91ccaf8ebe5d930f6d510967f0589f8e91affcbc16bdd8f2`다.
허용 입력은 [data pins](audited_inputs.json)의 두 감사된 byte identity뿐이다.
같은 bytes를 다른 경로로 옮기는 것은 허용하지만 다른 IR bytes는 REFUSED한다.
개수나 graph를 expected constant로 고정하지 않고 해당 IR에서 도출한다.

실제로 호출한 frozen interface는 `lab.v2_bound.step_forms`, `K=4`다.
import된 모듈과 요청한 repository의 `lab/v2_bound.py` 모두 LF-normalized SHA-256
`48b91d0c45fd7f62dd09df4db28756e6f82c6bd464a040dc60ac1c924ed99780`을 검사한다.
각 IR ADD/SUB/MUL마다 원래 순서대로 V2 ADD/SUB/MUL 하나를 실행한다.
Fusion, split, CSE, constant folding, 재배열이나 동등 식 치환을 하지 않는다.

## correspondence 결과

| 항목 | attempt-05 | closure-fresh-01 |
|---|---:|---:|
| 독립 checker | PASS | PASS |
| IR arithmetic nodes | 36 | 36 |
| V2 arithmetic operations | 36 | 36 |
| ADD / SUB / MUL | 12 / 8 / 16 | 12 / 8 / 16 |
| 전체 IR value nodes | 254 | 254 |
| scalar state bindings | 176 | 176 |
| boundary records | 12 | 12 |
| missing / duplicate / extra / reorder | 0 / 0 / 0 / 0 | 0 / 0 / 0 / 0 |

원본 value 배열과 producer/storage/slice provenance 전체를 보존한다.
State는 `value_id`와 byte offset으로 식별하므로 같은 raw bits의 서로 다른 dynamic
value를 합치지 않는다. 각 operation은 IR/V2/trace sequence, 종류, 세 value ID/raw bits,
module SHA, ELF address, instruction bytes, phase/step과 실제 V2 input/output Form을
기록한다. LOAD/CONST/ZERO root는 represented bits에 대한 zero Form, COPY는 연결된
Form, 산술 결과는 실제 V2 출력 Form으로 구분한다.

Boundary는 captured input root 9개와 captured state handoff 3개다.
Handoff COPY는 state binding이며 V2 arithmetic operation을 만들지 않는다.
Boundary `trace_sequence=null`과 캡처된 endpoint/start equality 의미를 유지한다.

- [attempt-05 output](artifacts/attempt-05/correspondence.json), [checker](artifacts/attempt-05/checker_report.json), [coverage](artifacts/attempt-05/coverage_report.json)
- [closure-fresh-01 output](artifacts/closure-fresh-01/correspondence.json), [checker](artifacts/closure-fresh-01/checker_report.json), [coverage](artifacts/closure-fresh-01/coverage_report.json)
- [normalized comparison](artifacts/normalized_comparison.json): **EQUAL**

출력 SHA-256은 attempt-05
`3edd42937e58c7655dc951d3683802ffddd5ae7cbfda27c5793d6cb42c7d35f3`, fresh
`a692db2f6f3b5b9a45de71cf8516fef4c8d2cdc8b173c6cdb20259c5812c572f`다.
Full normalized correspondence SHA-256은
`1493fd071d6be290bb4736fdd36b8723334793c308896998b5c7cf88b9a690a6`다.
비교에는 전체 value/state/operation/boundary와 frozen protocol을 유지하고 source-instance
label/IR byte hash 및 원 IR source의 trace hash/chain/diagnostic만 제거한다.

## 재현 명령과 evidence

최종 전용 V2 suite는 **69 passed in 5.84s**, 요청된 전체 통합 suite는
**479 passed in 103.62s**다. Skip/xfail 0이며 WSL Python 3.12.3에서
`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`로 새로 실행한 결과다.
첫 통합 실행은 기존 Numeric IR와 새 V2 테스트 모듈 이름 3개가 겹쳐 collection error로
중단됐다. 새 테스트 파일만 100% rename하여 해결했고 product/test 내용은 바꾸지 않았다.
[첫 실패 로그](artifacts/combined-collection-failed.log)도 보존한다.

초기 65/475 PASS evidence는 그대로 보존했다. 최종 코드 검토에서 adapter의 JSON 자원
제한 오류가 REFUSED 대신 traceback으로 끝나는 결함을 발견해 parser 경계의
ValueError/RecursionError를 AdapterRefused로 처리하고 회귀 시험 4개를 추가했다.
5,000자리 정수와 깊이 20,000 배열을 public API와 실제 별도 CLI에서 검사한다.
전역 정수·재귀 제한은 변경하지 않았다. 첫 수정 후 통합 실행의 478 PASS / 1 FAIL은
이미 AdapterRefused인 사유를 direct test가 너무 좁은 오류 문구로 검사한 실패였다.
기존 benchmark가 정수 제한을 해제한 환경에도 public 계약을 검사하도록 시험만 바로잡았다.
별도 CLI는 exit 2 / JSON REFUSED / traceback·stdout·출력 디렉터리 없음까지 유지한다.
해당 실패 [log](artifacts/validation-after-parser-fix/first-post-fix-combined-failed.log)와
[XML](artifacts/validation-after-parser-fix/first-post-fix-combined-failed.xml)도 보존했다.

수정 후 두 source를 다시 생성한 결과 기존 correspondence와 **BYTE_IDENTICAL**이고,
두 저장 파일을 독립 checker로 다시 통과시켰다. Normalized 비교도 기존 EQUAL/hash와 같다.
[byte stability](artifacts/validation-after-parser-fix/output-byte-stability.json)는 초기 manifest의
18개 payload가 모두 그대로임도 확인한다. 이전 저장 artifact는 재작성하지 않고 수정 후
검증만 `validation-after-parser-fix` 새 디렉터리에 기록했다.

요청된 12종을 포함한 **17개 semantic mutation을 모두 거부**했다.
수리한 dense sequence, operand/state/Form 참조, 같은 bits의 다른 dynamic ID,
boundary/산술 위장 공격을 포함한다. 별도 실제 CLI 시험에서는 correspondence와
completion SHA를 함께 다시 계산한 공격도 semantic FAIL이었다.
Checker의 과대 Form hex와 JSON 정수 오류는 traceback 없이 명시적 FAIL로 처리한다.
[최종 mutation 결과](artifacts/validation-after-parser-fix/mutation-results.json)는 실제 전체 JUnit에서 뽑은 17개 semantic
공격과 2개 malformed Form 검사, 총 19개 behavioral rejection 테스트의 실행 기록이다.
CLI와 JSON/type/publication 및 adapter parser 회귀 시험은 최종 69개 V2 suite에 포함된다.

새 output directory와 새 report 파일을 사용한다. 기존 저장 artifact를 수동 편집하지 않는다.

```bash
python -m runtime_trace.numeric_ir.v2.adapter \
  --ir runtime_trace/numeric_ir/artifacts/attempt-05/numeric_ir.json \
  --out /tmp/numeric-ir-v2-new-attempt
python -m runtime_trace.numeric_ir.v2.checker \
  --ir runtime_trace/numeric_ir/artifacts/attempt-05/numeric_ir.json \
  --correspondence /tmp/numeric-ir-v2-new-attempt/correspondence.json \
  --report /tmp/numeric-ir-v2-new-checker-report.json
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest \
  tests runtime_trace/tests runtime_trace/numeric_ir/tests \
  runtime_trace/numeric_ir/v2/tests -q
```

환경은 [execution environment](artifacts/execution-environment.json), 최초 생성은
[통합 실행 로그](artifacts/integration.log)에 보존한다. 최종 실행은
[전체 pytest 로그](artifacts/validation-after-parser-fix/combined-pytest.log),
[JUnit 원본](artifacts/validation-after-parser-fix/combined-pytest.xml),
[V2 pytest 로그](artifacts/validation-after-parser-fix/v2-dedicated-pytest.log)에 있다.
새 검증 파일의 SHA/size와 실제 479-test totals는
[최종 validation manifest](artifacts/validation-after-parser-fix/manifest.json), 최초 18개 payload는
[원 artifact manifest](artifacts/artifact_manifest.json)에서 확인한다.
세부 API, schema, 실패·publication 계약은 [CONTRACT](CONTRACT.md)에 있다.

## Git 및 남은 한계

작업 저장소는 `D:/numerical-audit-lab-recovered-2026-10-01`이다.
작업 시작 HEAD는 `d679c8ba32d98e6076708b2b70b93c4eb37f5a49`,
브랜치는 `numeric-ir-v2-regular-1step`이다. Push/fetch/merge하지 않았다.
종료 HEAD와 clean 상태, 독립 복원한 bundle ancestry, snapshot byte binding 및 ZIP manifest는
repository 밖 최종 delivery metadata에 기록한다. 구현 문서가 자신을 포함하는 commit SHA를
내부에 순환 기록하지 않는다.

외부 독립 감사는 아직 대기 중이다. 이 층의 결과를 다른 입력·instruction form, caller 전체,
10/100-step, chaotic orbit, 긴 궤적, horizon, V2.1, 새 bound나 물리적 인증으로 확대하지 않는다.
