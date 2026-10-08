"""Independent finite byte-bound EVEX memset checker.

No producer imports, observation assembly, or observed-result arithmetic.
Intel SDM Vol. 2 is the ISA authority (BZHI, CMP, AND, VPBROADCASTB,
KMOVD, VMOVDQU8, RET, ENDBR64):
https://www.intel.com/content/www/us/en/developer/articles/technical/intel-sdm.html

``verify_trace(document, library_path, expected_domain)`` authenticates the
libc ELF and replays exactly thirteen instructions. ``expected_domain`` must
come from the separate authority gate after it authenticates the actual Gala
caller ELF, CALL/GOT target, acquisition identity and source snapshot. Equality
to a document supplied by its own author is not caller authentication. This
module's PASS is finite native semantics, never independent promotion authority.

Document keys are schema/library/load_base/domain/entry/exit/steps. library is
{sha256,build_id}; step keys are elf_pc/instruction_bytes/before/after/reads/writes.
Domain required fields are listed in DOMAIN_KEYS; extra externally authenticated
domain fields are permitted and must match exactly. States use complete GPR/K,
ZMM0..31, raw x87, CET-disabled and availability groups. Undefined flags are
excluded from each local comparison and explicitly carried from observations.
"""
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import re
import struct


class Refused(ValueError):
    """The exact finite native contract could not be established."""


U64 = (1 << 64) - 1
U32 = (1 << 32) - 1
CF, PF, AF, ZF, SF, OF = 1, 4, 16, 64, 128, 2048
STATUS = CF | PF | AF | ZF | SF | OF
PATH = (
    (0x1996C0, "f30f1efa"), (0x1996C4, "62e27d287ac6"),
    (0x1996CA, "4889f8"), (0x1996CD, "4883fa20"),
    (0x1996D1, "722d"), (0x199700, "81e7ff0f0000"),
    (0x199706, "81ffe00f0000"), (0x19970C, "0f87ae000000"),
    (0x199712, "b9ffffffff"), (0x199717, "c4e268f5c9"),
    (0x19971C, "c5fb92c9"), (0x199720, "62e17f297f00"),
    (0x199726, "c3"),
)
FORMS = dict(PATH)
REGISTERS = frozenset((
    "rax", "rbx", "rcx", "rdx", "rsi", "rdi", "rbp", "rsp",
    *(f"r{i}" for i in range(8, 16)), "rip", "eflags", "mxcsr",
    "fs_base", "gs_base", "cs", "ss", "ds", "es", "fs", "gs", *(f"k{i}" for i in range(8)),
))
FPU_INTS = {"fctrl": 16, "fstat": 16, "ftag": 16,
            "fiseg": 16, "fioff": 64, "foseg": 16, "fooff": 64, "fop": 16}
DOMAIN_KEYS = frozenset((
    "provenance_kind", "source_sha256", "caller_module_sha256",
    "caller_elf_pc", "caller_instruction_bytes", "caller_return_pc",
    "caller_load_base", "caller_path", "caller_build_id",
    "destination", "length", "fill", "libc_sha256", "libc_build_id",
))


def _need(condition, message):
    if not condition:
        raise Refused(message)


def _keys(value, expected, name):
    _need(type(value) is dict and set(value) == set(expected), name + " exact keys")


def _uint(value, width, name):
    _need(type(value) is int and 0 <= value < 1 << width, name + " unsigned width/type")


def _typed_equal(left, right):
    if type(left) is not type(right):
        return False
    if type(left) is dict:
        return set(left) == set(right) and all(_typed_equal(left[k], right[k]) for k in left)
    if type(left) is list:
        return len(left) == len(right) and all(_typed_equal(a, b) for a, b in zip(left, right))
    return left == right


def _hex(value, size, name):
    _need(type(value) is str and len(value) == size * 2 and
          re.fullmatch("[0-9a-f]*", value) is not None, name + " lowercase byte hex")
    return bytes.fromhex(value)


def _context(state):
    _keys(state, ("registers", "vectors", "fpu", "control", "unavailable"), "state")
    _keys(state["registers"], REGISTERS, "registers")
    for name, value in state["registers"].items():
        width = 16 if name in {"cs", "ss", "ds", "es", "fs", "gs"} else 32 if name in {"eflags", "mxcsr"} else 64
        _uint(value, width, name)
    _keys(state["vectors"], (f"zmm{i}" for i in range(32)), "vectors")
    for name, value in state["vectors"].items():
        _hex(value, 64, name)
    _keys(state["fpu"], (*FPU_INTS, *(f"st{i}" for i in range(8))), "fpu")
    for name, width in FPU_INTS.items():
        _uint(state["fpu"][name], width, name)
    for i in range(8):
        _hex(state["fpu"][f"st{i}"], 10, f"st{i}")
    _keys(state["control"], ("cet_ibt", "cet_shstk"), "control")
    _need(all(value is False for value in state["control"].values()), "CET must be disabled")
    _need(type(state["unavailable"]) is list and state["unavailable"] == [],
          "unavailable contract state")


