import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]


def _registers(**updates):
    values = {name: 0 for name in [
        "rax", "rbx", "rcx", "rdx", "rsi", "rdi", "rbp", "rsp",
        "r8", "r9", "r10", "r11", "r12", "r13", "r14", "r15", "rip",
    ]}
    values.update(updates)
    return values


@pytest.mark.parametrize(
    ("assembly", "registers", "segments", "pc", "length", "expected"),
    [
        ("ret", _registers(rsp=0x1000), {"fs_base": 0, "gs_base": 0}, 0x4000, 1,
         [(0x1000, 8, "IMPLICIT_RET")]),
        ("pop %rbx", _registers(rsp=0x1010), {"fs_base": 0, "gs_base": 0}, 0x4000, 1,
         [(0x1010, 8, "IMPLICIT_POP")]),
        ("leave", _registers(rbp=0x1020), {"fs_base": 0, "gs_base": 0}, 0x4000, 1,
         [(0x1020, 8, "IMPLICIT_LEAVE")]),
        ("jmp *0x20(%rip)", _registers(), {"fs_base": 0, "gs_base": 0}, 0x4000, 6,
         [(0x4026, 8, "INDIRECT_CONTROL")]),
        ("movsd 0x18(%r13),%xmm0", _registers(r13=0x2000),
         {"fs_base": 0, "gs_base": 0}, 0x4000, 5, [(0x2018, 8, "EXPLICIT")]),
        ("mov %fs:0x10,%rax", _registers(), {"fs_base": 0x7000, "gs_base": 0},
         0x4000, 9, [(0x7010, 8, "EXPLICIT")]),
        ("push 0x38(%rsp)", _registers(rsp=0x3000), {"fs_base": 0, "gs_base": 0},
         0x4000, 4, [(0x3038, 8, "EXPLICIT")]),
        ("lock cmpxchg %edx,(%rdi)", _registers(rdi=0x5000),
         {"fs_base": 0, "gs_base": 0}, 0x4000, 4, [(0x5000, 4, "READ_MODIFY_WRITE")]),
    ],
)
def test_required_reads_address_width_and_kind(assembly, registers, segments, pc, length, expected):
    from runtime_trace.caller_transition.read_effects import required_reads

    actual = required_reads(assembly, registers, segments, pc, length)
    assert [(item["address"], item["size"], item["kind"]) for item in actual] == expected


@pytest.mark.parametrize(
    "assembly",
    [
        "lea 0x10(%rax),%rdx",
        "nopw 0x0(%rax,%rax,1)",
        "mov %rax,0x8(%rdx)",
        "vmovdqu %xmm0,(%rdi)",
    ],
)
def test_non_reading_memory_syntax_is_not_observed(assembly):
    from runtime_trace.caller_transition.read_effects import required_reads

    assert required_reads(
        assembly, _registers(rax=0x1000, rdx=0x2000, rdi=0x3000),
        {"fs_base": 0, "gs_base": 0}, 0x4000, 5,
    ) == []


def test_all_observed_v1_instructions_have_closed_read_classification():
    from runtime_trace.caller_transition.read_effects import required_reads

    trace = ROOT / "runtime_trace/caller_transition/artifacts/audited-attempt-05/caller_trace.jsonl"
    for line in trace.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        registers = {name: int(value, 16) for name, value in row["pre"]["gpr"].items()}
        required_reads(
            row["assembly"], registers, {"fs_base": 0, "gs_base": 0},
            row["pc"], len(bytes.fromhex(row["instruction_bytes"])),
        )


@pytest.mark.parametrize(
    ("assembly", "segments", "expected"),
    [
        ("movq $0x0,%fs:0xfffffffffffffff8", {"fs_base": 0x7000, "gs_base": 0},
         (0x6FF8, 8, "EXPLICIT")),
        ("mov %rdi,%fs:0xfffffffffffffff8", {"fs_base": 0x8000, "gs_base": 0},
         (0x7FF8, 8, "EXPLICIT")),
        ("andb $0xef,%gs:0x18", {"fs_base": 0, "gs_base": 0x9000},
         (0x9018, 1, "EXPLICIT")),
    ],
)
def test_segment_relative_writes_use_recorded_base(assembly, segments, expected):
    from runtime_trace.caller_transition.write_effects_reads import possible_writes

    writes = possible_writes(assembly, _registers(rdi=0x1234), segments, 0x4000, 9)
    assert [(item["address"], item["size"], item["kind"]) for item in writes] == [expected]
