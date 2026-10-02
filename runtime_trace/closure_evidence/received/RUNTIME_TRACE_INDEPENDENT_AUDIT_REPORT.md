# Runtime Trace regular 1-step prototype 독립 감사 보고서

- 감사 대상 ZIP: `runtime-trace-audit-d408a07.zip`
- ZIP SHA-256(독립 재계산): `91df4cfe0972ff2b048e87cb1c1f0fe9166392b66615bd90c8ce4e07860f7233`
- ZIP archive comment: `d408a07774bee44728d41d9a598b6d8142808075`
- 감사 범위: frozen gala 1.12.0 / regular orbit / 1 step / `c_init_velocity` / `c_leapfrog_step` / 실제 호출된 `c_gradient` 및 Hénon-Heiles gradient
- 최종 판정: **CONDITIONAL**

## 1. 결론 요약

이번 감사에서는 구현자가 기록한 record 수, scalar-FP 수, opcode 집계, endpoint, correspondence 결과를 expected constant로 사용하지 않았다. `machine_mapping.json`도 A1-A10의 독립 판정이 끝난 뒤에만 열어 사후 비교했다.

독립 감사 결과, 포함된 gala 바이너리에 결합되는 instruction stream, 36개의 scalar binary64 연산 의미, bit provenance, MXCSR, thread ownership, 함수 coverage, endpoint 및 attempt-04의 operand-width 결함 수정은 모두 강하게 지지된다. 특히 36개 `addsd/subsd/mulsd`는 trace의 `result`를 정답으로 사용하지 않고 operand raw bits를 유리수로 바꾼 뒤 IEEE-754 binary64 RN-even을 직접 구현하여 재계산했고, 모두 실제 post-XMM low 64-bit와 일치했다.

그러나 캡처 중 실행된 libc `memset` 구간 22 record가 참조하는 정확한 원본 libc 이미지(SHA-256 `3a15d66867d83762c7f2f1e37359cb8f6c5743edb369c65285cb0b1c4f7498bf`)가 ZIP에 없다. 따라서 424/446 record는 ZIP에 포함된 원본 ELF와 byte-for-byte 대조했지만, 나머지 22 record는 캡처 당시 libc 파일의 실제 bytes와 독립적으로 결합할 수 없다. 이 증거 공백 때문에 A1/A2, 그리고 엄격한 의미의 A3는 `UNRESOLVED`로 남긴다.

또한 현 감사 환경에는 GDB와 Python 3.12/gala 캡처 환경이 없어 fresh acquisition 재실행은 하지 못했다. 패키지의 `pytest`는 41 pass / 11 fail이었고, 11 fail은 모두 current checker가 캡처 당시 WSL의 절대 `.so` 경로를 다시 열려다 `FileNotFoundError`가 난 것이다. 이 문제는 trace 수학/데이터플로 자체의 반례는 아니지만 패키지 독립 재현성을 떨어뜨린다.

## 2. Frozen binary 및 snapshot 확인

독립 재계산값:

| 대상 | SHA-256 | 결과 |
|---|---|---|
| audit ZIP | `91df4cfe0972ff2b048e87cb1c1f0fe9166392b66615bd90c8ce4e07860f7233` | 일치 |
| gala wheel | `cc5f0cf3bc63a966a3c130b93f6c05026271fe7178492a02c6266c243b5fc2f0` | 일치 |
| leapfrog.so | `a6ac98736304bb9f6a92e473bba45da10d9b5b99f8019e2ca15eb6a7f86234fc` | 일치 |
| cybuiltin.so | `33d66d82c34c717560747ffbfca1d98f97432a0a671a0a210a0a225d8367ecaf` | 일치 |

Wheel 내부의 두 `.so` member도 vendor로 추출된 `.so`와 동일한 SHA-256을 가졌다.

ZIP에는 `.git`이 없으므로 archive comment의 SHA가 적혀 있다는 사실 이상으로 working tree clean, branch ancestry, origin 대비 commit 상태는 증명할 수 없다. 이 Git provenance는 별도 `UNRESOLVED`이며 Runtime Trace 기술 판정과 분리했다.