def _canonical(address):
    return 0 <= address <= 0x7FFFFFFFFFFF or 0xFFFF800000000000 <= address <= U64


def _address(address, size):
    _uint(address, 64, "memory address")
    _need(type(size) is int and 0 < size <= 64, "memory size")
    _need(address + size - 1 <= U64 and _canonical(address) and
          _canonical(address + size - 1), "noncanonical/wrapped address")


def _parity(result):
    return PF if (result & 255).bit_count() % 2 == 0 else 0


def _subtract_flags(left, right, width):
    mask = (1 << width) - 1
    left &= mask
    right &= mask
    result = (left - right) & mask
    sign = 1 << (width - 1)
    return ((CF if left < right else 0) | _parity(result) |
            (AF if (left ^ right ^ result) & 16 else 0) |
            (ZF if result == 0 else 0) | (SF if result & sign else 0) |
            (OF if (left ^ right) & (left ^ result) & sign else 0))


def derive_step(elf_pc, instruction_bytes, before, read_memory, load_base):
    """Derive one exact form from pre-state; callback returns raw bytes for RET.

    For undefined flags, after contains only a template copied from before.
    ``defined_flags_mask`` explicitly excludes them; callers must not assert
    these template bits as ISA-preserved or derived.
    """
    _uint(elf_pc, 64, "ELF PC")
    _uint(load_base, 64, "load base")
    _need(elf_pc in FORMS and instruction_bytes == FORMS[elf_pc], "unsupported exact instruction bytes/PC")
    _context(before)
    _need(before['registers']['eflags'] & (1 << 16) == 0,
          'resume flag input outside finite supported domain')
    _need(load_base + elf_pc <= U64 and before["registers"]["rip"] == load_base + elf_pc,
          "instruction RIP binding")
    # Independent frame rule: these exact instruction forms never assign a
    # segment selector. C3 is a near RET, not a far privilege/CS transfer.
    # Compare all six observed selectors unchanged with every complete post;
    # their numeric values do not themselves establish active execution mode.
    after = deepcopy(before)
    reg = after["registers"]
    source = before["registers"]
    reg["rip"] += len(instruction_bytes) // 2
    _need(reg["rip"] <= U64, "RIP wrap")
    reads, writes, features = [], [], []
    defined_mask = U32
    if elf_pc == 0x1996C0:
        pass  # ENDBR64 is a NOP with CET disabled.
    elif elf_pc == 0x1996C4:
        after["vectors"]["zmm16"] = bytes([source["rsi"] & 255]).hex() * 32 + "00" * 32
        features = ["avx512f", "avx512bw", "avx512vl"]
    elif elf_pc == 0x1996CA:
        reg["rax"] = source["rdi"]
    elif elf_pc == 0x1996CD:
        reg["eflags"] = (source["eflags"] & ~STATUS) | _subtract_flags(source["rdx"], 32, 64)
    elif elf_pc == 0x1996D1:
        if source["eflags"] & CF:
            reg["rip"] += 0x2D
    elif elf_pc == 0x199700:
        result = source["rdi"] & 0xFFF
        reg["rdi"] = result
        defined_mask &= ~AF
        reg["eflags"] = ((source["eflags"] & ~(STATUS & ~AF)) |
                         _parity(result) | (ZF if result == 0 else 0))
    elif elf_pc == 0x199706:
        reg["eflags"] = (source["eflags"] & ~STATUS) | _subtract_flags(source["rdi"], 0xFE0, 32)
    elif elf_pc == 0x19970C:
        if not source["eflags"] & (CF | ZF):
            reg["rip"] += 0xAE
    elif elf_pc == 0x199712:
        reg["rcx"] = U32
    elif elf_pc == 0x199717:
        index = source["rdx"] & 255
        result = source["rcx"] & U32
        if index < 32:
            result &= (1 << index) - 1
        reg["rcx"] = result
        defined_mask &= ~(AF | PF)
        reg["eflags"] = ((source["eflags"] & ~(CF | ZF | SF | OF)) |
                         (CF if index >= 32 else 0) | (ZF if result == 0 else 0) |
                         (SF if result & (1 << 31) else 0))
        features = ["bmi2"]
    elif elf_pc == 0x19971C:
        reg["k1"] = source["rcx"] & U32
        features = ["avx512bw"]
    elif elf_pc == 0x199720:
        vector = bytes.fromhex(before["vectors"]["zmm16"])
        for lane in range(32):
            if source["k1"] & (1 << lane):
                address = source["rax"] + lane
                _address(address, 1)
                writes.append({"address": address, "size": 1,
                               "after_hex": vector[lane:lane + 1].hex()})
        features = ["avx512f", "avx512bw", "avx512vl"]
    elif elf_pc == 0x199726:
        _address(source["rsp"], 8)
        _need(source['rsp'] + 8 <= U64 and _canonical(source['rsp'] + 8),
              'RET successor RSP wrapped/noncanonical')
        _need(callable(read_memory), "RET memory reader unavailable")
        data = read_memory(source["rsp"], 8)
        _need(type(data) is bytes and len(data) == 8, "RET stack eight raw bytes")
        target = int.from_bytes(data, "little")
        _need(_canonical(target), "RET target noncanonical")
        reg["rip"] = target
        reg["rsp"] = source["rsp"] + 8
        reads.append({"address": source["rsp"], "size": 8, "bytes_hex": data.hex()})
    return {"after": after, "reads": reads, "writes": writes,
            "defined_flags_mask": defined_mask, "required_features": features}


