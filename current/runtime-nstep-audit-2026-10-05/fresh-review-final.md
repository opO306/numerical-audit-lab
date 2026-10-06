# Runtime Trace N-step 최종 fresh agent 검토

2026-10-05. 판정: **FRESH_AGENT_REVIEW_COMPLETE / NO_OPEN_BLOCKING_FINDINGS_FOR_OBSERVED_CONTRACT**.

최종 동일 소스의 실제 10-step·100-step 공개 경로, 의미 공격과 관련 회귀, 저장된 기록의 별도 노트북 산술 재검산은 이번 regular 유한 경로의 구현·통합 검증 납품 기준을 충족한다. 이 검토에서 그 범위의 정확성·증거 연결·자원 제한을 깨뜨리는 미해결 차단 결함은 발견하지 않았다. 기존 초기 연결과 마지막 Python tail의 미추적 경계, 최초 allocation/root 및 실행 수집 신뢰 전제는 그대로 남는다. **외부 독립 감사 종료, 형식 인증, production 승인, 모든 미래 실행의 증명은 이 판정에 포함하지 않는다.**

| 질문 | 확인한 범위 |
| --- | --- |
| 외부 원본을 자동으로 검사하는가? | 원본 고정 Gala API/native wheel을 실제 실행하고 GDB 기록을 자동 IR/V2/독립 graph·Form 검사로 연결한다. 계산식을 다시 작성한 대체 실행기가 기록을 공급하지 않는다. 지원 계약·코드·수집/검사 규칙·환경 연결·공격·정적 검토는 사람이 작성했고, 실행별 수식/trace/IR/box 입력은 자동이다. |
| 10/100을 같은 구현으로 처리했는가? | 최종 요청 10/10 및 100/100 완료. 각각 234/2,214 산술 연산과 9/99 동적 연결. 동일한 89개 소스 집합/바이트를 두 실행의 pinset과 현재 파일에서 확인했다. |
| 잘못된 결과와 불완전 실행을 차단하는가? | 의미 공격 22개와 별도 HASH/TRUST 대조 2개의 실제 REFUSED·완료 false를 확인했다. 네 추가 공격은 바뀐 acquisition identity와 derived namespace도 완전 재결합하여 목표 의미 검사에서 거부됐다. 공개 경로는 실제 fresh checker의 정확한 요청/검사 N 및 완료 true를 요구한다. |
| 비용은 얼마인가? | 최종 Linux 세 작업 합계 49.901918038s/507.831822522s, 무추적 원본 작업 2.372904225s/1.792060390s. 최종 검토 시 합산 장부 2,520.163052665025s와 저장 snapshot 약 3.506GB를 확인했다. 아래의 장비·측정 범위 구분을 유지한다. |
| 확장이 완료됐는가? | 명시한 기존 regular 사례의 유한 10/100 관측 경로에 대한 구현·시험·증거 검토가 완료됐다. 이 문서는 최신 agent review receipt이며 기존 실행 결과의 생성 당시 AUDIT PENDING을 소급 수정하지 않는다. 외부 감사와 Verified Driver는 후속 범위다. |

## 검토 방식과 소스 동일성

본 reviewer는 생산 구현과 분리된 fresh agent다. 초기/후속 검토를 거쳐 `runtime_trace/regular_nstep/*.py` 11개 전체를 읽고, 재사용한 기존 독립 checker·caller/read-effect·correspondence·Form 계약 primitive를 필요한 범위에서 읽었다. 설계와 실행 계획 및 최종 납품 보고 초안을 읽었다. 최종 공개 완료·거부 수정은 다시 검토했고, 최종 core의 source pinset과 현재 파일을 바이트 해시로 재대조했다. 89개 전체를 줄 단위로 새로 감사했다는 의미는 아니다.

이번 최종 검토에서 수치 실행, pytest, compile, 원본 재실행을 새로 수행하지 않았다. 저장된 실제 로그/결과를 읽고 파일 해시와 장부 합계를 독립 대조했다. 시험 성공은 본 reviewer가 재실행한 결과로 표현하지 않는다. producer나 frozen V2 실행 결과를 독립 산술 증거로 재사용하지 않았다.

기준 HEAD는 `79a655f0848152aa765e1537b741518b2fa97acf`, 기존 감사 소스 기준은 `e69119e259b862a7d8462c8d61333782ee2747fd`다. 두 최종 실행의 `integration_source_pinset.json` SHA256:

`c949e61b420696f9ecfc61608d8e0e13be5f12a965e1e103f40ea2941689ddb3`

