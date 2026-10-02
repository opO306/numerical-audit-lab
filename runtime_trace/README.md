# Frozen gala regular 1-step Runtime Trace prototype

2026-10-02. **이 특정 실행의 machine instruction ↔ runtime record 대응 검사 PASS**.
이는 checker 초안의 실행별 검사이며 범용 tracing 지원이나 formal execution certificate가 아니다.
현재 독립 감사 판정은 **CONDITIONAL**이다. 원 libc 보존, SHA 기반 resolver,
fresh 1-step 재수집과 기존 실행 비교를 완료한 [closure 보강 보고](CLOSURE_REPORT.md)가 있다.
Major/Minor의 구현자 측 보강 검증은 통과했으며 같은 감사자의 재감사는 **PENDING**이다.
시작 HEAD는 `2ab9c742ccf4f0f0862406e2145bde6cf1efdcc9`, 작업 branch는 `main`이다. Push하지 않는다.
Gate 2C / Gate 2C.1의 봉인 코드·문서·증거와 audit ZIP을 수정하지 않는다.

## 코드와 증거

- `run.py`: 고정 Linux x86-64 GDB 실행, 원본 harness의 별도 1-step 비용 비교. 새 출력 폴더만 허용한다.
- `harness.py`: 원본 gala API로 regular 입력을 `n_steps=1` 실행. 계산 커널을 교체하거나 재빌드하지 않는다.
- `gdb_capture.py`: GDB Python 자동 `stepi`, 실제 pre/post raw 상태 수집과 byte 단위 출처 기록.
- `semantics.py`: 제한된 operand grammar / opcode 목록과 MXCSR / 유한성 검사. 모르는 형식은 REFUSED.
- `correspondence.py`: 수집기를 import하지 않는 사후 checker 초안. ELF bytes, 별도 objdump decode,
  PC 흐름, pre/post 연결, 실제 memory EA, byte 전달, Fraction 기반 scalar 결과, endpoint를 검사한다.
  이 검사 뒤에만 기존 `machine_mapping.json`을 읽어 산술 주소·종류·순서를 비교한다.
- `tests/`: parser/환경 검사, scalar/linkage 변형, 실제 trace 변형 검사.
- `artifacts/attempt-05/`: 최종 raw `trace.jsonl`, `capture.json`, `harness_output.json`, `execution.json`,
  `correspondence.json`, `gdb.log`, `pytest.log`, `timing.json`, 비계측 `baseline/`.
  `validation.json`은 파일 보존과 생성 코드 hash 확인 기록이다. 코드는 raw trace와 분리했다.

## 재현 명령

이미 설정된 WSL 환경과 `/home/otherside123/venvs/gate2c1-trace`를 사용했다.
설치·재빌드·backend 교체는 하지 않았다. 다음은 **WSL shell** 명령이다.
출력 경로 `reproduce-01`은 존재하지 않는 새 폴더여야 한다. 최종 저장된 실행은 `attempt-05`다.

```bash
cd /mnt/d/numerical-audit-lab-recovered-2026-10-01
PY=/home/otherside123/venvs/gate2c1-trace/bin/python
OUT=$PWD/runtime_trace/artifacts/reproduce-01
$PY -m pytest runtime_trace/tests/test_semantics.py runtime_trace/tests/test_correspondence_units.py -q
$PY runtime_trace/run.py --out "$OUT"
$PY runtime_trace/correspondence.py --out "$OUT"
$PY -m pytest runtime_trace/tests -q
```

`run.py`가 실행한 GDB 명령은 다음과 같으며 정확한 argv와 생성 코드 SHA-256은 `execution.json`에 있다.

```bash
LD_BIND_NOW=1 RT_OUTPUT="$OUT" gdb -q -nx -batch -x runtime_trace/gdb_capture.py \
  --args /home/otherside123/venvs/gate2c1-trace/bin/python runtime_trace/harness.py
```

