# ADR: Regular N-Step Template / Induction Design

**Status:** PROPOSED / DESIGN ONLY / PROOF OBLIGATIONS OPEN

**Date:** 2026-10-04

**Decider:** 사용자 / 설계자; 구현·native acquisition 시작은 별도 결정

**Evidence baseline:** `e69119e259b862a7d8462c8d61333782ee2747fd`

**N-step implementation:** NOT IMPLEMENTED

**General induction proof:** NOT PROVED / NotCertified

## 1. 한계와 목적

Regular 2-Step의 외부 INDEPENDENT AUDIT PASS는 known-03/fresh-03과 원 감사 계약에
한정한다. init return → step1 entry는 UNTRACED, 실제 native carry coefficient는 0,
box는 nonzero이며 ASLR diversity는 미입증이다. Frozen V2 수학의 재증명이 아니다.
trajectory/global error/shadowing/final observable/physical/cross-machine correctness는
이 설계가 작성돼도 승인되지 않는다.

이 문서는 3-step을 구현하지 않고, 다음 질문의 조건과 미해결 증명 의무를 정의한다.

> step k의 종료 상태를 실제 caller를 거쳐 step k+1의 입력으로 연결할 때,
> 무엇을 보존해야 같은 correspondence/proof 규칙을 재사용할 수 있는가?

설계 제안은 하나의 검증 규칙을 매 동적 occurrence에 적용하는 것이다. Static template은
실행 기록을 대체하지 않는다. 모든 새 body/caller에 실제 raw evidence가 필요하다.
두 관측만으로 일반 induction, future execution의 동일 path, finite bound 유지 또는
termination이 증명되지는 않는다.

## 2. 읽은 계약과 현재 구현의 고정점

설계의 근거는 다음 저장소 계약과 수령한 외부 감사다.

- [Regular 2-Step contract](../runtime_trace/regular_2step/CONTRACT.md)
- [Caller / Error-Continuity contract](../runtime_trace/caller_transition/CONTINUITY_CONTRACT.md)
- [Numeric IR → frozen V2 contract](../runtime_trace/numeric_ir/v2/CONTRACT.md)
- [Regular 2-Step README](../runtime_trace/regular_2step/README.md)
- [기존 2-Step 실행 spec](superpowers/specs/2026-10-03-regular-2step-design.md)
- [외부 재감사 현재 기록](../current/REGULAR_2STEP_INDEPENDENT_AUDIT_2026-10-04.md)
- [봉인된 비용 기록](../runtime_trace/regular_2step/COST_REPORT.json)

위 세 contract, Regular README/기존 실행 spec, 수령 보고서·receipt는 본문을 읽었다.
소스는 schema/producer/form_oracle와 checker의 trust/context/Form/chain 경계,
structure의 step/caller 비교 및 seam/argument/reset 검사를 중심으로 읽었다.
`lab/v2_bound.py`의 Form/step_forms/rebase 부분도 확인했다. 모든 저장소 코드, 모든 raw row,
모든 실패 로그를 새로 전수 감사한 것은 아니다. 이번 단계는 문서 검토이며 pytest,
native acquisition, 독립 수치 감사는 새로 실행하지 않았다.

현재 구현의 다음 제약을 그대로 보존한다.

| 현재 고정점 | 일반화에 필요한 별도 계약 |
|---|---|
| `schema.py:CASE_PINS`와 `checker.py:trusted_case`는 두 literal directory, acquisition/seal/structure hash에 고정 | 새 실행의 수집 신뢰 계약과 새 schema가 필요하다. 기존 pin 제거 또는 private TEST_ONLY_REPIN 공개로 확장하면 안 된다. |
| `checker.py:context`는 새 init+step1 graph/roots/bits를 기존 audited block과 정확히 비교 | Base case용 연결이다. 미래 step 전체를 과거 step1의 bits와 같다고 요구하거나 과거 결과로 대체하면 안 된다. |
| 현재 step2 carry는 기존 audited caller transition의 endpoint Form에 연결 | 미래 carry는 바로 이전 실제 step k의 terminal byte source와 Form에 연결해야 한다. 매 step마다 옛 step1 Form으로 초기화하면 오류 누적과 provenance가 사라진다. |
| `producer.py`와 `checker.py`는 `regions[2]`, `/step2`, `regular-step2-*`, `REGULAR_2STEP_CHAIN_V1`에 고정 | 신규 일반 occurrence 계약이 필요하다. 기존 schema와 산출물은 변경하지 않는다. |
| `_validate_antecedent_boundary`는 옛 second-entry component 및 t/dt bits와 같음을 검사 | k별 실제 schedule load와 carry continuity 조건을 새로 정의해야 한다. 단순 equality 삭제는 증명이 아니다. |
| `compare_step_structures`는 두 body의 instruction/control/storage sequence를 정확히 비교 | 유한 두 body 비교를 모든 상태에 대한 정리로 해석할 수 없다. Static 규칙과 dynamic instantiation을 분리한다. |
| `compare_caller_corridor`는 옛 caller의 instruction/read/write-effect sequence와 비교 | loop counter, save_all, 종료 조건, helper 경로가 바뀌는 caller의 admissibility는 미해결이다. `value_changed`도 비교 대상이므로 same-zero와 changed-zero를 임의로 합치지 않는다. |

