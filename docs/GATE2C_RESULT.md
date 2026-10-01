# Gate 2C — Binary-aware certification feasibility 결과

**측정 판정: PASS / LONG_REGULAR_PREFIX** (2026-10-01).
**새 adapter의 독립 수치 감사: NOT_PERFORMED.** 별도 코드 검토와 회귀시험을 수행했지만 독립 수치 감사 승인을 뜻하지 않는다.

계획: [GATE2C_PLAN.md](GATE2C_PLAN.md), [계획 봉인](../audit/gate2c/plan_seal.json).
원자료: [수정본 전체 실행 보고서](../reports/gate2c-home-pc-2026-10-01-verified/gate2c_report.json).
이 판정은 특정 gala wheel의 frozen forward 출력과 같은 이산 map의 정확 산술값 사이의 **반올림 층**에 한정된다.
연속 물리, gala 전체, 다른 플랫폼, 새 gala 실행 또는 블라인드 예측을 인증하지 않는다.

## 1. Gate 2B 종료와 보존

Gate 2B는 [별도 종료 기록](GATE2B_CLOSURE.md)에 **CLOSED / PASS / LIMITED**로 기록했다.
집 PC·클라우드의 저장된 deterministic 객체에서 digest를 재계산해
`6ccf3d5dd6f2d274c393c4f266bd740ebe9755fd589e4e335507ba7568b2928d`와 일치함을 확인했다.
이는 **analysis reproducibility PASS**이며 gala Linux wheel의 집 PC execution reproducibility는 미검증이다.

결과/계획/provenance/disassembly/fixture 및 관련 코드·V2 입력을 포함한 37개 파일을
[closure_seal.json](../audit/gate2b/closure_seal.json)의 raw SHA-256으로 보존했다.
기존 Gate 2B의 W1 NOT_IDENTICAL, W2–W4 REFUSED와 LIMITED를 바꾸지 않았다.
V2 구현과 봉인된 Gate 2A 파일도 변경하지 않았다.
A 저장소 접근·수정·push는 수행하지 않았다.

## 2. 새로 측정한 결과

조건: dt=1/64, N=100000, regular (vx,vy)=(1/4,1/8), chaotic (1/2,1/4), 원점 출발.
두 forward fixture에서 T_bin의 100000개 출력 step을 모두 대조했다.
비트 불일치 0은 **알려진 전제의 이식 확인**이며 새 블라인드 시험 성과가 아니다.

여기서 horizon은 상한 최댓값이 represented 상태 크기 최댓값 이상이 되는 **첫 step**이고,
certified prefix는 그 직전까지의 연속 구간 길이다.
이는 상한이 처음 수학적으로 틀리는 시점이 아니라 **유용한 판정력이 처음 부족해지는 지점**이다.

| 측정 | regular | chaotic |
|---|---:|---:|
| 출력 replay 대조 완료 | 100000 step | 100000 step |
| V2 certified prefix | **100000** (N 안에서 거부 없음) | **13906** |
| V2 첫 scale REFUSED | N 안에서 없음 | **13907** |
| cross-bound PASS | **100000 step** | **13662 step** |
| cross-bound 첫 REFUSED | N 안에서 없음 | **13663** |
| T_bin 내부 V2 상한 비유한 → UNAVAILABLE | 없음 | **13953** |
| Lab V2 상한 비유한 → UNAVAILABLE | 없음 | **13735** |
| 두 유한 상한이 존재하는 구간의 raw cross enclosure 위반 | 0 | 0 |
| 정확 국소 재시작 구간 | 3/3, 위반 0 | 3/3, 위반 0 |

혼돈 궤도에서 cross-bound가 더 먼저 거부된 이유는 두 상한의 **합**을 써야 하기 때문이다.
두 represented 출력의 residual과 상한 합은 Fraction으로 정확하게 비교했다.
cross의 scale REFUSED와 raw enclosure 위반을 분리했다.
상한이 비유한 상태가 된 이후에는 UNAVAILABLE이며, 해당 구간을 PASS로 세지 않았다.
regular의 실제 한계를 100000 밖으로 추정하지 않는다.

## 3. 상한 기록 지점

아래 값은 출력 네 성분 상한 중 최댓값이다.

| step | regular E_max | chaotic E_max |
|---:|---:|---:|
| 10 | 5.551691831387405e-17 | 1.2449518790483903e-16 |
| 100 | 1.3090287918611837e-15 | 3.418817226661225e-15 |
| 1000 | 6.663514800922983e-14 | 1.0856960404128685e-12 |
| 10000 | 3.330519688001657e-11 | 1.0971692511866228e-05 |
| 50000 | 3.0887995412589084e-09 | UNAVAILABLE |
| 100000 | 3.734460733670531e-08 | UNAVAILABLE |

finite cross 비교의 최대 residual/bound는 regular 0.8860840412813303,
chaotic 0.6401900600703238이었다.
이는 측정된 두 구현의 차이를 설명하는 비율이며 독립 exact 전역 참값을 측정한 비율은 아니다.

## 4. 검증 근거와 한계

