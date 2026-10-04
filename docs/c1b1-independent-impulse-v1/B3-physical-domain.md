# B3 — Physical r_min / domain binding

- status: F-CLOSURE-1 FIX APPLIED / INDEPENDENT RECHECK PENDING / DESIGN ONLY / NOT IMPLEMENTED
- version: 2, 2026-10-05; closure audit snapshot `4cb2910fe936f7b1d5150196e062b6b61edc240f`의 최소 규범 정정
- dependencies: [domain data](../../specs/c1b1-independent-impulse-v1/physical-domain.json); B1/B2; unchanged Arithmetic geometry
- unresolved items: 선택한 Lab binding의 independent closure 승인; future composition 구현 검증
- what this does NOT certify: production 구현, 모든 입력의 finite-budget 성공, 물리 정확성, J verification, integration/trajectory/replay/N-Step, certification.

기존 [감사 대상 설계](../C1B1_INDEPENDENT_IMPULSE_V1_DESIGN.md)는 역사적 snapshot으로 보존한다. 이 후속 사양은 지정한 항목에 한해 옛 제안/U1–U8을 대체하며, 독립 closure 재검토의 `IMPLEMENTATION MAY START` 판정 전 소스 구현을 허용하지 않는다.

## 명시적 설계 선택

이 Lab V1의 physical binding으로 원본 후보를 **채택한다**. 사용자 요청의 B3 결정에 따른 저자 설계 선택이며 독립 closure 승인과 다르다. 코드/manifest의 PENDING을 바꾸지 않는다.

```text
bohr = 529177210903/10^12 Å
r_min = (6/5)/bohr = 1200000000000/529177210903 bohr
r_min² = 1440000000000000000000000/280028520539078142075409 bohr²
```

admission은 exact R² 비교로 force/sqrt/zero-component보다 먼저 처리한다. schema와 spec/identity 검증은 domain 판정보다 먼저다.

| 입력 separation | producer / 실행 의미 |
|---|---|
| R=0 | REFUSED / SINGULAR_SEPARATION / STOP; zero-vector shortcut 불가 |
| 0<R<r_min | REFUSED / PHYSICAL_DOMAIN / STOP |
| R=r_min | point ADMITTED; mathematical denominator 정칙; integrator 초기 입장 승인과 다름 |
| R>r_min | point ADMITTED; nonlinear proof 실패는 여전히 UNPROVED 가능 |

이 physical r_min은 point Impulse admission **및** future drift guard의 공통 threshold다. 정식 규범은 다음 두 단계다.

```text
Point admission:
    exact current R² >= r_min²

After drift:
    minimum over the exact unrounded closed relative segment >= r_min²
    AND
    stored final relative position squared >= r_min²
```

drift 이후에는 exact unrounded closed relative segment 전체의 minimum과 저장된 최종 상대 위치 한 점의 squared distance를 각각 검사한다. 두 조건을 모두 만족해야 한다. Arithmetic geometry는 이 두 supplied-threshold 검사를 수행하는 감사 완료 kernel이고, 실제 physical threshold provenance는 이 새 binding에서 나온다. Arithmetic 소스나 guard 알고리즘은 변경하지 않는다.

FX lattice의 R² denominator는 약분 후 2의 거듭제곱이다. r_min²의 위 분모는 약분됐고 1보다 큰 홀수다. 따라서 이 FX(96,48) lattice에서는 exact equality가 불가능하다. equality policy를 삭제하지 않으며 rational-domain boundary reasoning와 실제 FX fixture를 구별한다.

## I17 denominator regularity

admitted R>=r_min>0으로 1/R 및 BO i=-1 항이 정의된다. 모든 alpha/eta는 양수이고 factorial은 양의 integer다. 모든 B_m>0이므로 retardation D(R)=1+Σ B_m R^m>=1, D²>0이다. Taylor full tail은 반드시 n+2>x_hi를 증명한 다음 (n+2-x_hi)로 나눈다. 분모 interval lower<=0인 coarse enclosure에서는 가능한 refinement를 시도하거나 UNPROVED/STOP으로 끝내고 reciprocal을 만들지 않는다. ordered endpoints가 깨지면 programming anomaly/STOP이다.

기존 geometry의 q=r_i-r_j와 impulse의 q=r_j-r_i는 부호가 반대다. squared geometry만 불변이며 geometry vector를 force orientation으로 재사용하지 않는다. generic geometry PASS를 physical admission 완료나 J verification으로 소급 해석하지 않는다.