`LD_BIND_NOW=1`은 loader의 지연 symbol resolution을 수치 구간 전에 완료한다.
그 외 환경이나 package를 변경하지 않았다. 실제-capture 변형 시험은 저장된 `attempt-05`를 검사한다.
다른 OS에서는 그 시험만 skip되므로 Linux의 전체 통과 결과와 혼동하면 안 된다.
core repository code를 수정하지 않아 요청의 조건부 전체 `pytest -n 6`은 실행하지 않았다.

## 실제 대상과 경계

입력은 `x=y=0`, `vx=1/4`, `vy=1/8`, `dt=1/64`, HenonHeilesPotential,
LeapfrogIntegrator, `cython_if_possible=True`다. 환경은 GDB 15.1 / GDB Python 및 venv Python 3.12.3,
gala 1.12.0 / numpy 2.5.3 / astropy 8.0.1 / scipy 1.18.1이다.

| 대상 | 실제 SHA-256 |
|---|---|
| frozen wheel | `cc5f0cf3bc63a966a3c130b93f6c05026271fe7178492a02c6266c243b5fc2f0` |
| 설치된 leapfrog.so | `a6ac98736304bb9f6a92e473bba45da10d9b5b99f8019e2ca15eb6a7f86234fc` |
| 설치된 cybuiltin.so | `33d66d82c34c717560747ffbfca1d98f97432a0a671a0a210a0a225d8367ecaf` |

loaded gala module 파일을 wheel 안의 실제 member bytes와 hash로 대조한다.
실제 .so 전체 경로 / libc hash / PT_LOAD segment / ASLR load base는 `capture.json`에 있다.
각 instruction의 inferior bytes가 ELF 파일 bytes와 같아야 하므로 debugger trap을 FP operation으로 세지 않는다.

구간은 함수 진입부터 실제 return까지의 `c_init_velocity`와 `c_leapfrog_step` 두 개다.
호출 내부의 `c_gradient`, cybuiltin의 `henon_heiles_gradient_single`과 실제 libc memset까지 single-step한다.
두 구간 사이 Cython caller 준비는 추적 경계 밖이다. q/full_v/latent의 끝과 시작 비트가 같아야 하며
경계의 실제 ABI pointer, register, memory bits를 기록한다. 구간 내부 수치 입력의 출처가 불명확하면 REFUSED한다.
배경 thread는 존재하며 숨기지 않는다. thread inventory와 수치 owner PID/TID를 기록하고,
구간에서는 GDB all-stop `scheduler-locking on`으로 다른 thread 실행을 멈춘다.
owner 변경이나 signal은 REFUSED한다. 두 구간 후에는 잠금을 풀어 정상 Python 종료를 허용한다.
이 실험은 동시에 실행하는 수치 multithread를 지원한다는 증거가 아니다.

## 기록 schema

`trace.jsonl`은 실행한 instruction 하나당 record 하나다. `capture.json`의 schema는
`gala-regular-1step-runtime-trace-v1`이며 seq는 0부터 시작한다.

| 필드 | 의미 |
|---|---|
| `seq`, `pid`, `ptid`, `phase`, `step` | 실행 순서, 실제 process/thread, init=0 / step=1 |
| `module_path`, `module_sha256`, `module_load_base` | 실행 module과 ASLR load bias |
| `runtime_pc`, `elf_address`, `elf_file_offset`, `mapping`, `bytes` | runtime PC - load bias = ELF vaddr; PT_LOAD로 파일 offset 복원 |
| `instruction`, `opcode`, `kind`, `symbol` | 현재 PC를 GDB가 decode한 명령과 실제 심볼 |
| `operands` | operand 종류·역할·폭·실제 EA·pre raw bits·byte별 생성 출처 |
| `pre`, `post`, `post_pc` | 전체 GPR / XMM0–15 / 참조 추가 vector register / MXCSR / EFLAGS |
| `result_bits` | FP 산술·copy·stack 전달·zero 생성의 실제 destination post bits |
| `changed_gpr_results` | 정수 routing의 실제 변경 GPR post bits; EFLAGS는 post 상태에 있다 |
| `chain` | 순서가 포함된 canonical record hash chain; 별도 raw trace SHA-256도 기록 |