def _elf(raw):
    """Independent ELF64 program-header parser; no objdump or producer map."""
    _need(len(raw) >= 64 and raw[:7] == b"\x7fELF\x02\x01\x01", "ELF64 little endian")
    header = struct.unpack_from("<HHIQQQIHHHHHH", raw, 16)
    kind, machine, version, _, phoff, _, _, ehsize, phsize, phnum, _, _, _ = header
    _need(kind == 3 and machine == 62 and version == 1 and ehsize == 64 and
          phsize == 56 and 0 < phnum <= 4096, "ELF x86-64 shared library header")
    _need(phoff >= 64 and phoff + phsize * phnum <= len(raw), "ELF program headers bounds")
    loads, build_ids = [], []
    for i in range(phnum):
        ptype, flags, offset, vaddr, _, filesz, memsz, _ = struct.unpack_from("<IIQQQQQQ", raw, phoff + i * phsize)
        _need(offset + filesz <= len(raw), "ELF segment file bounds")
        if ptype == 1:
            _need(filesz <= memsz and vaddr + memsz <= 1 << 64, "ELF load segment bounds")
            loads.append((offset, vaddr, filesz, flags))
        elif ptype == 4:
            end = offset + filesz
            cursor = offset
            while cursor < end:
                _need(cursor + 12 <= end, "ELF note header bounds")
                namesz, descsz, note_type = struct.unpack_from("<III", raw, cursor)
                name_at = cursor + 12
                desc_at = name_at + ((namesz + 3) & ~3)
                next_at = desc_at + ((descsz + 3) & ~3)
                _need(next_at <= end, "ELF note body bounds")
                if raw[name_at:name_at + namesz] == b"GNU\0" and note_type == 3:
                    _need(0 < descsz <= 64, "ELF GNU Build ID length")
                    build_ids.append(raw[desc_at:desc_at + descsz].hex())
                cursor = next_at
    _need(len(set(build_ids)) == 1, "ELF missing or ambiguous GNU Build ID")
    return loads, build_ids[0]


def _effect_records(records, write):
    _need(type(records) is list, "memory records list")
    key = "after_hex" if write else "bytes_hex"
    for record in records:
        _keys(record, ("address", "size", key), "memory record")
        _address(record["address"], record["size"])
        _hex(record[key], record["size"], key)


