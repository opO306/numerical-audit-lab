# C1-B1 Arithmetic V1 독립 감사

## 최종 결론

**Overall audit: FAIL — F-CLAIM-1, Claim Adapter의 큰 정수 결과 직렬화 경계에서 비정형 예외가 누출됨.**

수치 커널 자체에 대해서는 `exact_slow`, `exact_fast`, `exact_geometry` 모두 아래 명시한 산술 계약과 범위에서 PASS다. FAIL의 원인은 drift/kick의 오답이나 허위 물리 인증이 아니다. 허용 길이의 외부 입력을 정확히 계산하고도 claim 비교 단계에서 일반 `ValueError`가 발생하여, 정상적인 비교 결과 또는 구조화된 `LabRefusal`을 반환하지 못한다.

```yaml
audited_commit: f806d8ce1ef86a0948b1a8abafe1a22c3058178b
base_commit: e976fa0fdeef16a27f112a0a4ee42494fe1e46b1
scope: ARITHMETIC_ONLY
impulse: J_NOT_VERIFIED
certification: NotCertified
exact_slow: DEFAULT / ARITHMETIC KERNEL REVIEW PASS
exact_fast: EXPERIMENTAL / OPT-IN / ARITHMETIC KERNEL REVIEW PASS
claim_adapter: FAIL
independent_review: COMPLETED_WITH_FINDING
overall_audit: FAIL
```

PASS는 이 커밋의 명시된 수학·구현에 대한 독립 검토 판정이다. 유한한 테스트 집합을 전체 물리 영역의 증명으로 해석하지 않는다. 독립 impulse, 실제 단위 binding, replay 및 formal certification으로 승격하지 않는다.

## 0. 대상 고정과 Git/provenance

대상 저장소는 `opO306/numerical-audit-lab`, 요청 브랜치는 `regular-2step-chain`이다. 기존 작업 트리를 사용하거나 수정하지 않고 별도의 임시 clone에서 대상 커밋을 감사했다. 감사 중 대상 구현 코드를 수정하거나 commit/push하지 않았다.

### 0.1 불변 커밋의 provenance: PASS

| 확인 항목 | 직접 확인한 값 |
|---|---|
| 감사 clone HEAD | `f806d8ce1ef86a0948b1a8abafe1a22c3058178b` |
| 대상의 직접 parent | `e976fa0fdeef16a27f112a0a4ee42494fe1e46b1` |
| base tracked files | 1,921 |
| target tracked files | 1,943 |
| base → target 기존 파일 수정 | 0 |
| base → target 기존 파일 삭제 | 0 |
| base → target 신규 파일 | 22 |
| 신규 파일의 실제 바이트와 target Git blob 대조 | 22/22 일치 |
| suite 전후 감사 clone의 tracked 변경 | 없음 |

`git ls-tree -rz`에서 경로, mode, object type, blob ID를 비교했다. 단순 diff 요약이나 구현자의 receipt를 근거로 파일 보존을 인정하지 않았다. 신규 파일은 실제 읽은 바이트로 Git blob SHA-1을 재구성하여 target tree의 object ID와 대조했다.

### 0.2 원격 브랜치 포인터: 시작 시 일치, 종료 전에는 불일치

**현재 브랜치가 계속 target을 가리킨다는 주장은 최종 확인 시 FALSE다.**

2026-10-04 **10:10:39Z**에 기록한 `git ls-remote` 결과는 target `f806d8c`였다. 그러나 감사 종료 전 GitHub branch API 재조회 결과는 다음과 같다.

```yaml
remote_branch_head: 433be43ee6aca31f3a4cb76094a19d50e2cbefa8
its_parent: f806d8ce1ef86a0948b1a8abafe1a22c3058178b
its_committer_timestamp: 2026-10-04T10:34:59Z
new_commit_independently_audited_here: false
```

위 시간은 후속 커밋의 committer timestamp이며 실제 push 시각으로 단정하지 않는다. 이 변화는 감사 snapshot의 변조가 아니라 mutable branch가 후속 커밋으로 이동한 것이다. **본 판정은 끝까지 `f806d8c`에만 적용한다.** `433be43`에 결함이 남았거나 수정됐다는 판단은 하지 않았다.

### 0.3 과거 preservation receipt: 시간 구분 PASS

