# Runtime Trace 10/100-step 통합 후보 납품 보고

| 질문 | 실제 결과 |
| --- | --- |
| **외부 원본을 자동으로 검사하는가?** | **예, 명시한 regular 지원 경로에서 작동한다.** Gala 1.12.0 원본 API/네이티브 wheel 실행 → GDB 실제 기록 → 자동 Numeric IR → 변경 없는 frozen V2 → 독립 재구성 검사 → 상태·오차 연결 → 요청 완료/거부까지 공개 실행 경로로 연결했다. 수식·기록·IR을 사람이 베껴 입력하지 않는다. 처음의 기존 미추적 간격과 마지막 Python tail은 여전히 UNTRACED이다. |
| **10·100-step을 같은 구현으로 처리했는가?** | **예.** 최종 10-step은 10/10, 234 산술 연산, 9 연결; 최종 100-step은 100/100, 2,214 산술 연산, 99 연결을 검사했다. 둘 다 CHECKER_PASS / requested_complete=true다. 실행에 사용한 89개 Python 소스의 해시 묶음이 완전히 같다. |
| **잘못된 결과와 불완전한 실행을 차단하는가?** | **실행한 공격에서 차단했다.** 해시를 다시 맞춘 의미 공격 22개(획득 identity가 바뀐 네 추가 공격은 동적 namespace까지 완전 재결합)와 HASH/TRUST 대조 2개 모두 REFUSED, requested_complete=false다. 기록 누락·중복·순서 변경, 산술·COPY 결과/피연산자, 상태·오차 연결, terminal 저장, 지원 밖 명령, 거짓 완료를 포함한다. 실패 보고는 확보된 기록/기계 검사/수치 검사 범위를 별도로 보존한다. |
| **사용 비용은 얼마인가?** | 최종 데스크톱의 세 작업 시간 합계는 10-step **49.901918038초**, 100-step **507.831822522초**다. GDB 없는 원본 작업은 각각 2.372904225초와 1.792060390초였다. 모든 개발·시험·감사 실행의 실패분과 양 장비 작업을 합산한 현재 회계는 **2,520.163052665초**다. 최종 수치 비용, 메모리, 기록 크기와 미측정 범위는 아래에 분리한다. 유료 자원 사용은 없다. |
| **확장이 완료됐는가?** | **지원된 유한 경로의 구현·10/100 통합 검증·공격·회귀·별도 노트북 산술 재검산·새 독립 agent 검토를 완료했다.** 감사 판정은 FRESH_AGENT_REVIEW_COMPLETE / NO_OPEN_BLOCKING_FINDINGS_FOR_OBSERVED_CONTRACT다. 명시한 범위에서 미해결 차단 결함을 발견하지 않았다. 외부 감사 종료나 형식 인증은 별도 미완료 상태다. Verified Driver는 이번에 구현하지 않았다. |

이 보고의 완료는 관측한 유한 native 실행과 명시한 기존 신뢰 전제에 조건부다. 모든 프로그램·초기조건·미래 실행, 물리적 정확성, production 승인 또는 전칭 증명을 뜻하지 않는다.

## 실제 동작과 지원 조건

공개 진입점은 `python -m runtime_trace.regular_nstep.run --steps N --out ... --ledger ...`다. N에 따라 계산·검사 코드를 바꾸지 않는다. 원래 harness 파일 자체와 Gala wheel은 보존했고, 실행 시 기존 harness 텍스트의 `n_steps` 인자와 그 결과 metadata 두 곳만 같은 N 환경변수로 연결한다. 외부 계산식을 다시 작성한 실행기가 원본을 대신하지 않는다.

대상은 기존 regular Henon-Heiles 초기 사례, 1 orbit/2 coordinates, 표현된 dt=1/64, Linux x86-64/CPython3.12와 고정 Gala·ELF 모듈이다. 인터페이스는 정수 1..100을 받지만, 이번 실제 확장 증거는 최종 10과 100이다. 지원한 명령·효과·helper 범위 밖의 경로는 거부한다. 다음을 새 기록 수용 규칙으로 명시했고 기존 1/2-step literal 입력 제한은 그대로 보존했다.

