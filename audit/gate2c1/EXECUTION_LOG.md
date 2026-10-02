# Gate 2C.1 실행 기록

- 시작 HEAD aa192ae, working tree clean. 먼저 status/rev-parse/log 확인.
- d87b06a: audit decision / DESIGN ONLY plan / prior auditor raw artifacts 봉인.
- eb2305c: 비용 survey와 결과 전 verification method 봉인.
- 구조/변조 시험: 미구현 module에서 RED 확인 후 새 graph 구현, 13 PASS.
- package 시험: 미구현 builder에서 RED 확인 후 missing vendor/false hash 공격 3 PASS.
- 새 구현 시험 28 PASS. 20-step producer + 별도 계산 경로에서 checkpoint/판정/초기 local 일치.
- 위 항목까지의 사전 기록 시 full 결과 없음; 아래는 그 뒤 실행 기록이다.
- 기존 source/report/fixture/seal을 수정하지 않으며 숫자 일치를 성공 조건으로 쓰지 않는다.
- 작업자 실행 및 이식은 새 최종 독립 감사 승인이 아니다. Gate 2C CONDITIONAL 유지.

- 0f2fc62: 최초 구현/code seal; full suite 238 passed in 26.07s.
- `python run_gate2c1.py --out reports/gate2c1-measured-2026-10-02`: exit0, 317.1511553초,
  producer digest aedc69466aabeca697ed177d5a84ee7ae88b5d6ffb91211abd9b2bd00c2650f3.
- 새 읽기 전용 구현 검토: 증거 검증 5 Major/2 Minor. 6 regression RED→PASS; 수치 코드/결과 유지.
- 5504237: 보완 구현/code seal. full suite 244 passed in 24.89s.
- `python audit/gate2c1/independent/checker.py --producer reports/gate2c1-measured-2026-10-02 --out reports/gate2c1-independent-2026-10-02`:
  exit0, 250.6406987초, verification PASS, regular/chaotic 각100000 재계산, 200 endpoint/decision 일치,
  raw/replay/local violations0, pre/post seal failures0. 합계567.7918540초.
- 재검토: 이전5/2 보완 확인, 내부 manifest 검증의 추가 Major1 발견. 실행이 끝난 뒤 tool만 수정,
  5 manifest attacks RED→PASS, 관련9PASS. 이전 source/seal bytes는 pre_delivery_revision/에 보존.
- 최종 code/result seal 및 package receipt는 아래 실제 파일과 Git commit으로 식별한다.
- 최종 full suite: 250 passed in 24.92s. archive 규칙 추가 뒤 package/manifest 9 passed.
- c4f8d62: 최종 Charter/전달 tool 구현 봉인; code seal b89e537316a442c19b6dbcaf86538c34899577e3b6a9a7b2c55d5b363865000b.
- 기존 raw 보호 파일67개 유지. 최종 result commit 뒤에만 bundle/ZIP을 만들며, 외부 receipt에 최종 ZIP hash를 기록한다.