실제 receipt 파일을 읽었다. 기록 시각은 **2026-10-04 02:40:14.861257Z**, 기록 HEAD는 base `e976fa0`, `commit_or_push_performed=false`였다. 대상 커밋의 committer timestamp는 **02:50:38Z**로 그 뒤다. Receipt의 20개 신규 파일 바이트 SHA-256도 target 파일과 직접 대조하여 일치했다. Git의 신규 파일 22개에는 이 receipt 목록에 없는 두 `.gitattributes`가 포함된다.

따라서 receipt 작성 당시 “아직 commit/push하지 않았다”와 이후의 target commit 존재는 모순이 아니다. 다만 receipt는 현재 원격 포인터를 보증하는 문서도 아니다.

증거: `remote_evidence/remote_measurement_extract.json`의 `provenance`, `receipt`; `remote_branch_final_observation.json`; `remote_evidence/suite.log`.

## 항목별 판정표

| 항목 | 판정 | 결정 근거 |
|---|---|---|
| A1 Semantic Manifest | PASS | 직접 SHA-256 및 산술 의미·범위·검사 순서 검토 |
| A2 exact_slow | PASS | 별도 정수 유리수 oracle, exhaustive/edge 검사, 저장 위치 식 직접 확인 |
| A3 exact_fast drift | PASS | 음수 floor/divmod 증명, 독립 반올림 검사, unreduced ratio 및 endpoint 검증 |
| A4 Kick | PASS | 동일 격자의 정수 연산 유도, signed/overflow/order/immutability 검사 |
| A5 Geometry / Guard | PASS | 볼록 이차식 유도와 별도 외적 기반 oracle, exact endpoint/strict equality 검사 |
| A6 공통 dependency | PASS | geometry·validation을 별도 기대값으로 검사; slow==fast만으로 판정하지 않음 |
| A7 독립성 경계 | PASS | 신규 production 소스/호출 경계 검토, 실행 import/file 접근 방어 재실행; 작성 이력 인증은 아님 |
| A8 Mutants | PASS | 기존 16개 실제 mutant 재실행 + 별도 손계산 기대값으로 16/16 검출 |
| A9 Claim Adapter | **FAIL** | 성공 결과의 scope 비승격은 PASS이나, F-CLAIM-1로 외부 claim 처리의 구조화된 실패 계약이 깨짐 |
| A10 관련 test suite | PASS | 실제 105 passed 재실행. Repository full suite 판정이 아님 |
| A11 Benchmark | PASS | 저장 raw samples의 median/ratio, source binding, 계측 검산 및 새 실행 재현 |
| A12 알려진 미해결 | **UNRESOLVED** | 물리 binding, impulse, replay, trajectory, formal certification은 이번 감사로 닫지 않음 |

## A1. Manifest

직접 계산한 SHA-256:

```text
3217fc38aa798fff3ffea8072cecafaecac9f98be85589e9fa35a9dc6aa8119b
```

제시값과 일치하며 import-time pin 및 sidecar도 일치한다. 검토한 의미는 다음과 같다.

| 의미 | 판단 |
|---|---|
| signed FX raw 범위 | `-2^(W-1) <= raw <= 2^(W-1)-1`로 일관됨 |
| 지원 grid | W는 2..4096, F는 0..W-1; exact int/type/metadata 검증 |
| 반올림 | nearest-even; wrap/saturate가 아니라 범위 초과 거부 |
| drift v2 | displacement를 position grid로 한 번 반올림한 뒤 stored position에 정수로 더함 |
| exact displacement / endpoint | 저장 displacement/position과 구분하여 보존 |
| kick | i는 J를 빼고, j는 J를 더함; impulse와 momentum grid 일치 필요 |
| component order | i.x, i.y, i.z, j.x, j.y, j.z |
| drift refusal order | 입력 검증 후 각 component의 displacement range, position range 순서 |
| guarded drift | threshold 입력 검증, drift 산술/범위, segment guard, stored guard 순서 |
| intrusion | 오직 `min_R2 < r_min_squared` 또는 stored_R2의 같은 strict 비교 |
| equality | equality는 허용; 두 guard에서 동일 |
| 물리 범위 | supplied exact threshold만 다룸; 실제 r_min binding 미완료 |

내부 커널이 unreduced Ratio를 허용하는 것과 외부 wire가 canonical coprime rational을 요구하는 것은 서로 다른 층의 계약이며 모순이 아니다. 수학적 의미의 내부 모순은 발견하지 못했다. 출력 직렬화 크기의 처리 누락은 A9의 구현 경계 결함으로 별도 판정한다.

## A2–A3. Drift와 nearest-even의 독립 검증

### 정확한 식

