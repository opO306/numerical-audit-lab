# Regular 2-Step Chain 상태 — 2026-10-03

## 먼저 남아 있는 한계

이 결과는 frozen Gala 1.12.0, 한 regular 입력, 현재 두 native process acquisition에만
해당한다. 새 2-step chain은 외부 독립 감사를 받지 않았고, concrete native carry의
symbolic coefficient는 0이며 box만 0이 아니다. 별도 unit test가 nonzero coefficient
Form의 ADD/SUB/MUL을 비교했지만 실제 caller carry에서 nonzero coefficient를 관측한
증거는 아니다. init return에서 step1 entry까지의 기존 untraced gap도 그대로다.

3-step, 일반 N-step, trajectory correctness, 누적 오차, shadowing, observable/physical
accuracy, cross-machine 또는 ASLR 다양성은 주장하지 않는다. 현재 새 production Python이
2,813 physical lines에 달해 사용자가 지정한 수천 줄 scaling trigger를 충족한다. 따라서
이 2-step 전달 뒤 3-step으로 바로 확장하지 않고 regular transition template/induction
설계를 별도 문제로 검토해야 한다. 이것은 확장 불가능성의 수학적 증명이 아니다.

## 현재 판정

```text
Regular 2-Step Chain

IMPLEMENTED
CHECKER PASS
INDEPENDENT AUDIT PENDING
```

Authoritative native evidence는 `runtime_trace/regular_2step/artifacts/known-03`과
`fresh-03`이다. 두 case 모두 서로 다른 실제 process acquisition이며 각각 1,428개 raw
instruction row, 정상 process 종료, 구조 재사용 proof, 새 step2 Numeric IR, frozen V2
correspondence, endpoint 및 `REGULAR_2STEP_CHAIN_V1` composition artifact를 가진다.
known completion은 `f44d2edfca32d6b7fc14429a818a16995da9f6e5e869cfdf22e5da2872e91401`,
fresh completion은 `bcf9b24f5e62394a74508b97f2881d9b4d172e7f9a23e700cefc0cd2bb78429b`다.

새 checker는 actual raw graph와 storage/dynamic identity, full PT_LOAD module operand,
관측된 세 CONTROL memory form의 EA, exact-rational IEEE-754, 독립 Form propagation,
state/boundary 및 상위 composition join을 검사한다. 저장된 15개 repaired semantic mutation은
모두 SEMANTIC에서 REFUSED됐고 별도 HASH/TRUST control도 각각 해당 단계에서 REFUSED됐다.

최종 회귀 실행은 frozen Python 3.12.3과 `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`로 수행했다.

- 새 regular 2-step: 63 passed in 165.06s
- 기존 Caller: 101 passed in 60.61s
- 기존 regular: 479 passed in 203.81s
- 합계: 643 passed, JUnit failure/error/skip 0, 세 명령 모두 exit 0

명시적 mutation replay는 별도 exclusive tree에서 exit 0으로 실행했다. 원본과 재생본의
273개 공통 파일 중 256개는 byte-identical이고, 17개 `repair.json`은 실제 실행 경로를
기록하는 `/test_pins/capture_directory`만 달랐다. 모든 substantive input/result/repair hash,
산술, dynamic ID, bits, verdict/stage 및 manifest는 동일하다. 원본 `copy_receipt.json`은
과거 authoritative copy provenance로 보존하며 replay가 재작성하지 않았다.

기준 HEAD `43f1e9b21a014520facb5a545846d648eb67b288`의 1,488개 tracked raw-byte/Git-blob
map을 다시 확인했다. 허용된 `.gitattributes` evidence metadata delta를 제외한 1,487개가
모두 동일했고, frozen wheel, leapfrog module, `lab/v2_bound.py` hash도 일치했다.

## 기존 외부 감사 상태

다음 기존 범위의 `CLOSED / PASS`는 원 scope에서 그대로 유지한다.

- Runtime Trace → Numeric IR regular init + 1-step
- Numeric IR → frozen V2 regular init + 1-step
- Caller Transition / Error-Continuity Gate

Caller 외부 감사 원본은 `current/caller-external-audit-2026-10-03/`에 byte-preserved로
있다. ZIP SHA-256은 `534dce362247406e5798e88a5edd97b5864898d25d19127c58748f88a15854de`,
report SHA-256은 `b63f721c897e275c41d8bed2597025b9bb1d9846318e03a7c452e4b1add6d946`다.
그 PASS를 새 process의 caller instantiation이나 새 2-step chain의 외부 감사로 확대하지 않는다.

## 전달 lifecycle

최종 ZIP helper는 구현됐지만 아직 실행하지 않았다. 별도 Task 3 review와 whole-branch review가
끝난 깨끗한 HEAD에서만 exclusive destination에 실행한다. 그 실행은 exact HEAD snapshot,
`git bundle --all`, bare clone/fsck/ancestry, ZIP member SHA/size, 그리고 원 checkout 및
captured absolute module path 접근을 거부한 relocated known/fresh public checker를 검증한다.
Push는 사용자에게 승인됐지만 이 상태 문서 seal 시점에는 아직 실행하지 않았다. Controller가
최종 package 검증 후 실제 push와 remote ref 검증 영수증을 ZIP 밖에 남긴다.
