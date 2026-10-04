# I15/I19 — Semantic mutation obligations

- status: DESIGN CONDITIONS ADDRESSED / IMPLEMENTATION STILL NOT STARTED / REVIEW PENDING
- version: 1, 2026-10-04; audited design snapshot `023b186c0e9d95c11399893e7f75772cfff6c3a7`의 후속 저자 사양
- dependencies: updated I1–I22; B3/B4/B5/B6/B7/B8; auditor M1–M17 mapping
- unresolved items: fixture 획득/독립 expected/실제 source edit와 실행 전부 미실행
- what this does NOT certify: production 구현, 모든 입력의 finite-budget 성공, 물리 정확성, J verification, integration/trajectory/replay/N-Step, certification.

기존 [감사 대상 설계](../C1B1_INDEPENDENT_IMPULSE_V1_DESIGN.md)는 역사적 snapshot으로 보존한다. 이 후속 사양은 지정한 항목에 한해 옛 제안/U1–U8을 대체하며, 독립 closure 재검토의 `IMPLEMENTATION MAY START` 판정 전 소스 구현을 허용하지 않는다.

모든 아래 행은 계획이며 **NOT EXECUTED**다. baseline PASS / 실제 source mutant DETECTED가 구현 후 완료 기준이다. slash로 묶인 여러 edit는 각각 별도 mutant로 실행해야 한다. expected는 exact primitive inequalities, 독립 derivative 유도/term enclosure 또는 선택 producer와 코드/helper를 공유하지 않는 rechecker의 complete nonlinear proof로 만들고 그 근거를 남긴다. 근접한 high-precision point나 evaluator의 자체 결과를 정답으로 삼지 않는다.

| mutant | source edit | obligations | nondegenerate fixture 및 semantic detection 조건 |
|---|---|---|---|
| M1 | force sign flip | I4/I7/I8 | 인증된 nonzero rounded J를 쓰고 sign 반전이 서로 다른 cell로 가는 사례. 실제 힘이 0에 가깝다는 진단만으로 부족. |
| M2 | i/j kick sign swap | I9/I14 | 원자별 서로 다른 momentum과 nonzero J; common J 양쪽 적용 결과를 따로 비교. |
| M3 | half-step factor 제거/full-step 사용 | I4/I13 | h=dt/2와 다른 scalar가 동일 raw로 반올림되지 않는 fixture. 두 edit를 별도 mutant로 기록. |
| M4 | 1/R 제거 | I4/I7 | R≠1만으로 부족. 올바른 값과 변형 값의 cell이 분리되는 axis/off-axis fixture. |
| M5 | R power 오류 | I3/I4/I7 | 각 long term/derivative term의 독립 enclosure 또는 분리된 J cell; R=1 퇴화 회피. |
| M6 | short derivative/TT slope 누락 | I4/I7 | 빠진 항의 영향이 독립 증거로 관찰되는 term-level fixture; 거친 총 J 구간 일치만으로 검사하지 않음. |
| M7 | BO g′ 누락/REL leading 1−T | I3/I4 | 두 source edits를 분리. 각각 retarded BO, REL term identity 및 J 포함을 공격. |
| M8 | exp sign/rate 오류 | I6/I7 | x>0의 증명된 exp 구간 및 x=0 아닌 case. exp(+x), exp(−2x)는 별도 mutant. |
| M9 | component swap | I2/I7/I13 | 서로 다른 크기의 비영 q 성분으로 lane별 expected가 다르게 구성. |
| M10 | ties-away | I8 | 합성 scaled y의 양·음 even tie. 실제 Lang state에서 exact tie를 만들었다고 주장하지 않음. |
| M11 | inverse/division endpoint swap | I5/I7 | 양수 폭이 있는 분모와 signed numerator, exact rational containment로 검출. |
| M12 | corner 삭제/inward rounding | I5/I6/I7 | 누락 corner가 실제 extremum인 mixed-sign interval과 dyadic 경계. 두 결함군 분리. |
| M13 | early precision accept | I8/I10/I11 | midpoint를 가로지르는 sound interval이 false RESOLVED로 바뀌는지 검사. |
| M14 | overflow/operational refusal 제거 | I8/I10/I11 | lower/upper asymmetric threshold, 양끝 overflow이나 0을 포함한 coarse interval, budget 만료 각각 분리. |
| M15 | wrong spec/profile forced accept | I1/I2/I12/I13 | 다른 spec·grid·half/full binding을 valid-looking data와 함께 제시. 숫자 raw 일치로 통과시키면 실패. |
| M16 | intermediate R/F quantization | I4/I7/I8 | whole-expression once-rounding과 두 번 반올림의 결과가 다른 독립 증거가 필요. |
| M17 | fixed exp cutoff/output guard 제거 | I6/I10 | tail의 참값>0인 primitive 포함 반례와 output resource boundary 반례를 별도로 검사. |

