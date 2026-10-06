# Verified Driver V1 Task 8 최종 증거 제출

V1 완료 판정은 설계자의 검토를 기다린다. 승인된 Task8의 실제 Gala 실행, 구현 결함 수정, 정확한 최종 소스 회귀와 fresh 내부 검토 증거를 제출한다. 외부 감사와 전칭·형식·물리적 인증은 수행하지 않았다.

최종 지정 합동 회귀: **330 PASS / 0 FAIL / 0 ERROR / 0 SKIP** = V0 83 + V1/live-chain Tasks1–8 207 + Runtime Trace 선택40. 최종 guarded wall **92.740996091초**, 원래 cap120초 유지. `task8-final02-junit.xml`, `jobs/task8-final02/` 참조.

실제 실행 결과는 다음과 같다. 각 디렉터리의 SUMMARY, source-pinset, raw trace, checkpoint, worker report, store object/acceptance, containment receipt와 export hash manifest가 근거다. 캡은 실행 상한이며 측정 wall은 독립 guard가 기록한 값이다.

| 실행 | 실제 결과 | Guarded wall / cap (초) | 최종 증거 |
|---|---|---:|---|
| ordinary | PASS — 원래 Gala N=3 public q/v 대조 | 2.639127697 / 10 | [ordinary-02](ordinary-02/SUMMARY.json) |
| positive | PASS — 한 Gala PID의 S0 → S1 → S2 → S3 FINAL_TERMINAL; CURRENT 이후 resume, 다음 body 차단 관측 | 15.314360003 / 55 | [positive-03](positive-03/SUMMARY.json) |
| negative | PASS — 실제 S1/S2 인증 뒤 세 번째 Form 후보를 의도적으로 거부; CURRENT=S2, body4 없음, session STOP | 14.388732199 / 60 | [negative-02](negative-02/SUMMARY.json) |
| nonterminal | PASS — 실제 genesis→S2 replay 중 object/receipt/CURRENT 불변; 첫 S3 receipt만 transition ID, S4는 정상 연결 | 19.973404732 / 45 | [nonterminal-02](nonterminal-02/SUMMARY.json) |
| terminal | PASS — 실제 FINAL_TERMINAL replay; 기존 S3 유지, generation/receipt/attachment 증가 없음, body4 없음 | 13.581250737 / 55 | [terminal-02](terminal-02/SUMMARY.json) |
| paused-death | PASS — 실제 paused Gala에서 controller 종료; GDB와 별도 PGID inferior 모두 종료·수거, CURRENT=S0, body2 없음 | 5.564969602 / 15 | [paused-death-02](paused-death-02/SUMMARY.json) |
| active-death | PASS — 실제 Gala step1 native instruction trace 확인 뒤 controller 종료; 전체 자식 종료·수거, CURRENT=S0, body2 없음 | 3.901518536 / 15 | [active-death-02](active-death-02/SUMMARY.json) |
| interruption | PASS — 실제 CURRENT=S1 직후 exit75; acceptance/checkpoint와 독립 edge 재검증으로 S1 복구, 임의 resume 거부, body2 없음 | 8.397768554 / 25 | [interruption-02](interruption-02/SUMMARY.json) |

N=3의 실제 단일 inferior PID는422다. S1과 S2 atomic CURRENT publication 관측 시 GDB의 pause가 증명되고 다음 body marker는 없다. publication monotonic time은 동일 CURRENT를 가리키는 resume 관측보다 앞선다. body2/3 marker의 predecessor ID도 각각 S1/S2와 일치한다. S3는 FINAL_TERMINAL이며 body4는 없다. 원래 대조 실행의 public q/v와 네 binary64 bit pattern이 모두 같다.

N=4 negative는 actual checkpoint/raw를 그대로 두고 세 번째 derived candidate의 Form box를 변경한 뒤 edge/completion 외부 hash를 수리했다. 별도 checker가 SEMANTIC에서 거부한다. 내보낸 negative-02 store는 S2 snapshot을 그대로 보존하고, 이후 nonterminal replay의 새로운 S3/S4와 immutable attachment는 nonterminal-02/result-store에 따로 보존한다. replay proof1/2 시점마다 historical store의 모든 바이트가 그대로임을 확인했다.