- 같은 실제 inferior/process/thread와 각 동적 occurrence를 전역/지역 순서·해시·birth identity로 연결한다. 값이 같은 다른 실행이나 단계는 대체 입력이 아니다.
- 원본 ELF/objdump 디코드, 제어 흐름, GPR/XMM/정의된 flag, 유효주소, PRE 읽기와 실제 쓰기를 매 행 확인한다. 값이 바뀌지 않은 쓰기도 빠뜨리지 않는다.
- body/caller/terminal을 한 memory shadow로 연결한다. 직전 q/full_v/latent의 실제 출력 주소·비트가 다음 입력으로 이어지고 보호 상태의 겹치는 쓰기는 허용하지 않는다. t/dt의 실제 load/ABI 인자와 연속 schedule 주소도 확인한다.
- 여섯 q/full_v/latent lane의 직전 동적 Form을 한 K=4 computed-minus-true basis에서 전달한다. 같은 비트라는 이유로 Form을 재사용하거나 오차를 0으로 초기화하지 않는다. 실제 gradient zero reset만 별도 증거로 허용한다.
- 모든 N entry/return, 마지막 네 output store의 source/destination·stride·save index, 마지막 실제 루프 종료 분기와 정상 종료, 원본 API 출력 비트를 요구한다.
- producer가 수집 기록에서 IR을 자동 만들고 frozen V2를 호출한다. checker는 producer/frozen evaluator를 oracle로 import하지 않으며 실제 기록에서 별도로 graph/정확한 IEEE-754/def-use/Form을 재구성한다. 기존 독립 감사 기반 checker primitive 재사용과 새 reviewer 산술 구현을 구별한다.
- 공개 runner는 별도 최종 checker invocation이 실제로 작성한 fresh 보고의 정확한 정수 requested_steps=checked_steps=N, CHECKER_PASS, requested_complete=true를 확인한 뒤에만 성공을 발행한다. resource EXECUTED, staged PASS, 유효 prefix만으로 전체 성공을 발행하지 않는다. 실행 시작/끝의 소스 파일 집합과 바이트도 같아야 한다.

원시 기계 snapshot/effect 검사와 기록 metadata→IR/산술/Form 대응 검사는 별도 frontier다. 원시 산술 metadata만 조작한 경우 실제 기계 효과 검사는 끝날 수 있지만, 뒤의 독립 graph/IEEE 검사에서 거부된다. 실패 보고의 last_verified_native_trace_seq와 last_verified_v2_trace_seq를 같은 의미로 읽지 않는다.

사람이 처리한 수작업은 지원 계약·수집기/검사기 구현·공격 설계·환경 연결 및 코드 검토다. 사용자에게 계산식 재입력, trace 편집, IR 작성, 단계별 오류 box 수동 입력을 요구하지 않았다. 노트북 연결 정보를 사용자가 제공했다. 코드 작성·정적 검토 등 개발 노동 시간은 측정하지 않았다.

## 실제 최종 결과와 소스 동일성

| 항목 | 10-step | 100-step |
| --- | ---: | ---: |
| 요청/검사 단계 | 10/10 | 100/100 |
| raw 행 | 9,922 | 97,762 |
| IR/V2 산술 연산 | 234 = 14 init + 22×10 | 2,214 = 14 init + 22×100 |
| 단계 간 상태·Form 연결 | 9 | 99 |
| 마지막 native 행 번호(0부터) | 9,921 | 97,761 |
| 요청 전체 완료 | true | true |
| 최종 공개 결과 | CHECKER_PASS | CHECKER_PASS |
| GDB 없는 원본과 최종 출력 비트 | 네 lane 모두 동일 | 네 lane 모두 동일 |

최종 evidence 디렉터리는 `runtime_trace/regular_nstep/artifacts/connected10-final2`와 `connected100-final`이다. 두 실행의 `integration_source_pinset.json`은 같은 89개 소스를 담으며 SHA256은 `c949e61b420696f9ecfc61608d8e0e13be5f12a965e1e103f40ea2941689ddb3`이다. 10→100은 이 동일 최종 소스로 순서대로 실행했다. 이전 수리 전 실행과 실패는 별도 이름으로 남아 있고 최종 완료의 근거로 섞지 않는다.

