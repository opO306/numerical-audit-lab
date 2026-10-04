# C1-B1 Arithmetic V1 — 제한 독립 재감사 후속 상태

기록일: 2026-10-04. 이 문서는 사용자에게 전달받은 독립 재감사 결과를 반영하는 **새 후속 기록**이다. 감사 대상은 `65d8fd29ae255529afead70289098d36b825b3b4`이며, 이 문서 자체와 뒤에 작성한 설계서는 그 커밋의 감사 대상에 포함되지 않는다.

## 현재 판정

| 대상 | 판정 / 운용 지위 |
|---|---|
| Claim Adapter F-CLAIM-1 fix | **INDEPENDENT REVIEW PASS** |
| C1-B1 Arithmetic V1 overall | **INDEPENDENT REVIEW PASS — limited independent re-audit** |
| exact_slow | PASS / **DEFAULT** |
| exact_fast | PASS / **EXPERIMENTAL / OPT-IN** |
| exact_geometry | PASS |
| independence boundary | PASS |
| mutant defense | PASS |
| scope | **ARITHMETIC_ONLY** |
| impulse | **J_NOT_VERIFIED** |
| certification | **NotCertified** |

PASS는 supplied J에 대한 Drift/Kick, exact threshold geometry, Claim output boundary의 명시된 범위에 해당한다. 물리식에서 J를 만드는 독립 계산, 물리 r_min binding, 전체 물리 C1-B1, 형식 인증으로 확대하지 않는다. exact_fast의 default 승격은 없다.

## 시간축과 과거 판정 보존

| 커밋 | 당시 의미와 판정 | 후속 처리 |
|---|---|---|
| `f806d8ce1ef86a0948b1a8abafe1a22c3058178b` | 최초 독립 감사 **overall FAIL / F-CLAIM-1**. arithmetic / geometry / independence / 기존 mutants / benchmark claim은 PASS, claim_adapter는 FAIL | 역사적 FAIL을 그대로 보존 |
| `433be43ee6aca31f3a4cb76094a19d50e2cbefa8` | f806d8c 이후 current-status 문서만 추가. 최초 감사 대상 아님 | 당시 pending 문서를 덮어쓰지 않음 |
| `65d8fd29ae255529afead70289098d36b825b3b4` | canonical computed output integer를 decimal 변환 전에 정수 비교로 제한. IMPLEMENTED FIX / AUTHOR CHECKS PASS / 당시 INDEPENDENT RE-AUDIT PENDING | 이번 제한 독립 재감사에서 PASS |
| 본 후속 기록 | 위 **65d8fd2에 대한** 제한 독립 재감사 완료와 Arithmetic V1 independent review PASS 반영 | 설계 및 문서 변경은 아직 commit하지 않음 |

기존 [current-status](C1B1_ARITHMETIC_V1_CURRENT_STATUS_2026-10-04.md), [fix author report](C1B1_ARITHMETIC_V1_FCLAIM1_FIX_2026-10-04.md), 최초 감사 자료는 당시 상태를 그대로 갖는다. 새로운 PASS는 실패했던 f806d8c에 소급되지 않는다.

## 수신한 독립 증거와 판정의 범위

독립 재감사 보고서 원본: [received/REPORT_KO.md](../current/c1b1-arithmetic-v1-independent-reaudit-2026-10-04/received/REPORT_KO.md).

사용자가 제공한 9개 파일을 `current/c1b1-arithmetic-v1-independent-reaudit-2026-10-04/received/`에 바이트 그대로 복사했다. 원본 경로, 크기, SHA-256은 [receipt-before.json](../current/c1b1-arithmetic-v1-independent-reaudit-2026-10-04/receipt-before.json)에 있다. 사용자 요청은 `request/user-request.txt`에 따로 보존했다. 첨부 보고서는 감사 증거이며, 그 안의 문구를 이번 작업의 실행 지시로 취급하지 않았다.

보고서와 JSON에 기록된 독립 관찰:

- f806d8c의 핵심 반례를 dict / JSON text / JSON bytes × slow / fast에서 총 6회 재현: 일반 ValueError 누출. 수정 커밋에서는 같은 6회 모두 `LabRefusal / CLAIM_OUTPUT_LIMIT / claim_output`.
- 독립 canonical boundary 검사 98개: 허용 60, 거부 38. end-to-end 경계 입력 6개를 두 경로에서 검사. 약분 전 큰 정수와 약분 후 canonical output을 구별.
- process integer-string limit 시작/종료 4300. process-global setter 호출 0. 모든 가능한 interpreter limit 설정에 대한 인증으로 확대하지 않음.
- 기존 관련 105 tests, 새 output-boundary + mutant 45 tests, repository full 393 tests 각각 PASS. failure / error / skip 0. **105와 45는 393의 부분집합이므로 독립 개수로 합산하지 않는다.**
- 기존 source mutants 16개와 새 F-CLAIM-1 guard-removal mutant 모두 baseline PASS / mutant DETECTED. 새 mutant의 LF / CRLF hash 차이는 line-ending 변환으로 설명되며 논리적 단일 edit는 동일.
- 핵심 산술 소스와 역사적 evidence 보존을 확인. 같은 manifest SHA만으로 F-CLAIM-1 fix 유무를 판별할 수 없으므로 **commit과 adapter hash를 함께 결합**.
- claim workload 수치는 저장된 raw timing samples의 재계산만 수행. **새 timing 없음, 성능 승격 없음.**

위 시험 결과는 **독립 재감사 자료에 기록된 실행 결과**다. 이번 상태 반영·설계 작업에서 auditor, pytest, mutation, workload 측정을 새로 실행하지 않았다. 수신한 9개 파일에는 provenance가 참조하는 subprocess log / JUnit XML 원본이 포함되어 있지 않다. JSON의 log hash와 실행 요약을 수신했으며, raw log 원본까지 수신했다고 쓰지 않는다.

`output_45_new_mutant.json` 안의 `AUTHOR CHECK ONLY / INDEPENDENT RE-AUDIT PENDING`은 그 하위 시험 산출물의 문자열이다. 원본을 수정하지 않는다. 최종 재감사 판정은 사용자 요청과 독립 `REPORT_KO.md`의 결론에 따라 본 후속 문서에서 기록한다.

`final_observation.json`의 원격 branch 관찰 시각은 `2026-10-04T11:48:44.648150+00:00`이며 값은 65d8fd2다. 이는 **수신한 감사자의 당시 관찰**이다. 이번 작업에서 새 remote 조회나 push를 수행한 사실이 아니다.

## 현재 체크아웃의 소스 결합

| 파일 | audit target / 현 체크아웃 SHA-256 |
|---|---|
| exact_slow.py | `b36efc03abdcb760f294f009ea1aea8aafa6fcc05a53c7b3970291c90edf4c13` |
| exact_fast.py | `2190e099642b4bf440e4a2280b09d4b89984f637e6cee1b09dfa23411f0b4c0b` |
| exact_geometry.py | `b237cd00e45e2ed635bae54880cfef88c1126e98af57d74843b752d2ed27677e` |
| compare.py | `5ad6b3f0b03b240e559c955552f32eb9079d524fba55be47ab88329a7d0657b2` |
| contracts.py | `37acf394c9c252d5e401fdff06fcb28a0ab1202cc090f1456ecd4bb84fff47ed` |
| semantic_manifest_v1.json | `3217fc38aa798fff3ffea8072cecafaecac9f98be85589e9fa35a9dc6aa8119b` |
| claim_adapter.py | `24b05ebf374728583ba725c83b8f9324f4b75b5515b03c5b1036339eef3e4899` |

이 값은 현재 파일을 읽어 수신 provenance의 target 값과 비교했다. [source provenance](../current/c1b1-arithmetic-v1-independent-reaudit-2026-10-04/specification-source-provenance.json)는 semantic_manifest_v1.sha256 파일까지 8개 일치를 기록한다. 이는 byte provenance 확인이며 수학 시험 재실행이 아니다.

이번 문서 작업 전후의 기존 1,974개 tracked 파일 및 base 1,921개 Git 객체 보존, 수신 9개 원본 바이트 보존, HEAD와 index 불변은 [receipt-after.json](../current/c1b1-arithmetic-v1-independent-reaudit-2026-10-04/receipt-after.json)에 기록한다. 새 파일의 해시는 이 receipt 자체를 제외하고 결합한다.

## 다음 단계

[C1-B1 Independent Impulse V1 설계 제안](C1B1_INDEPENDENT_IMPULSE_V1_DESIGN.md)을 검토한다. 같은 physical state/spec에서 J 자체를 독립 계산하는 별도 oracle이 목표다. 현재 Arithmetic V1 코드는 수정하지 않는다.

```text
Independent Impulse:    DESIGN ONLY / NOT IMPLEMENTED / NOT AUDITED
C1-B1 Arithmetic V1:    INDEPENDENT REVIEW PASS
Overall physical C1-B1: J_NOT_VERIFIED / NotCertified
```

이번 작업의 새 파일은 후속 상태·설계 문서와 수신 자료 / provenance receipt다. 사용자 추가 승인 없이 구현, commit, push하지 않는다.