현재 `runtime_trace`의 artifacts 제외 Python 파일 집합과 `lab/v2_bound.py`, `independent_checker/oracle.py`를 별도로 열거해 89개 pinset과 집합 차이 0, 바이트 해시 차이 0을 확인했다. 10/100 pinset 파일 해시도 같다. 최종 수치 실행 뒤 추가 README·납품 문서는 계산 소스 집합을 바꾸지 않는다. frozen V2 LF hash `48b91d0c45fd7f62dd09df4db28756e6f82c6bd464a040dc60ac1c924ed99780`와 고정 Gala wheel hash `cc5f0cf3bc63a966a3c130b93f6c05026271fe7178492a02c6266c243b5fc2f0`의 계약을 유지한다.

## 실제 완료와 증거 결속

| 항목 | connected10-final2 | connected100-final |
| --- | ---: | ---: |
| fresh public checker 요청/검사 N | 10/10 | 100/100 |
| 완료/판정 | true / CHECKER_PASS | true / CHECKER_PASS |
| 실제 raw 행 | 9,922 | 97,762 |
| 산술 연산 | 234 | 2,214 |
| 단계 연결 | 9 | 99 |
| 마지막 native 행 | 9,921 | 97,761 |
| Linux PID / process start ticks | 390 / 34985 | 402 / 46414 |
| raw trace bytes | 35,959,343 | 353,950,758 |

두 실행은 동일 Linux boot identity 안의 서로 다른 실제 process birth identity를 보존한다. 각 `gdb_exit_event`는 동일 inferior의 observed true, exit code 0, 종료 후 선택 inferior PID 0을 기록한다. 별도 PID만으로 ASLR 다양성을 주장하지 않는다.

10-step acquisition ID:
`abac7b02f8c65297dd18a1f95c9403ccd5feff30b485236936d3d54a17c49a25`

100-step acquisition ID:
`5561ca5c3790b17b45f0a4e00a0375e8cc0cf763a1ead0f96bf33be092f515c1`

10-step completion SHA256:
`e4e443f0d3d5b9e7645d8d4a34eb4a8a3aebf68a3bc281ab988a4ba08d070efe`

100-step completion SHA256:
`919430cd56342102a8ec55de9c1918d64e9d24dcdd2e547ab12314573d2b5987`

각 acquisition seal의 6개 실제 파일(capture/pending/trace/source pinset/GDB log/harness), completion이 가리키는 blocks/native report, 공개 결과의 세 resource receipt를 다시 SHA256 검사해 불일치 0을 확인했다. 두 실행의 fresh checker report와 public run_result의 요청 완료를 확인했다. 무추적 원본 harness 결과와 수집 실행 harness의 네 출력 lane 비트도 직접 읽어 모두 동일함을 확인했다. 최종 출력 equality는 내부 순서/효과/def-use/Form 검사를 대신하는 증거로 쓰지 않는다.

실제 원본 실행의 harness 변환은 기존 `n_steps=1` 인자 및 결과 metadata를 같은 환경변수 N으로 연결하는 두 치환이다. 나머지 계산 텍스트는 그대로다. 기존 수집 class는 정의만 로드하며, 확장 row/time 상한 치환은 보존된 원본과 검토된 한정 치환이다. 단계당 동일 기록 template를 복사해 원본 실행으로 가장하지 않는다.

## 구조적 결함 수정과 최종 거부 시험

초기 검토에서 확인한 같은 원인의 누락을 관련 경로 전체에서 수정한 것을 확인했다. body의 GPR/정의된 flag/control/read/write 효과를 collector와 별개의 ELF/objdump decode로 확인하고, init 이후 body/caller/terminal에 하나의 memory shadow를 유지한다. shadow를 각 caller에서 다시 초기화해 잘못된 전달을 허용하던 구멍은 닫혔다. 기록의 hex/bit 이중 표현과 value_changed도 서로 일치해야 한다.

중간 및 마지막 네 출력 save는 실제 source load/store에서 도출한다. 같은 output allocation stride와 연속 +8 save index를 유지하고, 최종 loop fallthrough 및 schedule extent를 요청 N과 대조한다. 최초 allocation 생성/첫 column root를 새로 추적했다는 주장은 하지 않는다. 실제 RSI/RDX ABI 차원, process/thread owner와 all-stop, 동일 process의 정상 종료도 검사한다.