10-step completion SHA256: `e4e443f0d3d5b9e7645d8d4a34eb4a8a3aebf68a3bc281ab988a4ba08d070efe`.
100-step completion SHA256: `919430cd56342102a8ec55de9c1918d64e9d24dcdd2e547ab12314573d2b5987`.

frozen Gala wheel SHA256: `cc5f0cf3bc63a966a3c130b93f6c05026271fe7178492a02c6266c243b5fc2f0`.
frozen V2 LF SHA256: `48b91d0c45fd7f62dd09df4db28756e6f82c6bd464a040dc60ac1c924ed99780`.

## 거부 시험과 회귀

`attack-supplements02/final_attack_report.json`은 의미 공격 22개, HASH_CONTROL 1개, TRUST_CONTROL 1개를 구별한다. 의미 공격은 파일/global/local chain/component/completion 해시를 다시 맞췄다. raw 식별자가 바뀌는 네 추가 공격에서는 derived 동적 namespace/획득 identity까지 바꾸어 엉뚱한 해시·identity 불일치가 목표 검사를 대신하지 못하게 했다.

| 공격 묶음 | 거부한 실제 검사 |
| --- | --- |
| 누락·중복·순서 변경 | 실제 PC seam/order |
| body read/write 누락, callee-saved 변조, 같은 프로세스 조건 해제 | 전체 기계 효과·memory shadow·owner/all-stop |
| 다른 process나 acquisition, 잘못된 gradient/state 전달 | process/thread identity와 실제 caller/entry bits |
| terminal save pointer 변조, 정상 종료 누락 | 실제 read/write def-use와 정상 종료 전제 |
| 지원하지 않는 기록 명령 | 기록 assembly 대 독립 decode |
| box 초기화, 잘못된 error source, 같은 값의 다른 단계 identity | 직전 동적 state/Form 연결 |
| IR 순서·마지막 block 삭제·거짓 완료 | 모든 N+1 graph와 요청 완료/frontier |
| 산술 결과·피연산자·COPY metadata 완전 재결합 변조 | scalar rounding/operand, memory/register def-use, post destination bits |
| 실제 post snapshot까지 일관되게 바꾼 산술 변조 | 정확한 IEEE-754 결과 불일치 |
| HASH/TRUST 대조 | component integrity / 완전한 승인 소스 집합 |

초기 wrong-result 공격은 다른 derived identity 불일치에서 먼저 거부되어 목표 산술 검사의 증거로 제외했다. 실패/기존 기록을 보존하고 완전 재결합 공격으로 대체했다. 추가 공격 첫 실행의 기대 reason 문자열도 실제 memory def-use reason과 달라 실패했으며, 거부 자체는 올바르게 작동했다. 목표 reason을 확인한 재실행을 최종 공격 결과로 삼았다.

선정한 통합 회귀는 서로 다른 **211 시험**(새 N-step40 + 기존 관련171)이다. 첫 실행은 210 PASS / 1 FAIL / skip0이었다. 마지막 기존 재배치 시험의 Windows `.git` 경로를 Linux Git이 해석하지 못했다. 이어 ROOT 안 임시 디렉터리는 기존 엄격 audit hook이 금지해 거부했다. 기존 source/test/deny 기준을 바꾸지 않고 명시적인 GIT_DIR/GIT_WORK_TREE 및 ROOT 밖 `/home` proof 디렉터리로 동일 시험을 재실행해 **1 PASS / 실패0 / skip0**를 얻었다. 따라서 211개 각각의 최신 결과는 PASS이며, 한 번의 전체 실행이 전부 green이었다고 주장하지 않는다. 저장된 JUnit과 실패 로그를 보존했다. 저장소 전체 시험을 전부 실행했다는 주장도 아니다.

성공한 기존 재배치 증거는 별도 external proof에 기존 tracked bytes를 그대로 복사하고 원래 소스·모듈 경로 접근을 차단한 상태에서 공개 checker를 실행했다. CHECKER_PASS, test_trust_mode=false, audit DENIED0을 확인했다. 실제 snapshot/명령/소스 해시/접근 로그를 보존했다. 그 proof는 2-step 기존 경로의 재배치 회귀이며 새로운 N-step 외부 감사는 아니다.

## 비용과 장비 분리

