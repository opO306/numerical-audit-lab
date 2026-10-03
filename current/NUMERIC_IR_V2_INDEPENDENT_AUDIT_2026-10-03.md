# Numeric IR → frozen V2 regular init + 1-step 독립 감사 보고서

감사일: 2026-10-03  
감사 대상 ZIP: `numeric-ir-v2-regular-1step-34e062d.zip`  
제시/재계산 ZIP SHA-256: `993863754f689b472b8e9d24b72ce81a52be4029cd6e73fc9deed325e3100ad8`

## 최종 판정

**PASS**

- Critical: 0
- Major: 0
- Minor: 0
- 기술적 UNRESOLVED: 0
- 판정 범위: **audited Numeric IR → unchanged frozen V2 operation layer / regular orbit / init + 1-step / 두 byte-pinned IR 입력**

이 PASS는 10/100-step, caller 전체 실행, caller error continuity, chaotic orbit, horizon, V2.1, continuous-physics 정확성, 또는 V2가 center bits를 독립 재계산했다는 의미가 아니다.

## 독립 감사 결과

### A1. ZIP 및 manifest 무결성 — PASS

- ZIP SHA-256 재계산값이 제시값과 일치.
- root `manifest.json`: **875 entries**.
- 실제 payload 파일: **875 files**.
- missing/extra: **0/0**.
- 모든 entry의 SHA-256 및 byte size 재계산: **875/875 일치**.

### A2. Git provenance 및 snapshot binding — PASS

- bundle head: `34e062dee6bf0564d6aafa8ea901de317f7e2871`.
- branch: `numeric-ir-v2-regular-1step`.
- start: `d679c8ba32d98e6076708b2b70b93c4eb37f5a49`.
- start commit은 target HEAD의 ancestor임을 독립 확인.
- `git fsck --full`: clean.
- start tracked files 761, target tracked files 807, 신규 46, 삭제 0.
- 기존 tracked 761개 중 변경된 파일은 `.gitattributes`, `current/STATUS.md` 두 개뿐.
- 따라서 보호 대상 기존 파일 **759개는 Git object 기준 불변**.
- snapshot files **807**, target HEAD tracked files **807**, missing/extra **0/0**.
- snapshot ↔ HEAD Git blob byte mismatch **0**.

오프라인 ZIP만으로 원본 개발 머신이 역사적으로 실제 `git push`를 한 적이 없다는 사실 자체는 증명할 수 없다. 다만 전달된 bundle/snapshot에는 target HEAD와 일치하는 재현 가능한 이력이 있고, 이번 기술 판정은 그 전달 이력을 기준으로 한다.

### A3. frozen V2 prerequisite — PASS

- `lab/v2_bound.py` SHA-256: `48b91d0c45fd7f62dd09df4db28756e6f82c6bd464a040dc60ac1c924ed99780`.
- `K == 4`, `Form`, `step_forms` interface 확인.
- 시작 commit 대비 frozen V2 파일은 변경되지 않음.

### A4. 감사된 Numeric IR 입력 identity — PASS

독립 재계산:

- attempt-05: `bbb912c041cb47cf2f3814d416a298c3c6469c35a47c9b7cda629c11415586ba`
- closure-fresh-01: `c34576f87bd4abc5bdc5fc2f67e68251ec30d5659776ade984fd15ab2bcb5296`
- 두 입력의 normalized Numeric IR: `1ba19c48b8f812ad91ccaf8ebe5d930f6d510967f0589f8e91affcbc16bdd8f2`

핀 값과 모두 일치한다.

### A5. IR arithmetic occurrence → V2 call mapping — PASS

두 입력 각각:

- IR arithmetic nodes: **36**
- 실제 adapter `step_forms` 호출: **36**
- ADD/SUB/MUL: **12 / 8 / 16**
- 누락/중복/추가/재배열: **0 / 0 / 0 / 0**

adapter의 `step_forms`를 감사 시점에 wrapper로 계측하여 각 호출을 직접 관찰했다. 모든 호출은 정확히 1개 operation structure이며, 각 호출의:

- V2 op kind
- output state ID
- `[input0_state_id, input1_state_id]` 순서
- input/output represented-center regs
- input Form key 집합

이 해당 Numeric IR occurrence와 정확히 일치했다.

### A6. value/state/COPY/boundary correspondence — PASS

두 입력 각각:

- original IR values: **254**
- selected scalar state bindings: **176**
- boundaries: **12**

독립 구현으로 COPY slice를 재귀 추적하여 각 8-byte lane을 다시 구성했다.

- mixed/incomplete lane 없음.
- COPY source와 destination center bits 일치.
- 같은 bits를 가진 서로 다른 dynamic value ID를 병합하지 않음.
- arithmetic result는 해당 producer operation에 연결됨.
- boundary 9개는 `CAPTURED_INPUT_ROOT`.
- boundary handoff COPY 3개는 `CAPTURED_STATE_HANDOFF`.
- handoff의 `trace_sequence` 및 source operand identity는 null로 유지됨.
- boundary COPY를 V2 arithmetic operation으로 생성하지 않음.

### A7. V2 Form 결과 독립 재계산 — PASS

repository의 adapter/checker 계산 코드를 사용하지 않고 별도 감사 스크립트에서 다음을 다시 구현했다.

