# C1-B1 Arithmetic V1 — Post-Commit 현재 상태와 provenance

기록일: 2026-10-04 (Asia/Seoul). 범위: **ARITHMETIC_ONLY / J_NOT_VERIFIED**.
독립 impulse와 J physical verification은 구현되지 않았고, physical `r_min` binding은
PENDING, external executor compatibility는 NOT VERIFIED다. 정식 인증 상태는 **NotCertified**다.

```text
C1-B1 Arithmetic V1
IMPLEMENTED
AUTHOR CHECKS PASS
INDEPENDENT REVIEW PENDING
NotCertified
```

이 문서는 구현 commit 이후의 Git 상태와 감사 대상, 기존 기록과의 시간 관계를 기록한다.
새 수치 검증이나 독립 감사 판정을 발행하는 문서가 아니다. `AUTHOR CHECKS PASS`는
보존된 저자 실행 기록의 상태이며, 외부 독립 감사자는 별도로 재실행할 예정이다.

## 1. Git 상태와 고정 감사 대상

아래는 **이 문서 추가 직전** 실제 Git 조회로 확인한 snapshot이다.
실제 Git checkout은 `D:/numerical-audit-lab-recovered-2026-10-01`이며,
`D:/numerical-audit-lab`의 기존 비 Git 폴더와 구분한다.

```yaml
Implementation base: e976fa0fdeef16a27f112a0a4ee42494fe1e46b1
Implementation commit: f806d8ce1ef86a0948b1a8abafe1a22c3058178b
Branch: regular-2step-chain
HEAD: f806d8ce1ef86a0948b1a8abafe1a22c3058178b
Remote: origin/regular-2step-chain == f806d8ce1ef86a0948b1a8abafe1a22c3058178b
ahead/behind: 0/0
working tree: clean
Independent audit target: f806d8ce1ef86a0948b1a8abafe1a22c3058178b
```

`f806d8ce1ef86a0948b1a8abafe1a22c3058178b`의 parent는
`e976fa0fdeef16a27f112a0a4ee42494fe1e46b1`이다. 로컬 origin 추적 ref뿐 아니라
`git ls-remote --exit-code origin refs/heads/regular-2step-chain`으로 실제 원격 SHA도 확인했다.

이 문서 추가 후에는 문서 1개가 untracked 상태로 남으므로 working tree는 더 이상 clean이
아니다. 위 `clean`은 추가 직전 snapshot의 사실이다. 이번 문서 정리에서는 commit/push를
수행하지 않으며, HEAD와 독립 감사 대상 SHA는 그대로 유지한다.

독립 감사가 시작된 뒤 이 commit의 코드를 수정한 결과를 같은 감사 대상으로 취급하지
않는다. 수정이 필요하면 새 commit과 감사 대상 SHA를 지정하고, 기존 감사 결과와 구분한다.

## 2. 역사 기록과 현재 기록의 역할

| 자료 | 역할과 시점 |
|---|---|
| [기존 구현 보고서](C1B1_ARITHMETIC_V1_IMPLEMENTATION_REPORT_2026-10-04.md) | base HEAD에서 작성한 pre-commit implementation record. 당시 구현·저자 검증·계측과 미실시 작업의 역사 기록 |
| [implementation-preservation-v1.json](../../numerical-audit-lab-fast-arithmetic-preflight-2026-10-04/implementation-preservation-v1.json) | repository 밖의 pre-commit preservation receipt. 생성 당시 HEAD와 raw-byte 보존 검사 결과 |
| 이 문서 | post-commit current-status record. 구현 commit, 원격 일치, committed-tree preservation result와 감사 대상을 기록 |

Preservation receipt의 생성 시각은 `2026-10-04T02:40:14.861257+00:00`이며,
원본 경로는
`D:/numerical-audit-lab-fast-arithmetic-preflight-2026-10-04/implementation-preservation-v1.json`이다.
이 receipt와 실행 로그는 repository 밖 자료다. 위 링크는 현재 checkout의 형제 디렉터리를
가리키며, 다른 환경에서 재현하려면 해당 역사 자료를 별도로 전달해야 한다.

시간 순서는 다음과 같다.

1. **Preservation receipt 시점:** base HEAD는
   `e976fa0fdeef16a27f112a0a4ee42494fe1e46b1`이고 구현 파일은 아직 commit/push 전이었다.
   따라서 `commit_or_push_performed: false`는 생성 당시 사실이다.
2. **그 이후:** 동일 구현을 `f806d8ce1ef86a0948b1a8abafe1a22c3058178b`로 commit하고
   `regular-2step-chain`으로 push했다. 문서 추가 직전 HEAD와 origin이 일치하고,
   ahead/behind는 `0/0`, working tree는 clean이었다.

Receipt의 `commit_or_push_performed: false`와 기존 구현 보고서의
“Commit/push는 수행하지 않았다.”는 pre-commit 시점의 사실로 보존한다.
현재 상태에 맞춰 그 값을 `true`로 바꾸거나 기존 보고서를 사후 재작성하지 않는다.

## 3. Committed-tree preservation result

아래는 **committed-tree preservation result**다. Pre-commit receipt의 raw-byte 보존
검사와 별도로 base와 target의 `git ls-tree -r` path/blob 대응을 비교해 확인했다.