`S_p=2^Fmom`, `S_r=2^Fpos`, `dt=a/b`, `mass=c/e`라 두면, 유효 입력에서 b,c,e는 양수다.

\[
p=\frac{p_{raw}}{S_p},\qquad
 d=\frac{p_{raw}ae}{S_pbc}=\frac ND.
\]

저장 displacement와 stored position은 다음이다.

\[
\Delta r_{raw}=\operatorname{RN}_{even}(S_r d),\qquad
r'_{raw}=r_{raw}+\Delta r_{raw}.
\]

반면 exact endpoint는 다음이다.

\[
r_{exact,new}=\frac{r_{raw}}{S_r}+d
=\frac{r_{raw}D+NS_r}{DS_r}.
\]

Slow는 Fraction으로 이 의미를 계산한다. `stored_exact*S_r`는 정수이므로 `.numerator` 사용도 이 경로에서는 정확히 `r_raw+delta`와 같다. Fast는 같은 endpoint를 unreduced 정수 pair로 만든다. 두 구현의 코드를 서로 oracle로 삼지 않고 위 식에서 직접 결과를 만들었다.

### `r+round(d)`와 `round(r+d)`는 다르다

position grid의 F=0, `r_raw=1`, `d=1/2`일 때 계약상 delta는 0이고 stored position은 **1**이다. `round(1+1/2)`를 사용하면 **2**로 달라진다. `d=-1/2`도 반대 방향의 차이를 만든다. 두 경로 모두 displacement를 먼저 반올림한다. 이에 대한 실제 source mutant 6 역시 검출됐다.

### 음수 U에 대한 Fast의 반올림 증명

D>0이면 유클리드 나눗셈으로 유일한 정수 q,r이 존재하여

\[
U=qD+r,\qquad 0\le r<D
\]

이다. 따라서 `U/D=q+r/D`는 q와 q+1 사이에 있으며 두 정수까지의 거리는 `r/D`와 `(D-r)/D`다. `2r<D`, `2r>D`, `2r=D` 분기와 tie에서의 q parity는 U가 음수여도 그대로 성립한다.

예를 들어 `U/D=-3/2`이면 q=-2, r=1이므로 짝수 -2를 고른다. `-5/2`에서는 q=-3이므로 q+1=-2를 고른다. 이 구현의 negative floor semantics는 오류가 우연히 가려지는 의존성이 아니라 **증명에 사용되는 명시적인 semantics**다.

감사 oracle의 반올림은 이 구현을 복사하지 않았다. 절댓값에 대한 양수 정수 나눗셈만 사용하여 후보 정수의 절대 거리를 비교하고, 마지막에 부호를 복구한다. 별도의 brute nearest-integer 탐색과도 3,220건 대조했다.

| 값 | nearest-even |
|---|---:|
| 0 | 0 |
| 1/2, -1/2 | 0, 0 |
| 3/2, -3/2 | 2, -2 |
| 5/2, -5/2 | 2, -2 |
| 49/100, 51/100 | 0, 1 |
| -49/100, -51/100 | 0, -1 |

### gcd reduction을 생략해도 의미가 바뀌지 않는 이유

양의 공통 인자 k를 곱한 `(kN,kD)`는 동일한 유리수다. `U=qD+r`에 같은 k를 곱하면 `kU=q(kD)+kr`이고, quotient와 q parity는 그대로이며 `2kr` 대 `kD`의 비교도 같다. Exact endpoint는 교차곱으로 같은 값임을 확인할 수 있다. 결국 저장 delta와 position이 같으므로 range/refusal 결과도 같다. 단, 큰 중간 정수의 자원 비용까지 같다는 뜻은 아니다.

### 독립 실행 범위

| 검사 | 입력/검사 수 |
|---|---:|
| 반올림 유리수 셀, numerator -1024..1024, denominator 1..128 | 262,272; 각 셀을 두 구현에 대조 |
| 큰 정수 ties/neighbors/unreduced | 891 |
| 작은 grid drift 전수 | 34,560 |
| 임의 6-lane drift | 2,400 |
| 등가 unreduced drift | 2,400 |
| drift range/overflow edge | 324 |
| drift 다중 실패 순서 | 6 |
| 별도 guarded random cases | 400 |

큰 경계 검사에는 W=4096도 포함된다. Positive/negative tie, even/odd quotient, zero, exact limit, overflow ±1, displacement 범위와 position 범위의 분리를 검사했다. 예를 들어 저장 위치 합이 range 안으로 돌아오더라도 stored displacement 자체가 range를 벗어나면 먼저 거부해야 하는 계약을 검사했다.