hex raw_bits는 little-endian memory/register bytes를 정수로 표현한 것이다.
GDB `Value.bytes`를 읽어 XMM의 128 bits를 보존한다. decimal float 표시는 판정 입력으로 사용하지 않는다.
수치 def-use는 register/memory byte별로 기록한다. 경계 입력, integer XOR zero,
실제 zero-fill, instruction literal, 읽기 전용 ELF CONST, 이전 record 출처를 구분한다.
정수 sign-extension은 source/destination 폭을 각각 기록하고, broadcast zero-fill은 실제 source byte 하나를 기록한다.
NOP/LEA는 memory를 읽는 instruction으로 기록하지 않는다. call/ret 흐름과 실제 return stack bits를 보존한다.

## 지원과 거절

수치 산술 지원은 legacy scalar `addsd` / `subsd` / `mulsd`뿐이다.
실제 지원 이동은 `movsd`, `movapd`, `movq`, 크기가 명확한 GPR move와 stack 전달이다.
memset에 필요한 `vmovd`, `vmovdqu`는 raw bit copy이고 `vpbroadcastb`는 실제 source가 zero일 때만 zero-fill이다.
벡터 bit copy를 packed FP 산술로 번역하지 않는다. 제한된 정수 routing / branch / NOP는 제어 기록으로 남긴다.
전체 허용 목록은 `semantics.py`, 이 실행에서 등장한 opcode와 횟수는 `capture.json`에 있다.

FMA, packed FP arithmetic, DIV, SQRT, libm, 미지원 opcode/form, decode/alias 불명확,
알 수 없는 수치 memory/register source, FP 환경 불일치, 비유한 수치, signal, owner 변경은 REFUSED한다.
구간에서 wheel 밖으로 호출할 수 있는 유일한 예외는 실제 memset 심볼이다.
불확실한 instruction을 다른 backend로 우회하거나 추정해서 채우지 않는다.

## 최종 실행과 검사

| 항목 | attempt-05 결과 |
|---|---|
| instruction records | 446: init 191 / step 255 |
| scalar FP occurrences | 36: init 14 / step 22 |
| FP opcode | `mulsd` 16 / `addsd` 12 / `subsd` 8 |
| cybuiltin 실제 gradient FP | init 9 / step 9 |
| MXCSR | 모든 pre/post `0x1fa0`; RN-even, FTZ/DAZ off, 예외 mask on |
| 누락 / 중복 / 순서 위반 | captured 두 구간의 검사에서 0 / 0 / 0 |
| fixture | raw 4개 값, traced numerical endpoint, frozen fixture와 bit-for-bit 일치 |
| mapping 사후 비교 | 산술 init 14 / step 22의 ELF 주소·종류·순서 일치 |
| pytest | **52 passed in 2.78s**, skip 없음 (`pytest.log`) |
| verdict | acquisition CAPTURED / correspondence PASS |

기존 mapping의 init 17 / step 25는 CONST를 포함하는 비교 행 수다.
그 숫자에 동적 record 수를 맞추지 않았다. 추적기는 mapping/T_bin/V2를 읽거나 생성하지 않는다.
checker에서 mapping을 읽는 것은 실제 trace 생성과 ELF/흐름/결과 검사가 끝난 다음이다.

실제 기록 일부 (`seq=223`):

```text
runtime PC = 0x7fffae79780b; ELF vaddr = 0x1580b
bytes = f20f594cc500
mulsd 0x0(%rbp,%rax,8), %xmm1
memory input = 0x3fd0000000000000; width = 8; access = read
xmm1 pre    = 0x00000000000000003f90000000000000
xmm1 post   = 0x00000000000000003f70000000000000
result      = 0x3f70000000000000
MXCSR pre/post = 0x1fa0 / 0x1fa0
```