## 3. A1-A15 판정

### A1. Raw trace 자체의 무결성 — **UNRESOLVED**

**근거**
- `attempt-05/trace.jsonl`을 독립 파싱했다.
- 446개 record, sequence `0..445` 연속, 중복/누락 없음.
- init `0..190`, step `191..445`로 경계가 정확히 이어진다.
- PID는 전부 `409`, PTID는 전부 `[409,409,0]`이다.
- `runtime_pc - module_load_base == elf_address` 관계와 executable mapping/load-bias 관계를 검사했다.
- leapfrog/cybuiltin 소속 424 record는 포함된 ELF에서 직접 bytes를 읽고 trace bytes와 비교했으며 독립 `objdump` decode와도 일치했다.
- libc `memset` 소속 22 record는 캡처 당시 원본 libc 이미지가 없어서 원본 ELF bytes 대조가 불가능하다.

**독립 검증 방법**
- 별도 checker `/mnt/data/runtime_trace_independent_audit.py` 사용. Runtime Trace 구현 모듈을 import하지 않는다.
- trace hash-chain/sequence/region metadata를 직접 검증하고, ELF program header를 통해 vaddr→file offset을 독립 계산한다.

**재현**
```bash
python runtime_trace_independent_audit.py /tmp/runtime_trace_audit \
  --zip /mnt/data/runtime-trace-audit-d408a07.zip \
  --out /mnt/data/runtime_trace_independent_results.json
```

**발견된 문제**
- 캡처 당시 libc SHA `3a15d668...f7498bf`에 해당하는 원본 파일 부재. 전체 A1 PASS를 막는 증거 공백이다.

### A2. 실제 실행 instruction인지 확인 — **UNRESOLVED**

**근거**
- `gdb_capture.py`는 `stepi`로 instruction 단위 전진하며 pre/post PC/register/memory를 수집한다.
- acquisition source는 `machine_mapping.json` 또는 기존 T_bin을 읽어 예상 instruction을 채우는 경로가 없었다.
- attempt-05에 기록된 acquisition source hashes는 snapshot의 `run.py`, `harness.py`, `semantics.py`, `gdb_capture.py` 실제 SHA와 일치했다.
- packaged gala module의 PC/module/ELF/bytes/control-flow 연계는 독립 검증을 통과했다.
- libc 22 record는 당시 실제 libc image와의 byte binding을 독립적으로 재확인할 수 없다.

**발견된 문제**
- A1과 동일한 libc 원본 부재 때문에 전체 446 record를 캡처 당시 executable과 독립적으로 완전 결합했다고 말할 수 없다.

### A3. scalar FP instruction 완전성 — **UNRESOLVED**

**근거**
- 구현자 집계를 사용하지 않고 trace opcode를 독립 분류했다.
- captured stream에서 scalar FP는 36회: `mulsd 16`, `addsd 12`, `subsd 8`; init 14, step 22.
- 독립 decode된 gala/cybuiltin numerical path에는 FMA, packed FP arithmetic, DIV, SQRT 또는 기타 지원되지 않은 FP arithmetic이 발견되지 않았다.
- trace 전체 raw bytes를 독립 decode했을 때도 지원 외 FP opcode는 발견되지 않았다.

**왜 UNRESOLVED인가**
- “captured stream 내부의 완전성”은 강하게 지지되지만, 22 libc record를 캡처 당시 원본 ELF에 독립 결합할 수 없어 “실제로 실행된 전체 instruction stream의 완전성”이라는 더 강한 주장까지 PASS로 올리지 않는다.

### A4. 각 FP operation의 실제 의미 — **PASS**

**근거**
- 36개 scalar 연산 모두 source/destination raw 64-bit input을 직접 읽었다.
- memory operand는 독립 effective-address 계산 및 known-byte provenance로 확인했다.
- host float replay를 결과 oracle로 쓰지 않았다.
- raw binary64 → exact rational → exact ADD/SUB/MUL → 직접 구현한 binary64 RN-even 반올림으로 expected result bits를 산출했다.
- 36/36 모두 trace post-XMM low 64-bit와 정확히 일치했다.
- scalar instruction의 XMM upper lane도 보존됨을 확인했다.