증거: `independent_audit.py`, `independent_results.json`, `independent_audit.log`.

## A4. Kick

같은 grid의 간격을 `S=2^Fmom`이라 하면

\[
\frac{p_i}{S}-\frac J S=\frac{p_i-J}{S},\qquad
\frac{p_j}{S}+\frac J S=\frac{p_j+J}{S}.
\]

분자는 이미 정수이므로 successful update에는 추가적인 반올림 판단이 필요 없다. Slow가 exact 값에 적용하는 nearest-even도 이 경우 정수를 그대로 돌려준다. Fast의 직접 정수 덧셈·뺄셈과 동치다. 성공 시 두 atom의 momentum 합도 정확히 보존된다. 이는 **supplied J의 적용**에 관한 증명이며 J의 물리식을 증명한 것이 아니다.

작은 grid 4,608건 전수, 6-lane random 2,400건, range edge 60건, 다중 오류 순서 6건을 별도 정수 oracle과 대조했다. Positive/negative/zero J, min/max, exact limit, overflow ±1, i-before-j를 포함한다. 두 구현 모두 입력을 변경하지 않고 지역 결과만 쌓은 뒤 전체 성공 시 frozen result를 반환한다. 실패 입력의 전후 값도 독립 checker에서 비교했다.

## A5. Geometry / Guard

독립 유도는 다음 이차식에서 시작한다.

\[
f(t)=|q_0+t v|^2=A+2Bt+Ct^2,\quad 0\le t\le1.
\]

`C=|v|^2 >= 0`이다. C=0이면 v=0이므로 minimum은 A다. C>0이면 볼록한 이차식이며, 도함수 `2B+2Ct`의 영점을 닫힌 구간으로 제한하여 `tau=clamp(-B/C,0,1)`을 얻는다. 따라서 구현의 닫힌 선분 최소 공식은 맞다.

감사 oracle은 같은 closest-point 평가 코드를 복사하지 않았다. 시작점/끝점의 도함수 부호로 endpoint 경우를 나누고, interior에서는 별도의 외적 항등식

\[
\min f=\frac{|q_0\times q_1|^2}{|q_1-q_0|^2}
       =\frac{AC-B^2}{C}
\]

을 사용했다. 정수 pair 유리수로 모든 값을 계산한다.

검사 결과는 정수 좌표 전수 2,187건, 유리수 geometry 및 threshold equality/바로 위·아래 6,000건, 별도 hand-derived guard 4건, invalid geometry 5건 PASS다. Endpoint/interior minimum, C=0을 모두 포함한다.

### Exact endpoint와 stored endpoint를 구분해야 하는 실제 예

Fpos=0, 상대 위치 q0=1, 상대 drift=-1/4, threshold=81/100일 때:

- exact endpoint는 3/4이고 선분 minimum은 9/16이므로 intrusion이다.
- rounded displacement는 0이고 stored endpoint는 1이므로 stored guard만으로는 intrusion을 찾지 못한다.

실제 `guarded_drift`는 SEGMENT_INTRUSION을 반환한다. Rounded endpoint를 segment endpoint로 바꾼 source mutant는 검출된다.

다른 예로 q0=2, exact drift=-4/5, threshold=121/100이면 exact endpoint는 6/5이고 선분 minimum은 36/25이므로 segment는 허용된다. 그러나 stored endpoint=1이므로 **STORED_INTRUSION**이다. 두 guard가 독립적으로 동작함을 확인했다. 두 조건이 동시에 실패하면 segment가 먼저다.

Threshold와 minimum이 정확히 같은 경우는 두 guard에서 허용된다. Manifest와 구현 모두 `<`이며 `<=`가 아니다.

## A6. 공통 dependency 위험

독립 oracle은 자체 Euclidean gcd와 normalized integer-pair `Q`를 사용했다. Fraction은 slow rounding helper에 테스트 입력을 전달할 때만 사용했으며, 기대값의 반올림·drift·kick·geometry 계산을 Fraction이나 대상 helper에 맡기지 않았다.

Validation은 대상 `validate_*`를 oracle로 호출하지 않고 예상한 refusal code/phase/atom/component를 정해 100개 input case, 총 200개 kernel 호출로 확인했다. Bool-as-int, 잘못된 width/F/type, grid metadata lookalike, 다른 impulse grid, 잘못된 rational denominator/mass, raw range 및 입력 순서 등을 포함한다. 성공/실패 시 입력 불변도 함께 확인한다.

