# Gate 2C 독립 감사 결과 반영 — 2026-10-02

설계자가 제공한 감사 판정과 이번 대화의 결정:
**Gate 2C = PROVISIONAL / CONDITIONAL**.
Critical 0 / Major 2 / Minor 0 / UNRESOLVED 2.
기존 Gate 2C를 CLOSED / PASS로 승격하지 않는다.

| 의무 | 감사 판정 |
|---|---|
| A1 / A2 | FAIL: `(x+x)*y`는 machine-order `(x*y)+(x*y)`와 다른 graph |
| A3 | PASS: frozen fixture gzip/raw hash와 c5971ea 계보 |
| A4 | UNRESOLVED: chaotic 경계 확인, regular 전체 100000 독립 전파 미완료 |
| A5 | PASS: 13907은 finite bound >= represented scale |
| A6 | UNRESOLVED: chaotic cross 경계 확인, regular 전체 독립 검사 미완료 |
| A7–A11 | PASS: 6개 local checks, failure handling, 알려진 equality와 인증 범위 |

Major G2C-M1: machine instruction → T_bin → V2 trace의 1:1 불일치.
Major G2C-M2: 감사자가 실제 받은 ZIP의 hash와 안내 hash 불일치 및 wheel 누락.
전달된 파일명이 `numerical-audit-lab-recovered-2026-10-01.zip`, 감사자가 보고한 hash는
`13c5ccc2e04c6a92c2e8196b3404cfa89d828b9d2a6ac86b8fb384b3ffaa8bbe`였다.
로컬의 다른 파일 `gate2c-independent-audit-2026-10-01.zip`을 확인하는 것만으로
감사자가 받은 파일의 결함을 해소했다고 주장하지 않는다.

감사에서 독립 확인된 chaotic 경계는 기존 결과의 오류로 취급하지 않는다:
V2 PASS through 13906 / first REFUSED 13907;
cross PASS through 13662 / first REFUSED 13663.
새 버전의 성공 조건에 이 숫자와 같다는 조건을 넣지 않는다.

기존 코드/계획/결과/보고서/fixture/digest/봉인/기존 상태 문서는 역사적 바이트로 보존한다.
이 결정은 기존 `CURRENT_STATUS.md`, `docs/GATE2C_STATUS.md`의 PENDING 표시보다 나중의 상태 기록이다.
기존 측정 digest:
`a796c32a5be379c2cdfdd93757963ed92d981bf83dbd4c5e784d45c863fa3acc`.

감사 원문은 설계자가 이 대화에 제공했다. 이번 작업자가 감사 결과를 새로 작성한 것이 아니다.
원 감사 소스/결과 5개 파일은 설계자가 지정한 Downloads 경로에서 수령하여
`audit/gate2c1/prior_auditor/`에 raw bytes로 보존한다.
README는 regular 전체 결과, regular stdout, profiler 로그가 생성되지 않았다고 명시한다.
따라서 과거 실행의 정확한 비용 원인을 이미 입증했다고 쓰지 않는다.
동일 소스를 현재 환경에서 짧게 프로파일링해 측정한 원인과 과거 실행을 구별한다.

수정 작업은 Gate 2C.1에서만 한다. 다음 단계는 Gate 2C.1의 독립 감사 후 결정한다.
Gate 2D, V2.1, Verified Driver, 자동 trace 연구, A 저장소 수정, push는 금지한다.
