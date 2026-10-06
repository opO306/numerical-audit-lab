# Task 6 — replay 전환과 프로세스 차단, 2026-10-06

**단위·지정 회귀 구현 완료. 실제 Gala live/replay 검증, Task 7/8, 최종 fresh review와 외부 감사는 미완료다.**

설계자가 승인한 좁은 V1 저장소 계약 확장만 적용했다. V0 소스·승인 pinset·Runtime Trace batch 계약은 변경하지 않았다.

replay는 historical Sk의 object/receipt/CURRENT를 수정하지 않고 새 프로세스의 경계를 비교한다. q/full_v/latent, 여섯 Form의 역할·offset·center·coefficients·box, basis 계약, gradient, t/dt, source, step/scope와 역사 계보 위치가 같아야 한다. process/session/acquisition 및 prefix provenance의 차이는 semantic 비교 안에서만 허용한다. nonzero cross-process basis는 현재 지원 범위 밖이라 REFUSE한다.

replay 중에는 certified generation/object/acceptance receipt를 만들지 않는다. 중간 replay token은 검증된 CURRENT의 역사 ancestor와 fresh checkpoint/observation에 묶이며, 일반 LIVE token 발행과 구별된다. 기존 private session/barrier/checkpoint/generation binding과 단일 사용 조건은 유지한다.

complete replay 이후에만 content-addressed `VERIFIED_REPLAY_TRANSITION_V1` attachment를 생성한다. attachment는 genesis와 전체 historical chain, 각 fresh checker report 원문과 report/checkpoint/completion 해시, 전체 source snapshot, exact fresh Sk anchor를 자체 완결적으로 담는다. mutable 외부 로그 경로의 존재에 authority 검증을 의존하지 않는다. attachment 자체에는 publication/resume 권한이 없다.

첫 fresh Sk+1 acceptance receipt만 `replay_transition_id`를 포함한다. Sk+1.predecessor_id는 historical Sk를 유지한다. 저장소는 historical Sk→fresh Sk semantic equality 다음에 fresh Sk→Sk+1의 same-session/process 및 increasing-prefix/frontier 규칙을 검사한다. 다음 링크는 기존 정상 규칙으로 돌아간다. recovery도 receipt→transition ID→canonical immutable attachment→전체 역사와 replay proof를 다시 검사한다. FINAL_TERMINAL에는 전환을 허용하지 않는다.

watchdog supervisor는 controller pipe EOF에 대상 GDB/inferior process group을 SIGKILL하고 subreaper로 descendants까지 수거한다. 실제 session launcher/terminate 경로에 연결했다. paused/active controller SIGKILL 시험은 **실제 subprocess를 사용하는 TEST_ONLY marker 시험**이다. 실제 Gala controller-death 보장은 Task 8 미검증 범위다.

설계자의 13개 필수 항목을 확인했다: (1) replay store byte inventory 동일, (2) 첫 publication object 한 개 증가와 idempotent retry, (3) equal q/v의 latent/Form/t-dt/source/step 변조 거부, (4) report와 attachment 해시를 수리한 semantic 변조 거부, (5) 다른 historical parent 거부, (6) 다른 fresh session/process 거부, (7) second child 재사용 거부, (8) attachment 없는 cross-session 거부, (9) fresh prefix/frontier 비증가 거부, (10) terminal replay store 동일 및 successor/transition 거부, (11) pre-CURRENT S2 유지, (12) post-CURRENT S3 복구 및 attachment 변경 시 recovery 거부, (13) Tasks 1–6 + V0 통합 PASS.

RED/GREEN 기록은 모두 보존했다. 최초 managed transition RED는 30초 cap으로 `REFUSED_RESOURCE`였고 30.104070051초를 공유 ledger에 가산했다. native mirror RED는 미구현 API로 21 FAIL. 첫 GREEN은 nested ChainState serialization 오류로 18 FAIL / 20 PASS; 각 상태의 canonical 변환으로 수정했다. 다음 GREEN은 38 PASS / launcher 연결 누락 1 FAIL; 실제 containment 연결 후 core/session/controller 62 PASS였다.

최종 source-identical combined regression은 **264 PASS / 0 FAIL / 0 ERROR / 0 SKIP**, guarded wall **68.55732029500001초**다. 구성은 V0 83 + 기존 V1 100 + Task 6 41 + Runtime Trace 선택 40. `jobs/task6-done/`와 `task6-done-junit.xml`에 command/stdout/resource/storage/JUnit을 보존했다.

작성자의 내부 코드 검토이며 fresh review나 외부 독립 감사가 아니다. 실제 fresh Gala N=3/N=4·replay·controller-death, 수치 실행 대비 비용 비교와 최종 branch review는 남아 있다. UNTRACED/root/GDB/OS trust 가정도 유지한다.

최종 보호 inventory 7,232개 변경 0; pre-compatibility V1 역사 152개 변경 0. original runtime universe는 승인 89-file map과 같다. 현재 V1 pinset 40개에 이동된 11파일과 supervisor/replay/containment가 포함됐다. 기존 Task 4 fixture는 계속 TEST_ONLY 역사 자료이고 새 PASS를 소급 적용하지 않는다.

공유 ledger **3353.251577895021 / 3600초**, 잔여 **246.748422104979초**. 이번 guarded 증가분은 호환 116.51462793499968초 + Task 6 단위/회귀 122.85541414199952초 = 239.3700420769992초다. 개발·동기화·read-only hashing은 기존 ledger 의미대로 별도다. 새 ledger·증액·heavy Gala 실행은 없다. Task 8 직전에 hard caps와 잔여량을 다시 비교해야 한다.

`git diff --check` exit 0; HEAD `fbbb90171c43ed5462e9584c2621cb0b86b80bd4` 유지. staging/commit/push 없음. 제출: `task6-final-inventory.json`, `task6-source-pinset.json`, `task6-git-status.txt`, `preservation/task6-final.json`.
