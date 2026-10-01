# Gate 2B — 공개 제3자 Hénon–Heiles 구현 감사: 계획 (봉인)

이 문서는 **외부 코드로 궤도를 한 번도 실행하기 전에** 커밋한다.
지금까지 한 일은 소스 읽기, 설치, `import` 확인뿐이다. 결과를 본 뒤 이 문서를 고치지 않는다.

**질문:** 공개된 제3자 Hénon–Heiles 구현을, 구현자(gala 개발자)에게 정답이 주어지지 않은 상태에서,
감사된 V2([BINARY64_TOLERANCE_RULE_V2](BINARY64_TOLERANCE_RULE_V2.md))와 독립 물리·구조 검사로 감사하면 실제로 추가 신뢰성 정보를 줄 수 있는가?

- 외부 코드는 **수정하지 않는다.** 필요한 연결은 Lab 쪽 adapter에서만 한다. gala 모듈 속성에 값을 대입하거나 monkeypatch하는 것도 금지한다.
- 연속 물리(방법 층 B)는 이번에도 인증하지 않는다.

## 1. 후보 조사

| 항목 | **gala 1.12.0** (선정) | galpy 1.12.0 (예비, 이번 범위 아님) |
|---|---|---|
| 출처 | PyPI `gala`, 저장소 github.com/adrn/gala (저자 Adrian Price-Whelan) | PyPI `galpy`, 저장소 github.com/jobovy/galpy |
| 라이선스 | MIT | BSD-3 ("New BSD") |
| 버전·해시 | sdist `gala-1.12.0.tar.gz` sha256 `68d80d4f…3c50` (PyPI 값과 일치). 실행할 wheel `gala-1.12.0-cp312-cp312-manylinux_2_24_x86_64.manylinux_2_28_x86_64.whl` sha256 `cc5f0cf3bc63a966a3c130b93f6c05026271fe7178492a02c6266c243b5fc2f0` | sdist `galpy-1.12.0.tar.gz` sha256 `368c3b6a…7612` (PyPI 값과 일치) |
| 사용 적분기 | Cython `leapfrog.pyx`: 엇갈린(staggered) leapfrog. 시작할 때 속도를 반 step 당기고, 매 step `x += v½·dt`, 기울기 계산, `v = v½ − g·dt/2`(출력용), `v½ −= g·dt`. 그 밖에 ruth4, dop853, 순수 Python 적분기가 있다 | leapfrog(C/Python), symplec4, rk4, dop853, odeint |
| HH 방정식 형태 | 직교좌표 C++ (`builtin_potentials.cpp`): `grad[0] += q0 + 2*q0*q1`, `grad[1] += q1 + q0*q0 − q1*q1`. 퍼텐셜 ½(x² + y² + 2x²y − ⅔y³). 매개변수 없음 | 극좌표 Φ = ½[R² + ⅔R³ sin 3φ]. R³ sin 3φ = 3x²y − y³이므로 **같은 해밀토니안**. 힘 계산에 `sin`, `cos`, `pow` 사용 |
| 쓰는 연산 | + − × (기울기 배열 0 초기화 후 누적. 원점 이동·회전을 지정하지 않으면 변환 경로를 건너뜀: `cpotential.cpp` `do_shift_rotate`) | libm 초월함수 → **V2 적용 불가**(연산 범위 밖, libm은 올바른 반올림을 보장하지 않음) |
| 초기조건 설정 | `PhaseSpacePosition(pos, vel)` + `Hamiltonian(pot).integrate_orbit(w0, dt, n_steps, Integrator=LeapfrogIntegrator)`. 단위는 `DimensionlessUnitSystem` 사용 | `Orbit([R, vR, vT, φ])` 극좌표 입력 |
| 의존성 | Python ≥ 3.12 (1.11.0은 ≥ 3.11), numpy ≥ 2.2, scipy ≥ 1.15, astropy ≥ 7.0, pyyaml, cython. 확인한 환경: Python 3.12.3, numpy 2.5.3, astropy 8.0.1 | numpy, scipy, matplotlib, packaging |
| 수정 없이 실행 가능? | **예(Linux):** Python 3.12 venv에 설치 → `import gala`, `HenonHeilesPotential`, `LeapfrogIntegrator` 존재 확인(궤도 실행 안 함). **⚠ Windows wheel 없음.** 설계자 집 PC(Windows)에서 gala 자체를 돌리려면 WSL이나 MSVC 소스 빌드가 필요하다 | 예. win_amd64 wheel 있음 |
| adapter 최소 작업 | ① 고정 초기조건·dt·step 수로 gala를 호출하고 매 step 출력(x, y, vx, vy)을 받아 **동결 fixture**(SHA-256)로 저장 ② gala 연산 순서를 그대로 옮긴 replay 프로그램 T(numeric_core)를 쓰고 fixture와 비트 비교 ③ 이후 분석은 fixture와 T만 사용 | 극좌표↔직교좌표 변환 + 물리 검사만(V2 불가) |