이 표는 기존 checker의 결함 판정이 아니다. 현재 좁은 입력 계약이 미래 확장에 제공하지
않는 항목을 명시한 것이다.

## 3. 반복할 상태와 증거 단위

k는 실제 native step의 occurrence 순서이며 1부터 시작한다. Acquisition a 안에서
`B_k`는 entry부터 실제 RET까지의 body, `C_k`는 그 RET 이후부터 다음 body entry까지의
caller다. `E_k`는 body 종료, `S_{k+1}`은 다음 body 시작 상태다.

Carried set H는 q/full_v/latent의 6개 binary64 lane이다. 각 lane의 endpoint에는 center
bits, process-local pointer와 live allocation identity, 마지막 실제 8-byte write의 dynamic
value/COPY source, Form state ID, serialized coefficient/box, shared basis identity를 둔다.
기존 native에는 Form 객체가 없으며 Form은 offline correspondence의 산출물이다.

별도로 gradient reset 2개 lane, t/dt의 실제 load, register/stack/constant roots를 분류한다.
이들이 어떤 carry에서 파생됐는지 검사한 후에만 fresh root로 취급한다. Carried 상태의
reload를 일반 LOAD라는 이유로 zero Form에 초기화하면 안 된다.

환경 Γ에는 source/wheel/ELF SHA, ABI, instruction semantics, memory maps, rounding/MXCSR,
thread/stop policy, scalar finite domain과 실제 schedule provenance를 둔다. Γ는 기계 환경의
외부 감사 전제를 포함한다. Hash chain은 byte/order integrity이며 실제 실행의 진실성이나
GDB/OS 신뢰를 단독 증명하지 않는다.

## 4. 세 종류의 증명을 구분한다

1. **Static rule lemma:** pinned instruction 형식·byte-flow·V2 연산의 규칙이 명시된 전제에서
   sound하다는 정리. 반복 사용할 수 있으나 새로운 opcode/helper/domain은 포함하지 않는다.
2. **Observed chain composition:** 획득한 유한 B/C 각각이 그 전제를 만족함을 새로 검사해
   이 유한 실행의 연결을 구성한다. 미획득한 step의 correctness는 주장하지 않는다.
3. **Universal program induction:** admissible state/environment 집합 D를 먼저 정의하고,
   모든 k와 D의 모든 상태에서 body/caller precondition, invariant, termination 또는
   partial-correctness 조건이 보존됨을 증명한다. 현재 D와 보존 정리는 PENDING이다.

유한 chain을 수학적 induction 형식으로 결합할 수 있어도 그것은 3의 완료를 뜻하지 않는다.
특히 관측한 branch에서 exact discrete reference의 branch까지 동일하다고 결론내릴 수 없다.
수치 오차로 reference branch가 달라질 수 있으면, branch-equivalence lemma를 증명하거나
reference를 명시적인 관측 operation sequence로 한정해야 한다. 전자는 현재 OPEN이고,
후자는 실행 경로 조건부 주장으로 이름과 범위를 표시해야 한다.

## 5. Invariant 및 조건부 composition 규칙

검사 목표 I_k를 다음과 같이 정의한다. 이것은 새로 증명된 정리가 아니라 proof obligation의
목록이다.

