# Gate 2C.1 독립 감사 Charter

Gate 2C는 **PROVISIONAL / CONDITIONAL** 그대로다.
Gate 2C.1의 새 최종 독립 감사는 **PENDING**이며 결과를 본 작업자의 재계산은 최종 승인이 아니다.
V2 자체는 AUDITED / PASS / FROZEN으로 인정한다. 재감사하거나 V2.1로 바꾸지 않는다.

감사 대상 bytes는 `audit/gate2c1/code_seal.json` 및 `result_seal.json`을 따른다.
plan/method는 각각 구현/결과 전에 실제 Git commit으로 봉인했다.
wheel 및 관련 .so 원본은 `audit/gate2c1/vendor/`에 실제 존재해야 한다.
전달 ZIP은 외부 DELIVERY.md / delivery_receipt.json / .sha256의 **단일 filename/hash**로 식별한다.
전달 ZIP을 직접 읽어 모든 advertised path, wheel 내부 .so와 별도 .so의 bytes, Git lineage를 확인한다.
다른 checkout ZIP이나 hash만 복사한 vendor 기록은 대체 증거가 아니다.

## 독립성 및 검토 범위

- producer T_bin/adapter/판정/serializer를 독립 정답 함수로 재사용하지 않는다.
- `independent/checker.py`는 수령 auditor-origin 계산 경로의 **작업자 이식판**이다.
  producer와 분리된 재계산 evidence이지만 그 코드 자체도 이번 감사 대상이다.
- 감사자는 별도 검사 또는 유도로 순서/연결/판정/coverage를 검토한다.
  accepted frozen V2를 연산자로 호출할 수 있다. 그것이 adapter의 soundness를 자동 승인하지 않는다.
- 기존 chaotic 숫자는 expected answer가 아니다. 새 graph와 최초 거부 탐색을 기준으로 한다.
- 모든 finding, 반례, 미실행 항목을 공개한다. UNRESOLVED를 Minor로 낮추지 않는다.
- 코드 검토, 표본 시험, 별도 경로 전구간 재계산, 새 최종 독립 감사를 구별한다.

## A1–A11

| ID | 증명 의무 및 최소 evidence |
|---|---|
| A1 | 해당 wheel의 실제 branch/callback/gradient/leapfrog arithmetic를 machine_mapping의 주소 및 occurrence에 대응시킨다. N=1/ndim2/no transform의 call routing 근거, grad memset, operand 역할, half 상수 bytes, output/latent 갱신 순서를 별도 확인한다. LOAD/MOV/control은 산술 연산으로 위장하지 않는다. 다른 odd/vector/single-gradient branch와 바꾸지 않는다. |
| A2 | T_bin→V2 구조의 opcode/상수/입력/중간값/순서/초기화/출력/내부 상태가 1:1인지 확인한다. producer traces와 host 재계산의 operand/result bits 및 모든 checkpoint의 판정 digest를 검토한다. old doubling graph, 상수/순서/중간값 변조가 검출되는지 확인한다. |
| A3 | 기존 fixture 8개 gzip/raw hash, manifest shape, c5971ea 원 Git blob을 확인한다. 기존 Gate 2C code/result/report/digest/seals가 원래 바이트 그대로임을 확인한다. wheel/.so는 ZIP의 실제 bytes에서 다시 해시한다. |
| A4 | regular 1..100000 전체 유한/useful V2 전파를 독립 계산한다. segment별 coverage/endpoint뿐 아니라 매 step 판정의 재계산을 확인한다. chaotic 최초 REFUSED를 새 graph에서 다시 찾고 경계 앞/경계/뒤 값을 확인한다. 기존 13906/13907 숫자와 같아야 한다는 조건은 없다. |
| A5 | 각 최초 거부가 finite scale 부족인지 nonfinite/exception/replay/cost 실패인지 정확히 구별한다. 정확한 bound/scale inequality 및 모든 REFUSED reason 범위 기록을 확인한다. |
| A6 | exact staggered target=Lab Verlet 항등식과 triangle inequality를 별도로 유도한다. regular 1..100000 cross와 chaotic 경계는 독립 Fraction 합/residual/scale로 재계산한다. raw violation은 REFUSED로 숨기지 않는다. |
| A7 | 두 orbit n0=0,50000,99992의 6개 8-step에서 represented latent seed, 별도 exact Fraction map, output 4개, internal 4개를 모두 확인한다. 저장된 full vx/vy를 vh로 대체하지 않는다. local zero reset은 global propagation의 증거가 아니다. |
| A8 | finite/negative/inf/NaN/None, scale equality, opcode/trace failure, VM halt, init/step rebase fail-stop, huge Fraction display overflow, deadline, late mismatch에서 작은 finite bound나 false PASS가 나올 길을 공격한다. first prefix의 sticky 성질과 invalid Forms의 재사용 금지를 확인한다. |
| A9 | init fail-stop/prefix, huge finite display overflow, pre/post seal failure 보존, init rebase nonfinite의 기존 4종 회귀시험을 새 모듈에서 확인한다. 다른 우회 경로도 검토한다. code_seal 이후 source 변경이나 결과를 맞춘 수정이 없는지 확인한다. |
| A10 | gala bit equality는 이미 알려진 prerequisite이며 새로운 blind success/독립 발견으로 세지 않았는지 확인한다. 옛 horizon 숫자의 재일치 자체를 새 성공 조건으로 쓰지 않는다. |
| A11 | 특정 wheel의 frozen execution과 같은 discrete program의 exact arithmetic 사이 rounding layer만 다루는지 확인한다. 연속 Hénon–Heiles, method error, gala 전체, 다른 플랫폼/분기/입력 또는 새 Linux 실행을 인증하지 않는다. |

