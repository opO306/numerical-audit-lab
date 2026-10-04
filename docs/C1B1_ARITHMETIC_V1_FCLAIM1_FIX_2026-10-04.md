# C1-B1 Arithmetic V1 — F-CLAIM-1 후속 수정과 감사 결과 반영

2026-10-04 (Asia/Seoul). **ARITHMETIC_ONLY / J_NOT_VERIFIED / NotCertified**.

```text
IMPLEMENTED FIX
AUTHOR CHECKS PASS
INDEPENDENT RE-AUDIT PENDING
NotCertified
```

이 문서는 수령한 독립 감사의 FAIL을 반영하고, computed artifact 직렬화 경계만
수정한 새 제출물을 기록한다. 새 제출물에 대한 독립 감사 PASS를 발행하지 않는다.
fast는 **EXPERIMENTAL / OPT-IN**, 기본 경로는 `exact_slow`다.

## 역사적 감사 판정과 새 감사 대상

독립 감사 대상은 `f806d8ce1ef86a0948b1a8abafe1a22c3058178b`다.
수령한 [원본 REPORT_KO.md](../current/c1b1-claim-output-fix-2026-10-04/received/REPORT_KO.md)의
판정은 다음과 같으며 사후 수정하지 않았다.

| 항목 | f806d8c의 독립 감사 판정 |
|---|---|
| exact_slow | INDEPENDENT REVIEW PASS |
| exact_fast | INDEPENDENT REVIEW PASS |
| exact_geometry | INDEPENDENT REVIEW PASS |
| independence | PASS |
| 기존 16 mutant defense | PASS |
| benchmark claim | PASS |
| claim_adapter | FAIL — F-CLAIM-1 |
| overall audit | **FAIL** |
| scope / impulse / certification | ARITHMETIC_ONLY / J_NOT_VERIFIED / NotCertified |

작업 시작 시 local HEAD와 실제 remote `regular-2step-chain` HEAD는 모두
`433be43ee6aca31f3a4cb76094a19d50e2cbefa8`이었다. 이는 `f806d8c` 이후 상태 문서만
추가한 commit이며 위 독립 감사 대상이 아니다.
[433be43의 상태 문서](C1B1_ARITHMETIC_V1_CURRENT_STATUS_2026-10-04.md)는 당시의
“f806d8c independent review pending” 기록을 그대로 보존했다. 현재 판정은 이 후속
문서의 **f806d8c = overall FAIL**과 구분해서 읽는다.

새 수정은 `codex/c1b1-fclaim1-output-limit` 브랜치의 **이 문서·수정·회귀 시험·저자
검증 receipt를 함께 도입하는 별도 fix commit**을 감사 대상으로 한다. 그 대상의
상태는 **INDEPENDENT RE-AUDIT PENDING**이다. 자기 commit SHA를 자기 파일에
기록할 수 없으므로 정확한 commit/tree SHA와 committed-byte 검사는 commit 직후
저장소 밖에 생성하는
[post-commit receipt](../../numerical-audit-lab-fclaim1-delivery-2026-10-04/post-commit-receipt.json)에
고정한다. 저장소 안의 저자 receipt는 실제 시험한 source SHA-256을 먼저 고정한다.
사용자 PC 외부로 전달할 때 이 post-commit receipt도 함께 전달해야 한다.

## Claim V1 computed output 계약

Frozen [산술 manifest](../independent_checker/c1b1/semantic_manifest_v1.json)와
`SPEC_SHA256=3217fc38aa798fff3ffea8072cecafaecac9f98be85589e9fa35a9dc6aa8119b`는
byte-identical하게 보존했다. 기존 manifest에는 canonical wire integer 최대
4096 decimal digits가 이미 있다. 이 후속 문서는 그 한도와 맞춘 **computed output
표현 범위 및 새 출력 거부 계약**을 명시한다. 기존 manifest나 이전 감사 판정을
재작성하지 않으며, 출력 계약의 구현 revision은 새 fix commit/source hash로 구분한다.

1. Ratio/Fraction을 exact gcd로 약분한 뒤 canonical numerator `n`, denominator `d`를 만든다.
2. 유효한 산술 결과의 denominator는 양수다. numerator 부호는 보존하며 zero는 `0/1`이다.
   wire에는 leading zero, `+` 부호, `-0`을 허용하지 않는다. minus 부호는 digit 수에 포함하지 않는다.
