# C1-B1 Independent Impulse V1: B1–B8 closure 독립 재검토

## 최종 판정

**CLOSURE REVISION REQUIRED**

```yaml
audited_commit: 4cb2910fe936f7b1d5150196e062b6b61edc240f
direct_parent: 023b186c0e9d95c11399893e7f75772cfff6c3a7
arithmetic_antecedent: 65d8fd29ae255529afead70289098d36b825b3b4
implementation_may_start: false
runtime_numeric_instance_required: true
```

B3의 guard 연결에 **F-CLOSURE-1**, B4 Failure key 집합에 **F-CLOSURE-2**가 있다. 기존 Arithmetic V1의 “exact unrounded 선분 최소 + stored 종점” 검사를 “exact 선분 전체 + stored 선분 전체” 검사로 바꿨다. 두 계약이 같지 않음을 승인된 FX grid/full dt/명목 mass를 사용한 exact rational 반례로 확인했다. 아직 구현된 코드의 오답을 발견한 것이 아니라, 구현 전 사양을 정정해야 한다는 판정이다.

**두 finding은 규범 정정 요구다. Numeric budget 숫자가 아직 없다는 사실은 이 FAIL의 원인이 아니다.** B5의 parameterized method contract는 PASS로 평가한다. 다만 실제 production 실행 전에 정확한 numeric instance와 source/platform/allocator/worker에 결합된 활성화 승인이 필요하다.

기존 `f806d8c`의 overall FAIL/F-CLAIM-1, `65d8fd2`의 Arithmetic PASS, `023b186c`의 conditional design PASS 및 implementation=false는 역사적 판정으로 보존한다. 이번 결론은 4cb2910에만 귀속된다.

## 0. Snapshot 선택과 수행 범위

최신 붙여넣은 요청은 “전달된 고정 snapshot을 사용”하라고 했으나 새 closure commit/branch literal을 포함하지 않았다. 연결된 저장소에서 closure 자료를 포함한 branch를 조회한 뒤, `codex/c1b1-fclaim1-output-limit`의 `4cb2910fe936f7b1d5150196e062b6b61edc240f`를 발견했다. 직접 parent가 이전 설계 `023b186c...`임을 확인하고 검토 시작부에서 이 선택을 알린 뒤 모든 source read를 해당 SHA로 고정했다. 사용자가 새 SHA를 명시적으로 제공했다고 주장하지 않는다.

Commit object의 timestamp는 2026-10-04T14:33:32Z다. 이는 실제 push 시각을 증명하는 값은 아니다. 검토한 author receipt-after는 14:29:45.001643Z에 parent HEAD에서 작성됐다. 문서의 “아직 commit하지 않음”은 작성 당시 기록이며 뒤에 target commit이 생긴 사실과 모순이 아니다.

별도 임시 **no-checkout Git clone**에서 `git show <SHA>:<path>`와 `git ls-tree`로 객체를 읽었다. 해당 clone의 `git status`는 checkout을 생략했으므로 비어 있지 않다. 그 상태를 clean worktree라고 부르지 않는다. before/after status hash는 같고, 검토 대상 production checkout을 수정하지 않았다.

실행한 것은 Git/raw hash/정적 AST/정수 전사 검산과 guard 의미를 구분하는 별도 exact-rational 논증 script다. Impulse/V2 evaluator, production pytest, mutant 또는 benchmark는 실행하지 않았다. Commit/push도 하지 않았다.

## 1. C1–C12 판정

요청 마지막의 C 번호를 따른다. PASS는 그 행의 계약·증거에 한정한다. 예를 들어 B1의 규범 데이터 구조와 식이 PASS여도 B3의 잘못된 guard 요구가 정당화되지는 않는다. 같은 결함을 여러 신규 finding으로 중복 계산하지 않고 C3/I1/I14/최종 Gate에 연결한다.

