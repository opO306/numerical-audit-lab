# Gate 0 벤치마크 3 — GenDot-derived fixture (설계자 승인 2026-10-01)

## 결정

- **채택:** Ogita, Rump, Oishi, "Accurate Sum and Dot Product", SIAM J. Sci. Comput. 26(6):1955–1988, 2005, **Algorithm 6.1 `GenDot`**.
- **확인한 사람:** 설계자가 원문을 직접 확인했다.
  - GenDot은 벡터 길이 `n`과 목표 조건수 `c`를 받아 매우 나쁜 조건의 `x, y`를 만든다.
  - `d`는 정확한 dot product를 nearest로 반올림한 값이고, `C`는 실제 조건수다.
  - 생성에 난수를 쓴다.
  - TUHH의 공개 demo는 `n=50`, `cnd=10^25`를 예로 든다.

**정확한 이름:** "공개된 고정 canonical test vector"가 **아니다**.
**"출판된 GenDot 알고리즘으로 한 번 생성해 동결한 benchmark fixture"**다.

## 고정 절차

1. 매개변수를 생성 **전에** 이 문서와 생성기에 고정한다. `n = 50`, `c = 10^25`, seed `20261001`.
2. `python -m benchmarks.gate0.gendot_generate`를 **한 번** 실행한다.
   - 생성기는 fixture가 이미 있으면 거부한다.
   - 결과가 마음에 들지 않아도(예: 실제 조건수가 목표와 다름) 다시 만들지 않는다.
3. fixture를 커밋하고 SHA-256을 `benchmarks/gate0/gendot.py`에 고정한다. 시험이 해시를 강제한다.
4. 그 뒤에야 판정 코드를 쓴다.

## oracle을 더 강하게

논문의 `d`를 믿지 않는다. Lab이 직접 구한다.

- **정확 유도 1:** binary64 비트 → 정확한 분수 → Σ xᵢyᵢ (Python `Fraction`)
- **정확 유도 2:** 비트를 정수 가수·지수로 직접 풀고, 정수 곱을 최소 지수에 맞춰 큰 정수로 더함 (분수·float 변환을 쓰지 않는 다른 코드 경로)
- **고정밀 교차검사:** mpmath `fdot`. 항들의 지수 범위가 계산 정밀도 안에 들어가는지 확인한 뒤에만 쓴다(선언 손실 0)
- **GenDot의 `d` 감사:** 생성기가 기록한 `d`가 Lab이 구한 정답을 올바르게 반올림한 값인지 독립 채점기로 판정한다. **논문 알고리즘의 출력도 채점 대상이다.**

## ⚠ 설계자 확인 필요: 생성기 재구성

작업 환경에서는 원문(tuhh.de, arxiv.org)에 접속할 수 없었다. 그래서 생성기는 **구현자가 기억으로 재구성한** 아래 절차를 따른다.
원문 Algorithm 6.1과 줄 단위로 대조해 주기 바란다.

```
n2 = round(n/2)
b = log2(c)
e = round(rand(n2,1)*b/2)          % 앞 절반의 지수, 0 … b/2
e(1) = round(b/2) + 1
e(end) = 0
x(1:n2) = (2*rand(n2,1)-1) .* 2.^e
y(1:n2) = (2*rand(n2,1)-1) .* 2.^e
e = round(linspace(b/2, 0, n-n2))
for i = n2+1:n
    x(i) = (2*rand-1) * 2^e(i-n2)
    y(i) = ((2*rand-1) * 2^e(i-n2) - Dot_(x(1:i-1)', y(1:i-1))) / x(i)
end
[~, ii] = sort(rand(n,1));  x = x(ii);  y = y(ii)     % 무작위 순서 섞기
d = Dot_(x', y)                                      % 정확한 dot을 nearest로 반올림
C = 2 * (abs(x') * abs(y)) / abs(d)
```