## 추가 연결·provenance 의무

각 1000-step segment의 start는 독립 계산된 앞 endpoint 전체 center/Forms와 같아야 한다.
Form의 모든 coefficient와 box, represented center를 비교하여 동일 집합이고 따라서 포함임을 확인한다.
hash만의 일치, 저장 seed 신뢰, radius만의 일치, zero reset, 누락/중복은 거부한다.
전구간 매 step은 initial zero error부터 계산해야 한다. true exact 100k 궤도 Fraction brute force는 요구하지 않는다.
규모별 비용 profile과 방법 봉인의 선후관계, V2 inverse의 유지도 확인한다.

최종 ZIP을 완성한 후 계산한 SHA와 외부 문서/receipt/sidecar의 일치를 자동 검사한다.
누락 wheel/.so, wrong filename/hash, bundle/member 변조의 regression을 확인한다.
bundle의 HEAD에 실제 plan→method→implementation→result history와 봉인 bytes가 있어야 한다.
전달 자료가 이후 다른 ZIP으로 바뀌면 이 검증을 승계하지 않는다.

## 판정 규칙

각 A1–A11 및 추가 의무: **PASS / FAIL / UNRESOLVED**.

- Critical: 실제 오차보다 작은 finite bound, false PASS, 잘못된 certified horizon 가능.
- Major: soundness 논증의 미해결 구멍, 구체적인 under-bound 반례는 아직 없음.
- Minor: tightness, 문서, 성능, 유지보수.

최종 PASS: Critical 0 / Major 0 / UNRESOLVED 0.
CONDITIONAL: Critical 0이지만 Major 또는 UNRESOLVED 존재.
FAIL: Critical >=1.

새 최종 감사 PASS 뒤에만 Gate 2C.1 상태 승격을 결정한다. 기존 Gate 2C CONDITIONAL은 소급 변경하지 않는다.
그 전에는 Gate 2D, V2.1, Verified Driver, 자동 trace 연구, A 저장소 수정, push를 하지 않는다.
결함 수정 시 이번 bytes/results를 보존하고 별도 revision/version 및 재감사로 진행한다.

## 감사 대상 SHA-256 목록

최종 code seal SHA-256: b89e537316a442c19b6dbcaf86538c34899577e3b6a9a7b2c55d5b363865000b

아래 신규 source/evidence의 실제 raw SHA-256을 봉인한다. 보고서·400 segment·12 exact 자료·Charter 자체는 result_seal.json의 files 목록으로 추가 봉인한다. 이전 구현과 전달 도구 revision은 Git 및 pre_review/pre_delivery_revision으로 구별한다.

