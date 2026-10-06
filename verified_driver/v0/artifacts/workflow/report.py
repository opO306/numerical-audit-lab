"""Read actual receipts into final report; no tests, source changes or Git writes."""
from pathlib import Path
import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[4]
ART=ROOT/'verified_driver/v0/artifacts'
def load(p): return json.loads(p.read_bytes())
def sha(p):
    with p.open('rb') as stream: return hashlib.file_digest(stream,'sha256').hexdigest()
fresh=ART/'authority-03'; proof=load(fresh/'authority-proof.json'); actual=load(fresh/'actual-result.json')
pre=load(fresh/'pre.json'); preservation=load(ART/'preservation/after-final.json')
export=load(ART/'native-validation-final/manifest.json')
ledger=load(ROOT/'runtime_trace/regular_nstep/artifacts/budget.json')
reports={s:load(fresh/'pending/real'/s/'execution.json') for s in ('acquisition','derivation','independent_check')}
checker=load(fresh/'pending/real/fresh_checker_report.json'); state=proof['certified_state']
assert checker['verdict']=='CHECKER_PASS' and checker['requested_complete'] is True and checker['checked_steps']==checker['requested_steps']==1
assert actual['result']['verdict']=='ACCEPT' and state['generation']==1
assert (fresh/'certified/CURRENT').read_text().strip()==actual['result']['state_id']
assert proof['prior_refusal_state_id']==proof['after_refusal_state_id'] and proof['controlled_refusal']['verdict']=='STOP'
assert preservation['checked_files']==6892 and preservation['changed_or_missing']==[]
for scope in ('runtime','driver'):
    assert all(sha(ROOT/name)==digest for name,digest in pre['source'][scope].items())
assert sha(ROOT/'audit/gate2c1/vendor/gala-1.12.0-cp312-cp312-manylinux_2_24_x86_64.manylinux_2_28_x86_64.whl')==pre['wheel_sha256']
junit=ET.parse(ART/'final-review-green-junit.xml').getroot()
suites=list(junit.iter('testsuite')); counts={k:sum(int(s.get(k,0)) for s in suites) for k in ('tests','failures','errors','skipped')}
assert counts=={'tests':119,'failures':0,'errors':0,'skipped':0}
git=lambda *args:subprocess.check_output(['git',*args],cwd=ROOT,text=True)
assert git('rev-parse','HEAD').strip()=='79a655f0848152aa765e1537b741518b2fa97acf'
assert git('status','--porcelain','--untracked-files=no')==''
storage=export['storage']; combined=sum(storage[k]['logical_bytes'] for k in ('old_runtime_artifacts','managed_driver_artifacts','native_mirror_all'))
assert combined<8589934592
stage_seconds=sum(r['wall_seconds'] for r in reports.values())
summary={'schema':'VERIFIED_DRIVER_V0_FINAL_SUMMARY_V1','status':'IMPLEMENTED / AUTHORITY PATH DEMONSTRATED / INTERNAL REVIEW FIXES VALIDATED / NOT EXTERNALLY AUDITED',
    'actual_source_unchanged_since_final_run':True,'test_counts':counts,'fresh_run':'authority-03','checked_operations':checker['operation_count'],
    'state_id':actual['result']['state_id'],'output_bits':proof['exact_terminal_bits'],'generation':1,
    'controller_outside_adapter_seconds':actual['result']['driver_seconds'],'adapter_plus_guarded_work_seconds':actual['result']['runtime_seconds'],
    'summed_stage_receipt_seconds':stage_seconds,'full_api_seconds':actual['total_seconds'],
    'controller_peak_rss_bytes':proof['driver_controller_peak_rss_bytes'],'stage_receipts':reports,
    'shared_ledger_used_seconds':ledger['used_seconds'],'remaining_shared_seconds':3600-ledger['used_seconds'],
    'v0_guarded_execution_delta_seconds':ledger['used_seconds']-2521.5202657650216,
    'storage_snapshot_combined_including_native_mirror_bytes':combined,'storage':storage,
    'storage_note':'Measured export snapshot; subsequent small report/status/preservation metadata not included. Ledger guard wall excludes preflight filesystem traversal; total session elapsed and all metadata tooling wall not measured.',
    'protected_checked_files':6892,'protected_changes':0,'source_hashes':pre['source'],'external_independent_audit':'NOT COMPLETED','commit_push':'NOT PERFORMED'}