| ID | 항목 | 판정 | 직접 근거 |
|---|---|---|---|
| C1 | B1 semantic bundle | **PASS** | 규범식·수치 의미·버전·canonical bytes와 8개 dependency 결합 확인. B3의 잘못된 guard 조건은 C3에서 별도 FAIL로 귀속한다. |
| C2 | B2 units/constants provenance | **PASS** | P0 12,061 raw bytes 직접 hash, 91 exact record 및 87 P0 declaration/index/unit 검산, S1/S2 4개 값 대조, Git objects 20개와 Merkle paths 8개 검증. |
| C3 | B3 domain/r_min | **FAIL** | r_min 값과 admission은 맞지만 stored endpoint guard를 stored segment 전체 guard로 바꾸었다. F-CLOSURE-1의 정확 반례로 비동치 확인. |
| C4 | B4 proof wire/resources | **FAIL** | 4096-digit/pre-str/compact proof 전략은 타당하지만 proof-wire.json의 두 closed Failure field 목록이 resource_kind 필수 여부에서 충돌한다. F-CLOSURE-2. |
| C5 | B5 finite computation policy | **PASS** | METHOD SPEC PASS. PARAMETERIZED POLICY를 허용한다. 승인된 numeric instance·source-bound preflight·OS enforcement 없는 실제 실행은 금지. |
| C6 | B6 rechecker lineage | **PASS** | 독립 producer/validator와 pinned V2 경계가 명시됨. 소스와 private legacy projection 대조. 실제 구현 독립성은 구현 후 검증. |
| C7 | B7 acquisition/identity | **PASS** | State/projection/math/occurrence/acquisition/budget 구분, domain-separated identities, J0/J1·previous occurrence·cache 비활성 규칙 확인. |
| C8 | B8 status/composition | **PASS** | 각 layer 상태, 관측된 복합 실패 우선순위, point proof와 execution eligibility, atomic publication의 구분은 적절하다. 실제 future guard는 C3 수정 전 연결 불가. |
| C9 | I1–I22 ledger | **UNRESOLVED** | I1/I14는 F-CLOSURE-1, I10/I18은 F-CLOSURE-2 때문에 BLOCKED. 나머지는 READY 또는 IMPLEMENTATION-DEPENDENT로 재분류한다. |
| C10 | mutation/validation plan | **PASS** | 계획 closure만 PASS. 비퇴화 fixture·독립 expected·hash-only와 semantic detection 구분 및 위조/stale/partial-publication 공격 포함. |
| C11 | source/provenance preservation | **PASS** | 직접 parent 023b186c, 추가65/수정0/삭제0, Arithmetic8 actual bytes 불변, 신규 .py 없음. Git no-checkout 객체 기반 검토. |
| C12 | implementation readiness | **FAIL** | CLOSURE REVISION REQUIRED. B3와 B4의 규범 불일치가 남아 이 제출물의 착수 조건을 충족하지 못한다. |

## 2. F-CLOSURE-1: stored endpoint를 stored segment로 바꾼 계약

### 2.1 충돌하는 규범

B3 `B3-physical-domain.md`의 “명시적 설계 선택”에는 다음과 같이 적혀 있다.

> future guard는 exact segment와 저장 segment 각각의 모든 t∈[0,1]에서 R²(t)>=r_min²를 요구한다.

`physical-domain.json.applies_to`에도 `future exact and stored drift segment guards`가 들어간다. 반면 byte-preserved Arithmetic manifest의 `geometry`는 다음 두 검사다.

```text
segment_intrusion = min_R2(exact unrounded segment) < threshold
stored_intrusion  = stored_relative dot stored_relative < threshold
```

두 번째는 저장된 새 상대 위치 **한 점**의 검사다. 초기점부터 rounded 새 종점으로 이어지는 별도 선분의 minimum을 계산하지 않는다. Exact unrounded 선분과 stored 종점 사이의 차이는 drift v2의 displacement rounding에서 발생한다.

B8의 기존 Arithmetic bytes/semantics 보존과 이 B3 문구를 동시에 구현하려면, 적어도 명시적으로 승인하지 않은 추가 guard가 필요하다. 단순 용어 차이로 넘길 수 없다. 추가 guard를 구현하면서 그 검출 결과를 기존 physical-domain/Arithmetic 거부와 동일시하면 감사 범위를 바꾼다.

### 2.2 실제 grid와 mass의 정확 반례

`guard_contract_witness.py`는 production 모듈을 전혀 import하지 않는다. 정수/유리수로 drift 정의와 볼록 이차식의 minimum만 계산한다. 각 값은 다음과 같다.

```text
position grid = FX(96,48)
momentum grid = FX(96,80)
full dt = 40
mass = 39.9623831237 / 5.485799090441e-4
     = 399623831237000000 / 5485799090441

r_i_raw = (0, 0, 0)
r_j_raw = (2814749767106560, 638292740302269, 0)
p_i_raw = (0, 3910941818978, 0)
p_j_raw = (-24218309663095054343866316188, 3910941818977, 0)
```

입력 raw, rounded displacement raw, 새 stored raw 모두 signed96 범위 안이다. `y=ceil(r_min*2^48)=638292740302269`로 잡았다. Y 운동량 두 개는 각 원자의 stored displacement가 1 raw와 0 raw로 나뉘도록 half-unit 양옆에 놓인다. 반면 exact 상대 Y displacement는 두 운동량 raw의 차이 1개에 해당하는 아주 작은 변화다.

계약대로 `RN_even(2^48 * (p_raw/2^80)*40/mass)`를 계산하면:

```text
delta_i_raw = (0, 1, 0)
delta_j_raw = (-3096224743817216, 0, 0)

r_i_new_raw = (0, 1, 0)
r_j_new_raw = (-281474976710656, 638292740302269, 0)
```

초기 상대 위치는 `(10, y/2^48, 0)`이고 stored 상대 종점은 `(-1, (y-1)/2^48, 0)`이다. Exact 상대 종점은 JSON에 기약 유리수로 보존했다.

선분 q(t)=q0+t*v에 대해 A=q0·q0, B=q0·v, C=v·v라 두고, endpoint 도함수 부호로 최소 위치를 나눈다. Interior에서는 minimum=A−B²/C를 쓴다. 대상의 geometry helper를 호출하지 않았다.