최종 paused receipt는 GDB797와 별도 PGID의 Gala807, active receipt는 GDB829와 Gala839를 모두 기록한다. 두 receipt 모두 descendant_remaining_pids=[] 및 owned_subtree_verified=true이고, 실제 inferior /proc 항목이 없다. active 시험은 barrier metadata가 생성되기 전 실제 Gala leapfrog native step1 instruction의 complete raw row(seq191)를 보존했다. body2는 시작되지 않았다.

fresh 검토의 구현 결함 네 건을 RED로 보존한 뒤 최소 수정했다. 첫 검토의 prefix mutation 이후 resume, S0 replay-only의 LIVE dispatch, logical Form source ID 누락은 controller/replay만 수정했다. 이어 첫 actual sequence와 328-case 회귀 뒤 최종 검토에서 별도 PGID inferior가 supervisor 종료 판정 밖에 있는 문제를 발견했다. 실제 두 inferior가 죽은 관측만으로 제품의 전체 자식 종료 계약을 충족한다고 판단하지 않았다.

별도 group 자식을 생성하는 로컬 TEST_ONLY fixture는 paused/active 모두 2 FAIL을 재현했다. supervisor는 dedicated subreaper의 전체 자식·adopted subtree를 추적하고 start time과 pidfd로 PID 재사용을 구별한다. 전체 자식을 정지시킨 뒤 종료·수거하고, 새 adopted 자식과 모든 추적 identity 부재를 확인한다. launcher도 verified subtree receipt를 요구한다. focused51 PASS 후 globally bound source가 바뀌었으므로 actual8단계와 전체330회귀를 모두 재취득했다. 최종 fresh reviewer는 APPROVE이다. 수정은 승인된 계약의 구현 결함 해결이며 수치·replay-transition·source/token/session/barrier 계약을 넓히지 않았다.

`review-fixes.md`, `final-review-01.json`, `containment-fix.md`, `final-review-02.json` 및 RED/GREEN JUnit/stdout/source snapshots를 보존했다. reviewer는 별도 agent로 소스·저장된 증거·hash/JUnit을 읽었고 numerical checker나 실제 실행을 독립 재실행하지 않았다. 이는 fresh 내부 검토이며 외부 감사가 아니다.

최초 positive-01은 writer allocation512MiB에 원래 trace reserve512MiB와 사전 receipt6530bytes가 함께 들어가지 않아 S0에서 resource refusal했다. 그 실패는 그대로 보존했다. writer allocation만1GiB로 잡고 trace cap512MiB, storage8GiB, memory4GiB와 per-job wall cap은 유지해 positive-02를 취득했다. 이후 final review 수정으로 positive-03을 취득했다. 이전 Task8 PASS는 이전 binding의 historical evidence로 남기며 최종 소스 PASS로 소급하지 않는다.

최종 V1 source pinset **40개**, SHA256 `f75980706aefbbd68cddce09549695c2f633905e01185f92f96660db81a9e2cd`. 이동된 live-chain11/11 및 supervisor가 모두 포함됐다. source-identical 합친 native mirror는 **188파일**이며 V0-only baseline으로 회귀를 대체하지 않았다. Task7 대비 제품 변경은 verified_driver/v1/containment.py, verified_driver/v1/controller.py, verified_driver/v1/live_chain/supervisor.py, verified_driver/v1/replay.py 네 파일이다.

보호 inventory **7,232개 변경0**, pre-Task8 역사 **340개 변경0**, pre-Task7 **287개 변경0**, pre-compatibility **152개 변경0**. V0 승인89파일 map/원본 file SHA `c949e61b420696f9ecfc61608d8e0e13be5f12a965e1e103f40ea2941689ddb3` 유지. V0 gate와 source binding 의미, 기존 Runtime Trace/regular_nstep 소스·계약, V0 receipt/acceptance와 Task4 TEST_ONLY fixture를 변경하지 않았다. export된 최종 실제 증거 336파일 hash를 재검사했다.

