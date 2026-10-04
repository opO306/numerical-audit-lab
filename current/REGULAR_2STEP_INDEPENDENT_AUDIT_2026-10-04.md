# Regular 2-Step Chain 외부 재감사 반영 — 2026-10-04

## 범위와 남아 있는 한계

이번 PASS는 frozen Gala 1.12.0, 현재 regular 입력, known-03/fresh-03의 실제 두 native
process에서 얻은 Regular 2-Step Chain에 한정한다. init return → step1 entry는 여전히
UNTRACED다. 여섯 native carry Form의 symbolic coefficient는 모두 0이고 box는 nonzero다.
별도 nonzero coefficient unit test는 native caller에서 그 경우를 관측한 증거가 아니다.

known/fresh가 서로 다른 process라는 사실은 ASLR diversity 입증이 아니다.
`harness_output.json.n_steps=1`은 inherited stale metadata다. 실제 호출 두 개는 source의
정확한 한 토큰 변경과 native entry/return으로 확인된 것이다. Frozen V2의 수학 자체를
처음부터 다시 감사한 결과도 아니다. 기존 감사된 V2를 전제로 actual step2 → Numeric IR
→ frozen V2 correspondence를 감사한 결과다.

3-step, N-step induction, trajectory correctness, global accumulated error, shadowing,
final observable error, physical accuracy, cross-machine correctness는 범위 밖이다.

## 현재 외부 판정과 봉인 당시 상태

```text
Sealed implementation-time status:
IMPLEMENTED
CHECKER PASS
INDEPENDENT AUDIT PENDING

External independent audit result — 2026-10-04:
INDEPENDENT AUDIT PASS

Current scoped status:
IMPLEMENTED / CHECKER PASS / INDEPENDENT AUDIT PASS
```

감사 대상 branch는 `regular-2step-chain`, HEAD는
`e69119e259b862a7d8462c8d61333782ee2747fd`다. 이 후속 기록의 커밋을 새 외부 감사 대상
HEAD로 대체하지 않는다. 기존 implementation source와 봉인 증거의 바이트는 보존한다.

판정의 출처는 사용자가 전달한 외부 재감사 보고서와 receipt다. 이번 반영 작업자가 새로
수행한 독립 수치 감사나 외부 판정으로 표현하지 않는다. 아래 해시는 수령 바이트의
동일성을 나타내며 감사자 신원을 암호학적으로 인증하는 서명은 아니다.

## 수령 자료와 provenance

원 수령 위치: `D:/regular2step-independent-audit-retry-2026-10-04/`.
보고서·receipt·독립 검사 소스 6개를 새
[수령 자료 디렉터리](regular-2step-independent-audit-2026-10-04/INDEPENDENT_REAUDIT_REPORT_KO.md)에
원 바이트 그대로 복사했다. 디렉터리 자체의 `.gitattributes`로 Git의 text 변환을 끈다.
원 외부 감사 checkout, bundle, manifest, diagnostic scripts는 변경하지 않는다.

| 자료 | SHA-256 |
|---|---|
| [보고서 원본](regular-2step-independent-audit-2026-10-04/INDEPENDENT_REAUDIT_REPORT_KO.md) | `23537655ff0c244e21edc865f6b53320e5e3cc6f34022c81f5c9b30ef74e6338` |
| [receipt 원본](regular-2step-independent-audit-2026-10-04/independent_reaudit_receipt.json) | `9f72cf658b24e5442356ed68ddd3f2ba8cb82bb8bf8dc5731cfbe7bac869457f` |
| 기존 전달 ZIP | `868558e66f72c3344b4e1145812a2c50f6a6ff32749c5f5d718531e92af599e8` |

복사한 8개 파일의 size/SHA-256와 원 수령 경로는
[RECEIVED_EVIDENCE_MANIFEST.json](regular-2step-independent-audit-2026-10-04/RECEIVED_EVIDENCE_MANIFEST.json)에
기록했다. 독립 검사 소스에 있는 원 감사 checkout의 절대경로도 보존했다. 파일을
복사했다고 이 스크립트가 재배치 가능한 checker가 되거나 새로 재실행된 것은 아니다.

