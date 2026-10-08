"""Hand-authored native fixtures; no producer and no recorded-post oracle.

The tiny ELF is a synthetic unit fixture, never Gala execution evidence.
"""
import copy
import hashlib
import struct

import pytest

from verified_driver.v1.native_evex_checker import Refused, derive_step, verify_trace


PATH = [
    (0x1996C0, "f30f1efa"), (0x1996C4, "62e27d287ac6"),
    (0x1996CA, "4889f8"), (0x1996CD, "4883fa20"),
    (0x1996D1, "722d"), (0x199700, "81e7ff0f0000"),
    (0x199706, "81ffe00f0000"), (0x19970C, "0f87ae000000"),
    (0x199712, "b9ffffffff"), (0x199717, "c4e268f5c9"),
    (0x19971C, "c5fb92c9"), (0x199720, "62e17f297f00"),
    (0x199726, "c3"),
]
BASE = 0x70000000
DEST = 0x20002040
RETURN = 0x12345678


def context():
    registers = dict.fromkeys([
        "rax", "rbx", "rcx", "rdx", "rsi", "rdi", "rbp", "rsp",
        *[f"r{i}" for i in range(8, 16)], "rip", "eflags", "mxcsr",
        "fs_base", "gs_base", *[f"k{i}" for i in range(8)],
    ], 0)
    registers.update(rax=99, rbx=0x987654321, rcx=0xDEADBEEF12345678,
                     rdi=DEST, rdx=16, rsp=0x30000000,
                     rip=BASE + 0x1996C0, eflags=0x202, mxcsr=0x1F80,
                     fs_base=0x40000000, gs_base=0x50000000)
    registers.update(cs=0x33, ss=0x2b, ds=0, es=0, fs=0, gs=0)
    return {"registers": registers,
            "vectors": {f"zmm{i}": "ab" * 64 for i in range(32)},
            "fpu": {"fctrl": 0x37F, "fstat": 0, "ftag": 0xFFFF,
                    "fiseg": 0, "fioff": 0, "foseg": 0, "fooff": 0,
                    "fop": 0, **{f"st{i}": "bc" * 10 for i in range(8)}},
            "control": {"cet_ibt": False, "cet_shstk": False},
            "unavailable": []}