데스크톱 native/전체 검사 환경은 WSL Ubuntu24.04, Linux6.6.87.2, glibc2.39, Python3.12.3, Gala1.12.0, NumPy2.5.3, Astropy8.0.1, SciPy1.18.1이다. 노트북 DESKTOP-0EASI0F는 Windows11 Home10.0.22631, Python3.12.7, Ryzen5 4500U/6 logical processors, RAM7,968,595,968B다. 새 설치·유료 인스턴스는 사용하지 않았다.

다음 시간은 실제 해당 subprocess tree의 bounded job wall time이며 준비/WSL 시작/소스·저장 사전 조사 전체 latency를 포함하지 않는다. 각 값은 해당 최종 실행 한 번의 측정이다. 메모리는 Linux cgroup tree peak다.

| 작업 | 10-step 시간 / peak bytes | 100-step 시간 / peak bytes |
| --- | ---: | ---: |
| GDB 없는 원본(시작·import 포함) | 2.372904225 s / 212,111,360 B | 1.792060390 s / 120,639,488 B |
| 실제 원본 실행 + GDB 수집 | 22.409207972 s / 495,083,520 B | 283.694728142 s / 886,800,384 B |
| raw 검사 + IR/frozen V2 + staged 독립 검사 | 17.484319753 s / 276,389,888 B | 139.374120472 s / 2,093,670,400 B |
| 별도 최종 독립 checker | 10.008390313 s / 256,892,928 B | 84.762973908 s / 1,920,466,944 B |
| 연결된 세 작업 합계 | **49.901918038 s** | **507.831822522 s** |

동일 범주의 job 측정 합계/원본 job 비율은 각각 약21.0배/283.4배다. 세 작업에 각각 시작 비용이 포함되며 원본은 한 작업인 점, 한 번의 관측인 점을 포함해서 읽어야 한다. API 계산 호출만 비교하면 GDB 없는 원본은 0.000716309/0.000824788초, 수집 중 원본 API 호출은 17.379264415/273.369053306초였다. native 실행과 GDB 수집은 같은 과정이므로 수집 중 둘의 시간을 따로 빼낼 수 없고 별도 무추적 실행과 비교했다. 원본 계산에 비해 현재 trace 검사는 상당히 비싸다.

derivation 내부의 시간만 따로 측정하면 raw 의미 검사는 6.331539476/47.585293719초, 자동 IR+frozen V2는 0.676032836/6.560305358초, staged 독립 검사는 9.881561600/83.810888799초였다. 이 세 함수 각각의 peak 메모리는 **미측정**이며 위 derivation tree peak를 함수별 메모리라고 나누지 않는다. 단계 내 파싱·파일 저장 비용은 해당 job에 포함되고 저장 전용 시간을 따로 측정하지 않았다.

| 기록/저장 범주 | 10-step | 100-step |
| --- | ---: | ---: |
| raw trace.jsonl | 35,959,343 B | 353,950,758 B |
| capture 디렉터리(실제 raw·지역기록/영수증 포함) | 44,263,774 B | 444,364,369 B |
| derived 디렉터리(IR/Form/검사 증거) | 2,213,036 B | 21,051,665 B |
| 노트북 전달 ZIP | 3,198,968 B | 31,952,345 B |

개발·회귀·공격·실패·packaging/metadata 작업을 보존한 artifacts snapshot은 3,114,899,576B였다. 성공한 ROOT 밖 기존 재배치 proof는 352,826,723B/2,933 files, 노트북 전체 보존 파일은 38,522,999B/28 files였다. 두 장비에 저장한 같은 ZIP도 각 장비 비용으로 센다. 새 코드·문서·최종 보고를 포함한 최신 저장 합계는 최종 storage receipt를 별도로 제공한다. 논리적 파일 byte 합계이며 NTFS/ext4 allocation, cgroup page cache, 압축 전후의 같은 파일을 혼동하지 않는다.

실행 상한은 누적3,600초, 작업당 최대600초(남은 누적 허용량에 따라 축소), tree4GiB, 새 evidence 전체8GiB다. 사용자 답변으로 기존 무료 데스크톱/노트북을 활용하되 제안 상한을 유지했고 임의로 늘리지 않았다. Linux는 실제 cgroup MemoryMax/Swap0/time 한도를 실행 전에 확인하고, raw512MiB·harness1MiB와 공유 잠금 writer allocation으로 실제 쓰기를 제한했다. controller/예산/기록 실패는 완료로 처리하지 않는다. 외부 proof와 Windows 전송은 고정 입력/사전 byte 상한 및 별도 inventory로 함께 계산한다. 이는 임의 프로그램의 모든 filesystem write에 대한 OS 전역 quota 증명이 아니다.