최종 `x, y, vx, vy`는 각각
`0x3f70000000000000`, `0x3f60000000000000`, `0x3fcffeff00000000`, `0x3fbffefe80000000`다.
성공의 근거는 최종 출력만이 아니라 전체 instruction PC/bytes/order와 중간 raw bits 및 byte 전달 검사다.

실제 trace 변형 15종을 거절했다: 누락, 중복, 재정렬, operand, result, EA, instruction bytes,
module hash, MXCSR, thread, endpoint, harness output, boundary pointer, 정수 operand 폭,
수치 source root 제거. hash/개수/순번을 다시 맞춘 변형도 포함한다.
별도로 synthetic scalar operand/result/upper-lane/nonfinite 변형과 linkage 6종,
미지원·불명확 opcode 9종 및 MXCSR/주소 검사도 통과했다.

## 비용과 보존된 실패

최종 GDB 프로세스 wall time은 **4.462999초**, 비계측 1-step 프로세스는 **1.491800초**, 차이는 **2.971199초**다.
integrate call은 계측 **0.698085초**, 비계측 **0.000706699초**다.
import/startup과 capture I/O가 포함된 한 쌍의 측정이며 반복 평균이나 다음 규모의 예측이 아니다.
raw trace 크기는 1,667,765 bytes다. baseline도 같은 1-step 입력/출력이다.

기존 시도는 삭제하거나 덮어쓰지 않았다.

- attempt-01: `vmovd`를 미지원으로 REFUSED; 53 records / FP 0. 공식 ISA 의미를 확인한 뒤 bit copy로 지원했다.
- attempt-02: init 후 retired stack을 caller 구간에 걸쳐 추적해 alias 검사가 REFUSED; 191 records / FP 14.
  경계 밖 transient scratch를 버리고 실제 q/full_v/latent 연결을 검사하도록 수정했다.
- attempt-03: 446 records / FP 36 및 출력은 얻었으나 scheduler lock으로 Python 종료가 막혔다.
  해당 GDB 프로세스를 종료했으며 capture.json이 없는 **incomplete / REFUSED** 시도로 보존한다.
  이후 수치 구간 종료 후 scheduler 잠금을 풀도록 수정했다.
- attempt-04: 수집·당시 checker는 PASS였으나 최종 검토에서 정수 보조 operand 폭 오류를 찾았다.
  기존 trace/판정을 보존하고 **최종 사용 대상에서 제외**한다. 수정된 현재 checker는 이 기록을 거절한다.
- 실제-capture 변형 검사 초기 실행: 42 passed / 3 failed. 세 변형 모두 거절됐으나 시험이
  예상한 error 문구와 먼저 발생한 검사 문구가 달랐다. count/seq를 다시 맞추고 독립 EA를 변형해
  시험을 의도한 검사를 직접 타격하도록 고쳤다. 최종 결과는 위의 52 passed다.

attempt-01/02/03 당시 source snapshot hash는 저장되지 않았다. 이들 로그를 현재 코드와 동일한 생성물로 주장하지 않는다.
attempt-04/05는 실행 **전** 생성 코드 hash를 `execution.json`에 저장했다. 최종 checker hash도 보고서에 있다.

Numeric IR, V2 연결, chaotic 입력, 10/100 step, 범용 tracer, GPU/multithread 수치 실행은 이번에 구현·검증하지 않았다.
GDB로 멈춘 두 함수 구간 밖의 전체 Python/Cython 실행을 완전히 추적했다는 주장도 하지 않는다.
별도 독립 감사와 formal proof는 수행하지 않았다.

명세 근거: [GDB raw Value.bytes](https://sourceware.org/gdb/current/onlinedocs/gdb.html/Values-From-Inferior.html),
[GDB all-stop scheduler locking](https://sourceware.org/gdb/current/onlinedocs/gdb.html/All_002dStop-Mode.html),
[Intel SDM instruction semantics](https://cdrdv2-public.intel.com/825757/253667-sdm-vol-2b.pdf).
