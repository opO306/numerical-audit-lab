# C1-B1 Independent Impulse V1: F-CLOSURE-1 / F-CLOSURE-2 제한 독립 재감사

## 최종 판정

**DESIGN / PRE-IMPLEMENTATION CLOSURE PASS**

**IMPLEMENTATION MAY START WITH EXPLICIT RUNTIME-INSTANCE CONDITIONS**

```yaml
audited_commit: 8e5865964770b3752326d361276cbccd125c547a
direct_parent: 4cb2910fe936f7b1d5150196e062b6b61edc240f
F-CLOSURE-1: PASS
F-CLOSURE-2: PASS
closure_package: PASS
implementation_may_start: true
implementation: NOT YET IMPLEMENTED
runtime_activation_allowed: false
impulse: J_NOT_VERIFIED
certification: NotCertified
```

두 사전 구현 규범 blocker는 새 target에서 해소됐다. 이는 아직 없는 Impulse 구현의 정확성 PASS나 runtime activation 승인이 아니다. 기존 Arithmetic V1은 `65d8fd29ae255529afead70289098d36b825b3b4`의 감사 범위에서 PASS를 유지한다. `exact_slow`는 DEFAULT, `exact_fast`는 EXPERIMENTAL / OPT-IN, Arithmetic scope는 ARITHMETIC_ONLY다.

역사적 `4cb2910fe936f7b1d5150196e062b6b61edc240f`의 **CLOSURE REVISION REQUIRED / implementation_may_start=false / F-CLOSURE-1 / F-CLOSURE-2**는 그대로 유지한다. 이번 결론은 사용자가 지정한 target SHA에만 적용한다. 새 finding은 없다.

## 1. 범위와 직접 수행한 작업

저장소는 `opO306/numerical-audit-lab`, 확인한 branch는 `codex/c1b1-fclaim1-output-limit`다. 별도의 no-checkout clone에서 immutable Git 객체를 읽었다. 사용자 원본 working tree를 수정하거나 commit/push하지 않았다. No-checkout clone의 상태를 clean checkout이라고 표현하지 않는다.

독립 작성한 `independent_reaudit.py`는 Git tree와 blob bytes, canonical JSON, dependency, 규범 diff를 검사했다. 작성자의 `check_static.py`나 저장된 PASS 결과를 실행하거나 correctness oracle로 삼지 않았다. 정적 assertion **71개가 PASS**였다. 이는 production pytest 개수나 수학적 완전성의 증명이 아니다.

별도 `verify_preserved_witness.py`는 이전 witness JSON의 기약 유리수 부호와 저장된 차이를 정수 교차곱으로 검산했다. 기존 witness script, Arithmetic kernel, Impulse evaluator, V2, production pytest, mutant, benchmark는 실행하지 않았다. Potential 전체 수학, 91 constants 전사, A-EV Merkle 증명도 재수행하지 않고 이번 delta의 바이트 보존을 확인했다.

직접 Git 확인은 `evidence/independent_results.json`, 규범 변경은 `evidence/normative_docs.diff`와 `evidence/semantic_delta.json`, 과거 자료와 실제 새 received copy의 일치는 `evidence/history_copy_checks.json`에 남겼다.

최종 정적 실행의 관찰 기간은 **2026-10-04 16:58:59.957087Z ~ 16:59:09.564643Z**, 한국 시간 **2026-10-05 01:58:59 ~ 01:59:09**다. 두 시점에 요청 branch가 target을 가리켰다. 그 이후 원격 상태를 보증하지 않는다. Target의 committer timestamp는 2026-10-04 16:43:59Z이며, 실제 push 시각으로 단정하지 않는다.

## 2. R1–R14 판정

