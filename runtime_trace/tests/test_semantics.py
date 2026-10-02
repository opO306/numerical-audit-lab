import pytest

from runtime_trace.semantics import Refused, check_finite, check_mxcsr, decode, effective_address, routing_widths


def test_scalar_operands_preserve_att_roles_and_indexed_address():
    op, kind, args, width = decode("mulsd  0x0(%rbp,%rax,8),%xmm1")
    assert (op, kind, width) == ("mulsd", "MUL", 8)
    assert args == ["0x0(%rbp,%rax,8)", "%xmm1"]
    assert effective_address(args[0], {"rbp": 0x1000, "rax": 3}, 0, 6) == 0x1018


def test_rip_relative_uses_next_instruction_and_signed_displacement():
    assert effective_address("-0x20(%rip)", {}, 0x1000, 8) == 0xfe8


@pytest.mark.parametrize("assembly", ["vfmadd132sd %xmm0,%xmm1,%xmm2", "addpd %xmm0,%xmm1",
                                     "divsd %xmm0,%xmm1", "sqrtsd %xmm0,%xmm1", "vaddsd %xmm0,%xmm1,%xmm2",
                                     "movsd", "mov (%rax),(%rdx)", "pxor %xmm0,%xmm1",
                                     "rep stos %al,%es:(%rdi)"])
def test_unsupported_or_ambiguous_forms_refuse(assembly):
    with pytest.raises(Refused): decode(assembly)


def test_scalar_path_register_copy_is_bit_transfer_not_packed_arithmetic():
    assert decode("movapd %xmm1,%xmm2")[1:] == ("MOVE", ["%xmm1", "%xmm2"], 16)
    assert decode("movq %xmm1,%r15")[3] == 8
    assert decode("vpxor %xmm0,%xmm0,%xmm0")[1] == "ZERO"
    assert decode("vmovd %esi,%xmm0")[1:] == ("MOVE", ["%esi", "%xmm0"], 4)


def test_nop_prefix_does_not_implicitly_enable_prefixed_arithmetic():
    assert decode("data16 cs nopw 0x0(%rax,%rax,1)")[1] == "ROUTING"
    with pytest.raises(Refused): decode("data16 addsd %xmm0,%xmm1")


@pytest.mark.parametrize("value", [0x1fa0 | (1 << 15), 0x1fa0 | (1 << 6), 0x1fa0 | (1 << 13), 0])
def test_fp_environment_refuses_incompatible_control(value):
    with pytest.raises(Refused): check_mxcsr(value)


def test_flags_are_observed_not_forced_and_nonfinite_is_refused():
    check_mxcsr(0x1f80); check_mxcsr(0x1fa0)
    check_finite("0x8000000000000000")
    for value in ["0x7ff0000000000000", "0x7ff8000000000000"]:
        with pytest.raises(Refused): check_finite(value)


def test_unknown_or_segment_address_refuses():
    for operand in ["%fs:0x28", "(%notareg)", "(%rax,%rdx,3)"]:
        with pytest.raises(Refused): effective_address(operand, {"rax": 0, "rdx": 0}, 0, 3)


@pytest.mark.parametrize("op,args,widths",[("movslq",["(%rdi)","%rsi"],[4,8]),
    ("movslq",["%esi","%rax"],[4,8]),("cmpb",["$0x0","0x3f(%rsp)"],[1,1]),
    ("cmp",["$0x1","%eax"],[4,4]),("test",["%rsi","%rsi"],[8,8])])
def test_integer_routing_records_actual_source_destination_widths(op,args,widths):
    assert routing_widths(op,args)==widths
