# Gate 2B 종료 기록 — 2026-10-01

**CLOSED / PASS / LIMITED** — 설계자 승인.

집 PC와 클라우드의 analysis reproducibility: **PASS**.

`deterministic_digest: 6ccf3d5dd6f2d274c393c4f266bd740ebe9755fd589e4e335507ba7568b2928d`

확인한 파일:
- `reports/home-pc-2026-10-01/gate2b_report.json`
- `reports/cloud-container-2026-10-01/gate2b_report.json`

두 파일의 저장된 digest뿐 아니라 `deterministic` 객체를 기존 runner와 같은
`json.dumps(sort_keys=True, ensure_ascii=False)`로 직렬화해 SHA-256을 다시 계산했고 위 값과 같았다.
이 확인은 저장된 보고서 대조다. 이번 기록 작업에서 Gate 2B 분석을 새로 실행한 것은 아니다.

**gala Linux wheel의 execution reproducibility를 집 PC에서 재현한 것은 아니다.**
외부 실행 자체의 두 번째 환경 재현은 미검증으로 유지한다.

기존 결과/계획/provenance/fixture/disassembly와 분석 코드는 수정하지 않고
`audit/gate2b/closure_seal.json`의 raw SHA-256으로 봉인한다.
기존 결과의 '집 PC 확인 전'은 작성 당시 상태이며, 현재 상태는 이 종료 기록을 따른다.
현재 작업 폴더에는 `.git`이 없어 과거 커밋 순서와 HEAD를 직접 검증할 수 없다.
bundle은 보존하지만 Git 저장소를 새로 만들거나 bundle 내용을 작업 폴더 위에 덮어쓰지 않는다.
봉인은 변조 탐지용 해시 기록이며 제3자 서명이나 독립 감사 승인은 아니다.

Gate 2C는 새 계획과 결과로 기록한다. Gate 2B의 W2–W4 REFUSED와 LIMITED를 소급 변경하지 않는다.
