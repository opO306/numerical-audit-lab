# Gate 2C.1 결과와 감사 전달

Gate 2C는 **PROVISIONAL / CONDITIONAL**이다. 기존 Critical 0 / Major 2 / UNRESOLVED 2와 기존 bytes/digest는 유지했다.
Gate 2C.1의 새 외부 A1–A11 최종 독립 감사는 **PENDING**이다. runner의 operational PASS는 CLOSED / PASS 승격이 아니다.
V2는 AUDITED / PASS / FROZEN 그대로다. 인증 범위는 특정 frozen gala wheel 실행과 같은 이산 계산의 exact arithmetic 사이 rounding layer이다.
연속 Hénon–Heiles 궤적, method error, gala 전체, 다른 플랫폼/분기, 새 Linux wheel 실행을 인증하지 않는다.

## 봉인과 계보

- d87b06a: Gate 2C 감사 판정 수령 기록, Gate 2C.1 DESIGN ONLY 계획과 수령 원 checker bytes 봉인.
- eb2305c: 비용 조사와 검증 방법을 결과 전에 봉인.
- 0f2fc62: 새 T_bin/adapter/evidence 구현 봉인. 이 producer를 full 100k에서 1회 실행.
- 5504237: 증거 검사에서 발견한 5 Major / 2 Minor 보완을 독립 full 전파 전에 봉인.
- c4f8d62: 재개봉 내부 manifest 및 committed HEAD archive 검증, 감사 Charter와 최종 code seal 봉인.
- 최종 package 및 result 봉인은 뒤의 result_seal/실제 Git history로 식별한다.

최초 구현의 source/seal과 검토 수정 기록은 audit/gate2c1/pre_review 및 IMPLEMENTATION_REVIEW.md에 보존했다.
수치 producer/T_bin/V2 그래프는 full 측정 이후 바꾸지 않았고 결과에 맞춘 tuning을 하지 않았다.
작업자의 수령 checker 이식은 producer executor/adapter/판정/serializer를 import하지 않고 accepted V2만 공통 사용한다.
이 경로의 full 재계산과 새 외부 감사자의 최종 판정을 구별한다.

## Machine 대응

array gradient callback의 실제 N=1 분기는 `1ca65/1ca69 → 1cb60`이다.
gx는 `1cb85 MUL(y,x) → 1cb91 ADD(xy,xy)`이며 `(x+x)*y` graph를 사용하지 않는다.
gx/gy 사이의 실제 9개 scalar 산술 순서, gradient 뒤의 half 계산, x→y loop와 operand 역할까지 그대로 옮겼다.
init/step 각각 17/25 trace operation의 주소·occurrence·T_bin tuple·V2 tuple 대응은 machine_mapping.json에 있다.
CONST 3개는 load/initialization으로 표기하며 산술 명령이라고 세지 않는다.
wheel 원본, cybuiltin/leapfrog .so 원본, 해당 source/callback 및 c_gradient/disassembly bytes를 제공한다.
실제 ELF 위치 `3b360`의 half 상수는 binary64 0.5임을 확인했다.

## 측정

| 측정 | regular | chaotic |
|---|---:|---:|
| represented replay 검사 | 100000 | 100000 |
| V2 certified prefix | 100000 | 13906 |
| first V2 REFUSED | 없음 | 13907 |
| cross-bound PASS prefix | 100000 | 13662 |
| first cross REFUSED | 없음 | 13663 |
| raw enclosure violation | 0 | 0 |
| exact local 8-step 위반 | 세 구간 모두 0 | 세 구간 모두 0 |

이 숫자는 새 graph에서 최초 거부를 탐색하여 얻었다. 옛 숫자와의 동일 여부는 성공 조건에 포함하지 않았다.
chaotic V2 13907은 finite `max(E) >= max(abs(represented state))`에 의한 REFUSED다.
cross 13663은 exact Fraction 합 bound가 양쪽 state scale에 도달했기 때문이다.
Lab nonfinite 13735, bin latent nonfinite 13953은 별개의 사건이다.
거부 뒤 represented replay는 100000까지 유지하지만 nonfinite Forms는 재사용하지 않는다.

REFUSED reason 전구간은 producer 보고서의 refused_ranges에 저장했다.
cross: 13663..13734 scale 부족, 13735..100000 bound unavailable/nonfinite.
V2: 13907..13952 scale 부족, 13953..100000 nonfinite latent fail-stop.
display float overflow는 판정에 사용하지 않는다.

producer deterministic digest:
`aedc69466aabeca697ed177d5a84ee7ae88b5d6ffb91211abd9b2bd00c2650f3`

