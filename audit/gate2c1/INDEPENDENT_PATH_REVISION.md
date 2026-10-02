# 수령 auditor 계산 경로의 Gate 2C.1 이식

원본: `prior_auditor/g2c_regular.py`, `g2c_independent.py`, `g2c_windows.py`.
원본 bytes와 해시는 plan seal에 보존한다. 원본은 수정하지 않았다.

새 `independent/checker.py`는 이 작업자가 이식했다. 새 외부 감사자의 최종 판정 코드라고
표시하지 않는다. 역할은 별도 계산 경로로 전체 propagation을 재계산하는 것이다.
numeric_core, producer T_bin/adapter/판정/serialization은 import하지 않는다.
accepted frozen V2만 같은 연산자로 인정한다.

변경:

- Linux 하드코딩 경로를 현재 checkout에 연결하고 CLI/output 경로를 별도로 받는다.
- 원 auditor의 Lab graph/host binary arithmetic와 직접 fixture decoding은 유지한다.
- machine gradient를 실제 N=1 scalar loop의 전체 순서와 operand 역할로 다시 옮긴다.
- hhalf 연산도 gradient 뒤의 실제 위치로 옮기며 drift ADD의 operand 역할을 보존한다.
- nonfinite latent fail-stop을 반영하고 output bounds와 latent Forms를 구별한다.
- initial zero error부터 전 step을 순차 계산하며 1000-step의 전체 center/Forms/판정 digest와
  다음 segment 연결을 producer 자료와 비교한다. producer endpoint를 seed로 사용하지 않는다.
- 원 Fraction local map으로 6구간을 검사하고 모든 exact output/internal 값을 저장한다.
- trace 구조뿐 아니라 표본의 모든 operand/result bits를 별도로 계산하여 비교한다.
- raw seals/code seals를 전후 확인하고 예외/미완료는 failure로 보존한다.

Gate 2C.1 producer의 Lab 출력 bound는 output Form.rad()다. 다음 입력은 rebase Form이다.
기존 Gate 2C runner의 Lab cross 상한은 rebase 반환 E였다. 새 버전은 수령 auditor의
output Form.rad() 사용과 판정 시점을 맞췄다. V2, Lab graph, 판정 scale은 바꾸지 않았다.
이는 측정 결과를 보기 전에 정한 출력/내부 경계 구별이며 옛 숫자를 맞추는 조정이 아니다.

같은 accepted V2와 유도한 대응 graph를 사용하는 계산 경로의 재계산은 V2 재감사가 아니며,
작업자 이식 코드의 독립 최종 감사는 새 Charter에서 별도로 요구한다.
