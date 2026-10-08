"""Independent hand-literal graph bridge cases; no native producer imports."""
import copy

import pytest

from test_v1_evex_checker import fixture, DEST, BASE
from verified_driver.v1 import native_evex_graph_checker as bridge


def project(state):
    regs = state["registers"]
    names = ["rax", "rbx", "rcx", "rdx", "rsi", "rdi", "rbp", "rsp", *[f"r{i}" for i in range(8, 16)], "rip"]
    return {"gpr": {name: f"0x{regs[name]:016x}" for name in names},
            "xmm": {f"xmm{i}": "0x" + bytes.fromhex(state["vectors"][f"zmm{i}"])[:16][::-1].hex() for i in range(16)},
            "extra_vectors": {"ymm16": "0x" + bytes.fromhex(state["vectors"]["zmm16"])[:32][::-1].hex()},
            "segment_bases": {"fs_base": f"0x{regs['fs_base']:016x}", "gs_base": f"0x{regs['gs_base']:016x}"},
            "mxcsr": regs["mxcsr"], "eflags": regs["eflags"]}


def graph_fixture(tmp_path, monkeypatch):
    document, library, _ = fixture(tmp_path)
    rows = []
    decoded = {}
    for seq, item in enumerate(document["steps"]):
        pc = item["elf_pc"]
        opcode = ["endbr64", "vpbroadcastb", "mov", "cmp", "jb", "and", "cmp", "ja", "mov", "bzhi", "kmovd", "vmovdqu8", "ret"][seq]
        kind = "ZERO_FILL" if seq == 1 else "MOVE" if seq == 11 else "CONTROL" if seq in (4, 7, 12) else "ROUTING"
        operands = []
        result = None
        if seq == 1:
            operands = [{"kind": "register", "register": "esi", "width": 1, "raw_bits": "0x00", "access": "read"},
                        {"kind": "register", "register": "ymm16", "width": 32, "raw_bits": "0x" + "ab" * 32, "access": "write"}]
            result = "0x" + "00" * 32
        if seq == 11:
            operands = [{"kind": "register", "register": "ymm16", "width": 16, "raw_bits": "0x" + "00" * 16, "access": "read"},
                        {"kind": "memory", "address": DEST, "width": 16, "raw_bits": "0x" + "00" * 16, "access": "write"}]
            result = "0x" + "00" * 16
        if seq == 12:
            operands = [{"kind": "memory", "address": 0x30000000, "width": 8, "raw_bits": "0x0000000012345678", "access": "read"}]
        row = {"seq": seq, "phase": "init", "step": 0, "ptid": [1, 1, 0],
               "module_path": "libc", "module_sha256": document["library"]["sha256"],
               "module_load_base": BASE, "elf_address": pc, "bytes": item["instruction_bytes"],
               "runtime_pc": BASE + pc, "post_pc": item["after"]["registers"]["rip"],
               "kind": kind, "opcode": opcode, "pre": project(item["before"]), "post": project(item["after"]),
               "operands": operands, "result_bits": result,
               "extra": {}, "native_evex": {k: copy.deepcopy(item[k]) for k in ("before", "after", "reads", "writes")},
               "pre_memory_observations": copy.deepcopy(item["reads"]),
               "possible_memory_writes": [{**write, "before_hex": "00", "value_changed": False} for write in item["writes"]]}
        rows.append(row)
        decoded["libc", pc] = opcode
    pointers = {"gradient": DEST, "q": DEST + 0x100, "full_v": DEST + 0x200, "latent": DEST + 0x300}
    region = {"occurrence": "init", "start_seq": 0, "end_seq": 13, "pointers": pointers,
              "start_state": {name: ["0x0000000000000000"] * 2 for name in pointers},
              "end_state": {name: ["0x0000000000000000"] * 2 for name in pointers},
              "mxcsr": 0x1F80, "entry_pc": BASE + 0x1996C0, "return_pc": 0x12345678}
    capture = {"modules": {"libc": {"sha256": document["library"]["sha256"], "load_base": BASE, "segments": []}}, "regions": [region]}
    # ELF/authentication logic has its separate real-byte unit tests; here the
    # audited resolver entry point is stubbed only at the process boundary.
    monkeypatch.setattr(bridge.raw_checker, "disassembly_for_rows", lambda body, modules, root=None: decoded)
    monkeypatch.setattr(bridge.raw_checker, "FrozenBinaryResolver", lambda root: None)
    return capture, rows, [region], [{"start_seq": 0, "end_seq": 13}]