| 정확한 비교 | 결과 |
|---|---|
| exact unrounded segment minimum − r_min² | **양수** |
| stored endpoint R² − r_min² | **양수** |
| stored rounded segment minimum − r_min² | **음수** |

세 차이의 기약 분자·분모와 tau를 `guard_contract_witness.json`에 저장했고, 위 부호를 정확 교차곱으로 확인한다. 따라서 기존 두 guard는 허용하고 새 stored-segment 요구는 거부한다. 반례는 D_valid나 integrator 초기 입장, 실제 trajectory 또는 impulse 전이의 적합성 주장에 사용하지 않는다. **계약 비동치만 증명한다.**

### 2.3 최소 수정과 재검토 범위

추가 알고리즘을 만들지 말고 B3의 규범을 다음으로 되돌리는 것이 가장 작은 수정이다.

```text
Point admission:
    exact R² >= r_min²

After drift:
    minimum over the exact unrounded closed relative segment >= r_min²
    AND stored final relative position squared >= r_min²
```

`B3-physical-domain.md`, `physical-domain.json`과 같은 표현을 참조하는 규범을 정정하고, 바뀐 파일의 sidecar와 모든 전이 의존 SHA 및 package manifest를 새 revision에 맞춰 재발급해야 한다. 기존 Arithmetic source/manifest는 수정할 필요가 없다.

정말 stored 선분 전체도 검사하려는 의도라면 별도의 더 강한 정책으로 선언해야 한다. 목적, 추가 거부의 분류, 기존 admission과의 차이, 구현 위치와 감사 책임을 따로 검토해야 한다. 이 closure에서 기존 guard와 같은 것처럼 승인할 수 없다.

## 2A. F-CLOSURE-2: 같은 proof-wire 안의 두 closed Failure 목록이 다르다

`proof-wire.json.closed_object_keys.Failure`는 다음 필드를 요구한다.

```text
schema, status, phase, reason, resource_kind,
spec_sha256, state_sha256, occurrence_sha256, budget_sha256,
attempt_count, attempt_digest
```

`resource_kind_rule`도 `required Failure field`라고 명시하며, resource 실패가 아니면 null이라고 정한다. B4 markdown의 closed schema 표 역시 resource_kind를 포함한다.

그런데 동일 JSON의 `resource_failure_record`는 `closed fixed fields only`라면서 다음 집합만 나열한다.

```text
schema, status, phase, reason,
spec_sha256, state_sha256, occurrence_sha256, budget_sha256,
attempt_count, attempt_digest
```

두 집합의 차이는 정확히 `{resource_kind}`다. 첫 번째 규범대로 이 필드를 포함하면 두 번째 “only” 목록을 위반하고, 빼면 첫 번째 필수 key 규칙을 위반한다. 두 closed 목록의 우선순위는 명시되지 않았다. 감사자가 임의로 더 그럴듯한 목록을 골라 source 불일치를 없었던 것으로 처리하지 않는다.

이 finding은 메모리 침범이나 틀린 J가 관측됐다는 뜻이 아니다. **구현자가 두 방식으로 해석할 수 있는 failure schema를 구현 전 단일화해야 한다는 요구**다. 가장 작은 정정은 이미 명시된 resource_kind 필수 규칙을 유지하면서 `resource_failure_record`의 목록에도 같은 필드를 넣는 것이다. Nonresource failure의 null 규칙을 유지한다. 이후 wire 및 모든 dependent hash/sidecar를 새 revision으로 발급한다.

고정 enum 필드 하나를 포함하는 것 자체는 기존 4096-byte failure cap을 어렵게 만들지 않는다. 이 정정에 새로운 계산기나 production source 수정은 필요 없다. `failure_key_conflict.json`은 원문에서 읽은 두 집합과 set difference를 기록한다.

## 3. Git / 실제 바이트 / provenance

| 직접 확인 | 결과 |
|---|---|
| target parent | 023b186c0e9d95c11399893e7f75772cfff6c3a7 |
| parent tracked count | 1,990 |
| target tracked count | 2,055 |
| 신규 / 수정 / 삭제 | 65 / 0 / 0 |
| docs 추가 | 13 |
| specs 추가 | 19 |
| current evidence/reference 추가 | 33 |
| 신규 .py | 0 |
| 보호 Arithmetic source/manifest | 8/8 actual bytes 동일 |
| 기존 설계서 | 불변 |

`.raw`에 저장된 Fortran/checker/A-EV source 객체는 읽기용 provenance다. 이를 신규 Impulse production source나 새로 실행한 구현으로 세지 않는다. Compare 기준은 작업트리의 filename 유사성이 아니라 고정 commit의 mode/type/object ID 및 실제 blob bytes다.

### 3.1 Arithmetic antecedent의 보존

아래 SHA는 `65d8fd2`와 `4cb2910`의 Git blob bytes를 각각 읽고 비교했다.

