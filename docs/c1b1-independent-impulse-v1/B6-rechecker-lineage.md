# B6 — Rechecker lineage / trust boundary

- status: DESIGN CONDITIONS ADDRESSED / IMPLEMENTATION STILL NOT STARTED / REVIEW PENDING
- version: 1, 2026-10-04; audited design snapshot `023b186c0e9d95c11399893e7f75772cfff6c3a7`의 후속 저자 사양
- dependencies: [lineage data](../../specs/c1b1-independent-impulse-v1/rechecker-lineage.json); B1/B2/B4/B5/B7; exported exact source objects
- unresolved items: 새 binding 및 source 전체의 독립 closure review; 실제 구현 경로 증거; I19 soundness
- what this does NOT certify: production 구현, 모든 입력의 finite-budget 성공, 물리 정확성, J verification, integration/trajectory/replay/N-Step, certification.

기존 [감사 대상 설계](../C1B1_INDEPENDENT_IMPULSE_V1_DESIGN.md)는 역사적 snapshot으로 보존한다. 이 후속 사양은 지정한 항목에 한해 옛 제안/U1–U8을 대체하며, 독립 closure 재검토의 `IMPLEMENTATION MAY START` 판정 전 소스 구현을 허용하지 않는다.

## 공식 V1 설계 선택: 후보 B

**새 Lab binding/producer + 기존 exact checker V2**를 선택한다. 후보 A의 새 nonlinear rechecker를 추가하지 않는다. 기존 V1/V2/Point Prover/A-EV를 independent oracle 개수로 합산하지 않는다. 새 producer는 V2를 expected generator로 호출하거나 primitive/enclosure/rounding 코드를 복사하지 않는다. 별도 recheck boundary만 지정된 source의 check_certificate를 호출할 수 있다. 이번에는 호출/배선/구현하지 않는다.

V2 source antecedent는 원본 commit `0f7b744cf754450424a63c47f305e0327c5b37c1`, path `a_reference/c1b1_exact_impulse_checker_v2.py`, blob `ad1a66091ec743359565f3d19affbef800c70192`, raw SHA-256 `180d5a19bbea606594912e95b3c210b5a7739995afa39c5300959faef8b94d96`다. [raw object/Merkle records](../../current/c1b1-impulse-design-conditions-2026-10-04/provenance/source-recovery.json)를 확보했다. 이 정확 source가 기존 프로젝트에서 가졌던 승인 범위는 신규 Lab binding을 자동 승인하지 않는다. trust selection은 저자 설계이고 independent closure 판단 대기다.

| 공유 경계 | 후보 A: 새 producer+새 rechecker | 선택 B: 새 producer+지정 V2 |
|---|---|---|
| TCB | spec, 정수/Fraction/OS 신뢰; 두 신규 엔진 감사 필요 | 같은 표준 의미/OS 신뢰 + pinned V2 source, pure-data binding/worker 검증 필요 |
| specification | 승인 Lab 사양 공유 허용 | Lab 사양과 legacy format mapping 공유 허용 |
| constants | exact data 의미 공유, 서로 전사 확인 | producer Lab data; V2 자기 embedded decimals; exact rational parity 및 fingerprint 별도 확인 |
| parser | schema만 공유, 실행 parser 구현 분리 | producer input parser와 recheck binding validator 분리; V2 private parser를 producer가 사용 금지 |
| certificate schema | 규범 공유 | Lab compact wire + 별도 private legacy projection |
| primitive/enclosure/rounding helper | 실행 코드 공유 금지 | K2 helper/enclosure/down/up/decision을 producer에 import/copy/call 금지 |
| executor helper | 양쪽 금지 | 양쪽 금지; comparison 대상 프로세스만 별도 |

Point Prover는 K2.enclosure 및 K2.check_certificate를 사용하므로 **Point Prover+V2는 한 checker family**다. predictor/found는 별도 independent acceptance가 아니다. A-EV exact object는 local 복구했으나 comparison-only / NOT A TRUSTED ANTECEDENT다. 새 V1이 A-EV 함수를 복사하지 않는다.

## Full recheck와 private schema projection