기존 ledger의 모든 과거 job 기록과 사용량을 보존하고 승인된 ceiling만3600→4200초로 증액했다. Task8 추가 guarded wall **499.539212663초**, 현재 누적 **3972.2898382100198/4200초**, 잔여 **227.71016178998025초**. 실패·검토 수정으로 필요한 RED/GREEN/전체 회귀/actual재실행을 모두 같은 ledger에 반영했다. 원인·대상은 reruns.md에, 각 정확한 wall은 아래 표와 기존 ledger/jobs에 있다. 신규 ledger나 10/100-step·성능·멀티코어·신경망·진화 실험은 없다.

| Guarded job | Wall seconds |
|---|---:|
| task8-review-red01 | 0.5716825540000023 |
| task8-review-red02 | 1.7228472310000011 |
| task8-review-green01 | 6.847199700000004 |
| task8-review-related-full | 113.39857679599996 |
| task8-ordinary-01 | 2.4766909100000003 |
| task8-positive-01 | 0.7356423289999974 |
| task8-positive-02 | 14.065877654999994 |
| task8-negative-01 | 15.466942888999995 |
| task8-nonterminal-01 | 22.1635429 |
| task8-terminal-01 | 16.792222642 |
| task8-paused-death-01 | 6.332439693999998 |
| task8-active-death-01 | 4.865630314999997 |
| task8-interruption-01 | 10.707243916 |
| task8-final01 | 100.82271907 |
| task8-containment-red | 0.933560859 |
| task8-containment-green | 5.134265051999989 |
| task8-ordinary-02 | 2.6391276970000206 |
| task8-positive-03 | 15.314360003000019 |
| task8-negative-02 | 14.388732199000003 |
| task8-nonterminal-02 | 19.973404732000006 |
| task8-terminal-02 | 13.581250737000005 |
| task8-paused-death-02 | 5.564969602000019 |
| task8-active-death-02 | 3.901518535999969 |
| task8-interruption-02 | 8.397768554000038 |
| task8-final02 | 92.740996091 |

실제 N=3 per-barrier 측정값은 다음과 같다. 독립 producer/checker 실행과 sealing/publication 동안 pause한 비용이며 일반 성능 최적화 실험이나 완료시간 예측으로 확장하지 않는다. 초기 acquisition4.896246380999997초, 다음 body acquisition은 각각1.2713560299999926초와1.3166462509999803초다.

| Barrier | Produce | Check | Seal | Publication | Paused (초) |
|---|---:|---:|---:|---:|---:|
| 1 | 1.096555211 | 1.175763395 | 0.051392306 | 0.015017805 | 2.427148005 |
| 2 | 0.922286854 | 0.952806122 | 0.063056910 | 0.016050744 | 2.092055706 |
| 3 | 1.113852274 | 1.142418370 | 0.080569366 | 0.023566116 | 2.516145127 |

init-return→step1-entry와 terminal frontier 이후 wrapper tail은 기존 UNTRACED 범위를 유지한다. 검증된 finite numerical bodies와 저장소/실행 순서에 한정한다. 기존 root/GDB/OS trust 가정도 유지한다. arbitrary resume, terminal successor와 일반 cross-session publication은 허용하지 않는다.

배분 재검사(`execution-accounting.json`): 원래 승인된 9개 실행/회귀의 실제 guarded wall은193.69330999099998초다. 필요한 실패·검토 검증과 재취득은305.845902672초로, 승인 reserve327.2493744529793초 이내다. reserve 잔여21.40347178097926초와 사용하지 않은 원래 cap206.30669000900002초를 합해 총227.71016178998025초가 남는다. 이 수치를 범위 밖의 실행 허용으로 해석하지 않는다.

Git HEAD `fbbb90171c43ed5462e9584c2621cb0b86b80bd4`, branch `codex/runtime-trace`; index empty, tracked git diff --check exit0. 수정한 untracked 제품/시험도 no-index whitespace 검사를 거친다. 전체 Git status와 정확한 명령/exit/diagnostic은 git-status.txt와 git-verification.json에 제출한다. staging·commit·push 없음. 최종 V1 완료와 외부 acceptance 판정은 설계자가 한다.
