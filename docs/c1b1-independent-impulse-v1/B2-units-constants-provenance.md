# B2 — Unit / constant provenance

- status: DESIGN CONDITIONS ADDRESSED / IMPLEMENTATION STILL NOT STARTED / REVIEW PENDING
- version: 1, 2026-10-04; audited design snapshot `023b186c0e9d95c11399893e7f75772cfff6c3a7`의 후속 저자 사양
- dependencies: [91-record data](../../specs/c1b1-independent-impulse-v1/constants.json); P0; S1/S2 frozen records; B1/B3
- unresolved items: P0 raw bytes의 독립 감사자 재확인; 동결 mass 출처의 재확인; 새 전사 구현 검증
- what this does NOT certify: production 구현, 모든 입력의 finite-budget 성공, 물리 정확성, J verification, integration/trajectory/replay/N-Step, certification.

기존 [감사 대상 설계](../C1B1_INDEPENDENT_IMPULSE_V1_DESIGN.md)는 역사적 snapshot으로 보존한다. 이 후속 사양은 지정한 항목에 한해 옛 제안/U1–U8을 대체하며, 독립 closure 재검토의 `IMPLEMENTATION MAY START` 판정 전 소스 구현을 허용하지 않는다.

## 전사 범위

[constants.json](../../specs/c1b1-independent-impulse-v1/constants.json)의 SHA-256은 `f1cf6a71afaf45e40db37a6e8a5b4f643a57885f4040d4fa285835530363e196`이다. 91개 record는 BO/REL/QED의 Jn/Imin/Imax/Kmin/Kmax/Kadd, alpha, polynomial coefficients, eta, C_2k, retardation A_m/B_m, σ 계수/index, bohr 변환, r_min, Ar40/electron mass nominal 값을 각각 고정한다. 모든 record에 source/version/section, exact textual token, decimal→exact reduced rational 해석, unit, index/family, Lab canonical n/d, 사용 역할이 있다. σ 데이터는 `UNCERTAINTY ONLY / EXCLUDED FROM J`로 분리한다.

Fortran `a(i,j)`는 column-major이며 ascending i가 먼저, j가 나중이다. BO i=-1..2, REL/QED i=0..2, j=1,2. long k는 BO3..8/kadd1, REL2..4/kadd0, QED3..4/kadd0이다. A는 m1..5, B는 m1..6. `_prec`는 type suffix로 제거하고 e/D 지수는 십진 exact rational로 해석한다. host float로 거쳐 가지 않는다. 원본 floating evaluator의 `EXPTHR`, `limit1/limit2`, `extra*`, `prec`는 adopted physical constants가 아니며 평가 편의 상수로 제외한다.

이것은 승인 대상인 static data bundle의 고정 91-record schema다. B4 runtime Input/Certificate의 array cap12는 이 static 전사표에 적용하지 않는다. 요청 wire에는 constants bundle을 재삽입하거나 override할 수 없고, 승인된 exact hash의 data만 별도로 로드한다. unit은 각 record의 unit_basis에 표시한 physical equation 차원 유도이며 계수 선언에 단위 문자열이 literal로 있었던 것으로 주장하지 않는다.

## 단위·species·mass

| 데이터 | 단위 / 의미 |
|---|---|
| R, q, position | bohr=a0 |
| V, nominal short coefficient a_i | hartree; a_i는 hartree·bohr^(-i) |
| alpha, eta | bohr^-1 |
| C_2k | hartree·bohr^(2k) |
| A_m/B_m | bohr^-m; g는 무차원 |
| force | hartree/bohr |
| full_dt / half kick | atomic time=hbar/Eh |
| momentum / impulse | atomic momentum=hbar/a0 |
| σ leading rate / Gaussian rate | bohr^-1 / bohr^-2; amplitude는 hartree |

단위 차원은 물리식에서 유도한 것이다. 식·모델은 [Lang et al., arXiv:2304.14719v2](https://arxiv.org/html/2304.14719v2) 및 정확 bytes를 확보한 P0/기존 동결 계약에 결합한다. bohr conversion은 동결된 `0.529177210903 Å`(CODATA2018)를 유지한다. Ar40 nominal mass `39.9623831237 u`, electron nominal mass `5.485799090441e-4 u`(원본 D1의 CODATA2022)를 exact ratio로 결합한다. 두 판을 최신 값으로 통일하지 않는다. isotope mass uncertainty `(24)`와 electron `(97)`는 원본 계약의 provenance이며 이 값들의 새 외부 확인을 했다는 주장은 아니다. mass는 future Arithmetic Drift의 species binding용이고 J값 인자가 아니다.

## 실제 확보와 확인 수준

P0 local raw source는 `D:/reference/ar2_lang2024/S2_ar2_pot.f90`에서 확보했고 [동결 raw copy](../../current/c1b1-impulse-design-conditions-2026-10-04/provenance/P0-S2_ar2_pot.f90.raw)는 12,061 bytes, SHA-256 `a598057183121b9c928b3a9804c8e2e99afa553bad570a471aa4130f20e6b049`다. **AUTHOR LOCAL RAW BYTE CHECK**다. 앞선 독립 감사자의 offline raw-byte 재확인 불가 판정을 바꾸지 않는다. 이번 공개 raw 재다운로드나 independent reconfirmation은 없다.

A-EV exact commit `27e48770ab5db666bcd78034d151ddbb04b6af54`는 local 감사 worktree의 Git object에서 실제 복구했다. 다른 commit으로 대체하지 않았다. [source recovery](../../current/c1b1-impulse-design-conditions-2026-10-04/provenance/source-recovery.json)에 raw commit/root tree/path trees/blob과 객체 ID 재계산 결과가 있다. 이는 저자의 local object 확인이다. 감사자의 과거 GitHub retrieval 실패와 독립 확인 미완료는 보존한다. A-EV는 이번 V1의 필수 TCB가 아니며 `comparison-only / NOT A TRUSTED ANTECEDENT`다.

원본 선택 source commit `0f7b744cf754450424a63c47f305e0327c5b37c1`의 S1/S2/S4/S5와 V2/V1 checker blob도 같은 방식으로 따로 확보했다. raw object들의 Git SHA-1(type+length+NUL+content) 및 raw SHA-256과 Merkle path를 저장했다. 전체 repository/history Git bundle이라는 주장은 아니다. compatibility fingerprint `ada6153be05af3e582139fdc81b5697fffaf18d12f9f2de6e8d5ac2fdfe0839e`는 σ를 포함하며 Lab semantic bundle ID 대신 쓰지 않는다.