### A5. load/store/move provenance — **PASS**

**근거**
- q/full_v/latent/gradient boundary memory와 XMM/GPR/stack을 byte 단위 knowledge map으로 추적했다.
- `movsd`, `movapd`, `movq`, GPR 이동, stack, memory load/store, zero-fill을 독립 처리했다.
- `movslq`, `vmovd`, `vpbroadcastb` 등의 폭/zero-extension 규칙을 opcode별로 검사했다.
- 최종 q/full_v 16-byte endpoint가 중간 write provenance로 모두 설명되었다.

**주의**
- 이 PASS는 저장 artifact 내부 데이터플로 의미론에 대한 판정이다. libc 실행 이미지와의 외부 binding 공백은 A1/A2에서 별도로 남겼다.

### A6. attempt-04 결함 — **PASS**

**근거**
- attempt-04 raw artifact를 별도로 검사했다.
- 실제 width 오류 예:
  - `movslq 0x4(%rdi),%rsi`: attempt-04 `[8,8]`, attempt-05 `[4,8]`
  - `movslq (%rdi),%rcx`: attempt-04 `[8,8]`, attempt-05 `[4,8]`
  - `vpbroadcastb %xmm0,%xmm0`: attempt-04 source 16-byte, attempt-05 source 1-byte
  - `cmpb`: attempt-04 8-byte, attempt-05 1-byte
- 독립 checker는 attempt-04를 `movslq width`로 FAIL시켰다.
- 현재 `correspondence.verify_flow`에도 독립 decode를 공급해 attempt-04를 실행했으며 `integer extension operand widths`로 실제 거절됨을 확인했다.
- attempt-05의 current semantics에는 opcode-specific routing width가 명시되어 있어 단순 endpoint 증상 회피가 아니라 operand model 자체가 수정되었다.

**제한**
- attempt-04 당시의 정확한 옛 `semantics.py`/`gdb_capture.py` source bytes는 snapshot에 없고 hashes만 남아 있어 구버전 코드의 정확한 line-level 원인은 재구성할 수 없다. 하지만 artifact 결함과 현재 checker의 거절은 독립적으로 확인됐다.

### A7. MXCSR — **PASS**

- 모든 446 record의 pre/post MXCSR를 독립 집계: `0x1fa0` 하나뿐.
- RC bits = `00` → round-to-nearest-even.
- FTZ = 0, DAZ = 0.
- FP exception masks가 유지되며 중간 control-bit 변경 없음.

### A8. thread — **PASS**

- numerical region의 모든 446 record가 동일 PTID `[409,409,0]`.
- 캡처 metadata의 owner thread와 일치.
- region에서 scheduler-locking `on`이 기록되어 있다.
- Python background threads 존재 자체는 보였지만 추적 numerical region에 다른 thread record가 개입한 증거는 없다.

### A9. 함수 및 module coverage — **PASS**

PC/module/ELF bytes 및 symbol/disassembly를 함께 검사했다.

- `c_init_velocity`: trace 진입 확인
- `c_leapfrog_step`: trace 진입 확인
- `c_gradient`: 실제 trace call path 확인
- `cybuiltin.so`의 Hénon-Heiles gradient: 해당 module SHA 및 `henon_heiles_gradient...` symbol 영역 record 확인

단순 로그 이름 문자열만으로 판정하지 않았다.

### A10. endpoint — **PASS**

독립 추출한 regular 1-step final bits:

```text
x  = 0x3f70000000000000
y  = 0x3f60000000000000
vx = 0x3fcffeff00000000
vy = 0x3fbffefe80000000
```

이 값은 감사 코드에 expected constant로 하드코딩하지 않았다. frozen fixture `regular_forward.u64.gz`와 manifest를 직접 읽고 step-1 bits를 추출하여 4/4 bit-for-bit 일치를 확인했다. Fixture raw SHA도 manifest와 독립 대조했다.