| 항목 | 판정 | 직접 근거 |
|---|---|---|
| R1 Git / delta | **PASS** | 정확한 target/parent Git 객체 확인. 신규 42, 수정 22, 삭제 0. 규범 문서·spec·sidecar와 audit/history 자료로 분류. |
| R2 F-CLOSURE-1 historical finding preserved | **PASS** | Parent의 잘못된 stored-segment 요구가 보존되고 과거 보고서·판정 사본의 SHA가 실제 이전 첨부와 일치. |
| R3 F-CLOSURE-1 fix correctness | **PASS** | B3/domain과 B8/status의 active 규범이 exact unrounded closed segment minimum AND stored final relative position squared로 일치. |
| R4 witness interpretation | **PASS** | 보존된 기약 유리수와 차이의 정수 교차곱을 독립 재검산: 부호 +,+,-. 계약 비동치 증거로만 사용. |
| R5 F-CLOSURE-2 historical finding preserved | **PASS** | Parent의 두 Failure key 집합 차이가 resource_kind 하나임을 직접 다시 비교. 과거 FAIL을 변경하지 않음. |
| R6 F-CLOSURE-2 fix correctness | **PASS** | Primary JSON, secondary closed-fields 문구, B4 표의 순서·집합이 같은 11개. required resource_kind와 resource enum/nonresource null 규칙 일치. |
| R7 resource contract preservation | **PASS** | Wire limits와 parser/writer/publication 의미가 불변. Failure 보수적 최대 789 bytes로 cap 4096 이내. |
| R8 canonical / hash / dependency consistency | **PASS** | Canonical JSON 9개와 sidecar 9개 검산. 28개 dependency 참조, package semantic ID, active 20파일의 stale hash 부재 확인. |
| R9 no unrelated semantic redesign | **PASS** | 실제 semantic delta는 guard/Failure 정정과 종속 hash·review/revision metadata. Constants와 B5/B6/B7의 규칙·상태층·mutation 계획 재설계 없음. |
| R10 Arithmetic antecedent preservation | **PASS** | 65d8fd2의 8개 보호 파일과 target 실제 Git blob bytes 및 SHA-256 일치. |
| R11 no production implementation | **PASS** | Production/test delta 0. 추가 Python은 audit/check_static.py 및 received historical witness의 2개뿐. V2 source 보존. |
| R12 obligation blocker closure | **PASS** | I1→READY, I10/I14/I18→IMPLEMENTATION-DEPENDENT. 나머지 의무의 직전 독립 분류 보존. |
| R13 B5 activation separation | **PASS** | B5는 dependency hash 외 불변. METHOD SPEC PASS를 유지하며 numeric instance·activation decision·resource 보호 없는 실행은 승인하지 않음. |
| R14 provenance preservation | **PASS** | Constants bytes 및 P0/원본/A-EV의 22개 provenance 파일 실제 bytes 보존. 과거 전사·Merkle 판정을 선행 근거로만 유지, A-EV trust 승격 없음. |

## 3. Git / delta / 역사 보존

직접 parent는 `4cb2910fe936f7b1d5150196e062b6b61edc240f`, target tree는 `0914445ba53684b85f87846739523002b05ed88c`다. `target.commit.raw`의 실제 내용에서 Git commit object ID도 재계산했다.

| 분류 | 수정 | 추가 | 삭제 |
|---|---:|---:|---:|
| 기존 normative docs | 6 | 0 | 0 |
| canonical spec JSON | 8 | 0 | 0 |
| spec SHA-256 sidecar | 8 | 0 | 0 |
| 새 fix report | 0 | 1 | 0 |
| audit 자료 | 0 | 2 | 0 |
| current archive / 수신 자료 / receipt / request / static evidence | 0 | 39 | 0 |
| production source / production tests | 0 | 0 | 0 |
| **합계** | **22** | **42** | **0** |

Parent tree는 2,055개, target tree는 2,097개 파일이다. 기존 2,055개 중 수정되지 않은 파일은 2,033개다. 신규 Python은 아래 두 개뿐이며 production 구현과 구분했다.

```text
audit/c1b1-closure-fixes-2026-10-05/check_static.py
current/c1b1-closure-fixes-2026-10-05/received/guard_contract_witness.py
```

첫 파일은 audit 전용 정적 검사기, 두 번째는 기존 계약 비동치 witness의 보존 사본이다. 이 둘도 이번 감사에서 실행하지 않았다.

새 before-docs 6개와 before-specs 19개를 parent의 실제 bytes에 직접 대조했고 **25/25 동일**했다. 새 received에 복사된 이전 보고서·판정·witness·정적 결과 7개는 현재 대화에 실제 첨부된 원본 bytes와 SHA-256/크기를 비교해 **7/7 동일**했다. 따라서 과거 FAIL을 새 PASS로 덮어쓴 정황은 없다. 옛 문구와 해시가 이런 archive에 남는 것은 정상이다.

문서의 author-time `아직 commit되지 않았다`, `RECHECK PENDING` 등의 표시는 그 기록 시점과 구분한다. 새 Git commit 존재를 이유로 과거 receipt를 오류로 바꾸지 않는다.

