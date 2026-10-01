# Gate 2C 신규 adapter 독립 감사 Charter — 2026-10-01

현재 상태: **PROVISIONAL PASS / LONG_REGULAR_PREFIX**. 독립 감사: **PENDING**.
이 Charter와 `audit/gate2c_independent/charter_seal.json`을 감사 시작 전에 봉인한다.
이 문서를 만드는 것은 독립 감사 수행 또는 PASS 승인이 아니다.

## 1. 감사 범위 및 동결 식별자

감사 대상은 Gate 2C에서 새로 만든 T_bin, V2 입력 연결, horizon/cross 판정,
failure handling, 국소 exact 검사의 연결 및 주장 범위다.
**V2 자체를 다시 감사하지 않는다.** V2는 기존 **AUDITED / PASS / FROZEN**이다.
기존 V2의 연산 규칙과 rebase 건전성은 인정된 dependency contract로 다룬다.
그 PASS가 새 adapter의 PASS로 자동 승계되지는 않는다.

아래 SHA-256은 CRLF 정규화 없이 **raw bytes** 기준이다.

| 신규 감사 대상 파일 | raw SHA-256 |
|---|---|
| `benchmarks/gate2c/binary_replay.py` | `12449c2c5e017566230ec858e46a2d1abe390e6628787f4435b89c32f14ed41c` |
| `benchmarks/gate2c/__init__.py` | `1864a6a8b6fe062e856f74a7b5f6ac47131c6e7fd8d2b9097c0dff98b177cbad` |
| `lab/gate2c_checks.py` | `493aacdb6cd8a41b7754a53015e839269aed90c94425258537e6c6bc68f735eb` |
| `run_gate2c.py` | `b1c4f024e4e4ccf7a0e433e064bb8a548e73c340fe9507cce89225c89ca2653a` |
| `tests/test_gate2c.py` | `92c5fb3237eef77496888dcc3c341c2c3847567bfcdf588f4df884767e3ef6ac` |
| `tests/test_gate2c_sealed.py` | `cfa5f8c8435678766a69e6eaeaef0eaaebf13d4bf9a36441030156e8b5d71cc7` |
| `docs/GATE2C_PLAN.md` | `2dd72f3f5664d61085db51d26c496f428d2161ec7d12f2be085474da8f4660cc` |
| `docs/GATE2C_RESULT.md` | `853d344328a341dc39bb039ee043d3ba7ff66d1c00a37792229f836b1a320c4d` |
| `reports/gate2c-home-pc-2026-10-01-verified/gate2c_report.json` | `c11023b11bbddebea8810a4aa69e5e5c18fbdf3f25944235053feaf0dd50db03` |

추가 input/fixture/dependency 및 기존 봉인 목록의 해시는 charter seal의 역할별 목록을 따른다.
그 목록에는 원래 closure/result seal 자체의 raw SHA-256도 포함한다.
감사관은 감사 시작 시 해시를 직접 다시 계산한다. 이름 또는 버전 문자열만으로 동일성을 인정하지 않는다.

특정 wheel:
`gala-1.12.0-cp312-cp312-manylinux_2_24_x86_64.manylinux_2_28_x86_64.whl`
SHA-256 `cc5f0cf3bc63a966a3c130b93f6c05026271fe7178492a02c6266c243b5fc2f0`.
frozen fixture는 `benchmarks/gate2b/fixtures/cloud-2026-10-01/`이다.
원래 Linux 실행 자체를 집 PC에서 재실행한 것으로 해석하지 않는다.

## 2. 독립성 계약

- 각 A1–A11에 **PASS / FAIL / UNRESOLVED**와 독립 근거를 남긴다.
- 기존 tests 통과, 구현자의 보고, bit equality, exporter가 만든 expected output만으로 PASS를 주지 않는다.
- 판정용 독립 checker/유도는 감사관이 별도 작성한다. 준비자는 대신 작성하지 않는다.
- 판정 경로에서 T_bin, BinBound, output_status, cross_check, exact_window,
  run_gate2c의 gate_verdict 등 감사 대상 구현을 정답 계산에 재사용하지 않는다.
- 대상 코드를 실행할 경우 그것은 SUT 관측/trace 수집으로 격리한다.
  독립 정확 계산·scale 비교·경계 결정·변조 판정은 다른 구현과 계산 경로에서 한다.
