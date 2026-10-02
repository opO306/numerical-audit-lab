# Gate 2C.1 Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task-by-task. The user has authorized implementation after sealing; no additional execution-choice approval is required. Steps use checkbox syntax. Do not delegate the independent verdict to this implementation's author.

**Goal:** 실제 frozen wheel arithmetic 순서를 보존하고, 전달 provenance와 regular 전체 독립 재계산을 검증하는 별도 Gate 2C.1을 만든다.

**Architecture:** T_bin/adapter/runner/tests는 새 경로에 만든다. 기존 auditor 코드를 입력 evidence로 보존하고, 별도 graph·host executor·판정 경로와 accepted frozen V2로 전구간을 재계산한다. 먼저 짧은 비용 프로파일을 수행하고 검증 방법을 별도 봉인한 뒤 결과를 측정한다.

**Tech Stack:** Python stdlib, Fraction, frozen numeric_core / V2, pytest, Git bundle, ZIP, SHA-256. gala는 설치하거나 실행하지 않는다.

**Spec:** `docs/GATE2C_AUDIT_DECISION_2026-10-02.md`와 2026-10-02 설계자 요구사항.

## Global Constraints

- 시작: Gate 2C = PROVISIONAL / CONDITIONAL; Gate 2C.1 = DESIGN ONLY.
- 기존 Gate 2C와 V2/fixture/모든 기존 sealed byte 및 digest를 변경하지 않는다.
- 신규 경로: `benchmarks/gate2c1/`, `lab/gate2c1_checks.py`, `run_gate2c1.py`,
  `audit/gate2c1/independent/`, `tools/gate2c1_*.py`, `tests/test_gate2c1*.py`.
- dt=1/64, 두 기존 initial state, N=100000. 기존 결과와 숫자가 같아야 한다는 조건 없음.
- Gate 2D, V2.1, Verified Driver, 자동 trace 연구, A 저장소 수정, push 금지.
- 기존 auditor 코드의 경로 이식과 graph revision은 별도 기록. 감사자 출처를 유지하며
  작업자의 이식/수정/재실행을 새 외부 감사자의 최종 승인으로 부르지 않는다.
- plan → implementation → result를 실제 Git 커밋으로 남긴다. 날짜를 소급하지 않는다.
- 새 검증 방법을 적용하면 방법/건전성 조건을 결과 전 봉인하고 별도 Git 커밋한다.
- 결과 및 checkpoint를 덮어쓰지 않는다. 비용 실패/예외/REFUSED를 기록한다.

## Machine operation contract

wheel hash `cc5f0cf3bc63a966a3c130b93f6c05026271fe7178492a02c6266c243b5fc2f0`.
cybuiltin .so `33d66d82c34c717560747ffbfca1d98f97432a0a671a0a210a0a225d8367ecaf`;
leapfrog .so `a6ac98736304bb9f6a92e473bba45da10d9b5b99f8019e2ca15eb6a7f86234fc`.

capture는 단일 orbit, ndim=2, default origin/rotation. wheel의 cybuiltin.pyx에서
HenonHeilesWrapper.gradient[0]은 array gradient를 지정한다. cpotential.pyx 98–102의
zero origin / identity R 조건은 transform을 생략한다. c_gradient의 memset와 callback,
array gradient의 N=1 branch를 근거로 아래 실행 순서를 고정한다.
실행 중 다른 branch/FTZ/FMA 조건까지 재인증했다고 주장하지 않는다.

모델의 CONST는 load/zero initialization 기록이다. arithmetic ADD/SUB/MUL은 각 실행
instruction occurrence와 1:1이며 서로 독립인 연산도 순서를 바꾸지 않는다.
MOV/branch/address 계산은 대응표에서 routing/control로 분리하여 산술 연산처럼 세지 않는다.
T_bin 순서와 V2 구조 순서는 같은 기록과 중간값에 대응해야 한다.