## 4. F-CLOSURE-1: 수정 PASS

### 과거 결함의 의미

기존 Arithmetic 계약은 exact unrounded relative segment 전체의 최소 거리와 stored 최종 상대 위치 한 점을 별도로 검사한다. Parent B3의 stored rounded segment 전체 검사 요구는 다른 조건이었다. 이 역사적 비동치는 무효화하지 않는다.

### 수정본의 단일한 규범

B3 문서와 `physical-domain.json.guard_contract`, B8 문서와 `status-composition.json.future_KDK`를 대조했다. 다음 의미로 일치한다.

```text
Point admission:
    exact current R² >= r_min²

After drift:
    minimum over the exact unrounded closed relative segment >= r_min²
    AND
    stored final relative position squared >= r_min²
```

수학적으로, ρ = r_min², q1_exact는 unrounded endpoint, q1_stored는 stored endpoint일 때:

```text
min_{0 <= t <= 1} ||q0 + t(q1_exact - q0)||² >= ρ
AND
||q1_stored||² >= ρ
```

추가로 `min ||q0+t(q1_stored-q0)||²`를 요구하지 않는다. 정확한 segment 검사를 endpoint admission만으로 대체하지도 않는다.

Domain JSON의 실질 변경은 `applies_to[1]`, `cases["R=r_min"]`의 guard 참조, 새 `guard_contract` 명시다. r_min 수치, 단위, threshold equality, R=0/below-domain 처리, denominator regularity는 변하지 않았다. B8의 실질 변경도 future KDK guard 참조 하나다. 일반 상태층·실패 우선순위·publication 의미는 그대로다.

### Witness 재검산과 해석 제한

이전 JSON의 저장값에서 n1/d1과 n2/d2의 비교를 `n1*d2 - n2*d1`의 부호로 직접 판정했다. 저장된 차이 유리수도 같은 차이를 나타내는지 교차곱으로 확인했다.

| 보존된 양 | r_min²와의 관계 |
|---|---|
| exact unrounded segment minimum | **>** |
| stored final endpoint R² | **>** |
| initial point부터 stored rounded endpoint로 이은 선분 minimum | **<** |

따라서 원래 Arithmetic 계약은 허용하고 잘못 추가된 stored-segment 조건은 거부한다. 이 결과의 용도는 오직 **PRE-IMPLEMENTATION CONTRACT NON-EQUIVALENCE WITNESS**다. Arithmetic kernel bug, Impulse bug, D_valid failure, integrator failure, trajectory failure로 확대하지 않는다.

이 재감사에서는 segment 최소값을 생성한 기존 script를 다시 실행하지 않았다. 이미 보존된 정확한 유리수와 부호 관계의 독립 재검산만 했다. 검산 소스와 결과는 `verify_preserved_witness.py`, `witness_recheck.json`이다.

## 5. F-CLOSURE-2: 수정 PASS

다음 세 위치의 Failure field 집합과 순서가 모두 같은 11개임을 직접 비교했다.

```text
proof-wire.json.closed_object_keys.Failure
proof-wire.json.resource_failure_record
B4-proof-wire-resource.md의 Failure 표
```

정식 field는 다음과 같다.

```text
schema, status, phase, reason, resource_kind,
spec_sha256, state_sha256, occurrence_sha256, budget_sha256,
attempt_count, attempt_digest
```

`resource_kind_rule`과 추가된 B4 설명도 일치한다. `resource_kind`는 언제나 존재하는 required key다. Resource-related failure에는 정해진 enum, non-resource failure에는 null을 넣는다. 두 closed 목록 사이에 암묵적인 precedence를 둔 것이 아니라 목록 자체가 같아졌다.

Parent JSON을 별도로 읽었을 때는 같은 두 목록의 집합 차이가 정확히 `{"resource_kind"}`였다. 새 JSON은 이 차이가 비어 있다. 따라서 과거 finding의 존재와 새 수정의 효과를 각각 확인했다.

## 6. Resource 계약: 불변, 789-byte 보수적 상한

`proof-wire.json`의 모든 limits, parser/writer 순서, resource kind 정책, publication 규칙은 dependency hash와 누락 필드 정정을 제외하고 parent와 동일하다.

