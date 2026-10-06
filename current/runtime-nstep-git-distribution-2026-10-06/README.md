# 100-step trace Git 배포 후보 — 2026-10-06

GitHub가 거부한 최신 로컬 커밋은 `f686e6ca17d2c8dee5d7b5beb2af0477d306b41b`이며 부모는 `79a655f0848152aa765e1537b741518b2fa97acf`다. 이 커밋에서 추가된 두 trace만 일반 Git의 100MiB 파일 한도를 넘는다. 이 패키지는 원본 기록을 바꾸지 않고 무손실 gzip으로 운반하기 위한 새 배포 후보다. 기존 수치 검증이나 감사 결과를 새로 생성하지 않는다.

| 기록 | 원본 bytes | gzip bytes |
|---|---:|---:|
| connected100-01 | 353,950,758 | 26,071,371 |
| connected100-final | 353,950,758 | 26,053,533 |

`manifest.json`에 원본 경로·크기·SHA-256·Git blob ID·acquisition ID와 gzip 크기·SHA-256을 기록했다. 빌더가 원본 SHA를 기존 acquisition seal에 대조하고 압축 해제 SHA를 다시 확인했다. 실제 별도 폴더에 두 파일을 복원하는 시험도 수행했다. 빌드와 스트림 왕복 검증 시간은 5.036831초이며 별도 복원 시험 시간과 전체 준비 작업은 이 수치에 포함되지 않는다. 유료 자원과 Git LFS는 사용하지 않았다.

## 복원

배포 후보가 커밋된 저장소를 새로 내려받은 경우, 기존 checker를 실행하기 전에 저장소 루트에서 다음 명령을 실행한다.

```text
python current/runtime-nstep-git-distribution-2026-10-06/restore_traces.py --restore
```

기존 원본이 있으면 크기와 SHA가 일치하는지만 확인하며 덮어쓰지 않는다. 원본이 없으면 크기 제한을 적용하여 임시 파일로 압축 해제하고 SHA/CRC를 확인한 뒤, 목적지 파일이 없는 경우에만 공개한다. 압축 파일 또는 기존 원본이 다르면 거부한다. `--restore` 없이 실행하면 쓰기 없이 검증한다. `--repo-root PATH`는 별도 복원 폴더 시험용이다.

복원된 두 원본은 `.gitignore`로 제외된다. 다른 capture 파일, 기존 seal, completion, checker 결과와 소스는 원래 내용 그대로 Git에 남는다. byte 복원 검증은 새 수치 계산·물리 검증·외부 감사가 아니다.

## 승인된 커밋 교체와 push 분리

큰 파일은 기존 커밋에서 이미 추적 중이므로 `.gitignore`만 추가하거나 삭제 커밋을 덧붙여서는 push 거부가 해소되지 않는다. 큰 두 파일을 Git tree에서 제외하고 이 패키지로 대체하여, 최신 미푸시 커밋 하나를 amend하는 방식이다. 원본 파일은 로컬에 유지한다. 2026-10-06 사용자의 “커밋은 너가 직접해 푸시만 내가 할게” 지시에 따라 로컬 커밋 교체를 승인받았다. push는 사용자가 직접 수행한다.

원래 커밋은 로컬 백업 브랜치 `codex/runtime-trace-before-size-fix-2026-10-06`에 보존했다. 이 백업에는 큰 파일이 있으므로 `--all`로 함께 push하지 않는다. 확인 당시 원격 `codex/runtime-trace` 브랜치는 없었다. 실제 push 직전에는 다시 확인해야 한다.