| instruction | T_bin operation | V2 operation |
|---|---|---|
| gradient 1cb85 mulsd x,xmm2(y) | xy=MUL(y,x) | 동일 MUL/operand/result |
| 1cb89 addsd x,xmm3(gz) | ax=ADD(gz,x) | 동일 ADD |
| 1cb8d mulsd x,xmm0(x) | xx=MUL(x,x) | 동일 MUL |
| 1cb91 addsd xmm2,xmm2 | dbl=ADD(xy,xy) | 동일 ADD |
| 1cb95 addsd xmm3,xmm2 | gx=ADD(dbl,ax) | 동일 ADD |
| 1cba3 mulsd y,xmm2(y) | yy=MUL(y,y) | 동일 MUL |
| 1cba7 addsd grad_y,xmm1(y) | ay=ADD(y,gz) | 동일 ADD |
| 1cbac subsd yy,xmm0(xx) | diff=SUB(xx,yy) | 동일 SUB |
| 1cbb0 addsd ay,xmm0(diff) | gy=ADD(diff,ay) | 동일 ADD |
| init 15941 | hhalf=MUL(dt,half), gradient 뒤 | 동일 MUL |
| init 15993/15997, x→y loop | k=MUL(g,hhalf); vh=SUB(v,k) | 동일 순서 |
| step 1580b/15818, x→y loop | d=MUL(dt,vh); xnew=ADD(d,x) | 동일 순서 |
| step 15855 | hhalf=MUL(dt,half), gradient 뒤 | 동일 MUL |
| step 1588e/15892/158a1/158ac, x→y | k=MUL(g,hhalf); out=SUB(vh,k); gd=MUL(dt,g); vhnew=SUB(vh,gd) | 동일 순서 |

MUL(y,x)는 x*y instruction의 operand 역할을 보존한다. ADD의 입력도 교환하지 않는다.
3b360의 상수 bytes가 binary64 1/2인지 ELF에서 확인한다.
다른 single-gradient symbol이나 vector/odd-N branch를 이 순서의 대체 근거로 쓰지 않는다.
대응표를 JSON으로 만들고 init/step의 address occurrence, 상수, register bits와 V2 입력을 저장한다.

## Certification and exact target

V2는 accepted AUDITED/PASS/FROZEN dependency이며 재감사하거나 변경하지 않는다.
initial full-state zero error에서 init graph를 통과하고 latent `(x,y,vhx,vhy)`를 전구간 전파한다.
output `(x1,y1,vox,voy)`의 finite bounds와 represented scale을 exact Fraction으로 비교한다.
max bound >= scale은 REFUSED. negative/NaN/nonfinite bound, 예외, 잘못된 trace도 REFUSED다.
최초 REFUSED 이전 연속 prefix만 인증하며 나중 PASS로 연장하지 않는다.

exact target 항등식: h=1/64, u_n=v_n-h*g(q_n)/2.
q_(n+1)=q_n+h*u_n,
v_(n+1)=u_n-h*g(q_(n+1))/2,
u_(n+1)=u_n-h*g(q_(n+1))。
u_(n+1)=v_(n+1)-h*g(q_(n+1))/2이므로 귀납적으로 Lab Verlet과 같은 exact target이다.
따라서 성분별 |bin-lab| <= E_bin+E_lab. 합과 residual은 Fraction으로 비교한다.
raw violation은 scale REFUSED로 숨기지 않고 FAIL이다. 표시용 float는 판정에 쓰지 않는다.
V2 output E와 rebase 뒤 latent bounds를 구별하고 nonfinite latent는 다음 step 전 fail-stop한다.

## Cheapest independent verification, staged before results

1. 원 auditor regular 소스를 변경하지 않고 128/512/1024 step만 현재 환경에서 profile한다.
   ROOT를 현재 checkout에 연결하는 이식만 수행한다. cProfile calls/cumulative/self time,
   total wall, 같은 seed에서 길이별 비용, inverse 입력 float의 Fraction bit-length 범위를 기록한다.
   survey 상한 60초. 그 이상의 원 slow path나 100k를 먼저 실행하지 않는다.
2. 과거 regular stdout/profile은 미생성이다. 현재 측정으로 과거 환경의 원인을 확정하지 않는다.
   Fraction/역행렬/VM/load/표시 비용을 실측으로 구분한다. V2 inverse는 매번 binary64 행렬에서
   만들어지며 exact 궤도의 거대한 Fraction을 물려받지 않는다. 코드 사실과 측정을 구별한다.