| 파일 | SHA-256 |
|---|---|
| audit/gate2c1/DELIVERY_REVIEW.md | 0de5fd5dfa36d4d75c6d660aa800830a9e5f942fc9a8c00f6b5f953f0a48f0a0 |
| audit/gate2c1/IMPLEMENTATION_REVIEW.md | 508c2cb50b86eb2aa4ee76603e8850bc5d0f32c16479029a146eddd536f4ae97 |
| audit/gate2c1/REVIEW_OUTCOME.md | fdcc5c390d3b62700d90084b07e05fbc69a94aba888e1e01f134a5fc767f4738 |
| audit/gate2c1/evidence/c_gradient.txt | 7631d85b07f3960cc170f91fef1f54419fc561f26393f2c3614b4efbb9e443e2 |
| audit/gate2c1/independent/checker.py | f80d07ca596f6b7a5982142058ba9ed353d6d4b08371bccda492dd480681c68b |
| audit/gate2c1/machine_mapping.json | 771730ef9b8d5132dc5f38644eaaf40bff05bd788af890eae5e069f9d766d669 |
| audit/gate2c1/vendor/gala-1.12.0-cp312-cp312-manylinux_2_24_x86_64.manylinux_2_28_x86_64.whl | cc5f0cf3bc63a966a3c130b93f6c05026271fe7178492a02c6266c243b5fc2f0 |
| audit/gate2c1/vendor/gala/integrate/cyintegrators/leapfrog.cpython-312-x86_64-linux-gnu.so | a6ac98736304bb9f6a92e473bba45da10d9b5b99f8019e2ca15eb6a7f86234fc |
| audit/gate2c1/vendor/gala/integrate/cyintegrators/leapfrog.pyx | 001e8ebf19a55c8a52690e905cbe9c2d62bf3418d844551dc85a6294d6206e17 |
| audit/gate2c1/vendor/gala/potential/potential/builtin/cybuiltin.cpython-312-x86_64-linux-gnu.so | 33d66d82c34c717560747ffbfca1d98f97432a0a671a0a210a0a225d8367ecaf |
| audit/gate2c1/vendor/gala/potential/potential/builtin/cybuiltin.pyx | 0448e4b52ed9fe640629401279cbd93eaa863c0dc25ebccc73df69652156ca64 |
| audit/gate2c1/vendor/gala/potential/potential/cpotential.pyx | 9c0dd74eb1feb8df1c5255cbe1a5775fdf1a2a4b621d9a2cc3987233d81e56d4 |
| audit/gate2c1/vendor/gala/potential/potential/src/cpotential.cpp | 153b3edd82e490abccd21e720c1c1f24fbd2f84cd82ce50a557005b12ee625ba |
| benchmarks/gate2c1/__init__.py | 21300fe39a2f4786ee403805d999ca15b376499b66cff2b5490a5c10774bcc7e |
| benchmarks/gate2c1/binary_replay.py | 81cf5103740a6026c461736ab5b6f384a3005992a342edce0554d2c954d19f53 |
| lab/gate2c1_artifacts.py | f73066898d9ee2e9063d61d55cc66609117118612c7a96fff7f48ee6d135109f |
| lab/gate2c1_checks.py | 712364ec4077276bdefd6d524571993f171c0ebfd0a0f3f4d8a5356c96fb8c9b |
| lab/gate2c1_contract.py | 5ee1ed3eba6eb8464ac619654f99ba57d6a5b124a61a428d3e1e0bd9631125f7 |
| run_gate2c1.py | d327f2c42768232d58442d6312079dfda55eab2d7b663340f6990f5b3765a892 |
| tests/test_gate2c1.py | 0629c6ed6afa985e015c7c9ca6ebcb7555e57481a1e7d9015ed76518c40826d6 |
| tests/test_gate2c1_delivery_manifest.py | 0ad5167f42792a2e7aaedec1e951e8ea734987de9f16c9e228036434d3976928 |
| tests/test_gate2c1_independent.py | a3c8d1f2089f83aae26da62bf0aed9a65b2b11380b8347e229a70e8d9123bed6 |
| tests/test_gate2c1_package.py | 2d7ce2f13583177cfbcb7515284a278af9fd64be62c002677ec102a7889fbef8 |
| tests/test_gate2c1_review_regressions.py | 211d14b27be09c2cb69de90a7ad0a67ad1cb5f1ea3abeb39cec4a8276368435d |
| tests/test_gate2c1_sealed.py | c0d9cf112fca18d7afde2856343a9ee35a86ec3085bb4cbead02010ad458832a |
| tools/gate2c1_package.py | 616a3ca238bfe40b87e5aa37e890678493225380c1e95d942d5c9bb4a891863d |
| tools/gate2c1_profile_auditor.py | 9a375be9d9d31e432d31495cece7fea4e7b765f9ab5fc97a308c0bfad76f2bd7 |