| 항목 | 유지된 규범 |
|---|---|
| Canonical integer | Sign 제외 최대 4096 decimal digits |
| Rational | Exact reduction 후 분자·분모 정수 한도 확인 |
| Complete proof artifact | 최대 1,048,576 bytes, terminal LF 포함 |
| Failure | 최대 4096 bytes |
| Diagnostics / metadata | 자유 payload·거대 원문·예외 문자열 echo 금지 |
| Process-global integer-string limit | 변경 금지, host conversion refusal은 bounded 처리 |
| Publication | 세 축·전체 artifact 승인 전 partial publication 금지 |

고정 key와 punctuation, 64자리 hash들, 각 layer·phase·reason·resource_kind enum의 최대 길이, 실패 attempt_count=null을 이용해 canonical Failure 크기의 상한을 다시 계산했다. 결과는 **789 bytes**다. 실행상 동시에 발생할 수 없는 enum 조합까지 최대 길이로 선택했으므로 보수적 상한이며, 실제 production serializer를 실행한 관측이 아니다.

789 <= 4096이므로 field 정합성 복구 때문에 cap을 넓힐 이유가 없다. 실제로 cap은 바뀌지 않았다. 내부 계산 성공, proof 구성, rechecker acceptance, serializable artifact, atomic publication의 구분도 유지된다.

## 7. Canonical / dependency hash 재발급

Target의 canonical JSON 9개와 sidecar 9개를 전부 실제 Git blob bytes에서 재계산했다. ASCII JSON, lexical key sort, compact separator, ensure_ascii escape, terminal LF 1개 및 duplicate/nonfinite 부재를 확인했다.

Dependency 참조 **28개**를 검산했다. 여기에는 package manifest member 8개, semantic bundle dependencies 및 P0/source-recovery의 외부 고정 hash 참조가 포함된다. Package의 별도 semantic_bundle_sha256도 실제 semantic bundle hash와 같았다.

| Canonical JSON | Target SHA-256 | 변화 |
|---|---|---|
| `acquisition-identity.json` | `673941bf9f88835f9ee494268e2837a6bd3e6b09323ad75db70d1f8df7666759` | 재발급 |
| `constants.json` | `f1cf6a71afaf45e40db37a6e8a5b4f643a57885f4040d4fa285835530363e196` | 불변 |
| `finite-policy.json` | `e8ceec423827a0699a8d3709508dff3eebd7f7e8a99f92d4436dc7b57f83fdd8` | 재발급 |
| `package-manifest.json` | `9d430833bb359600b4c9f67f225e9c8a74fb883d6fe119ca8b7c2502b8ce4499` | 재발급 |
| `physical-domain.json` | `eef0a3531c7bc5f233e7cd7212c3807735c05bc88284bd16600c894afc817c03` | 재발급 |
| `proof-wire.json` | `b7994420f6896eb352730ac0fb5983a6c74c0635d357dffea3281535b57f27e9` | 재발급 |
| `rechecker-lineage.json` | `4767ae1773fa2f697e749b90aa1b66da686605cbfb690307aa9c2d0c87427ab9` | 재발급 |
| `semantic-bundle.json` | `11eedb45fc80d8b1f8db1bc5afdceb1754914c5e2f49ba48ad2b4d87d63bb007` | 재발급 |
| `status-composition.json` | `4257563b2c82a66094f96da539cdf9bbe1967699403fd61ba613d195b26483ee` | 재발급 |

8개 JSON과 그 8개 sidecar가 재발급됐고 `constants.json` 및 sidecar는 불변이다. Active normative 범위인 `docs/c1b1-independent-impulse-v1/*.md` 11개와 `specs/c1b1-independent-impulse-v1/*.json` 9개, 합계 **20개 파일**에서 수정 전 hash의 stale reference와 잘못된 stored-segment 요구 문구를 검사했다. 발견되지 않았다.

이는 repository 전체에서 과거 표현을 지웠다는 뜻이 아니다. 기존 설계, 받은 감사 보고서, before-* 사본과 receipt의 역사적 문구·hash는 보존한다.

## 8. 최소 변경과 기존 PASS antecedents

Parsed JSON을 leaf 단위로 직접 비교했다.

| 파일군 | dependency hash 외 변화 |
|---|---|
| physical-domain.json | F-CLOSURE-1 guard 의미와 명시적 guard_contract |
| proof-wire.json | F-CLOSURE-2 secondary field 목록에 resource_kind 복구 |
| status-composition.json | future_KDK의 guard 참조 |
| semantic-bundle.json | 없음 |
| finite-policy.json | 없음 |
| rechecker-lineage.json | 없음 |
| acquisition-identity.json | 없음 |
| constants.json | bytes 자체 불변 |
| package-manifest.json | 새 semantic hash, fix revision 식별자, 독립 재검토 대기 metadata |

