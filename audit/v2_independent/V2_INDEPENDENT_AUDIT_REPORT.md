# numerical-audit-lab V2 독립 감사 보고서

감사 대상: 사용자 제공 `numerical-audit-lab.zip`의 봉인 V2 바이트.

## 최종 판정

**PASS**

- Critical: 0
- Major: 0
- UNRESOLVED: 0
- P1–P15: 전부 PASS
- Minor: 5

업로드 ZIP에는 `.git` 디렉터리가 없어서 commit/HEAD 자체는 검증할 수 없었다. 대신 `tests/test_v2_sealed.py`에 기록된 7개 SHA-256을 직접 재계산했고 전부 일치했다.

## 핵심 독립 증거

1. `python -m pytest -q` 전체 저장소: **177 passed**.
2. 독립 IEEE-754 경계 검사(`v2_boundary_audit.py`, 프로젝트 import 없음):
   - P1 targeted 14 cases PASS
   - P2 finite-convertible targeted 8 cases PASS
   - P3 exact rounding-cell targeted 14 cases PASS
   - `up(RN product)` targeted 9 cases PASS
   - F-SELF-1 targeted 31 cases PASS
   - F-SELF-1 subnormal grid 71,825 cases PASS
   - F-SELF-1 random finite nonnegative triples 120,000 cases PASS
3. 독립 primitive exact checker(`v2_primitive_independent_check.py`, 프로젝트 import 없음): **15,840 exact samples PASS**.
4. 독립 rebase exact checker(`v2_rebase_independent_check.py`, 프로젝트 import 없음): **34 cases PASS**, 예외 0.
5. 12-step exact-rational 재실행: 주 2 + holdout 4 = **6/6 PASS**. 최악의 `actual/bound`는 `holdout_chaotic_1`의 약 **0.822623**.
6. exact program 교차검사: 독립 Fraction step graph가 저장소 `exact_steps`와 regular/chaotic 각각 12 step 모두 정확히 일치.
7. exact time reversal: L=1,2,3,8,12에서 정확히 원상 복귀(P13 보조 근거).
8. 120 dps mpmath vs exact Fraction(12 step): 최대 차이 약 `1.03e-121`.

## P1–P15

| ID | 판정 | 독립 근거 요약 |
|---|---|---|
| P1 | PASS | `nextafter(v,+inf)`는 비음수 finite에서 v 이상, max finite에서는 +inf, +inf는 +inf, NaN 분기는 +inf. 0/-0/subnormal/binade/max를 직접 검사. |
| P2 | PASS | `float(q)`가 finite로 반환되는 경우, 결과가 q보다 작으면 바로 다음 float가 q 이상이라는 RN 성질로 증명. 아주 큰 Fraction은 CPython에서 `OverflowError`로 fail-stop하며 작은 bound를 반환하지 않음. |
| P3 | PASS | finite 결과 c의 RN rounding cell 반경은 normal에서 `|c|*2^-52`보다 작고, subnormal/0은 `TINY` 항이 덮음. max finite와 +inf도 보수적. exact cell 검사 PASS. |
| P4 | PASS | `δz=δa±δb+r`. 저장 계수의 1회 add/sub 반올림 오차를 좌표별 `rnd_err`로 잡아 공통 box에 합산. box 합·extra·rho 각 add 뒤 `up`. |
| P5 | PASS | `δz=xhat δy + yhat δx - δxδy + r` 직접 유도. mapping은 `xhat * b.coef + yhat * a.coef`로 맞음. 선형 coefficient storage error, box terms, `rad(a)rad(b)`, rho 모두 포함. F-SELF-1 별도 증명/공격 통과. |
| P6 | PASS | NEG는 finite float 부호 반전이라 수치값에 추가 반올림 없음. CONST는 represented result와 exact literal 차이를 Fraction으로 계산해 `up_q`. |
| P7 | PASS | rho는 represented operands/output의 exact Fractions로 `|z-(x op y)|`를 계산. SUT가 올바른 rounding이라는 가정에 의존하지 않음. |
| P8 | PASS | A의 float 원소를 exact Fraction으로 바꾼 뒤 Gauss-Jordan. `A^-1 M` 및 `A^-1[-w,w]`의 L1 행 상한 공식을 exact rational로 계산. 34 black-box rebase cases 독립 검증 PASS. |
| P9 | PASS | `c_ij=fl(A_ij r_j)`의 각 저장 반올림을 `rnd_err(c_ij)`로 row box에 합산. E는 각 `|A_ij|r_j`를 개별 upward product + upward sum으로 계산하고 box까지 더하므로 요구 상한 이상. |
| P10 | PASS | 건전성에 필요한 것은 A의 정확 직교성이 아니라 exact-rational invertibility. QR threshold는 A 선택/조임에만 영향. singular/실패는 예외 또는 비유한 bound로 fail-stop/unknown. |
| P11 | PASS | rebase 후 실제 `η=A^-1δ`를 `[-r,r]`로 감싸고 `η_j=r_j ξ'_j`로 새 기호를 도입하므로 이전 상관을 버리지만 집합은 확대됨. step 내부에서는 동일 ξ'를 공유. |
| P12 | PASS | SUT graph와 독립 Fraction graph를 직접 대조. `h=1/64`, `hh=1/128`, `two=2`, force/kick/drift/kick 순서 및 12-step 결과 일치. |
| P13 | PASS | `S=diag(1,1,-1,-1)`이면 reverse 시작 오차는 `Sδ`; 따라서 momentum form 계수만 부호 반전하고 box는 유지하는 것이 정확. exact reversal L=1,2,3,8,12 확인. |
| P14 | PASS | 120 dps 코드는 exact arithmetic에서 동일한 Verlet map과 대수적으로 동일. 엄밀 enclosure는 아니며 그 한계는 공개됨. 12-step exact와 차이는 약 1e-121 수준. |
| P15 | PASS | judge는 `n1_bad` 판정에만 쓰이고 `e_out` 계산에는 영향 없음. monkeypatch 전후 V1 bound 동일, `finally`로 정상/예외 양쪽 모두 judge 복원 확인. |

