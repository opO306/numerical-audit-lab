# Independent Impulse V1 — F-CLOSURE-1/2 fix report

- status: DESIGN ONLY / NOT IMPLEMENTED; F-CLOSURE-1 FIX APPLIED; F-CLOSURE-2 FIX APPLIED; INDEPENDENT RECHECK PENDING
- version: F-CLOSURE-1-2-2026-10-05, 별도 working revision; 아직 commit하지 않음
- dependencies: audited snapshot `4cb2910fe936f7b1d5150196e062b6b61edc240f`, direct parent `023b186c0e9d95c11399893e7f75772cfff6c3a7`, Arithmetic antecedent `65d8fd29ae255529afead70289098d36b825b3b4`; 수정한 B3/B4 및 전이 dependency graph
- unresolved items: 두 fix의 independent recheck; 구현 착수 판정; runtime activation 증거는 별도 미발급
- what this does NOT certify: Impulse 구현/판정/J verification, 실제 D_valid/trajectory/admission, 물리 정확성, certification

## 역사 판정과 이번 범위

[독립 재검토 원문](../current/c1b1-closure-fixes-2026-10-05/received/REPORT_KO.md)과 [verdicts](../current/c1b1-closure-fixes-2026-10-05/received/verdicts.json)를 exact bytes로 보존했다. 실제 사용자 요청은 별도 [request copy](../current/c1b1-closure-fixes-2026-10-05/request/user-request.txt)에서 읽었으며 첨부 문서의 재현 지시를 실행하지 않았다.

```text
4cb2910fe936f7b1d5150196e062b6b61edc240f
CLOSURE REVISION REQUIRED
F-CLOSURE-1 / F-CLOSURE-2
implementation_may_start = false
```

이 역사 판정을 사후 PASS로 바꾸지 않는다. f806d8c overall FAIL/F-CLAIM-1, 65d8fd2 Arithmetic PASS, 023b186c conditional design PASS도 그대로다. 이번 수정은 아래 두 규범 정정과 관련 참조·상태·hash 갱신에 한정한다.

## F-CLOSURE-1: 기존 Arithmetic guard 의미로 복원

[B3](c1b1-independent-impulse-v1/B3-physical-domain.md), [physical-domain.json](../specs/c1b1-independent-impulse-v1/physical-domain.json), B8 markdown/JSON의 future guard 참조를 다음으로 통일했다.

```text
Point admission:
    exact current R² >= r_min²

After drift:
    minimum over the exact unrounded closed relative segment >= r_min²
    AND
    stored final relative position squared >= r_min²
```

두 번째 검사는 저장된 최종 상대 위치 한 점이다. 감사된 Arithmetic `geometry.segment_intrusion`은 exact 선분 minimum 비교, `stored_intrusion`은 stored_relative dot stored_relative 비교다. 이전 B3의 stored rounded 선분 전체 minimum 요구를 제거했다. 새 guard나 수치 알고리즘을 구현하지 않았다. r_min 값/단위, admission의 R=0/below/equal/above 의미, denominator regularity는 변경하지 않았다.

[exact witness JSON](../current/c1b1-closure-fixes-2026-10-05/received/guard_contract_witness.json)과 [제공된 witness script](../current/c1b1-closure-fixes-2026-10-05/received/guard_contract_witness.py)는 원문 그대로 보존했다. 이 자료의 분류는 **PRE-IMPLEMENTATION CONTRACT NON-EQUIVALENCE WITNESS**다.

| witness의 exact 비교 | 부호 / 계약 의미 |
|---|---|
| exact unrounded segment minimum − r_min² | >0 |
| stored endpoint R² − r_min² | >0 |
| stored rounded segment minimum − r_min² | <0 |
| 기존 Arithmetic contract | ACCEPT |
| 잘못 추가된 stronger stored-segment contract | REFUSE |