**선정: gala 1.12.0.** HH 기울기가 V2 연산 범위(+ − ×) 안이고, 적분기 소스를 읽을 수 있다.
galpy는 libm 때문에 V2가 원리적으로 적용되지 않으므로 이번 범위에서 뺀다.
1.11.0과 1.12.0의 HH 기울기, leapfrog, `c_gradient` 코드는 grep 비교로 같았다(전체 diff는 아님).

## 2. 실행 조건 (Lab이 정함, 논문 초기조건 아님)

- 적분기: gala `LeapfrogIntegrator`, Cython 경로(기본값)
- dt = 1/64, N = 100,000 step, 단위 `DimensionlessUnitSystem`
- 궤도: Gate 2A의 주 궤도 둘, 원점 출발
  - 규칙 궤도 (p_x, p_y) = (1/4, 1/8)
  - 혼돈 궤도 (1/2, 1/4)
- 실행 환경: 클라우드 Linux, Python 3.12 venv, 위 wheel 해시. 실제 버전은 실행 기록에 남긴다.

## 3. 검사 분류

| ID | 검사 | 필요한 지식 | 종류 | 판정 방법 |
|---|---|---|---|---|
| B1 | 에너지 보존 | 공개 해밀토니안만 (**블랙박스**) | 2종 | 방법 오차 상한이 없으므로 **REFUSED**. 값은 참고 정보 |
| B2 | 시간 역전: gala를 (x_N, −v_N)에서 N step 다시 돌려 (x₀, −v₀)와 비교 | 블랙박스 실행 2회 | 1종 (아래 유도 ①) | 잔차가 정확히 0이면 PASS(상한 불필요). 아니면 상한이 필요하므로 블랙박스만으로는 REFUSED. W2가 성립하면 V2 상한으로 판정 |
| B3 | 거울 대칭: gala를 (−x₀, y₀, −vx₀, vy₀)로 돌려 거울상과 비교 | 블랙박스 실행 2회 | 1종 | 잔차가 정확히 0이면 PASS. 아니면 B2와 같은 처리 |
| B4 | 국소 힘 법칙: 궤적 위 모든 위치에서 gala의 `potential.gradient(q)`와 정확한 ∇V(q) 비교 | 공개 해밀토니안 + gala 함수 호출 | 1종 | 상한: 기울기 식의 연산 수(성분당 최대 3–4회)와 표준 반올림 모형에서 유도한 국소 상한. 연산 순서는 소스로 확인 (**source-informed**) |
| W1 | replay 비트 동일성: T의 매 step 출력이 gala fixture와 비트 단위로 같은가 | gala 소스(**화이트박스**) | — | BIT_IDENTICAL / NOT_IDENTICAL(첫 불일치 step과 원인 후보 기록). 실패가 아니라 측정 결과다 |
| W2 | V2 상한으로 gala 출력 인증 (W1이 BIT_IDENTICAL일 때만) | 화이트박스 | 1종 | 인증 한계(step), 상한 증가 곡선. W1이 NOT_IDENTICAL이면 **REFUSED** |
| W3 | V2 상한으로 B2를 다시 판정 | 화이트박스 | 1종 | PASS / FAIL / REFUSED |
| W4 | 교차 구현: gala 출력과 Lab의 Gate 2A Verlet 출력 비교 | Lab 구현(**참조 의존**) | 1종 (아래 유도 ②) | \|gala − Lab\| ≤ V2(gala, T 경유) + V2(Lab). W1이 NOT_IDENTICAL이면 REFUSED |