| 항목 | I_k에 포함할 사실 |
|---|---|
| Identity/order | acquisition/process/thread가 맞고, body/caller occurrence와 global seq가 유일하고 연속이다. 같은 bits의 다른 value ID는 합치지 않는다. |
| Execution/binary | 모든 row가 actual raw bytes와 등록된 ELF에 연결되고 PC/next-PC/ret/call seam, PRE/POST, memory effect, MXCSR가 검증됐다. |
| Graph/storage | arithmetic coverage·operand order·def-use·COPY lane·alias/overlap·terminal last-write source가 완전하다. partial/mixed lane과 temporal-forward edge가 없다. |
| Roots/reference | carried/reset/exogenous/derived roots의 의미와 exact discrete reference가 명시돼 있고 필요한 body/caller branch 전제가 성립한다. |
| Form | 각 carried lane의 error enclosure가 동일 shared basis 아래 동시에 성립하고 coefficient/box가 유한하다. native bits와 offline Form binding이 연결된다. |
| Publication | lower checks 및 semantic joins가 모두 통과했다. hashes만 수리한 공격으로 완성 artifact가 승인되지 않는다. |

Form convention은 기존 계약대로 `δ_i = computed_i - true_i`이며,

```text
δ_i = Σ(j=0..3) c_ij ξ_j + η_i,
ξ ∈ [-1,1]^4 (모든 lane/step에서 공유), |η_i| ≤ box_i.
```

성립 주장은 lane마다 무관한 ξ를 새로 고르는 방식이 아니다. 동일 concrete reference
실행의 여섯 δ_i를 하나의 ξ와 lane별 허용 η_i로 동시에 감쌀 수 있어야 한다.
box는 기존 enclosure이며 step이 바뀌어도 0으로 리셋하지 않는다.

J_k를 실제 C_k의 continuity/reset/root 증거, A_{k+1}을 실제 B_{k+1}의 graph/arithmetic/
static-rule 전제 검사, V_{k+1}을 frozen V2의 독립 Form/state 검증으로 정의한다.
제안하는 조건부 규칙은 다음과 같다.

```text
I_k ∧ J_k ∧ A_{k+1} ∧ V_{k+1}
∧ 동일 exact-reference semantics ∧ 적용되는 static lemma 전제
⇒ I_{k+1}.
```

Universal induction에는 별도로 `∀k, I_k ⇒ J_k ∧ A_{k+1}의 전제`가 필요하다.
현재 관측 두 개는 이 전칭 명제를 제공하지 않는다. Finite domain 또는 path guard가
깨지면 중단하고 REFUSED를 기록한다. Future termination도 현재 증명되지 않았다.

Base I_1은 기존 accepted init+1-step endpoint와 현재 실행의 정확한 graph/bits 비교에
조건부로 연결할 수 있다. init return → step1 entry의 UNTRACED 경계를 같은 전제로
표시한다. 그 gap까지 완전한 native chain을 주장하려면 새 수집과 별도 감사가 필요하다.

## 6. 매 caller에서 보존할 것

H의 각 lane에서 다음 chain을 bits·pointer·storage lineage로 검사한다.

```text
E_k → caller PRE/start → caller POST/end → entry ABI → S_{k+1}
```

같은 acquisition/process/thread이고, q/full_v/latent의 보호 48 bytes에 대한 모든 possible
write overlap이 0이어야 한다. Before/after가 같은 store도 write다. 숨은 helper, stack,
string/SIMD store와 implicit call/return 효과를 제외하지 않는다. 주소는 actual PRE GPR,
RIP-relative displacement 및 FS/GS base에서 독립 재계산한다. Module memory는 전체
PT_LOAD 범위와 ELF identity로 해석하며, process 밖의 같은 주소/같은 bits는 handoff가 아니다.

같은 pointer만으로 storage lifetime 보존이 되지는 않는다. Free/reallocation 뒤 같은
주소 재사용, alias 변경, concurrent modification, 부분 overwrite는 이 template의 precondition을
깨뜨린다. 첫 후보는 allocation relocation을 지원하지 않는다. Body 안의 pointer/alias
변화도 검증 없이 허용하지 않는다.