def test_hand_literal_zero_copy_provenance(tmp_path, monkeypatch):
    capture, rows, regions, spans = graph_fixture(tmp_path, monkeypatch)
    ops, values, state = bridge.graph(capture, rows, regions, tmp_path, spans)
    assert ops == []
    zero = next(v for v in values if v["value_id"] == "v:r1:zero")
    copy_value = next(v for v in values if v["value_id"] == "v:r11:copy")
    assert zero["width"] == 32 and zero["raw_bits"] == "0x" + "00" * 32
    assert zero["storage"] == {"space": "register", "name": "v16", "byte_offset": 0, "width": 32}
    assert copy_value["width"] == 16 and copy_value["storage"]["name"] == "gradient"
    assert copy_value["source_slices"] == [{"value_id": "v:r1:zero", "source_offset": 0, "destination_offset": 0,
        "width": 16, "trace_sequence": 11, "source_operand_index": 0,
        "source_storage": {"space": "register", "name": "v16", "byte_offset": 0, "width": 16},
        "destination_storage": {"space": "buffer", "name": "gradient", "byte_offset": 0, "width": 16}}]
    assert all(state["m", DEST + i] == ("v:r11:copy", i) for i in range(16))


@pytest.mark.parametrize("attack", ["missing_span", "overlap", "deletedrow", "deletedwrite", "outsidewrite", "sourceoperand",
    "projection", "native_result", "samevalue", "mask", "code", "unmarked", "thread", "retread", "outsidevector", "prebyte", "boolsize",
    "length", "fill", "boundary_bits", "boundary_alias", "boundary_width"])
def test_raw_graph_mutations_refuse(tmp_path, monkeypatch, attack):
    capture, rows, regions, spans = graph_fixture(tmp_path, monkeypatch)
    if attack == "missing_span": spans = []
    elif attack == "overlap": spans *= 2
    elif attack == "deletedrow": rows.pop(9)
    elif attack == "deletedwrite": rows[11]["possible_memory_writes"].pop()
    elif attack == "outsidewrite": rows[11]["possible_memory_writes"].append({"address": DEST + 16, "size": 1, "after_hex": "00", "before_hex": "00", "value_changed": False})
    elif attack == "sourceoperand": rows[11]["operands"][0]["raw_bits"] = "0x" + "01" + "00" * 15
    elif attack == "projection": rows[0]["pre"]["gpr"]["rax"] = "0x0000000000000000"
    elif attack == "native_result": rows[1]["native_evex"]["after"]["vectors"]["zmm16"] = "01" + "00" * 63
    elif attack == "samevalue": rows[11]["possible_memory_writes"][0]["value_changed"] = True
    elif attack == "mask": rows[11]["native_evex"]["before"]["registers"]["k1"] = 0x7FFF
    elif attack == "code": rows[9]["bytes"] = "c4e268f5c8"
    elif attack == "unmarked": rows[0].pop("native_evex")
    elif attack == "thread": rows[9]["ptid"] = [2, 2, 0]
    elif attack == "retread": rows[12]["pre_memory_observations"] = []
    elif attack == "outsidevector": rows[0]["native_evex"]["after"]["vectors"]["zmm31"] = "ac" + "ab" * 63
    elif attack == "prebyte":
        rows[11]["possible_memory_writes"][0].update(before_hex="01", value_changed=True)
        rows[11]["operands"][1]["raw_bits"] = "0x" + "00" * 15 + "01"
    elif attack == "boolsize": rows[11]["native_evex"]["writes"][0]["size"] = True
    elif attack == "length": rows[0]["native_evex"]["before"]["registers"]["rdx"] = 15
    elif attack == "fill": rows[0]["native_evex"]["before"]["registers"]["rsi"] = 1
    elif attack == "boundary_bits": regions[0]["start_state"]["gradient"][0] = "0x0000000000000001"
    elif attack == "boundary_alias": regions[0]["pointers"]["q"] = DEST
    elif attack == "boundary_width": regions[0]["end_state"]["gradient"][0] = "0x00000000000000"
    with pytest.raises(ValueError): bridge.graph(capture, rows, regions, tmp_path, spans)


