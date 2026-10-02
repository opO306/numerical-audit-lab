# Gate 2C.1 검증 방법 — 결과 전 봉인

이 문서는 Gate 2C.1 horizon/cross 측정 전에 고정한다.
기존 Gate 2C는 PROVISIONAL / CONDITIONAL이다. 새 버전의 독립 최종 감사는 PENDING이다.

## 비용 측정과 채택 이유

수령한 auditor regular 원본을 현재 ROOT에만 연결하여 128/512/1024 step cProfile을 수행했다.
wall: 0.7619644 / 2.8353353 / 5.7717984초. 측정 전체 10.4024914초.
원시 자료 `audit/gate2c1/cost_survey.json`에 함수별 calls/self/cumulative time을 보존한다.
별도 128-step 관측에서 inverse 257회, inverse 입력은 모두 float,
Fraction 변환 분자 최대 53bit / 분모 최대 145bit였다.
이것은 짧은 초기 구간의 관측이며 100k까지 같은 비용을 보장하는 근거가 아니다.
과거 감사 환경의 stdout/profile은 없으므로 과거 20k 중단의 정확한 원인을 확정하지 않는다.

실측 병목은 rebase/radii 안 exact-rational 행렬 계산과 step_forms의 rational rounding residual이다.
각 rebase는 float 행렬에서 새 inverse를 계산한다. 참 궤도의 커지는 Fraction을 전역 전파하지 않는다.
현재 짧은 비용은 급격한 길이 의존 폭증을 보여 주지 않았다. cProfile overhead도 실제 포함되어 있다.
frozen V2 inverse를 없애면 accepted dependency를 바꾸거나 별도 포함 증명이 필요하다.
이번에는 inverse 제거/근사 대체를 하지 않는다. V2 그대로의 순차 전파를 채택한다.

세그먼트는 비용을 마법처럼 줄이는 기법이 아니다. 매 1000-step의 엄밀한 연결과 중단 보존,
감사자의 재계산 단위를 제공한다. 필요했던 regular full 100k를 cheap host runner로 재계산하며,
exact trajectory의 global Fraction brute force는 하지 않는다. exact Fraction map은 local 8-step뿐이다.
producer와 independent 총 60분 wall budget. 시간이 부족하면 결과를 줄여 PASS하지 않는다.

## 독립 계산 경로

producer: 새 numeric_core T_bin, 새 adapter, frozen V2.
independent reproduction: 수령한 auditor 원본에서 파생한 별도 graph/host-float executor/
fixture decoder/exact scale/cross/first-refusal/exact map. Gate2A/Gate2C/Gate2C.1 실행/adapter를 import하지 않는다.
accepted V2의 step_forms/rebase/zero_forms만 공통 연산자로 인정한다. V2 재감사가 아니다.
graph는 machine mapping의 주소를 사람이 별도로 옮긴다. producer graph를 생성기로 재사용하지 않는다.
independent graph 수정은 원 artifact 대비 diff와 source hash로 공개한다.
이 작업자가 수행한 이식·실행은 새 외부 감사자의 독립 최종 판정과 구별한다.

## 연결 증명

initial represented full state는 frozen fixture step0. exact initial error는 zero이다.
init graph를 독립 실행하고 accepted V2 init/rebase의 latent Forms를 계산한다.
각 step은 계산된 이전 center/Form만 입력한다. 다음 segment의 입력을 저장 seed로 초기화하지 않는다.

checkpoint의 필수 요소:
bin represented `(x,y,vhx,vhy)`, Lab represented `(x,y,px,py)`,
각각의 4 Forms × 4 coefficient + box의 binary64 bits,
bin/Lab fail-stop, 최초 horizon/cross refusal, prefix, segment 앞 hash, 누적 coverage.
각 producer segment는 start/end와 해당 범위의 모든 결정에 대한 rolling digest를 기록한다.
independent path는 원점에서 모든 step을 재계산하고 producer의 start/end와 bit 단위로 비교한다.
독립 endpoint와 다음 segment start의 모든 center/Forms가 같아야 한다.

Form集合 S(M,w,c)={c−Mξ−η: |ξ_j|≤1, |η_i|≤w_i}를 생각하면
동일 c/M/w의 byte equality는 동일 실수값 equality를 주므로 S_end=S_next_input이다.
그러므로 앞 certified endpoint가 다음 입력에 포함된다. 이 연결에서 새로운 rounding은 없다.
hash equality만으로 이 증명을 대신하지 않는다. hash는 보존 식별자일 뿐이다.
전구간 1..N의 누락/중복이 없어야 하며, 모든 step별 유한/scale/residual 판정을 재계산한다.
radius만의 비교, error=0 reset, 저장 checkpoint의 신뢰, segment당 local window는 전역 증거가 아니다.

## 실패와 coverage

bin output과 latent bound를 분리한다. negative/nonfinite bound 또는 state는 REFUSED.
유용한 V2 PASS는 max(E)<scale. equality는 REFUSED. 첫 거부의 reason/step은 sticky하다.
init 실패면 prefix0. nonfinite latent Forms는 다음 step으로 전달하지 않는다.
cross의 exact Fraction residual이 합 상한을 넘으면 scale 거부와 별개로 FAIL이다.
합 상한 max>=양쪽 represented scale max는 REFUSED. display overflow는 판정에 영향 없음.
각 REFUSED를 step/reason으로 기록하되 저장 크기는 같은 reason의 연속 범위로 압축할 수 있다.
late replay mismatch는 거부 뒤에도 검출한다.
deadline/trace/exception/pre/post seal failure가 생기면 완료된 자료와 실패를 보존한다.

regular 요구는 N=100000 전체 replay/Forms/scale/cross의 새 독립 계산 완료다.
chaotic도 N 전체 represented replay와 6 local 중 3구간의 seed를 재구성한다.
global bound fail-stop 뒤는 reason이 유지된 UNAVAILABLE이며 추가 global PASS를 만들지 않는다.
모든 구간은 checkpoint와 first refusal 근처 ±1 step의 bounds/scale/output/latent를 저장한다.
기존 chaotic 숫자 또는 regular 최종 상한을 expected answer로 넣지 않는다.

## 사전 고정된 공격 시험

- opcode/operand/상수/중간값/순서의 구조 변조 탐지. old doubling graph는 거부.
- checkpoint center/coef/box 변조, zero reset, gap/overlap, 이전 hash만 바꾸거나 맞추기 공격 거부.
- finite/negative/NaN/inf/None, exact scale equality, init/step fail-stop과 sticky prefix.
- huge finite 합 display overflow, pre/post seals 보고 보존, late replay mismatch.
- package missing wheel/.so/fixture/bundle, raw byte 변조, 거짓 external hash/다른 filename 거부.

제공될 새 Charter는 A1–A11과 regular coverage/연결/자료 전달을 다시 감사하게 한다.
이 방법의 완료와 저자의 시험이 Gate 2C.1 CLOSED/PASS를 자동 승인하지 않는다.
