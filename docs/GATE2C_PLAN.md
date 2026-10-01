# Gate 2C Implementation Plan — Binary-aware certification feasibility

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax. 설계자가 계획 봉인 후 구현까지 요청했으므로 같은 세션에서 수행한다.

**Goal:** 특정 gala 1.12.0 Linux wheel의 frozen forward 실행을 T_bin과 audited V2로 분석하여 인증 길이, 교차 상한, 비용과 REFUSED 지점을 측정한다.

**Architecture:** 계산기 측 T_bin은 동결 disassembly의 2D 연산 순서를 numeric_core 직선형 프로그램으로 옮긴다. 검사기 측은 frozen V2를 수정 없이 사용하며 calculator를 import하지 않는다. runner가 실행 기록을 전달하고, 별도의 Fraction 식으로 짧은 구간을 확인한다.

**Tech Stack:** Python 3.12, 표준 라이브러리, 기존 numeric_core, audited lab/v2_bound.py. gala 설치·실행은 필요 없다.

**Spec:** 설계자의 2026-10-01 지시와 이 문서. 원래 Gate 2B/V2 문서는 읽기 전용이다.

## Global Constraints

- A 저장소는 건드리지 말고 push하지 마십시오.
- V2 및 Gate 2A/2B의 동결 바이트를 수정하지 않는다. V2.1을 만들지 않는다.
- 대상 wheel SHA-256: `cc5f0cf3bc63a966a3c130b93f6c05026271fe7178492a02c6266c243b5fc2f0`.
- 입력 fixture: `benchmarks/gate2b/fixtures/cloud-2026-10-01/`, dt=1/64, N=100000.
- 원점 출발 regular (vx,vy)=(1/4,1/8), chaotic (1/2,1/4) 두 forward 실행만 이번 측정 대상이다.
- T_bin 비트 동일성은 Gate 2B 사후 진단으로 이미 알려졌다. **새 블라인드 시험 또는 효용 성공 기준이 아니다.** 이식 정확성과 V2 적용 전제 검사로만 사용한다.
- 연속 물리, gala 전체, 다른 wheel/OS/FMA/FTZ 경로, 새로운 외부 실행은 인증하지 않는다.
- 현재 폴더에는 .git이 없다. raw SHA-256 입력 봉인 + 별도 계획 봉인으로 실행 순서를 기록한다. Git commit/서명과 같다고 주장하지 않는다.

## 1. 사전에 알려진 것과 미측정 대상

Gate 2B의 기계어 진단은 forward/mirror 100001개 상태와 reversal 끝점에 일치했다.
새 numeric_core T_bin 이식도 이를 따라야 하지만 이미 알려진 결과를 독립 발견으로 세지 않는다.
이번에 새로 측정할 것은 V2 horizon, regular/chaotic 차이, Lab Verlet cross-bound, 실제 비용, REFUSED의 첫 지점과 이유다.
V2 감사 PASS는 V2의 기존 바이트에 대한 것이다. 새 adapter에 독립 감사 PASS를 자동 승계하지 않는다.

## 2. T_bin 연산 계약 (disassembly 입력에 근거)

2D 분기(별칭 없는 q/gradient, 0 초기화)를 명시한다. 위치 이동·회전은 없다.

- `gx = ADD(ADD(0,x), MUL(ADD(x,x),y))`
- `gy = ADD(SUB(MUL(x,x),MUL(y,y)), ADD(0,y))`
- `hhalf = MUL(dt,1/2)` (1/128, 정확히 표현됨).
- 초기화: `vhx=SUB(vx,MUL(gx,hhalf))`, `vhy=SUB(vy,MUL(gy,hhalf))`.
- step: `x1=ADD(x,MUL(dt,vhx))`, `y1=ADD(y,MUL(dt,vhy))`.
- 새 위치의 g를 계산한 뒤 출력 `vox=SUB(vhx,MUL(gx,hhalf))`, `voy=SUB(vhy,MUL(gy,hhalf))`.
- 다음 내부 속도 `vhx1=SUB(vhx,MUL(dt,gx))`, `vhy1=SUB(vhy,MUL(dt,gy))`.
- 출력 상태는 `(x1,y1,vox,voy)`, 전파 상태는 `(x1,y1,vhx1,vhy1)`다.
- 허용 연산: CONST, ADD, SUB, MUL만. opcode/입력 구조 미지원은 REFUSED.