def verify_trace(document, library_path, expected_domain):
    """Validate exact native trace with caller domain authenticated by authority.

    Read payloads are pre-state input evidence. All reads must be consumed
    exactly; store writes include unchanged bytes and do not imply CPU reads.
    Replay carries one shadow state; recorded posts never become arithmetic
    input, except explicitly undefined flag bits with a transparent mask receipt.
    """
    _keys(document, ("schema", "library", "load_base", "domain", "entry", "exit", "steps"), "document")
    _need(document["schema"] == "native-evex-trace-v1", "trace schema")
    _need(type(expected_domain) is dict and DOMAIN_KEYS <= set(expected_domain), "expected authority domain keys")
    _need(_typed_equal(document["domain"], expected_domain) and expected_domain["provenance_kind"] == "ACTUAL_GALA_CALL", "actual Gala caller domain binding")
    for name in ("source_sha256", "caller_module_sha256", "libc_sha256"):
        _hex(expected_domain[name], 32, name)
    for name in ("caller_elf_pc", "caller_return_pc", "caller_load_base", "destination"):
        _uint(expected_domain[name], 64, name)
    for name in ("caller_build_id", "libc_build_id", "caller_instruction_bytes"):
        value = expected_domain[name]
        _need(type(value) is str and len(value) > 0 and len(value) % 2 == 0, name + " nonempty hex")
        _hex(value, len(value) // 2, name)
    caller_code = expected_domain["caller_instruction_bytes"]
    _need(len(caller_code) == 10 and caller_code.startswith("e8"), "finite actual caller CALL rel32 form")
    _need(expected_domain["caller_return_pc"] == expected_domain["caller_load_base"] +
          expected_domain["caller_elf_pc"] + 5, "CALL fallthrough return seam")
    _need(type(expected_domain["caller_path"]) is str and expected_domain["caller_path"], "caller path")
    _need(type(expected_domain["length"]) is int and expected_domain["length"] == 16 and
          type(expected_domain["fill"]) is int and expected_domain["fill"] == 0, "only sixteen zero-fill bytes authorized")
    _address(expected_domain["destination"], 16)
    _need(expected_domain["destination"] & 0xFFF <= 0xFE0, "cross-page alternate route outside finite path")
    _keys(document["library"], ("sha256", "build_id"), "library")
    _need(document["library"] == {"sha256": expected_domain["libc_sha256"],
                                 "build_id": expected_domain["libc_build_id"]}, "pinned libc identity")
    try:
        raw = Path(library_path).read_bytes()
    except (OSError, TypeError, ValueError) as error:
        raise Refused("library file unavailable") from error
    _need(sha256(raw).hexdigest() == document["library"]["sha256"], "actual library SHA256")
    loads, build_id = _elf(raw)
    _need(build_id == document["library"]["build_id"], "actual library GNU Build ID")
    for pc, code in PATH:
        size = len(code) // 2
        matches = [(offset + pc - vaddr) for offset, vaddr, filesz, flags in loads
                   if flags & 1 and vaddr <= pc and pc + size <= vaddr + filesz]
        _need(len(matches) == 1 and raw[matches[0]:matches[0] + size].hex() == code,
              "actual executable ELF instruction bytes")
    base = document["load_base"]
    _uint(base, 64, "load base")
    _context(document["entry"])
    _context(document["exit"])
    entry = document["entry"]["registers"]
    _need(entry["rip"] == base + PATH[0][0] and entry["rdi"] == expected_domain["destination"] and
          entry["rdx"] == 16 and entry["rsi"] & 255 == 0, "native entry/input binding")
    _need(type(document["steps"]) is list and len(document["steps"]) == 13, "exact thirteen instruction path")
    shadow = deepcopy(document["entry"])
    memory = {}
    undefined = []
    features = set()
    reads_count = writes_count = 0
    for index, (row, (pc, code)) in enumerate(zip(document["steps"], PATH)):
        _keys(row, ("elf_pc", "instruction_bytes", "before", "after", "reads", "writes"), "step")
        _need(type(row["elf_pc"]) is int and row["elf_pc"] == pc and row["instruction_bytes"] == code,
              "byte-bound path order")
        _context(row["before"])
        _context(row["after"])
        _need(row["before"] == shadow, "continuous derived pre-state")
        _effect_records(row["reads"], False)
        _effect_records(row["writes"], True)
        cursor = 0

        def read_memory(address, size):
            nonlocal cursor
            _need(cursor < len(row["reads"]), "missing required memory read")
            record = row["reads"][cursor]
            _need(record["address"] == address and record["size"] == size, "exact memory read address/width/order")
            data = bytes.fromhex(record["bytes_hex"])
            for lane, byte in enumerate(data):
                if address + lane in memory:
                    _need(memory[address + lane] == byte, "carried memory read continuity")
            cursor += 1
            return data

        result = derive_step(pc, code, shadow, read_memory, base)
        _need(cursor == len(row["reads"]) and row["reads"] == result["reads"], "unexpected/omitted CPU memory reads")
        _need(row["writes"] == result["writes"], "exact activated writes including unchanged bytes")
        derived = result["after"]
        mask = result["defined_flags_mask"]
        unknown = U32 ^ mask
        if unknown:
            undefined.append({"step": index, "mask": unknown})
            derived["registers"]["eflags"] = ((derived["registers"]["eflags"] & mask) |
                                                (row["after"]["registers"]["eflags"] & unknown))
        _need(row["after"] == derived, "independently derived complete post-state")
        for write in result["writes"]:
            for lane, byte in enumerate(bytes.fromhex(write["after_hex"])):
                memory[write["address"] + lane] = byte
        shadow = derived
        features.update(result["required_features"])
        reads_count += len(result["reads"])
        writes_count += len(result["writes"])
    _need(shadow == document["exit"] and shadow["registers"]["rip"] == expected_domain["caller_return_pc"],
          "return caller seam and complete exit")
    _need(shadow["registers"]["rax"] == expected_domain["destination"], "memset return destination")
    return {"verdict": "PASS", "scope": "FINITE_NATIVE_SEMANTICS_ONLY",
            "instruction_count": 13, "read_count": reads_count,
            "write_count": writes_count, "undefined_flags": undefined,
            "required_features": sorted(features), "library_sha256": sha256(raw).hexdigest(),
            "library_build_id": build_id}
