# Verified Driver V1 현재 상태 — 2026-10-06

**V1 전체는 미완료. 실제 persistent Gala live 인증·replay·controller-death와 외부 감사 PASS는 아직 없다.**

Task 1–7 단위·지정 회귀와 공격 검증은 완료했다. Task 8 실제 Gala N=3/N=4·replay·비용·최종 fresh review는 시작하지 않았다. Task 8 allowance 400초는 잔여 예산에 들어가지 않아 실행을 차단했다.

설계자의 namespace 판정에 따라 V1 live-chain 11파일을 `verified_driver/v1/live_chain/`으로 옮겼다. V1 import·GDB/harness·worker 경로·source pinning·root depth만 위치에 맞췄다. V0 gate, approved 89-file pinset, 보호 소스와 기존 수치 계약은 그대로다.

합친 V0+V1 제품과 source-identical한 native 트리에서 순서대로 실행한 결과: 기존 실패 10개 **10 PASS**, V0 전체 **83 PASS**, V1 Task 1–5 **100 PASS**, Runtime Trace 선택 **40 PASS**, 과거와 같은 합동 집합 **183 PASS / 0 FAIL**. 별도 V0 기준선 결과로 대체하지 않았다. Task 5를 완료 처리했다.

기존 173 PASS / 10 FAIL, 모든 RED/GREEN/충돌 자료와 Task 4 N=3 TEST_ONLY fixture는 pre-compatibility historical evidence로 보존했다. 새 PASS를 과거 실행에 소급 적용하지 않았다. 이전 현재 상태 문서도 `verified_driver/v1/artifacts/namespace-compatibility/pre-compatibility-status.md`에 보존했다.

Task 6에서는 승인된 좁은 저장소 확장을 구현했다. replay 중 historical Sk object/receipt/CURRENT와 generation은 변하지 않는다. complete replay 뒤 immutable `VERIFIED_REPLAY_TRANSITION_V1`에 자체 완결적 proof/report/source/fresh anchor를 담는다. attachment 자체에 publication/resume 권한은 없으며, 첫 Sk+1 receipt만 그 ID를 포함한다. historical predecessor는 유지하고 이후 same-session/process 규칙으로 돌아간다. recovery도 attachment를 재검증하고 FINAL_TERMINAL은 후속 body/generation을 만들지 않는다.

watchdog supervisor를 실제 session launcher에 연결했다. controller SIGKILL을 사용하는 paused/active **marker subprocess** 시험에서 group 종료·descendant 수거·next-body marker 부재를 확인했다. 실제 Gala 차단 증거는 아직 없다.

설계자의 Task 6 필수 13항목 및 기존 회귀를 포함한 최종 실행은 **264 PASS / 0 FAIL / 0 ERROR / 0 SKIP**이다. V0 83 + 기존 V1 100 + Task 6 41 + Runtime Trace 40이며, guarded wall **68.55732029500001초**다. 초기 30초 resource refusal과 수정 전 실패도 보존했다.

최종 보호 inventory **7,232개 변경 0**, pre-compatibility V1 역사 **152개 변경 0**. 승인 runtime 89-file map은 동일하고 V1 source snapshot 40개에 이동된 11파일 및 supervisor/replay/containment가 포함됐다. mutable 제외는 기존 공유 budget 두 파일뿐이다.

Task 6 제출 당시 공유 ledger는 **3353.251577895021 / 3600초**, 잔여 **246.748422104979초**였으며, 그 제출의 guarded 단위/회귀 증가분은 **239.3700420769992초**였다. 이 과거 수치는 Task 6 증거에 그대로 보존한다.

저장소 ordering·replay equality·marker containment는 구현 및 회귀 확인 범위다. 실제 같은 Gala의 S1→S2→S3 인증, N=4 실패 위치, 실제 controller-death/replay와 per-barrier 수치 비용은 미검증이다. init-return→step1-entry와 terminal frontier 이후 wrapper tail의 **UNTRACED**, 기존 root/GDB/OS trust 가정은 유지한다. 전칭·형식·물리적 정확성이나 외부 감사 완료를 주장하지 않는다.