```yaml
base e976fa0 tracked files: 1921
target f806d8c tracked files: 1943
common: 1921
unchanged common Git blobs: 1921
changed existing: 0
deleted existing: 0
added: 22
```

공통 경로의 Git blob 1,921개가 모두 동일하며 mode/type 변경도 없다.
기존 source/test/audit/sealed evidence의 변경이나 삭제 없이 22개 파일을 추가한 commit이다.
이번에 추가한 현재 상태 문서는 target commit의 1,943개 파일 또는 위 22개에 포함되지 않는다.
이 보존 확인 자체는 산술 정확성, 독립 감사 또는 정식 인증 판정이 아니다.

## 4. C1-B1 Arithmetic V1 구성요소 상태

이 표의 범위는 C1-B1 Arithmetic V1만이다.

| Component | Status |
|---|---|
| semantic manifest | FROZEN FOR AUDIT TARGET |
| exact_slow | IMPLEMENTED / AUTHOR CHECKS PASS |
| exact_fast | IMPLEMENTED / EXPERIMENTAL / OPT-IN |
| exact_geometry | IMPLEMENTED / AUTHOR CHECKS PASS |
| claim adapter | ARITHMETIC_ONLY |
| J physical verification | NOT IMPLEMENTED |
| physical r_min binding | PENDING |
| external executor compatibility | NOT VERIFIED |
| independent audit | PENDING |
| formal certification | NotCertified |

감사 대상 [semantic manifest](../independent_checker/c1b1/semantic_manifest_v1.json)의
raw-byte SHA-256은
`3217fc38aa798fff3ffea8072cecafaecac9f98be85589e9fa35a9dc6aa8119b`이며
[SHA 기록](../independent_checker/c1b1/semantic_manifest_v1.sha256)에 고정돼 있다.
`FROZEN FOR AUDIT TARGET`은 위 commit의 사양 고정을 뜻하며 독립 감사 완료를 뜻하지 않는다.
기본 claim 계산 경로는 `exact_slow`, `exact_fast`는 **EXPERIMENTAL / OPT-IN**이다.

## 5. 보존된 저자 테스트 결과

```text
105 passed
RELATED SUITE ONLY
NOT REPOSITORY FULL
AUTHOR CHECKS PASS
INDEPENDENT REVIEW PENDING
```

출처는 기존 구현 보고서와 보존된
`D:/numerical-audit-lab-fast-arithmetic-preflight-2026-10-04/implementation-pytest-final-v1.txt`다.
로그에는 `105 passed in 3.34s`가 기록돼 있다. 새 전용 검증 98개와 기존
independence/provenance 검증 7개의 관련 suite 결과이며 repository 전체 실행 결과가 아니다.
이번 작업에서는 로그를 읽었으며 pytest를 새로 실행하지 않았다.

외부 독립 감사자의 별도 재실행과 판정은 PENDING이다. 저자 검증 상태를
`INDEPENDENT AUDIT PASS`로 합치거나 선반영하지 않는다.

## 6. 보존된 성능 기록과 적용 범위

출처: [기존 benchmark.json](c1b1-arithmetic-v1/benchmark.json)과 기존 구현 보고서.
이번 문서 정리에서는 benchmark를 재실행하지 않았다.

```text
ARITHMETIC_ONLY
synthetic 8-input workload
J_NOT_VERIFIED
```

| 기존 workload | 보존된 slow/fast wall 중앙값 비율 |
|---|---:|
| Drift | 5.85x |
| Kick | 6.08x |
| K-D-K + exact guards | 2.27x |

이 값은 시험용 mass/dt/threshold와 supplied J를 사용하는 8-input synthetic 산술 workload의
기존 관측이다. K-D-K는 exact segment/stored guards와 validation 비용을 포함하지만 독립
impulse는 포함하지 않는다. C1-B1 전체, full audit, world executor 또는 physical replay의
성능으로 확대 해석할 수 없다. 물리 binding이나 실제 sealed C1-B1 audit workload의
성능 근거도 아니다. 새 성능 주장, fast 기본 승격, fast impulse 작업은 이번 범위에 없다.

## 7. Regular 2-Step 및 N-Step과의 분리

[Regular 2-Step의 기존 외부 감사 반영 기록](../current/REGULAR_2STEP_INDEPENDENT_AUDIT_2026-10-04.md)은
그 범위에서 **IMPLEMENTED / CHECKER PASS / INDEPENDENT AUDIT PASS**다.
그 기존 외부 PASS는 C1-B1 Arithmetic V1의 감사 근거가 아니다. 이번 계산기의 상태는
**INDEPENDENT REVIEW PENDING**으로 유지하며 위 구성요소 표에 Regular 2-Step 상태를 섞지 않는다.
기존 Regular 2-Step evidence와 과거 상태 기록은 보존한다.

[Regular N-Step 설계](REGULAR_NSTEP_TEMPLATE_INDUCTION_DESIGN_2026-10-04.md)의 상태는
**PROPOSED / DESIGN ONLY / PROOF OBLIGATIONS OPEN**이다.
C1-B1 arithmetic fast path의 구현·감사와 N-Step induction은 별도 작업이다.
한쪽의 PASS를 다른 쪽의 진척이나 증명으로 기록하지 않는다.