Gradient는 E_k의 Form을 운반하지 않는다. 실제 reset write로 16 bytes 전체가 exact +zero가
됐고 그 뒤 entry까지 다시 바뀌지 않았음을 확인한다. 모든 same-zero store도 보존한다.
Reference program도 이 reset을 수행한다는 전제에서만 새 Form=(0 coefficients, 0 box)다.
Zero endpoint만 있고 write coverage가 없으면 J_k는 성립하지 않는다.

Caller가 H에 산술/serialization/quantization/reconstruction을 수행하면 pure carry 규칙을
중단한다. 별도 dynamic graph와 sound error-transfer 계약이 필요하다. 조용히 기존 Form을
복사하거나 같은 endpoint bits로 PASS 처리하면 안 된다.

## 7. t/dt와 occurrence namespace

현재 관측은 second entry의 t[2], dt load다. 미래 k에서의 source index 식은 byte-bound
caller/source 분석으로 도출해야 하며 아직 일반 식을 채택하지 않는다. 각 k에는 actual
load instruction, operand, PRE address/bytes, destination XMM, entry argument 및 source
array/object lineage를 기록한다. 값이 같아도 매 load의 occurrence/provenance를 보존한다.

최초 후보 reference는 실제 공급된 represented t/dt schedule bits를 exact 입력으로 둔다.
이는 이상적인 연속 시간 또는 exact t0+k·dt를 인증하지 않는다. Schedule가 실행 중
산술로 생성됐고 그 산술의 오차까지 주장하려면 생성 graph와 Form을 별도 연결해야 한다.
근거 없이 매 time load를 수학적 exact time의 zero-error root로 만들면 안 된다.

Namespace 제안은 `(acquisition_id, region_kind, k, global_trace_seq, local_value_id,
byte_offset)`의 유일한 tuple이다. 문자열 encoding은 새 schema 검토 전까지 PENDING이다.
`body(k)`와 `caller(k,k+1)`는 별도 구간이고, 값의 bits나 static PC로 dynamic ID를 만들지
않는다. Fresh acquisition은 별도 namespace이며 교차 process edge는 금지한다.

COPY/reload source는 이전 E_k의 실제 terminal memory value와 명시적 COPY chain을
가리킨다. 오래된 step1 ID를 k번 반복하는 것은 새 occurrence 증거가 아니다.
Global row order와 local arithmetic order를 모두 보존하며 inherited `step=1` 또는
`harness_output.n_steps=1`을 실제 occurrence count로 사용하지 않는다.

## 8. Static template에서 한 번 다룰 것과 새로 검사할 것

| 재사용 후보인 static 규칙 | 모든 occurrence에서 필요한 dynamic evidence |
|---|---|
| pinned ELF/code bytes, opcode/ABI/operand width와 effect decoder semantics | actual module/load base/bytes/PC, PRE/POST registers, 실제 branch/call/return targets |
| 허용된 role/alias topology 및 complete scalar COPY 규칙 | actual EA/read/write bits, storage lifetime/overlap, graph def-use와 terminal byte provenance |
| ADD/SUB/MUL → Numeric IR → frozen V2의 순서 보존 mapping | actual operand/output bits, exact binary64 RNE 검사, operation coverage/order, k별 Form propagation |
| pure carry 및 reset rule의 논리적 정리 | C_k 전체 writes, six-lane joins, gradient full reset, t/dt 실제 source와 entry ABI |
| namespace/parser/completion/hash 참조 규칙 | unique acquisition/occurrence IDs, dense global seq, prev/next seam, semantic completion |

Static 정리가 증명됐다고 실제 instruction/read/write row를 삭제하거나 요약 문자열로
대체할 수 없다. Decoder/effect classifier의 completeness는 신뢰 경계다. 구현자가 사용한
classifier만 다시 호출한 결과를 그 classifier의 독립 검증으로 취급하지 않는다.

허용된 normalization은 module RVA, component/lane 역할, stack 역할과 검증된 nonnumeric
heap routing byte의 일대일 alias 대응뿐이다. Instruction bytes/order, operand order,
width/access, module identity, observed alias/overlap, branch target, actual input/output bits와
Form을 보존한다. Loop counter 값이나 주소가 달라도 안전하다는 정리는 별도로 필요하다.
Current caller signature의 mismatch를 맞추기 위해 fields를 삭제하는 변경은 승인되지 않았다.

## 9. V2 carry의 algebra와 induction 조건

