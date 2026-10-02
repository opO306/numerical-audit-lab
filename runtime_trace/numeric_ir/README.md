# Runtime Trace → Numeric IR regular 1-step prototype

**구현 및 별도 checker 검증: PASS. Numeric IR의 외부 독립 재감사는 아직 수행하지 않았다.**

Runtime Trace의 기존 독립 재감사 `CLOSED / PASS`는 frozen gala 1.12.0,
regular orbit, init과 1-step의 machine execution ↔ runtime trace 대응에 한정한다.
그 판정과 수령 원본은 [현재 상태](../../current/STATUS.md)와
[closure 재감사 보고서](../../current/RUNTIME_TRACE_CLOSURE_REAUDIT_REPORT.md)에 있다.
이 디렉터리는 실제 scalar ADD/SUB/MUL occurrence를 대수적 재작성 없이
Numeric IR 산술 node로 1:1 변환하는 새 prototype이다.

## 생성 및 검사 결과

먼저 audited attempt-05를 변환하고 checker를 통과시켰다. 이후 기존
closure-fresh-01을 별도로 변환·검사하고, 전체 normalized IR을 비교했다.
새 GDB acquisition은 실행하지 않았다. 생성·검사 code HEAD는
`6bd4246b97bafc742f3de54332677277905406bf`이다.

| 항목 | attempt-05 | closure-fresh-01 |
|---|---:|---:|
| 원시 machine records | 446 | 446 |
| 실제 scalar arithmetic occurrence | 36 | 36 |
| 생성 IR arithmetic node | 36 | 36 |
| value/provenance node | 254 | 254 |
| COPY byte-slice edge | 140 | 140 |
| arithmetic input edge | 72 | 72 |
| provenance edge 합계 | 212 | 212 |
| 누락 / 중복 / extra / 재배열 | 0 / 0 / 0 / 0 | 0 / 0 / 0 / 0 |
| 독립 구현 checker | PASS | PASS |

산술은 ADD 12 / SUB 8 / MUL 16이며, phase별로 init 14 / step 22다.
값 종류는 COPY_BITS 135 / ZERO_BITS 72 / ARITHMETIC_RESULT 36 /
LOAD_BITS 9 / CONST_BITS 2다. 산술 수를 하드코딩하여 맞추지 않는다.
각 산술 input 0은 destination pre-value, input 1은 AT&T source다.
identity는 producer occurrence와 storage relation으로 정하며 같은 raw bits로 합치지 않는다.

원 source trace와 생성 IR의 SHA-256:

```text
attempt-05 trace:
fec0379874f2a3ae792f041d553dd34533f90b02ad9bcf9d43cb022ef03e149c
attempt-05 numeric_ir.json:
bbb912c041cb47cf2f3814d416a298c3c6469c35a47c9b7cda629c11415586ba

closure-fresh-01 trace:
e0bd088e844561ef6752b6498d734e32d94d20ae0abbfc7853b0fd85504cad86
closure-fresh-01 numeric_ir.json:
c34576f87bd4abc5bdc5fc2f67e68251ec30d5659776ade984fd15ab2bcb5296

전체 normalized Numeric IR SHA-256 — 두 source 일치:
1ba19c48b8f812ad91ccaf8ebe5d930f6d510967f0589f8e91affcbc16bdd8f2
```

[old IR](artifacts/attempt-05/numeric_ir.json),
[old checker report](artifacts/attempt-05/checker_report.json),
[old coverage](artifacts/attempt-05/coverage_report.json),
[fresh IR](artifacts/closure-fresh-01/numeric_ir.json),
[fresh checker report](artifacts/closure-fresh-01/checker_report.json),
[fresh coverage](artifacts/closure-fresh-01/coverage_report.json),
[normalized comparison](artifacts/normalized_comparison.json)에 실제 결과를 보존했다.
source 전체는 raw hash·chain·진단 경로 때문에 정규화에서 제외한다.
산술 순서, 모든 값의 producer/storage/byte-slice 관계와 raw bits는 유지한다.
주소 차이를 지우기 위해 producer identity를 없애지 않는다.

## 구조와 검증 경계

[CONTRACT](CONTRACT.md)는 직렬화 필드와 phase 경계를 정의한다.
`schema.py`는 canonical serialization, `translator.py`는 변환,
`checker.py`는 별도 raw byte-state 재구성, `normalization.py`는 전체 graph 비교를 담당한다.
checker production code는 translator의 핵심 conversion을 import하거나 호출하지 않는다.
test fixture에서만 translator로 후보 IR을 만든다.

