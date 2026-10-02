# Runtime Trace regular 1-step independent audit closure 보강 — 2026-10-02

**현재 독립 감사 판정: CONDITIONAL. 재감사: PENDING.**
이번 작업은 구현자 측 closure 보강과 실제 재검증이다. 아래 PASS는 해당 검사 결과이며
감사자의 새 A1–A15 판정이나 formal execution certificate로 대신하지 않는다.
Numeric IR, V2 연결, 10/100-step을 시작하지 않았다. Push하지 않았다.

## 대상, 원 감사와 원본 보존

작업 저장소: `D:/numerical-audit-lab-recovered-2026-10-01`.
시작 branch는 `main`, HEAD는 `d408a07774bee44728d41d9a598b6d8142808075`, working tree는 clean이었다.
시작 시 로컬 `origin/main`도 같은 SHA였다. 이번에는 fetch하지 않았으므로 이것은 원격 서버의 현재 상태 확인이 아니다.
새 commit SHA와 최종 Git 상태는 배포 ZIP의 `DELIVERY_PROVENANCE.json`에 기록한다.

수령 보고서 전체와 감사자 checker 전체를 읽었다. 보고서의 권고를 별도 명령 권한으로 취급하지 않고
이번 사용자의 1–8 closure 요청을 작업 범위로 사용했다.
수령 파일은 [received](closure_evidence/received/)에 원래 bytes로 보존했다.

| 자료 | 실제 재계산 SHA-256 |
|---|---|
| 수령 보고서 | `bbc500b609e6af1c77a307dd6f35e7d2844533e9f85edd4d85be6673bacd7bad` |
| 수령 감사 번들 | `638f61995417ae2fb9acdbab8e370ef6c4461804765cb3e3eaf9a5d685bd6000` |
| 원 감사 대상 ZIP | `91df4cfe0972ff2b048e87cb1c1f0fe9166392b66615bd90c8ce4e07860f7233` |

수령 manifest가 나열한 파일 모두 hash/size를 다시 확인했다.
원 attempt-05의 **11개 파일 전부**를 작업 전 hash/size 및 원 감사 ZIP member bytes와 비교했다.
모두 동일하며 기존 trace, capture, execution, correspondence, validation, 로그와 baseline을 재작성하지 않았다.
[보존 증거](closure_evidence/attempt05_preservation.json)를 참조한다.

## Major 1: 정확한 libc 및 22 records

첫 실행 명령은 WSL의 `sha256sum /usr/lib/x86_64-linux-gnu/libc.so.6`였다.
현재 SHA와 보존한 [libc.so.6](frozen_binaries/libc.so.6)의 SHA는 모두
`3a15d66867d83762c7f2f1e37359cb8f6c5743edb369c65285cb0b1c4f7498bf`다.
마지막 검증에서도 live libc SHA가 동일했다. 다른 libc로 대체하지 않았다.

[closure_check.py](closure_check.py)는 acquisition/semantics/correspondence를 import하지 않는다.
ELF64 program header를 직접 파싱하고 실제 PT_LOAD executable segment 및 objdump bytes/decode에 결합했다.
기존 trace와 fresh trace 각각의 libc **22/22**, 전체 module **446/446**에서 다음을 확인했다.

- runtime PC − load base = ELF vaddr, executable runtime mapping과 실제 ELF segment의 load bias.
- ELF vaddr → file offset, 원본 image bytes, objdump instruction bytes/length/opcode.
- leapfrog 366 records, cybuiltin 58 records, libc 22 records.

seq별 old/fresh 주소·offset·bytes·전체 decode를 [결합 및 비교 JSON](closure_evidence/elf-binding-and-comparison.json)에 남겼다.
이 별도 검증 코드도 이번 구현자가 작성한 증거 검사이며 별도 감사자의 승인이라고 주장하지 않는다.

## Minor 1: SHA 기반 packaged binary resolver

[correspondence.py](correspondence.py)의 ELF decode와 ELF constant source 두 경로 모두
`module SHA-256 → frozen_binaries/manifest.json → package 내부 파일`을 사용한다.
trace의 `module_path`는 module metadata lookup/provenance로만 남겨 두며 그 파일을 다시 열지 않는다.
resolver는 package 내부로 제한된 경로와 실제 image SHA를 검사하고 검증한 bytes를 캐시한다.
미등록 SHA, 누락 파일, 잘못된 hash, package 밖 경로는 FAIL이며 live file fallback은 없다.
원 수집기 네 파일과 raw schema, 수치 의미론은 변경하지 않았다.