recheck process는 원래 bounded Input/Certificate와 독립 검증한 승인 사양을 받아 모든 hash/state/phase/role/grid/constants/budget을 다시 검사한다. producer가 적은 `final_interval`, constants override 또는 derivative override는 wire에서 허용하지 않는다. validator를 producer parser helper로 공유하지 않는다. canonical byte framing/hash protocol이라는 data 의미는 공유하지만 실행 parser validation은 분리한다.

relative raw는 재검증한 absolute state에서 `r_j_raw-r_i_raw`로 직접 다시 만든다. V2 certificate는 source의 정확 FORMAT=`c1b1-exact-impulse-certificate-v2`, METHOD=`dyadic-outward-taylor-v2` token으로 구성한다(해당 source literal과 exact equality를 요구한다). contract c1a-ar2-lang2024-v1, frozen fingerprint, retardation=true는 private legacy 타입이고 Lab wire bool 허용을 뜻하지 않는다. input position_frac_bits=48, dr_raw[3] canonical integer strings, component=0/1/2 native small integer, dt_kick=`20` canonical legacy rational string이다. output width=96, frac_bits=80, raw=각 axis claim; proof sqrt_bits=N/work_bits=P_R 및 아래 9개 rate/full/n_R를 exact decimal rational로 넘긴다. runtime_binding은 private projection에도 넣지 않는다.

rate order는 BO.alpha1, BO.alpha2, REL.alpha1, REL.alpha2, QED.alpha1, QED.alpha2, BO.eta, REL.eta, QED.eta이다. wire rate_id는 각각 BO_ALPHA_1, BO_ALPHA_2, REL_ALPHA_1, REL_ALPHA_2, QED_ALPHA_1, QED_ALPHA_2, BO_ETA, REL_ETA, QED_ETA. source RATE_ORDER에 실제 고정된 이 순서를 따른다. legacy full mode 소문자 `full`로 exact mapping한다. legacy fraction string은 n 또는 n/d의 exact canonical value로만 만들며 pre-str guard를 받는다.

V2는 자기 sqrt/powers/exp/dV/force/J enclosure를 재구성하고 strict rounding cell 포함을 검사한다. producer가 final interval만 주고 rechecker가 cell만 확인하는 구조가 아니다. wrong constants/spec은 Lab binding 및 V2 frozen model check에서 거부된다. producer의 누락 derivative는 독립 V2 재구성과 다른 claim을 만들 수 있어 I15/I19의 nondegenerate semantic mutant로 검증해야 한다.

## 기존 source의 제한과 보완 의무

V2는 even raw도 cell **strict interior**만 받아 exact tie를 증명하지 못할 수 있다. nearest-even 물리 의미를 바꾸지 않고 availability 제한으로 둔다. axis q_k=0은 V2가 not_a_decision으로 거부하므로 recheck binding이 exact input equality로 zero를 따로 증명한다. 이는 새로운 nonlinear 엔진이 아니라 integer zero identity의 검증이다. all-zero separation이나 domain 실패를 shortcut으로 통과시키지 않는다.

V2 runtime_binding은 의미 binding 검증을 하지 않는다. 이를 Lab occurrence proof로 사용하지 않는다. full-state/acquisition/budget/source identity는 별도 independent Lab validator의 TCB다. V2 stats의 float/seconds는 proof 권위가 아니며 Lab wire에서 버린다. unexpected exception은 bounded ERROR/STOP이다. 기존 Limits의 사후 bit 검사/협력 시간검사를 hard allocation guard로 부르지 않는다; B5 whole-call preflight+isolated hard caps가 없으면 NOT_PROVED/STOP.

구현 승인 후 source allowlist/import AST, 별도 processes의 실제 sys.modules/call records, no shared helpers, immutable inputs, pinned bytes, zero shortcut, model/raw mismatch 및 forged certificate 거부를 검사한다. 기존 문서 hash만으로 I12/I19 PASS를 부여하지 않는다. 공유 물리 source 전사 오류와 Python/Fraction/theorem 신뢰의 correlated risk는 남으며 certification으로 확대하지 않는다.