- 인정된 frozen V2를 동일 바이트의 연산자로 호출해 adapter 연결을 재현할 수는 있다.
  그러나 대상 adapter가 구성한 trace/forms/상태 배선/판정값 자체를 독립 증거로 믿지 않는다.
  별도 trace와 별도 horizon/cross 판정으로 검증하며 기존 P1–P15 재감사로 범위를 확장하지 않는다.
- numeric_core 또는 기존 exact_latent_step에서 얻은 값도 producer 관측값이다.
  감사관의 exact reference와 동일 구현이면 독립 근거가 아니다.
- 결함 주입은 사본/별도 process에서만 한다. 원 fixture와 봉인된 adapter/V2 바이트를 바꾸지 않는다.
- 원 실행의 SHA 봉인과 복구 Git 이력을 구별한다. 복구 커밋은 측정 뒤의 재구성이지
  원래 Git 사전등록의 소급 증거가 아니다.
- 감사자의 이름/방법/도구/검사 범위/실행하지 않은 범위를 명시한다.

## 3. 고정 측정과 판정 조건

dt=1/64, N=100000. regular (vx,vy)=(1/4,1/8), chaotic (1/2,1/4), 원점 출발.

| 항목 | 동결 값 |
|---|---:|
| regular V2 certified prefix | 100000 |
| chaotic V2 certified prefix | 13906 |
| chaotic first REFUSED | 13907 |
| regular Lab cross-bound PASS | 100000 |
| chaotic Lab cross-bound PASS | 13662 |
| first cross-bound REFUSED | 13663 |

동결 deterministic digest:
`a796c32a5be379c2cdfdd93757963ed92d981bf83dbd4c5e784d45c863fa3acc`.
숫자를 보고 adapter 또는 판정식을 바꾸지 않는다.

V2 출력 상한은 `(x1,y1,vox,voy)` Form의 rad이고,
다음 step 전파는 `(x1,y1,vhx1,vhy1)`를 rebase한 네 Form이다.
initial full-state 오차를 zero로 두고 init graph를 통과시킨 뒤 latent 상태로 전파한다.
유용한 finite certification은 모든 출력 bound가 finite이고
`max(E) < max_i |represented_output_i|`인 경우다. 등호는 REFUSED다.
비유한/예외/trace 불일치 이후의 구간을 인증 prefix에 넣지 않는다.
first refusal 이전의 연속 prefix만 기록한다. 중간에 다시 작아진 상한으로 prefix를 늘리지 않는다.

cross residual과 `E_bin_i+E_lab_i`는 exact Fraction으로 비교한다.
cross의 유용한 판정 조건은 유한 합 상한 및
`max_i(E_bin_i+E_lab_i) < max(scale_bin,scale_lab)`이다.
scale REFUSED가 raw enclosure violation을 숨겨서는 안 된다.

## 4. 증명 의무