기존 11 failures를 실제로 재현했다. 원 `d408a07` 감사 ZIP을 별도 임시 디렉터리에 풀고,
[portable_pytest.py](portable_pytest.py)로 캡처 당시 module 경로의 Path.open 접근을 차단했다.
원본 suite는 **41 passed / 11 failed**, 모두 금지된 절대경로를 여는 FileNotFoundError였다.
같은 차단 조건의 수정본 전체 Runtime Trace suite는 **66 passed / 0 failed / 0 skipped**이며
금지 경로 읽기 시도는 **0회**다. 이것은 접근 차단 조건의 재현이지 다른 OS에서 GDB를 재실행했다는 뜻은 아니다.

## Fresh acquisition 및 old/fresh 비교

현재 WSL의 **Python 3.12.3 / GDB 15.1 / frozen gala 1.12.0 wheel**로
새 [closure-fresh-01](artifacts/closure-fresh-01/) 폴더에 regular 1-step을 실제 수집했다.
wheel SHA는 `cc5f0cf3bc63a966a3c130b93f6c05026271fe7178492a02c6266c243b5fc2f0`다.
패키지를 설치하거나 wheel/커널을 재빌드하지 않았다. acquisition source hashes는 attempt-05와 동일하다.

| 항목 | 실제 결과 |
|---|---|
| acquisition | CAPTURED, GDB exit 0, 정상 inferior 종료 |
| records / scalar FP | 446 / 36; init 14 FP, step 22 FP |
| current correspondence | PASS, fixture bit-for-bit 일치 |
| ELF-relative instruction stream / offsets / decode | old/fresh 일치 |
| scalar dynamic order / raw operand / result / pre-post destination XMM / MXCSR | old/fresh 일치 |
| endpoint q / full_v / latent / gradient | old/fresh 일치 |
| runtime PC | 비교 판정에서 제외; 이번 실제 PC 차이는 0개 |
| trace raw SHA, old | `fec0379874f2a3ae792f041d553dd34533f90b02ad9bcf9d43cb022ef03e149c` |
| trace raw SHA, fresh | `e0bd088e844561ef6752b6498d734e32d94d20ae0abbfc7853b0fd85504cad86` |

scalar operand 비교에서는 memory의 절대 주소를 제외하고 kind/width/access/raw bits와 constant origin을 비교했다.
instruction 비교는 seq/phase/step/module SHA/ELF 주소/file offset/bytes/opcode/kind 및 ELF decode를 사용했다.
힙/스택 pointer와 PID, wall time, raw trace hash 전체가 같다고 주장하지 않는다.
runtime PC와 load base를 옮겨도 비교가 통과하는 회귀 시험, instruction/offset/operand/result/endpoint 변조를
거절하는 회귀 시험도 포함했다. 독립된 executable binding 검사는 별도로 실제 PC 관계를 확인한다.

fresh endpoint는 `x=0x3f70000000000000`, `y=0x3f60000000000000`,
`vx=0x3fcffeff00000000`, `vy=0x3fbffefe80000000`이며 frozen fixture step 1과 일치한다.
GDB process wall time은 **4.692903686 s**, baseline은 **2.606486561 s**였다.
이는 한 쌍의 실측이며 확대 실행 비용의 추정이 아니다.

## 감사자 코드 재실행의 정확한 성격

수령 원 checker는 보존했다. 별도 [adapter](closure_evidence/auditor_checker_with_packaged_libc.py)에
libc SHA → 보존 image를 연결하는 **한 줄만 추가**했고 [전체 diff](closure_evidence/auditor_checker_libc_only.diff)를 남겼다.
그 코드의 exact-rational → 직접 binary64 RN-even 알고리즘과 판정 로직은 수정하지 않았다.
old/fresh 각각의 재실행은 모든 8개 check PASS, original module binding 446, missing 0,
exact scalar 연산 36개 일치였다. 이 결과는 **구현자의 감사자 코드 재실행**이며 같은 감사자가
새 A1/A2/A3/A15 및 Major/Minor를 승인한 결과가 아니다.

