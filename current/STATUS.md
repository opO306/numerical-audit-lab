# 현재 상태 및 Gate 2C.1 closure/addendum — 2026-10-02

**Gate 2C = historical PROVISIONAL / CONDITIONAL**

**Gate 2C.1 = CLOSED / PASS**

이 문서는 설계자가 이번 요청에 전달한 감사자의 최신 정정 판정을 반영한 현재 상태의 우선 기록이다.
기존 [CURRENT_STATUS_GATE2C1](../CURRENT_STATUS_GATE2C1.md)의 FINAL AUDIT PENDING과
기존 상태 문서의 PENDING 표시는 당시 기록으로 보존한다. Gate 2C의 판정은 소급 변경하지 않는다.
V2는 AUDITED / PASS / FROZEN 그대로이며 Gate 2C 계열 연구는 여기서 종료한다.

## 정정 판정과 과거 기록

- A1–A11은 모두 PASS였다.
- 기존 CONDITIONAL은 ZIP 외부 delivery sidecar 형식 문제 하나 때문이었다.
- 감사자는 이후 ZIP 자체 SHA-256을 이미 직접 검증하여 일치했음을 확인했고,
  해당 sidecar 요구를 실질 검증과 구분하지 못한 과도한 형식 요구였다고 정정했다.
- 수치, machine correspondence, provenance, 100k propagation, exact verification에는 미해결 사항이 없다.
- 최종 Gate 2C.1 independent audit 판정은 PASS이다.

```yaml
A1–A11: PASS
Critical: 0
Major: 0
Minor: 0
Gate 2C.1 independent audit: PASS
```

정정 판정의 출처는 설계자가 2026-10-02 이번 요청에 전달한 감사자 정정 내용이다.
작업자의 새 수치 감사나 원 CONDITIONAL 보고서의 개작으로 취급하지 않는다.
원 보고서 `GATE2C1_INDEPENDENT_AUDIT_2026-10-02.md`와 UNRESOLVED 1 / CONDITIONAL,
감사자 checker·결과·로그·manifest는 수령한 [independent audit evidence ZIP](gate2c1-independent-audit-evidence-2026-10-02.zip)
안에 원래 바이트 그대로 보존한다. 이 addendum을 후속 정정 기록으로 함께 읽는다.
감사자 로그의 전체 시험은 **250 passed in 21.51s**이며 이번 문서 정리에서 다시 실행한 시험이 아니다.

## 감사 대상과 보존

감사 대상 HEAD: `bb436647ee76a0bd73dfd108f4db8d295a17d61f`.
Git 작업 경로: `D:/numerical-audit-lab-recovered-2026-10-01`.
작업 시작 시 main, working tree clean, origin/main보다 로컬 11 commits 앞이었다.
원 작업 폴더 `D:/numerical-audit-lab`에는 .git이 없으며 새 저장소를 만들지 않았다.

- 기존 complete audit ZIP: `D:/numerical-audit-lab-gate2c1-audit-delivery-2026-10-02/gate2c1-complete-audit-2026-10-02.zip`
  — SHA-256 `b3adbc940d7c819a87f2366bb36c10a0e67597976bb9b85f3c50503ef85c261d`.
- 수령한 independent audit evidence ZIP
  — SHA-256 `527ebcc2f8fcd64615a4c20438487d7e5cd5aa1f954627cab91d15e7e0d577c9`.

두 ZIP은 서로 다른 자료이며 각각 실제 파일에서 SHA-256을 확인했다.
기존 Gate 2C 자료, Gate 2C.1 plan/method/result/charter, 모든 기존 manifests/seals,
wheel/.so, disassembly, segment evidence, Git bundle과 delivery 기록을 보존한다.
README와 기존 상태 문서도 봉인 목록에 포함되어 있으므로 수정하지 않고 이 우선 기록을 추가한다.
기존 evidence 재생성, ZIP 재패키징, 수치·구현 변경과 push는 수행하지 않는다.

감사 PASS의 범위는 기존 charter/result의 특정 frozen 실행과 동일 exact discrete map 사이 rounding layer이다.
연속 물리 궤적, method error, gala 전체나 다른 입력·플랫폼·분기에 관한 인증으로 확대하지 않는다.