독립 graph는 각 동적 body의 metadata 입력/출력과 실제 PRE/POST·exact IEEE-754·COPY/root를 대조한다. 여섯 q/full_v/latent state와 coef4/box는 바로 앞 occurrence의 acquisition/state ID와 Form에서 이어져야 한다. center 비트가 같아도 다른 occurrence나 다른 실행의 Form으로 대체할 수 없다. 실제 gradient reset과 carried error를 구별한다.

native frontier는 실제 기계 snapshot/effect 검사 범위다. 수치 metadata→IR/IEEE/Form 교량은 뒤 graph 게이트에서 끝난다. raw metadata만 바꾸면 native frontier가 끝날 수 있으나 전체 graph에서 거부된다. 이 경우 마지막 native 행을 마지막 수치 검증 행 또는 전체 완료로 해석하지 않는다.

최종 `attack-supplements02/final_attack_report.json`에서 아래 22개의 의미 공격 모두 해시 수선 후 REFUSED·requested_complete false인 것을 확인했다.

- 기록 누락/중복/순서 변경, body read/write 누락, coherent callee-saved GPR 변조, terminal save pointer -8 변조.
- 다른 process, all-stop 해제, gradient 전달 변조, 지원하지 않는 기록 명령, 정상 종료 누락.
- error box 초기화, 잘못된 error source, 다른 acquisition identity, IR 순서 변경, 마지막 block 누락, 실제10에 대해 거짓100 완료 주장.
- 완전 재결합한 산술 결과/피연산자/COPY metadata 및 actual post snapshot까지 일관되게 바꾼 산술 결과.

마지막 네 공격은 acquisition ID 변경 뒤 derived namespace·component·completion hash까지 재결합했고, 각각 scalar rounding/operand, memory/register def-use, post destination, exact IEEE-754 오류라는 목표 거부 stage/reason을 assert했다. 초기 wrong-result는 derived identity에서 먼저 거부되어 목표 산술 공격 개수에서 제외했고, 기존 실패 기록은 보존했다. HASH 대조 1개와 TRUST 대조 1개는 의미 공격과 구별한다. 유한 공격 집합이 모든 악의적 입력에 대한 증명은 아니다.

공개 runner는 실제 별도 checker invocation이 남긴 fresh report를 읽고 `type(requested_steps) is int`, `type(checked_steps) is int`, 두 값 N, 완료 True와 CHECKER_PASS를 요구한다. producer의 staged PASS나 resource EXECUTED가 요청 완료를 대신하지 않는다. 시작/끝 source 집합과 byte도 같아야 한다. 거부에서는 fresh 실패 보고를 우선하고 captured/native/V2 frontier를 나누며, malformed fresh report도 CHECKER_REPORT_UNAVAILABLE로 거부 증거를 남긴다. 관련 `frontier-final/stdout.log`의 9 PASS/1 deselected와 보존된 RED/GREEN 결함 재현 기록을 읽었다.

선정 통합 회귀의 211 distinct 시험은 첫 실행 210 PASS/1 FAIL/skip0이고, 동일 마지막 시험 재실행 1 PASS다. 그 환경 실패는 WSL Git의 Windows .git pointer 해석과 이후 ROOT 내부 relocation 임시 디렉터리였다. source/test/audit hook 기준을 바꾸지 않고 명시적 Git 환경과 ROOT 밖 임시 proof로 통과했다. 각 시험의 최신 결과가 PASS라는 판정이며 단일 전체 green 실행 또는 저장소 전체 시험을 주장하지 않는다. 두 실패 시도와 JUnit/로그를 보존했다.

원래 2-step public checker의 재배치 PASS receipt와 source/input hash, audit.jsonl(47,441 bytes, SHA256 `345091f113a19313cab11394bbc6b5cc41c724cdc5d8ae2bc1343bf62a0360fc`)을 읽었다. deny event 0, test_trust_mode false, 실제 공개 checker exit0을 확인했다. 이는 기존 경로의 보존/재배치 회귀이며 새로운 N-step 외부 감사가 아니다.

## 별도 노트북 산술 재검산

본 reviewer가 생산 translator/V2/form_oracle/checker를 import하거나 복사 실행하지 않는 표준라이브러리 script를 별도로 작성했다. frozen V2의 수학 계약으로 Fraction/정수 nearest-even binary64, signed zero, coef4+box 전파·재계산, 수치적으로 소비되는 완전한 8-byte COPY/root def-use, 실제 scalar 순서/입력/출력 및 바로 앞 동적 carry를 구현했다. 본 reviewer는 script를 실행하지 않았으며 parent가 Windows guard 아래 실행한 실제 기록을 읽었다.

