# Runtime Trace 첫 실험 — 짧은 설계·실험 계획

2026-10-02. **DESIGN ONLY / NOT IMPLEMENTED / NOT RUN**.
Gate 2C 계열의 종료 판정은 [현재 상태 및 closure/addendum](STATUS.md)을 따른다.
이번에는 계획만 작성한다. 범용 tracer, V2.1, Gate 2D는 시작하지 않는다.

## 대상과 첫 계측 방식

대상은 현재 frozen `gala-1.12.0-cp312-cp312-manylinux_2_24_x86_64.manylinux_2_28_x86_64.whl` 하나다.
wheel SHA-256은 `cc5f0cf3bc63a966a3c130b93f6c05026271fe7178492a02c6266c243b5fc2f0`.
기존 [machine mapping](../audit/gate2c1/machine_mapping.json)의 N=1, ndim=2,
zero origin / identity rotation, dt=1/64, 기존 regular/chaotic initial state만 사용한다.
원본 wheel/.so를 재빌드하거나 패치한 계산 커널로 대체하지 않는다.

첫 후보는 Linux x86-64에서 GDB의 instruction single-step으로 원본 실행의 전후 상태를 읽는 제한된 계측이다.
`stepi`는 한 machine instruction씩 실행하며 호출 내부도 추적할 수 있다.
공식 근거: [GDB instruction stepping](https://sourceware.org/gdb/current/onlinedocs/gdb.html/Continuing-and-Stepping.html),
[register/memory access](https://sourceware.org/gdb/current/onlinedocs/gdb.html/GDB_002fMI-Data-Manipulation.html).
실제 Linux 환경, GDB 버전, raw XMM/MXCSR 접근과 비용은 아직 확인하지 않았다.
따라서 backend 채택은 PENDING이며 이 문서는 환경 적합성이나 실행 성공을 주장하지 않는다.

계측 구간은 init + 각 leapfrog step + c_gradient/callback + 필요한 초기화·데이터 이동이다.
Python 준비 코드는 경계 밖으로 두고 경계 입력 bits를 기록한다. 구간 안의 외부 호출은
입출력 의존성을 추적하며, 경계 밖의 불명확한 값 생성이나 무기록 쓰기가 있으면 REFUSED한다.
기존 정적 대응표는 나중의 비교 대상으로만 사용한다. 실행되지 않은 명령을 trace에 채워 넣지 않는다.

## operation 계약과 기록

초기 수치 지원은 **scalar binary64 ADD / SUB / MUL / CONST**와 필요한 load/store/move뿐이다.
FMA, packed SIMD 산술, DIV, SQRT, libm, GPU, multithread 및 미지원 연산은 REFUSED한다.
기존 scalar 경로에도 있는 `movapd` 같은 register copy는 실제 lane/bit 전달 의미를 확인한 이동으로만 취급한다.
zero 초기화와 CONST는 출처를 기록하며 산술 instruction으로 세지 않는다.
정확한 instruction form의 허용 목록과 zero/memset 전달 계약은 구현 전 별도로 확인한다.

각 동적 record는 다음을 갖는다.

- 순번, orbit/phase/step/thread, module SHA-256, load base, runtime PC와 ELF 주소, 원 instruction bytes.
- opcode와 operand 역할, 실행 전 source/destination bits, memory 주소·폭·읽기/쓰기 bits, 실행 후 result bits.
- 실행 전후 MXCSR, branch/call 흐름, 입력 값의 생성 record와 load/store/move를 통한 연결.
- 대응하는 Numeric IR ID와 V2 ID. 값은 decimal 표시가 아닌 원래 64-bit 패턴을 기준으로 한다.

ASLR 주소를 ELF load mapping으로 복원한다. pre/post 중 하나라도 누락되거나 decode/operand/alias가
불명확하면 번역하지 않는다. ROUND-TO-NEAREST ties-to-even과 FTZ/DAZ 비활성 조건을 확인한다.
조건 불일치·비유한 값·신호·계측 실패·다른 thread의 구간 접근은 이유와 마지막 정상 record를 보존하고 REFUSED한다.
계측기 자신의 명령이나 debugger trap을 원본 FP operation으로 기록하지 않는다.

## Numeric IR과 frozen V2 연결

`원본 binary → runtime instrumentation → 실제 실행 FP trace → Numeric IR → frozen V2`.
IR은 trace에서만 만들고, 실제 operand 순서와 중간 결과를 보존하는 SSA 값 ID를 사용한다.
ADD/SUB/MUL 동적 occurrence 하나는 IR operation 하나와 V2 operation 하나에 대응해야 한다.
순서 변경, 합치기, common-subexpression 제거, `(x*y)+(x*y)`의 재작성은 하지 않는다.
load/store/move는 값 전달 record로 남기고, CONST는 실제 load/초기화 출처에 연결한다.
이 routing 계층을 추가 FP 산술로 세거나 기록에서 지우지 않는다.
init에서 만들어진 latent state와 output full state를 구별하고 다음 step으로 그대로 연결한다.
V2는 기존 연산자를 호출하며 수정하지 않는다. IR producer를 correspondence checker의 정답으로 재사용하지 않는다.

## 1 → 10 → 100 step 실험

1. **1 step:** 원본 wheel/.so hash와 loaded module을 확인하고 init+step1의 실제 실행을 수집한다.
   별도 대조 경로에서 instruction bytes/address/occurrence/operand/result를 record, IR, V2와 하나씩 비교한다.
   기존 mapping의 init 17 / step 25는 CONST를 포함한 비교 항목 수이며 새 trace를 강제로 맞출 템플릿이 아니다.
2. **10 step:** 1-step 대응이 통과한 뒤 같은 두 입력으로 확대한다. 모든 step의 dynamic occurrence,
   register/memory def-use와 latent 연결, gap/duplicate/reorder가 없는지 검사한다.
3. **100 step:** 앞 단계 통과 뒤 전 occurrence coverage와 대응을 확인하고 wall time/trace bytes를 실측한다.
   100k로 확장하지 않는다. 각 단계의 비용 상한은 1-step 실측 후 다음 실행 전에 고정한다.

미지원 instruction, record 누락/중복/순서·operand 변조, 잘못된 module/PC, 불명확한 load,
FP 환경 불일치를 주입하여 REFUSED 또는 correspondence FAIL을 확인할 계획이다.
최종 값 일치는 보조 검사다. 성공 기준은 **machine instruction ↔ runtime record ↔ Numeric IR ↔ V2 operation의 1:1 대응**,
전체 발생 횟수 coverage, 매 중간 operand/result bits와 실제 순서의 일치다.
그 대응이 입증되지 않으면 최종 값이 같아도 성공으로 판정하지 않는다.

다음 구현은 이 계획에 대한 설계자 검토 이후 별도 작업이다. 지금은 계측 코드·harness·IR translator를 작성하거나 실행하지 않는다.