- 계산기 측: numeric_core에 명시적 binary-order graph를 실행했다.
- 검사기 측: frozen V2를 수정 없이 사용했다. 검사기 모듈은 numeric_core를 import하지 않는다.
- 내부 전파 상태 `(x,y,vhx,vhy)`와 출력 `(x,y,vox,voy)`를 구분했다.
- 초기화 graph의 반올림 오차도 네 zero Form에서 시작해 전파했다.
- 정확 산술에서 staggered leapfrog와 Lab velocity Verlet의 full-step 출력은 같다.
  따라서 두 구현의 공통 exact target에 대한 오차 상한 합으로 cross 비교를 한다.
- 직접 작성한 Fraction map으로 n0=0,50000,99992에서 8 step씩 국소 재시작했다.
  output과 내부 상태의 포함 검사를 모두 수행했고 총 6개 구간에서 위반 0이다.
  **이 구간은 represented 내부 상태에서 zero-error로 재시작한 국소 검사다.
  전체 100000-step exact 실행을 독립 계산한 증거가 아니다.**
- 새 replay의 full-state exact target과 Lab Verlet의 6-step/비영 위치 4-step 동치를 시험했다.
- 별도 reviewer가 disassembly 대응과 전파 구조를 읽기 전용으로 검토했다.
  실제 wheel 런타임의 모든 분기를 새로 추적한 것은 아니다.
- [코드 검토 및 수정](../audit/gate2c/CODE_REVIEW.md): 초기화 실패 prefix, 표시용 float overflow,
  봉인 실패의 보고서 보존, 초기화 nonfinite 검사 4건을 수정했다.
  5개 회귀 실패를 실제로 재현한 뒤 전체 suite **210 passed in 27.90s**를 확인했다.
- 첫 REFUSED 뒤에도 replay가 진행되며 late 변조를 탐지하는 runner 시험을 포함했다.
- 독립 수치 감사 evidence/reproduction code의 기존 미수령 상태, PyPI 서명 체인 미검증 등
  기존 provenance의 한계를 이번 작업으로 닫았다고 주장하지 않는다.

## 5. 비용과 검증 재실행

| 실행 | wall seconds |
|---|---:|
| 수정본 regular 전체 분석 | 251.11182089999784 |
| 수정본 chaotic 전체 분석 | 63.42251259999466 |
| 수정본 전체 runner | **314.6772837000026** |
| 검토 전 첫 전체 실행 | 321.04941999999573 |
| 두 전체 실행 합계 | **635.7267036999983** |

60분 비용 한도 안에서 완료했다. 실제 이번 작업에는 두 전체 실행 및 별도 시험·구현 시간이 들었다.
runner의 `peak_rss_bytes` 원시 값은 0이었다. **신뢰할 수 있는 메모리 수치를 확보하지 못한 것으로 처리하며 0 bytes를 썼다고 해석하지 않는다.**

첫 전체 실행 보고서는 [원래 별도 경로](../reports/gate2c-home-pc-2026-10-01/gate2c_report.json)에 보존했다.
검토 수정 후 새 경로에서 전체 실행을 반복했다.
두 deterministic 객체는 수정본에 추가한 빈 `seal_failures=[]` 필드를 제외하면 완전히 같았다.
이 필드 추가 때문에 digest 자체는 달라졌다. 결과를 맞추기 위해 기준·초기조건·상한 구현을 바꾸지 않았다.

## 6. 최종 digest와 상태

수정본 보고서의 deterministic 객체를 다시 직렬화·SHA-256 계산하여 아래 값과 같음을 확인했다.

```text
a796c32a5be379c2cdfdd93757963ed92d981bf83dbd4c5e784d45c863fa3acc
```

| 기준 | 결과 |
|---|---|
| 계획 먼저 봉인 | SHA-256 봉인 당시 세 구현 파일 없음 기록; Git commit 아님 |
| 기존 입력 무결성 | 실행 전후 37개 입력 파일 unchanged |
| 전체 N 측정 | 두 궤도 완료 |
| replay 전제 | 비트 불일치 0, 알려진 전제 확인 |
| exact 국소 검사 | 6/6 위반 0 |
| raw cross 상한 위반 | 관측 가능한 유한 상한 구간에서 0 |
| REFUSED 기록 | scale 및 nonfinite 지점 보존 |
| 비용 | 60분 이내 |
| 효용 | regular prefix 100000 >= 사전 기준 17790 |
| Gate 2C 측정 | **PASS / LONG_REGULAR_PREFIX** |
| 새 adapter 독립 수치 감사 | **NOT_PERFORMED** |

최종 파일·결과는 [result_seal.json](../audit/gate2c/result_seal.json)에 raw SHA-256으로 기록한다.
현재 폴더에는 .git이 없으므로 커밋/HEAD 봉인은 하지 않았다.
해시와 로컬 기록은 제3자 서명이나 독립적인 역사 증명과 같지 않다.
이 실행에 대한 추가 실험이나 자동화 확장성 평가는 이번 범위에 포함하지 않았다.

재현하려면 이미 존재하는 보고서를 덮어쓰지 않는 새 경로를 지정한다.

```powershell
python run_gate2c.py --out reports/gate2c-reproduction-new
```