3. 분자와 분모는 **각각 최대 4096 decimal digits**다. `L=10**4096`으로 두고
   `abs(n) < L` 및 `0 < d < L`일 때만 decimal serialization을 진행한다.
   `L-1`은 허용하고 `L`, `L+1`은 거부한다. 분자에 대해서는 음수에도 같은 절댓값 경계를 적용한다.
4. 두 canonical integer의 exact 비교를 **둘 다 완료한 다음** `str(n)`, `str(d)`를 호출한다.
   비약분 내부 pair가 크더라도 약분 후 둘 다 범위에 들면 허용한다.
5. computed artifact의 raw integer도 같은 wire integer 한도를 적용한다.
6. 어떤 canonical output integer라도 초과하면 `compare_claim`은 비교 결과나 partial
   computed artifact를 반환하지 않고 아래 `LabRefusal`을 발생시킨다. 이 단계는 kernel의
   산술 거부를 담는 `capture()` 이후의 adapter 경계이므로 `compare.py`는 변경하지 않았다.

```yaml
exception: LabRefusal
code: CLAIM_OUTPUT_LIMIT
phase: claim_output
atom: ""
component: ""
message: canonical computed integer exceeds Claim V1 4096 decimal digits
scope: ARITHMETIC_ONLY
j_status: J_NOT_VERIFIED
```

의미: **정확한 산술 결과는 계산됐지만 LAB_C1B1_CLAIM wire가 표현할 수 있는 canonical
output 범위를 초과했다.** Arithmetic failure나 physical failure를 뜻하지 않는다.
Slow/Fast는 같은 adapter 경계와 immutable Failure 계약을 사용한다. 입력은 변경하지
않고 process-global integer-string limit도 변경하지 않는다. 직렬화 경계는 integer
비교로 검사하며, digit 판정을 위해 먼저 `str(value)`를 호출하지 않는다.

## 변경 범위와 실제 검증

기존 production 파일의 변경은
[claim_adapter.py](../independent_checker/c1b1/claim_adapter.py) 하나다.
`exact_slow.py`, `exact_fast.py`, `exact_geometry.py`, `compare.py`, `contracts.py`,
frozen manifest/sidecar와 기존 시험·benchmark·mutant 결과는 그대로다.

수정 전 원본 재현 소스를 byte-identical한 adapter에 실행한
[baseline-reproduction.json](../current/c1b1-claim-output-fix-2026-10-04/baseline-reproduction.json)은
두 경로의 일반 ValueError 누출을 실제로 확인했다. 그 REPRODUCED는 역사적 adapter FAIL의
재현 성공이다. 수정 전 새 경계 시험은 **25 failed / 15 passed**였고
[실패 로그](../current/c1b1-claim-output-fix-2026-10-04/red-boundary-tests.log)를 보존했다.

새 [경계 시험](../tests/test_c1b1_claim_output_boundary.py)과
[실제 source mutant 시험](../tests/test_c1b1_claim_output_mutant.py)은 다음을 검사한다.

- 원본 반례 `x=10**2150`, Grid(8,0), mass_i=(x+3)/1, dt=1/(x+1): exact displacement
  `1/((x+1)(x+3))`, denominator 정확히 4301자리, stored displacement/position 모두 0.
  Slow/Fast의 kernel은 계속 정확하고, adapter는 동일한 CLAIM_OUTPUT_LIMIT/claim_output을 발생시킨다.
- dict/JSON text/bytes 입력, 동일 Failure 전체, 입력 불변, scope/J 표시와 process limit 보존.
- canonical 분자·분모 각각 `L-1 / L / L+1`, 양수·음수 numerator, Ratio/Fraction,
  zero=0/1, 약분 전 크고 약분 후 작은 pair, raw integer 경계.
- Python 기본 limit보다 큰 5001자리 분자/분모도 decimal conversion 전 구조화된 거부.
- 실제 유효 Drift 입력으로 분자만 초과하는 경우와 분모만 초과하는 경우, 각각 ±dt,
  Slow/Fast의 동일 refusal. 정확히 4096자리 denominator의 successful output도 두 경로에서 허용.
