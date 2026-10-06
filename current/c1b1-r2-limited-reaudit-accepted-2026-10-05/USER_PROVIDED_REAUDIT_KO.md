제출 보고를 그대로 승인하지 않고 현재 Git·소스·실행을 다시 확인했습니다. 프로젝트 원칙대로 “작성자 PASS”와 “독립 검증 PASS”는 분리했습니다.    안읽으면-프런터기-라고-3번-복창

## 최종 판정

| 항목                               | 독립 판정                                |
| -------------------------------- | ------------------------------------ |
| `F-RESOURCE-R2-PRECHARGE`        | **PASS — 제한 독립 재감사 범위에서 finding 종결** |
| `F-RESOURCE-QDIV-SIGN`           | **PASS 상태 보존 확인**                    |
| `F-RESOURCE-ROUND-ADD`           | **PASS 상태 보존 확인**                    |
| W3                               | **독립 재현 성공**                         |
| 전체 pytest                        | **1136 passed** 새로 실행                |
| static spec                      | **155 PASS** 새로 실행                   |
| 전역 resource accounting           | **NOT PASS 유지**                      |
| reference producer 전체 승인         | **아직 아님**                            |
| Runtime / V2 / J / Certification | **계속 미승인**                           |

### R² 수정 자체

현재 실제 코드는 요청한 최소 형태입니다.
```ini
r2 = c.fraction(0, 1)for x in parsed.q:    r2 = c.qadd(r2, c.qmul(x, x))
```

저비용 경계를 production 실행 경로에서 다시 추적했습니다.

| cap    | 독립 관측                                                  |
| ------ | ------------------------------------------------------ |
| 1, 31  | accumulator 생성 전 WORK refusal, multiply 0회, sqrt 진입 0회 |
| 32, 47 | accumulator만 허용, 첫 `5×5` 실제 곱셈 전에 refusal              |
| 48     | 청구된 `5×5` 한 번만 실행, 다음 곱셈 전에 refusal                    |

즉 **“계산하고 나서 비용을 붙이는” 사후 accounting은 아닙니다.**

실제 `pre()` 호출자의 피연산자를 읽고 승인 비용식을 별도로 다시 계산한 결과도 정확히:
```java
R² work       = 16,717
R² operations = 25

whole work       = 2,605,253,326,092,221,245
whole operations = 36,851
```

따라서 보고한 W3와 일치합니다.
```ini
W3 = 2605253326092221245
```

W2에서는 이제 `RESOURCE_CAP / WORK`, W3−1도 동일하게 raw/opposite/certificate 없이 거부되고, W3에서만 기존 raw가 나왔습니다.
```
(52119986341579705480988,
 31271991804947823288593,
 -20847994536631882192395)
```

이때도 `NOT_PUBLISHED / STOP`입니다.

### 수학 결과 보존

`baba8ea`의 수정 전 producer와 현재 producer를 같은 충분한 budget으로 직접 비교했습니다.
```
R²          equal
radius      equal
V           equal
V′          equal
J endpoints equal
exp orders  equal
raw         equal
```

추가로 두 입력도 별도로 재실행했습니다.
```makefile
q=(11/2,-3/2,0)
R²=65/2
R² work=55376
operations=25
before/after raw equal

q=(0,-6,2)
R²=40
R² work=15121
operations=25
before/after raw equal
```

그리고 과거 결함 코드를 cap=1에서 다시 실행하면 **R²=38을 work=0, operations=0인 채 sqrt까지 넘깁니다.** 현재 코드는 같은 cap에서 accumulator 생성 전 정지합니다. 즉 회귀 검사가 실제 결함과 수정본을 의미 있게 구별합니다. 단순히 “테스트가 녹색이라 기분이 좋다” 수준의 증거는 아닙니다.

전체 repository도 제가 다시 실행해서:
```
1136 passed in 45.55s
```

를 확인했습니다. Static checker도 올바른 인자로 재실행해 **155 PASS**였습니다. 첫 static checker 호출은 제가 `--output`을 빠뜨려 exit 2가 났고, 이는 감사 명령 오류였습니다. 추가 변형 probe도 첫 REPL 입력에서 구문 오류가 한 번 났고 별도 프로세스로 수정 없이 재실행해 통과했습니다. 이런 건 숨기면 나중에 로그가 사람보다 정직해지는 골치 아픈 상황이 생깁니다.

## 다만 Git 상태에 중요한 충돌이 있습니다

사용자 보고에는:
```
HEAD = baba8ea...
수정은 미커밋
commit/push 하지 않음
```

이라고 되어 있었는데, **현재 실제 상태는 다릅니다.**
```yaml
HEAD:
79a655f0848152aa765e1537b741518b2fa97acf

parent:
baba8ea942b896af64ceaa7ab41e2bc5db73112c

commit:
Account impulse radius arithmetic within the work budget

commit time:
2026-10-05 14:41:41 +09:00
```

사용자 메시지 시각은 **14:42:00 +09:00**이므로, commit은 보고보다 **19초 전에 이미 존재했습니다.**

더구나 현재:
```
origin/codex/c1b1-fclaim1-output-limit
=
79a655f0848152aa765e1537b741518b2fa97acf
```

이고 `ls-remote origin`으로도 같은 SHA를 확인했습니다. 즉 **현재는 push까지 된 상태입니다.**

정확히 구분하면, commit이 메시지 전에 존재했다는 것은 확정입니다. **push가 정확히 몇 시에 실행됐는지는 이번 자료만으로는 판정할 수 없습니다.** 따라서 누가 어떤 경로로 commit/push했는지도 추정하지 않겠습니다.

이건 수학 finding과 별개의 **프로세스 finding**입니다. 이전의 “추가 승인 전 commit/push 금지” 조건과 현재 저장소 상태가 충돌합니다.

## 현재 유지해야 할 상태
```yaml
target:
79a655f0848152aa765e1537b741518b2fa97acf

source bundle:
4bd5cb0ef00c022689aa1a1dd4354deba08961ab4e1887b38d2f62f287a8cced

F-RESOURCE-ROUND-ADD:
LIMITED INDEPENDENT REAUDIT PASS

F-RESOURCE-QDIV-SIGN:
LIMITED INDEPENDENT REAUDIT PASS

F-RESOURCE-R2-PRECHARGE:
LIMITED INDEPENDENT REAUDIT PASS

GLOBAL RESOURCE ACCOUNTING:
NOT PASS
```

`O-CONTROL-PARAMETERS`, **다른** direct Fraction construction 범위, allocator/worker가 여전히 OPEN입니다. Adapter schedule reconstruction 역시 OPEN입니다. 따라서 세 개의 실제 accounting bug를 잡았다고 해서 갑자기 전체 장부가 성경책이 되는 것은 아닙니다.
```yaml
reference_producer_implementation:
NOT YET INDEPENDENTLY APPROVED

adapter:
PREPARED_ONLY / invoke blocked

V2 numerical recheck:
NOT APPROVED

runtime_activation_allowed = false
J_NOT_VERIFIED
NotCertified
```

Receipt의 **185개 evidence 파일 hash/size도 직접 대조했고 불일치 0개**였습니다. 따라서 **R² finding 자체는 이제 닫아도 됩니다.** 다음 단계는 새 arithmetic patch가 아니라, 아직 OPEN인 resource-accounting 범위를 하나씩 계약상 분류하는 쪽입니다.