| 파일 | 동일한 SHA-256 | 결과 |
|---|---|---|
| `claim_adapter.py` | `24b05ebf374728583ba725c83b8f9324f4b75b5515b03c5b1036339eef3e4899` | 동일 |
| `compare.py` | `5ad6b3f0b03b240e559c955552f32eb9079d524fba55be47ab88329a7d0657b2` | 동일 |
| `contracts.py` | `37acf394c9c252d5e401fdff06fcb28a0ab1202cc090f1456ecd4bb84fff47ed` | 동일 |
| `exact_fast.py` | `2190e099642b4bf440e4a2280b09d4b89984f637e6cee1b09dfa23411f0b4c0b` | 동일 |
| `exact_geometry.py` | `b237cd00e45e2ed635bae54880cfef88c1126e98af57d74843b752d2ed27677e` | 동일 |
| `exact_slow.py` | `b36efc03abdcb760f294f009ea1aea8aafa6fcc05a53c7b3970291c90edf4c13` | 동일 |
| `semantic_manifest_v1.json` | `3217fc38aa798fff3ffea8072cecafaecac9f98be85589e9fa35a9dc6aa8119b` | 동일 |
| `semantic_manifest_v1.sha256` | `ae8b89667a539b4252cac34b0f96786dda67c10747e66f2468482d94e5a6db79` | 동일 |

이를 근거로 기존 Arithmetic PASS를 유지한다. 이번에 105/45/393 tests나 대규모 rounding audit를 다시 실행했다고 주장하지 않는다.

### 3.2 P0와 정확한 source 객체 복구

P0 raw copy를 `git show`로 직접 받아 hash를 재계산했다.

```text
bytes = 12061
SHA256 = a598057183121b9c928b3a9804c8e2e99afa553bad570a471aa4130f20e6b049
```

작성자의 checksum 문자열을 그대로 믿은 결과가 아니다. 다만 이번 검사는 frozen package raw bytes에 대한 확인이며, 출판사 서버에서 다시 내려받았거나 모든 공개 출처의 진위까지 인증한 것은 아니다.

별도로 20개 raw Git objects를 `SHA1(type + ' ' + decimal length + NUL + content)`로 재계산했다. 구성은 commit2/tree10/blob8이다. Binary tree entry를 직접 parse하여 두 정확 commit부터 8개 source blob까지 경로를 따라갔다.

- `0f7b744c...`: S1/S2/S4/S5, exact checker V1/V2의 6개 경로.
- `27e48770ab5db666bcd78034d151ddbb04b6af54`: A-EV force source와 Phase1 report의 2개 경로.

따라서 A-EV의 다른 commit으로 대체하지 않고 요청한 exact object가 복구됐음을 확인했다. 이 사실은 A-EV의 correctness/trust 승인과 무관하다. 계속 **comparison-only / NOT A TRUSTED ANTECEDENT**다. 전체 Git history/full bundle 또는 commit 서명·작성자 인증으로도 확대하지 않는다.

### 3.3 Constants 91개

Fortran의 integer/real parameter declaration을 별도 정적 parser로 읽었다. 원자료의 column-major 순서에서 ascending i, 그다음 j를 적용했다. Decimal 문자열은 own integer parser로 coefficient와 exponent를 분리하여 정수/10의 거듭제곱으로 만들고 Euclidean gcd로 약분했다. Host float를 거치지 않았다.

87개 P0 record의 **token/declaration, family, index, 물리식으로 유도한 unit**과 Lab의 n/d를 대조했다. 나머지 4개는 복구된 S1/S2와 대조했다.

```text
bohr_in_angstrom = 0.529177210903
r_min_in_angstrom = 1.2
Ar40_mass_u = 39.9623831237
electron_mass_u = 5.485799090441e-4
```

4개 모두 exact canonical pair가 맞다. 원본에서 고정한 CODATA2018/2022 사용을 임의로 최신 값 하나로 통일하지 않았다. σ와 nominal model을 분리했고, excluded evaluator thresholds를 물리 계수로 이식하지 않았다. Unit strings는 물리식의 차원 유도라는 명시를 따른다.

추가로 pinned V2를 실행하지 않고 AST literal data만 읽어 Lab 계수의 72개 관련 값을 대조했다. 선언 구조의 같은 값이라는 검산이지 V2가 출력한 계산값을 source oracle로 사용한 것이 아니다.

## 4. B1: bundle와 authority

다음 9개 JSON은 exact canonical ASCII JSON bytes와 sidecar SHA를 독립 확인했다. 8개 semantic data 파일과 package-manifest 1개다. Package manifest의 8개 dependency도 actual bytes에 대조했다.

```text
semantic-bundle SHA256:
a179dcfc065931d09ba4f364d159416ede4b9090a0924bf3fcc119815ed4266f

constants SHA256:
f1cf6a71afaf45e40db37a6e8a5b4f643a57885f4040d4fa285835530363e196
```

Bundle는 단순 source hash 목록이 아니다. V/V′ 및 BO/REL/QED retardation 분기, q 방향, R²/√R², common impulse sign, full_dt=40와 half fraction1/2, FX grids, once-nearest-even/overflow, methods/wire/상태 규칙을 실제 데이터로 고정한다. 원본 executor fingerprint를 유일한 semantic ID로 쓰지 않는다.