| ID | 감사 질문 및 최소 요구 증거 |
|---|---|
| **A1** | T_bin이 **특정 wheel**의 확인된 machine-level evaluation order를 모델링하는가? wheel 내부 실제 .so 해시를 확인하고 gradient 2D branch 및 leapfrog init/drift/output kick/latent kick의 instruction→변수 대응을 별도로 검토한다. doubling, zero addition, multiplication order, constants, branch/aliasing/FTZ/FMA 전제를 명시한다. 기존 진단 equality만으로 명령 순서를 증명하지 않는다. |
| **A2** | 실제 실행 operation trace와 V2에 넘기는 trace가 **연산 순서·상수·중간값 기준으로 1:1**인가? init/step의 opcode, dst, operands, literal, represented result를 비교하고 latent↔output 배선, init error와 rebase 입력을 확인한다. opcode 삭제/재배열, constant 변경, 중간값 교체, output/internal 혼동을 사본에서 주입해 독립 검사 탐지를 확인한다. |
| **A3** | frozen fixture가 Gate 2B 원본인가? compressed 및 decompressed SHA-256, manifest shape, 원 bundle의 fixture commit `c5971ea` 및 result tip과 대조한다. 새 Gate 2C 결과 뒤 바뀌지 않았다는 근거를 raw seals/Git 조상 blob과 구별해 보고한다. fixture/manifest 양쪽 변조도 공격한다. |
| **A4** | V2 horizon 조건과 연속 prefix가 정확한가? 독립 scale/finite 판정과 독립 trace 배선으로 regular 1..100000의 finite/useful bounds, chaotic **13906 PASS / 13907 REFUSED**를 재계산한다. 경계 직전/경계/직후의 네 bounds, 네 represented outputs, scale, first refusal, propagation continuity를 로그로 남긴다. 요약 값만으로 PASS하지 않는다. |
| **A5** | chaotic 13907의 REFUSED 이유가 **bound가 상태 크기에 도달해 판정력을 잃음**인가? equality/inequality를 exact rational로 검사한다. overflow, exception, replay mismatch와 구별한다. infinity 전환(step 13953 T_bin, 13735 Lab; 보고된 값)과 최초 scale refusal을 혼동하지 않는다. |
| **A6** | Lab↔gala cross-bound 부등식을 독립 재유도한다. 정확 산술에서 두 full-step 출력의 target이 같음을 init 및 귀납식으로 확인하고 triangle inequality를 적용한다. Fraction 합의 upward/downward 표시와 판정 분리를 점검한다. regular 1..100000 PASS, chaotic **13662 PASS / 13663 REFUSED** 경계의 residual, 양쪽 bounds, exact sum, scale을 독립 재계산한다. 유한 합 상한 구간의 raw violations와 scale REFUSED를 별도로 확인한다. |
| **A7** | 원래 **8-step exact Fraction 검사 6개**(각 궤도 n0=0,50000,99992)가 T_bin과 동일 discrete program을 검사하는가? 실제 latent represented 시작값과 full-state seed를 구별하고, local reset 및 init 수행 여부, 모든 output/internal bounds를 확인한다. 준비자가 제공하는 producer fixture를 독립 재계산한다. global propagation 증거로 과장하지 않는다. 미보존 latent checkpoint는 감사관이 별도 구현으로 재구성하거나 UNRESOLVED로 둔다. |
| **A8** | finite/infinity/NaN/REFUSED 전환에서 작은 finite bound·거짓 PASS·잘못된 prefix가 나올 경로가 없는가? init/step의 nonfinite coefficient/box/bounds, NaN, unsupported opcode, VM halt, arithmetic exception, exact-to-float display overflow, scale equality, pre/post seal failure 및 budget stop을 공격한다. 출력/latent 비유한 전환을 구별하고 raw violation 기록, prefix≥0, refusal 이후 late mismatch 탐지를 확인한다. |
| **A9** | failure-handling 수정 4건의 실제 수정 범위·회귀시험·우회 경로를 확인한다. 아래 표의 original snapshots와 final bytes를 비교한다. 기존 회귀시험만 믿지 않고 각 failure의 다른 호출/예외/표시/초기화 경로를 독립 결함 주입으로 확인한다. |
| **A10** | T_bin bit-identical이 Gate 2B 사후 진단에서 이미 알려진 사실임을 plan/result/report가 공개했는가? 재확인을 새 blind test, 독립 발견 또는 utility 성공 기준으로 다시 세지 않았는지 점검한다. |
| **A11** | 인증 범위가 **특정 frozen gala wheel 실행↔같은 이산 계산의 exact arithmetic 사이 rounding layer**로 제한되는가? 연속 HH 궤적, 방법 오차, gala 전체, 다른 wheel/platform/dt/IC, 새로운 외부 실행으로 과장하지 않았는지 모든 status/result/package 문구를 확인한다. |

## 5. A9: failure-handling 수정 4건

| 수정 | 원 결함 | 회귀시험 |
|---|---|---|
| 1 | init fail-stop이면 certified_prefix=-1 | `test_runner_init_fail_stop_has_zero_prefix` |
| 2 | 두 큰 finite bound의 exact sum을 표시용 float로 변환하다 OverflowError | `test_finite_cross_sum_outside_float_range_is_refused_without_crash` |
| 3 | pre/post seal failure가 보고서 없이 종료, post failure에서 이미 측정한 결과 소실 | `test_runner_seal_failure_is_preserved_as_fail_report[before/after]` |
| 4 | init rebase nonfinite Forms를 다음 V2 step에 넘길 수 있음 | `test_init_nonfinite_forms_are_refused_before_next_step` |

추가 기존 시험: `test_runner_first_refused_prefix_stays_fixed_and_late_mismatch_is_detected`.
검토 전 소스 사본은 `audit/gate2c/pre_review/`의 .txt로 보존되어 있다.
이것은 원래 code-review/수정 기록이며 이번 독립 감사 판정은 아니다.