worktree `C:\Users\zun24\.codex\worktrees\runtime-nstep\numerical-audit-lab-recovered-2026-10-01`, branch `codex/runtime-trace`, HEAD `fbbb90171c43ed5462e9584c2621cb0b86b80bd4`. `git diff --check` exit 0. staging·commit·push 없음.

상세 보고: `verified_driver/v1/artifacts/namespace-compatibility/report.md`, `verified_driver/v1/artifacts/task6-report.md`. 최종 제출: `task6-final-inventory.json`, `task6-source-pinset.json`, `task6-git-status.txt`, `task6-done-junit.xml` 및 `jobs/task6-done/`.

Task 7 신규 공격 **54 PASS**: positive/retry와 replay-only publication trap 2개 PASS, 부정 공격은 **20 REFUSED + 32 STOP**. state/receipt 변조, q/full_v/latent, Form coefficient/box/reset, t/dt/gradient, 토큰·barrier, 조기 resume, prefix/source 변경, checker/resource 실패, 정확한 CURRENT crash, replay hidden state/인증 주장/저장 증거 변조를 검사했다. marker와 저장된 TEST_ONLY 증거의 범위이며 실제 Gala 실행 증거로 승격하지 않는다.

초기 **51 PASS / 3 FAIL**은 공격 토큰 생성자가 잘못된 generation/sequence를 거부하는 지점을 새 테스트가 예상 거부 범위 밖에 둔 오류였다. RED 코드·JUnit·stdout을 보존하고 테스트만 최소 수정했다. 별도 제출 inventory 도구의 file-byte SHA와 재직렬화 content ID 혼동도 원인과 수정 전 소스를 보존했다. 제품 19개 Python 파일 및 V1 40-file source pinset은 Task 6와 동일하다. 계약 확장·제품 수정·새 아키텍처 충돌 없음.

최종 같은 합친 제품의 지정 회귀: **318 PASS / 0 FAIL / 0 ERROR / 0 SKIP** = V0 83 + V1/live-chain Tasks 1–7 195 + Runtime Trace 선택 40. guarded wall **85.819888322초**. Task 7의 모든 RED/GREEN/final 추가 guarded wall은 **119.499047652초**다.

보호 **7,232개 변경 0**, pre-Task7 V1 역사 **287개 변경 0**, pre-compatibility 역사 **152개 변경 0**. V0 89-file pinset 파일 SHA는 `c949e61b420696f9ecfc61608d8e0e13be5f12a965e1e103f40ea2941689ddb3`. V1 pinset **40개**, binding SHA `1b8c9d97907b2308b079aefdb6b40c6263b741c3b8c6d4cd136c6b0451e160c5`, 이동된 11파일 모두 포함. Task 4 fixture와 과거 실패/회귀/receipt 변경 없음.

현재 공유 ledger **3472.7506255470207 / 3600초**, Task 8 잔여 **127.24937445297928초**. 기존 allowance hard caps 280초와 final regression 120초 합계 **400초**에 **272.7506255470207초 부족**하다. 이 cap은 예상 완료 시간이나 측정 Gala 비용이 아니다. review 수정·재실행 reserve도 별도이며 이 400초에는 없다. 새 ledger·증액 없이 `STOP_ALLOWANCE_INSUFFICIENT`; Task 8 실행 전 설계자의 예산 판단이 필요하다.

Task 7 제출: `verified_driver/v1/artifacts/task7/report.md`, `final-inventory.json`, `source-pinset.json`, `task7-all-final-attack-results.json`, `task7-all-final-junit.xml`, `task8-allowance.json`, `git-status.txt`, `git-verification.json`. Task 7은 내부 공격/회귀 확인이며 외부 감사 PASS나 실제 Gala 인증은 아니다. staging·commit·push 없음.