## F-SELF-1 독립 판정

원본 68–69행은 **현재 형태 그대로도 건전하다**.

`p,q,X >= 0`인 float라 하고

- `s = RN(p+q)`
- `t = RN(s+X)`
- `U(y) = nextafter(y,+inf)-y`

라 하자. 비음수 RN은 단조이므로 `t >= s`이고, binary64의 upward spacing은 비음수 영역에서 감소하지 않으므로 `U(t) >= U(s)`이다.

round-down 쪽 오차만 보면

- `(p+q)-s <= U(s)/2`
- `(s+X)-t <= U(t)/2`

따라서

`(p+q+X)-t <= U(s)/2 + U(t)/2 <= U(t)`.

그러므로 `nextafter(t,+inf) >= p+q+X`이다. subnormal에서는 spacing이 일정해 동일하고, binade 경계에서는 spacing이 증가하므로 더 안전하다. `X=0`도 동일하다. `t=max_finite` 또는 overflow면 `nextafter`가 +inf라 보수적이다.

자동 공격도 targeted 31 + subnormal grid 71,825 + random 120,000에서 반례가 없었다.

## 발견 사항

### MINOR-1: `up_q`의 매우 큰 Fraction은 +inf 반환이 아니라 `OverflowError` fail-stop

예: `up_q(Fraction(2)**2000)`에 해당하는 코드 경로는 CPython에서 `float(q)`가 `OverflowError`를 낸다.

- 작은 bound를 내지는 않으므로 soundness 위반은 아님.
- V2.1에서는 `OverflowError -> +inf`로 명시하면 계약이 더 깔끔하다.

### MINOR-2: F-SELF-1은 건전하지만 구현이 우연한 후속 보상에 의존

현재 증명은 성립한다. 그래도 유지보수 측면에서는 V2.1에서 68행 자체의 합도 명시적으로 upward-round하는 편이 안전하다.

### MINOR-3: 기존 `tests/test_v2.py`에는 실제 회귀 맹점이 있음

사본에서 `rebase`의 line 170을

`box = up(box + rnd_err(c))`

에서

`box = box`

로 바꾸면 coefficient-storage rounding enclosure가 사라져 **실제로 불건전**해진다. 그런데 `python -m pytest -q tests/test_v2.py`는 **12 passed**였다.

정확 반례 입력:

```python
M = [
 [1e-12, 2e-13, 0.0, 0.0],
 [-3e-13, 9e-13, 1e-14, 0.0],
 [0.0, 1e-14, 5e-13, -2e-13],
 [1e-15, 0.0, 3e-13, 7e-13],
]
w = [1e-16, 2e-16, 0.0, 5e-17]
xi = (-1,-1,-1,-1)
```

변이본에서 `D=A*diag(r)`, 저장 행렬을 `C=fl(D)`라 하면 이 vertex에 대해 exact rational 계산으로

`max_i |(C^-1 D xi)_i| = 1 + 1.066699945641295e-16 > 1`.

즉 box=0인 변이본 `C[-1,1]^4`가 의도한 `D[-1,1]^4`의 해당 점을 포함하지 못한다. 이 결함을 기존 S1이 놓친다.

### MINOR-4: F-SELF-2 확인

`E`에 coefficient-rounding box를 추가하는 것은 현재 δ의 component bound에는 불필요하게 보수적이다. 작은 bound를 만들지는 않는다.

### MINOR-5: P15 monkeypatch는 in-process thread-safe가 아님

현재 `run_v2.py`는 순차 실행이므로 문제 없음. 향후 같은 프로세스에서 병렬 스레드로 V1 audit를 돌리면 전역 `judge` 교체가 경쟁할 수 있다.

## 결론

현재 봉인 V2 바이트에 대해 실제 오차보다 작은 finite bound를 만들 수 있는 경로는 발견하지 못했다. 직접 유도와 독립 exact/Fraction 검사에 의해 P1–P15를 모두 PASS로 판정한다.

따라서 감사 계약 기준 최종 판정은 **PASS**다. Minor는 V2.1의 유지보수/회귀시험 강화 항목으로 넘기는 것이 맞고, 현재 V2를 수정해서 감사 대상을 바꾸면 안 된다.