## 테스트 및 실패 기록

| 실제 실행 | 결과 | 로그 |
|---|---|---|
| 수정 전 WSL runtime_trace/tests | 52 passed | baseline-pytest.log |
| 원 ZIP, 절대경로 접근 차단 | 41 passed / 11 failed | original-portable-pytest-red.log |
| resolver 회귀 시험, 수정 전 | 5 failed | resolver-red-corrected.log |
| resolver 수정 후 기존 및 새 시험 | 57 passed | resolver-green.log |
| 새 비교 회귀 시험, 구현 전 | 9 failed | comparison-red.log |
| 수정본 전체 runtime_trace/tests, 절대경로 접근 차단 | 66 passed | portable-pytest.log |
| 최종 tests + runtime_trace/tests 전체 | 316 passed / 0 failed / 0 skipped | final-full-pytest.log |

모든 로그는 [closure_evidence](closure_evidence/)에 있다.
첫 resolver red run에는 세 시험의 보조 package fixture가 부족해서 FileNotFoundError가 먼저 났다.
시험 package에 원 frozen fixture/mapping을 포함한 뒤 올바른 실패를 확인했다. 첫 실패 로그도 보존했다.
중간 전체 시험의 307 pass는 비교 회귀 시험 9개가 추가되기 전 결과이며 최종 316과 구별한다.
전체 staged diff의 whitespace 검사는 보존한 pytest 실패 로그와 원 감사 로그/patch의 trailing whitespace를 지적했다.
원 evidence는 정리하지 않았으며 코드·시험·문서만 대상으로 한 diff check는 통과했다.

## Git provenance 및 재감사

closure commit을 로컬 `main`에 만들고 전체 ancestry를 가진 Git bundle을 배포 package에 넣는다.
배포 provenance에 exact HEAD, parent, 저장소 상태, 로컬 remote-tracking 상태, commit ancestry 검사 및
Git bundle clone/fsck/byte roundtrip 결과를 기록한다. **이번 작업에서 push와 fetch를 수행하지 않는다.**
기존 Gate 2C/2C.1/V2 봉인 파일은 수정하지 않았다. 새 evidence는 Git newline 변환도 하지 않는다.

같은 감사자에게 **A1/A2/A3/A15 + Major 1/Minor 1 closure** 재감사를 요청할 자료가 준비됐다.
감사자가 다음을 직접 확인한 뒤 판정을 갱신해야 한다.

1. 패키지 libc SHA 및 original attempt-05 22 records의 bytes/decode binding.
2. resolver의 absolute-path 비의존성과 missing/corrupt/unknown SHA fail-closed.
3. fresh capture, ELF-relative stream/scalar raw bits/endpoint 비교 및 실제 테스트 로그.
4. bundle의 HEAD 및 `d408a07` ancestry, old artifact 보존과 package manifest.

재감사 PASS 이후 Numeric IR로 넘어갈 수 있다. 이번 자료는 regular 1-step 한 frozen 실행에 한정하며
연속 물리 정확성, 긴 궤적, gala 전체, 다른 OS/CPU/wheel 또는 범용 tracer의 인증이 아니다.

## 재현 명령 (WSL)

```bash
cd /mnt/d/numerical-audit-lab-recovered-2026-10-01
PY=/home/otherside123/venvs/gate2c1-trace/bin/python
$PY -m pytest runtime_trace/tests -q
$PY runtime_trace/portable_pytest.py
$PY runtime_trace/closure_check.py --out /tmp/runtime-closure-check-new.json
$PY runtime_trace/closure_evidence/auditor_checker_with_packaged_libc.py "$PWD" --attempt attempt-05 --out /tmp/runtime-auditor-code-old-new.json
$PY runtime_trace/closure_evidence/auditor_checker_with_packaged_libc.py "$PWD" --attempt closure-fresh-01 --out /tmp/runtime-auditor-code-fresh-new.json
$PY -m pytest tests runtime_trace/tests -q
```

fresh capture를 다시 실행할 때는 존재하지 않는 새 폴더를 지정한다. 기존 old/fresh evidence를 덮어쓰지 않는다.
배포 ZIP은 source snapshot을 `snapshot/` 아래에 두므로 다른 위치에서는 그 디렉터리가 ROOT다.