## 6. Evidence package와 남은 관측 공백

`audit/gate2c_independent/EVIDENCE_INDEX.md`와 payload manifest를 먼저 읽는다.
frozen fixtures, source, disassembly, vendor wheel, trace format,
표본 V2 입력 trace, exact fixture, 저장된 horizon/cross 로그, 회귀시험, 계획/결과/원 해시 봉인과 Git bundle을 포함한다.
vendor wheel은 static reading용으로 다운로드·해시 확인하며 설치하거나 실행하지 않는다.
기존 PyPI attestation 서명 체인 미검증은 이번에도 닫았다고 주장하지 않는다.

exporter는 기존 VM과 V2 adapter를 읽기 전용으로 호출하는 **producer**다.
감사자의 independent checker를 작성하지 않는다. exporter의 수치는 신뢰할 정답이 아니다.
preparation에서는 새로운 100000-step 실행을 하지 않는다.

원 보고서에는 summary/marks가 있고 전 step의 bounds/forms 로그가 없다.
13906과 13662의 전파 상태·bounds도 독립 checkpoint로 저장되지 않았다.
step 50000,99992의 원 국소 검사 latent 시작값도 별도 보존되지 않았다.
시작점 n0=0의 두 exact 8-step fixture와 6개 frozen full-state anchor를 제공한다.
나머지 네 구간을 원래 latent window의 exact fixture라고 대체 표시하지 않는다.
누락을 채우려면 감사관이 별도 구현으로 원 시작점에서 전파해야 한다.
그것을 수행하지 않으면 해당 의무는 UNRESOLVED다.

## 7. 판정·심각도·최종 규칙

각 A1–A11: **PASS / FAIL / UNRESOLVED**.
각 finding: ID, A 번호, severity, source hash/line, 독립 유도 또는 실행 증거,
counterexample/fault, reproducibility, 영향 범위를 기록한다.

- **Critical:** 실제 오차보다 작은 finite bound, 거짓 PASS, 잘못된 certified horizon 가능.
- **Major:** 건전성 논증에 미해결 구멍이 있으나 구체적 under-bound 반례는 아직 없음.
- **Minor:** tightness, 문서, 성능, 유지보수 문제.

최종 판정은 설계자가 지정한 규칙 그대로다.

| 최종 판정 | 조건 |
|---|---|
| **PASS** | Critical 0, Major 0, UNRESOLVED 0 |
| **CONDITIONAL** | Critical 0이지만 Major 또는 UNRESOLVED 존재 |
| **FAIL** | Critical >= 1 |

UNRESOLVED는 A1–A11의 unresolved 의무 수다. 증거를 얻지 못한 항목을
Minor로 내려서 PASS 조건을 우회하지 않는다. 모든 A 판정과 finding을 공개한다.
제공된 결과를 틀렸다고 지적하는 것이 감사 실패가 아니다. 반례·불확실성을 그대로 남긴다.

## 8. 감사 전·후 변경 관리

감사 전: adapter/T_bin/판정식/horizon 수정, 추가 100k campaign, Gate 2D,
V2.1, A 저장소 수정, push를 하지 않는다.
감사에서 결함이 나오면 현재 Gate 2C 바이트와 결과를 보존한다.
수정판은 Gate 2C.1처럼 별도 version이며 이번 PASS를 자동 승계하지 않는다.

감사 최종 PASS 후에만 설계자가 `Gate 2C = CLOSED / PASS / LONG_REGULAR_PREFIX`로 승격한다.
그다음 연구 질문은 HH 계산을 늘리는 것이 아니라 외부 바이너리에서 V2용 operation trace/replay를
얼마나 자동으로 생성할 수 있는가다. 이 Charter는 그 조사 착수 승인이 아니다.

## 9. 감사 보고서 양식

새 파일 `GATE2C_INDEPENDENT_AUDIT_REPORT.md`에 감사 대상 seal/commit과 도구 환경을 적는다.
각 A1–A11은 미검토 상태에서는 UNRESOLVED로 시작한다.
독립 유도/새 실행/기존 로그 열람을 구별하고 실행하지 않은 항목을 명시한다.
최종 Critical/Major/Minor/UNRESOLVED counts와 위 규칙의 PASS/CONDITIONAL/FAIL을 기록한다.
준비 단계에서 감사관의 verdict 칸을 대신 채우지 않는다.