Human B 문서도 공동 규범이지만 semantic-bundle SHA만으로 human 문서까지 자동 고정되는 것은 아니다. 이 package가 밝힌 대로 전체 commit/review target과 함께 결합해야 한다. 규범 문서를 바꾸면 새 revision/review target이 필요하다.

새 `m=-2^95 → OPPOSITE_RAW_UNREPRESENTABLE` 조건은 B1에 명시된 보수적 **신규 point-availability 제한**이다. 원래 Arithmetic Kick는 wide integer `-J`를 중간값으로 사용해 정상 update가 가능한 경우도 있다. 이 추가 제한을 기존 Kick의 수학적 필요조건으로 재해석하지 않는다. 본문이 이 차이를 공개하므로 숨은 Arithmetic 변경으로 판정하지 않았다.

## 5. B3의 맞는 부분: r_min·단위·정칙성

```text
(6/5)/(529177210903/10^12)
= 1200000000000/529177210903 bohr

r_min² = 1440000000000000000000000 / 280028520539078142075409
```

정확한 값과 Lab domain binding은 source와 대응한다. R=0은 singular refusal, 0<R<r_min은 physical-domain refusal, equality와 위쪽은 point admission이다. Schema/spec가 먼저이고 zero-axis shortcut보다 domain이 먼저다.

R²의 FX lattice denominator는 dyadic인 반면 r_min²의 기약 분모는 1보다 큰 홀수이므로 exact lattice equality는 불가능하다. Equality 규칙 자체를 없애지 않고 rational-domain boundary 논증과 lattice 양옆 fixture를 나눈 것은 적절하다.

모든 α/η와 B_m 양수, admitted R>0, retardation denominator D(R)>=1, factorial 양수, full-tail denominator n+2−x_hi>0, inverse interval lower>0 전제가 명시됐다. Coarse lower<=0에서는 actual singularity로 오판하지 않고 permitted refinement/UNPROVED로 처리한다.

이 scalar/admission 부분이 맞아도 F-CLOSURE-1 때문에 B3 전체를 PASS로 닫지는 못한다.

## 6. B4+B5 공동 판정

### 6.1 Wire 전략은 타당하지만 closed Failure 집합을 먼저 단일화해야 한다

Canonical integer는 sign 제외4096 digits, rational은 exact coprime n/d와 zero0/1이다. Writer는 gcd/normalization을 cap 안에서 수행한 뒤 `abs(n)<10**4096`, `0<d<10**4096`의 exact integer comparison을 끝내고 `str`한다. 큰 unreduced pair가 약분으로 작아질 수 있더라도 그 약분 자체의 temporary 비용은 없던 것으로 취급하지 않는다.

Input/Certificate/Artifact는 각각1MiB, 완전한 최종 artifact에도 따로 총량cap이 있다. Root container=1로 센 depth7, fixed-length atom2/vector3/exp9 및 any-array<=12, closed keys/enums, fixed64hex IDs/hashes, 자유 metadata/diagnostics0, 직렬화 history/intermediate interval0 규칙을 함께 사용한다. Failure는 고정 fields/enum/hash/null만으로4096bytes 안에 묶이며 offending integer나 원본 exception string을 싣지 않는다.

Byte/구조/token 길이를 `int()`보다 먼저 확인하고, 더 낮은 host decimal limit은 bounded HOST_SERIALIZATION_LIMIT로 거부한다. Process-global setter는 금지다. 이 제안이 실제 parser의 모든 allocation을 이미 보장한 것은 아니며 그 구현은 I10/I18에 남긴다.

### 6.2 Compact proof가 해결한 것과 해결하지 않은 것

Certificate는 원래 input/spec binding, N/P_R/n_R와 raw claims를 싣고 V2가 nonlinear 값을 재구성한다. Producer가 준 좁은 interval을 재신뢰하는 방식이 아니다. 큰 `2^P` 분모 전체를 wire에 쓰지 않으므로 과거 P=13607의 expanded dyadic denominator/4096-digit 충돌을 직접 피한다. 내부 arithmetic의 큰 분모/곱셈/메모리는 여전히 존재한다.

다섯 단계를 분리한다.

```text
mathematical J resolved
→ private proof constructed / serializable
→ independent rechecker accepted
→ complete artifact within cap
→ atomic publication
```

어느 단계든 실패하면 raw J만 성공으로 먼저 발행하지 않는다. Point proof publication은 comparison/arithmetic 실행과도 별개다.

### 6.3 B5는 METHOD SPEC PASS; RUNTIME INSTANCE STILL REQUIRED

B5 standalone method의 PASS와 B4+B5 공동 closure 승인은 다르다. F-CLOSURE-2 정정 전 공동 wire/resource interface는 승인하지 않는다.

23개 positive finite parameter, N absolute radius bits/P producer absolute dyadic bits/P_R V2 significant bits의 차이, doubling attempts, bounded order search, 앞선 cap 검사 및 고정 retry/refusal 순서가 규정됐다. 수학적 work charge는 기계 instruction 수나 실측 시간이 아니라 보수적 정책 단위라는 점도 구분했다.