각 M행은 independently verified baseline cell/term enclosure가 실제 edit의 wrong 결과와 분리돼야 한다. M3/M7/M8/M12/M14/M17의 두 fault는 단일 edit 여러 건으로 나눈다. M10의 exact ties는 synthetic numeric decision fixture이고 실제 Lang exact tie를 찾았다는 주장이 아니다. M17 output guard는 publication cap 넘는 static certificate fixture를 사용하고 거대한 integer를 error text로 재출력하지 않는지도 검사한다. 축/부호 비교만으로 검출하지 못하는 tiny J fixture는 채택하지 않는다.

| 추가 ID | attack | fixture/independent expected / 실제 semantic detection |
|---|---|---|
| M18a | rechecker를 producer interval만 신뢰하도록 변경 | admitted nonzero state의 독립 proved raw와 다른 raw를 가진 valid-looking compact cert; baseline nonlinear 재구성 REJECTED, mutant의 위조 acceptance 검출. interval field 삽입은 별도 schema control |
| M18b | constants/spec override 허용 | 동일 raw를 우연히 얻어도 다른 exact constants/source/version certificate 거부가 expected; forced accept를 의미 실패로 검출 |
| M18c | rechecker dV term 누락 | 해당 항이 cell을 이동시키는 독립 term/J fixture와 위조 raw; baseline reject/mutant accept. producer M6와 독립 source edit |
| M19a | denominator positivity/admission 검사 삭제 | R=0, R<r_min 및 positive-width denominator touching zero; exact rational inequality가 expected refusal; 계산 진입/invalid reciprocal 검출 |
| M19b | zero-axis로 domain 우회 | q=(0,nonzero,0)이면서 below-min; expected PHYSICAL_DOMAIN 전에 zero 승인 금지; 부분 ACCEPTED 검출 |
| M20a | preallocation/work guard 삭제 | 독립 계산한 symbolic bound가 configured finite cap 바로 넘는 구조; 실제 위험 allocation 전에 baseline stop/mutant 진입 검출; huge memory allocation을 실제 실행할 필요 없음 |
| M20b | resource exhaustion 시 마지막 approximation 채택 | cell midpoint를 가로지르는 sound enclosure+유한 exhausted budget; exact cell noncontainment expected; false RESOLVED 검출 |
| M21 | conflicting refinements 덮어쓰기 | exact nonnested sound fixture는 정상; empty intersection/서로 다른 proved raw는 independent inequality로 anomaly; silent last-wins 검출 |
| M22a | occurrence identity/cache key에서 phase/acquisition 제거 | 동일 bits의 서로 다른 record/phase; independent canonical domain hash와 binding expected; stale accept 검출 |
| M22b | J1을 J0 snapshot으로 재사용 | drift 후 다른 position snapshot과 independently resolved 다른 J1; J1 binding mismatch가 expected; same supplied J 재사용 검출 |
| M23 | 첫 축 이후 partial publish/state write | x accepted, y overflow 또는 unproved, z pending; whole-vector publication expected zero; publish/write interception에서 partial output 검출 |

현재 실제 source를 만들지 않았으므로 번호가 있다는 것만으로 mutant defense PASS를 부여하지 않는다. 기존 Arithmetic 16+F-CLAIM mutant evidence는 변경 없이 보존한다.