두 최종 실행의 script SHA256은 `047858ce7e3d0c5ae50799b80416abaac925f745c2db3a57172fa89a198d5d0a`로 같다. 저장 패키지의 trace/acquisition identity는 위 Linux 최종 기록과 일치한다.

| 항목 | 10-step | 100-step |
| --- | ---: | ---: |
| 재검산 판정 | INDEPENDENT_NUMERICAL_REPLAY_PASS | INDEPENDENT_NUMERICAL_REPLAY_PASS |
| 실제 산술 연산 | 234 | 2,214 |
| 비교 Form 묶음(각 coef4+box) | 702 | 6,642 |
| 계수 scalar 비교 수 | 2,808 | 26,568 |
| box scalar 비교 수 | 702 | 6,642 |
| replay 내부 wall | 2.430325300s | 24.644762900s |
| Windows bounded job wall | 2.633679200s | 24.920636500s |
| Job committed memory peak | 62,722,048B | 435,724,288B |

각 실행의 wrong-result/reset-box/previous-dynamic-id/false-N 자체 공격 네 가지는 파일 hash 검사를 거부 이유로 쓰지 않고 모두 의미 거부했다. 노트북 DESKTOP-0EASI0F/Windows11/Python3.12.7은 저장된 Linux 기록의 checker host다. Gala 원본을 노트북에서 다시 실행한 것이 아니며 script는 전체 x86/ELF 효과, OS/GDB 실행 사실/source attestation을 별도로 증명하지 않는다. COPY/root 표현도 received IR에서 수치적으로 소비된 완전한 scalar def-use 범위다. Linux native checker와 fresh source 검토의 별도 범위를 합쳐 읽어야 한다. native coef는 모두 0이므로 비영 계수 native 실행 검증은 제공하지 않는다.

## 실측 비용·한도·회계

다음은 최종 각 subprocess tree 작업 한 번의 wall 및 Linux cgroup memory peak다. API 호출/함수 timing과 전체 job timing을 혼동하지 않는다.

| 작업 | 10-step wall / cgroup peak | 100-step wall / cgroup peak |
| --- | ---: | ---: |
| GDB 없는 원본(import/start 포함) | 2.372904225s / 212,111,360B | 1.792060390s / 120,639,488B |
| 원본 실행+GDB 수집 | 22.409207972s / 495,083,520B | 283.694728142s / 886,800,384B |
| raw 검사+IR/V2+staged checker | 17.484319753s / 276,389,888B | 139.374120472s / 2,093,670,400B |
| 별도 최종 checker | 10.008390313s / 256,892,928B | 84.762973908s / 1,920,466,944B |
| 세 작업 합계 | 49.901918038s | 507.831822522s |

세 job 합계/원본 한 job의 관측 비율은 약21.0/283.4배다. 세 job 각각에 start/import가 포함되는 단일 관측 비교이고 반복 성능 분포나 확장성 보장이 아니다. 무추적 원본 API 호출은 0.000716309/0.000824788s, 수집 중 API 호출은 17.379264415/273.369053306s였다. GDB 수집과 원본 실행은 같은 실행이므로 그 안에서 두 시간/메모리를 따로 측정했다고 표현할 수 없다.

derivation의 raw 의미 검사 6.331539476/47.585293719s, 자동 IR+frozen V2 0.676032836/6.560305358s, staged 독립 검사 9.881561600/83.810888799s의 내부 timing을 읽었다. 함수별 peak와 저장 전용 시간은 미측정이다. final100의 표본 process RSS 합계 3,805,978,624B는 shared page 중복 가능성을 가진 별도 지표이며 cgroup peak와 합산하지 않는다. Windows committed-memory peak도 Linux cgroup/RSS와 다른 지표이고 노트북/전체 Linux checker 속도를 직접 비교하지 않는다.

실제 enforce 값은 각 Linux 작업의 cgroup memory 4,294,967,296B·swap0, job 최대600s 및 남은 누적3,600s 한도다. child가 실제 cgroup 값을 확인하고 receipt가 이를 보존한다. file-backed 잠금 writer quota가 실제 GDB/raw/harness/producer/report writer에 연결된다. raw512MiB 및 harness1MiB 선예약, 기타 실제 byte 예약과 전체8GiB 한도를 확인했다. controller/receipt/ledger 실패는 거부 또는 RUNNING marker 보존으로 후속 무회계 실행을 차단한다. 임의 프로그램의 모든 filesystem write에 대한 OS 전역 quota를 주장하지 않는다.

