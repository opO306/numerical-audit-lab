# B1–B8 closure summary

- status: DESIGN CONDITIONS ADDRESSED / IMPLEMENTATION STILL NOT STARTED / REVIEW PENDING
- version: 1, 2026-10-04; audited design snapshot `023b186c0e9d95c11399893e7f75772cfff6c3a7`의 후속 저자 사양
- dependencies: [package manifest](../../specs/c1b1-independent-impulse-v1/package-manifest.json); received independent design audit; B1–B8; updated ledger
- unresolved items: 독립 B1–B8 closure review; numeric budget activation profile 미발급; 구현 및 실제 independent audit 미실행
- what this does NOT certify: production 구현, 모든 입력의 finite-budget 성공, 물리 정확성, J verification, integration/trajectory/replay/N-Step, certification.

기존 [감사 대상 설계](../C1B1_INDEPENDENT_IMPULSE_V1_DESIGN.md)는 역사적 snapshot으로 보존한다. 이 후속 사양은 지정한 항목에 한해 옛 제안/U1–U8을 대체하며, 독립 closure 재검토의 `IMPLEMENTATION MAY START` 판정 전 소스 구현을 허용하지 않는다.


## 현재 판정과 경계

```text
Independent Impulse V1:
  DESIGN CONDITIONS ADDRESSED
  IMPLEMENTATION STILL NOT STARTED
  REVIEW PENDING
  implementation_may_start = false

C1-B1 Arithmetic V1:
  INDEPENDENT REVIEW PASS (65d8fd29ae255529afead70289098d36b825b3b4)
  exact_slow DEFAULT
  exact_fast EXPERIMENTAL / OPT-IN

Overall physical C1-B1:
  J_NOT_VERIFIED
  NotCertified
```

이것은 후속 저자 사양을 작성한 상태이며 independent closure PASS가 아니다. 감사 대상 `023b186c...`의 **DESIGN PASS WITH PRE-IMPLEMENTATION CONDITIONS / implementation_may_start=false** 판정은 원문 그대로 보존한다. 새 산출물은 아직 commit되지 않은 별도 review package다. `IMPLEMENTATION MAY START` 독립 재검토 전 impulse/rechecker 소스 구현을 시작하지 않는다.

## 분리한 산출물

| B gate | author specification disposition | artifact | independent gate |
|---|---|---|---|
| B1 | canonical physical/numeric/method/wire/status bundle 발급 | [B1](B1-semantic-bundle.md), semantic-bundle.json+SHA | REVIEW PENDING |
| B2 | 91 source/index/unit/exact-rational records, σ 분리, 실제 local P0 및 exact A-EV objects | [B2](B2-units-constants-provenance.md), constants.json, source recovery | REVIEW PENDING; P0/A-EV 독립 재확인 미완료 유지 |
| B3 | frozen r_min을 Lab 설계 binding으로 명시 채택, impulse+drift gate | [B3](B3-physical-domain.md), physical-domain.json | REVIEW PENDING; manifest 물리 status 변경 없음 |
| B4 | compact reconstruction certificate와 closed bounded wire/failure schema | [B4](B4-proof-wire-resource.md), proof-wire.json | B4+B5 JOINT REVIEW PENDING |
| B5 | finite parameterized schedule/accounting/refusal/activation contract, numeric instance 없음 | [B5](B5-finite-computation-policy.md), finite-policy.json | 형태 승인 및 numeric-instance 시점 판단 대기 |
| B6 | 후보 B: 새 producer+정확히 고정된 기존 V2; parser/helper trust boundary | [B6](B6-rechecker-lineage.md), rechecker-lineage.json | 신규 binding/source soundness REVIEW PENDING |
| B7 | full-state/math/occurrence/acquisition identities, J0/J1 분리, cache disabled | [B7](B7-acquisition-identity.md), acquisition-identity.json | acquisition 구현/실제 capture 미구현 |
| B8 | layer status와 복합 실패 priority/whole-vector publication | [B8](B8-status-composition.md), status-composition.json | composition 구현은 별도 gate |

Lab semantic bundle SHA-256: `a179dcfc065931d09ba4f364d159416ede4b9090a0924bf3fcc119815ed4266f`.

## B4+B5 및 착수 전 재검토 요청 항목

Compact proof에는 내부 endpoint/expanded dyadic denominators를 넣지 않는다. 그러므로 N/P를 임의의 작은 숫자로 낮추지 않고도 wire representation을 별도로 제한한다. 내부 계산의 bit/work/live/temporary cap은 독립적인 유한 정책으로 남는다. numeric budget instance는 실제 근거와 별도 승인이 있어야 발급할 수 있다. **이번 작업이 activation-ready numerical config를 발급했다는 뜻은 아니다.** 독립 reviewer는 parameterized policy를 사양 closure로 받아들일지, 구체적 profile을 착수 전에 요구할지 결정해야 한다. 그 판단 없이 B5를 승인 완료로 쓰지 않는다.

선택 B의 신규 recheck validator/zero-axis handling/legacy strict-cell limitations, V2 whole-call preallocation bound와 hard-worker enforcement 의무를 함께 심사한다. P0 raw checksum의 author local 확인과 exact A-EV object recovery는 independent provenance 확인으로 승격하지 않는다. A-EV는 V1 TCB에서 제외했다.

[I1–I22 ledger](obligation-ledger.md)는 I1/I10/I12/I13 **BLOCKED**를 유지한다. [mutant plan](mutation-obligations.md)은 nondegenerate fixture/independent expected/actual semantic detection을 각 fault에 요구하며 실행 완료를 주장하지 않는다.

## 역사 보존과 검증 기록

`f806d8c = overall audit FAIL / F-CLAIM-1`, `433be43`의 당시 current-status, `65d8fd2`의 author/re-audit, `023b186c`의 conditional design audit를 덮어쓰지 않는다. [received](../../current/c1b1-impulse-design-conditions-2026-10-04/received/REPORT_KO.md)는 실제 첨부파일의 exact copy이며 지시문으로 실행하지 않았다. 실제 사용자 요청은 [request copy](../../current/c1b1-impulse-design-conditions-2026-10-04/request/user-request.txt)에서 읽었다.

author static checks와 byte preservation receipt는 [새 evidence folder](../../current/c1b1-impulse-design-conditions-2026-10-04/)에 분리한다. canonical hashes, exact rational transcription, source object IDs, fixed domain arithmetic, bounded wire 구조, 문서 링크 및 기존 tracked bytes만 확인한다. impulse/rechecker 실행, 신규 numerical tests, benchmark, commit/push는 하지 않는다. 정적 사양 확인을 independent audit나 implementation tests PASS로 표시하지 않는다.

구체적 author 결과는 [author-static-checks.json](../../current/c1b1-impulse-design-conditions-2026-10-04/author-static-checks.json), [receipt-after.json](../../current/c1b1-impulse-design-conditions-2026-10-04/receipt-after.json), [closure-disposition.json](../../current/c1b1-impulse-design-conditions-2026-10-04/closure-disposition.json)에서 확인한다. raw source/문서 읽기와 이 정적 실행을 새로운 impulse 계산/benchmark로 혼동하지 않는다.