기존 V2는 direct full-x Taylor를 쓰므로 producer의 range-reduced local order를 넘기지 않는다. 별도의 n_R 계획과 positive upper bound를 요구한다. Tail 조건 n_R+2>x_hi가 성립하는 것과 최종 rounding separation은 다른 의무다.

실제 실행 전 다음이 모두 있어야 한다.

1. Policy version, exact numeric instance hash, issuer/basis evidence 및 독립 activation decision.
2. Source/platform/allocator/worker에 결합된 temporary/live byte majorants.
3. Pinned V2 whole-call upper-bound DAG에 의한 사전 work/allocation charge.
4. Isolated worker의 실제 OS memory/CPU/wall enforcement와 bounded interruption mapping.

V2의 `_Ctx.note`가 allocation 이후에 검사한다는 사실은 source에서 확인했다. 기존 V2를 그대로 쓰면서 이를 “연산 전 allocation 보호”라고 부르면 안 된다. 현재 package는 그 한계를 명시하고 위 wrapper 조건이 없으면 호출하지 않도록 한다. 따라서 V2 code 수정이 이 방법의 필수 선행 조건이라고 판정하지 않는다. 대신 검증된 wrapper 보호가 없는 runtime activation은 금지다.

아직 코드가 없는 단계에서 이 네 구현 증거가 없는 것은 implementation-dependent다. 근거 없는 numeric budget을 여기서 임의 발급하지 않는다. 전체 valid input의 finite-budget 성공을 주장하지 않는 first V1에 대해서는 parameterized fail-closed method contract를 인정한다.

I11a internal convergence, I11b cell decidability, I11c configured finite-budget success, I11d publication feasibility는 문서와 JSON 모두에서 분리됐다. 어느 하나를 나머지 세 개의 증거로 취급하지 않는다.

## 7. B6: pinned V2와 새 producer의 독립성

선택한 V2는 원본 commit0f7b744c의 blob `ad1a66091ec743359565f3d19affbef800c70192`, raw SHA `180d5a19bbea606594912e95b3c210b5a7739995afa39c5300959faef8b94d96`다. 이 source의 정적 import는 hashlib/json/math/time/fractions뿐이다. AST에서 직접 exec/eval/__import__ 호출을 찾지 못했다. 실제 신규 process/call independence 증거를 이미 수행했다고 주장하지 않는다.

B6의 private legacy projection은 source FORMAT/METHOD, position_frac_bits48, raw dr 범위, dt_kick20, output96/80, N/P_R, fixed9 rates/full mode와 대응한다. Runtime binding은 source에서 optional일 뿐 mathematical identity를 검증하지 않는다. Lab validator가 full state/spec/occurrence/phase/budget/source를 재검증해야 한다.

Nonzero axis는 V2가 자기 sqrt/powers/exp/V′/J enclosure를 재구성한다. Zero axis는 V2가 not_a_decision으로 거부하므로 독립 binding validator가 full domain admission 후 q_k=0과 J_k=0을 exact integer identity로 증명한다. Zero shortcut이 singular/below-min admission을 우회해서는 안 된다.

V2는 even-cell boundary까지 포함하는 nearest-even 전체 cell이 아니라 **strict interior**만 수용한다. True exact tie에서 NOT_PROVED가 남을 수 있는 것은 availability 제한이지 잘못된 raw를 승인하는 soundness failure가 아니다.

Producer와 V2는 공개식/정확상수/입력/int-Fraction 의미는 공유할 수 있다. Executable parser, primitive/enclosure/rounding helper와 결과 cache를 공유하면서 독립된 두 판정으로 세면 안 된다. Point Prover가 V2를 호출하는 기존 계보를 third independent judge로 추가하지 않는 선택은 맞다. A-EV object 복구도 trust 승격이 아니다.

## 8. B7/B8: identity와 상태

Identity는 `SHA256(ASCII domain || NUL || canonical payload)`로 분리하며 파일 SHA와 역할이 다르다. Full-state는 momentum까지 포함하고 projection은 J에 필요한 위치/spec/constants/domain/atom roles/species/timing만 담는다. Math request는 method/wire/axis를 결합한다. Occurrence는 acquisition/record/phase/previous occurrence/source/tool과 full-state를 결합한다.

FIRST_HALF_KICK은 start snapshot과 previous=null, SECOND_HALF_KICK은 drift 후 새 snapshot과 previous-first 연결이다. Cache는 V1에서 비활성이므로 같은 position/raw 값이 반복된다는 이유만으로 이전 occurrence를 다시 발행하지 않는다. Hash equality는 authenticated capture 자체가 아니며 유효한 외부 수집 근거가 없으면 NOT_AVAILABLE/STOP이다. 실제 capture tool과 binding 구현은 아직 없다.

B8의 producer/rechecker/executor comparison/Arithmetic/publication/execution을 별도 field로 둔 것은 적절하다. Fixed phase 선행 규칙이 먼저이며 동일 작업 안에서 관측된 실패의 우선순위를 사용한다. 금지된 다음 단계를 실행하여 더 높은 오류를 찾아내도록 요구하지 않는다.