Windows는 suspend 상태 child를 Job Object에 배치하고 committed-memory4GiB/timeout을 enforce했다. 메모리와 timeout 실패 probe가 REFUSED인 실제 receipt를 읽었다. 실패 요청의 API peak가 limit보다 큰 값을 보인 것은 성공 resident allocation으로 해석하지 않는다. 실제 최종 replay 둘은 limit 아래 exit0이다.

최종 장부를 독립 합산해 71 job path 중복0, Windows17 receipt key 중복0·원본 receipt와 wall/host/exit/verdict 불일치0을 확인했다. job wall 합계 2,468.810914765025s + bootstrap 보수적 추가51.35213790000034s = used 2,520.163052665025s(약42.003분)다. Linux marker FINISHED 후 Windows 영수증을 직렬 병합했고, 3,600s 이하이며 잔여1,079.8369473349749s다. 동시에 두 장비를 쓴 시간도 합산한다. ledger를 0으로 초기화해 예산을 늘리지 않았다. 유료 자원/commit/push는 하지 않았다.

검토 시 artifacts snapshot 3,114,899,576B + ROOT 밖 재배치 proof352,826,723B + 노트북38,522,999B = 3,506,249,298B다. 문서·metadata 최종 seal의 작은 추가분은 납품 시 별도 최신 storage receipt에 포함해야 한다. 이 값은 논리적 파일 byte 합계이며 디스크 allocation 크기가 아니다. NTFS/WSL current link는 lstat로 별도 기록하고 따라가 중복 계산하지 않았다. static review/development 노동, electricity, Remote Desktop control, 네트워크 전송만의 시간과 cold/warm 반복은 미측정이다.

## 역사와 다른 작업 보존

preflight baseline에 지정된 보호1291개(290,568,061B)를 원본 D:와 후보 C: 각각 본 reviewer가 size/SHA256으로 다시 대조했다. 두 집합의 변경/누락은 0이고, 원본 다른 작업의 미커밋11개(747,441B)도 변경/누락0이다. 기존 frozen V2/1·2-step source/evidence를 새 실행에 맞춰 수정하거나 과거 증거 공백을 지우지 않았다. 원본과 후보 HEAD가 기준79a655f인 것을 최종 inventory에서 확인했고 기존 tracked 수정 없이 새 경로를 사용했다. 초기 감사 보고와 실패 시도도 남아 있다.

## 유지되는 판정 경계

- init-return→step1-entry와 terminal native frontier→Python wrapper tail은 UNTRACED다. 원본 source/동일 inferior 정상 종료/base 전제로만 연결한다.
- 최초 output allocation/첫 save column root를 생성한 malloc 등은 추적하지 않았다. 이후 모든 save의 동일 stride·연속 index를 검사한 범위와 구별한다.
- collector/GDB/OS의 실제 실행 사실, 고정 module/source의 신뢰는 남는다. hash는 provenance 수단이며 semantic evidence의 대체물이 아니다.
- 실제 coef는 모두0, box는 실제로 비영이며 carry했다. 비영 계수 algebra 시험을 비영 계수 native 실행 검증으로 부르지 않는다.
- 표현된 schedule/관측 연산의 rounding 계약이다. schedule 생성 오차, exact-reference branch 동치, continuous/physical trajectory, 다른 초기조건·미래 실행·범용 CPU/GPU/program 지원은 미검증이다.
- 별도 reviewer의 source/evidence 감사와 별도 작성 산술 재검산은 agent 독립 검토다. 기존 감사 primitive 재사용, 실행 기록의 CHECKER_PASS, 형식 인증 및 외부 감사 종료를 구별한다.

기존 completion/run_result의 `FRESH INDEPENDENT AUDIT PENDING`은 생성 시점 역사라 보존한다. 본 새 receipt는 현재 agent review가 완료됐다는 별도 증거다. 후속 목표는 설계자가 이 확장과 비용을 확인한 뒤 기존 Verified Driver로 이어가는 일이며, 이번에 Driver나 별도 연구 목표를 추가하지 않았다.

검토한 최종 근거는 `current/runtime-nstep-delivery-2026-10-05-03/inventory.json`, 최종10/100 개별 capture/completion/fresh report/resource receipts, `attack-supplements02/final_attack_report.json`, 통합 회귀/재배치 로그, `laptop-results/` 및 `resource-accounting-final.json`/`budget.json`이다. 최종 전체 납품 seal은 이 새 문서 이후 생성되는 metadata이므로 그 후속 seal 자체까지 이 문서에서 이미 검토했다고 주장하지 않는다.