현재 frozen source는 `lab/v2_bound.py`, LF-normalized SHA-256
`48b91d0c45fd7f62dd09df4db28756e6f82c6bd464a040dc60ac1c924ed99780`, K=4다.
의미는 동일 exact discrete operation sequence에 대한 rounding layer다.
아래 exact identities에서 r은 `z_hat - exact_op(x_hat,y_hat)`이다.

```text
ADD: δ_z = δ_x + δ_y + r
SUB: δ_z = δ_x - δ_y + r
MUL: δ_z = x_hat·δ_y + y_hat·δ_x - δ_x·δ_y + r
```

이 identities와 coefficient/box arithmetic의 outward enclosure를 분리한다. 실제 native
binary64 output bits의 exact/RNE 검사는 Form evaluator와 독립적으로 수행해야 한다.
단순히 producer와 checker의 출력 Form이 같다는 사실은 sound enclosure의 새 증명이 아니다.

Pure carry는 같은 represented center와 reference state, 같은 coefficient 문자열·box·basis를
그대로 운반한다. 다음 body의 변화한 center에 맞춰 각 실제 operation에서 다시 전파한다.
모든 six-lane correlation, nonlinear remainder, local residual, coefficient rounding의 상한을
기존 operator 계약대로 포함한다. Nonfinite center/Form, invalid box 또는 unsupported
operation은 REFUSED이며 한계를 줄이거나 heuristic 상한으로 대체하지 않는다.

현재 native carry coefficient=0이라는 coverage에서 nonzero coefficient의 native induction을
도출하지 않는다. 별도 algebra unit test와 universal Form lemma, native storage binding의
관측 coverage는 서로 다른 증거다.

이 첫 template 제안은 QR/rebase를 추가하지 않는다. Existing `rebase`는 네 output Forms를
대상으로 하는 별도 경로이며 여섯 carried lanes에 그대로 적용할 수 없다. Rebase가 필요하면
공유 basis 변환, exact inverse 및 outward enclosure, 여섯 lane의 동시 containment와 reference
identity를 별도 증명해야 한다. Box 폭증과 REFUSED는 허용된 결과다. Tightness 개선은
soundness 목표를 낮출 이유가 아니다.

## 10. Template가 깨지는 조건

| 사건 | 제안하는 처리 |
|---|---|
| body branch/helper/opcode/operand form 또는 module hash 변경 | 현재 lemma 적용 중단, REFUSED. 새 계약과 독립 검증 없이는 path를 포괄하지 않는다. |
| save_all/loop/GIL/memset/종료 branch로 caller sequence 변경 | 실제 C_k로 새 path 의무를 평가한다. 옛 727 rows를 복사하거나 중간 구간을 생략하지 않는다. |
| q/full_v/latent write, alias 변경, allocation/free, thread 변경 | pure carry precondition 실패. 다른 transfer 계약이 없으면 REFUSED. |
| gradient 부분 reset, t/dt missing source, register reload의 carry lineage 소실 | J_k 실패, REFUSED. 같은 최종 bits로 복구하지 않는다. |
| rounding mode/FTZ/DAZ 변경, nonfinite/unsupported domain | operator precondition 실패, REFUSED. 현재 MXCSR bit pattern만으로 모든 환경을 보장하지 않는다. |
| exact reference의 branch와 관측 branch가 달라질 가능성 | branch-equivalence obligation OPEN; 무조건적 program correspondence/trajectory 주장 금지. |
| raw row 누락/duplicate/reorder/cross-process splice 또는 불완전 decode | HASH/TRUST/SEMANTIC 해당 단계에서 거부. 재해시한 semantic 변조도 거부해야 한다. |
| prefix는 유효하지만 후속 step이 실패/timeout/terminal corridor 미수집 | 마지막 확인된 prefix를 명시적으로 보존하고 requested complete chain은 REFUSED/INCOMPLETE로 기록한다. |

마지막 B_N의 return → 정상 harness 종료는 별도 completion 경계다. 내부 C_k와 같은
template로 가정하지 않는다. Final output/save_all storage·exit count·중간 상태의 terminal
binding을 확인해야 한다. Inherited stale metadata를 최종 N의 증거로 고쳐 쓰지 않는다.

## 11. 비용: 측정값과 조건부 식