다음 연구의 [Runtime Trace 첫 실험 계획](RUNTIME_TRACE_INITIAL_PLAN.md)은 작성 당시의 DESIGN ONLY 기록으로 보존한다.
**Runtime Trace regular 1-step = CLOSED / PASS.**
최종 [closure 독립 재감사 보고서](RUNTIME_TRACE_CLOSURE_REAUDIT_REPORT.md)와
[원 evidence ZIP](runtime_trace_closure_reaudit_evidence.zip)을 원 bytes로 보존했다.
대상 commit은 `736b55198947bd3c8cecc024a12af156459cfa02`, parent는
`d408a07774bee44728d41d9a598b6d8142808075`다. A1/A2/A3/A15 PASS,
Critical 0 / Major 0 / Minor 0 / closure 범위 UNRESOLVED 0이며 기존 Major/Minor는 CLOSED다.
libc 22/22 및 전체 executable 446/446 binding, 절대경로 의존 제거, fresh artifact와 old/fresh 비교,
관련 combined tests 316/316을 재감사자가 확인했다. 재감사 환경에서는 세 번째 live GDB acquisition을 실행하지 못했고,
fresh acquisition은 보고서 R6의 artifact-review fallback에 따른 PASS다.

PASS는 **frozen gala 1.12.0 / regular orbit / 1-step / machine execution ↔ runtime trace correspondence**에 한정한다.
Numeric IR, V2 automatic connection, 10/100-step, 긴 궤적, 범용 x86 tracer 및 물리 정확성의 PASS가 아니다.
기존 attempt-05, closure evidence, frozen binaries와 과거 감사 결과를 보존한다.
첫 Numeric IR 입력은 `runtime_trace/artifacts/attempt-05/trace.jsonl`이며 fresh는 별도 교차검증 입력이다.
당시 승인 범위는 **Runtime Trace → Numeric IR regular 1-step prototype**까지였다.
현재 구현·실행 명령·trace schema는 [Runtime Trace README](../runtime_trace/README.md)에 있다. Push하지 않는다.

## Runtime Trace → Numeric IR regular 1-step prototype

**Runtime Trace → Numeric IR regular 1-step = CLOSED / PASS.**
2026-10-02 수령한 [외부 독립 감사 보고서](NUMERIC_IR_REGULAR_1STEP_INDEPENDENT_AUDIT_2026-10-02.md)와
[원 evidence ZIP](numeric-ir-regular-1step-independent-audit-evidence-2026-10-02.zip)을 원 bytes로 보존한다.
감사 대상 HEAD는 `d679c8ba32d98e6076708b2b70b93c4eb37f5a49`이며 A1–A12 PASS,
Critical 0 / Major 0 / Minor 0 / UNRESOLVED 0, Final PASS다.
PASS 범위는 **frozen gala 1.12.0 / regular orbit / init + 1-step / audited Runtime Trace ↔ Numeric IR**다.
보고서 SHA-256은 `bee5681667f8ece088cc3c66dba9b02468f7fb871d26ff6f29667f9d03916189`,
evidence ZIP SHA-256은 `acb9b5294096338b090612616acd4c09562f6420d9a30cd8fdf6ea18e0f10224`다.

첫 입력은 audited attempt-05로 고정했다. 기존 closure-fresh-01은 별도 변환·검사했다.
두 source 모두 scalar arithmetic 36개 ↔ IR arithmetic 36개, value node 254개,
누락/중복/extra/재배열 0이며 전체 producer/storage/byte-slice를 포함한 normalized IR이 일치한다.
재해시한 IR 공격 19종, raw kind-label 재서명 공격, 타입 혼동 회귀 18개를 검사했다.
새 artifact 생성 뒤 전체 관련 pytest는 **410 passed in 103.63s**다.
기존 증거 141개 파일의 SHA-256·size는 보존 검사 PASS다.

정확한 scope·입력 hash·결과·한계·명령은 [Numeric IR 결과](../runtime_trace/numeric_ir/README.md)에 한 곳으로 기록했다.
phase-boundary COPY는 캡처된 endpoint/start의 상태 연결이며 캡처 밖 caller의 실행 증명이 아니다.
이번 독립 감사는 machine bytes를 별도로 decode하고 전체 value/provenance를 재구성하여 현재 frozen trace를 검증했다.
production translator/checker의 shared decoder에 관한 PASS를 미래 instruction form으로 확대하지 않는다.
감사자가 별도 snapshot에서 새로 재현한 시험은 plugin autoload를 끄고 전용 94 / 전체 관련 410 PASS다.
V2 연결, 10/100-step, 일반 x86/FP 확장 및 물리 인증의 PASS가 아니다.

