# I1–I22 — Updated obligation ledger

- status: DESIGN CONDITIONS ADDRESSED / IMPLEMENTATION STILL NOT STARTED / REVIEW PENDING
- version: 1, 2026-10-04; audited design snapshot `023b186c0e9d95c11399893e7f75772cfff6c3a7`의 후속 저자 사양
- dependencies: B1–B8; [independent verdicts](../../current/c1b1-impulse-design-conditions-2026-10-04/received/verdicts.json); historical design §16
- unresolved items: I1/I10/I12/I13은 B gate independent 승인 전 BLOCKED; 모든 구현 증거 미발급
- what this does NOT certify: production 구현, 모든 입력의 finite-budget 성공, 물리 정확성, J verification, integration/trajectory/replay/N-Step, certification.

기존 [감사 대상 설계](../C1B1_INDEPENDENT_IMPULSE_V1_DESIGN.md)는 역사적 snapshot으로 보존한다. 이 후속 사양은 지정한 항목에 한해 옛 제안/U1–U8을 대체하며, 독립 closure 재검토의 `IMPLEMENTATION MAY START` 판정 전 소스 구현을 허용하지 않는다.

이 표는 historical verdict를 바꾸지 않는 후속 ledger다. 감사의 READY FOR IMPLEMENTATION은 개별 식 전략 평가이지 B1–B8을 건너뛰는 전체 착수 허가가 아니다. 이번 specification 작성이 implementation PASS라는 뜻도 아니다.

| ID | revised obligation | historical auditor state | current author state | dependencies |
|---|---|---|---|---|
| I1 | Lab bundle/constants/units/domain authority+canonical hash+source 전사 승인 | BLOCKED | BLOCKED — independent B-gate closure 승인 전 | B1/B2/B3 |
| I2 | bounded raw→q=r_j-r_i→R²; acquisition/full-state equality | IMPLEMENTATION-DEPENDENT | OPEN — specification addressed; implementation/proof evidence pending | B1/B7 |
| I3 | 모든 V short/long/retarded branches 및 indices 정확 전사 | READY FOR IMPLEMENTATION | OPEN — specification addressed; implementation/proof evidence pending | B1/B2 |
| I4 | analytic V′, BO i=-1/g′/TT slope/REL leading, force/sign/h/no-mass 대응 | READY FOR IMPLEMENTATION | OPEN — specification addressed; implementation/proof evidence pending | B1/B2 |
| I5 | sqrt/inverse/power/signed interval containment; denominator positivity | OPEN | OPEN — specification addressed; implementation/proof evidence pending | B3/B5/I17 |
| I6 | exp-tail/range reduction/각 squaring outward widening, cutoff 없음 | READY FOR IMPLEMENTATION | OPEN — specification addressed; implementation/proof evidence pending | B1/B5 |
| I7 | V′→-V′/R→h*q→J sound composition; correlation/cancellation은 availability 문제 | READY FOR IMPLEMENTATION | OPEN — specification addressed; implementation/proof evidence pending | B1/B5 |
| I8 | exact nearest-even cells, negative ties, asymmetric signed overflow; strict V2 제한 | READY FOR IMPLEMENTATION | OPEN — specification addressed; implementation/proof evidence pending | B1/B8 |
| I9 | spec/domain 후 exact-zero만; common J orientation/negation range | READY FOR IMPLEMENTATION | OPEN — specification addressed; implementation/proof evidence pending | B3/B6 |
| I10 | 모든 refusal에서 immutable input/state; bounded error; pre-str guard; atomic publication | BLOCKED | BLOCKED — independent B-gate closure 승인 전 | B4/B5/B8 |
| I11 | I11a–d 네 명제 별도 논증; finite-budget all-input success를 요구하지 않음 | OPEN | OPEN — specification addressed; implementation/proof evidence pending | B4/B5 |
| I12 | 선택 B parser/primitive/enclosure/rounding/executor helpers 독립; 실제 source/process/call 증거 | BLOCKED | BLOCKED — independent B-gate closure 승인 전 | B6 |
| I13 | same-state/spec/occurrence/phase comparison; missing/mismatch/refusal 보존 | BLOCKED | BLOCKED — independent B-gate closure 승인 전 | B7/B8 |
| I14 | 기존 Arithmetic bytes/status 보존; J0/J1 새 snapshot; point와 composition gate 구분 | IMPLEMENTATION-DEPENDENT | OPEN — specification addressed; implementation/proof evidence pending | B3/B7/B8 |
| I15 | 각 실제 source mutant의 nondegenerate fixture+independent expected+semantic detection | IMPLEMENTATION-DEPENDENT | OPEN — specification addressed; implementation/proof evidence pending | B6/B8 |
| I16 | author와 independent 대상 source/dependency/proof/receipt를 각각 고정 | IMPLEMENTATION-DEPENDENT | OPEN — specification addressed; implementation/proof evidence pending | B1–B8 |
| I17 | 전역 domain 및 모든 denominator regularity와 coarse-lower-zero 처리 | NEW AUDIT OBLIGATION | OPEN — specification addressed; implementation/proof evidence pending | B3/B5 |
| I18 | bit/allocation/work preflight 및 compact proof/wire/failure-envelope 공동 호환성 | NEW AUDIT OBLIGATION | OPEN — specification addressed; implementation/proof evidence pending | B4+B5 |
| I19 | certificate→recheck full soundness; 원입력 nonlinear 재구성 또는 각 witness independent 검증 | NEW AUDIT OBLIGATION | OPEN — specification addressed; implementation/proof evidence pending | B6/B7 |
| I20 | refinement sequence 결정론; nonnested sound 허용; empty intersection/conflicting raw anomaly STOP | NEW AUDIT OBLIGATION | OPEN — specification addressed; implementation/proof evidence pending | B5/B8 |
| I21 | canonical full/math/occurrence identity와 stale cache 방어; V1 cache disabled | NEW AUDIT OBLIGATION | OPEN — specification addressed; implementation/proof evidence pending | B7 |
| I22 | 모든3축 승인/출판 가능 후 atomic J/certificate/state; partial commit 없음 | NEW AUDIT OBLIGATION | OPEN — specification addressed; implementation/proof evidence pending | B4/B8 |