현재 봉인 비용: production Python 2,972 physical lines, tests 1,033 lines,
native acquisitions 15회(실패 5 / 성공 10), 누적 actual observed pytest 2,206.37s.
이 수치는 기존 기록이며 이번 설계 단계의 실행 시간이 아니다. Successful 10회 전체가
동일 authoritative capture라는 뜻도 아니며 현재 authoritative captures는 두 개다.

두 authoritative case의 실제 rows는 각각 191 + 255 + 727 + 255 = 1,428이다.
미래 acquisition의 body rows B_k, internal corridor rows C_k, 추가 terminal rows F_N에 대해
조건부 raw-row 식은 다음과 같다.

```text
R_N = I + Σ(k=1..N) B_k + Σ(k=1..N-1) C_k + F_N.

만약 I=191, 모든 B_k=255, 모든 C_k=727, F_N=0이면:
R_N = 191 + 255N + 727(N-1) = 982N - 536.
```

후자의 모든 조건이 일반 N에서 성립한다는 증거는 없다. 현재 N=2와의 대조만 제공한다.
Case당 step2의 operations 22 / values 151 / state bindings 107 역시 관측값이며 미래 body의
고정 count나 모든 N의 runtime 예측으로 사용하지 않는다.

| 비용 항목 | 검토할 증가 구조 | 아직 모르는 것 |
|---|---|---|
| native acquisition | 모든 실제 row를 single-step 수집하므로 전체 실행량에 의존 | k별 corridor 길이, GDB/helper 비용, 실패율과 timeout; 새 실측 없음 |
| raw/derived artifact | 모든 새 raw row·occurrence를 보존하므로 적어도 실제 증거량에 비례 | serialized row bytes, 압축률, source/ELF 중복 배제 효과 |
| checker | module/static lemma 및 audited base를 한 번 검증하고 각 새 row·join·Form을 검사하는 후보 | Fraction 크기, reference/decode/cache 비용, 전체 Python 실제 시간 |
| 반복 prefix 검사 | 매 k에서 과거 전체를 재검사하면 ∑ prefix 크기로 이차 증가 가능 | 신규 compositional checker의 정확한 검증·cache trust 계약은 미구현 |
| memory | full trace/graph 보유 방식은 전체 증거량에 비례; bounded frontier streaming은 후보 | live provenance frontier·pending refs·parser/hash state의 상한은 미증명 |
| source/test code | step마다 복제 대신 하나의 규칙과 파라미터화된 occurrence를 목표로 함 | 실제 신규 LOC와 시험 수; 현재 수치에서 추정하지 않는다 |

191/255/727를 곱해 wall time, 비용, 메모리 또는 실패율을 추정하지 않는다. 2,206.37s에는
다른 종류와 반복 실행이 포함돼 per-step 비용이 아니다. Static 공유/streaming은 목표이며
선형 wall-time이나 상수 메모리의 측정·증명 결과가 아니다.

## 12. 선택지와 제안

| 선택지 | 장점 | 비용·증명 경계 |
|---|---|---|
| A. 현재 구조로 3-step 추가 복제 | 기존 narrow 구현을 이어가는 방식 | 새 코드·case-specific pins·prefix 재검사 반복; 일반 induction 정보가 자동 생기지 않음. 이번에는 채택하지 않는다. |
| B. Static 규칙 + 각 step/caller의 실제 evidence + endpoint frontier | 하나의 proof 규칙을 재사용하면서 dynamic identity 유지 | 새로운 generic trust/schema/semantic checker와 composition proof가 필요. 현재 제안, 구현 승인 아님. |
| C. Path-specific finite segment contracts | 여러 caller/helper path를 별도 lemma로 분리 가능 | 모든 실제 segment evidence와 semantic join 필요; path 수 증가와 branch guard 증명은 남음. |
| D. 기존 narrow 결과에서 중단 | 추가 실행 비용 없음, 기존 외부 PASS 유지 | N-step 미검증을 그대로 남긴다. Template 의무를 풀 수 없으면 허용되는 선택이다. |

**제안:** B의 proof obligations를 먼저 검토한다. 해결되지 않으면 C 또는 D를 비교한다.
A의 새 3-step acquisition/구현은 현재 요청 범위에 없다. Sampling, endpoint-only equality,
같은 bits의 occurrence 합치기, raw evidence 생략은 더 싼 증명 대안으로 인정하지 않는다.
독립 exact-discrete-map 검사도 machine correspondence의 대체물이 되지는 않는다.