Package revision은 `F-CLOSURE-1-2-2026-10-05`, revises_snapshot은 parent, scope는 두 finding으로 명시한다. 기존 B1/B2/B5/B6/B7의 의미, B8 일반 layer/state 구조, mutation/validation 계획의 재설계는 없다. 문서 6개의 diff도 직접 검토했다.

8개 Arithmetic 보호 파일은 antecedent와 target의 실제 bytes 및 SHA-256이 일치했다.

| 파일 | 공통 SHA-256 | Bytes |
|---|---|---:|
| `claim_adapter.py` | `24b05ebf374728583ba725c83b8f9324f4b75b5515b03c5b1036339eef3e4899` | 7,649 |
| `compare.py` | `5ad6b3f0b03b240e559c955552f32eb9079d524fba55be47ab88329a7d0657b2` | 2,425 |
| `contracts.py` | `37acf394c9c252d5e401fdff06fcb28a0ab1202cc090f1456ecd4bb84fff47ed` | 5,856 |
| `exact_slow.py` | `b36efc03abdcb760f294f009ea1aea8aafa6fcc05a53c7b3970291c90edf4c13` | 3,400 |
| `exact_fast.py` | `2190e099642b4bf440e4a2280b09d4b89984f637e6cee1b09dfa23411f0b4c0b` | 3,170 |
| `exact_geometry.py` | `b237cd00e45e2ed635bae54880cfef88c1126e98af57d74843b752d2ed27677e` | 2,724 |
| `semantic_manifest_v1.json` | `3217fc38aa798fff3ffea8072cecafaecac9f98be85589e9fa35a9dc6aa8119b` | 4,385 |
| `semantic_manifest_v1.sha256` | `ae8b89667a539b4252cac34b0f96786dda67c10747e66f2468482d94e5a6db79` | 93 |

따라서 Arithmetic의 기존 독립 PASS를 선행 근거로 유지한다. 새 Impulse correctness를 승인한 것은 아니다.

P0 및 복구 원본/A-EV object 자료의 **22개 provenance 파일**도 parent와 실제 bytes가 같았다. P0는 12,061 bytes와 SHA-256 `a598057183121b9c928b3a9804c8e2e99afa553bad570a471aa4130f20e6b049`를 유지한다. Constants 91개 전사가 맞았다는 사실과 A-EV exact commit/object의 과거 검증을 보존된 antecedent로 사용하며, 이번에 전사·Merkle 검사를 전부 새로 했다고 주장하지 않는다. A-EV의 역할은 comparison-only / NOT A TRUSTED ANTECEDENT다.

## 9. I1–I22 후속 분류

두 finding에 의해 BLOCKED였던 사전 규범 의무가 해제됐다.

**I1은 READY**다. 단, 새로운 구현의 formula transcription이나 correctness PASS가 아니다.
**I10 / I14 / I18은 IMPLEMENTATION-DEPENDENT**다. Failure 처리·불변성·composition·resource majorant와 enforcement의 실제 증거는 구현 후에만 얻을 수 있다.

| 의무 | 직전 독립 상태 | 이번 후속 상태 |
|---|---|---|
| I1 | BLOCKED | **READY** |
| I2 | IMPLEMENTATION-DEPENDENT | **IMPLEMENTATION-DEPENDENT** |
| I3 | READY | **READY** |
| I4 | READY | **READY** |
| I5 | READY | **READY** |
| I6 | READY | **READY** |
| I7 | READY | **READY** |
| I8 | READY | **READY** |
| I9 | IMPLEMENTATION-DEPENDENT | **IMPLEMENTATION-DEPENDENT** |
| I10 | BLOCKED | **IMPLEMENTATION-DEPENDENT** |
| I11 | IMPLEMENTATION-DEPENDENT | **IMPLEMENTATION-DEPENDENT** |
| I12 | IMPLEMENTATION-DEPENDENT | **IMPLEMENTATION-DEPENDENT** |
| I13 | IMPLEMENTATION-DEPENDENT | **IMPLEMENTATION-DEPENDENT** |
| I14 | BLOCKED | **IMPLEMENTATION-DEPENDENT** |
| I15 | IMPLEMENTATION-DEPENDENT | **IMPLEMENTATION-DEPENDENT** |
| I16 | IMPLEMENTATION-DEPENDENT | **IMPLEMENTATION-DEPENDENT** |
| I17 | READY | **READY** |
| I18 | BLOCKED | **IMPLEMENTATION-DEPENDENT** |
| I19 | IMPLEMENTATION-DEPENDENT | **IMPLEMENTATION-DEPENDENT** |
| I20 | IMPLEMENTATION-DEPENDENT | **IMPLEMENTATION-DEPENDENT** |
| I21 | IMPLEMENTATION-DEPENDENT | **IMPLEMENTATION-DEPENDENT** |
| I22 | IMPLEMENTATION-DEPENDENT | **IMPLEMENTATION-DEPENDENT** |