(ART/'final-summary.json').write_text(json.dumps(summary,sort_keys=True,indent=2)+'\n')
lines=['# Verified Driver V0 최종 보고 — 2026-10-05','',
'승인된 V0 범위의 구현·검증을 완료했다. 실제 외부 Gala 후보는 fresh 독립 검사 PASS 뒤에만 인증 상태로 채택됐고, 최종 소스의 거부·변조·자원·복구 시험이 통과했다. 여기서 인증은 기존 Runtime Trace 계약에 조건부인 Driver 내부 상태다. 외부 독립 감사와 형식·물리 인증은 완료되지 않았다.','',
'| 확인 항목 | 실제 결과 |','|---|---|',
'| 검증 전 후보의 권위 | 최종 후보의 실제 실행·공격 시험에서 무검증 후보의 채택 없음. 개발 RED에서 발견한 잘못된 fallback/source 연결과 거부 metadata 결함은 보존·수정했다. |',
'| 실제 실행 경로 | 원본 Gala → GDB 실제 기록 → 기존 Numeric IR/frozen V2 → 기존 독립 checker → Driver gate → 영수증·객체 → atomic CURRENT. 최종 fresh N=1,36연산,전체완료 PASS,세대0→1. |',
'| 변조·불완전 실행 | Driver83시험과 기존 Runtime Trace36시험, 총119PASS/0실패/0오류/0skip. 최종 실제 실행 기반1ulp대조 STOP,인증 상태 불변. |',
'| fallback·재시작 | 생산 fallback 없음,STOP 기본값. TEST_ONLY 대조만 같은 gate로 검증. 완료 transaction 재요청/재시작은 같은 세대1; 임의 S1에서 Gala 재출발은 STOP. |',
'| 완료·감사·Git | 승인된 V0 완료. fresh-context 내부 검토 Important2건을 TDD로 수정하고 전체회귀·원본실행 재검증. 외부감사 없음. commit/push 없음. |','',
'## 실제 작동 범위와 증거','',
'데스크톱 Windows host `으악`의 WSL Ubuntu24.04/Linux x86-64/CPython3.12.3에서 실행했다. 실제 authority 저장소와 수치 증거는 관리 worktree의 NTFS mount에 있다. 이번 V0는 노트북 실행을 추가하지 않았다. 단위·저장 증거 시험은 같은 WSL의 Linux-native mirror를 사용했으며 매 동기화마다 현재 Runtime Trace89소스와 Driver/test 바이트 동일성을 확인했다. 이 mirror는 다른 장비/외부 감사가 아니다.','',
'- 최종 원본 실행: `verified_driver/v0/artifacts/authority-03/authority-proof.json`, `actual-result.json`, `pending/real/fresh_checker_report.json`, `pending/real/derived/completion.json`.','- 수정 전 실행: `authority-02/` 보존. `authority-01/`은 사전 Git 경로 수집 실패이며 수치 실행을 시작하지 않았다.','- 최종 source hash·비용·검증 요약: `verified_driver/v0/artifacts/final-summary.json`.','- 최종 시험: `final-review-green-junit.xml`, `jobs/final-review-green/stdout.log`. 전체명령은 해당 `execution.json`에 기록됐다.','- 모든 native 시험 증거 내보내기: `native-validation-final/test-evidence.zip` 및 member SHA-256/CRC검증 `manifest.json`. 모두 TEST_ONLY이며 새로운 수치 실행으로 세지 않는다.','',
'최종 출력 q0,q1,v0,v1: `'+ '`, `'.join(proof['exact_terminal_bits'])+'`.','',
'최종 상태 ID: `'+actual['result']['state_id']+'`. acceptance ID: `'+state['acceptance_id']+'`. acquisition ID: `'+state['run_id']+'`. completion SHA: `'+checker['completion_sha256']+'`.','',
'`after_objects`와 `before_replace`에서 CURRENT는 genesis ID를 유지했고 checker PASS와 영수증이 존재했다. `after_replace`에서만 새 상태 ID가 보였다. 재요청은 기존 완료를 반환하여 수치 실행·세대 증가를 반복하지 않았다. 원본을 베껴 계산하는 대체 프로그램이나 N별 별도 코드는 추가하지 않았다. fresh Driver 실행은 N=1이며 저장된 N=10은 계약 시험 대조다. 기존 Runtime Trace N=10/100 역사적 결과를 Driver의 새 fresh10/100 증거로 승격하지 않았다.','',
'## 거부·공격·복구','',
'실행한 행렬:1ulp,repair한 hashes,오래된 PASS/이전영수증,후보A의 증거를B에 연결,checker생략,REFUSED강제ACCEPT,checker전 publication,fallback재검증우회,predecessor교체,잘린/unknown/dangling CURRENT,잘못된 checker JSON/중복key/nonfinite,timeout/exception,resource refusal,transaction중 source변경/fallback의 source초기화,기존/금지된 evidence경로에 거부파일 추가,저장·시간예산소진 후 반복metadata작성,audit_only경로.','',
'최종 행렬은 이전 인증 ID·세대·바이트 유지 또는 완전히 기록된 새 세대만 허용했다. 실제 프로세스 `os._exit(73)`를 after_objects/before_replace/after_replace에서 실행했다. 교체 전은 세대0,교체 후는 영수증·객체가 유효한 세대1로 복구했다. 이 crash시험은 Linux-native 시험 파일시스템에서 수행했으며 전원차단·모든 NTFS/스토리지의 내구성을 증명하지 않는다. 잘린 CURRENT를 임의 다른 객체로 복구하거나 genesis로 덮어쓰지 않고 거부한다.','',
'개발 중 RED에서 foreign TEST_ONLY fallback이 다른 transaction 상태를 publish하면서 STOP을 반환하는 반례와 fallback의 source epoch 초기화 반례가 재현됐다. active transaction/input/source를 고정하여 수정했다. 최종 검토는 STOP이 기존 디렉터리에 결과 파일을 추가하는 문제와 소진된 저장예산에서 metadata가 자라는 문제를 추가로 찾았다. 여섯 회귀시험을 RED로 관찰한 뒤 생성 전 admission·8MiB bounded metadata reservation·이번 호출의 exclusive ownership을 적용했다. 실패 로그를 삭제하거나 과거 PASS로 대체하지 않았다.','',
'## 측정 비용과 한도','',
'| 최종 실제 N=1 측정 구간 | 시간 | 메모리 |','|---|---:|---:|',
f"| 전체 transact API | {actual['total_seconds']:.6f}s | controller RSS peak {proof['driver_controller_peak_rss_bytes']:,}bytes |",
f"| 어댑터 밖:admission/소스/게이트/저장 등 | {actual['result']['driver_seconds']:.6f}s | 위 controller 측정 |",
f"| 어댑터+guarded Runtime Trace 경로 | {actual['result']['runtime_seconds']:.6f}s | 단계별 아래 |"]
for stage,rec in reports.items(): lines.append(f"| {stage} guarded unit | {rec['wall_seconds']:.6f}s | cgroup peak {rec['peak_tree_memory_bytes']:,}bytes |")
lines+=['',f'단계 receipt wall 합은 {stage_seconds:.6f}s다. 어댑터 시간에는 source hashing·저장 장부 filesystem traversal·controller·보고 처리가 섞여 있다. 원본 계산 자체와 추적만의 시간을 분리 측정하지 않았으며, 원본 대비 속도배수·확장성을 보장하지 않는다. API전체와 두 기록구간 합의 작은 차이는 결과metadata/반환 등 계측구간 밖이다. 어댑터 내부를 더 잘게 계측하는 최적화는 미룬 Minor다.','',
f"기존 공유장부 사용 {ledger['used_seconds']:.6f}/3600s,남음 {3600-ledger['used_seconds']:.6f}s. V0에서 장부에 추가된 guarded wall은 {ledger['used_seconds']-2521.5202657650216:.6f}s이며 실패·시험·증거 내보내기도 포함한다. 이 수치는 전체 대화/개발 elapsed나 모든 metadata tooling wall이 아니다. guard 사전 filesystem traversal은 장부 job wall에 포함되지 않으므로 위 실제 API 시간과 구분한다. 장부를 초기화하거나 증액하지 않았다.",'',
'수치 단계는 기존 Linux cgroup guard의 단일job 최대600s,tree MemoryMax4GiB/swap0,누적장부3600s를 사용했다. 이번 실제 controller는 RLIMIT_AS4GiB로 실행했다. 이것을 전 장비·모든 controller/작업의 합산메모리 상한으로 표시하지 않는다. 새 transaction은 기존 승인 장부/Driver namespace/완료 marker/남은시간/aggregate 저장공간을 쓰기 전에 검사한다. Driver JSON/object/receipt/pointer용8MiB를 예약하고, 현재 Driver파일과 미사용예약분을 기존 guard storage cap에서 차감하여8GiB범위를 유지한다. 생산 fallback은 없고 유료 자원도 사용하지 않았다.','',
f"내보내기 때 old Runtime artifacts {storage['old_runtime_artifacts']['logical_bytes']:,}bytes,관리 Driver artifacts {storage['managed_driver_artifacts']['logical_bytes']:,}bytes,전체 native mirror(원본 복제 포함) {storage['native_mirror_all']['logical_bytes']:,}bytes였다. 보수적으로 합산 {combined:,}bytes <8GiB. 이후 작은 보고서·status metadata는 이 snapshot에 포함되지 않는다. source/harness/wheel은 프로그램이 자동으로 호출·수집했다. 사람/도구가 수행한 수동 계약 작업은 저장 시험 증거의 경로 재결합,공격 주입,검토 후 수정이다. 실제 계산식을 옮겨 적은 구현은 없다.",'',
'## 보존·읽은 자료·한계','',
'design/spec와6-task plan은 전체 읽었다. 기존 runner/acquire/resources/schema와 필요한 연결 경로는 직접 확인했고 전체 Runtime Trace89소스는 바이트 hash로 결합했다. frozen V2/Impulse/A 전체를 새로 감사했다고 주장하지 않는다. 보호 baseline6,892파일을 전후 SHA-256/크기로 재검사하여 변경·누락0건이었다. 승인된 mutable `runtime_trace/regular_nstep/artifacts/budget.json`과 `.running.json`만 제외했다. Gala wheel SHA는 사전/사후 일치하고 그 값은 final-summary에 있다. unrelated 원본 worktree 미커밋 파일도 보존했다.','',
'init-return→step1-entry와 native terminal frontier→Python wrapper tail은 UNTRACED다. 초기 allocation/root 전제와 GDB/collector/OS 실행 진실의 신뢰 전제는 유지된다. native symbolic coefficients0,물리궤적/모든입력/모든미래/범용CPU·GPU/형식인증/외부감사 closure는 미입증이다. trusted controller/low-level Store/OS와 serialized calls 범위이며 임의 권한 Python/filesystem writer나 concurrent runner를 방어한다고 주장하지 않는다.','',
'## 검토·구현 판단','',
'새 문맥 내부 검토는 Critical0/Important2/Minor1,판정With fixes였다. Important2건은 작성자가 한 번의 TDD fix pass와119회귀·fresh authority-03으로 해결했다. 재검토자는 보내지 않았으며 external audit를 수행한 것도 아니다. 검토 원문 요지는 `artifacts/review/fresh-review.md`에 보존했다.','',
'판단1:기존 public runner는 old RT장부폴더만 output으로 허용하여 unchanged acquire/producer/checker CLI 어댑터를 새 Driver경로에 연결했다. 비용/위험은 어댑터차이이며 source/command binding·기존회귀·실제실행으로 검사했다.','판단2:trusted controller의 실제 observed report와 사전 transaction/source를 candidate디스크와 분리·고정했다. 비용/위험은 OS/controller신뢰 전제이며 적대적 privileged writer를 다루지 않는다.','판단3:저장·권위 시험은 바이트동일 native mirror로 실행했다. 비용/위험은 파일시스템·환경차이이며 실제수치/authority는 관리NTFS mount에서 별도 수행했고 power-loss 일반화는 하지 않았다.','판단4:no-commit/no-cleanup 사용자 지시 때문에 generic review-package의 빈 commit range를 실제 Git no-index untracked patch로 대체하고 RED/ledger를 보존했다. 비용/위험은 Git commit recovery checkpoint가 없다는 것이며 current HEAD·source hashes·증거ZIP을 남겼다.','검토가 판단하지 않은 privileged writer/concurrency/전칭물리·미지원프로그램/생산fallback/전원·하드웨어/상속checker외부감사/검토자의재실행은 모두 위 경계로 남긴다. 그 경계를 넘는 주장에는 새 증거가 필요하다.','미룬 Minor:어댑터 내부 세부 timer 추가. 현재 측정구간을 혼합 시간으로 정확히 표기했다.','',
'## Git diff/status와 납품','',
'HEAD는 `79a655f0848152aa765e1537b741518b2fa97acf`이며 detached managed worktree를 재사용했다. tracked diff와 tracked status는 비어 있다. 새 Driver package/test/report는 untracked이므로 일반git diff만으로 변경이 보이지 않는다. 기존 Runtime Trace N-step uncommitted 입력은 별도 이전 작업으로 status에 남아 있다. staging/commit/push/강제정리 없음.','',
'- 실제 전체 Git status: `verified_driver/v0/artifacts/review/git-status.txt`.','- 실제 tracked Git diff: `review/git-diff.patch`(비어 있음).','- 새 Driver production/test/report를 파일별 실제 `git diff --no-index NUL`로 모은 검토패치: `review/untracked-source-git-diff.patch`.','- 바이트 SHA/줄수/source목록: `review/source-inventory.json`.','- Task TDD/판단/실패 기록: `.superpowers/sdd/2026-10-05-verified-driver-v0/progress.md` 및 `verified_driver/v0/artifacts/jobs/`.','',
'승인된 V0 완료 기준을 최종 소스·실제 후보·거부·권위·복구 증거로 충족했다. 이 보고는 merge/push/production 인증의 승인이 아니다. 새 연구 목표나 후속 구현을 자동으로 추가하지 않았다.','']
destination=ROOT/'current/VERIFIED_DRIVER_V0_2026-10-05.md'
destination.write_text('\n'.join(lines),encoding='utf-8')
print(json.dumps({k:summary[k] for k in ('status','test_counts','full_api_seconds','summed_stage_receipt_seconds','remaining_shared_seconds','storage_snapshot_combined_including_native_mirror_bytes')}))
