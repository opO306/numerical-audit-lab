import pytest


def regs(**updates):
    base = {name: 0 for name in [
        "rax", "rbx", "rcx", "rdx", "rsi", "rdi", "rbp", "rsp",
        "r8", "r9", "r10", "r11", "r12", "r13", "r14", "r15", "rip",
    ]}
    base.update(updates)
    return base


@pytest.mark.parametrize(
    ("assembly", "registers", "pc", "length", "expected"),
    [
        ("call 0x1234", regs(rsp=0x2000), 0x1000, 5, [(0x1FF8, 8, "CALL_STACK")]),
        ("push %rbp", regs(rsp=0x2000), 0x1000, 1, [(0x1FF8, 8, "PUSH_STACK")]),
        ("movsd %xmm0,0x8(%rax)", regs(rax=0x3000), 0x1000, 5, [(0x3008, 8, "EXPLICIT")]),
        ("rep stos %rax,%es:(%rdi)", regs(rdi=0x4000, rcx=2), 0x1000, 3, [(0x4000, 16, "STRING")]),
    ],
)
def test_write_effects_cover_explicit_implicit_and_string_writes(
    assembly, registers, pc, length, expected
):
    from runtime_trace.caller_transition.write_effects import possible_writes

    got = possible_writes(assembly, registers, pc, length)
    assert [(x["address"], x["size"], x["kind"]) for x in got] == expected


def test_write_effects_refuse_unsupported_opcode():
    from runtime_trace.caller_transition.write_effects import EffectsRefused, possible_writes

    with pytest.raises(EffectsRefused, match="unsupported"):
        possible_writes("mystery %rax,(%rbx)", regs(rbx=0x1000), 0, 3)