아직 구현되지 않은 의무를 모두 PASS로 만들지 않았다. 나머지 상태는 의미 변화가 없는 한 직전 독립 판정을 그대로 유지했다.

## 10. 구현 착수와 runtime activation

B5는 **METHOD SPEC PASS / RUNTIME NUMERIC INSTANCE STILL REQUIRED BEFORE ACTIVATION**다. Numeric instance 미발급이 과거 closure FAIL의 원인이 아니었고, 이번 두 수정의 PASS가 곧 activation 승인이 되지도 않는다.

사전 구현 closure가 통과했으므로 규정된 scope의 구현 착수는 허용한다. 실제 production 실행 전에는 승인된 exact numeric instance/hash와 independent activation decision, source/platform/allocator-bound resource majorants, pinned V2 whole-call preflight 및 실제 isolated worker memory/CPU/wall enforcement가 필요하다. 기존 V2의 사후 bit 검사와 cooperative time check만으로 이를 대신할 수 없다. 향후 구현은 specification의 correctness·독립성·failure·publication 검증을 별도로 받아야 한다.

이번에 허용한 최대 상태는 다음과 같다.

```text
Independent Impulse V1:
  DESIGN / PRE-IMPLEMENTATION CLOSURE PASS
  implementation_may_start = true
  implementation = NOT YET IMPLEMENTED
  runtime_activation_allowed = false

Arithmetic V1:
  INDEPENDENT REVIEW PASS
  exact_slow = DEFAULT
  exact_fast = EXPERIMENTAL / OPT-IN
  scope = ARITHMETIC_ONLY

Overall physical:
  J_NOT_VERIFIED
  NotCertified
```

## 11. 재현과 패키지 한계

`independent_reaudit.py`는 고정 commit들이 있는 Git repository를 인자로 받아 객체부터 다시 검산한다. 출력 directory는 아직 존재하지 않는 별도 경로여야 한다. 이 패키지는 전체 repository나 모든 raw source snapshot을 포함한 배포본이 아니다. 실제 source 재검산에는 Git 객체가 필요하며, 포함된 diff/record만을 원본 source와 동등한 것으로 취급하지 않는다.

`verify_packet.py`는 패키지 파일 SHA-256, 고정 target/parent의 recorded binding, raw commit object ID, 역사적 verdict 보존, 정적 결과와 witness 부등식을 검증한다. 이는 production correctness나 모든 미래 runtime 동작을 인증하는 도구가 아니다. 상세 실행 방법은 `REPRODUCE.md`다.

### 감사 도구 자체의 수정 기록

초기 독립 checker의 7개 flag 중 6개는 `domain_sha256`, `wire_sha256`, `identity_sha256`, `policy_sha256` 같은 abbreviated dependency key를 실제 파일명으로 연결하지 못한 감사 도구 문제였다. 나머지 하나는 허용 가능한 package review/revision metadata를 처음의 좁은 allowlist가 분류하지 못한 경우였다. 해당 source의 dependency 의미와 정확한 metadata 값을 직접 읽고 감사 도구만 수정해 새 출력 경로에서 재실행했다. Target 규범이나 production source는 변경하지 않았다.

최종 checker는 metadata에 임의 허용을 주지 않고 exact 예상 revision/status 값을 따로 검증한다. 최종 **71/71 static assertion PASS**다. 초기 소스와 결과는 `auditor_initial/`, 수정 설명은 `auditor_corrections.json`에 그대로 남겼다. 이를 target의 새 correctness 결함으로 보고하지 않는다.

**두 finding의 사전 규범 불일치는 `8e5865964770b3752326d361276cbccd125c547a`에서 해소됐다. 구현 착수는 허용되지만, 구현 완료·J 검증·runtime activation·물리 또는 trajectory 인증은 승인되지 않았다.**
