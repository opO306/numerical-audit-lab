# Verified Driver V1 진행 및 차단 보고 — 2026-10-06

**INCOMPLETE / Task 5 회귀 계약 확인 대기. V1 완료·live 인증·외부 감사 PASS가 아니다.**

승인된 설계와 구현 계획을 모두 전체 읽고 Task 1→4를 RED→GREEN 순서로 수행했다. Task 5 controller/gate 구현 및 단독 시험은 통과했지만, 지정된 통합 회귀가 실패하여 Task 5를 완료로 기록하지 않았다. Task 6→8은 시작하지 않았다. 최종 persistent Gala 증거, replay, controller-death containment, fresh review는 아직 없다.

| 확인 항목 | 현재 확인된 사실 |
|---|---|
| 같은 원본 Gala 프로세스의 연속 인증 | 구현 후보는 있으나 실제 persistent live 실행은 아직 미검증 |
| S1→S2→S3 상태·Form 연결 | TEST_ONLY N=3 edge fixture에서 producer/독립 checker 통과. live pause/resume 증거가 아니다 |
| CURRENT 이전/이후 실패 순서 | 저장소와 marker controller 시험 통과. 실제 Gala crash 실험은 미수행 |
| controller 사망 시 차단 | Task 6 containment 미구현, 실제 실험 미수행 |
| genesis replay / FINAL_TERMINAL replay | Task 6 미구현·미검증 |
| 완성 여부 | 미완료. Task 5의 V0 회귀 환경 판정을 설계자에게 확인 요청 |

## 차단 원인과 요청한 결정

보호된 `verified_driver/v0/gate.py`는 `runtime_trace/`의 **전체 .py 목록과 바이트**를 기존 승인 pinset과 비교한다. 승인 pinset은 89개이며 SHA-256은 `c949e61b420696f9ecfc61608d8e0e13be5f12a965e1e103f40ea2941689ddb3`이다.

V1 설계가 지정한 `runtime_trace/live_chain/`에 11개 파일을 추가하여 현재 목록은 100개가 되었다. 기존 승인 파일의 변경·삭제는 0개다. V0 gate는 이 확장된 목록을 승인하지 않으므로, 기존 V0 positive 시험 10개가 source binding에서 거부된다. 이를 통과시키려고 V0 gate·pinset·과거 증거를 변경하지 않았다.

설계자에게 다음 중 검증 계약을 확인하도록 요청했다.

1. 현재 V1 트리 회귀와, 원본 바이트가 동일한 별도 V0 기준선 트리의 전체 V0 회귀를 분리 실행하고, 합친 트리의 거부도 그대로 보고한다.
2. 합친 트리의 V0 PASS도 필수라면, 최소 호환 변경안을 먼저 설계 보고하고 승인 후 적용한다.

확인 전에는 분리 회귀를 전체 통합 PASS로 간주하거나 V0 조건을 완화하지 않는다. 증거: `verified_driver/v1/artifacts/task5-compatibility-conflict.json`.

## 시험 및 증거

| 작업 | 실제 결과 | receipt / 로그 |
|---|---|---|
| Task 1 | model/store + V0 store 회귀 56 PASS | `artifacts/jobs/task1-done/` |
| Task 2 | protocol/checkpoint 19 PASS | `artifacts/jobs/task2-done/` |
| Task 3 | marker session + 기존 acquisition 회귀 12 PASS | `artifacts/jobs/task3-done/` |
| Task 4 | 새 edge + 기존 pipeline/raw 회귀 35 PASS, 68.924391709초 | `artifacts/jobs/task4-done/` |
| Task 5 단독 | marker controller/gate 13 PASS, 1.373360537초 | `artifacts/jobs/task5-green/` |
| Task 5 통합 | 173 PASS / 10 FAIL, 31.319499484초 | `artifacts/jobs/task5-done/` |

위 로그 경로의 접두사는 모두 `verified_driver/v1/`이다. 실패한 RED와 중간 GREEN도 `artifacts/jobs/`에 보존했다. Task 4에서는 빈 optional vector map/JSON tuple 표현 차이를 정규화하고, 서로 다른 프로세스 구조 비교에 이미 검토된 module 해시/RVA 기준 비교를 사용했다. 같은 live 세션의 단계·prefix·상태 검사는 엄격히 유지했다. 건수/histogram을 바꾸고 checkpoint 및 derived 해시까지 다시 맞춘 변조가 통과하는 RED를 확인한 뒤 두 counter의 의미 검사를 함께 추가했다.