정확 산술에서는 재결합과 doubling이 같은 다항식이다. `vh` 초기화와 출력의 반 kick을 합치면
Lab velocity Verlet의 각 full-step 출력과 정확히 같다. 두 구현의 exact target이 같으므로
`|gala_i - Lab_i| <= E_bin_i + E_lab_i`가 삼각부등식으로 성립한다.
이 대수 관계는 exact Fraction 짧은 구간으로 확인하지만 유한 표본만으로 증명했다고 쓰지 않는다.

## 3. V2 전파와 판정 정의

- initial full state는 정확히 표현된 fixture의 step 0. 네 zero Form으로 init graph를 통과시킨다.
- `(x,y,vhx,vhy)` 네 Form을 rebase하고 이후 step에 넘긴다. K=4를 바꾸지 않는다.
- 매 step `(x1,y1,vox,voy)`의 상한은 해당 출력 Form의 `rad()`로 얻는다.
  다음 step을 위한 rebase는 `(x1,y1,vhx1,vhy1)`에만 수행한다.
- finite bound와 useful bound를 구별한다. `scale=max_i |output_i|`는 represented 출력의 exact Fraction이다.
- **horizon = max(E_bin) >= scale이 처음 되는 step**. 최초 거부 전 연속 prefix 길이를 함께 기록한다.
  없으면 `first_refused=null`, `certified_prefix=N`이며 N 밖을 추정하지 않는다.
- `E=inf/NaN` 또는 V2 fail-stop 예외는 REFUSED이고 이유와 step을 남긴다.
  비유한 Form을 다시 V2에 넣지 않는다. 그 이후 bound는 UNAVAILABLE로 기록한다.
- scale 거부 뒤에도 finite인 동안 상한과 raw enclosure 교차 비교를 계속 측정한다.
  이후 다시 작아진 bound를 앞 prefix에 합쳐 horizon을 늘리지 않는다.
- replay 불일치가 있으면 그 step 이후 외부 인증은 REFUSED. 불일치는 새 발견 성공으로 세지 않는다.
- Lab Verlet도 기존 binary64 stepper + V2 rebase를 읽기 전용으로 사용한다.
- cross residual과 E_bin+E_lab는 **Fraction으로 정확히 비교**한다. 부동소수점 합을 비교 상한으로 쓰지 않는다.
- cross 판정은 합 상한이 finite이고 `max_i(E_bin_i+E_lab_i)<max(scale_bin,scale_lab)`일 때만 PASS/FAIL을 낸다.
  scale 부족은 REFUSED. raw enclosure 위반 여부는 별도로 저장하여 거부가 위반을 숨기지 않게 한다.
- bound는 전역 step 0에서 전파한다. 짧은 exact window는 해당 내부 represented state에서 오차를 zero로 재설정한 **국소 검사**이며 전역 인증으로 부르지 않는다.

## 4. 측정·비공허성·비용 (결과 전 고정)

- 기록 marks = 10,100,1000,10000,50000,100000 및 첫 scale REFUSED/첫 비유한·예외 지점.
- exact windows: n0=0,50000,99992에서 내부 상태를 잡고 8 step씩 재시작; 각 output과 inherited internal bound를 Fraction 식과 대조. regular/chaotic 둘 다 수행.
- 초기 출발 full-state exact T_bin=Lab Verlet 6 step 검사, 초기 비영 위치의 4 step 검사, 초기화 bound 포함 검사를 추가한다.
- input seal과 plan seal 검증을 실행 전·후 수행한다.
- VM replay는 100000 step 모두 대조한다. 실패/예외를 위치와 함께 기록한다.
- 비공허성: in-memory fixture 1-bit 변경/step 교환과 late 변조, cross 초과 residual, nonfinite bound, scale equality, inherited init error 제거 공격을 시험한다.
- 비용은 actual wall seconds, orbit별 seconds와 peak RSS(지원되는 경우)를 기록한다. timing/machine 정보는 deterministic digest에서 제외한다.
- 전체 60분 wall budget. 초과하면 중단·완료된 prefix와 COST_BUDGET REFUSED를 저장한다. 한도 초과 후 원격 확장이나 새 궤도 추가는 하지 않는다.
- 최소 1000 step마다 진행을 출력한다. shortened --n run은 개발 검사이며 N=100000 실험을 대체하지 않는다.