따라서 이 판정은 slow==fast agreement를 전체 정확성의 증거로 사용하지 않는다. 다만 두 경로와 감사 코드가 Python의 arbitrary-precision int와 실행 환경을 공유한다는 신뢰 기반까지 제거한 것은 아니다. Python interpreter/stdlib/hardware에 대한 formal verification을 주장하지 않는다.

## A7. 독립성 경계

신규 production 여섯 모듈의 import와 호출 구조를 직접 읽고 AST로 점검했다. `a_reference`, `a_numeric`, 원본 c1b1 helper, 숨은 subprocess oracle, source extraction/exec, 원본 함수의 FunctionType 복제 또는 monkeypatch 호출 경로는 신규 production 코드에서 발견하지 못했다. Slow와 fast의 arithmetic/rounding helper도 서로 호출하지 않는다. Fast의 drift/kick kernel은 Fraction을 사용하지 않으며, Fraction은 공통 geometry 경계에서 사용된다.

원본의 `c1b1_combined_arithmetic.py`, `c1b1_fast_impulse.py`, `c1b1_impulse_primitives.py` 및 `c1b1_two_atom.py`의 관련 계약/구조도 비교 자료로 읽었다. 원본의 prepared contract, original helper 호출, FunctionType rebinding 구조는 신규 Lab kernel의 실행 경로에 없다. **현재 소스의 독립 실행 경계를 확인한 것이며, 구현자가 과거에 무엇을 읽었는지까지 인증한 것은 아니다.** 실행되지 않은 전체 원본 함수 AST의 자동 동일성 검사 결과를 주장하지 않는다.

Full repository의 parent `independent_checker/__init__.py`에는 legacy `.audit/.hard_cases/.oracle` import가 존재한다. 따라서 “새 계산기를 import하면 신규 파일만 로드된다”고 주장하지 않는다. 그러나 원본/numeric_core 접근을 차단하는 fresh interpreter test는 실제로 통과했고, 그 test는 의도적인 금지 import와 원본 경로 open이 먼저 차단되는지 확인하여 방어가 비어 있지 않음을 검사한다.

별도의 실행 trace에서는 benchmark의 8개 입력에 대해 각 경로의 24개 stage를 직접 검사했다. 실제 kernel 호출 파일은 각자 `exact_slow.py` 또는 `exact_fast.py`, 공통 `contracts.py`, 공통 `exact_geometry.py`뿐이었다. 반대 arithmetic path, compare, claim_adapter 호출은 없었다. 이 trace는 hash-검증한 core snapshot에서 실행했으며, full-package startup은 별도의 원격 105개 suite 결과와 구분한다.

증거: `supplemental_checks.py`, `supplemental_results.json`, `remote_evidence/suite.log`의 boundary/independence 항목.

## A8. 16개 실제 source mutant

기존 mutation harness는 소스 파일을 복사하고 지정 문자열을 실제로 교체한 뒤 compile/import하여 실행한다. 매 경우 baseline이 먼저 통과해야 하며, mutant의 예상 assertion failure만 검출로 인정한다. 그 harness를 다시 실행했고, 저장된 mutant SHA와 새 실행의 mutant SHA 및 edit가 16개 모두 같았다.

추가로 별도 mutation driver를 작성했다. 이 driver는 **slow와 compare를 import하지 않으며**, 손으로 유도한 raw/rational/refusal 기대값으로 mutant를 판정한다. 두 driver 모두 16개 baseline PASS 및 16개 mutant DETECTED다.

| ID | 실제 변경한 결함 | Baseline | Mutant |
|---|---|---|---|
| 1 | ties-away | PASS | DETECTED |
| 2 | mass denominator factor 누락 | PASS | DETECTED |
| 3 | denominator의 2^Fmom 누락 | PASS | DETECTED |
| 4 | mass numerator/denominator swap | PASS | DETECTED |
| 5 | dt numerator/denominator swap | PASS | DETECTED |
| 6 | round(r+d)로 변경 | PASS | DETECTED |
| 7 | rounded endpoint로 segment guard | PASS | DETECTED |
| 8 | kick sign swap | PASS | DETECTED |
| 9 | displacement/position/momentum range check 제거 | PASS | DETECTED |
| 10 | j-before-i 검사 순서 | PASS | DETECTED |
| 10_write | early input mutation | PASS | DETECTED |
| 11 | stale coefficient cache | PASS | DETECTED |
| 12 | wrong impulse grid를 강제로 맞춰 fast 진행 | PASS | DETECTED |
| geometry_tie | strict <를 <=로 변경 | PASS | DETECTED |
| geometry_tau | -B/C 부호 오류 | PASS | DETECTED |
| geometry_stored | stored guard 비활성화 | PASS | DETECTED |