- `round`는 MATLAB 방식(0.5는 0에서 먼 쪽)으로 구현했다.
- 난수는 MATLAB과 다른 Python Mersenne Twister를 쓴다. 따라서 논문·demo와 **같은 벡터가 나오지 않는다.**
- **대조 결과 다른 점이 있으면:**
  - 이 fixture는 "GenDot을 변형한 생성기로 만든 fixture"로 이름을 고친다.
  - 필요하면 v2 fixture를 새로 만든다. v1은 지우지 않는다.
- 이 재구성이 틀려도 벤치마크의 **정답(oracle)과 판정은 틀리지 않는다.** 정답은 동결된 벡터에서 Lab이 직접 계산하기 때문이다.
  영향을 받는 것은 "GenDot으로 생성했다"는 이름뿐이다.

## Algorithm 6.1 줄 단위 대조 결과 (2026-10-01) → 이름: **GenDot-derived fixture**

원문 PDF는 이번에도 받지 못했다. tuhh.de, arxiv.org에 더해 저자 연구실(ogilab.w.waseda.jp)도 네트워크 정책에 막혔다.
검색 결과 요약에 원문 몇 줄이 인용되어 그 줄들만 대조할 수 있었다.

| # | 구현한 줄 | 원문 대조 | 근거 |
|---|---|---|---|
| 1 | `n2 = round(n/2)` | 부분 확인 | 검색 요약: "sets n2 = round(n/2)" |
| 2 | `b = log2(c)` | 미확인 | — |
| 3 | `e = round(rand(n2,1)*b/2)` | 미확인 | 검색 요약: 앞 절반은 "조건수에 맞춘 큰 지수 범위에서 무작위" (형태만 일치) |
| 4 | `e(1) = round(b/2)+1` | **확인** | 검색 인용 + 원문 주석 "ensures that exponents b/2 and 0 actually occur" |
| 5 | `e(end) = 0` | 간접 확인 | 위 주석이 지수 0이 나오도록 한다고 말함 |
| 6–7 | `x(1:n2)`, `y(1:n2) = (2*rand(n2,1)-1).*(2.^e)` | **확인** (식 형태) | 검색 인용 |
| 8 | `e = round(linspace(b/2,0,n-n2))` | 부분 확인 | 검색 요약: "uses linspace … decreasing exponent" |
| 9–12 | 뒤 절반 루프: `x(i)` 무작위, `y(i) = ((2*rand-1)*2^e - Dot_(…))/x(i)` | 부분 확인 | 검색 요약: "x_i randomly with decreasing exponent and calculating y_i such that some cancellation occurs". 정확한 식은 미확인 |
| 13 | 무작위 순서 섞기 | 부분 확인 | 설계자 요약 + 검색 요약("randomly permuting") |
| 14 | `d = Dot_(x',y)` | 확인(설계자) | 설계자: "d는 정확한 dot product를 nearest로 반올림" |
| 15 | `C = 2*(abs(x')*abs(y))/abs(d)` | **확인** | 검색 인용 |

**확실한 차이 1개:** 난수 발생기가 다르다. MATLAB `rand`가 아니라 Python Mersenne Twister를 쓰며, 둘은 seed 방식이 다르다.
따라서 이 fixture는 원문 코드로 재현되지 않는다.

**판정:**
- 15줄 중 원문 문자열로 확인된 것은 3줄(4, 6–7, 15)뿐이다. 나머지는 요약이나 설계자 설명과 형태만 일치한다.
- "동일"이라고 쓸 근거가 부족하므로, 설계자 지시에 따라 **`GenDot-derived fixture`**로 기록한다.
- fixture는 다시 만들지 않았고, SHA-256 `b9c97150…5582`를 그대로 유지한다.
- oracle은 계속 Lab의 정확 유리수 계산(두 경로)이다.

**나중에 올릴 수 있는 조건:** 누군가 원문 Algorithm 6.1과 위 표를 글자 단위로 대조해 차이가 없으면(난수 발생기는 제외),
이름을 `GenDot Algorithm 6.1 implementation (Python RNG)`로 올릴 수 있다. 그때도 fixture는 그대로다.