노트북은 저장된 Linux 기록의 별도 산술 재검산을 맡았다. 최종 bounded Windows 작업 시간은 10-step2.633679200초/Job peak62,722,048B, 100-step24.920636500초/435,724,288B였다. 자체 exact RNE/Fraction 구현으로 234/2,214 연산과 702/6,642 Form 묶음(각 계수4+box)을 비교했다. 각 실행의 wrong-result/reset-box/previous-dynamic-id/false-N 자체 공격 네 가지는 모두 의미 거부였다. script SHA256은 두 실행 모두 `047858ce7e3d0c5ae50799b80416abaac925f745c2db3a57172fa89a198d5d0a`다. 원본을 노트북에서 다시 실행한 것이 아니며 전체 x86/ELF 효과 검사를 대신하지 않는다. 데스크톱 전체 checker보다 빠르다는 성능 비교는 하지 않는다.

Windows suspended child를 Job Object에 넣고 한도를 확인한 뒤 재개했다. Windows peak는 Job Object committed-memory API 값으로 Linux cgroup/RSS와 다르다. allocation 실패 probe는 실제 MemoryError를 기록했지만 API peak가 설정 한도보다 크게 보고되어 그 receipt도 REFUSED로 처리했다. 그 counter를 성공한 resident allocation 크기라고 해석하지 않는다. timeout probe도 전체 job 종료/REFUSED였다. 지표 정의는 [Microsoft Job Object extended information](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_extended_limit_information)의 설명을 따른다.

RSS는 별도 표본 지표다. 최종100 독립 checker의 process RSS 합계 peak3,805,978,624B에는 fork/shared pages가 여러 프로세스에 중복 계산될 수 있다. 이를 cgroup tree peak1,920,466,944B와 합산하지 않는다. 개발 초기 PID 중복 합산 측정 버그는 최종 실행 전에 고쳤고 초기 잘못된 RSS를 최종 peak로 재사용하지 않았다.

master ledger는 Linux 작업 FINISHED 후 Windows receipt를 경로별 한 번씩 병합했다. 동시 사용분은 각 장비 작업 시간을 합산하며 concurrency 때문에 무료 시간이 생기지 않는다. 현재71개 작업과 bootstrap 추가51.352137900초를 포함한 합계2,520.163052665초이며 최종 봉인 metadata 작업 후 회계를 다시 갱신한다. electricity, 개발 노동, 정적 reviewer 시간, Remote Desktop control 요청, 네트워크 전송만의 시간 및 cold/warm 반복 분포는 미측정이다. 별도 유료 자원을 사용하지 않았다는 사실을 전체 경제 비용0으로 해석하지 않는다. 속도나 일반 확장성 보장은 하지 않는다.

## 보존·감사·남은 경계

원본 Git HEAD와 분리 후보 HEAD는 모두 `79a655f0848152aa765e1537b741518b2fa97acf`다. 독립 감사된 2-step 소스 기준 `e69119e259b862a7d8462c8d61333782ee2747fd`와 비교해 기존 Runtime Trace/V2/Gate2C.1 경로의 차이가 없음을 preflight에서 확인했다. 원본 protected1,291개, 후보의 동일 protected1,291개, 다른 작업의 미커밋11개를 실제 size/SHA256 재검사했고 변경/누락0이었다. 기존 tracked source diff도 없다. 코드와 증거는 이 채팅에 붙인 별도 managed worktree의 새 경로에만 있다. 원본의 다른 작업 파일을 수정·삭제하거나 강제 정리하지 않았다. commit/push는 수행하지 않았다.