- IEEE-754 binary64 bits → exact `Fraction` 변환
- V2 `up`, `up_q`, `rnd_err`
- ADD/SUB affine Form propagation
- MUL affine Form propagation
- root zero Form / COPY Form 전달

이 독립 구현으로 **전체 expected correspondence document**를 다시 생성하여 저장된 결과와 object-level exact equality를 비교했다.

결과:

- attempt-05 correspondence SHA-256: `3edd42937e58c7655dc951d3683802ffddd5ae7cbfda27c5793d6cb42c7d35f3`
- closure-fresh-01 correspondence SHA-256: `a692db2f6f3b5b9a45de71cf8516fef4c8d2cdc8b173c6cdb20259c5812c572f`
- 두 문서 모두 독립 생성 expected와 **완전 일치**.

### A8. checker 독립성 — PASS for current frozen scope

- `checker.py`는 `adapter.py`를 import/call하지 않음.
- checker는 IR validation, COPY lane selection, state reconstruction, V2 calls, full-document expected reconstruction을 별도로 수행함.
- 공유되는 것은 byte-pinned input data와 frozen V2 prerequisite 자체이며, 현재 계약에서 허용되는 범위임.

추가로 본 감사에서는 adapter/checker 어느 쪽도 사용하지 않는 제3의 재구성 경로로 현재 두 frozen 입력의 full correspondence를 확인했으므로 현재 범위의 common-mode 위험을 별도로 줄였다.

### A9. old/fresh normalized correspondence — PASS

source-instance metadata만 제거한 뒤 두 전체 correspondence가 exact equal.

독립 normalized SHA-256:

`1493fd071d6be290bb4736fdd36b8723334793c308896998b5c7cf88b9a690a6`

저장된 비교 결과와 일치.

### A10. fail-closed / mutation behavior — PASS

전체 69-test V2 suite에서 저장된 17개 semantic mutation + 2개 malformed Form rejection이 전부 통과했다.

추가로 감사자가 별도 생성한 변조를 checker에 직접 넣었다.

- V2 operation kind 변조 → REJECTED
- state box 변조 → REJECTED
- boundary classification 변조 → REJECTED
- extra operation + dense V2 resequence → REJECTED
- 같은 raw bits의 다른 dynamic state ID 치환 → REJECTED

또한 5,000자리 JSON integer를 별도 CLI 입력으로 사용한 결과:

- exit code **2**
- stderr JSON `REFUSED`
- traceback 없음
- stdout 없음
- output directory 생성 없음

### A11. fresh regeneration / byte stability — PASS

현재 target HEAD에서 두 입력을 새 output directory에 다시 adapter 실행 후 checker 실행.

- attempt-05 `correspondence.json`: 저장 artifact와 **BYTE_IDENTICAL**
- attempt-05 `completion_report.json`: **BYTE_IDENTICAL**
- closure-fresh-01 `correspondence.json`: **BYTE_IDENTICAL**
- closure-fresh-01 `completion_report.json`: **BYTE_IDENTICAL**
- 재생성 결과 checker: 두 입력 모두 PASS.

### A12. test reproduction — PASS

감사 환경에서 직접 실행:

```text
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest runtime_trace/numeric_ir/v2/tests -q
69 passed in 5.44s
```

```text
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest \
  tests runtime_trace/tests runtime_trace/numeric_ir/tests \
  runtime_trace/numeric_ir/v2/tests -q
479 passed in 56.07s
```

skip/xfail 없음. 두 명령 모두 exit 0.

## 결함 분류

- Critical: 0
- Major: 0
- Minor: 0
- 기술적 UNRESOLVED: 0

## 범위 제한

이번 PASS가 증명하는 것은 정확히 다음 연결이다.

```text
감사 완료된 두 Numeric IR
        ↓
각 36개 ADD/SUB/MUL occurrence의 identity/order/state 연결
        ↓
unchanged frozen V2 step_forms 실제 호출
        ↓
해당 represented centers에 대한 V2 Form propagation
```

증명하지 않는 것:

1. V2가 output center bits를 독립적으로 재계산했다는 것.
2. 캡처 밖 caller가 실제로 단순 COPY만 했다는 것.
3. init endpoint → step start 사이 exact-program error continuity.
4. 10/100-step 또는 장기 trajectory correctness.
5. chaotic orbit/horizon/V2.1.
6. continuous physical trajectory와의 최종 오차.

특히 **다음 multi-step 확장의 핵심 선행 문제는 caller/error continuity**다. 현재 boundary byte equality만으로는 계산된 binary64 state가 같다는 것은 알 수 있지만, 캡처 밖 caller가 exact mathematical state를 어떻게 변화시켰는지까지는 알 수 없다. 따라서 이를 닫지 않고 Form을 다음 step으로 계속 넘기면 one-step PASS를 trajectory PASS로 잘못 확장하게 된다.

## 최종 결론

**Numeric IR → frozen V2 regular init + 1-step은 `CLOSED / PASS`로 승격해도 된다.**

다만 승격 문구는 반드시 위 범위 그대로 유지해야 하며, 다음 단계는 10/100-step 전수 확장보다 먼저 **init/step 사이 caller transition의 error continuity를 증명하는 가장 싼 방법**을 찾는 것이 적절하다.