### A11. machine_mapping 사후 비교 — **PASS**

A1-A10 독립 분석이 완료된 뒤에만 `machine_mapping.json`을 읽었다.

사후 비교 결과:

```text
init: observed 14 / mapping 14 — PASS
step: observed 22 / mapping 22 — PASS
```

비교한 항목:
- ELF address
- opcode/kind
- dynamic occurrence/order
- T_bin의 source operand relation

operand relation은 mapping의 semantic source 이름을 실제 pre-operand raw bits와 대조하고, 각 operation 결과를 독립 exact-RN 계산으로 갱신하여 다음 operation까지 연결했다.

재현 로그: `runtime_trace_machine_mapping_posthoc.txt`.

### A12. mutation tests 독립성 — **PASS**

기존 mutation test 코드를 읽되 기존 PASS 보고를 증거로 사용하지 않았다. 기존 suite가 다루는 missing/duplicate/reorder/operand/result/address/instruction-byte/module-hash/MXCSR/thread/endpoint/operand-width 계열을 확인했다.

감사자가 별도로 추가한 mutation 4종은 trace chain/hash를 다시 맞춘 뒤에도 모두 거절되었다.

1. `scalar-kind-cloak-with-rehash` → FAIL: opcode/kind semantic mismatch
2. `paired-load-bias-shift-with-rehash` → FAIL: file offset inconsistency
3. `linkage-consistent-control-target-shift-with-rehash` → FAIL: load-bias + control-flow semantics
4. `scalar-upper-lane-mutation-with-rehash` → FAIL: scalar upper lane changed

즉 단순 hash/sequence integrity만 공격해서 다시 맞추는 것으로 구조적 오류를 숨길 수 없었다.

### A13. checker 자기참조 여부 — **PASS**

- acquisition은 `gdb_capture.py` + `semantics.py`를 사용한다.
- final verifier `correspondence.py`는 `gdb_capture.py`/`semantics.py`를 import하지 않고 별도 objdump decode, def-use, scalar replay를 수행한다.
- `machine_mapping.json`은 verifier의 raw-trace 검사가 끝난 뒤에만 읽는다.
- producer와 verifier가 동일 helper를 공유해 동일 오해를 자동 승인하는 직접적인 자기참조 구조는 발견하지 못했다.

추가로 독립 checker는 `record.kind`를 oracle로 믿지 않고 opcode↔kind consistency를 따로 검사했고, kind-cloak mutation을 거절했다.

### A14. 실패 정책 — **PASS**

코드 검토 및 mutation에서 다음 경로가 fail-closed임을 확인했다.

- unsupported/ambiguous instruction
- unknown numerical source
- alias/effective-address mismatch
- unsupported FP arithmetic
- nonfinite scalar input
- MXCSR mismatch
- module/hash mismatch
- thread change
- missing/duplicate/reordered record
- malformed/inconsistent trace metadata

`semantics.py`는 acquisition 단계에서 `Refused`를 사용하고, `correspondence.py`는 `AuditError`를 통해 최종 FAIL로 떨어진다. 무조건 계속 진행하여 PASS로 바꾸는 fallback은 발견하지 못했다.

### A15. 테스트 및 재현 — **UNRESOLVED**

현 감사 환경:

```text
Python 3.13.5
Linux x86_64
objdump: available
nm: available
gdb: unavailable
```

따라서 fresh GDB acquisition 자체는 재실행하지 못했다.

실행한 명령:

```bash
python -m pytest runtime_trace/tests -q
```

결과:

```text
41 passed, 11 failed
```

11 failures는 모두 current correspondence checker가 캡처 당시 절대 경로
`/home/otherside123/venvs/gate2c1-trace/.../*.so`
를 열려고 하면서 발생한 `FileNotFoundError`이다. 이는 assertion이 trace 반례를 찾은 실패가 아니라 패키지 이식성 문제다. 하지만 감사 계약의 “직접 pytest 및 가능한 경우 acquisition 재실행”을 완전 충족하지 못했으므로 A15는 `UNRESOLVED`다.

## 4. 구현자 주장과 마지막 사후 비교

