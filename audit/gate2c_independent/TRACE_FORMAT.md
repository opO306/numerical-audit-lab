# Producer operation trace / V2 입력 형식

이 형식은 봉인된 신규 adapter를 관측한 자료다. 독립 checker 또는 정답 규격 구현이 아니다.

`schema=gate2c-operation-trace-producer-v1`.
- kind: init 또는 step_1. 현재 표본은 두 궤도의 시작점 init/첫 binary step뿐이다.
- V2_structure: `(op,dst,args,literal)` 목록. CONST의 args는 빈 목록이고 literal은 exact 문자열이다.
- V2_registers_bits: 실제 VM이 반환한 전체 레지스터의 binary64 uint64 hex 문자열.
- V2_input_forms: state name → 네 coef bits와 box bits. init에서는 zero forms,
  step_1에서는 frozen init/rebase가 만든 latent forms다.
- operations: graph order의 index/op/dst/operands/literal/operand_bits/result_bits.
- producer_output_bound_bits: 기존 BinBound가 낸 네 output Form rad의 binary64 bits.
  이는 producer 값이며 감사관의 별도 판정용 reference가 아니다.
- fixture_output_bits: 원 frozen fixture에서 읽은 step_1의 full-state output.

uint64 hex는 16자리 big-endian 표기값이다. byte 파일의 endianness와 구별한다.
값은 IEEE binary64로 decode한다. signed zero의 bit는 유지한다.
NaN/inf 경로는 이 정상 시작점 표본에 없다. A8 fault injection은 감사관의 별도 의무다.

이 frozen graph는 모든 dst가 unique이므로 최종 register map에서 각 연산 당시의
operand/result 값을 가져올 수 있다. exporter는 duplicate dst이면 거부한다.
그 조건을 일반 프로그램의 trace 규칙으로 확대하지 않는다.
init/step당 모든 op가 대응하는지 별도 확인해야 하며 표본 trace만으로 전 범위 A2를 PASS하지 않는다.

exact producer fixture는 numerator_hex / denominator_hex로 Fraction을 기록한다.
음수 numerator에는 -0x prefix가 붙고 denominator는 양수다.
기존 VM Exact profile의 출력을 직렬화했으며 별도 independent arithmetic이 아니다.
두 n0=0 fixture만 원래 국소 검사 latent 시작점과 연결된다.
n0=50000/99992 anchor의 full-state는 frozen fixture 원자료지만 historical latent start는 미보존이다.
full-state vx/vy를 latent vhx/vhy로 간주하거나 full-state에서 새 init을 하여 원래 checkpoint라고 표시하면 안 된다.