이는 이 16개 변이에 대한 방어 PASS이지 모든 결함에 대한 완전성 증명이 아니다. 특히 이번에 찾은 F-CLAIM-1은 이 mutation panel에 없으므로 16/16 검출과 양립한다.

증거: `independent_mutants.py`, `independent_mutants.json`, `independent_mutants.log`; 원격 실제 재실행 결과는 measurement extract의 `mutants`와 suite log.

## A9. Claim Adapter — FAIL

### 성공 결과의 비승격: PASS

별도 정수 oracle에서 만든 외부 claim 44건이 예상한 ARITHMETIC_MATCH를 반환했다. 틀린 endpoint, 잘못된 scope/spec/J status, 비정규 정수 표기, 중복 JSON key, NaN, 큰 wire, opt-in 누락도 검사했다. Matching refusal은 `calculation_status=REFUSED`로 보존되어 accepted transition으로 승격되지 않는다. 성공/비교 결과는 `ARITHMETIC_ONLY`, `J_NOT_VERIFIED`, `external_compatibility=NOT VERIFIED`를 유지한다.

`REPLAY_VERIFIED`, `CONFIRMED`, `CERTIFIED` 또는 physical correctness로 자동 승격되는 경로는 발견하지 못했다.

### F-CLAIM-1: 유효 길이 입력으로 만든 결과를 직렬화하다 일반 ValueError 누출

영향 위치:

```text
independent_checker/c1b1/claim_adapter.py:158  expected = canonical_data(computed)
independent_checker/c1b1/claim_adapter.py:95   str(value.denominator // divisor)
```

정확한 반례를 다음처럼 간단히 표시할 수 있다.

```text
x = 10^2150
position_grid = momentum_grid = Grid(8, 0)
r_i = r_j = (0,0,0)
p_i = (1,0,0), p_j = (0,0,0)
mass_i = (x+3)/1
mass_j = 1/1
dt = 1/(x+1)
```

각 큰 입력 정수는 2,151자리로 adapter의 4,096자리 제한보다 작다. Wire는 약 5.9 KB이며 1 MiB보다 훨씬 작다. 모든 입력 rational은 canonical/coprime이다. 제공한 claim은 exact displacement/endpoint까지 모두 0이라고 주장하는 **틀렸지만 형식상 유효한 claim**이다. 그 claim의 정수는 모두 짧다. “정답 claim에 4,301자리 정수를 넣었으니 원래 wire 제한 위반”이라는 반례가 아니다.

실제 exact displacement는

\[
d_i=\frac{1}{(10^{2150}+1)(10^{2150}+3)}
\]

이고 denominator는 4,301자리다. 두 산술 kernel 모두 이를 정확하게 계산하며 stored displacement와 stored position은 0이다. 그러나 `compare_claim`는 비교 결과를 만들기 전에 computed value를 decimal string으로 바꾼다. 실행 환경의 int→decimal string 기본 제한 4,300자리를 넘어 다음 예외가 발생한다.

```text
ValueError: Exceeds the limit (4300 digits) for integer string conversion
isinstance(exception, LabRefusal) == False
```

**Python 3.13.5 core snapshot과 실제 full repository의 Python 3.12.7에서 slow/default 및 fast/opt-in 모두 재현했다.** 전역 integer-string limit를 낮추거나 바꿔서 만든 반례가 아니다.

기대되는 처리는 ARITHMETIC_MISMATCH 또는 계약으로 정한 구조화된 output/resource refusal이다. 실제 동작은 일반 ValueError 누출이다. 잘못된 결과를 MATCH로 인정한 사례는 아니지만, 외부 claim API의 정의된 결과/실패 경계를 닫지 못한다.

### 수정 권고 — 구현은 하지 않음

입력 크기 한도와 별개로 **결과 직렬화 크기의 한도와 거부 계약**을 명시해야 한다. Decimal string으로 만들기 전의 정확한 정수 크기 검사, 제한 초과에 대한 결정적인 LabRefusal, slow/fast 동일 처리 및 scope/J status 보존이 필요하다. 새 failure code/phase를 추가한다면 frozen manifest와 wire 계약에 대한 변경 검토도 필요하다.