def fixture(tmp_path):
    # A literal independent ELF64 image: executable load plus GNU Build ID.
    raw = bytearray(0x2000)
    raw[:16] = b"\x7fELF\x02\x01\x01" + bytes(9)
    struct.pack_into("<HHIQQQIHHHHHH", raw, 16,
                     3, 62, 1, 0, 64, 0, 0, 64, 56, 2, 0, 0, 0)
    struct.pack_into("<IIQQQQQQ", raw, 64, 1, 5, 0x1000,
                     0x199000, 0, 0x1000, 0x1000, 0x1000)
    struct.pack_into("<IIQQQQQQ", raw, 120, 4, 4, 0x200,
                     0, 0, 20, 20, 4)
    raw[0x200:0x214] = struct.pack("<III", 4, 4, 3) + b"GNU\0" + bytes.fromhex("12345678")
    for pc, code in PATH:
        offset = 0x1000 + pc - 0x199000
        raw[offset:offset + len(code) // 2] = bytes.fromhex(code)
    library = tmp_path / "synthetic-libc.so"
    library.write_bytes(raw)
    domain = {"provenance_kind": "ACTUAL_GALA_CALL",
              "source_sha256": "01" * 32, "caller_module_sha256": "02" * 32,
              "caller_elf_pc": 0x1234, "caller_instruction_bytes": "e800000000",
              "caller_return_pc": RETURN, "caller_load_base": 0x1234443F,
              "caller_path": "synthetic-unit-caller", "caller_build_id": "deadbeef",
              "destination": DEST, "length": 16, "fill": 0,
              "libc_sha256": hashlib.sha256(raw).hexdigest(),
              "libc_build_id": "12345678"}
    initial = context()
    current = copy.deepcopy(initial)
    rows = []
    # Hand-evaluated states: CMP16-32 -> 0x287; AND0x40 -> 0x202;
    # CMP0x40-0xfe0 -> 0x287; BZHI32 0xffffffff,16 -> 0xffff -> 0x206.
    changes = [{}, {}, {"rax": DEST}, {"eflags": 0x287}, {},
               {"rdi": 0x40, "eflags": 0x202}, {"eflags": 0x287}, {},
               {"rcx": 0xFFFFFFFF}, {"rcx": 0xFFFF, "eflags": 0x206},
               {"k1": 0xFFFF}, {}, {"rsp": 0x30000008}]
    next_pcs = [pc for pc, _ in PATH[1:]] + [RETURN - BASE]
    for i, (pc, code) in enumerate(PATH):
        before = copy.deepcopy(current)
        current["registers"].update(changes[i], rip=BASE + next_pcs[i])
        if i == 1:
            current["vectors"]["zmm16"] = "00" * 64
        reads = [{"address": 0x30000000, "size": 8,
                  "bytes_hex": "7856341200000000"}] if i == 12 else []
        writes = [{"address": DEST + lane, "size": 1, "after_hex": "00"}
                  for lane in range(16)] if i == 11 else []
        rows.append({"elf_pc": pc, "instruction_bytes": code, "before": before,
                     "after": copy.deepcopy(current), "reads": reads, "writes": writes})
    doc = {"schema": "native-evex-trace-v1", "library": {
        "sha256": hashlib.sha256(raw).hexdigest(), "build_id": "12345678"},
        "load_base": BASE, "domain": domain, "entry": initial,
        "exit": copy.deepcopy(current), "steps": rows}
    return doc, library, copy.deepcopy(domain)


def test_complete_hand_literal_path(tmp_path):
    document, library, domain = fixture(tmp_path)
    result = verify_trace(document, library, domain)
    assert result["verdict"] == "PASS"
    assert result["instruction_count"] == 13
    assert result["write_count"] == 16
    assert result["read_count"] == 1
    assert result["undefined_flags"] == [
        {"step": 5, "mask": 0x10}, {"step": 9, "mask": 0x14}]


@pytest.mark.parametrize("attack", [
    "resultbit", "outsidewrite", "preservedreg", "codebyte",
    "samevaluewriteomission", "caller", "entry", "mask", "length",
    "nonzerofill", "otherlibc",
])
def test_eleven_negative_classes(tmp_path, attack):
    document, library, domain = fixture(tmp_path)
    if attack == "resultbit":
        document["steps"][9]["after"]["registers"]["rcx"] ^= 1
    elif attack == "outsidewrite":
        document["steps"][11]["writes"].append({"address": DEST + 16, "size": 1, "after_hex": "00"})
    elif attack == "preservedreg":
        document["steps"][0]["after"]["registers"]["rbx"] ^= 1
    elif attack == "codebyte":
        document["steps"][1]["instruction_bytes"] = "62e27d287ac7"
    elif attack == "samevaluewriteomission":
        document["steps"][11]["writes"].pop()
    elif attack == "caller":
        document["domain"]["caller_module_sha256"] = "03" * 32
    elif attack == "entry":
        document["entry"]["registers"]["rip"] += 4
    elif attack == "mask":
        document["steps"][10]["after"]["registers"]["k1"] = 0x7FFF
    elif attack == "length":
        document["entry"]["registers"]["rdx"] = 15
    elif attack == "nonzerofill":
        document["entry"]["registers"]["rsi"] = 1
    elif attack == "otherlibc":
        data = bytearray(library.read_bytes())
        data[0x1000 + 0x6C0] ^= 1
        library.write_bytes(data)
        document["library"]["sha256"] = hashlib.sha256(data).hexdigest()
    with pytest.raises(Refused):
        verify_trace(document, library, domain)


@pytest.mark.parametrize("change", [
    lambda s: s.pop("fpu"), lambda s: s.pop("control"),
    lambda s: s["unavailable"].append("zmm31"),
    lambda s: s["vectors"].pop("zmm31"),
    lambda s: s["vectors"].update(zmm32="00" * 64),
    lambda s: s["vectors"].update(zmm0="00" * 32),
    lambda s: s["registers"].update(rax=True),
    lambda s: s["registers"].update(eflags=1 << 32),
    lambda s: s["fpu"].update(st0="00" * 9),
    lambda s: s["control"].update(cet_shstk=True),
])
def test_incomplete_or_invalid_context_refuses(change):
    state = context()
    change(state)
    with pytest.raises(Refused):
        derive_step(0x1996C0, "f30f1efa", state, lambda a, n: bytes(n), BASE)


def test_broadcast_zero_upper_and_preserve_other_vectors():
    state = context()
    state["registers"].update(rip=BASE + 0x1996C4, rsi=0x100A5)
    result = derive_step(0x1996C4, "62e27d287ac6", state, None, BASE)
    assert result["after"]["vectors"]["zmm16"] == "a5" * 32 + "00" * 32
    assert result["after"]["vectors"]["zmm17"] == "ab" * 64
    assert result["after"]["fpu"] == state["fpu"]


@pytest.mark.parametrize("index,expected,flags", [
    (0, 0, 0x242), (16, 0xFFFF, 0x202), (31, 0x7FFFFFFF, 0x202),
    (32, 0xFFFFFFFF, 0x283), (256, 0, 0x242), (255, 0xFFFFFFFF, 0x283),
])
def test_bzhi_index_low8_zeroextend_and_defined_flags(index, expected, flags):
    state = context()
    state["registers"].update(rip=BASE + 0x199717,
                              rcx=0x12345678FFFFFFFF, rdx=index)
    result = derive_step(0x199717, "c4e268f5c9", state, None, BASE)
    assert result["after"]["registers"]["rcx"] == expected
    assert result["after"]["registers"]["eflags"] & 0xFFFFFFEB == flags
    assert result["defined_flags_mask"] == 0xFFFFFFEB


def test_undefined_bits_may_vary_and_are_carried(tmp_path):
    document, library, domain = fixture(tmp_path)
    # AF is undefined after AND; its observed setting carries until CMP derives AF.
    for row in document["steps"][5:7]:
        row["before"]["registers"]["eflags"] |= 0x10 if row is document["steps"][6] else 0
    document["steps"][5]["after"]["registers"]["eflags"] |= 0x10
    assert verify_trace(document, library, domain)["verdict"] == "PASS"


def test_ret_exact_stack_read_no_store(tmp_path):
    document, library, domain = fixture(tmp_path)
    document["steps"][12]["writes"].append({"address": 0x30000000, "size": 1, "after_hex": "78"})
    with pytest.raises(Refused):
        verify_trace(document, library, domain)


def test_no_store_reads_or_omitted_ret_reads(tmp_path):
    document, library, domain = fixture(tmp_path)
    document["steps"][11]["reads"] = [{"address": DEST, "size": 1, "bytes_hex": "00"}]
    with pytest.raises(Refused):
        verify_trace(document, library, domain)
    document, library, domain = fixture(tmp_path)
    document["steps"][12]["reads"] = []
    with pytest.raises(Refused):
        verify_trace(document, library, domain)


def test_cross_page_route_refused(tmp_path):
    document, library, domain = fixture(tmp_path)
    domain["destination"] = DEST | 0xFF0
    document["domain"] = copy.deepcopy(domain)
    document["entry"]["registers"]["rdi"] = domain["destination"]
    with pytest.raises(Refused):
        verify_trace(document, library, domain)


@pytest.mark.parametrize("name", sorted(context()["registers"]))
def test_every_preserved_register_bit_checked(tmp_path, name):
    document, library, domain = fixture(tmp_path)
    document["steps"][0]["after"]["registers"][name] ^= 1
    with pytest.raises(Refused):
        verify_trace(document, library, domain)


@pytest.mark.parametrize("name", sorted(context()["vectors"]))
def test_every_preserved_zmm_checked(tmp_path, name):
    document, library, domain = fixture(tmp_path)
    document["steps"][0]["after"]["vectors"][name] = "aa" + "ab" * 63
    with pytest.raises(Refused):
        verify_trace(document, library, domain)


@pytest.mark.parametrize("name", sorted(context()["fpu"]))
def test_every_raw_fp_field_checked(tmp_path, name):
    document, library, domain = fixture(tmp_path)
    value = document["steps"][0]["after"]["fpu"][name]
    document["steps"][0]["after"]["fpu"][name] = value ^ 1 if type(value) is int else "bd" + "bc" * 9
    with pytest.raises(Refused):
        verify_trace(document, library, domain)


@pytest.mark.parametrize("step,bit", [(3, 1), (3, 4), (3, 16), (3, 64), (3, 128), (3, 2048),
                                     (5, 1), (5, 4), (5, 64), (5, 128), (5, 2048),
                                     (6, 1), (6, 4), (6, 16), (6, 64), (6, 128), (6, 2048),
                                     (9, 1), (9, 64), (9, 128), (9, 2048)])
def test_every_defined_status_flag_checked(tmp_path, step, bit):
    document, library, domain = fixture(tmp_path)
    document["steps"][step]["after"]["registers"]["eflags"] ^= bit
    with pytest.raises(Refused):
        verify_trace(document, library, domain)


def test_bzhi_undefined_af_pf_are_carried_not_claimed(tmp_path):
    document, library, domain = fixture(tmp_path)
    document["steps"][9]["after"]["registers"]["eflags"] ^= 0x14
    for row in document["steps"][10:]:
        row["before"]["registers"]["eflags"] ^= 0x14
        row["after"]["registers"]["eflags"] ^= 0x14
    document["exit"]["registers"]["eflags"] ^= 0x14
    assert verify_trace(document, library, domain)["verdict"] == "PASS"


def test_typed_authority_domain_and_build_id_checked(tmp_path):
    document, library, domain = fixture(tmp_path)
    document["domain"]["fill"] = False
    with pytest.raises(Refused):
        verify_trace(document, library, domain)
    document, library, domain = fixture(tmp_path)
    document["library"]["build_id"] = "12345679"
    document["domain"]["libc_build_id"] = "12345679"
    domain["libc_build_id"] = "12345679"
    with pytest.raises(Refused):
        verify_trace(document, library, domain)


def test_exact_elf_bytes_even_after_rebinding_sha(tmp_path):
    document, library, domain = fixture(tmp_path)
    raw = bytearray(library.read_bytes())
    raw[0x16C4] ^= 1
    library.write_bytes(raw)
    digest = hashlib.sha256(raw).hexdigest()
    document["library"]["sha256"] = digest
    document["domain"]["libc_sha256"] = digest
    domain["libc_sha256"] = digest
    with pytest.raises(Refused, match="actual executable ELF instruction bytes"):
        verify_trace(document, library, domain)


def test_wrong_stack_return_seam_and_fallthrough_domain(tmp_path):
    document, library, domain = fixture(tmp_path)
    document["steps"][12]["reads"][0]["bytes_hex"] = "7956341200000000"
    document["steps"][12]["after"]["registers"]["rip"] += 1
    document["exit"]["registers"]["rip"] += 1
    with pytest.raises(Refused, match="return caller seam"):
        verify_trace(document, library, domain)
    document, library, domain = fixture(tmp_path)
    domain["caller_return_pc"] += 1
    document["domain"] = copy.deepcopy(domain)
    with pytest.raises(Refused, match="CALL fallthrough return seam"):
        verify_trace(document, library, domain)


def test_lane_mask_writes_only_low32_and_kmov_zeroextends():
    state = context()
    state["registers"].update(rip=BASE + 0x19971C,
                              rcx=0xDEAD000080000001, k1=(1 << 64) - 1)
    result = derive_step(0x19971C, "c5fb92c9", state, None, BASE)
    assert result["after"]["registers"]["k1"] == 0x80000001
    state["registers"].update(rip=BASE + 0x199720, rax=DEST,
                              k1=0xFFFFFFFF80000001)
    result = derive_step(0x199720, "62e17f297f00", state, None, BASE)
    assert result["reads"] == []
    assert result["writes"] == [{"address": DEST, "size": 1, "after_hex": "ab"},
                                 {"address": DEST + 31, "size": 1, "after_hex": "ab"}]


@pytest.mark.parametrize("mutate", [
    lambda d: d["steps"].pop(), lambda d: d["steps"].reverse(),
    lambda d: d["steps"][2]["before"]["registers"].update(rbx=0),
    lambda d: d["steps"][4]["after"]["registers"].update(rip=BASE + 0x1996D3),
    lambda d: d["steps"][7]["after"]["registers"].update(rip=BASE + 0x1997C0),
    lambda d: d["steps"][11]["writes"].reverse(),
    lambda d: d["steps"][12]["reads"][0].update(size=7, bytes_hex="78563412000000"),
])
def test_path_continuity_order_read_width_refuses(tmp_path, mutate):
    document, library, domain = fixture(tmp_path)
    mutate(document)
    with pytest.raises(Refused):
        verify_trace(document, library, domain)


def test_resume_flag_requires_outside_supported_domain():
    state = context()
    state['registers']['eflags'] |= 1 << 16
    with pytest.raises(Refused, match='resume flag'):
        derive_step(0x1996C0, 'f30f1efa', state, None, BASE)


@pytest.mark.parametrize('rsp', [0xFFFFFFFFFFFFFFF8, 0x7FFFFFFFFFF8])
def test_ret_successor_rsp_wrap_or_noncanonical_refused(rsp):
    state = context()
    state['registers'].update(rip=BASE + 0x199726, rsp=rsp)
    with pytest.raises(Refused, match='RET successor RSP'):
        derive_step(0x199726, 'c3', state, lambda address, size: bytes.fromhex('7856341200000000'), BASE)


SELECTOR_NAMES = ('cs', 'ss', 'ds', 'es', 'fs', 'gs')
SELECTOR_VALUES = dict(zip(SELECTOR_NAMES, (0x33, 0x2b, 0, 1, 0xfffe, 0xffff)))


def selector_context(pc):
    complete = copy.deepcopy(context())
    complete['registers'].update(SELECTOR_VALUES, rip=BASE + pc)
    return complete


def selector_fixture(tmp_path):
    document, library, domain = fixture(tmp_path)
    # Add only actual hand-literal selector values to the dedicated clone.
    # Producer arithmetic supplies none of the independent checker fixture.
    for complete in [document['entry'], document['exit']] + [
            complete for row in document['steps'] for complete in (row['before'], row['after'])]:
        complete['registers'].update(SELECTOR_VALUES)
    return document, library, domain


@pytest.mark.parametrize('pc,code', PATH)
def test_all_thirteen_checker_forms_preserve_actual_six_uint16_selectors(pc, code):
    before = selector_context(pc)
    frozen = copy.deepcopy(before)
    result = derive_step(pc, code, before, lambda *_: bytes.fromhex('7856341200000000'), BASE)
    assert {name: result['after']['registers'][name] for name in SELECTOR_NAMES} == SELECTOR_VALUES
    assert all(type(result['after']['registers'][name]) is int for name in SELECTOR_NAMES)
    assert before == frozen


@pytest.mark.parametrize('step', range(13))
@pytest.mark.parametrize('name', SELECTOR_NAMES)
def test_checker_compares_each_actual_selector_at_every_instruction(tmp_path, step, name):
    document, library, domain = selector_fixture(tmp_path)
    assert verify_trace(document, library, domain)['verdict'] == 'PASS'
    document['steps'][step]['after']['registers'][name] ^= 1
    with pytest.raises(Refused):
        verify_trace(document, library, domain)


@pytest.mark.parametrize('name', SELECTOR_NAMES)
def test_checker_missing_actual_selector_refuses(name):
    before = selector_context(0x1996c0)
    derive_step(0x1996c0, 'f30f1efa', before, None, BASE)
    del before['registers'][name]
    with pytest.raises(Refused):
        derive_step(0x1996c0, 'f30f1efa', before, None, BASE)


@pytest.mark.parametrize('name', SELECTOR_NAMES)
@pytest.mark.parametrize('value', [-1, 1 << 16, True, False])
def test_checker_selector_width_and_boolean_refuse(name, value):
    before = selector_context(0x1996c0)
    derive_step(0x1996c0, 'f30f1efa', before, None, BASE)
    before['registers'][name] = value
    with pytest.raises(Refused):
        derive_step(0x1996c0, 'f30f1efa', before, None, BASE)