양쪽은 이미 감사된 raw-only `verify_linkage`, `disassembly_for_rows`, `verify_flow`를
사용한다. 이 공용 기계/ELF 검증 경계를 숨기지 않는다. Numeric IR 값 재구성은 별도 코드다.
machine_mapping.json, T_bin 및 V2를 새 conversion/checking의 입력으로 사용하지 않는다.
기존 Runtime Trace 코드·attempt-05·closure evidence·frozen binaries·과거 audit를 수정하지 않았다.
[기존 141개 파일 보존 검사](artifacts/preservation_report.json)는 SHA-256와 size 모두 PASS다.

캡처 밖 init→step caller setup은 추적되지 않았다. q/full_v/latent의 step COPY edge는
캡처된 init endpoint와 step start의 상태 연결이다. 실제 caller copy instruction이나
같은 비트를 다시 쓰지 않았다는 증명이 아니다. step gradient 및 XMM은 명시적 captured
boundary root다. 이 계약은 전체 caller 실행 provenance나 물리 법칙을 추가하지 않는다.

## 공격과 테스트

재해시한 IR 공격 19종을 모두 거부한다:

1. 산술 node 삭제, 복제, 순서 교환, kind 변경.
2. input ID, operand/result bits, trace sequence, ELF address 변경.
3. equal-bit producer edge로 변경, 서로 다른 equal-bit read 병합, extra arithmetic 삽입.
4. destination lane/source offset 변경, dangling edge, cycle, unregistered value.
5. phase-boundary root 초기화, producer identity 복제.

공격 뒤 normalized hash를 다시 계산하고 순서 공격의 dense IR sequence도 다시 맞춘다.
별도로 raw chain/hash/metadata까지 다시 계산한 kind-label 공격을 거부한다.
또 bool/정수형 float 타입 혼동 회귀 18개가 있다. 검토 중 3-field bool 변조가 실제 PASS를
우회했던 결함을 재현한 뒤, strict type 검사와 canonical JSON byte 비교로 수정했다.
source relocation, translator import 차단, mapping/T_bin 없는 packaged root, malformed metadata,
register 누락, buffer overlap 및 CLI PASS/FAIL도 검사한다.

```text
Numeric IR dedicated suite:
python -m pytest runtime_trace/numeric_ir/tests -q
94 passed in 48.24s

최종 전체 관련 suite — WSL Python 3.12.3:
python -m pytest tests runtime_trace/tests runtime_trace/numeric_ir/tests -q
410 passed in 103.63s
```

dedicated suite는 checker 구현자가 마지막 code 변경 후 실행했다.
전체 관련 suite는 최종 artifact 생성 후 새로 실행했다.
[최종 combined log](artifacts/combined_pytest.log)에 실제 결과가 있다.
skip·xfail·warning을 PASS 수에 포함하지 않았다.
변환기와 checker의 task별 spec/quality review는 모두 Approved다.

## 재실행과 남은 범위

새 출력 디렉터리와 새 report 파일을 사용한다:

```bash
python -m runtime_trace.numeric_ir.translator \
  --source runtime_trace/artifacts/attempt-05 \
  --out /tmp/numeric-ir-attempt05-new --root "$PWD"
python -m runtime_trace.numeric_ir.checker \
  --ir /tmp/numeric-ir-attempt05-new/numeric_ir.json \
  --source runtime_trace/artifacts/attempt-05 \
  --report /tmp/numeric-ir-attempt05-check-new.json --root "$PWD"
```

독립 checker가 두 IR에 각각 PASS를 낸 뒤 `compare_normalized(old, fresh)`를 호출한다.
직렬화 정규화는 candidate의 source 유효성을 검증하는 함수가 아니다.
converter는 출력 디렉터리를 독점 생성하고 conversion report를 마지막 완료 표시로 쓴다.
REFUSED/일반 Python 예외의 cleanup과 process-kill atomic publication은 구분한다.
출력은 두 파일과 성공 completion report를 확인한 뒤 사용한다.

시작 HEAD는 `736b55198947bd3c8cecc024a12af156459cfa02`이며, 작업은
`numeric-ir-regular-1step` 로컬 branch에서 수행했다. 최종 배포 HEAD·Git ancestry·manifest는
별도 delivery metadata와 Git bundle에 기록한다. Push하지 않았다.

V2 연결/호출/bound 생성, Numeric IR→V2 translator, 10/100-step, chaotic orbit,
범용 x86, FMA/SIMD/DIV/SQRT 산술 확장, 성능 최적화, 새로운 물리 검증은 구현하지 않았다.
현재 결과는 이 고정된 1-step prototype의 구현·checker 검증이며 외부 독립 감사나 형식 증명이 아니다.