Task 4 fixture는 새 원본 batch N=3 실행으로 얻었다. 과거 감사된 N=3 자산이 아니다.

- 경로: `verified_driver/v1/artifacts/fixtures/n3/capture/`
- acquisition ID: `16d9870ef3d16b5824e55c096c6ffa26c036735918e773a1b23321f10d6c9799`
- CAPTURED, 3090 records, init/step1/step2/step3/terminal3, GDB return code 0
- 측정 wall time: **10.515922052초**
- receipt: `verified_driver/v1/artifacts/jobs/task4-fixture-n3/execution.json`
- 역할: **TEST_ONLY**, 인접 `FIXTURE_ONLY.json` 및 각 checkpoint metadata에 명시

fixture의 PASS는 persistent live session, resume-after-CURRENT, controller containment를 증명하지 않는다. Task 8에서는 별도의 fresh live N=3/N=4 증거가 필요하다.

## 자원 및 보존

공유 ledger를 새로 만들거나 초기화하지 않았다. 현재 `runtime_trace/regular_nstep/artifacts/budget.json`의 누계는 **3113.881535818022 / 3600초**, 잔여는 **486.118464181978초**다. 시작 누계 대비 **177.19444222초**를 추가 사용했으며 fixture 획득과 RED/GREEN/회귀가 포함된다. 이는 guarded 실행 시간이며, 개발·복사·preflight 시간을 포함한 총 작업 시간이나 Gala 대비 속도 비율이 아니다.

기존 제한은 프로세스 트리 cgroup 메모리 4 GiB, swap 0, 전체 증거 저장 8 GiB, 개별 실행 최대 600초다. 새 V1 workflow는 기존 ledger를 읽기 전 lock을 잡고 실제 Windows 파일 크기를 합산한다. 초기 preflight 중복으로 누락된 0.483317105초 receipt는 같은 ledger에 정확히 가산해 조정했고 해당 receipt와 경위를 보존했다. Task 8 실행 allowance는 실제 실행 직전에 다시 계산해야 한다. 수치 실행·수집·검사 비용 비교와 replay 비용은 아직 측정되지 않았다.

보호 inventory **7,232개를 재해시해 변경 0개**를 확인했다. 검사 보고서는 `verified_driver/v1/artifacts/preservation/task5-conflict-recheck.json`이다. 명시된 mutable 제외는 기존 `budget.json`, `budget.running.json`뿐이다. 원래 작업 트리의 Impulse/A/다른 미커밋 작업을 수정하지 않았다.

source 및 회귀 입력 처리 자동화는 구현자가 작성했다. marker 단위 시험의 숫자는 TEST_ONLY literal이며 실제 수치 증거로 채택하지 않는다. 사람이 Gala 계산식을 베껴 구현한 대체 solver는 없다. 이번 작업의 실제 수치 실행은 위 fixture batch 획득 하나이며, live V1 실행은 아직 없다.

## Git 및 미완료 항목

실제 managed worktree는 `C:\Users\zun24\.codex\worktrees\runtime-nstep\numerical-audit-lab-recovered-2026-10-01`, branch는 `codex/runtime-trace`, HEAD는 `fbbb90171c43ed5462e9584c2621cb0b86b80bd4`다. 설계 기준 eada258 이후 HEAD 차이는 설계 문서 추가이며 기존 승인 working 문서 변경은 보존했다.

staging/commit/push는 **수행하지 않았다**. 새 소스는 untracked이며 승인 전 index를 변경하지 않는다. Git status, tracked diff 및 untracked source diff는 `verified_driver/v1/artifacts/task5-git/`에 별도로 제출한다.

Task 6 replay/containment, Task 7 추가 공격 및 회귀, Task 8 실제 N=3/N=4·controller-death·replay·비용·최종 fresh review가 남아 있다. 기존 `init-return → step1-entry`와 terminal frontier 이후 wrapper tail의 **UNTRACED** 구간은 유지된다. frozen V2/독립 수치 checker 사용은 전칭·형식·물리적 정확성 증명이나 외부 독립 감사 완료를 뜻하지 않는다.