- 실제 소스 사본의 `_check_output_integer` 방어를 제거하여 compile/import/실행.
  Baseline PASS를 먼저 요구하고, Slow/Fast 양쪽에서 mutant의 일반 ValueError 누출을 검출.

새 실행 기록은
[author-verification-receipt.json](../current/c1b1-claim-output-fix-2026-10-04/verification-v1/author-verification-receipt.json)에 있다.

| 새로 실행한 검사 | 결과 |
|---|---|
| F-CLAIM-1 exact reproduction | 두 kernel의 정확한 결과 + 두 adapter의 동일한 structured refusal |
| 기존 관련 suite | **105 passed**, failure/error/skip 0 |
| 새 output boundary + 새 mutant 시험 | **45 passed**, failure/error/skip 0 |
| 기존 실제 source mutants | **16 baseline PASS / 16 DETECTED**, 기존 edit/hash와 일치 |
| 새 F-CLAIM-1 실제 source mutant | **baseline PASS / mutant DETECTED**, Slow/Fast 각각 확인 |
| 저장소 전체 pytest | **393 passed**, failure/error/skip 0 |
| 감사된 산술 3파일 및 compare 등 | f806d8c Git blob과 raw bytes / SHA-256 동일 |

모든 실행은 이번 저자 검증이다. Independent re-audit나 certification을 뜻하지 않는다.
재실행은 역사 기록을 덮지 않는 새 evidence 디렉터리를 지정한다.

```powershell
python tools/verify_c1b1_claim_output_fix.py --out <NEW_DIRECTORY> --preservation-before current/c1b1-claim-output-fix-2026-10-04/preservation-before.json
```

## Byte 보존과 성능 회귀 기록

[preservation-before.json](../current/c1b1-claim-output-fix-2026-10-04/preservation-before.json)은
수정 전 1,944개 tracked file의 raw SHA-256과 수령 자료 7개의 raw hash를 고정한다.
최종 receipt는 그중 **1,943개 raw bytes 불변**, 변경 1개는 adapter임을 확인했다.
기존 base `e976fa0`의 **1,921개는 Git blob/mode/type와 raw bytes 모두 불변**이며 삭제도 없다.
기존 audit/sealed evidence, 과거 상태 문서, implementation report와 benchmark/mutant 자료를
덮지 않았다. 수령 원본과 저장소에 복사한 7개 자료도 byte-identical하게 확인했다.

| 감사된 산술 파일 | f806d8c 및 이번 수정의 동일한 SHA-256 |
|---|---|
| exact_slow.py | b36efc03abdcb760f294f009ea1aea8aafa6fcc05a53c7b3970291c90edf4c13 |
| exact_fast.py | 2190e099642b4bf440e4a2280b09d4b89984f637e6cee1b09dfa23411f0b4c0b |
| exact_geometry.py | b237cd00e45e2ed635bae54880cfef88c1126e98af57d74843b752d2ed27677e |

기존 산술 benchmark의 timed Drift/Kick/supplied-J paired kernel 호출에는 adapter가 없다.
그 source도 불변이며 기존 benchmark를 다시 실행하거나 성능 승격하지 않았다.
Adapter 비용은 별도
[claim-regression.json](../current/c1b1-claim-output-fix-2026-10-04/claim-regression.json)에만 기록했다.
한 개의 hand-authored synthetic Drift claim, revision/path별 400회 호출 × 9 raw wall samples,
교대 revision 순서의 작은 저자 회귀 측정이다. Import/startup은 측정에서 제외했고,
audited adapter와 fix adapter의 성공 결과는 동일했다.

| 작은 synthetic claim 전체 처리 | 이전 adapter wall median | 새 adapter wall median |
|---|---:|---:|
| exact_slow | 193.119 µs | 200.505 µs |
| exact_fast | 136.607 µs | 138.789 µs |

이는 JSON decode부터 computed_json까지의 작은 local claim 회귀 관측이다.
기존 kernel benchmark의 speedup, 장기 처리량, 다른 입력/하드웨어 또는 물리 검증으로 확대하지 않는다.

fast impulse, physical r_min binding, J verification, replay, trajectory, N-Step은
이번 수정 범위에 포함하지 않았다. **push는 수행하지 않으며 추가 사용자 승인이 필요하다.**