이번 정적 checker는 JSON에 기록된 세 reduced rational 값/차이와 부호를 확인했다. witness script나 Arithmetic kernel은 실행하지 않았고 segment minimum을 새로 계산하지 않았다. 기존 구현의 버그 반례로 기록하지 않으며 D_valid·실제 trajectory·impulse 실행 적합성의 증명/반증으로 확대하지 않는다.

## F-CLOSURE-2: Failure closed 목록 단일화

[B4](c1b1-independent-impulse-v1/B4-proof-wire-resource.md)와 [proof-wire.json](../specs/c1b1-independent-impulse-v1/proof-wire.json)의 정식 Failure fields는 다음과 같다.

```text
schema, status, phase, reason, resource_kind,
spec_sha256, state_sha256, occurrence_sha256, budget_sha256,
attempt_count, attempt_digest
```

기존 `closed_object_keys.Failure`는 유지했고 `resource_failure_record`의 secondary closed 목록에 `resource_kind`를 추가했다. 두 ordered 목록과 B4 markdown key 목록은 동일한 11개 필드다. resource_kind는 항상 존재하며 resource-related failure에는 정의된 enum, non-resource failure에는 null이다. 암묵적인 precedence는 없다.

Failure <=4096 bytes, canonical integer 4096 digits, input/certificate/artifact 1 MiB 등 기존 한도를 그대로 유지했다. giant integer/payload/certificate/Python exception text/자유 diagnostics를 failure에 싣지 않는다. 고정 schema의 longest enum/hash를 사용한 보수적 Failure byte accounting은 789 bytes였다. 이것은 size accounting이며 실제 runtime 실패를 실행한 결과가 아니다.

## Hash / dependency 재발급

canonical ASCII JSON, sorted keys, compact separators, terminal LF 규칙은 바꾸지 않았다. physical-domain 내용 정정 → proof-wire 내용 및 domain 참조 갱신 → finite-policy/acquisition/status/lineage/semantic bundle → package-manifest 순서로 정확 bytes의 SHA-256과 sidecar를 재발급했다. [hash-rebinding.json](../current/c1b1-closure-fixes-2026-10-05/hash-rebinding.json)에 audited before/working after hash를 분리했다.

| canonical file | 수정 종류 | 새 SHA-256 |
|---|---|---|
| physical-domain.json | F-CLOSURE-1 규범 | `eef0a3531c7bc5f233e7cd7212c3807735c05bc88284bd16600c894afc817c03` |
| proof-wire.json | F-CLOSURE-2 규범 | `b7994420f6896eb352730ac0fb5983a6c74c0635d357dffea3281535b57f27e9` |
| finite-policy.json | dependency ID / package revision | `e8ceec423827a0699a8d3709508dff3eebd7f7e8a99f92d4436dc7b57f83fdd8` |
| acquisition-identity.json | dependency ID / package revision | `673941bf9f88835f9ee494268e2837a6bd3e6b09323ad75db70d1f8df7666759` |
| status-composition.json | guard 참조 + dependency ID | `4257563b2c82a66094f96da539cdf9bbe1967699403fd61ba613d195b26483ee` |
| rechecker-lineage.json | dependency ID / package revision | `4767ae1773fa2f697e749b90aa1b66da686605cbfb690307aa9c2d0c87427ab9` |
| semantic-bundle.json | dependency ID / package revision | `11eedb45fc80d8b1f8db1bc5afdceb1754914c5e2f49ba48ad2b4d87d63bb007` |
| package-manifest.json | dependency ID / package revision | `9d430833bb359600b4c9f67f225e9c8a74fb883d6fe119ca8b7c2502b8ce4499` |

constants.json과 그 sidecar는 byte-preserved다. finite-policy/acquisition-identity/rechecker-lineage/semantic-bundle은 dependency ID만 바뀌었다. status-composition은 guard 참조만 추가 정정했으며 기존 status/priority/publication 의미는 보존했다. B1 문서의 embedded bundle ID를 새 hash로 갱신했다. active normative JSON/markdown reverse-reference 검사에서 변경된 old hash가 남지 않았다. 역사 report/receipt와 before-* archive의 old hash는 의도적으로 보존한다.