```text
X: overflow proven
Y: UNPROVED
Z: resolved
→ producer REFUSED / RAW_UNREPRESENTABLE
→ NOT_PUBLISHED / STOP
```

Resource 중단 전에 overflow가 이미 증명되었으면 유지하고, 아직 계산하지 못한 축을 추정하지 않는다. Empty intersection/conflicting proved raw는 anomaly STOP이다. Nonnested이지만 서로 양립하는 sound enclosures는 허용한다.

POINT_PROOF는 whole-vector recheck/cap을 만족하면 comparison/arithmetic NOT_RUN인 상태로 출판할 수 있지만 세계 execution은 STOP이다. COMPOSITION_RESULT는 별도 승인·same authenticated occurrence MATCH·Arithmetic COMPUTED를 추가로 요구한다. **실제 future guard 계약만은 F-CLOSURE-1 정정 전 연결할 수 없다.**

## 9. I1–I22 재판정

READY는 해당 사양·수학적 선행조건을 구현할 만큼 정했다는 뜻이다. 아직 존재하지 않는 구현의 correctness PASS가 아니다. IMPLEMENTATION-DEPENDENT는 필요한 acceptance 기준이 정해져 있으나 실제 source/proof/runtime 증거가 남았다는 뜻이다.

| ID | 현재 독립 판정 | 근거 |
|---|---|---|
| I1 | **BLOCKED** | r_min scalar와 출처는 확인됐으나 domain/guard normative bundle의 F-CLOSURE-1 수정이 필요하다. |
| I2 | **IMPLEMENTATION-DEPENDENT** | raw→q→R²와 full-state/획득 결합 규칙은 충분하다. parser·전사·실제 획득 동치는 구현 후 검증. |
| I3 | **READY** | V family, coefficient/index mapping 및 retardation 분기는 원자료와 대응한다. 아직 코드 전사 PASS는 아니다. |
| I4 | **READY** | analytic derivative, BO i=-1, TT/g′, sign, h 및 mass 부재의 규범 의미가 닫혔다. |
| I5 | **READY** | sqrt/inverse/power/signed interval과 분모 정칙성의 전제가 B3/B5에 명시됐다. 구간 연산 코드는 미구현. |
| I6 | **READY** | exp tail·range reduction·각 squaring outward widening·cutoff 금지 전략이 구체적이다. |
| I7 | **READY** | V′→-V′/R→h*q의 포함 합성과 cancellation의 의미 구분은 충분하다. |
| I8 | **READY** | nearest-even cell과 signed overflow, V2 strict-cell availability 제한을 구분했다. |
| I9 | **IMPLEMENTATION-DEPENDENT** | domain 이후 zero-axis를 독립 validator가 증명하는 규칙은 명시됨. 실제 우회 방지와 whole-vector 처리는 검증 필요. |
| I10 | **BLOCKED** | bounded failure 원칙은 명시됐지만 Failure의 closed key 집합이 모순이다. F-CLOSURE-2 정정 후 parser/writer/transaction은 구현 후 검증. |
| I11 | **IMPLEMENTATION-DEPENDENT** | I11a–d 네 명제는 분리됐다. method convergence 전사·실제 finite-budget 결과·출판은 별도 증거가 필요하다. |
| I12 | **IMPLEMENTATION-DEPENDENT** | pinned V2와 공유금지 helper/parser의 계보가 선택됐다. 신규 source/process/call 증거는 아직 없다. |
| I13 | **IMPLEMENTATION-DEPENDENT** | canonical identity·missing/stale/mismatch 규칙은 충분하다. authenticated capture와 실제 comparator 검증은 미실행. |
| I14 | **BLOCKED** | 기존 Arithmetic가 하는 stored endpoint 검사와 새 B3가 요구하는 stored segment 검사가 다르다. |
| I15 | **IMPLEMENTATION-DEPENDENT** | 비퇴화 fixture 획득과 실제 source mutant 및 독립 expected 실행은 아직 없다. |
| I16 | **IMPLEMENTATION-DEPENDENT** | 이번 사양 snapshot과 증거는 고정했지만 미래 구현·의존·감사 대상과 결과는 아직 없다. |
| I17 | **READY** | R>0, positive rates, D(R)>=1, positive factorial/tail denominator, coarse lower zero의 정칙성 규칙 확인. |
| I18 | **BLOCKED** | B4의 failure schema를 단일화해야 공동 resource/wire 계약이 닫힌다. Source-bound majorant와 OS enforcement는 그 뒤 구현 후 검증. |
| I19 | **IMPLEMENTATION-DEPENDENT** | 원입력부터 V2가 nonlinear 값을 재구성한다는 계약은 충분하다. validator→legacy mapping→acceptance의 실제 soundness 확인 필요. |
| I20 | **IMPLEMENTATION-DEPENDENT** | 정해진 attempt sequence, nonnested 허용, empty intersection/conflicting raw anomaly 규칙을 구현으로 검증해야 한다. |
| I21 | **IMPLEMENTATION-DEPENDENT** | domain-separated full/math/occurrence identity 및 disabled cache를 실제 구현에서 확인해야 한다. |
| I22 | **IMPLEMENTATION-DEPENDENT** | 3축 proof·cap 통과 후 publication, partial vector/state 금지를 실제 writer/transaction에서 확인해야 한다. |

