# 채팅에서 받은 구현 승인 범위

2026-10-05 사용자는 작업 범위 확인에 답하여 아래 범위를 명시적으로 승인했다.
이는 NEXT_STEP_KO.md 자체에서 권한을 추정한 기록이 아니다.

```text
AUTHORIZED SCOPE:
Fix F-RESOURCE-R2-PRECHARGE minimally, derive and verify W3,
run required regressions, preserve all remaining OPEN gates,
then report results before any commit/push.
```

R² 초기 accumulator도 가능하면 c.fraction(0,1)로 청구하고 각 좌표의
rational multiply/add를 기존 account 경로로 보낸다. 실제 연산 전 검사·청구하며
사후 일괄 청구는 금지한다. 사용자의 손계산 16717/25는 예상치일 뿐 구현 정답으로
먼저 고정하지 않고 실제 피연산자 비용 재구성과 ledger를 대조한다.

Control/parameter, 직접 Fraction construction 전체, allocator/worker, adapter,
V2 numerical recheck, runtime, J_VERIFIED, Certified 및 전역 accounting PASS는 범위 밖이다.
추가 승인 없는 commit/push는 금지한다.

이 문서는 채팅 승인의 작성자 기록이며, 원본 attachment의 byte copy라고 부르지 않는다.