## 독립 PASS와 의무 상태 반영

B1 구조, B2 provenance, B5 finite method, B6 lineage, B7 identity, B8 status/composition 및 mutation/validation **plan**의 4cb2910 독립 PASS를 보존한다. 이들을 재설계하지 않았다. [I1–I22 ledger](c1b1-independent-impulse-v1/obligation-ledger.md)의 상태는:

```text
I1, I14:  FIX APPLIED / INDEPENDENT RECHECK PENDING (F-CLOSURE-1)
I10, I18: FIX APPLIED / INDEPENDENT RECHECK PENDING (F-CLOSURE-2)
other obligations: received READY / IMPLEMENTATION-DEPENDENT retained
```

B5는 **METHOD SPEC PASS / RUNTIME NUMERIC INSTANCE STILL REQUIRED BEFORE ACTIVATION**다. Numeric instance가 없는 것이 이번 FAIL의 원인은 아니다. 근거 없는 budget 숫자를 발급하지 않았다. 실제 activation 전 exact instance hash, independent activation decision, source/platform/allocator-bound majorants, whole-call preflight, isolated worker memory/CPU/wall enforcement는 별도 gate로 남는다.

P0 raw 12,061 bytes/SHA-256 `a598057183121b9c928b3a9804c8e2e99afa553bad570a471aa4130f20e6b049`, 91 constants exact transcription, A-EV exact `27e48770ab5db666bcd78034d151ddbb04b6af54` object/path는 독립 재검토에서 확인됐다. [audit-result-update.json](../current/c1b1-closure-fixes-2026-10-05/audit-result-update.json)에 그 확인 상태를 기록했다. 이전 author-time provenance flags는 역사 metadata로 보존하며 현재 미확인으로 되돌리는 판정에 쓰지 않는다. A-EV는 계속 comparison-only / NOT A TRUSTED ANTECEDENT다. Publisher raw를 새로 다운로드하거나 모든 출처 진위를 인증했다는 주장은 아니다.

## 작성자 정적 확인과 bytes 보존

[static checker](../audit/c1b1-closure-fixes-2026-10-05/check_static.py)는 구현 helper나 attached witness script를 import/호출하지 않는다. JSON/markdown의 규범과 exact bytes/hash, 기록된 witness 차이만 검사하는 author 도구이며 Impulse validator/rechecker가 아니다.

```text
python audit/c1b1-closure-fixes-2026-10-05/check_static.py --output current/c1b1-closure-fixes-2026-10-05/static-consistency.json
```

[static consistency receipt](../current/c1b1-closure-fixes-2026-10-05/static-consistency.json): author static checks PASS. [preservation receipt](../current/c1b1-closure-fixes-2026-10-05/receipt-after.json): 보호 Arithmetic 8개는 65d8fd2 antecedent와 actual bytes 동일, 기존 tracked source/tests 불변, 기존 historical current/evidence 불변, 새 Impulse production .py 없음. 추가 .py는 이 정적 검사 도구와 그대로 보존한 auditor witness script뿐이다.

B2/B5/B6/B7/mutation 문서와 constants data는 byte-preserved다. Impulse/V2 실행, production tests, mutants, benchmark, 새 numeric runtime instance, commit/push는 하지 않았다. 새 receipt의 self hash는 별도 파일에서 자기 참조하지 않는다. 독립 review 전 author 확인을 independent PASS로 승격하지 않는다.

```text
Independent Impulse V1: DESIGN ONLY / NOT IMPLEMENTED
Closure fixes: F-CLOSURE-1 FIX APPLIED / F-CLOSURE-2 FIX APPLIED
INDEPENDENT RECHECK PENDING
implementation_may_start = false
Arithmetic V1: INDEPENDENT REVIEW PASS
exact_slow DEFAULT; exact_fast EXPERIMENTAL / OPT-IN
Overall physical C1-B1: J_NOT_VERIFIED / NotCertified
```