독립 감사 범위는 최종 새 reviewer agent의 source/evidence 검토와 그 reviewer가 별도로 작성하여 실제 노트북에서 실행한 산술 재검산이다. 기존 감사된 primitive를 새 독립 외부 감사처럼 부르지 않는다. 최종 보고 `current/runtime-nstep-audit-2026-10-05/fresh-review-final.md`의 판정은 **FRESH_AGENT_REVIEW_COMPLETE / NO_OPEN_BLOCKING_FINDINGS_FOR_OBSERVED_CONTRACT**, SHA256은 `5882ae3ba00346b7d6803216dd80ee07513a89acb09971d5da44a82c2f540690`이다. reviewer는 최종 source/evidence·실제 결과/로그·해시·회계를 대조했고, 이 마지막 정적 검토에서 수치 실행을 새로 하지 않았다. sealed completion/run_result 안의 `FRESH INDEPENDENT AUDIT PENDING`은 생성 당시 상태로 보존하며 사후에 고쳐 쓰지 않는다. 새 review receipt가 최신 agent review 상태를 설명하고, 외부 감사 종료는 계속 미완료다.

지원 범위의 완료를 제한하는 조건은 다음과 같다.

- 기존 init-return→step1-entry의 미추적 간격과 새 terminal native frontier→Python wrapper tail은 UNTRACED다. 원본 source/normal exit와 base 전제로만 연결한다.
- 최초 output allocation/first column의 root 전제는 유지했다. malloc의 instruction trace를 새로 얻지 않았다.
- collector/GDB/OS 실행 사실의 신뢰, 해시가 동일한 모듈/소스 신뢰는 남는다. 해시 일치만으로 수치 검사를 대신하지 않았다.
- 실제 native symbolic coefficients는 모두0이다. 비영 box를 단계마다 이어갔지만 별도 비영 계수 algebra 시험을 비영 계수 native 실행 검증이라고 부르지 않는다.
- 표현된 t/dt와 관측 연산을 기준으로 한 rounding 검증이다. schedule 생성 오차, 정확한 reference의 branch 동치, 연속/물리 궤적 및 모든 초기조건·미래 실행은 미검증이다.
- 별도 process의 실행은 기록했지만 ASLR 다양성을 입증하지 않았다.
- 이번 agent 독립 검토와 별도 산술 재검산은 외부 독립 감사 종료·형식 증명·production 승인과 구별한다.

**후속 목표는 기존에 논의한 Verified Driver다.** 설계자가 이 지원 범위와 실제 비용을 확인한 뒤 외부 계산의 채택·거부·엄밀 재계산을 통제하는 시제품으로 이어갈 수 있다. 이번에 다른 연구 목표를 추가하거나 Driver를 구현하지 않았다.

## 파일 진입점

아래 경로의 기준 root는 이 채팅의 managed candidate `C:\Users\zun24\.codex\worktrees\runtime-nstep\numerical-audit-lab-recovered-2026-10-01`이다.

- `runtime_trace/regular_nstep/README.md`: 실행 명령과 수용 계약.
- `runtime_trace/regular_nstep/artifacts/connected10-final2/run_result.json`, `connected100-final/run_result.json`: 최종 실제 공개 완료.
- `runtime_trace/regular_nstep/artifacts/attack-supplements02/final_attack_report.json`: 의미22/HASH·TRUST2 및 실제 거부 reason/frontier.
- `runtime_trace/regular_nstep/artifacts/integration-regression-junit.xml`, `portability-retry02-junit.xml`: 전체 관련 회귀와 동일 실패 시험 재실행 결과.
- `runtime_trace/regular_nstep/artifacts/laptop-results/`: 노트북 환경/정확한 source·ZIP·trace identity/검사·resource receipt.
- `runtime_trace/regular_nstep/artifacts/resource-accounting-final.json`, `budget.json`: 양 장비 회계.
- `current/runtime-nstep-delivery-2026-10-05-03/inventory.json`: 역사적 bytes/다른 작업 보존, 최종 source·비용·evidence hash 목록.
- `current/runtime-nstep-audit-2026-10-05/`: 초기 결함 보고, 후속 확인, 별도 reviewer source와 최종 검토.
- `current/runtime-nstep-delivery-2026-10-05-final/verification.json`, `closeout.json`: 최종 현재 소스·증거/JUnit 대조와 후속 양 장비 회계·보수적 전체 저장 합계. verification은 수치 검사를 다시 실행한 보고가 아니라 이미 실행한 증거와 현재 바이트의 연결 검사다.