다음 승인 범위는 **audited Numeric IR → frozen V2 operation layer regular init + 1-step prototype**다.
frozen V2와 감사 완료된 Numeric IR 및 Runtime Trace를 수정하지 않는다. 새 adapter의 상태는 구현·checker 검증과
외부 독립 감사를 구분하여 기록한다. Push하지 않는다.

## Numeric IR → frozen V2 regular init + 1-step — 2026-10-03

**Numeric IR → frozen V2 regular init + 1-step = CLOSED / PASS.**
2026-10-03 수령한 [외부 독립 감사 보고서](NUMERIC_IR_V2_INDEPENDENT_AUDIT_2026-10-03.md)와
[원 evidence ZIP](numeric_ir_v2_independent_audit_evidence_2026-10-03.zip)을 원 bytes로 보존한다.
감사 대상 HEAD는 `34e062dee6bf0564d6aafa8ea901de317f7e2871`이며 A1–A12 PASS,
Critical 0 / Major 0 / Minor 0 / 기술적 UNRESOLVED 0, Final PASS다.
이 범위의 INDEPENDENT AUDIT PENDING은 종료했다. 이전 구현 README의 PENDING은 감사 당시 기록으로 보존한다.
수령 ZIP SHA-256은 `6fd330347662c535fd80f7b6c9cc80df0532740883e50ea7c88290a1d39419dc`,
내부 보고서 SHA-256은 `86aa095d84420f0ca5278bbdbce65d8c504d27100dc574c5e51bcef6bed425d9`다.
수령 ZIP의 SHA256SUMS에 나열된 payload 6/6을 다시 검사했다.
선행 Runtime Trace → Numeric IR의 위 CLOSED / PASS는 별도 범위로 유지한다.

독립 감사자는 전달 ZIP의 manifest 875/875, Git bundle/ancestry, 보호 대상 기존 파일 759개와
snapshot 807개 전부의 HEAD blob byte identity를 확인했다. Adapter/checker evaluator를 사용하지 않는
별도 IEEE-754 bits → exact rational 및 V2 Form 구현으로 전체 correspondence를 다시 계산했다.
두 source의 fresh regeneration은 byte-identical이며 감사자가 새로 실행한 시험은
전용 69 passed in 5.44s / 전체 479 passed in 56.07s, skip/xfail 0이다.
이 수치는 수령 감사의 재현 결과이며 이번 상태 기록 갱신에서 다시 실행한 시험으로 표현하지 않는다.

PASS 범위는 **두 byte-pinned audited Numeric IR / unchanged frozen V2 operation layer /
regular orbit / init + 1-step**이다. Caller 실행·error continuity, center 독립 재계산,
10/100-step, trajectory/global error/physical/observable accuracy로 확대하지 않는다.

첫 audited attempt-05 Numeric IR의 출력 파일을 생성·검사한 뒤 closure-fresh-01을 별도로
통과시켰다. 각 입력은 IR arithmetic 36개 ↔ 실제 frozen V2 arithmetic 36개,
ADD 12 / SUB 8 / MUL 16, value 254개 / state binding 176개 / boundary 12개다.
독립 checker는 adapter 핵심 함수를 사용하지 않고 전체 대응을 재구성했으며 두 출력 모두 PASS다.
Missing/duplicate/extra/reorder는 모두 0이고, 같은 raw bits의 다른 dynamic value ID를 유지한다.
Boundary는 captured root 9개와 handoff COPY 3개이며 `trace_sequence=null`인 COPY를 산술로 만들지 않는다.

전체 normalized correspondence는 EQUAL이며 SHA-256은
`1493fd071d6be290bb4736fdd36b8723334793c308896998b5c7cf88b9a690a6`다.
17개 semantic mutation과 completion hash까지 수리한 CLI 공격을 모두 거부했다.
최종 전용 테스트 **69 passed in 5.84s**, 요청한 전체 통합 테스트 **479 passed in 103.62s**, skip/xfail 0이다.
WSL Python 3.12.3, `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`로 실행했다.
첫 통합 collection error는 새 테스트 모듈 3개를 이름만 바꿔 해결했고 실패 로그를 보존했다.
최종 코드 검토에서 발견한 adapter JSON 자원 제한 오류는 명시적 REFUSED로 수정하고
public/별도 CLI 회귀 시험 4개를 추가했다. 수정 후 통합의 과도한 direct-test 오류 문구 실패도
시험에서 바로잡았다. 두 실패 실행, 초기 475 PASS evidence와 모든 기존 correspondence는 보존했다.
정상 출력 재생성 bytes는 두 source 모두 기존 파일과 동일하고 독립 checker PASS / normalized EQUAL이다.
수정 후 최종 검증은 새 `validation-after-parser-fix` 디렉터리에 저장했다.