**유도 ① (B2가 1종인 이유):** gala는 출발할 때 v½ = v − g(x)·dt/2를 계산한다.
(x_N, −v_N)에서 출발하면 v′½ = −v_N − g_N·dt/2 = −v_{N−½}이다. 그러면 x′ = x_N − v_{N−½}·dt = x_{N−1}이 되고,
이후 같은 관계가 귀납적으로 이어져 정확 산술에서 (x₀, −v₀)로 돌아온다.

**유도 ② (gala leapfrog ≡ Lab Verlet, 정확 산술):** gala의 v_{j−½}가 Verlet의 p½(step j)와 같다는 것을 귀납으로 보인다.
- j = 1: v_{1/2} = v₀ − g₀·dt/2 = p₀ + a₀h/2. 성립.
- j → j+1: v_{j+½} = v_{j−½} − g_j·dt = (v_{j−½} − g_j·dt/2) − g_j·dt/2 = v_j + a_j·h/2. 이것이 Verlet의 다음 p½이고, gala의 출력 v_j는 Verlet의 p_j와 같다.
- 따라서 매 step 위치와 속도가 정확 산술에서 같다.
- 구현 단계에서 짧은 정확 산술 시험으로 이 유도를 확인한다.

## 4. 파이프라인이 실제로 FAIL을 낼 수 있는지 확인 (외부 코드는 건드리지 않음)

| ID | 주입 | 탐지할 것으로 예측한 검사 |
|---|---|---|
| T1 | fixture **사본**에서 step 50,000의 x를 1 ulp 바꿈 | W1 (불일치 step = 50,000). 그 step이 인증 한계 안이면 W4 |
| T2 | fixture **사본**에서 step 50,000과 50,001을 서로 바꿈 | W1, W4 |

원본 fixture는 바꾸지 않는다.

## 5. 판정 기준 (실행 전 고정)

| ID | 기준 |
|---|---|
| G2B-0 | **무결성:** gala를 위 wheel 해시 그대로 설치하고, 수정·monkeypatch하지 않는다(adapter 정적 검사). 실행 출력은 분석 코드를 돌리기 **전에** fixture로 커밋한다 |
| G2B-1 | 두 궤도 모두에서 B1–B4, W1(과 해당하면 W2–W4)이 끝까지 실행된다 |
| G2B-2 | W1 결과가 BIT_IDENTICAL 또는 NOT_IDENTICAL로 확정되고, NOT_IDENTICAL이면 첫 불일치와 원인 후보가 기록된다. **어느 쪽이든 실패가 아니다** |
| G2B-3 | **건전성 이어받기:** W2를 적용했다면 T에서 정확 산술 구간(8 step, n₀ ∈ {0, 50000, 99992})의 상한 위반이 0이어야 한다. 위반하면 FAIL |
| G2B-4 | 모든 검사에 규칙상 이유가 붙은 판정이 기록된다. T1·T2가 예측한 검사에서 잡히고, 다르면 원인을 적는다 |

**Gate 2B 판정**
- **PASS:** G2B-0–4를 모두 충족. 결과가 "정보 있음"이든 "제한적"이든 정직한 결과면 PASS다.
- **FAIL:** G2B-0 위반(외부 코드를 수정함, 실행 후에 fixture를 만듦), G2B-3 위반, 또는 결함을 확인 없이 단정함.
- **REFUSED:** gala를 수정 없이 실행할 수 없음(설치·실행 불가).

**질문에 대한 답 (미리 정한 분류)**
- **YES — 추가 정보 있음:** 다음 중 하나 이상
  - (a) W2가 규칙 궤도에서 gala 출력을 17,790 step 이상 인증
  - (b) 어떤 1종 검사가 FAIL이고, 재실행과 독립 유도로 재확인됨
  - (c) W4가 인증 한계 안에서 PASS(gala와 Lab이 엄밀한 범위 안에서 일치)