def test_native_copy_feeds_unchanged_audited_scalar_provenance(tmp_path, monkeypatch):
    capture, rows, regions, spans = graph_fixture(tmp_path, monkeypatch)
    for row in rows:
        for side in ('before', 'after'):
            row['native_evex'][side]['vectors']['zmm1'] = '000000000000f03f' + '00' * 56
        row['pre'] = project(row['native_evex']['before'])
        row['post'] = project(row['native_evex']['after'])
    pre = copy.deepcopy(rows[-1]['post'])
    moved = copy.deepcopy(pre)
    moved['gpr']['rip'] = '0x000000001234567c'
    moved['xmm']['xmm0'] = '0x' + '00' * 16
    move = {'seq': 13, 'phase': 'init', 'step': 0, 'ptid': [1, 1, 0],
        'module_path': 'scalar', 'module_sha256': '04' * 32, 'module_load_base': 0x12345456,
        'elf_address': 0x222, 'bytes': 'f20f1000', 'runtime_pc': 0x12345678, 'post_pc': 0x1234567C,
        'kind': 'MOVE', 'opcode': 'movsd', 'pre': pre, 'post': moved,
        'operands': [{'kind': 'memory', 'address': DEST, 'width': 8, 'raw_bits': '0x0000000000000000', 'access': 'read'},
                     {'kind': 'register', 'register': 'xmm0', 'width': 8, 'raw_bits': '0xabababababababab', 'access': 'write'}],
        'result_bits': '0x0000000000000000', 'extra': {}}
    added = copy.deepcopy(moved)
    added['gpr']['rip'] = '0x0000000012345680'
    added['xmm']['xmm0'] = '0x00000000000000003ff0000000000000'
    add = {'seq': 14, 'phase': 'init', 'step': 0, 'ptid': [1, 1, 0],
        'module_path': 'scalar', 'module_sha256': '04' * 32, 'module_load_base': 0x12345456,
        'elf_address': 0x226, 'bytes': 'f20f58c1', 'runtime_pc': 0x1234567C, 'post_pc': 0x12345680,
        'kind': 'ADD', 'opcode': 'addsd', 'pre': moved, 'post': added,
        'operands': [{'kind': 'register', 'register': 'xmm1', 'width': 8, 'raw_bits': '0x3ff0000000000000', 'access': 'read'},
                     {'kind': 'register', 'register': 'xmm0', 'width': 8, 'raw_bits': '0x0000000000000000', 'access': 'readwrite'}],
        'result_bits': '0x3ff0000000000000', 'extra': {}}
    rows.extend([move, add])
    regions[0].update(end_seq=15, return_pc=0x12345680)
    capture['modules']['scalar'] = {'sha256': '04' * 32, 'load_base': 0x12345456, 'segments': []}
    decoded = {('libc', row['elf_address']): row['opcode'] for row in rows[:13]}
    decoded.update({('scalar', 0x222): 'movsd (%rax),%xmm0', ('scalar', 0x226): 'addsd %xmm1,%xmm0'})
    monkeypatch.setattr(bridge.raw_checker, 'disassembly_for_rows', lambda body, modules, root=None: decoded)
    ops, values, state = bridge.graph(capture, rows, regions, tmp_path, spans)
    assert len(ops) == 1 and ops[0]['operation_kind'] == 'ADD_BINARY64'
    assert ops[0]['trace_sequence'] == 14 and ops[0]['output_raw_bits'] == '0x3ff0000000000000'
    copy_value = next(value for value in values if value['value_id'] == 'v:r13:copy')
    assert copy_value['source_slices'][0]['value_id'] == 'v:r11:copy'
    assert state['r', 'v0', 0] == ('v:r14:result', 0)
    add['result_bits'] = '0x3ff0000000000001'
    with pytest.raises(ValueError): bridge.graph(capture, rows, regions, tmp_path, spans)