Frozen V2 source/interface/계약, 기존 Trace와 Numeric IR은 변경하지 않았다.
요청된 상태·Git attributes 변경을 제외한 기존 tracked 파일 759개의 원본 SHA/size 보존 검사 PASS다.
V2에 전달한 center는 IR 원본 bits이며 실제 V2 계산은 error Form 전파다.
Boundary의 Form 전달은 선언된 IR 모델이며 캡처 밖 caller 실행·rounding·error continuity 증명이 아니다.
이 prototype은 정확히 두 감사된 IR byte identity에 한정한다.
10/100-step, chaotic/long trajectory, horizon, V2.1, 새 bound, 범용 opcode 및 물리 인증은 수행하지 않았다.

입력 hash, 실제 output/checker/비교, mutation/pytest, 재현 명령과 한계는
[V2 연결 구현 보고](../runtime_trace/numeric_ir/v2/README.md)에 기록했다.
로컬 브랜치는 `numeric-ir-v2-regular-1step`, 시작 HEAD는
`d679c8ba32d98e6076708b2b70b93c4eb37f5a49`다. Push하지 않았다.

## Caller Transition / Error-Continuity Gate — 2026-10-03

```text
IMPLEMENTED
CHECKER PASS
INDEPENDENT AUDIT PENDING
```

Frozen Gala 1.12.0의 실제 production 경로에서 **첫 `c_leapfrog_step` return →
Cython caller와 실제 helper → 두 번째 entry**를 새 프로세스 두 개에서 획득했다.
기존 regular `H.integrate_orbit` harness는 실제 호출의 `n_steps=1`만 `n_steps=2`로 바꿨다.
두 번째 body 실행 전 debugger로 종료했으며 harness 정상 완료로 표현하지 않는다.
기존 n_steps=1 캡처는 감사된 endpoint 선행 조건이고 다음 caller를 추정한 증거가 아니다.

각 trace는 명령 728개 / 실제 PRE reads 219개 / possible writes 111개 /
same-value writes 21개 / 간접 control 16개 / return 23개 / second body 0개다.
독립 checker는 packaged ELF SHA/relative address/offset/bytes/decode, memory shadow,
read/write semantics, GPR/XMM lanes, 정의된 flags, actual control targets 및
마지막 ABI 9개 origin chains를 확인했다. Production trust는 reviewed literal pins다.

q/full_v/latent 6 lanes는 같은 주소·bits와 corridor 전체 write overlap 0을 함께 요구한다.
감사된 dynamic COPY/identity/Form/shared basis의 carry는 기존 외부 endpoint/Form 감사에
조건부로 연결한다. Native Gala에는 Form 객체가 없으며 center equality만으로 exact state를 만들지 않는다.
grad_v는 실제 16-byte zeroing 뒤 새 exact-zero scratch다. t는 새 schedule load,
dt는 실제 다음 call argument의 bits/source로 검사하고 임시 레지스터/XMM은 새 boundary roots다.

최신 정상 결과는 [caller README](../runtime_trace/caller_transition/README.md)의
`checker/fix-round2` 두 CHECKER_PASS, 실제 입력과 generator는 `checker/fix-round3`다.
기존 35종 + regression 6종, 총 41종 모두 현재 checker에서 REFUSED다.
27 raw bundles / 12 transition inputs / 2 unit fixtures의 mode·stage를 구분하고
fresh replay는 367-file mutation tree 전체와 byte-identical이다.
최종 전용 **101 passed in 68.67s**, 새 전체 통합 **580 passed in 214.16s**,
failure/error/skip 0이다. 통합 실행 중 tracked Python 148개 SHA map 변화가 없었다.
WSL Python 3.12.3와 `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`로 실제 실행한 결과다.

원 trace와 기존 Numeric IR/frozen V2 및 모든 실패·superseded 증거를 보존했다.
초기 checker의 control/read/ABI/trust 및 MOVSD/origin/sequence 문제는 새 버전에서
수정하고 scoped 재검토했다. 초기 526/570 통합 결과는 최신 Gate closure 증거가 아니다.
새 Gate의 외부 감사는 아직 PENDING이다. 두 번째 산술/IR/V2, 완성된 2-step trajectory,
10/100-step, global accumulated error 및 physical/observable accuracy로 확대하지 않는다.
로컬 branch는 `caller-error-continuity-regular-1step`이며 push/fetch/merge하지 않았다.