전역 `sys.set_int_max_str_digits(0)`으로 제한을 없애는 것을 수정 완료로 간주하지 않는다. 이번 반례의 두 경로, false-but-well-shaped claim, 실패 시 불변성, 출력 한도 바로 아래/같음/위, 그리고 기존 105개와 mutant panel을 회귀 검사해야 한다.

재현: `reproduce_claim_boundary.py`, `claim_boundary_reproduction.json`, `claim_boundary_reproduction.log`; 원격 Python 3.12 traceback은 `remote_evidence/remote_measurement_extract.json`의 `claim_counterexample`.

## A10. 관련 suite 재실행

실제 결과:

```text
105 passed in 3.94s
subprocess exit = 0
```

대상은 신규 7개 test module에 기존 `test_independence.py`, `test_provenance.py`를 포함한 관련 suite다. 명령 전체와 각 test의 실제 출력은 `remote_evidence/suite.log`에 있다. 이 결과는 수학 증명의 대체물이 아니며 **repository FULL PASS가 아니다**. F-CLAIM-1이 이 suite에서 빠져 있기 때문에 105 PASS와 overall FAIL은 모순이 아니다.

## A11. Benchmark 검산

저장/새 실행 모두 각 행의 wall 및 CPU raw sample 9개를 정렬하여 다섯 번째 값을 직접 선택했다. Median/min/max와 slow/fast ratio를 다시 계산했고 저장 요약과 일치했다. 두 보고서의 implementation SHA-256도 감사 target source와 일치했다.

### Wall-clock median, 1 invocation당 microseconds

| 획득 | Workload | Slow µs | Fast µs | Slow/Fast |
|---|---|---:|---:|---:|
| 저장 raw samples 재계산 | Drift | 84.039929 | 14.375039 | 5.846240 |
| 저장 raw samples 재계산 | Kick | 45.424428 | 7.473641 | 6.077952 |
| 저장 raw samples 재계산 | supplied-J K–D–K + exact guards | 262.452130 | 115.595093 | 2.270444 |
| 이번 독립 실행 | Drift | 82.647049 | 14.749386 | 5.603423 |
| 이번 독립 실행 | Kick | 48.266619 | 7.478162 | 6.454343 |
| 이번 독립 실행 | supplied-J K–D–K + exact guards | 249.328170 | 109.932545 | 2.268011 |

저장 자료의 84.04/14.38/5.85x, 45.42/7.47/6.08x, 262.45/115.60/2.27x는 반올림된 표시로 맞다. 새 실행은 같은 Windows/Python 3.12.7 환경에서 별도 획득했고, 동일한 숫자를 복사한 것이 아니다. CPU raw sample도 함께 검산했으며 Windows CPU clock 양자화는 측정 제약으로 남는다. 장기 처리량이나 다른 하드웨어로의 일반화는 하지 않는다.

### 실제 연산 계측

아래 수치는 paired panel의 **8개 input invocation 합계**다. 하나의 invocation당 수치나 CPU의 모든 내부 연산 수가 아니다.

| Count | Slow | Fast |
|---|---:|---:|
| Fraction constructions | 2,072 | 512 |
| math.gcd calls | 2,128 | 664 |
| 계측 범위의 integer multiply | 3,296 | 1,296 |

Fraction constructions는 `Fraction.__new__`와 `_from_coprime_ints` 경로를 합한 값이다. 별도로 ordinary source에 직접 profiler를 걸어 Fraction과 gcd를 세었으며, AST-instrumented 수치 및 새 실행 수치와 같았다. Integer multiply는 명시된 Python AST 연산 범위이며 native bigint 내부 곱셈 수가 아니다.

계측 wrapper는 해당 연산자를 실행하면서 counter를 올린다. 새 benchmark 자체의 ordinary/instrumented 대조 외에 별도 recursive rational/dataclass 비교로 48개 output을 대조하는 검사도 실행했다. 이 equivalence 검사는 해당 panel의 실행 결과에 한정하며, 모든 가능한 Python 객체에서 AST rewrite가 의미 보존한다는 주장은 하지 않는다. 타이밍 구간은 profiler 없는 ordinary source다.

또한 panel의 첫 kick → drift/guard → 마지막 kick 기대값을 감사 oracle에서 독립적으로 구성하여 8개 입력×2경로×3stage=48회를 검사했다. 다음 stage의 입력을 대상 출력에서 무비판적으로 가져오지 않았다. 이 workload는 두 kick에서 supplied J를 재사용하는 synthetic arithmetic transition이다.