## I11의 네 독립 명제

I11a는 fixed admitted input에서 enclosure containment와 내부 수렴이다. I11b는 exact cell 판정 가능성으로, exact tie/zero 특수 사례와 엄격한 V2 cell 제한을 따로 다룬다. I11c는 finite budget 성공이며 V1은 전 입력 성공을 보장하지 않고 bounded UNPROVED/STOP을 허용한다. I11d는 wire 크기 및 완전한 proof publication 가능성이다. 어느 하나의 성공으로 다른 세 명제를 PASS 처리하지 않는다.

I17의 regularity는 R>0, rates>0, D>=1, factorial>0, n+2>x_hi, interval denominator lower>0을 각각 검증한다. I18은 compact representation이라도 내부 denominator/temporary 비용을 없던 것으로 취급하지 않는다. I19는 producer final interval을 신뢰하지 않는다. I20은 wall-time refusal과 mathematical determinism을 구별한다. I21은 same bits/different occurrence 구분을 강제한다. I22는 failure 시 어떤 부분 vector/state도 세계에 쓰지 않는다.

## I15: semantic mutation acceptance 조건

각 source mutant에는 baseline source/hash, 정확한 단일 edit, mutant hash, nondegenerate fixture, **구현으로부터 독립된 expected 및 검증 근거**, actual semantic detection을 요구한다. hash mismatch만 잡힌 경우는 HASH/TRUST control이고 semantic DETECTED 수에 포함하지 않는다. wrong output/cell, invalid containment, forbidden acceptance, lost refusal/immutability/atomicity 같은 실제 의미 결함이 관측되어야 한다. 현재 baseline PASS나 mutant DETECTED 실행 결과는 없다.

[mutation obligations](mutation-obligations.md)는 M1–M17을 audit 요구대로 구체화하고 I17–I22 공격 항목을 추가한 **계획**이다. 실제 Lang fixture가 아직 없는 경우 fixture specification 및 독립 expected 취득 조건으로 표시한다; 존재하지 않는 raw 값을 만들어 증거처럼 넣지 않는다.