producer wall 317.1511553초, orbit 전파 regular 255.2060656초 / chaotic 61.7079373초.
이는 실제 현재 Windows/Python3.12.7 측정이다. peak_rss_bytes=0은 측정값을 얻지 못한 것으로 읽어야 하며 메모리 사용량 0을 뜻하지 않는다.
독립 full 재계산은 250.6406987초에 완료했다. verification_verdict=PASS, failure=None, pre/post seal failures=0.
regular V2/cross 1..100000을 모두 재계산했고, chaotic replay도 100000까지 진행했다.
모든 200개 producer segment와 200개 독립 segment의 endpoint/판정 digest/coverage 연결이 일치했다.
replay mismatch와 raw violation은 두 orbit 모두 0, 6개 독립 local 검사도 모두 위반 0이었다.
first refusal ±1 자료는 13662/13663/13664와 13906/13907/13908을 자동 선택해 bounds/scale/output/latent로 보존했다.
producer+independent 합계는 567.7918540초(약 9분 28초)로 봉인한 합계 60분 상한 안이다.

## Cross-bound의 exact target 연결

`h=1/64`, `g(q)=∇V(q)`로 둔다. exact gala latent `u=p−(h/2)g(q)`라면
`q'=q+h u`, `p'=u−(h/2)g(q')`, `u'=u−h g(q')`이다.
Lab velocity Verlet의 `p_half=p−(h/2)g(q)`, `q'=q+h p_half`,
`p'=p_half−(h/2)g(q')`와 같은 exact full state를 만든다.
init에서 이 latent 관계를 설정하고 다음 step에 `u'=p'−(h/2)g(q')`이므로 귀납적으로 유지된다.
binary 연산 그래프는 다르지만 exact discrete target은 같다.

따라서 component별 `|bin_i−lab_i| ≤ |bin_i−exact_i|+|lab_i−exact_i| ≤ E_bin_i+E_lab_i`.
잔차와 합은 represented binary64를 Fraction으로 정확히 변환하여 비교한다.
raw residual 초과는 FAIL이다. enclosure가 성립해도 max(sum bound)가 양쪽 represented scale의 최대에 도달하면 REFUSED다.
새 producer의 Lab output 상한은 output Form.rad(), 다음 입력은 rebase Form으로 구별한다.
옛 Gate 2C의 rebase 반환 output 상한을 변경하지 않고, 새 버전의 선택은 결과 전에 문서화했다.

## 전구간 연결과 local 검사의 한계

1000-step segment는 producer 200개, 독립 재계산 200개다. 순차 재계산한 center와 Form의 모든 coefficient/box를
비교하여 앞 endpoint와 다음 입력이 같은 집합임을 확인한다. 저장된 값을 seed로 사용하거나 zero reset하지 않는다.
매 step 판정 digest와 coverage/hash chain도 비교한다. hash 자체가 수학적 포함 증명인 것은 아니다.
nonfinite 이후의 segment는 represented replay와 UNAVAILABLE 상태를 보존하며 새 certification을 부여하지 않는다.

6개 local 구간은 실제 replay로 복원한 n0=0/50000/99992 latent를 exact represented 값으로 재시작한다.
각 8-step의 입력 latent, output, internal state, Fraction exact 값 및 양쪽 bound를 저장하고 비교한다.
local 위반 0은 global true exact 궤도를 직접 100k Fraction으로 계산했다는 주장이 아니다.

## 전달과 남은 감사

최종 ZIP에는 원본 wheel/.so, fixture와 raw/gzip hashes, disassembly, trace/mapping,
12개 producer/independent exact 자료, 400 segment, plan/method/result/report/charter, Git bundle, 모든 봉인 manifest가 실제 포함되어야 한다.
최종 ZIP을 닫은 다음 외부 DELIVERY.md/receipt/sidecar에 같은 filename/SHA를 쓴다. ZIP 안에 자신의 hash를 기록하는 순환은 피한다.
완성한 ZIP의 재개봉 검증과 fresh clone provenance 확인 결과는 실행 기록 및 전달 receipt를 따른다.
독립 재계산이 끝난 뒤 추가로 발견된 내부 manifest 검증 누락은 전달 tool만 보완했다.
5개 manifest 공격 RED→PASS 및 source/seal 보존 내역은 DELIVERY_REVIEW.md를 따른다.
측정 수치와 결과 bytes는 수정하지 않았으며, 이 수정 때문에 100k campaign을 다시 실행하지 않았다.
전체 시험은 `python -m pytest -q`: **250 passed in 24.92s**.
committed HEAD archive 규칙 추가 뒤 관련 package/manifest 시험 9 passed도 확인했다.
읽기 전용 구현 재검토의 지적은 모두 보완 확인되었지만 새 외부 최종 감사는 계속 PENDING이다.
이전 봉인 대상 67개 raw 파일을 그대로 유지했다. 최종 result_seal은 보고서·trace·exact·segment와 새 문서를 SHA-256으로 묶는다.

새 감사자는 charter A1–A11 및 package/coverage를 PASS / FAIL / UNRESOLVED로 판정한다.
Critical 0 / Major 0 / UNRESOLVED 0일 때만 새 최종 PASS다. 아직 그 판정을 받지 않았다.
A 저장소 수정, push, Gate 2D, V2.1, Verified Driver, 자동 trace 연구는 수행하지 않았다.