## 외부 감사자가 직접 수행한 검사

아래 결과는 수령 보고서의 실행 결과다. 이번 문서 반영 작업에서 재실행한 결과와 구분한다.

| 항목 | 수령한 외부 재감사 결과 |
|---|---|
| 전달 ZIP | 355,162,217 bytes; CRC 이상 없음; 전체 4,885 entries / payload 4,884; size/SHA mismatch 0; duplicate name 0 |
| Git/bundle | bundle verify PASS; strict fsck exit 0; baseline ancestry PASS; recovered HEAD 일치 |
| 기존 자산 | baseline 1,488개 중 Git blob 동일 1,487개; 기존 변경은 `.gitattributes` 1개; 삭제 0 |
| public checker | known/fresh 각각 CHECKER_PASS; test_trust_mode=false |
| step2 구조 | case당 operations 22 = ADD 7 / SUB 5 / MUL 10; values 151; state bindings 107; carry 6 |
| raw chain | case당 1,428 rows = init 191 / step1 255 / caller 727 / step2 255; seq·SHA chain·seam 재계산 일치 |
| caller EA | case당 PRE reads 218 / writes 111; 실제 PRE registers·FS/GS로 주소 재계산; mismatch 0 / unsupported 0 / protected overlap 0 |
| gradient·t/dt | 실제 gradient 16-byte zero write와 same-zero write; 실제 t/dt PRE-read instruction·operand·address·bytes·XMM 인자 연결 |
| 독립 binary64 | 별도 Fraction + 직접 구현 RNE encoder; known 22/22, fresh 22/22; mismatch 0 |
| semantic mutations | 새 임시 디렉터리 생성·재실행; repaired semantic 1–15 모두 SEMANTIC REFUSED; HASH/TRUST control 각각 REFUSED |

이전 caller effective-address 질문은 이번 독립 주소 재계산으로 해소됐다는 외부 판정을
반영한다. 이를 미래 caller path의 모든 addressing form에 대한 증명으로 확대하지 않는다.

## 테스트 수의 정확한 의미

외부 감사자가 이번에 새로 실행한 Regular 2-Step 전용 테스트는 **81/81 PASS**다.
chain/mutation/delivery/portability 37개와 acquisition/structure 44개로 구성된다.

기존 final JUnit의 63 + 101 + 479는 고유 ID 643개다. covering 37개와의 중복은 19개,
추가는 18개여서 전체 고유 inventory는 **643 + 18 = 661**이다. 외부 감사에서 이 661개
전체를 새로 실행한 것은 아니다. 나머지는 기존 JUnit과 Git blob 보존으로 확인했다.

이번 반영 작업의 새 native acquisition은 **0**, 새 pytest 실행도 **0**이다.
검증 대상은 수령 파일의 byte identity, 링크/JSON, 기존 tracked 파일 보존, 새 커밋의 Git
복구와 원격 SHA다. 새 실행 영수증은 원 감사 디렉터리와 기존 ZIP 밖의 별도 작업 경로
`D:/numerical-audit-lab-regular-nstep-design-2026-10-04/`에 둔다.

## 다음 작업의 경계

[Regular N-Step Template / Induction Design](../docs/REGULAR_NSTEP_TEMPLATE_INDUCTION_DESIGN_2026-10-04.md)은
이번 요청에 따른 설계 산출물이다. 상태는 PROPOSED / DESIGN ONLY이며 induction 증명이
완료됐거나 새 checker/실행기가 구현됐다는 뜻이 아니다. 2-step 결과를 반복 복제하는
3-step 구현과 native acquisition은 시작하지 않았다.

기존 chain/capture/acquisition seal/structure report/PACKAGE_MANIFEST/delivery ZIP/audit
evidence와 과거 PENDING 기록을 보존한다. 이 문서가 좁은 Regular 2-Step 외부 판정의
후속 우선 기록이다. 이전 Gate/one-step/Caller 판정은 각 원 범위에서 유지한다.