3. frozen V2 inverse 삭제, float inverse 대체, V2.1을 하지 않는다. 정당한 inverse 감소에는
   별도 inclusion certificate가 필요하며 미증명 상태에서는 채택하지 않는다.
4. segment 후보: 길이 1000의 순차 독립 replay. checkpoint에는 bin/Lab represented bits,
   전체 Form coefficient/box의 binary64 bits, 최초 거부/fail-stop, 앞 segment hash를 저장한다.
   independent verifier는 initial zero forms부터 매 step을 재계산한다. 저장 seed를 신뢰하지 않는다.
5. 연결 증명: verifier가 계산한 endpoint error set S_e와 다음 segment 입력 S_s의
   모든 Forms/center가 bit-identical이어야 한다. 따라서 S_e=S_s이고 엄밀 포함이 성립한다.
   state/radius만의 일치, 도중 zero reset, segment 누락/중복, hash만의 일치는 불충분하다.
   equality를 확인할 수 없으면 UNRESOLVED. 다른 집합으로 확대하는 방식은 이번에 쓰지 않는다.
6. segmentation은 arithmetic을 생략하지 않는다. 재개/증거 보존/감사를 도울 뿐,
   100k의 참 exact 궤도를 Fraction으로 brute force하는 방법이 아니다.
7. survey 뒤 `docs/GATE2C1_VERIFICATION_METHOD.md`와 method seal을 commit한다.
   cost evidence, 선택/기각 이유, 독립성, 연결 조건, coverage/failure tests와 예산을 고정한다.
   method seal 전에는 Gate 2C.1 horizon/cross 결과를 측정하지 않는다.
8. 필요하면 accepted V2의 full 100k 독립 propagation을 위 segment로 끝까지 수행한다.
   producer+independent 합계 wall budget 60분. 초과/미완료는 REFUSED/UNRESOLVED로 보존한다.

## Exact local checks and persisted evidence

두 orbit의 n0=0,50000,99992에서 각 8-step, 총 6구간. binary latent 시작을 전체 replay로 재구성한다.
각 step의 represented input/output/next latent bits, 별도 Fraction map의 exact output/internal 값,
local zero Form에서 8-step bounds와 각각의 포함 비교를 저장한다. 큰 정수는 hex 분자/분모로 기록한다.
저장된 full vx/vy를 latent vh로 대체하지 않는다. global checkpoint에서 error=0으로 재설정하지 않는다.
local violations=0을 global trajectory의 exact 증명으로 세지 않는다.

## Package provenance contract

wheel 원본 bytes, 해당 cybuiltin/leapfrog .so 원본 bytes와 hash, 8 fixture+manifest, disassembly,
T_bin, V2 operation/input traces, 6 exact-check 자료, plan/method/result/report/charter,
Git bundle과 file manifest를 실제 ZIP에 넣는다. 옛 package의 목록으로 대체하지 않는다.
build는 clean committed HEAD의 tracked bytes로 bundle을 만든다. required path 부족은 실패다.
재개봉한 ZIP에서 광고한 모든 path의 존재/raw hash와 wheel 내부 .so byte 일치를 검사한다.
ZIP을 닫아 완성한 뒤 SHA-256을 계산하고 외부 DELIVERY.md / delivery_receipt.json / .sha256을 만든다.
ZIP 자신의 hash를 내부에 쓰는 순환을 만들지 않는다. 내부 manifest는 모든 member hash를 묶는다.
자동 시험은 문서/receipt/sidecar/file의 hash 일치, 잘못된 hash, wheel/.so 누락, bundle 변조를 검사한다.
납품할 단일 filename/hash를 외부 receipt에 지정한다. 다른 workspace ZIP을 납품물로 부르지 않는다.

## Success conditions and audit

