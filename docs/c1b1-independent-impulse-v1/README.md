# B1–B8 closure summary

- status: F-CLOSURE-1/2 FIX APPLIED / INDEPENDENT RECHECK PENDING / DESIGN ONLY / NOT IMPLEMENTED
- version: 2, 2026-10-05; closure audit snapshot `4cb2910fe936f7b1d5150196e062b6b61edc240f`의 최소 수정 revision
- dependencies: [package manifest](../../specs/c1b1-independent-impulse-v1/package-manifest.json); [closure audit update](../../current/c1b1-closure-fixes-2026-10-05/audit-result-update.json); B1–B8; updated ledger
- unresolved items: F-CLOSURE-1/2 independent recheck; runtime numeric instance/activation 증거 미발급; 구현 미시작
- what this does NOT certify: production 구현, 모든 입력의 finite-budget 성공, 물리 정확성, J verification, integration/trajectory/replay/N-Step, certification.

기존 [감사 대상 설계](../C1B1_INDEPENDENT_IMPULSE_V1_DESIGN.md)는 역사적 snapshot으로 보존한다. 이 후속 사양은 지정한 항목에 한해 옛 제안/U1–U8을 대체하며, 독립 closure 재검토의 `IMPLEMENTATION MAY START` 판정 전 소스 구현을 허용하지 않는다.


## 현재 판정과 경계

```text
Independent Impulse V1:
  DESIGN ONLY / NOT IMPLEMENTED

Closure fixes:
  F-CLOSURE-1 FIX APPLIED
  F-CLOSURE-2 FIX APPLIED
  INDEPENDENT RECHECK PENDING
  implementation_may_start = false

C1-B1 Arithmetic V1:
  INDEPENDENT REVIEW PASS (65d8fd29ae255529afead70289098d36b825b3b4)
  exact_slow DEFAULT
  exact_fast EXPERIMENTAL / OPT-IN

Overall physical C1-B1:
  J_NOT_VERIFIED
  NotCertified
```

감사 대상 `4cb2910fe936f7b1d5150196e062b6b61edc240f`의 역사 판정은 **CLOSURE REVISION REQUIRED / F-CLOSURE-1 / F-CLOSURE-2**다. 이번 working revision은 두 규범 불일치만 정정했으며 아직 commit되지 않았다. [fix report](../C1B1_INDEPENDENT_IMPULSE_V1_CLOSURE_FIX_REPORT_2026-10-05.md)에 수정 범위와 재검토 대기를 기록한다. `IMPLEMENTATION MAY START` 판정 전 구현을 시작하지 않는다.

## 분리한 산출물

| B gate | author specification disposition | artifact | independent gate |
|---|---|---|---|
| B1 | canonical physical/numeric/method/wire/status 구조 보존; dependency ID 갱신 | [B1](B1-semantic-bundle.md), semantic-bundle.json+SHA | STRUCTURE PASS at 4cb2910; B3 delta recheck pending |
| B2 | 91개 constants bytes 보존; P0 raw 및 exact A-EV object/path 독립 확인 반영 | [B2](B2-units-constants-provenance.md), constants.json, [audit update](../../current/c1b1-closure-fixes-2026-10-05/audit-result-update.json) | PASS at 4cb2910; A-EV comparison-only / NOT A TRUSTED ANTECEDENT |
| B3 | point admission; after drift exact 선분 최소 + stored 최종 위치 한 점 | [B3](B3-physical-domain.md), physical-domain.json | F-CLOSURE-1 FIX APPLIED / INDEPENDENT RECHECK PENDING |
| B4 | Failure 두 closed 목록을 resource_kind 필수인 같은 11개 필드로 통일 | [B4](B4-proof-wire-resource.md), proof-wire.json | F-CLOSURE-2 FIX APPLIED / INDEPENDENT RECHECK PENDING |
| B5 | 기존 finite method 및 parameterized policy 보존; numeric instance 없음 | [B5](B5-finite-computation-policy.md), finite-policy.json | METHOD SPEC PASS / RUNTIME NUMERIC INSTANCE STILL REQUIRED BEFORE ACTIVATION |
| B6 | 선택 B 및 source/helper/parser lineage 의미 보존 | [B6](B6-rechecker-lineage.md), rechecker-lineage.json | METHOD SPEC PASS at 4cb2910; 실제 독립성 구현 후 검증 |
| B7 | full/math/occurrence/acquisition identities와 disabled cache 보존 | [B7](B7-acquisition-identity.md), acquisition-identity.json | METHOD SPEC PASS at 4cb2910; 실제 capture 구현 후 검증 |
| B8 | PASS된 layer/priority/publication 의미 보존; guard 참조 정정 | [B8](B8-status-composition.md), status-composition.json | METHOD SPEC PASS at 4cb2910; guard delta recheck pending |