- **LIMITED:** V2를 적용할 수 없고, 블랙박스·source-informed 검사(B2–B4)만 판정을 낸 경우
- **NO:** 모든 검사가 REFUSED

**결함 보고 규칙:** gala에서 FAIL이 나오면 바로 "gala 버그"라고 하지 않는다.
adapter 결함, 단위 변환, 출력 저장 경로를 먼저 배제하고, 재실행과 독립 유도로 확인한 뒤에야 보고한다.
외부 저장소에 이슈를 올리는 일은 설계자 결정 없이 하지 않는다.

## 6. 재현성 (설계자 결정 필요)

- gala 실행은 Linux(클라우드)에서 하고, 출력은 SHA-256 fixture로 동결한다.
- 설계자 집 PC(Windows)에서는 **fixture를 입력으로 한 분석**을 재현해 digest를 비교한다.
- gala 실행 자체를 집 PC에서 재현하려면 WSL이 필요하다. 필수로 할지는 설계자가 정한다.

## 7. 비용 추정 (실행 전)

- gala 실행: C 경로라 몇 초
- T replay와 V2: 궤도당 약 4–8분
- 시간 역전·거울 실행: 각각 같은 수준
- 전체 30–60분

## 8. 한계 (미리 공개)

- 감사 범위는 gala 전체가 아니라 **HenonHeilesPotential + Cython leapfrog 경로**뿐이다.
- 궤도 두 개, 하나의 dt.
- 결과는 이 wheel(manylinux, x86-64)의 기계어에 대한 것이다. 다른 플랫폼의 빌드(예: FMA를 쓰는 ARM)에는 그대로 옮겨 적용하지 않는다.
- 연속 물리(층 B)는 인증하지 않는다.

---

## 부록 A — 실행 전 설계자 요청 추가 (2026-10-01, 외부 코드 실행 전)

본문은 고치지 않고, 설계자가 실행 전에 요청한 세 가지를 여기 추가한다.

### A1. execution reproducibility와 analysis reproducibility를 구분한다

| 구분 | 무엇을 재현하나 | 판정 방법 | 이번 계획에서 |
|---|---|---|---|
| **execution reproducibility** | gala를 실제로 다시 실행했을 때 같은 출력(fixture)이 나오는가 | 다른 실행에서 fixture SHA-256이 같은지 | 클라우드 Linux에서 1회 생성. 집 PC(Windows)는 gala wheel이 없으므로 **기본 범위 밖**. WSL 등으로 재현하면 별도로 기록한다 |
| **analysis reproducibility** | 동결된 fixture를 입력으로 한 Lab의 분석(W1–W4, B1–B4)이 같은 결과를 내는가 | 분석 보고서의 deterministic_digest가 같은지 | 클라우드와 설계자 집 PC에서 비교. 집 PC에는 gala가 필요 없다 |

두 가지를 섞어 보고하지 않는다. "집 PC 재현 PASS"는 별도로 적지 않는 한 **analysis reproducibility**를 뜻한다.

### A2. W2 인증 대상의 정확한 범위

W2가 PASS여도 인증되는 것은 다음뿐이다.
> **gala 1.12.0 Linux wheel** (`gala-1.12.0-cp312-cp312-manylinux_2_24_x86_64.manylinux_2_28_x86_64.whl`, SHA-256 `cc5f0cf3…f2c0`)을 클라우드 x86-64 Linux에서 **한 번 실행해 동결한 출력(fixture)**,
> 그리고 그 fixture와 비트 단위로 같다고 확인된 **replay 프로그램 T**.
> 상한은 "fixture 값 ↔ T를 정확 산술로 실행한 값" 사이에 대한 것이다.

인증하지 않는 것:
- gala 소스 일반, 다른 wheel이나 다른 플랫폼 빌드, 다른 dt·초기조건·적분기
- 연속 Hénon–Heiles 궤적

### A3. provenance

[GATE2B_PROVENANCE.md](GATE2B_PROVENANCE.md)에 wheel SHA-256과 PyPI attestation의 GitHub source commit `bebac7d728478c5122a568e12175ef894d1c1516`을 기록한다.
