# independent_numeric — R1-0 어려운 입력 감사

A-Numeric VM(`a_numeric/`)의 반올림이 **경계에서도** 맞는지 판정한다. 설명과 결과: `docs/current/A_NUMERIC_EXECUTION_STACK_V1.md` 3.8.

- `oracle.py` — 반올림을 계산하지 않는 판정기. 결과의 이웃 두 값과의 중점(정확 분수) 사이에 정확값이 있는지, 끝점이면 짝수인지.
- `hard_cases.py` — 동점·동점 옆·중점 근처 몫과 제곱근·밑넘침/넘침 경계·SUM/DOT 사례. 난수 없음.
- `audit.py` — 실행기(함수 묶음)를 받아 모든 불일치를 모은다. 멈춤은 이유 문자열로 받는다.

**`a_numeric`과 `engine`을 import하지 않는다** (`tests/test_audit_numeric_hard_cases.py`가 강제). VM의 반올림 결함이 판정기 안에도
같이 들어 있을 수 없게 하기 위해서다.

판정기 자체도 시험한다: 하드웨어 결과를 전부 받아들이고, 정답의 한 칸 이웃을 전부 거부해야 한다.
