# Git provenance 복구 기록 — 2026-10-01

원래 작업 폴더 `D:/numerical-audit-lab`에서 git status, git rev-parse HEAD,
git log -5 --oneline은 모두 .git 없음으로 실패했다. 그 폴더에서 git init을 하지 않았다.

복구본: `D:/numerical-audit-lab-recovered-2026-10-01`.

검색한 범위와 실제 후보는 [GIT_RECONSTRUCTION.json](../audit/gate2c/GIT_RECONSTRUCTION.json)에 있다.
`rg --files --hidden --no-ignore -g '*.bundle'`로 확인한 Lab bundle은 한 개였다.
Downloads의 numerical-audit-lab.zip도 ZIP entry를 열어 확인했으나 embedded bundle은 없었다.
이 검색 범위 밖에 다른 bundle이 없다고 주장하지 않는다. 파일 날짜로 최신을 추측하지 않았다.

실제 bundle refs/HEAD는 `2f2a2216f7455429fc36b06c919793ee9bebf781`이다.
bundle SHA-256은 `84e862a1cd5281ea7a73ca592f496703f7d2a875dc1f6887d76c64f833978f4e`.
fresh clone 후 git bundle verify는 complete history로 정상 종료했고 git fsck --full도 exit 0이었다.
해당 이력에는 V2 봉인/승격, Gate 2A 및 Gate 2B plan/capture/fixture/result가 있다.

## 복구 커밋 순서

| 단계 | commit |
|---|---|
| 기존 V2 / Gate 2A / Gate 2B tip | `2f2a2216f7455429fc36b06c919793ee9bebf781` |
| Gate 2B closure 및 raw-byte 보존 설정 | `01f7fcb47fa7b6576895b02b4a9ea0b4228d7207` |
| Gate 2C plan sealed | `96e8863` |
| 동결 Gate 2C implementation/tests/review snapshots | `7b167b0` |
| 동결 Gate 2C result 및 PROVISIONAL 상태 기록 | `0ea95c1` |

위 새 커밋들은 **이미 완료된 작업을 현재 시점에 재구성한 이력**이다.
측정 당시 Git commit으로 plan을 선등록했다는 소급 증거가 아니다.
과거 commit dates를 만들지 않았고 bundle의 원래 조상 커밋을 rewrite하지 않았다.
원래 plan/result/source 봉인 목록과 그 당시 로컬 기록을 함께 보존한다.

Git의 자동 줄바꿈 정규화가 새 CRLF JSON을 LF로 저장하는 것을 처음 두 복구 커밋에서 발견했다.
우리의 미공개 복구 커밋 두 개만 working files를 보존하는 mixed reset으로 다시 구성했고,
봉인 경로에는 -text를 설정했다. 기존 bundle 이력, 원본 폴더, adapter, 결과 바이트는 수정하지 않았다.
기존 closure/result seal에 있는 모든 파일은 working copy와 committed Git blob 양쪽에서 raw SHA-256이 일치했다.

현재 origin은 clone에 사용한 로컬 bundle이다. 새 원격 주소를 추측해 설정하지 않았고 push하지 않았다.
원본 .git 없는 폴더는 그대로 둔다. 새 Git 작업은 복구본에서 한다.
봉인된 README와 결과의 당시 PASS 문구는 바꾸지 않는다.
현재 상태의 우선 기록은 [GATE2C_STATUS](GATE2C_STATUS.md)의
**PROVISIONAL PASS / LONG_REGULAR_PREFIX, independent audit PENDING**다.