- 실제 machine 순서→T_bin→V2 각 operation 1:1, 상수/중간값/순서를 확인한다.
- package completeness와 document/file hash 일치 자동 시험 PASS.
- 6 exact local checks、output/internal violations 0。
- regular 1..100000의 모든 step을 독립 재계산하고 finite/useful V2와 cross를 확인한다.
- 새 graph의 chaotic horizon/cross를 재측정하고 모든 REFUSED reason을 보존한다.
- raw cross violation 0, false PASS 0, failure-handling 4종 regression 유지.
- 기존 숫자 일치는 성공 조건이 아니다. 변하면 그대로 보고한다.
- 자기 시험, 원 auditor 재실행, 별도 checker 이식과 새 독립 최종 감사를 구별한다.
- 새 감사 A1–A11: PASS/FAIL/UNRESOLVED; Critical/Major/Minor; 최종 규칙은 기존 Charter와 같다.
- Gate 2C.1 CLOSED/PASS는 새 독립 감사 PASS 후에만 가능하다. 다음 연구는 그때까지 시작하지 않는다.

## Review Focus

1. arithmetic 동치이나 순서 다름: opcode/operand/address 순서 mutant를 검출한다.
2. checkpoint zero reset/latent-full 혼동: 전체 Forms/represented bits/coverage 연결 검사로 거부한다.
3. negative/NaN/inf/small bound, scale equality, 예외 뒤 PASS: fail-stop/sticky prefix로 거부한다.
4. display overflow, pre/post seal failure: 큰 Fraction의 표시는 실패해도 data를 보존하고 FAIL한다.
5. advertised vendor/hash가 다른 ZIP을 가리킴: 누락/변조 member와 false receipt를 거부한다.

## Implementation tasks

### Task 1 — Receipt and seals
Create audit decision, prior_auditor input hashes, plan and plan seal.
- [ ] 원 auditor 5파일과 기존 seals의 raw bytes를 확인한다.
- [ ] 새 implementation 미존재를 seal에 기록하고 계획 단계만 commit한다.

### Task 2 — Cost survey and method
Create tools/gate2c1_profile_auditor.py, cost report, verification method and seal.
- [ ] 원 auditor short profiling만 실행하고 환경/이식/호출수/비용을 기록한다.
- [ ] 후보 비용과 포함 조건을 비교하고 결과 전에 방법을 seal/commit한다.

### Task 3 — Separate machine-order implementation
Create benchmarks/gate2c1/binary_replay.py, lab/gate2c1_checks.py, run_gate2c1.py,
machine_mapping.json, tests/test_gate2c1.py and tests/test_gate2c1_sealed.py.
- [ ] structural/mutant/failure tests가 기존 graph 또는 미구현에서 실패함을 확인한다.
- [ ] 새 graph/adapter는 초기/내부/출력 상태를 구별하고 모든 operation occurrence를 내보낸다.
- [ ] short-run, 6 local 저장 계약, failure 4건, late mismatch, 기존 seals를 확인하고 commit한다.

### Task 4 — Independent propagation and connection evidence
Create audit/gate2c1/independent/checker.py from preserved auditor logic with explicit revision record.
Interfaces: verify(root,n,out,budget) returns report with per-segment input/endpoint and every-step decisions.
- [ ] producer imports 없이 별도 graph/float runner/scale/cross/exact map과 frozen V2만 사용한다.
- [ ] state/Form/gap/overlap/zero-reset 변조를 거부하는 시험을 수행한다.
- [ ] method seal 검증 후 producer와 독립 전구간 실행, checkpoint/6 window를 보존한다.
- [ ] 결과/cost/coverage를 문서화하고 결과 단계를 commit한다. 숫자를 맞추는 수정은 금지한다.

### Task 5 — Audit package and delivery
Create docs/GATE2C1_AUDIT_CHARTER.md, tools/gate2c1_package.py, package tests and delivery.
- [ ] charter/targets를 seal하고 author-run과 새 감사 상태를 구별한다.
- [ ] 완전한 ZIP을 build하고 재개봉하여 hash/presence를 자동 검사한다.
- [ ] 최종 ZIP hash를 외부 문서에 기록하고 다시 검사한다. Git clean, 기존 byte 보존, push 없음 확인.

이 plan은 seal 뒤 수정하지 않는다. 실행 상태는 별도 ledger, 방법 결정은 별도 sealed method,
결함 수정은 새 version/evidence에 기록한다.
