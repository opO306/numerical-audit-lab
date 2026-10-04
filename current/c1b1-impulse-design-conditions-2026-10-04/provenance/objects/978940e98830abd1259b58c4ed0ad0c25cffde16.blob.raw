# C1-A 동결 — Ar–Ar 퍼텐셜의 물리·수치 의미 계약 v1

**상태:** 동결 (설계자 판정 10판, 2026-09-25). 계약 판 `c1a-ar2-lang2024-v1`.
**강제:** `tests/test_c1a_freeze.py` (계약 상수·매개변수 지문·fixture 해시·Lang 원자료 해시·provenance 일치).
**근거 문서:** `A_MICRO_V6_ARAR_POTENTIAL_SURVEY_V1.md` 10·11절, `A_MICRO_V6_C0_NUMERIC_EXECUTION_PLAN_V1.md` 11.6~11.8.

동결 시험이 깨지면 회귀가 아니라 **계약이 바뀐 것**이다 — 새 계약 판과 설계자 판정이 필요하다.

---

## 1. 동결하는 것 (물리·수치 의미)

| 항목 | 내용 |
|---|---|
| 모델 | Lang·Przybytek·Lesiuk 2024 해석적 Ar–Ar 퍼텐셜 |
| 매개변수 | 공개 Fortran(`S2_ar2_pot.f90`)의 소수 표기를 **정확한 십진 유리수**로 해석. 매개변수 지문 `ada6153b…0839e` |
| 퍼텐셜 | `V_real = V_BO + V_rel + V_QED` |
| 지연(retardation) | **A 세계에서는 ON** (`WORLD_RETARDATION = True`). OFF 경로는 감사·비교용이며 A의 물리 선택이 아니다 |
| 적용 하한 | `r_min = 1.2 Å`. 그 미만은 `physics_domain_exceeded` (clamp·대체 반발·외삽 금지) |
| 단위 변환 | CODATA 2018 a₀ = 0.529177210903 Å는 **이 계약의 출처 고정 변환에만** 쓴다. A 전체의 Å↔bohr 상수는 정하지 않는다 |
| 단위 | 거리 bohr, 에너지 hartree, 힘 hartree/bohr |
| 값 | `V = round_profile(V_real(R))` — 한 번 반올림 |
| 힘 | `F = round_profile(−dV_real/dR)` — 해석적 미분, 한 번 반올림 |
| 오차 장부 | 모델 불확도(σ)와 수치 오차는 **별개 장부** |
| 극저온 | 아홉 번째 진동 상태·s파 산란 길이 등 ultracold 미해결 영역은 일반 C1-B 검증과 분리 |
| 기준 결과 | fixture `a_reference/fixtures/ar2_lang2024_c1a_v1.json`의 결과 비트 (LF 정규화 SHA-256 `9038bb15…fe76b`) |
| 거부 | 기준 평가기가 정밀도 상한까지 결정하지 못하면 **추측하지 않고 거부**(`ReferenceUndecided`) |

## 2. 동결하지 않는 것 (실행기 구현·성능)

B0의 `R ≤ 2²⁰ bohr` 능력 한계 · B0 최대 정밀도(3072비트) · B1 스레드 수·작업 분할 · B2 limb 수(96) · B2 정밀도 시도 횟수(4) ·
CUDA block/grid 구조 · 실행 시간 · 이후의 메모리·병렬화 최적화.

결과 의미를 바꾸지 않는 한 개선할 수 있다. **개선된 실행기는 같은 동결 계약과 fixture를 다시 통과해야 한다.**

## 3. 아직 고르지 않은 것

- **세계의 최종 수 체계** (FX(64,32)도 binary64도 아직 아님). C1-A는 퍼텐셜 평가 능력만 확인했다. FX(64,32)가 약 90 bohr(V)·61 bohr(F)부터
  꼬리를 0으로 만든다는 사실은 기록하되, 문제인지는 C1-B의 cutoff·오차 계약 뒤에 판정한다.
- **fast profile**: 만들지 않는다. C1-B의 작은 기준 실험으로 실제 비용이 병목임이 확인될 때만 설계한다. 만들더라도 정확 profile과 같은 것으로
  가장하지 않고, 별도의 오차 상한과 수렴 검증을 갖는다.

## 4. 동결 직전 provenance 정리 (10판 1항)

fixture를 **최종 코드 상태의 커밋 `868e865`에서 재생성**했다. 생성기는 이제 결과를 정하는 코드 파일(기준 평가기, `a_numeric/exp.py`·`profiles.py`,
생성기, 감사 코드)이 모두 커밋된 상태가 아니면 생성을 거부한다. 코드 해시는 CRLF→LF 정규화(= Git blob)로 계산해 Windows 체크아웃에서도 같다.

| 확인 | 결과 |
|---|---|
| 입력·태그·**모든 결과 비트**·경계 거리 | 이전 fixture와 **완전히 동일** |
| 계약 판, 매개변수 지문 | 현재와 일치 |
| Lang 원자료 SHA-256 | `D:\reference`의 파일·`SHA256SUMS.txt`·이전 기록과 일치 |
| 기준·의존 파일·감사·생성기 SHA-256 | 현재 파일과 일치 |
| `git_head_at_generation` | `868e865`, 그 커밋의 해당 파일 blob이 기록된 해시와 정확히 일치 |

재생성 때 모든 결과 비트를 독립 감사로 다시 판정했다(전부 통과).