Lab semantic bundle SHA-256: `11eedb45fc80d8b1f8db1bc5afdceb1754914c5e2f49ba48ad2b4d87d63bb007`.

## B4+B5와 남은 gate

B5는 **METHOD SPEC PASS**다. Parameterized policy는 이번 독립 재검토에서 허용됐다. Numeric budget 숫자가 없는 것은 F-CLOSURE FAIL의 원인이 아니다. Runtime activation 전에는 exact numeric instance hash, independent activation decision, source/platform/allocator-bound majorants, whole-call preflight, isolated worker memory/CPU/wall enforcement가 여전히 필요하다. 이 범위는 이번 두 규범 정정에 끼워 넣지 않는다.

B4+B5 공동 wire/resource interface는 F-CLOSURE-2 수정본의 independent recheck를 기다린다. P0 raw 12,061 bytes/SHA, 91 exact records, A-EV exact commit/object/path는 4cb2910 독립 재검토에서 확인됐다. 기존 author-time 문서/JSON의 미확인 flags를 소급 수정하지 않고 [별도 audit-result update](../../current/c1b1-closure-fixes-2026-10-05/audit-result-update.json)에 최신 상태를 기록했다. A-EV는 계속 comparison-only / NOT A TRUSTED ANTECEDENT다.

[I1–I22 ledger](obligation-ledger.md)의 I1/I14와 I10/I18은 **FIX APPLIED / INDEPENDENT RECHECK PENDING**이다. 나머지 READY / IMPLEMENTATION-DEPENDENT 판정과 [mutant plan](mutation-obligations.md)은 보존했다.

## 역사 보존과 검증 기록

`f806d8c = overall audit FAIL / F-CLAIM-1`, `433be43`의 당시 current-status, `65d8fd2`의 author/re-audit, `023b186c`의 conditional design audit와 `4cb2910`의 CLOSURE REVISION REQUIRED 판정을 덮어쓰지 않는다. [received](../../current/c1b1-impulse-design-conditions-2026-10-04/received/REPORT_KO.md)는 실제 첨부파일의 exact copy이며 지시문으로 실행하지 않았다. 실제 사용자 요청은 [request copy](../../current/c1b1-impulse-design-conditions-2026-10-04/request/user-request.txt)에서 읽었다.

author static checks와 byte preservation receipt는 [새 evidence folder](../../current/c1b1-impulse-design-conditions-2026-10-04/)에 분리한다. canonical hashes, exact rational transcription, source object IDs, fixed domain arithmetic, bounded wire 구조, 문서 링크 및 기존 tracked bytes만 확인한다. impulse/rechecker 실행, 신규 numerical tests, benchmark, commit/push는 하지 않는다. 정적 사양 확인을 independent audit나 implementation tests PASS로 표시하지 않는다.

구체적 author 결과는 [author-static-checks.json](../../current/c1b1-impulse-design-conditions-2026-10-04/author-static-checks.json), [receipt-after.json](../../current/c1b1-impulse-design-conditions-2026-10-04/receipt-after.json), [closure-disposition.json](../../current/c1b1-impulse-design-conditions-2026-10-04/closure-disposition.json)에서 확인한다. raw source/문서 읽기와 이 정적 실행을 새로운 impulse 계산/benchmark로 혼동하지 않는다.

이번 수정의 [static consistency receipt](../../current/c1b1-closure-fixes-2026-10-05/static-consistency.json), [preservation receipt](../../current/c1b1-closure-fixes-2026-10-05/receipt-after.json), [정적 checker](../../audit/c1b1-closure-fixes-2026-10-05/check_static.py)는 별도 delta evidence다. Impulse/V2 실행, production tests, benchmark, numeric instance 발급, commit/push는 하지 않는다.