독립 분석을 끝낸 뒤 구현자 보고와 비교했다.

| 항목 | 독립 결과 | 구현자 보고와 비교 |
|---|---:|---|
| dynamic records | 446 | 일치 |
| init / step | 191 / 255 | 일치 |
| scalar FP | 36 | 일치 |
| init / step FP | 14 / 22 | 일치 |
| mulsd/addsd/subsd | 16 / 12 / 8 | 일치 |
| MXCSR | 0x1fa0 throughout | 일치 |
| endpoint | fixture bit-for-bit | 일치 |

이 일치는 독립 판정의 근거가 아니라 감사 후 사후 대조 결과다.

## 5. 결함 및 미해결 분류

### Critical: 0

확인된 stored trace의 scalar arithmetic/result/provenance/endpoint를 틀리게 만드는 Critical 반례는 발견하지 못했다.

### Major: 1

**M1. 캡처 당시 원본 libc image 부재**

- 영향: 22/446 `memset` 내부 record를 캡처 당시 정확한 ELF bytes에 독립 결합할 수 없다.
- 결과: A1/A2 및 엄격한 A3의 full PASS를 차단한다.
- 필요한 보강: SHA-256 `3a15d66867d83762c7f2f1e37359cb8f6c5743edb369c65285cb0b1c4f7498bf`와 일치하는 당시 libc image를 package에 포함하고, 22 records의 vaddr/file-offset/bytes/decode를 다시 대조해야 한다.

### Minor: 1

**m1. checker/test의 절대 runtime path 의존**

- current correspondence code가 trace에 기록된 캡처 당시 절대 `.so` path를 직접 다시 연다.
- 결과: 원본 환경 밖에서는 packaged vendor `.so`가 있어도 captured tests 11개가 `FileNotFoundError`로 실행되지 않는다.
- 권장: module SHA→packaged frozen image resolver를 사용하고, 기록된 absolute path는 provenance metadata로만 취급한다.

### UNRESOLVED

1. missing captured libc 때문에 22 records의 original-byte binding.
2. GDB/Python 3.12/gala 동일 환경에서 fresh 1-step acquisition 재실행.
3. ZIP에 `.git`이 없으므로 working tree/ancestry/origin 상태의 Git provenance.

## 6. 최종 판정

**CONDITIONAL**

현재 증거로 신뢰할 수 있는 범위는 다음과 같다.

> 포함된 frozen gala binaries에 결합된 regular 1-step trace에서, scalar FP operation의 동적 순서·operand bits·IEEE-754 RN-even 결과·bit provenance·함수 coverage·최종 endpoint가 서로 일관되며, attempt-04의 operand-width 결함은 attempt-05에서 수정되었다.

그러나 정확한 캡처 당시 libc binary가 없으므로 전체 dynamic stream 446/446의 original executable-byte correspondence를 독립 인증했다고 확대해서는 안 된다. 또한 fresh acquisition을 재실행하지 못했으므로 이 보고서는 저장 artifact의 강한 독립 감사이지 새로운 런타임 캡처 재현 인증은 아니다.

이 결과는 **Numeric IR, V2 자동 연결, 10-step, 100-step, 긴 궤적, gala 전체, 범용 x86 tracer, 다른 OS/CPU/wheel, 연속 Hénon-Heiles 물리 정확성**에 대한 인증이 아니다.

## 7. 감사 산출물

- `runtime_trace_independent_audit.py`: 구현 코드와 분리한 독립 checker
- `runtime_trace_independent_results.json`: attempt-05 독립 결과
- `runtime_trace_attempt04_independent_results.json`: attempt-04 독립 결과
- `runtime_trace_new_mutations.py`: 감사자 추가 mutation 4종
- `runtime_trace_new_mutation_results.json`: mutation 결과
- `runtime_trace_machine_mapping_posthoc.txt`: A1-A10 후 machine_mapping 사후 비교
- `runtime_trace_pytest_local.log`: local pytest 재현 로그
- `runtime_trace_audit_evidence_manifest.json`: 감사 산출물 hashes 및 환경
