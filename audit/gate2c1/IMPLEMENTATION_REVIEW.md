# Gate 2C.1 구현 검토와 보완

기존 Gate 2C의 Critical 0 / Major 2 / UNRESOLVED 2, PROVISIONAL / CONDITIONAL은 유지한다.
이 문서는 신규 Gate 2C.1의 구현 검토이며 새 외부 독립 감사 A1–A11 최종 판정이 아니다.

계획 d87b06a → 방법 eb2305c → 최초 구현 0f2fc62 순서로 봉인했다.
0f2fc62의 producer로 full frozen forward 측정을 1회 수행했다. 이후 수치식, T_bin, V2 입력 그래프,
producer 소스와 해당 결과 bytes는 변경하지 않았다. digest는
`aedc69466aabeca697ed177d5a84ee7ae88b5d6ffb91211abd9b2bd00c2650f3`이다.
독립 전구간 재계산은 아래 보완을 봉인한 다음 수행한다.

읽기 전용 새 검토자는 수치식의 직접 오류를 찾지 않았고 실제 .so의 N=1 분기, 9개 gradient 산술,
half 상수 0.5와 callback 경로를 확인했다. 다음 증거 검증 문제를 Major 5 / Minor 2로 보고했다.
이 수는 기존 Gate 2C 감사 건수와 별개이다. 보완 전 소스와 seal은 pre_review/에 그대로 보존한다.

| 발견 | 보완 | 회귀시험 |
|---|---|---|
| ZIP에 segment가 없어도 수락 가능 | producer/independent 400개 필수; 보고서 advertised 경로·hash·coverage·endpoint·hash chain 연결 | required count/경로 시험 및 실제 ZIP 전체 재검사 |
| 빈/짧은 local records 수락 가능 | 정확히 8개, 순서·입력·exact/represented output/internal·두 bound·위반수 전체 비교 | empty/short/extra/input/bound 변조 |
| raw/local 위반인데 exit 0 가능 | 명시 verification_verdict; 위반 FAIL, 미완료 UNRESOLVED, regular 유용성 REFUSED; PASS만 exit 0 | raw/replay/local 위반 및 미완료 주입 |
| pre 실패 보고서 없음, post seal 불완전 | pre/post 모두 plan/method/code/기존 봉인 bytes 확인; 실패보고·완성된 segment endpoint 보존 | pre/post seal failure 주입 |
| trace 주소/occurrence/Form 미검사 | 별도 전사 주소·순서 및 재계산된 실제 V2 입력 Form 비교 | address/occurrence/ordinal/Form 변조 |
| 합계 60분 대신 각각 60분 | independent deadline에서 producer 실제 wall 시간을 차감 | finite/NaN budget 시험 |
| 경계 latent 부족 | independent first refusal ±1에 next latent/Form/bound 기록 | 결과의 동적 경계자료 확인 |

신규 회귀시험 6개는 보완 전 6 failed, 보완 후 PASS를 확인했다. 기존 4종 failure handling도 유지한다.
여기서 false PASS 경로 차단은 명시한 fault 시험과 코드 검토의 결과이지 모든 가능한 프로그램의 형식 증명이 아니다.
새 외부 감사자는 저자가 이식한 auditor-origin checker를 그대로 신뢰하지 않고 별도 구현으로 감사한다.
