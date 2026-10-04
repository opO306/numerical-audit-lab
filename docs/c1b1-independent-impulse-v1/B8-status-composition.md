# B8 — Status / composition boundary

- status: DESIGN CONDITIONS ADDRESSED / IMPLEMENTATION STILL NOT STARTED / REVIEW PENDING
- version: 2, 2026-10-05; B8의 PASS된 상태 의미를 유지하고 F-CLOSURE-1 guard 참조만 정정
- dependencies: [status data](../../specs/c1b1-independent-impulse-v1/status-composition.json); B1/B3/B4/B5/B6/B7; Arithmetic audit 65d8fd2
- unresolved items: 독립 closure review; future point 구현과 별도 composition 승인/검증
- what this does NOT certify: production 구현, 모든 입력의 finite-budget 성공, 물리 정확성, J verification, integration/trajectory/replay/N-Step, certification.

기존 [감사 대상 설계](../C1B1_INDEPENDENT_IMPULSE_V1_DESIGN.md)는 역사적 snapshot으로 보존한다. 이 후속 사양은 지정한 항목에 한해 옛 제안/U1–U8을 대체하며, 독립 closure 재검토의 `IMPLEMENTATION MAY START` 판정 전 소스 구현을 허용하지 않는다.

## 상태를 각 층에 유지

| layer | closed enum / 의미 |
|---|---|
| producer | NOT_STARTED, RESOLVED(3 raw private 증명), UNPROVED(finite policy 부족), REFUSED(입력/도메인/범위), ERROR(구현 이상) |
| rechecker | NOT_RUN, ACCEPTED(전체 nonlinear/zero proof 재확인), REJECTED(명확한 binding/raw 오류), NOT_PROVED(분리/자원 미증명), ERROR |
| executor_comparison | NOT_RUN, MATCH, MISMATCH, NOT_AVAILABLE(유효한 같은 occurrence 자료 부족) |
| arithmetic | NOT_RUN, COMPUTED, REFUSED; 기존 Arithmetic failure 의미 그대로 |
| publication | NOT_PUBLISHED, PUBLISHED |
| execution | STOP, ELIGIBLE_FOR_SEPARATELY_APPROVED_POINT_USE |

현재 producer=NOT_STARTED/rechecker=NOT_RUN/comparison=NOT_RUN/새 composition arithmetic=NOT_RUN/publication=NOT_PUBLISHED/execution=STOP이다. source/문서 정리만으로 ACCEPTED/MATCH/PUBLISHED를 미리 발급하지 않는다. 기존 Arithmetic 결과의 과거 COMPUTED/PASS는 유지한다.

## 단계와 복합 실패

bounded parse/schema → spec/source/identity → exact physical admission → finite policy → private nonlinear/cell resolution → bounded complete certificate → independent full recheck → (composition 요청이면) authenticated comparator → (별도 승인된 경우) private Arithmetic → atomic publication 순서다. 앞 단계가 실패하면 뒤 단계 작업을 하지 않는다. 높은 우선순위 오류를 찾기 위해 금지된 뒤 계산을 실행하지 않는다.

관측된 같은 작업 내 failure class 우선순위는 programming anomaly, schema/binding, singular/physical-domain, proved raw unrepresentable, resource cap, rounding/recheck unproved, acquisition not available, executor mismatch, Arithmetic refusal, publication limit이다. 이 priority는 phase 선행 규칙을 뒤집지 않는다. 동일 class는 fixed schema key 순서/축 x,y,z 순서로 primary reason을 고른다. 실패 시 다른 발견된 이유를 free-text array로 늘리지 않고 primary fixed reason 및 layer status만 공개한다.

| 상황 | 결론 |
|---|---|
| 한 축 proved overflow, 다른 축 UNPROVED | producer REFUSED/RAW_UNREPRESENTABLE가 primary; 전체 NOT_PUBLISHED/STOP |
| resource 중단 전에 proved overflow 관측 | 이미 증명된 overflow 유지; resource로 못 본 다른 축을 추정하지 않음 |
| coarse interval 양끝 각각 overflow, 가운데 representable cell 포함 | overflow가 증명되지 않음; refine 또는 UNPROVED/STOP |
| programming anomaly와 어떤 다른 성공/실패 | ERROR/PROGRAMMING_ANOMALY/STOP; 기존 입력 불변 |
| producer RESOLVED, wire digit/byte 초과 | producer RESOLVED를 보존하나 publication NOT_PUBLISHED/ARTIFACT_LIMIT/STOP; rechecker NOT_RUN |
| rechecker NOT_PROVED | 남은 deterministic attempt가 있으면 private retry; 최종 부족이면 전체 UNPROVED/STOP |
| rechecker REJECTED | attempt acceptance로 숨기지 않음; RECHECK_REJECTED/STOP |
| raw MATCH지만 acquisition 부족 | comparison NOT_AVAILABLE; execution STOP |
| comparator MISMATCH | 외부 J를 oracle로 바꾸지 않음; MISMATCH/STOP |

y=J_j·2^80에서 signed96 lower overflow는 **upper endpoint < -2^95-1/2**, upper overflow는 **lower endpoint >=2^95-1/2**일 때 증명된다. 비대칭 tie 처리를 정확히 유지한다. accepted common impulse의 negation도 grid에 표현돼야 하므로 j raw=-2^95는 별도 opposite-raw refusal이다. overlap sound intervals가 nonnested인 것은 가능하지만 교집합 empty 또는 서로 다른 proved raw는 anomaly STOP이다. 조용히 마지막 interval을 고르지 않는다.

V2 VALID는 Lab binding/domain/zero/whole-vector 조건까지 통과한 경우만 ACCEPTED다. INVALID/not_separated는 NOT_PROVED, INVALID/raw_mismatch 등은 REJECTED, REFUSED resource는 NOT_PROVED, unexpected exception은 ERROR/STOP이다. legacy physics_domain rejected를 새로운 physical admission bypass로 받아들이지 않는다. diagnostic width float/time은 proof evidence가 아니다.

## Publication과 composition

독립 point proof는 세 축 모두 producer RESOLVED/rechecker ACCEPTED, 모든 wire cap 충족 후 `POINT_PROOF`로 공개할 수 있다. 이때 외부 comparison/arithmetic이 NOT_RUN인 것은 정확하며 실제 세계 execution은 STOP이다. `COMPOSITION_RESULT`와 실행 eligibility에는 같은 authenticated occurrence의 MATCH 및 별도 승인된 Arithmetic COMPUTED를 추가로 요구한다. point publication을 KDK 실행 승인으로 쓰지 않는다.

future KDK는 승인 후에도 J0(start snapshot) → audited Kick → Drift → exact unrounded closed relative segment minimum >= r_min² AND stored final relative position squared >= r_min² → J1(새 snapshot) → Kick을 local temporary로 완료하고 전체 result만 atomic publication한다. 세 축 승인 전 partial J/certificate/state update/commit 금지다. 여기서 atomic publication은 application transaction이며 Git commit을 뜻하지 않는다. user 승인 없는 Git commit/push도 이번에는 하지 않는다.

Arithmetic V1은 `65d8fd29ae255529afead70289098d36b825b3b4`의 **INDEPENDENT REVIEW PASS / exact_slow DEFAULT / exact_fast EXPERIMENTAL·OPT-IN**을 유지한다. kernel/adapter/compare/contracts/manifest를 수정하지 않는다. 기존 ARITHMETIC_ONLY/J_NOT_VERIFIED, overall physical NotCertified는 그대로다. initial energy admission, D_valid, force physics validation, integration error, replay/trajectory/N-Step은 별도 미승인 gate다.