**이것은 full C1-B1 audit 2.27x, 전체 세계 2.27x, 물리 verifier 2.27x가 아니다.** 독립 impulse와 physical binding이 없으므로 full C1-B1 audit speedup은 측정되지 않았다.

증거: `remote_evidence/remote_measurement_extract.json`에는 원본/새 보고서의 raw rows, 각 보고서 파일의 SHA-256, runtime/processor 및 계측 범위가 들어 있다. 이는 원본 benchmark JSON 전체 바이트의 복사본이 아니라 raw sample과 검증 필드를 보존한 발췌다. `verify_saved_samples.py`로 다시 계산할 수 있다.

## A12. 닫히지 않은 항목

| 항목 | 상태 |
|---|---|
| 실제 1.2 angstrom → bohr r_min binding | UNRESOLVED |
| 독립 impulse 계산 | UNRESOLVED |
| J physical correctness | UNRESOLVED / J_NOT_VERIFIED |
| 원본 executor detailed exception compatibility | UNRESOLVED |
| Full C1-B1 replay | UNRESOLVED |
| 전체 physical domain | UNRESOLVED |
| Trajectory correctness | UNRESOLVED |
| Formal certification | UNRESOLVED / NotCertified |

## 별도 최종 판정

| 대상 | 판정 | 범위/제한 |
|---|---|---|
| C1-B1 Arithmetic V1 exact_slow | PASS | drift/kick/guard의 명시된 산술 kernel; DEFAULT 유지 |
| C1-B1 Arithmetic V1 exact_fast | PASS | 같은 산술 kernel; EXPERIMENTAL/OPT-IN 유지 |
| exact_geometry | PASS | supplied exact threshold에 대한 geometry/guard |
| independence boundary | PASS | 현재 소스의 실행 의존 경계; 작성 이력이나 runtime 자체의 인증 아님 |
| mutant defense | PASS | 명시한 실제 16개 source mutant에 한정 |
| benchmark claim | PASS | synthetic ARITHMETIC_ONLY timing/count와 source binding |
| overall audit | **FAIL** | F-CLAIM-1이 남은 target `f806d8c`의 전체 제출물 |

## 실행 환경과 자료 해석

기존 suite와 benchmark 및 원격 반례 재현은 Windows 11, Python 3.12.7, pytest 9.1.1에서 수행했다. 독립 정수 oracle, 별도 mutant 검사 및 supplementary panel 검사는 Linux/Python 3.13.5에서 hash-검증한 동일 core bytes로 수행했다. Core snapshot에는 기존 parent package initializer를 복사하지 않았으므로 full-package startup의 근거는 원격 suite와 구분했다.

`independent_results.json`의 `boundary_bug_reproduction.status=PASS`는 “반례 재현에 성공”이라는 뜻이다. 같은 파일의 `claim_serialization_counterexample.verdict=FAIL`이 adapter 판정이다. 이를 adapter PASS로 읽으면 안 된다.

이 패키지에는 독립 checker 소스, 실행 로그, 실제 원격 suite 로그, raw benchmark sample 발췌, mutant 결과와 재현 소스가 포함된다. 완전한 원격 측정 원본과 감사 작업 파일은 사용자 PC의 다음 임시 디렉터리에 남아 있다.

```text
C:\Users\zun24\AppData\Local\Temp\independent_c1b1_f806d8c_o8jnu8ki
```

그곳의 `remote_evidence.zip` SHA-256은 다음이며, 이것을 이 다운로드 패키지 ZIP의 hash와 혼동하면 안 된다.

```text
e6bb3651a00dd4d5dbb55c8a9fc10881883f6adbedcbd92a9e4a90909da00382
```

본 패키지로 옮긴 compact 원격 증거 ZIP은 실제 바이트 SHA-256 및 ZIP CRC를 확인한 뒤 풀었다.

```text
c9586612f5d638a78bd7e143b22d810d92c827debdc95ee1d4ad5c108d61b862
```

### 외부 언어 semantics 참고

Python 3.12 공식 문서의 Built-in Types / Integer string conversion length limitation과 Expressions / Binary arithmetic operations를 확인했다. 기본 4,300자리 제한과 integer floor/divmod semantics에 대한 참고이며, 대상 구현의 correctness를 문서 주장만으로 인정한 것은 아니다. 해당 동작은 실행에서도 확인했다.

```text
https://docs.python.org/3.12/library/stdtypes.html#integer-string-conversion-length-limitation
https://docs.python.org/3.12/reference/expressions.html#binary-arithmetic-operations
```