## 13. Proof obligation ledger

| ID | 풀어야 할 의무 | 현재 상태 / 필요한 근거 |
|---|---|---|
| PO-01 | Γ, D, finite horizon/termination, exact reference와 entry state 정의 | OPEN; 미래 admissible domain 자동 선택 금지 |
| PO-02 | I_1 base 연결 및 init→step1 gap 표시 | 기존 narrow antecedent 사용 가능; gap UNTRACED 유지 |
| PO-03 | general body path의 opcode/control/storage lemma와 exhaustive semantics | OPEN; 현재 두 body의 structural equality만 있음 |
| PO-04 | 모든 C_k의 EA/effect completeness와 pure carry non-overlap | OPEN; 현재 caller12 두 case의 독립 EA 검증이 antecedent |
| PO-05 | allocation lifetime/alias/thread 환경과 six-lane state continuity | OPEN; 관측 case 밖의 invariant 보존 증명 필요 |
| PO-06 | gradient full reset와 exact-reference reset 의미 | 현재 caller12 관측, general rule/coverage OPEN |
| PO-07 | k별 t/dt load, schedule producer, exact-root 또는 propagated-error 분류 | OPEN; t[2]를 모든 k의 규칙으로 대체 금지 |
| PO-08 | unique occurrence namespace, complete graph/COPY/last-write bindings | 설계 tuple 제안; 새 parser/schema/checker 미구현 |
| PO-09 | arbitrary admissible Forms의 independent sound propagation 및 shared basis carry | 기존 frozen V2 전제; 새 induction 적용·binding proof OPEN |
| PO-10 | branch equivalence, helper/control-flow changes, unsupported behavior refusal | OPEN; future observed path와 exact reference 범위 분리 필요 |
| PO-11 | semantic composition, trust/capture identity, public acceptance of new evidence | OPEN; immutable CASE_PINS 계약을 변경하지 않음 |
| PO-12 | terminal return/output/normal exit와 complete vs prefix 판정 | OPEN; future N에 대한 신규 completion 계약 필요 |
| PO-13 | static/module/base 검증 재사용 및 cache의 semantic trust soundness | OPEN; digest cache만으로 감사 상태 승격 금지 |
| PO-14 | cost/memory bounds 및 승인 후 작은 falsification survey의 질문 | OPEN; 새 acquisition·survey·benchmarks 실행 없음 |
| PO-15 | 새로운 checker와 template의 외부 독립 감사 | PENDING; 2-step PASS가 미래 checker 승인으로 이전되지 않음 |

새 fault-injection 설계에는 cross-k terminal/COPY swap, equal-bit ID merge, old step1 Form 재사용,
shared basis 변경, box reset, omitted same-value write, repaired caller EA, gradient partial reset,
t/dt source swap, duplicate/overlapping segment, branch/helper 누락과 premature completion을 넣어야
한다. HASH/TRUST controls는 repaired semantic refusal과 구분한다. 이것은 향후 검토할 시험
목록이며 이번 단계에서 생성·실행한 테스트 결과가 아니다.

## 14. 3-step 실측의 정보 가치와 다음 결정

새 3-step은 다음 중 구체적인 질문을 해결할 때만 향후 선택지가 된다.
예를 들어 C_2의 loop/termination/save_all path가 C_1과 다르는지, endpoint frontier로 새
step3 input을 provenance/Form reset 없이 연결하는지, 실제 acquisition/checker/artifact 비용을
독립 계측할 수 있는지다. 이는 일반 induction의 충분조건이 아니며 nonzero coefficient를
관측한다는 보장도 없다.

정적 byte/contract 분석으로 먼저 확인할 수 있는 의무를 해결한 뒤, unresolved 질문과
관측 계획·중단 기준·예산을 명시하여 사용자에게 별도 실행 결정을 받는다. 현재 N, 새
harness, executor/cutoff/time budget 또는 원격 실행 자원을 자동 선택하지 않는다.

현재 완료되는 것은 외부 재감사 상태 반영, 이 설계와 proof-obligation 목록, 기존 바이트의
보존 확인, 요청된 문서 커밋·푸시다. 이후 구현은 별도 승인 범위다. 이 문서는 feasibility
성공, induction proof, production approval 또는 formal certification의 완료 기록이 아니다.