저자의 I1/I10/I12/I13 BLOCKED 문자열을 그대로 승계하지 않았다. I12/I13의 사양 선택은 충분해 IMPLEMENTATION-DEPENDENT로 재분류했다. I1/I14는 F-CLOSURE-1, I10/I18은 F-CLOSURE-2 때문에 BLOCKED다. 어떤 상태도 전체 구현 착수를 우회하는 별도 허가로 읽으면 안 된다.

## 10. Mutation/validation 계획

M1–M17은 실제 오류의 영향을 증명할 비퇴화 fixture를 요구한다. Sign flip은 nonzero force만이 아니라 서로 다른 proved rounded cells, 1/R 제거는 R!=1만이 아니라 실제 결과 분리, ties-away는 exact even tie synthetic decision fixture를 요구한다. Source edit가 여러 개인 행은 각각의 mutant로 나누며 hash-only rejection은 semantic detection 수에 넣지 않는다.

추가 M18–M23은 forged certificate, source/constants override, rechecker derivative 누락, zero-axis admission 우회, preallocation/last-approximation 우회, conflicting refinements, stale/phase identity, J1/J0 혼동과 partial publication을 공격한다. 각 행의 I 의무 연결과 independent expected 요구가 있다.

이는 **PLAN PASS / NOT EXECUTED**다. 아직 실제 Lang fixture가 없는 곳은 fixture selection criteria로 남아 있으며, 존재하지 않는 expected raw나 mutant 실행 횟수를 만들어 붙이지 않았다. 이번 guard 차이 반례도 future contract regression으로 보존하는 것이 적절하지만 본 재검토에서 production test나 mutant로 실행한 것은 아니다.

## 11. 범위·증거 한계와 다음 최소 단위

이번에 판정하는 것은 pre-implementation closure다. Arithmetic source 보존을 확인했지만 Impulse 구현·J physical correctness·원본 executor 상세 호환·full replay·trajectory·D_valid·physical model accuracy·formal certification으로 확대하지 않는다. Arithmetic slow DEFAULT와 fast EXPERIMENTAL/OPT-IN도 유지한다.

다음 재검토는 F-CLOSURE-1/2의 문서·JSON 정정과 그 dependency hash 재발급 delta면 된다. 91개 constants나 전체 Arithmetic 수학을 불필요하게 처음부터 반복할 필요는 없다. 수정된 snapshot에서 해당 guard semantics, 관련 hash consistency, 보호 source 불변 및 남은 runtime activation 조건을 확인하면 된다.

## 12. 증거 파일과 재현

- `remote_evidence/static_review.py`: 실제 원격 실행한 독립 Git/hash/raw-object/상수 전사 검사 source.
- `remote_evidence/finish_static.py`: 실제 원격 실행한 S1/S2 및 V2 embedded literal parity, package hash 검사 source.
- `remote_evidence/static_results.json`: 실제 검사 결과. 대량 no-checkout git status 원문은 hash/empty flags로 줄였으며 author source-recovery metadata 필드만 제거했다. 제거한 항목을 명시한다.
- `remote_evidence/extended_results.json`: 위 추가 source parity 확인 결과.
- `transfer_integrity.json`: 원격→container compressed payload SHA 대조 및 전달된 각 파일의 SHA.
- `guard_contract_witness.py/.json/.log`: production import 없는 별도 exact 계약 반례, 정수/유리수 입력 및 부호 결과.
- `verdicts.json`: C1–C12, I1–I22, F-CLOSURE-1/2, 최종 implementation flag.

원격 검사기 재현에는 검사기 파일 옆 `repo`라는 Git repository가 필요하다. 고정 target과 antecedent objects를 가져온 뒤 두 script를 순서대로 실행한다. 첫 script는 P0를 audit directory에 복사하고 JSON을 기록한다. 원본 production 코드를 실행하지 않는다. 둘째 script는 audit export 파일을 추가로 만든다. No-checkout clone status는 clean으로 기대하지 않는다.

전체 P0/Git source 원본과 full remote clone를 이 작은 보고서 ZIP에 모두 재배포하지 않는다. 원본은 고정 repository closure package에서 경로/객체 ID로 가져올 수 있다. Packet checksum 검사는 artifact의 무결성 확인이며, 재실행하지 않은 수학·원자료 진위를 자동 인증하는 것이 아니다.

### 최종 상태

```yaml
closure_review: CLOSURE REVISION REQUIRED
implementation_may_start: false
numeric_runtime_instance: STILL REQUIRED BEFORE ACTIVATION
Arithmetic_V1: INDEPENDENT REVIEW PASS
exact_slow: DEFAULT
exact_fast: EXPERIMENTAL / OPT-IN
Independent_Impulse_V1: DESIGN ONLY / NOT IMPLEMENTED
impulse: J_NOT_VERIFIED
certification: NotCertified
```