## 5. Gate 판정

- **FAIL:** 봉인 입력 변경, 허용 범위 내 exact window 위반, 공통 exact target에 대한 raw cross enclosure 위반, 필요한 판정을 숨김. 결과는 실패 원인과 함께 보존한다.
- **REFUSED:** full N 측정 완료 불가(비용/실행), replay 이식 불일치/예외로 외부 인증 전제 미충족. 유효하게 측정된 prefix도 보고한다.
- **PASS:** 입력·계획 무결성, exact 국소 검사, raw cross 위반 0, N 측정과 이유 있는 REFUSED 기록이 모두 충족. PASS 자체는 긴 horizon을 뜻하지 않는다.
- 효용은 Gate 판정과 별도다: regular certified_prefix>=17790이면 LONG_REGULAR_PREFIX, 아니면 LIMITED_HORIZON. chaotic 비교와 비용은 수치 그대로 기록하며 'YES'를 강제하지 않는다.
- 독립 검토는 별도 상태로 남긴다. 구현자 자기 검토는 독립 감사 PASS가 아니다.

## Review Focus

1. 출력 vx와 내부 vh 혼동: exact 초기화/step 및 output containment 검사.
2. 초기화 오차 누락: nonzero-position exact initial bound 검사.
3. 두 상한의 float 합 하향 반올림: exact Fraction 합 및 synthetic 경계 시험.
4. 이미 REFUSED인 검사가 late 결함을 가림: replay를 끝까지 대조하고 변조 위치를 기록하는 시험.
5. inf/fail-stop/scale equality를 PASS로 분류: 직접 REFUSED 시험과 첫 prefix 고정 시험.

## 6. 구현 작업

### Task 1 — Gate 2B 종료 및 계획/입력 봉인

Files: docs/GATE2B_CLOSURE.md, audit/gate2b/closure_seal.json, docs/GATE2C_PLAN.md,
audit/gate2c/plan_seal.json, tests/test_gate2c_sealed.py; README.md 상태 갱신.
Interface: seal은 path -> raw SHA-256. 기존 파일은 변경하지 않는다.

- [ ] 두 기존 보고서의 digest를 재계산하여 동일성 기록.
- [ ] Gate 2B input/output seal 생성, 계획 SHA-256 고정; 구현 파일 생성 전 시각 기록.
- [ ] 해시 변경을 탐지하는 시험 작성·실행.

### Task 2 — 계산기 측 binary replay와 검사기 측 adapter

Files: benchmarks/gate2c/binary_replay.py, lab/gate2c_checks.py, tests/test_gate2c.py.
Interfaces: BinaryReplay.init(x,y,vx,vy), .step(x,y,vhx,vhy) -> register bit dictionary;
BinBound.init(regs), .step(regs) -> four output bounds; exact_window(state,n=8) independent Fraction verification.

- [ ] missing module RED 확인 후 계약 그대로 구현.
- [ ] full-state 및 latent-state exact identities, init propagation, frozen fixture 1000-step 이식 확인.
- [ ] REFUSED, exact cross 합, 변조 탐지 시험 통과.

### Task 3 — 측정 runner와 결과 기록

Files: run_gate2c.py, reports/gate2c-home-pc-2026-10-01/gate2c_report.json, docs/GATE2C_RESULT.md.
Interfaces: main(argv=None)->int, --n (1..100000), --out; default는 새 Gate 2C 보고서 경로.

- [ ] shortened-run 시험/실행 후 전체 suite 검증.
- [ ] N=100000 regular/chaotic 측정, 비용과 거부 이유 저장.
- [ ] 결과 문서 작성, author review와 독립 검토 상태 구별, 최종 입력 해시·전체 suite 확인.

봉인 후 이 문서의 기준을 고치지 않는다. 구현 수리는 별도 실행 기록에 남긴다.
