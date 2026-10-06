# Runtime N-step 후속 독립 소스 검토

2026-10-05. 수행자: 구현 담당자와 별도의 fresh reviewer agent. 이 문서는 `fresh-review-01.md`의 후속 정적 검토이다. 이 agent는 수치 실행이나 시험을 새로 실행하지 않았다. 기록된 pytest 출력과 10-step 자료를 읽은 사실을 새 시험 수행으로 표현하지 않는다. 외부 독립 감사 종료 보고가 아니다.

## 소스상 닫힌 최초 결함

`machine_check.py`는 실제 ELF/objdump 해석으로 얻은 body/caller 연산에 대해 GPR, XMM, MXCSR, flag, control 및 read/write 효과를 독립적으로 대조한다. `raw_check.py`는 init→step1의 기존 미추적 경계만 memory shadow를 다시 시작하고, 그 뒤 body/caller/terminal 구간에서는 하나의 shadow를 유지한다. 실제 output의 모든 네 lane 저장을 내부 caller와 terminal에서 도출하고, 동일 stride 및 매번 +8 save index를 대조한다. Linux PTID owner/PID 관계와 write hex/bits/value_changed 일관성도 확인한다.

`resources.py`는 guardian 예약과 실제 writer의 shared file-backed quota를 연결한다. controller 조사 실패는 자원 거부와 실제 elapsed budget으로 남으며, receipt/ledger 기록 전에 예외가 나면 RUNNING marker 때문에 다음 작업을 거부한다. 공개 runner는 요청 전후 소스 file set 및 bytes를 대조한다.

기록된 `final-gates-red/stdout.log`에서 controller-read-error, unreconciled-job, source-change 3개 시험이 초기 실패한 것을 읽었다. `final-gates-green/stdout.log`에서 해당 관련 모음이 12 passed였음을 읽었다. 이는 파일 검토이며 이 reviewer가 다시 실행한 결과가 아니다.

## 아직 닫아야 하는 같은 완료/거부 경로

검토 시점의 `run.py`는 공개 성공 전에 checker_report의 verdict/requested_steps만 확인했다. checked_steps의 정확한 integer N 및 requested_complete가 True임을 함께 검증해야 한다.

또한 검토 시점의 `checker.main`은 마지막 fresh check 보고를 stdout에만 썼다. runner가 읽는 `derived/checker_report.json`은 producer의 staged check에서 만든 이전 보고였다. 마지막 check의 거부와 frontier를 공개 결과에 연결하려면 마지막 stage의 실제 보고를 독점 파일 또는 검증된 stdout JSON으로 받아 사용해야 한다. 이전 producer PASS의 checked_steps를 최신 실패 범위로 오인하지 않아야 한다.

producer가 raw native 검증 후 IR 생성 또는 저장 중 실패한 경우, 아직 V2가 독립적으로 확인되지 않았으므로 checked_steps=0은 적절하지만, 검증 완료된 native frontier까지 없애면 안 된다. raw/native/V2 진행 상태 및 failure_stage를 분리 보존해야 한다. 이 세 항목은 parent에 즉시 보고했고, 후속 소스와 회귀 결과를 확인하기 전에는 닫힌 것으로 표시하지 않는다.

## 노트북용 별도 수치 재검사

요청에 따라 표준 라이브러리만 쓰는 `laptop_independent.py`를 신규 작성했다. producer/translator/V2/checker/oracle 함수의 import 또는 복사 실행을 하지 않는다. Fraction과 정수 significand RNE를 구현하고 frozen V2 수학 계약의 모든 coef4+box, 실제 산술 순서/입출력 bits, 수치적으로 쓰이는 COPY 및 root, acquisition/phase 및 immediate previous endpoint Form 전달, 정상 exit와 유한 요청 범위를 대조한다. wrong-result/reset-box/previous-dynamic-id/false-N 자체 의미 공격을 포함한다. Windows는 저장된 Linux 기록의 checker host이며 원본 Gala executor가 아니다.

초기 Windows 시도는 storage-space 및 legacy step 필드 해석 때문에 거부되었다. 실제 IR/record를 읽어 stack/instruction storage와 부분 routing COPY의 표현을 인정하되, 수치 scalar bind의 완전한 8-byte source 요구를 보존했다. 실제 raw seq1199는 phase/occurrence=step2이지만 step=1이다. step은 기존 init/body 0/1 구분이며, 동적 단계 동일성은 stepK phase, occurrence, namespaced value ID와 직전 endpoint로 검증한다. 이 parser 정합 수정은 검증 기준 완화가 아니다. 마지막 script SHA256은 `047858ce7e3d0c5ae50799b80416abaac925f745c2db3a57172fa89a198d5d0a`이고, 이 reviewer는 실행/compile/test하지 않았다.

이 replay는 전체 x86 decoder, ELF/source attestation, OS 관측 진실성, 외부 감사 또는 형식 인증을 수행하지 않는다. 실제 native 초기 coef들은 0이어서 비영 계수의 원본 실행 시험 강도는 제공하지 않는다. 기존 init→step1과 native terminal→Python tail의 UNTRACED 조건, 초기 allocation 생성/첫 column root 전제는 유지한다. 최종 10/100 같은 소스 실행과 공격 모음 및 Windows 실제 결과가 전달된 뒤 영향 범위를 다시 확인해야 한다.
