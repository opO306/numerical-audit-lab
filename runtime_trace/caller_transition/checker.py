"""Independent checker for the frozen regular one-step caller transition.

The checker does not import acquisition, producer, module-resolver, adapter,
legacy-checker, or Form-evaluator proof logic.  It resolves the three pinned
ELFs itself, decodes their instructions with GNU objdump, derives the observed
x86-64 write/control effects, and traverses the frozen IR data as data.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import struct
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


CAPTURE_SCHEMA = "gala-caller-transition-capture-v2"
ROW_SCHEMA = "gala-caller-transition-instruction-v2"
TRANSITION_SCHEMA = "gala-caller-transition-v2"
EXECUTION_SCHEMA = "caller-transition-execution-v2"
SEAL_SCHEMA = "caller-transition-acquisition-seal-v1"
IR_SCHEMA = "runtime-trace-numeric-ir-regular-1step-v1"
CORRESPONDENCE_SCHEMA = "numeric-ir-frozen-v2-regular-1step-v1"
REPORT_SCHEMA = "gala-caller-transition-independent-checker-v3"

SOURCE_RECEIPTS = {
    "runtime_trace/caller_transition/__init__.py": "3729bd7cadae1870f61c52ef8bdf8962f0ecbb596ac54cab3818767a4a4f7c96",
    "runtime_trace/caller_transition/frozen_modules/manifest.json": "060b4df8ca0506827016bf63859511a27864f7fd43d4322fdc2896324bdc28eb",
    "runtime_trace/caller_transition/gdb_acquire_reads.py": "00da02b2459289bfcba3635049f27f7d29324c261c7e174e144cea99acc3335b",
    "runtime_trace/caller_transition/module_resolver.py": "0593b66711df2820e57e647d129af601e7cef8dada1b1fac3b79e5439aed029a",
    "runtime_trace/caller_transition/read_effects.py": "5d595f6d520ecf0a7e48a01d254abf53d8ac356ad2133656f63c927550ece85a",
    "runtime_trace/caller_transition/run_acquisition_reads.py": "68e6c03358b526e92f0ff36261939781ad06cc9c70d2a5a972cbca35bde0f306",
    "runtime_trace/caller_transition/write_effects.py": "0917f62f2ae3f083d3c271522df2b6574023e476cfd24e29239b5e6017bb6b5e",
    "runtime_trace/caller_transition/write_effects_reads.py": "d051fbde85df19472ccc9403477adfcaebf7ca4561096cb72030bbb8926c908e",
    "runtime_trace/harness.py": "4928f88e4c6255cfbc3f68798648b543146fb5b13327490d331814f778a9fc26",
    "runtime_trace/harness_nsteps2.py": "a9125c7199a73e11dde7780ab833e44d444122b3c7c49e297ea1ea2155777c99",
    "runtime_trace/semantics.py": "d6797e279cdf2b85e91612426e4e2be3cac2fe2a837a4917fffa9530a5286331",
}
MODULE_SHA256S = {
    "3a15d66867d83762c7f2f1e37359cb8f6c5743edb369c65285cb0b1c4f7498bf",
    "a6ac98736304bb9f6a92e473bba45da10d9b5b99f8019e2ca15eb6a7f86234fc",
    "e50d468e8b0adfb05733f5b87b3cff34829c4a8c1aea50c865aa8bdfe4bb150f",
}
MODULE_LOAD_BASES = {
    "3a15d66867d83762c7f2f1e37359cb8f6c5743edb369c65285cb0b1c4f7498bf": 140737349943296,
    "a6ac98736304bb9f6a92e473bba45da10d9b5b99f8019e2ca15eb6a7f86234fc": 140736120496128,
    "e50d468e8b0adfb05733f5b87b3cff34829c4a8c1aea50c865aa8bdfe4bb150f": 0,
}
WHEEL_SHA256 = "cc5f0cf3bc63a966a3c130b93f6c05026271fe7178492a02c6266c243b5fc2f0"


@dataclass(frozen=True)
class TrustedCasePins:
    case: str
    label: str
    capture_directory: str
    transition_path: str
    transition_sha256: str
    seal_sha256: str
    capture_sha256: str
    execution_sha256: str
    trace_sha256: str
    trace_final_chain: str
    process_identity: dict[str, Any]
    sealed_files: dict[str, str]
    ir_path: str
    ir_sha256: str
    correspondence_path: str
    correspondence_sha256: str


def _case_pins(case: str, label: str, transition_sha256: str, seal_sha256: str,
               capture_sha256: str, execution_sha256: str, trace_sha256: str,
               final_chain: str, pid: int, start_ticks: int,
               sealed_files: dict[str, str], ir_path: str, ir_sha256: str,
               correspondence_path: str, correspondence_sha256: str) -> TrustedCasePins:
    return TrustedCasePins(
        case, label, f"runtime_trace/caller_transition/artifacts/{case}",
        f"runtime_trace/caller_transition/artifacts/producer-fix-round2/{case}/transition.json",
        transition_sha256, seal_sha256, capture_sha256, execution_sha256,
        trace_sha256, final_chain,
        {"linux_boot_id": "ad2a0c22-e8d1-466b-8bbf-31c2cf4f54cd", "pid": pid,
         "proc_stat_start_time_ticks": start_ticks}, sealed_files, ir_path,
        ir_sha256, correspondence_path, correspondence_sha256,
    )


_PRODUCTION_CASE_PINS = {
    "audited-attempt-05-readproof-01": _case_pins(
        "audited-attempt-05-readproof-01", "attempt-05",
        "526132b3ec1d1efcb06c05dd4ac803cd818074b63b47bec1a381ac38b4aa0f59",
        "ece7e1a54b681bea33c948a467eec9df2bf029cb7d386276fbc67c9819641627",
        "9ae29bee14c2d42265dbf353a1e55caa78012c16210fa7c5b6bf8e84cd8c9157",
        "f0b0fe461031a402bc2cdbfa962afde4846c29280a6d6ebb76222de2a15d1e62",
        "64f5f8caaf00cbd691ad24bdb8fa59fd6f50bbf4036d8671895fd27ac7766877",
        "547800c2b2c7a7374c779a25b5eada1131b4a5f70ea46beb977f637295770404", 394, 12881,
        {"caller_trace.jsonl":"64f5f8caaf00cbd691ad24bdb8fa59fd6f50bbf4036d8671895fd27ac7766877","capture.json":"9ae29bee14c2d42265dbf353a1e55caa78012c16210fa7c5b6bf8e84cd8c9157","execution.json":"f0b0fe461031a402bc2cdbfa962afde4846c29280a6d6ebb76222de2a15d1e62","first_step_disassembly.txt":"e1f03c4dcdc20aabe2496152914e549deebebbd39f2b119fed2e6e96c9cb0ed1","gdb.log":"91317a0faee26f0e66e080eb40ef23e9c9b26242d98818eae2f20b49c4a59ea5","harness_diff.json":"b71b84d1cdec37eb31cc6aca9af5f3cde3d9cb0863143cf5ba9f0bd938140f29","module_pinset.json":"0ceaf7fbfdfaae5edce9b912f3bc1af4f38058f2b8dea1f74b0d33893eee4387","source_pinset.json":"9c074226e62ee7ddb44744ac20fed0fd08bb74b62230bbf988a162bf779bf1ae"},
        "runtime_trace/numeric_ir/artifacts/attempt-05/numeric_ir.json", "bbb912c041cb47cf2f3814d416a298c3c6469c35a47c9b7cda629c11415586ba",
        "runtime_trace/numeric_ir/v2/artifacts/attempt-05/correspondence.json", "3edd42937e58c7655dc951d3683802ffddd5ae7cbfda27c5793d6cb42c7d35f3"),
    "fresh-closure-fresh-01-readproof-01": _case_pins(
        "fresh-closure-fresh-01-readproof-01", "closure-fresh-01",
        "01ca255ece2fef51fe4737deb42a005d6ea5ba39a2ed79c9f8eab66f9eac61f7",
        "7ca5c4be32793f54a52e5a5dd9089684e1f60a1d82f3984b014b7ea967df4d0e",
        "ebb9a05557a28a58afa8835d74e4f473048b2bcc554fc5e8f18c1fdb715ab185",
        "6f32d21122efeccb5f482bdfadd2b0b8c7b2682c75cd907e8505b0fc28569027",
        "0f195ce50ae247394bd95bda00a5de304e180752df69284405c80c112b4ad9b5",
        "f09a81a91e8cf866c900252d14569d384f4a421c5540df136d6228c67ccd1f73", 449, 13968,
        {"caller_trace.jsonl":"0f195ce50ae247394bd95bda00a5de304e180752df69284405c80c112b4ad9b5","capture.json":"ebb9a05557a28a58afa8835d74e4f473048b2bcc554fc5e8f18c1fdb715ab185","execution.json":"6f32d21122efeccb5f482bdfadd2b0b8c7b2682c75cd907e8505b0fc28569027","first_step_disassembly.txt":"e1f03c4dcdc20aabe2496152914e549deebebbd39f2b119fed2e6e96c9cb0ed1","gdb.log":"91b9c392a698ded4c4d4f7a6f4cdff2aa3ac3549c12fa650e43178b1901276f5","harness_diff.json":"b71b84d1cdec37eb31cc6aca9af5f3cde3d9cb0863143cf5ba9f0bd938140f29","module_pinset.json":"0ceaf7fbfdfaae5edce9b912f3bc1af4f38058f2b8dea1f74b0d33893eee4387","source_pinset.json":"9c074226e62ee7ddb44744ac20fed0fd08bb74b62230bbf988a162bf779bf1ae"},
        "runtime_trace/numeric_ir/artifacts/closure-fresh-01/numeric_ir.json", "c34576f87bd4abc5bdc5fc2f67e68251ec30d5659776ade984fd15ab2bcb5296",
        "runtime_trace/numeric_ir/v2/artifacts/closure-fresh-01/correspondence.json", "a692db2f6f3b5b9a45de71cf8516fef4c8d2cdc8b173c6cdb20259c5812c572f"),
}

ANTECEDENTS = {
    "attempt-05": (
        "runtime_trace/numeric_ir/artifacts/attempt-05/numeric_ir.json",
        "runtime_trace/numeric_ir/v2/artifacts/attempt-05/correspondence.json",
    ),
    "closure-fresh-01": (
        "runtime_trace/numeric_ir/artifacts/closure-fresh-01/numeric_ir.json",
        "runtime_trace/numeric_ir/v2/artifacts/closure-fresh-01/correspondence.json",
    ),
}
CARRY_LANES = (
    ("q", 0),
    ("q", 8),
    ("full_v", 0),
    ("full_v", 8),
    ("latent", 0),
    ("latent", 8),
)
ZERO_FORM = {
    "coef": ["0x0.0p+0", "0x0.0p+0", "0x0.0p+0", "0x0.0p+0"],
    "box": "0x0.0p+0",
}
GPRS = (
    "rax", "rbx", "rcx", "rdx", "rsi", "rdi", "rbp", "rsp", "r8",
    "r9", "r10", "r11", "r12", "r13", "r14", "r15", "rip",
)

ALIASES: dict[str, tuple[str, int]] = {
    "rax": ("rax", 64), "eax": ("rax", 32), "ax": ("rax", 16), "al": ("rax", 8),
    "rbx": ("rbx", 64), "ebx": ("rbx", 32), "bx": ("rbx", 16), "bl": ("rbx", 8),
    "rcx": ("rcx", 64), "ecx": ("rcx", 32), "cx": ("rcx", 16), "cl": ("rcx", 8),
    "rdx": ("rdx", 64), "edx": ("rdx", 32), "dx": ("rdx", 16), "dl": ("rdx", 8),
    "rsi": ("rsi", 64), "esi": ("rsi", 32), "si": ("rsi", 16), "sil": ("rsi", 8),
    "rdi": ("rdi", 64), "edi": ("rdi", 32), "di": ("rdi", 16), "dil": ("rdi", 8),
    "rbp": ("rbp", 64), "ebp": ("rbp", 32), "bp": ("rbp", 16), "bpl": ("rbp", 8),
    "rsp": ("rsp", 64), "esp": ("rsp", 32), "sp": ("rsp", 16), "spl": ("rsp", 8),
}
for _number in range(8, 16):
    ALIASES[f"r{_number}"] = (f"r{_number}", 64)
    ALIASES[f"r{_number}d"] = (f"r{_number}", 32)
    ALIASES[f"r{_number}w"] = (f"r{_number}", 16)
    ALIASES[f"r{_number}b"] = (f"r{_number}", 8)


class CheckerRefused(ValueError):
    """Fail-closed checker refusal with a stable category."""

    def __init__(self, code: str, reason: str):
        super().__init__(reason)
        self.code = code
        self.reason = reason


def _refuse(code: str, reason: str) -> None:
    raise CheckerRefused(code, reason)


def _require(condition: bool, code: str, reason: str) -> None:
    if not condition:
        _refuse(code, reason)


def _pairs_no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            _refuse("JSON_STRUCTURE", f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"), object_pairs_hook=_pairs_no_duplicates
        )
    except CheckerRefused:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        _refuse("JSON_STRUCTURE", f"cannot read {path}: {exc}")
    if not isinstance(value, dict):
        _refuse("JSON_STRUCTURE", f"top-level object required: {path}")
    return value


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            while block := stream.read(1024 * 1024):
                digest.update(block)
    except OSError as exc:
        _refuse("SOURCE_INTEGRITY", f"cannot hash {path}: {exc}")
    return digest.hexdigest()


def _integer(value: Any, code: str, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        _refuse(code, f"{field} must be an integer")
    return value


def _hex_int(value: Any, code: str, field: str) -> int:
    if not isinstance(value, str) or not re.fullmatch(r"0x[0-9a-f]+", value):
        _refuse(code, f"{field} must be lowercase hexadecimal")
    return int(value, 16)


def _bits(value: int, size: int) -> str:
    return f"0x{value & ((1 << (size * 8)) - 1):0{size * 2}x}"


def _split_operands(text: str) -> list[str]:
    result: list[str] = []
    depth = 0
    start = 0
    for index, char in enumerate(text):
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        elif char == "," and depth == 0:
            result.append(text[start:index].strip())
            start = index + 1
    tail = text[start:].strip()
    if tail:
        result.append(tail)
    return result


def _parse_assembly(assembly: str) -> tuple[str, list[str]]:
    clean = assembly.split("#", 1)[0].strip()
    clean = re.sub(r"\s+<.*$", "", clean)
    if not clean:
        _refuse("OBJDUMP_DECODE", "empty decoded assembly")
    parts = clean.split(None, 1)
    mnemonic = parts[0]
    rest = parts[1] if len(parts) == 2 else ""
    if mnemonic == "lock":
        locked = rest.split(None, 1)
        if not locked:
            _refuse("OBJDUMP_DECODE", "bare lock prefix")
        mnemonic = f"lock {locked[0]}"
        rest = locked[1] if len(locked) == 2 else ""
    return mnemonic, _split_operands(rest)


def _reg_value(context: dict[str, Any], operand: str) -> tuple[int, int]:
    name = operand.strip().lstrip("%")
    if name.startswith("xmm"):
        try:
            return int(context["xmm"][name], 16), 128
        except (KeyError, TypeError, ValueError):
            _refuse("TRACE_STATE", f"missing or malformed %{name}")
    if name not in ALIASES:
        _refuse("UNKNOWN_INSTRUCTION_EFFECT", f"unsupported register %{name}")
    canonical, width = ALIASES[name]
    try:
        value = int(context["gpr"][canonical], 16)
    except (KeyError, TypeError, ValueError):
        _refuse("TRACE_STATE", f"missing or malformed %{name}")
    return value & ((1 << width) - 1), width


_MEMORY = re.compile(
    r"^(?P<disp>[+-]?(?:0x[0-9a-f]+|[0-9]+))?"
    r"\((?P<base>%[a-z0-9]+)?(?:,(?P<index>%[a-z0-9]+)?(?:,(?P<scale>[1248]))?)?\)$"
)


def _is_memory_operand(operand: str) -> bool:
    value = operand.strip()
    return "(" in value or value.startswith(("%fs:", "%gs:"))


def _segment_base(row: dict[str, Any], segment: str) -> int:
    state = row.get("pre")
    bases = state.get("segment_bases") if isinstance(state, dict) else None
    _require(isinstance(bases, dict), "SEGMENT_BASE", "segment base state missing")
    return _hex_int(bases.get(f"{segment}_base"), "SEGMENT_BASE", f"{segment}_base")


def _effective_address(row: dict[str, Any], operand: str) -> int:
    value = operand.strip().removeprefix("*")
    segment = None
    if value.startswith(("%fs:", "%gs:")):
        segment, value = value[1:3], value[4:]
    if "(" not in value:
        try:
            address = int(value, 0)
        except ValueError:
            _refuse("UNKNOWN_INSTRUCTION_EFFECT", f"unsupported memory operand: {operand}")
        if address & (1 << 63):
            address -= 1 << 64
        base = 0 if segment is None else _segment_base(row, segment)
        return (base + address) & ((1 << 64) - 1)
    match = _MEMORY.fullmatch(value)
    if match is None:
        _refuse("UNKNOWN_INSTRUCTION_EFFECT", f"unsupported memory operand: {operand}")
    displacement_text = match.group("disp")
    displacement = int(displacement_text, 0) if displacement_text else 0
    address = displacement
    base_name = match.group("base")
    if base_name:
        if base_name == "%rip":
            address += row["pc"] + len(bytes.fromhex(row["instruction_bytes"]))
        else:
            address += _reg_value(row["pre"], base_name)[0]
    index_name = match.group("index")
    if index_name:
        address += _reg_value(row["pre"], index_name)[0] * int(match.group("scale") or "1")
    if segment is not None:
        address += _segment_base(row, segment)
    return address & ((1 << 64) - 1)


def _source_value(row: dict[str, Any], operand: str, size: int) -> int | None:
    operand = operand.strip()
    if operand.startswith("$"):
        return int(operand[1:], 0) & ((1 << (size * 8)) - 1)
    if _is_memory_operand(operand):
        wanted = operand.strip().removeprefix("*")
        matches = [item for item in row.get("pre_memory_observations", [])
                   if str(item.get("operand", "")).removeprefix("*") == wanted
                   and item.get("size") == size and item.get("status") == "OK"]
        _require(len(matches) == 1, "MEMORY_SOURCE", f"missing/duplicate memory source at sequence {row.get('sequence')}: {operand}")
        try:
            raw = bytes.fromhex(matches[0]["bytes_hex"])
        except (KeyError, TypeError, ValueError):
            _refuse("MEMORY_SOURCE", f"malformed memory source at sequence {row.get('sequence')}")
        _require(len(raw) == size, "MEMORY_SOURCE", f"memory source width mismatch at sequence {row.get('sequence')}")
        return int.from_bytes(raw, "little")
    if operand.startswith("%"):
        return _reg_value(row["pre"], operand)[0] & ((1 << (size * 8)) - 1)
    _refuse("UNKNOWN_INSTRUCTION_EFFECT", f"unsupported source operand: {operand}")


def _write_size(mnemonic: str, source: str) -> int:
    base = mnemonic.removeprefix("lock ")
    fixed = {
        "movsd": 8, "vmovdqu": 16, "movdqu": 16, "movl": 4, "movq": 8,
        "addl": 4, "subl": 4, "andb": 1, "cmpxchg": 4, "setne": 1,
        "vmovd": 4,
    }
    if base in fixed:
        return fixed[base]
    suffixes = {"b": 1, "w": 2, "l": 4, "q": 8}
    if base and base[-1] in suffixes:
        return suffixes[base[-1]]
    if source.startswith("%"):
        name = source.lstrip("%")
        if name.startswith("xmm"):
            return 16
        if name in ALIASES:
            return ALIASES[name][1] // 8
    _refuse("UNKNOWN_INSTRUCTION_EFFECT", f"cannot derive write width for {mnemonic}")


def derive_possible_write_effects(row: dict, decoded_assembly: str) -> list[dict]:
    """Derive possible writes, refusing unknown instruction effects."""

    mnemonic, operands = _parse_assembly(decoded_assembly)
    base = mnemonic.removeprefix("lock ")
    pre_rsp = _reg_value(row["pre"], "%rsp")[0]
    length = len(bytes.fromhex(row["instruction_bytes"]))
    if base == "call":
        return [{
            "address": (pre_rsp - 8) & ((1 << 64) - 1),
            "size": 8,
            "kind": "CALL_STACK",
            "expected_after_bits": _bits(row["pc"] + length, 8),
        }]
    if base == "push":
        _require(len(operands) == 1, "UNKNOWN_INSTRUCTION_EFFECT", "push operand count")
        value = _source_value(row, operands[0], 8)
        effect: dict[str, Any] = {
            "address": (pre_rsp - 8) & ((1 << 64) - 1),
            "size": 8,
            "kind": "PUSH_STACK",
        }
        if value is not None:
            effect["expected_after_bits"] = _bits(value, 8)
        return [effect]

    explicit_writers = {
        "mov", "movb", "movw", "movl", "movq", "movsd", "vmovd", "vmovdqu",
        "movdqu", "add", "addb", "addw", "addl", "addq", "sub", "subb",
        "subw", "subl", "subq", "and", "andb", "andw", "andl", "andq",
        "or", "orb", "orw", "orl", "orq", "xor", "xorb", "xorw", "xorl",
        "xorq", "shl", "shlb", "shlw", "shll", "shlq", "shr", "shrb",
        "shrw", "shrl", "shrq", "xchg", "cmpxchg", "setne",
    }
    read_only = {
        "cmp", "cmpb", "cmpw", "cmpl", "cmpq", "test", "testb", "testw",
        "testl", "testq", "lea", "movzbl", "vpbroadcastb",
    }
    control_or_stack_read = {
        "ret", "pop", "leave", "endbr64", "nop", "nopw", "ja", "jb", "jbe",
        "je", "jge", "jle", "jmp", "jne",
    }
    if base in control_or_stack_read and base != "pop":
        return []
    if base == "pop" and operands and "(" not in operands[-1]:
        return []
    memory_destination = bool(operands and _is_memory_operand(operands[-1]))
    if memory_destination:
        if base not in explicit_writers:
            if base in read_only:
                return []
            _refuse(
                "UNKNOWN_INSTRUCTION_EFFECT",
                f"unknown memory-destination effect at sequence {row.get('sequence')}: {decoded_assembly}",
            )
        source = operands[0] if len(operands) > 1 else ""
        size = _write_size(mnemonic, source)
        effect = {
            "address": _effective_address(row, operands[-1]),
            "size": size,
            "kind": "EXPLICIT",
        }
        mask = (1 << (size * 8)) - 1
        source_value = _source_value(row, source, size) if source else None
        before: int | None = None
        observations = [item for item in row.get("pre_memory_observations", [])
                        if str(item.get("operand", "")).removeprefix("*") == operands[-1].removeprefix("*")
                        and item.get("size") == size and item.get("status") == "OK"]
        if observations:
            _require(len(observations) == 1, "MEMORY_SOURCE", f"duplicate destination read at sequence {row.get('sequence')}")
            raw = bytes.fromhex(observations[0]["bytes_hex"])
            _require(len(raw) == size, "MEMORY_SOURCE", f"destination read width mismatch at sequence {row.get('sequence')}")
            before = int.from_bytes(raw, "little")
        if base.startswith(("mov", "vmov")):
            if source_value is not None:
                effect["expected_after_bits"] = _bits(source_value, size)
        elif base == "setne":
            flags = _integer(row["pre"].get("eflags"), "TRACE_STATE", "eflags")
            effect["expected_after_bits"] = _bits(0 if flags & 0x40 else 1, 1)
        elif base in {"xchg", "cmpxchg"}:
            if source_value is not None and before is not None:
                if base == "xchg":
                    after = source_value
                else:
                    after = source_value if (_reg_value(row["pre"], "%eax")[0] & mask) == before else before
                effect["expected_after_bits"] = _bits(after, size)
        elif before is not None and source_value is not None:
            if base.startswith("add"):
                after = before + source_value
            elif base.startswith("sub"):
                after = before - source_value
            elif base.startswith("and"):
                after = before & source_value
            elif base.startswith("or"):
                after = before | source_value
            elif base.startswith("xor"):
                after = before ^ source_value
            elif base.startswith("shl"):
                after = before << (source_value & 0x3F)
            elif base.startswith("shr"):
                after = before >> (source_value & 0x3F)
            else:
                _refuse("UNKNOWN_INSTRUCTION_EFFECT", f"unsupported RMW effect: {mnemonic}")
            effect["expected_after_bits"] = _bits(after & mask, size)
        return [effect]
    if base in explicit_writers | read_only | control_or_stack_read:
        return []
    if any(_is_memory_operand(operand) for operand in operands):
        _refuse("UNKNOWN_INSTRUCTION_EFFECT", f"unknown memory effect: {decoded_assembly}")
    _refuse("UNKNOWN_INSTRUCTION_EFFECT", f"unsupported decoded instruction: {decoded_assembly}")


def _elf_segments(path: Path) -> list[dict[str, int]]:
    try:
        data = path.read_bytes()
    except OSError as exc:
        _refuse("ELF_INTEGRITY", f"cannot read ELF {path}: {exc}")
    if len(data) < 64 or data[:4] != b"\x7fELF" or data[4] != 2 or data[5] != 1:
        _refuse("ELF_INTEGRITY", f"ELF64 little-endian required: {path}")
    try:
        header = struct.unpack_from("<16sHHIQQQIHHHHHH", data, 0)
    except struct.error as exc:
        _refuse("ELF_INTEGRITY", f"truncated ELF header: {exc}")
    phoff, phentsize, phnum = header[5], header[9], header[10]
    _require(phentsize >= 56 and phoff + phentsize * phnum <= len(data), "ELF_INTEGRITY", "invalid program header table")
    segments: list[dict[str, int]] = []
    for index in range(phnum):
        p_type, flags, offset, vaddr, _paddr, filesz, memsz, _align = struct.unpack_from(
            "<IIQQQQQQ", data, phoff + index * phentsize
        )
        if p_type == 1:
            _require(offset + filesz <= len(data), "ELF_INTEGRITY", "PT_LOAD exceeds file")
            segments.append({
                "file_offset": offset, "vaddr": vaddr, "filesz": filesz,
                "memsz": memsz, "flags": flags,
            })
    _require(bool(segments), "ELF_INTEGRITY", f"ELF has no PT_LOAD: {path}")
    return segments


def _file_offset(segments: list[dict[str, int]], address: int) -> tuple[int, int]:
    matches = [segment for segment in segments if segment["vaddr"] <= address < segment["vaddr"] + segment["filesz"]]
    _require(len(matches) == 1, "ELF_INTEGRITY", f"ELF address has {len(matches)} file mappings")
    segment = matches[0]
    return segment["file_offset"] + address - segment["vaddr"], segment["flags"]


_OBJDUMP_CACHE: dict[tuple[str, tuple[int, ...], str], dict[int, tuple[str, str]]] = {}


def _objdump_decode(path: Path, sha256: str, addresses: Iterable[int], executable: str) -> dict[int, tuple[str, str]]:
    wanted = tuple(sorted(set(addresses)))
    key = (sha256, wanted, executable)
    if key in _OBJDUMP_CACHE:
        return _OBJDUMP_CACHE[key]
    groups: list[list[int]] = []
    for address in wanted:
        if not groups or address - groups[-1][-1] > 4096:
            groups.append([address])
        else:
            groups[-1].append(address)
    decoded: dict[int, tuple[str, str]] = {}
    line_pattern = re.compile(r"^\s*([0-9a-f]+):\s+((?:[0-9a-f]{2}(?:\s+|$))+)(.*?)\s*$")
    for group in groups:
        command = [
            executable, "-d", "--insn-width=16", f"--start-address=0x{group[0]:x}",
            f"--stop-address=0x{group[-1] + 16:x}", str(path),
        ]
        try:
            completed = subprocess.run(command, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        except OSError as exc:
            _refuse("OBJDUMP_UNAVAILABLE", f"cannot execute {executable}: {exc}")
        _require(completed.returncode == 0, "OBJDUMP_DECODE", f"objdump failed: {completed.stderr.strip()}")
        for line in completed.stdout.splitlines():
            match = line_pattern.match(line)
            if match:
                address = int(match.group(1), 16)
                byte_text = "".join(match.group(2).split())
                assembly = match.group(3).strip()
                if assembly and not assembly.startswith(".byte"):
                    decoded[address] = (byte_text, assembly)
    missing = sorted(set(wanted) - set(decoded))
    _require(not missing, "OBJDUMP_DECODE", f"objdump did not decode addresses: {missing[:4]}")
    result = {address: decoded[address] for address in wanted}
    _OBJDUMP_CACHE[key] = result
    return result


def _validate_recorded_decode(
    recorded: Any, decoded: str, load_base: int, sequence: int
) -> None:
    _require(isinstance(recorded, str), "OBJDUMP_DECODE", f"recorded assembly missing at sequence {sequence}")
    recorded_mnemonic, recorded_operands = _parse_assembly(recorded)
    decoded_mnemonic, decoded_operands = _parse_assembly(decoded)
    _require(recorded_mnemonic == decoded_mnemonic, "OBJDUMP_DECODE", f"mnemonic mismatch at sequence {sequence}")
    control = recorded_mnemonic in {"call", "jmp", "ja", "jb", "jbe", "je", "jge", "jle", "jne"}
    if control and recorded_operands and decoded_operands and not decoded_operands[0].startswith("*"):
        recorded_match = re.fullmatch(r"(?:0x)?([0-9a-f]+)", recorded_operands[0])
        decoded_match = re.fullmatch(r"(?:0x)?([0-9a-f]+)", decoded_operands[0])
        _require(recorded_match is not None and decoded_match is not None, "OBJDUMP_DECODE", f"direct target parse failure at sequence {sequence}")
        _require(int(recorded_match.group(1), 16) == load_base + int(decoded_match.group(1), 16), "OBJDUMP_DECODE", f"direct target mismatch at sequence {sequence}")
        _require(recorded_operands[1:] == decoded_operands[1:], "OBJDUMP_DECODE", f"control operand mismatch at sequence {sequence}")
    else:
        _require(recorded_operands == decoded_operands, "OBJDUMP_DECODE", f"operand mismatch at sequence {sequence}")


def _resolve_modules(
    root: Path, capture: dict[str, Any], rows: list[dict[str, Any]], objdump: str
) -> tuple[dict[str, tuple[Path, list[dict[str, int]], int]], dict[int, str]]:
    manifest_path = root / "runtime_trace" / "caller_transition" / "frozen_modules" / "manifest.json"
    manifest = _load_json(manifest_path)
    _require(manifest.get("schema") == "caller-transition-module-resolver-v1", "ELF_INTEGRITY", "wrong module manifest schema")
    entries = manifest.get("modules")
    capture_modules = capture.get("modules")
    _require(isinstance(entries, dict) and isinstance(capture_modules, dict), "ELF_INTEGRITY", "module table missing")
    by_sha: dict[str, dict[str, Any]] = {}
    for captured_path, metadata in capture_modules.items():
        _require(isinstance(metadata, dict) and metadata.get("captured_path") == captured_path, "ELF_INTEGRITY", "captured module metadata mismatch")
        sha = metadata.get("sha256")
        _require(isinstance(sha, str) and sha not in by_sha, "ELF_INTEGRITY", "duplicate or invalid module SHA")
        by_sha[sha] = metadata
    used = {row.get("module_sha256") for row in rows}
    _require(all(isinstance(value, str) for value in used), "ELF_INTEGRITY", "row module SHA missing")
    _require(set(by_sha) == MODULE_SHA256S and used <= MODULE_SHA256S and set(entries) == MODULE_SHA256S,
             "MODULE_SET", "module set differs from literal three-module pin")
    resolved: dict[str, tuple[Path, list[dict[str, int]], int]] = {}
    decoded_by_sequence: dict[int, str] = {}
    for sha in sorted(used):
        _require(sha in entries and sha in by_sha, "ELF_INTEGRITY", f"unregistered module {sha}")
        relative = entries[sha]
        _require(isinstance(relative, str), "ELF_INTEGRITY", f"bad resolver path for {sha}")
        path = (manifest_path.parent / relative).resolve()
        _require(path.is_file() and _sha_file(path) == sha, "ELF_INTEGRITY", f"pinned ELF mismatch {sha}")
        segments = _elf_segments(path)
        metadata = by_sha[sha]
        _require(metadata.get("segments") == segments, "ELF_INTEGRITY", f"ELF segment receipt mismatch {sha}")
        load_base = _integer(metadata.get("load_base"), "ELF_INTEGRITY", "load_base")
        module_rows = [row for row in rows if row.get("module_sha256") == sha]
        decoded = _objdump_decode(path, sha, (row["elf_address"] for row in module_rows), objdump)
        elf_bytes = path.read_bytes()
        for row in module_rows:
            sequence = row["sequence"]
            address = _integer(row.get("elf_address"), "ELF_INTEGRITY", "elf_address")
            offset, flags = _file_offset(segments, address)
            recorded_bytes = row.get("instruction_bytes")
            _require(isinstance(recorded_bytes, str) and re.fullmatch(r"(?:[0-9a-f]{2})+", recorded_bytes) is not None, "ELF_INTEGRITY", f"bad instruction bytes at sequence {sequence}")
            decoded_bytes, assembly = decoded[address]
            _require(decoded_bytes == recorded_bytes, "OBJDUMP_DECODE", f"objdump byte mismatch at sequence {sequence}")
            _validate_recorded_decode(row.get("assembly"), assembly, load_base, sequence)
            width = len(bytes.fromhex(recorded_bytes))
            _require(elf_bytes[offset : offset + width].hex() == recorded_bytes, "ELF_INTEGRITY", f"ELF byte mismatch at sequence {sequence}")
            _require(row.get("file_offset") == offset, "ELF_INTEGRITY", f"file offset mismatch at sequence {sequence}")
            _require(flags & 1 == 1, "ELF_INTEGRITY", f"non-executable mapping at sequence {sequence}")
            _require(row.get("load_base") == load_base and row.get("pc") == load_base + address, "ELF_INTEGRITY", f"PC/load-base mismatch at sequence {sequence}")
            _require(row.get("captured_module_path") == metadata.get("captured_path"), "ELF_INTEGRITY", f"module path mismatch at sequence {sequence}")
            decoded_by_sequence[sequence] = assembly
        resolved[sha] = (path, segments, load_base)
    return resolved, decoded_by_sequence


def _direct_target(assembly: str, load_base: int) -> int | None:
    _mnemonic, operands = _parse_assembly(assembly)
    if not operands or operands[0].startswith("*"):
        return None
    match = re.match(r"^(?:0x)?([0-9a-f]+)$", operands[0])
    return None if match is None else load_base + int(match.group(1), 16)


def _expected_observations(row: dict[str, Any], assembly: str) -> list[tuple[str, str, int]]:
    mnemonic, operands = _parse_assembly(assembly)
    base = mnemonic.removeprefix("lock ")
    if base == "ret":
        expected = [("IMPLICIT_RET", "(%rsp)", 8)]
    elif base == "pop":
        expected = [("IMPLICIT_POP", "(%rsp)", 8)]
    elif base == "leave":
        expected = [("IMPLICIT_LEAVE", "(%rbp)", 8)]
    else:
        expected = []
        for index, operand in enumerate(operands):
            if not _is_memory_operand(operand):
                continue
            destination = index == len(operands) - 1
            pure_store = destination and base.startswith(("mov", "vmov"))
            if base in {"lea", "nop", "nopw"} or pure_store:
                continue
            if base in {"jmp", "call"} and operand.startswith("*"):
                kind, size = "INDIRECT_CONTROL", 8
            elif base == "push":
                kind, size = "EXPLICIT", 8
            elif destination and base not in {"cmp", "cmpb", "cmpw", "cmpl", "cmpq", "test", "testb", "testw", "testl", "testq"}:
                kind, size = "READ_MODIFY_WRITE", _operand_width(base, operands) // 8
            else:
                kind, size = "EXPLICIT", _operand_width(base, operands) // 8
            expected.append((kind, operand, size))
    if row["sequence"] == 727:
        expected.append(("ABI_STACK_ARGUMENT", "(%rsp)", 8))
    return expected


def _validate_memory_observations(rows: list[dict[str, Any]], decoded: dict[int, str]) -> dict[str, int]:
    shadow: dict[int, int] = {}
    count = 0
    for row in rows:
        _require(row["pre"].get("segment_bases") == row["post"].get("segment_bases"),
                 "SEGMENT_BASE", f"segment base changed at sequence {row['sequence']}")
        bases = row["pre"].get("segment_bases")
        _require(isinstance(bases, dict) and set(bases) == {"fs_base", "gs_base"},
                 "SEGMENT_BASE", f"missing FS/GS bases at sequence {row['sequence']}")
        observations = row.get("pre_memory_observations")
        _require(isinstance(observations, list), "MEMORY_OBSERVATION", "observation list missing")
        expected_observations = _expected_observations(row, decoded[row["sequence"]])
        actual_observations = [(item.get("kind"), item.get("operand"), item.get("size")) for item in observations]
        _require(actual_observations == expected_observations, "MEMORY_OBSERVATION",
                 f"read observation set mismatch at sequence {row['sequence']}")
        for observation in observations:
            count += 1
            _require(isinstance(observation, dict) and observation.get("status") == "OK"
                     and observation.get("timing") == "PRE_INSTRUCTION",
                     "MEMORY_OBSERVATION", f"failed/non-pre observation at sequence {row['sequence']}")
            size = _integer(observation.get("size"), "MEMORY_OBSERVATION", "observation size")
            operand = observation.get("operand")
            _require(isinstance(operand, str) and observation.get("address") == _effective_address(row, operand),
                     "MEMORY_OBSERVATION", f"observation address mismatch at sequence {row['sequence']}")
            try:
                raw = bytes.fromhex(observation.get("bytes_hex", ""))
            except (TypeError, ValueError):
                _refuse("MEMORY_OBSERVATION", f"bad observation bytes at sequence {row['sequence']}")
            _require(len(raw) == size, "MEMORY_OBSERVATION", f"observation width mismatch at sequence {row['sequence']}")
            address = observation["address"]
            for offset, byte in enumerate(raw):
                if address + offset in shadow:
                    _require(shadow[address + offset] == byte, "MEMORY_SHADOW", f"observed byte disagrees with prior write at sequence {row['sequence']}")
                shadow[address + offset] = byte
        for write in row.get("possible_memory_writes", []):
            address = _integer(write.get("address"), "WRITE_SET", "write address")
            size = _integer(write.get("size"), "WRITE_SET", "write size")
            try:
                before = int(write["before_bits"], 16).to_bytes(size, "little")
                after = int(write["after_bits"], 16).to_bytes(size, "little")
            except (KeyError, TypeError, ValueError, OverflowError):
                _refuse("WRITE_SET", f"malformed write bytes at sequence {row['sequence']}")
            for offset, byte in enumerate(before):
                if address + offset in shadow:
                    _require(shadow[address + offset] == byte, "MEMORY_SHADOW", f"write preimage disagrees with shadow at sequence {row['sequence']}")
            for offset, byte in enumerate(after):
                shadow[address + offset] = byte
    return {"count": count, "rooted_bytes": len(shadow)}


def _validate_sequence_receipts(
    capture: dict[str, Any], transition: dict[str, Any], rows: list[dict[str, Any]]
) -> None:
    """Reject stale sequence/count wrappers before instruction semantics."""
    count = len(rows)
    _require(capture.get("record_count") == count, "SEQUENCE_RECEIPT", "capture record_count is stale")
    capture_counts = capture.get("counts")
    readproof = transition.get("readproof")
    transition_capture = transition.get("capture")
    _require(isinstance(capture_counts, dict) and capture_counts.get("rows") == count,
             "SEQUENCE_RECEIPT", "capture row count is stale")
    _require(isinstance(readproof, dict) and readproof.get("rows") == count,
             "SEQUENCE_RECEIPT", "transition readproof row count is stale")
    _require(isinstance(transition_capture, dict) and transition_capture.get("record_count") == count,
             "SEQUENCE_RECEIPT", "transition capture record_count is stale")

    actual_counts = {
        "pre_memory_observations": sum(len(row.get("pre_memory_observations", [])) for row in rows),
        "pre_memory_observation_failures": sum(
            observation.get("status") != "OK"
            for row in rows for observation in row.get("pre_memory_observations", [])
        ),
        "possible_memory_writes": sum(len(row.get("possible_memory_writes", [])) for row in rows),
        "same_value_writes": sum(
            write.get("value_changed") is False
            for row in rows for write in row.get("possible_memory_writes", [])
        ),
        "indirect_memory_controls": sum(
            _parse_assembly(row.get("assembly", ""))[0] in {"jmp", "call"}
            and bool(_parse_assembly(row.get("assembly", ""))[1])
            and _parse_assembly(row.get("assembly", ""))[1][0].startswith("*")
            for row in rows
        ),
        "returns": sum(_parse_assembly(row.get("assembly", ""))[0] == "ret" for row in rows),
        "pops": sum(_parse_assembly(row.get("assembly", ""))[0] == "pop" for row in rows),
        "leaves": sum(_parse_assembly(row.get("assembly", ""))[0] == "leave" for row in rows),
    }
    for key, value in actual_counts.items():
        _require(capture_counts.get(key) == value and readproof.get(key) == value,
                 "SEQUENCE_RECEIPT", f"stale {key} receipt")

    def sequence(number: Any, location: str) -> int:
        _require(isinstance(number, int) and 0 <= number < count,
                 "SEQUENCE_RECEIPT", f"out-of-range sequence at {location}: {number!r}")
        _require(rows[number].get("sequence") == number,
                 "SEQUENCE_RECEIPT", f"sequence does not select retained row at {location}")
        return number

    first_return = capture.get("first_step_return")
    _require(isinstance(first_return, dict), "SEQUENCE_RECEIPT", "first return receipt missing")
    sequence(first_return.get("instruction_sequence"), "capture.first_step_return")
    second_entry = capture.get("second_step_entry")
    sources = second_entry.get("argument_sources") if isinstance(second_entry, dict) else None
    _require(isinstance(sources, dict), "SEQUENCE_RECEIPT", "argument source receipts missing")
    for role in ("t", "dt"):
        receipt = sources.get(role)
        _require(isinstance(receipt, dict), "SEQUENCE_RECEIPT", f"{role} receipt missing")
        seq = sequence(receipt.get("instruction_sequence"), f"capture.argument_sources.{role}")
        _require(receipt.get("assembly") == rows[seq].get("assembly"),
                 "SEQUENCE_RECEIPT", f"{role} receipt selects wrong retained row")

    bindings = transition.get("bindings")
    _require(isinstance(bindings, dict), "SEQUENCE_RECEIPT", "transition bindings missing")
    for role, list_key in (("time", "source_instruction_sequences"), ("dt", "caller_change_sequences")):
        binding = bindings.get(role)
        _require(isinstance(binding, dict), "SEQUENCE_RECEIPT", f"{role} binding missing")
        receipt = binding.get("actual_source_receipt")
        _require(isinstance(receipt, dict), "SEQUENCE_RECEIPT", f"{role} source receipt missing")
        seq = sequence(receipt.get("instruction_sequence"), f"bindings.{role}.actual_source_receipt")
        declared = binding.get(list_key)
        _require(declared == [seq], "SEQUENCE_RECEIPT", f"{role} sequence list is stale")

    final_observations = readproof.get("final_abi_source_observations")
    _require(isinstance(final_observations, list), "SEQUENCE_RECEIPT", "final ABI observations missing")
    for index, item in enumerate(final_observations):
        _require(isinstance(item, dict), "SEQUENCE_RECEIPT", "malformed final ABI observation")
        sequence(item.get("sequence"), f"readproof.final_abi_source_observations[{index}]")

    write_set = transition.get("write_set")
    _require(isinstance(write_set, dict), "SEQUENCE_RECEIPT", "write-set receipt missing")
    for field in ("gradient_writes", "save_all_copy_candidates"):
        items = write_set.get(field)
        _require(isinstance(items, list), "SEQUENCE_RECEIPT", f"{field} receipt missing")
        for index, item in enumerate(items):
            _require(isinstance(item, dict), "SEQUENCE_RECEIPT", f"malformed {field} receipt")
            sequence(item.get("sequence"), f"write_set.{field}[{index}]")
    gradient = bindings.get("gradient")
    _require(isinstance(gradient, dict), "SEQUENCE_RECEIPT", "gradient binding missing")
    gradient_sequences = gradient.get("write_sequences")
    _require(isinstance(gradient_sequences, list), "SEQUENCE_RECEIPT", "gradient sequence list missing")
    for index, number in enumerate(gradient_sequences):
        sequence(number, f"bindings.gradient.write_sequences[{index}]")


def _condition_taken(mnemonic: str, eflags: int) -> bool:
    cf, zf, sf, of = bool(eflags & 1), bool(eflags & 0x40), bool(eflags & 0x80), bool(eflags & 0x800)
    return {"ja": not cf and not zf, "jb": cf, "jbe": cf or zf, "je": zf,
            "jne": not zf, "jge": sf == of, "jle": zf or sf != of}[mnemonic]


def _operand_width(mnemonic: str, operands: list[str]) -> int:
    base = mnemonic.removeprefix("lock ")
    special = {"movsd": 64, "vmovd": 32, "vmovdqu": 128, "movdqu": 128,
               "movzbl": 8, "setne": 8}
    if base in special:
        return special[base]
    if base.endswith(("b", "w", "l", "q")) and base not in {
        "mov", "add", "sub", "and", "or", "xor", "cmp", "test", "shl", "shr",
        "call", "jmp", "ret", "push", "pop",
    }:
        return {"b": 8, "w": 16, "l": 32, "q": 64}[base[-1]]
    for operand in reversed(operands):
        name = operand.strip().lstrip("%")
        if name in ALIASES:
            return ALIASES[name][1]
    _refuse("UNKNOWN_INSTRUCTION_EFFECT", f"cannot derive operand width: {mnemonic} {operands}")


def _set_register(state: dict[str, Any], operand: str, value: int) -> None:
    name = operand.strip().lstrip("%")
    if name.startswith("xmm"):
        state["xmm"][name] = _bits(value, 16)
        return
    _require(name in ALIASES, "UNKNOWN_INSTRUCTION_EFFECT", f"unsupported destination %{name}")
    canonical, width = ALIASES[name]
    mask = (1 << width) - 1
    old = int(state["gpr"][canonical], 16)
    if width == 32:
        result = value & mask
    else:
        result = (old & ~mask) | (value & mask)
    state["gpr"][canonical] = _bits(result, 8)


def _parity(value: int) -> bool:
    return (value & 0xFF).bit_count() % 2 == 0


def _flags_result(old: int, left: int, right: int, result: int, width: int, operation: str) -> int:
    mask = (1 << width) - 1
    sign = 1 << (width - 1)
    result &= mask
    flags = old & ~(1 | 4 | 16 | 64 | 128 | 0x800)
    if operation == "sub":
        cf = (left & mask) < (right & mask)
        of = bool(((left ^ right) & (left ^ result) & sign))
        af = bool((left ^ right ^ result) & 0x10)
    elif operation == "add":
        cf = (left & mask) + (right & mask) > mask
        of = bool((~(left ^ right) & (left ^ result) & sign))
        af = bool((left ^ right ^ result) & 0x10)
    else:
        cf = of = af = False
    return flags | cf | (_parity(result) << 2) | (af << 4) | ((result == 0) << 6) | (bool(result & sign) << 7) | (of << 11)


def _validate_register_semantics(rows: list[dict[str, Any]], decoded: dict[int, str]) -> None:
    for row in rows:
        sequence = row["sequence"]
        mnemonic, operands = _parse_assembly(decoded[sequence])
        base = mnemonic.removeprefix("lock ")
        expected = copy.deepcopy(row["pre"])
        expected["gpr"]["rip"] = _bits(row["next_pc"], 8)
        flag_mask = (1 << 64) - 1
        width = None
        if base in {"mov", "movb", "movw", "movl", "movq"} and len(operands) == 2 and operands[1].startswith("%") and not _is_memory_operand(operands[1]):
            width = _operand_width(base, operands)
            value = _source_value(row, operands[0], width // 8)
            _set_register(expected, operands[1], value)
        elif base == "movzbl" and len(operands) == 2:
            _set_register(expected, operands[1], _source_value(row, operands[0], 1))
        elif base == "lea" and len(operands) == 2:
            _set_register(expected, operands[1], _effective_address(row, operands[0]))
        elif base == "movsd" and len(operands) == 2 and operands[1].startswith("%xmm"):
            value = _source_value(row, operands[0], 8)
            if _is_memory_operand(operands[0]):
                _set_register(expected, operands[1], value)
            else:
                old = _reg_value(row["pre"], operands[1])[0]
                _set_register(expected, operands[1], (old & ~((1 << 64) - 1)) | value)
        elif base == "vmovd" and len(operands) == 2:
            _set_register(expected, operands[1], _source_value(row, operands[0], 4))
        elif base == "vpbroadcastb" and len(operands) == 2:
            byte = _source_value(row, operands[0], 1)
            _set_register(expected, operands[1], int.from_bytes(bytes([byte]) * 16, "little"))
        elif base == "pop":
            value = _source_value(row, "(%rsp)", 8)
            _set_register(expected, operands[0], value)
            expected["gpr"]["rsp"] = _bits(_reg_value(row["pre"], "%rsp")[0] + 8, 8)
        elif base == "leave":
            value = _source_value(row, "(%rbp)", 8)
            _set_register(expected, "%rbp", value)
            expected["gpr"]["rsp"] = _bits(_reg_value(row["pre"], "%rbp")[0] + 8, 8)
        elif base == "ret":
            expected["gpr"]["rsp"] = _bits(_reg_value(row["pre"], "%rsp")[0] + 8, 8)
        elif base in {"push", "call"}:
            expected["gpr"]["rsp"] = _bits(_reg_value(row["pre"], "%rsp")[0] - 8, 8)
        elif base in {"add", "addb", "addw", "addl", "addq", "sub", "subb", "subw", "subl", "subq",
                      "and", "andb", "andw", "andl", "andq", "or", "orb", "orw", "orl", "orq",
                      "xor", "xorb", "xorw", "xorl", "xorq"} and len(operands) == 2:
            width = _operand_width(base, operands)
            left = _source_value(row, operands[1], width // 8)
            right = _source_value(row, operands[0], width // 8)
            if base.startswith("add"): result, op = left + right, "add"
            elif base.startswith("sub"): result, op = left - right, "sub"
            elif base.startswith("and"): result, op = left & right, "logic"
            elif base.startswith("or"): result, op = left | right, "logic"
            else: result, op = left ^ right, "logic"
            if operands[1].startswith("%"):
                _set_register(expected, operands[1], result)
            expected["eflags"] = _flags_result(row["pre"]["eflags"], left, right, result, width, op)
            if op == "logic":
                flag_mask &= ~0x10
        elif base in {"cmp", "cmpb", "cmpw", "cmpl", "cmpq", "test", "testb", "testw", "testl", "testq"}:
            width = _operand_width(base, operands)
            left = _source_value(row, operands[1], width // 8)
            right = _source_value(row, operands[0], width // 8)
            if base.startswith("cmp"):
                result, op = left - right, "sub"
            else:
                result, op = left & right, "logic"
            expected["eflags"] = _flags_result(row["pre"]["eflags"], left, right, result, width, op)
            if op == "logic":
                flag_mask &= ~0x10
        elif base in {"shl", "shlb", "shlw", "shll", "shlq", "shr", "shrb", "shrw", "shrl", "shrq"}:
            width = _operand_width(base, operands)
            value = _source_value(row, operands[1], width // 8)
            count = _source_value(row, operands[0], 1) & (0x3F if width == 64 else 0x1F)
            if count:
                mask = (1 << width) - 1
                if base.startswith("shl"):
                    result = (value << count) & mask
                    cf = bool((value >> (width - count)) & 1)
                    of = bool((result >> (width - 1)) & 1) ^ cf if count == 1 else False
                else:
                    result = value >> count
                    cf = bool((value >> (count - 1)) & 1)
                    of = bool(value & (1 << (width - 1))) if count == 1 else False
                _set_register(expected, operands[1], result)
                flags = row["pre"]["eflags"] & ~(1 | 4 | 64 | 128 | 0x800)
                expected["eflags"] = flags | cf | (_parity(result) << 2) | ((result == 0) << 6) | (bool(result & (1 << (width - 1))) << 7) | (of << 11)
                flag_mask &= ~0x10
                if count != 1:
                    flag_mask &= ~0x800
        elif base == "setne":
            _set_register(expected, operands[0], 0 if row["pre"]["eflags"] & 0x40 else 1)
        elif base == "xchg" and _is_memory_operand(operands[1]):
            width = _operand_width(base, operands)
            _set_register(expected, operands[0], _source_value(row, operands[1], width // 8))
        elif base == "cmpxchg" and _is_memory_operand(operands[1]):
            width = _operand_width(base, operands)
            memory = _source_value(row, operands[1], width // 8)
            accumulator = _reg_value(row["pre"], "%eax" if width == 32 else "%rax")[0]
            result = accumulator - memory
            expected["eflags"] = _flags_result(row["pre"]["eflags"], accumulator, memory, result, width, "sub")
            if (accumulator & ((1 << width) - 1)) != memory:
                _set_register(expected, "%eax" if width == 32 else "%rax", memory)
        elif base in {"jmp", "ja", "jb", "jbe", "je", "jge", "jle", "jne", "endbr64", "nop", "nopw"}:
            pass
        elif (base in {"mov", "movb", "movw", "movl", "movq", "movsd", "vmovdqu", "movdqu"}
              and len(operands) == 2 and _is_memory_operand(operands[1])):
            pass
        else:
            _refuse("UNKNOWN_INSTRUCTION_EFFECT", f"unsupported register semantics at sequence {sequence}: {decoded[sequence]}")
        _require(expected["gpr"] == row["post"]["gpr"] and expected["xmm"] == row["post"]["xmm"],
                 "REGISTER_SEMANTICS", f"register result mismatch at sequence {sequence}")
        _require(((expected["eflags"] ^ row["post"]["eflags"]) & flag_mask) == 0,
                 "FLAG_SEMANTICS", f"defined flags mismatch at sequence {sequence}")
        _require(expected["mxcsr"] == row["post"]["mxcsr"] and expected["segment_bases"] == row["post"]["segment_bases"],
                 "REGISTER_SEMANTICS", f"control state mismatch at sequence {sequence}")


def _origin(kind: str, **fields: Any) -> dict[str, Any]:
    return {"kind": kind, **fields}


def _origin_has_role(value: Any, role: str) -> bool:
    if isinstance(value, dict):
        return value.get("role") == role or any(_origin_has_role(item, role) for item in value.values())
    if isinstance(value, list):
        return any(_origin_has_role(item, role) for item in value)
    return False


def _require_origin_role(value: dict[str, Any], role: str, location: str) -> None:
    _require(_origin_has_role(value, role), "ABI_PROVENANCE",
             f"{location} does not derive from authenticated {role} root")


def _compact_origins(origins: list[dict[str, Any]]) -> Any:
    unique: list[dict[str, Any]] = []
    for item in origins:
        if not any(item == prior for prior in unique):
            unique.append(item)
    return unique[0] if len(unique) == 1 else unique


def _origin_register(state: dict[str, Any], operand: str, width: int) -> dict[str, Any]:
    name = operand.strip().lstrip("%")
    if name.startswith("xmm"):
        lanes = state["xmm"][name]
        return lanes["low64"] if width <= 8 else _origin(
            "Copy", sequence=state["sequence"], source=[lanes["low64"], lanes["high64"]]
        )
    _require(name in ALIASES, "ABI_PROVENANCE", f"unsupported origin register %{name}")
    return state["gpr"][ALIASES[name][0]]


def _origin_memory_load(
    row: dict[str, Any], operand: str, width: int, memory: dict[int, dict[str, Any]]
) -> dict[str, Any]:
    address = _effective_address(row, operand)
    cells = [memory.get(address + offset) for offset in range(width)]
    _require(all(isinstance(cell, dict) for cell in cells), "ABI_PROVENANCE",
             f"origin memory gap at sequence {row['sequence']} address {address:#x}")
    return _origin(
        "Load", sequence=row["sequence"], address=address, width=width,
        memory_origin=_compact_origins([cell for cell in cells if isinstance(cell, dict)]),
    )


def _origin_source(
    row: dict[str, Any], operand: str, width: int, state: dict[str, Any],
    memory: dict[int, dict[str, Any]],
) -> dict[str, Any]:
    text = operand.strip().removeprefix("*")
    if text.startswith("$"):
        return _origin("InstructionResult", sequence=row["sequence"], opcode="immediate", literal=text)
    if text.startswith("%") and not _is_memory_operand(text):
        return _origin_register(state, text, width)
    if _is_memory_operand(text):
        return _origin_memory_load(row, text, width, memory)
    _refuse("ABI_PROVENANCE", f"unknown origin source at sequence {row['sequence']}: {operand}")


def _set_gpr_origin(
    state: dict[str, Any], operand: str, source: dict[str, Any], sequence: int, opcode: str
) -> None:
    name = operand.strip().lstrip("%")
    _require(name in ALIASES, "ABI_PROVENANCE", f"unsupported origin destination %{name}")
    canonical, width = ALIASES[name]
    if width in {8, 16}:
        source = _origin(
            "InstructionResult", sequence=sequence, opcode=f"{opcode}:partial-{width}",
            operand_origins=[state["gpr"][canonical], source],
        )
    state["gpr"][canonical] = source


def _memory_role_roots(
    capture: dict[str, Any], rows: list[dict[str, Any]]
) -> dict[tuple[int, int, bytes], str]:
    second = capture["second_step_entry"]["abi"]
    specifications = {
        718: ("time", int(second["t_bits"], 16), 8),
        721: ("gradient", second["pointers"]["gradient"], 8),
        722: ("cpotential", second["cpointer"], 8),
        723: ("dt", int(second["dt_bits"], 16), 8),
        724: ("half_ndim", second["half_ndim"], 4),
        725: ("n", second["n"], 8),
        726: ("full_v", second["pointers"]["full_v"], 8),
    }
    roots: dict[tuple[int, int, bytes], str] = {}
    for sequence, (role, expected, width) in specifications.items():
        _require(sequence < len(rows), "ABI_PROVENANCE", f"missing final ABI source row {sequence}")
        observations = rows[sequence].get("pre_memory_observations", [])
        _require(len(observations) == 1, "ABI_PROVENANCE", f"ambiguous final ABI source row {sequence}")
        observation = observations[0]
        address = _integer(observation.get("address"), "ABI_PROVENANCE", "source address")
        raw = bytes.fromhex(observation.get("bytes_hex", ""))
        _require(len(raw) == width and int.from_bytes(raw, "little") == expected,
                 "ABI_PROVENANCE", f"authenticated {role} source bits mismatch")
        roots[(address, width, raw)] = role
    return roots


def _validate_origin_semantics(
    case: str, capture: dict[str, Any], rows: list[dict[str, Any]], decoded: dict[int, str]
) -> dict[str, dict[str, Any]]:
    """Propagate origin expressions independently of producer provenance claims."""
    first = capture["first_step_entry"]["abi"]
    first_context = rows[0]["pre"]
    q_pointer = first["pointers"]["q"]
    latent_pointer = first["pointers"]["latent"]
    _require(_reg_value(first_context, "%r15")[0] == q_pointer,
             "ABI_PROVENANCE", "initial r15 is not authenticated q")
    _require(_reg_value(first_context, "%r14")[0] == latent_pointer,
             "ABI_PROVENANCE", "initial r14 is not authenticated latent")

    state: dict[str, Any] = {
        "sequence": 0,
        "gpr": {},
        "xmm": {},
        "eflags": _origin("AuthenticatedContext", case=case, boundary="first-return", field="eflags"),
        "mxcsr": _origin("AuthenticatedContext", case=case, boundary="first-return", field="mxcsr"),
    }
    for name in GPRS:
        role = "q" if name == "r15" else "latent" if name == "r14" else None
        state["gpr"][name] = _origin(
            "AuthenticatedContext", case=case, boundary="first-return", field=f"gpr.{name}",
            **({"role": role} if role else {}),
        )
    for name in first_context["xmm"]:
        state["xmm"][name] = {
            "low64": _origin("AuthenticatedContext", case=case, boundary="first-return", field=f"xmm.{name}.low64"),
            "high64": _origin("AuthenticatedContext", case=case, boundary="first-return", field=f"xmm.{name}.high64"),
        }

    role_roots = _memory_role_roots(capture, rows)
    memory: dict[int, dict[str, Any]] = {}
    final_state: dict[str, Any] | None = None
    final_stack_origin: dict[str, Any] | None = None

    for row in rows:
        sequence = row["sequence"]
        state["sequence"] = sequence
        mnemonic, operands = _parse_assembly(decoded[sequence])
        base = mnemonic.removeprefix("lock ")

        for observation in row.get("pre_memory_observations", []):
            address = observation["address"]
            raw = bytes.fromhex(observation["bytes_hex"])
            role = role_roots.get((address, len(raw), raw))
            root = _origin(
                "AuthenticatedMemoryRoot", case=case, address=address,
                captured_before_sequence=sequence, width=len(raw),
                **({"role": role} if role else {}),
            )
            for offset in range(len(raw)):
                memory.setdefault(address + offset, root)

        if sequence == rows[-1]["sequence"]:
            final_state = copy.deepcopy(state)
            rsp = _reg_value(row["pre"], "%rsp")[0]
            cells = [memory.get(rsp + offset) for offset in range(8)]
            _require(all(isinstance(cell, dict) for cell in cells), "ABI_PROVENANCE", "final stack origin missing")
            final_stack_origin = _compact_origins([cell for cell in cells if isinstance(cell, dict)])

        destination_register: str | None = None
        destination_origin: dict[str, Any] | None = None
        exchange_store_origin: dict[str, Any] | None = None
        width = _operand_width(base, operands) if operands and base not in {
            "call", "jmp", "ret", "push", "pop", "leave", "endbr64", "nop", "nopw",
            "ja", "jb", "jbe", "je", "jge", "jle", "jne",
        } else 0

        if base in {"mov", "movb", "movw", "movl", "movq", "movzbl"} and len(operands) == 2 and operands[1].startswith("%") and not _is_memory_operand(operands[1]):
            source_width = 1 if base == "movzbl" else width // 8
            destination_register = operands[1]
            destination_origin = _origin("Copy", sequence=sequence, source=_origin_source(row, operands[0], source_width, state, memory))
            _set_gpr_origin(state, destination_register, destination_origin, sequence, base)
        elif base == "lea" and len(operands) == 2:
            dependencies = []
            for register in re.findall(r"%([a-z0-9]+)", operands[0]):
                if register in ALIASES:
                    dependencies.append(state["gpr"][ALIASES[register][0]])
            destination_origin = _origin("InstructionResult", sequence=sequence, opcode="lea", operand_origins=dependencies)
            _set_gpr_origin(state, operands[1], destination_origin, sequence, base)
        elif base == "movsd" and len(operands) == 2 and operands[1].startswith("%xmm"):
            source = _origin_source(row, operands[0], 8, state, memory)
            destination = operands[1].lstrip("%")
            state["xmm"][destination]["low64"] = source if source.get("kind") == "Load" else _origin("Copy", sequence=sequence, source=source)
            if _is_memory_operand(operands[0]):
                state["xmm"][destination]["high64"] = _origin(
                    "InstructionResult", sequence=sequence, opcode="legacy-movsd-zero-upper", operand_origins=[]
                )
        elif base == "vmovd" and len(operands) == 2:
            source = _origin_source(row, operands[0], 4, state, memory)
            destination = operands[1].lstrip("%")
            state["xmm"][destination] = {
                "low64": _origin("InstructionResult", sequence=sequence, opcode="vmovd-low", operand_origins=[source]),
                "high64": _origin("InstructionResult", sequence=sequence, opcode="vmovd-zero-upper", operand_origins=[]),
            }
        elif base == "vpbroadcastb" and len(operands) == 2:
            source = _origin_source(row, operands[0], 1, state, memory)
            broadcast = _origin("InstructionResult", sequence=sequence, opcode="vpbroadcastb", operand_origins=[source])
            state["xmm"][operands[1].lstrip("%")] = {"low64": broadcast, "high64": broadcast}
        elif base == "pop":
            source = _origin_memory_load(row, "(%rsp)", 8, memory)
            _set_gpr_origin(state, operands[0], source, sequence, base)
            state["gpr"]["rsp"] = _origin("Arithmetic", sequence=sequence, opcode="pop-rsp", operand_origins=[state["gpr"]["rsp"]])
        elif base == "leave":
            source = _origin_memory_load(row, "(%rbp)", 8, memory)
            old_rbp = state["gpr"]["rbp"]
            state["gpr"]["rbp"] = source
            state["gpr"]["rsp"] = _origin("Arithmetic", sequence=sequence, opcode="leave-rsp", operand_origins=[old_rbp])
        elif base == "ret":
            state["gpr"]["rsp"] = _origin("Arithmetic", sequence=sequence, opcode="ret-rsp", operand_origins=[state["gpr"]["rsp"]])
        elif base in {"push", "call"}:
            state["gpr"]["rsp"] = _origin("Arithmetic", sequence=sequence, opcode=f"{base}-rsp", operand_origins=[state["gpr"]["rsp"]])
        elif base in {"add", "addb", "addw", "addl", "addq", "sub", "subb", "subw", "subl", "subq",
                      "and", "andb", "andw", "andl", "andq", "or", "orb", "orw", "orl", "orq",
                      "xor", "xorb", "xorw", "xorl", "xorq", "shl", "shlb", "shlw", "shll", "shlq",
                      "shr", "shrb", "shrw", "shrl", "shrq"} and len(operands) == 2:
            left = _origin_source(row, operands[1], width // 8, state, memory)
            right = _origin_source(row, operands[0], 1 if base.startswith(("shl", "shr")) else width // 8, state, memory)
            result = _origin("Arithmetic", sequence=sequence, opcode=base, operand_origins=[left, right])
            if operands[1].startswith("%"):
                _set_gpr_origin(state, operands[1], result, sequence, base)
            state["eflags"] = result
        elif base in {"cmp", "cmpb", "cmpw", "cmpl", "cmpq", "test", "testb", "testw", "testl", "testq"}:
            state["eflags"] = _origin(
                "Arithmetic", sequence=sequence, opcode=base,
                operand_origins=[
                    _origin_source(row, operands[1], width // 8, state, memory),
                    _origin_source(row, operands[0], width // 8, state, memory),
                ],
            )
        elif base == "setne":
            _set_gpr_origin(state, operands[0], _origin("InstructionResult", sequence=sequence, opcode="setne", operand_origins=[state["eflags"]]), sequence, base)
        elif base == "xchg" and _is_memory_operand(operands[1]):
            exchange_store_origin = _origin_source(row, operands[0], width // 8, state, memory)
            source = _origin_memory_load(row, operands[1], width // 8, memory)
            _set_gpr_origin(state, operands[0], source, sequence, base)
        elif base == "cmpxchg" and _is_memory_operand(operands[1]):
            memory_source = _origin_memory_load(row, operands[1], width // 8, memory)
            exchange_store_origin = _origin_source(row, operands[0], width // 8, state, memory)
            accumulator_name = "%eax" if width == 32 else "%rax"
            accumulator = _reg_value(row["pre"], accumulator_name)[0] & ((1 << width) - 1)
            memory_value = _source_value(row, operands[1], width // 8)
            state["eflags"] = _origin("Arithmetic", sequence=sequence, opcode="cmpxchg", operand_origins=[state["gpr"]["rax"], memory_source])
            if accumulator != memory_value:
                _set_gpr_origin(state, accumulator_name, memory_source, sequence, base)
        elif base in {"jmp", "ja", "jb", "jbe", "je", "jge", "jle", "jne", "endbr64", "nop", "nopw"}:
            pass
        elif base in {"mov", "movb", "movw", "movl", "movq", "movsd", "vmovdqu", "movdqu"} and len(operands) == 2 and _is_memory_operand(operands[1]):
            pass
        else:
            _refuse("ABI_PROVENANCE", f"unsupported origin semantics at sequence {sequence}: {decoded[sequence]}")

        for write in row.get("possible_memory_writes", []):
            address = write["address"]
            size = write["size"]
            if base == "push":
                source = _origin_source(row, operands[0], size, state, memory)
            elif base == "call":
                source = _origin("InstructionResult", sequence=sequence, opcode="call-return-address", operand_origins=[state["gpr"]["rip"]])
            elif base in {"mov", "movb", "movw", "movl", "movq", "movsd", "vmovdqu", "movdqu"}:
                source = _origin_source(row, operands[0], size, state, memory)
            elif base in {"add", "addb", "addw", "addl", "addq", "sub", "subb", "subw", "subl", "subq", "and", "andb", "andw", "andl", "andq"}:
                source = _origin("Arithmetic", sequence=sequence, opcode=base, operand_origins=[
                    _origin_memory_load(row, operands[1], size, memory),
                    _origin_source(row, operands[0], size, state, memory),
                ])
            elif base == "xchg":
                _require(exchange_store_origin is not None, "ABI_PROVENANCE", "xchg source origin absent")
                source = exchange_store_origin
            elif base == "cmpxchg":
                accumulator_name = "%eax" if size == 4 else "%rax"
                accumulator = _reg_value(row["pre"], accumulator_name)[0] & ((1 << (size * 8)) - 1)
                memory_value = _source_value(row, operands[1], size)
                _require(exchange_store_origin is not None, "ABI_PROVENANCE", "cmpxchg source origin absent")
                source = exchange_store_origin if accumulator == memory_value else _origin_memory_load(row, operands[1], size, memory)
            else:
                _refuse("ABI_PROVENANCE", f"unsupported write origin at sequence {sequence}: {decoded[sequence]}")
            stored = _origin("Store", sequence=sequence, address=address, source_origin=source)
            for offset in range(size):
                memory[address + offset] = stored

        control_operands: list[dict[str, Any]] = []
        if base == "ret":
            control_operands.append(_origin_memory_load(row, "(%rsp)", 8, memory))
        elif base in {"jmp", "call"} and operands and operands[0].startswith("*"):
            control_operands.append(_origin_source(row, operands[0], 8, state, memory))
        elif base in {"ja", "jb", "jbe", "je", "jge", "jle", "jne"}:
            control_operands.append(state["eflags"])
        state["gpr"]["rip"] = _origin("InstructionResult", sequence=sequence, opcode=f"control:{base}", operand_origins=control_operands)

    _require(final_state is not None and final_stack_origin is not None,
             "ABI_PROVENANCE", "final ABI origin snapshot absent")
    final = final_state
    chains = {
        "rcx_q": {"role": "q", "origin": final["gpr"]["rcx"]},
        "r8_full_v": {"role": "full_v", "origin": final["gpr"]["r8"]},
        "r9_latent": {"role": "latent", "origin": final["gpr"]["r9"]},
        "stack_gradient": {"role": "gradient", "origin": final_stack_origin},
        "xmm0_time": {"role": "time", "origin": final["xmm"]["xmm0"]["low64"]},
        "xmm1_dt": {"role": "dt", "origin": final["xmm"]["xmm1"]["low64"]},
        "rdi_cpotential": {"role": "cpotential", "origin": final["gpr"]["rdi"]},
        "rsi_n": {"role": "n", "origin": final["gpr"]["rsi"]},
        "rdx_half_ndim": {"role": "half_ndim", "origin": final["gpr"]["rdx"]},
    }
    expected_tops = {
        "rcx_q": ("Copy", 719), "r8_full_v": ("Copy", 726),
        "r9_latent": ("Copy", 720), "stack_gradient": ("Store", 721),
        "xmm0_time": ("Load", 718), "xmm1_dt": ("Load", 723),
        "rdi_cpotential": ("Copy", 722), "rsi_n": ("Copy", 725),
        "rdx_half_ndim": ("Copy", 724),
    }
    for name, item in chains.items():
        origin = item["origin"]
        kind, sequence = expected_tops[name]
        _require(origin.get("kind") == kind and origin.get("sequence") == sequence,
                 "ABI_PROVENANCE", f"{name} final origin shape mismatch")
        _require_origin_role(origin, item["role"], name)
    return chains


def _validate_control(rows: list[dict[str, Any]], decoded: dict[int, str], load_bases: dict[str, int]) -> None:
    conditional = {"ja", "jb", "jbe", "je", "jge", "jle", "jne"}
    for index, row in enumerate(rows):
        sequence = row["sequence"]
        assembly = decoded[sequence]
        mnemonic, operands = _parse_assembly(assembly)
        base = mnemonic.removeprefix("lock ")
        length = len(bytes.fromhex(row["instruction_bytes"]))
        fallthrough = row["pc"] + length
        next_pc = row["next_pc"]
        _require(row["pre"]["gpr"]["rip"] == _bits(row["pc"], 8), "TRACE_STATE", f"pre RIP mismatch at sequence {sequence}")
        _require(row["post"]["gpr"]["rip"] == _bits(next_pc, 8), "TRACE_STATE", f"post RIP mismatch at sequence {sequence}")
        target = _direct_target(assembly, load_bases[row["module_sha256"]])
        if base in conditional:
            _require(target is not None, "TRACE_CONTROL_TARGET", f"conditional target absent at sequence {sequence}")
            expected = target if _condition_taken(base, _integer(row["pre"].get("eflags"), "TRACE_STATE", "eflags")) else fallthrough
            _require(next_pc == expected, "TRACE_CONTROL_TARGET", f"conditional target mismatch at sequence {sequence}")
        elif base == "jmp":
            if target is None:
                _require(len(operands) == 1, "TRACE_CONTROL_TARGET", "indirect jump operand count")
                expected = _source_value(row, operands[0].removeprefix("*"), 8)
                _require(next_pc == expected, "TRACE_CONTROL_TARGET", f"indirect jump mismatch at sequence {sequence}")
            else:
                _require(next_pc == target, "TRACE_CONTROL_TARGET", f"direct jump mismatch at sequence {sequence}")
        elif base == "call":
            if target is None:
                _require(len(operands) == 1, "TRACE_CONTROL_TARGET", "indirect call operand count")
                expected = _source_value(row, operands[0].removeprefix("*"), 8)
                _require(next_pc == expected, "TRACE_CONTROL_TARGET", f"indirect call mismatch at sequence {sequence}")
            else:
                _require(next_pc == target, "TRACE_CONTROL_TARGET", f"direct call mismatch at sequence {sequence}")
            _require(_reg_value(row["post"], "%rsp")[0] == (_reg_value(row["pre"], "%rsp")[0] - 8) & ((1 << 64) - 1), "TRACE_CONTROL", f"call RSP mismatch at sequence {sequence}")
        elif base == "ret":
            expected = _source_value(row, "(%rsp)", 8)
            _require(next_pc == expected, "TRACE_CONTROL_TARGET", f"return target mismatch at sequence {sequence}")
            _require(_reg_value(row["post"], "%rsp")[0] == (_reg_value(row["pre"], "%rsp")[0] + 8) & ((1 << 64) - 1), "TRACE_CONTROL", f"ret RSP mismatch at sequence {sequence}")
        elif base == "push":
            _require(next_pc == fallthrough and _reg_value(row["post"], "%rsp")[0] == (_reg_value(row["pre"], "%rsp")[0] - 8) & ((1 << 64) - 1), "TRACE_CONTROL", f"push mismatch at sequence {sequence}")
        elif base == "pop":
            _require(next_pc == fallthrough and _reg_value(row["post"], "%rsp")[0] == (_reg_value(row["pre"], "%rsp")[0] + 8) & ((1 << 64) - 1), "TRACE_CONTROL", f"pop mismatch at sequence {sequence}")
        elif base == "leave":
            _require(next_pc == fallthrough and _reg_value(row["post"], "%rsp")[0] == (_reg_value(row["pre"], "%rbp")[0] + 8) & ((1 << 64) - 1), "TRACE_CONTROL", f"leave mismatch at sequence {sequence}")
        else:
            _require(next_pc == fallthrough, "TRACE_CONTROL_TARGET", f"sequential flow mismatch at sequence {sequence}")
        if index + 1 < len(rows):
            _require(next_pc == rows[index + 1]["pc"], "TRACE_FLOW", f"flow gap after sequence {sequence}")


def _validate_recorded_writes(rows: list[dict[str, Any]], decoded: dict[int, str]) -> list[dict[str, Any]]:
    flattened: list[dict[str, Any]] = []
    for row in rows:
        derived = derive_possible_write_effects(row, decoded[row["sequence"]])
        recorded = row.get("possible_memory_writes")
        _require(isinstance(recorded, list) and len(recorded) == len(derived), "WRITE_SET", f"write count mismatch at sequence {row['sequence']}")
        for actual, expected in zip(recorded, derived, strict=True):
            _require(isinstance(actual, dict), "WRITE_SET", "write record must be an object")
            for field in ("address", "size", "kind"):
                _require(actual.get(field) == expected[field], "WRITE_SET", f"{field} mismatch at sequence {row['sequence']}")
            size = expected["size"]
            before = actual.get("before_bits")
            after = actual.get("after_bits")
            _require(isinstance(before, str) and re.fullmatch(rf"0x[0-9a-f]{{{size * 2}}}", before) is not None, "WRITE_SET", f"bad before bits at sequence {row['sequence']}")
            _require(isinstance(after, str) and re.fullmatch(rf"0x[0-9a-f]{{{size * 2}}}", after) is not None, "WRITE_SET", f"bad after bits at sequence {row['sequence']}")
            if "expected_after_bits" in expected:
                _require(after == expected["expected_after_bits"], "WRITE_SET", f"stored value mismatch at sequence {row['sequence']}")
            _require(actual.get("value_changed") is (before != after), "WRITE_SET", f"value_changed mismatch at sequence {row['sequence']}")
            flattened.append({"sequence": row["sequence"], **actual})
    return flattened


def _overlaps(address: int, size: int, start: int, width: int) -> bool:
    return address < start + width and start < address + size


def _safe_source(root: Path, relative: Any, expected: str) -> Path:
    _require(relative == expected, "ANTECEDENT_IDENTITY", f"unexpected antecedent path: {relative}")
    path = (root / expected).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError:
        _refuse("ANTECEDENT_IDENTITY", f"antecedent path escapes root: {relative}")
    _require(path.is_file(), "SOURCE_INTEGRITY", f"missing antecedent source: {path}")
    return path


def _terminal_buffer_value(values: list[dict[str, Any]], component: str, offset: int) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    for value in values:
        storage = value.get("storage")
        producer = value.get("producer")
        if not isinstance(storage, dict) or not isinstance(producer, dict):
            continue
        if (
            storage.get("space") == "buffer" and storage.get("name") == component
            and storage.get("byte_offset") == offset and storage.get("width") == 8
            and value.get("width") == 8 and producer.get("role") == "copy_result"
            and isinstance(producer.get("trace_sequence"), int)
        ):
            candidates.append(value)
    _require(bool(candidates), "CARRY_BINDING", f"no terminal write for {component}[{offset // 8}]")
    return max(candidates, key=lambda value: value["producer"]["trace_sequence"])


def _copy_source(value: dict[str, Any]) -> str:
    _require(value.get("producer_kind") == "COPY_BITS", "CARRY_BINDING", "terminal value is not COPY_BITS")
    slices = value.get("source_slices")
    _require(isinstance(slices, list) and len(slices) == 1, "CARRY_BINDING", "COPY must have one source slice")
    source = slices[0]
    _require(source.get("destination_offset") == 0 and source.get("source_offset") == 0 and source.get("width") == 8, "CARRY_BINDING", "COPY source is not a full lane")
    source_id = source.get("value_id")
    _require(isinstance(source_id, str), "CARRY_BINDING", "COPY source ID missing")
    return source_id


def _form_binding(
    terminal: dict[str, Any], values_by_id: dict[str, dict[str, Any]], states: dict[str, dict[str, Any]]
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    current = terminal
    direct_state: dict[str, Any] | None = None
    seen: set[str] = set()
    while True:
        value_id = current.get("value_id")
        _require(isinstance(value_id, str) and value_id not in seen, "FORM_BINDING", "COPY chain cycle or missing ID")
        seen.add(value_id)
        state = states.get(f"state:{value_id}:byte:0")
        if current is terminal:
            direct_state = state
        if state is not None:
            _require(state.get("value_id") == value_id and state.get("byte_offset") == 0 and state.get("width") == 8, "FORM_BINDING", "malformed state binding")
            _require(state.get("raw_center_bits") == terminal.get("raw_bits"), "FORM_BINDING", "Form ancestor center mismatch")
            return direct_state, state
        source_id = _copy_source(current)
        _require(source_id in values_by_id, "FORM_BINDING", f"missing COPY source {source_id}")
        source = values_by_id[source_id]
        _require(source.get("width") == 8 and source.get("raw_bits") == terminal.get("raw_bits"), "FORM_BINDING", "COPY source bits differ")
        current = source


def _derive_scalar_load(rows: list[dict[str, Any]], decoded: dict[int, str], destination: str) -> dict[str, Any]:
    candidates: list[tuple[dict[str, Any], str]] = []
    for row in rows:
        mnemonic, operands = _parse_assembly(decoded[row["sequence"]])
        if mnemonic == "movsd" and len(operands) == 2 and "(" in operands[0] and operands[1] == destination:
            candidates.append((row, operands[0]))
    code = "TIME_PROVENANCE" if destination == "%xmm0" else "DT_PROVENANCE"
    _require(bool(candidates), code, f"no memory load into {destination}")
    row, source_operand = candidates[-1]
    return {
        "instruction_sequence": row["sequence"],
        "assembly": row["assembly"],
        "source_memory_address": _effective_address(row, source_operand),
        "source_bits": _bits(_source_value(row, source_operand, 8), 8),
        "source_operand": source_operand,
        "destination_register": destination.lstrip("%"),
    }


def _validate_threads(capture: dict[str, Any], rows: list[dict[str, Any]]) -> int:
    all_stop = capture.get("single_thread_all_stop")
    _require(
        isinstance(all_stop, dict)
        and all_stop.get("non_stop") == "Controlling the inferior in non-stop mode is off."
        and all_stop.get("scheduler_locking") == "on",
        "THREAD_CONTROL",
        "capture is not scheduler-locked all-stop",
    )
    owner = all_stop.get("owner_ptid")
    _require(isinstance(owner, list) and len(owner) == 3, "THREAD_CONTROL", "owner PTID missing")
    _require(all(row.get("thread_ptid") == owner for row in rows), "THREAD_CONTROL", "instruction owner changed")
    counts: list[int] = []
    for boundary_name in ("first_step_entry", "first_step_return", "second_step_entry"):
        boundary = capture.get(boundary_name)
        _require(isinstance(boundary, dict), "THREAD_CONTROL", f"missing {boundary_name}")
        inventory = boundary.get("thread_inventory")
        _require(isinstance(inventory, list) and inventory, "THREAD_CONTROL", f"missing inventory at {boundary_name}")
        selected = [item for item in inventory if item.get("selected_owner") is True]
        _require(len(selected) == 1 and selected[0].get("ptid") == owner, "THREAD_CONTROL", f"wrong owner at {boundary_name}")
        _require(all(item.get("stopped_under_all_stop") is True for item in inventory), "THREAD_CONTROL", f"unstopped thread at {boundary_name}")
        counts.append(len(inventory))
    _require(len(set(counts)) == 1, "THREAD_CONTROL", "thread inventory changed")
    return counts[0]


def _read_trace(trace_path: Path) -> tuple[bytes, list[dict[str, Any]]]:
    try:
        trace_bytes = trace_path.read_bytes()
        lines = trace_bytes.decode("utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        _refuse("TRACE_SEQUENCE", f"cannot read trace: {exc}")
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(lines, 1):
        try:
            row = json.loads(line, object_pairs_hook=_pairs_no_duplicates)
        except (json.JSONDecodeError, CheckerRefused) as exc:
            _refuse("TRACE_SEQUENCE", f"bad trace row {line_number}: {exc}")
        _require(isinstance(row, dict), "TRACE_SEQUENCE", f"row {line_number} is not an object")
        rows.append(row)
    _require(bool(rows), "TRACE_SEQUENCE", "empty caller trace")
    return trace_bytes, rows


def _validate_trace_structure(
    capture: dict[str, Any], transition_capture: dict[str, Any], rows: list[dict[str, Any]]
) -> None:
    _require(len(rows) == capture.get("record_count") == transition_capture.get("record_count"), "TRACE_SEQUENCE", "record count mismatch")
    previous_chain = rows[0].get("previous_chain")
    _require(isinstance(previous_chain, str) and re.fullmatch(r"[0-9a-f]{64}", previous_chain) is not None, "TRACE_SEQUENCE", "invalid initial chain")
    owner = capture.get("single_thread_all_stop", {}).get("owner_ptid")
    for index, row in enumerate(rows):
        _require(row.get("schema") == ROW_SCHEMA and row.get("sequence") == index, "TRACE_SEQUENCE", f"schema or dense sequence mismatch at row {index}")
        expected_phase = "first_step_return" if index == 0 else "caller"
        _require(row.get("phase") == expected_phase, "TRACE_SEQUENCE", f"wrong phase at row {index}")
        _require(row.get("previous_chain") == previous_chain, "TRACE_SEQUENCE", f"chain predecessor mismatch at row {index}")
        unsigned = {key: value for key, value in row.items() if key != "record_chain"}
        computed = _sha_bytes(_canonical(unsigned))
        _require(row.get("record_chain") == computed, "TRACE_SEQUENCE", f"record chain mismatch at row {index}")
        previous_chain = computed
        for state_name in ("pre", "post"):
            state = row.get(state_name)
            _require(isinstance(state, dict), "TRACE_STATE", f"missing {state_name} at row {index}")
            gpr = state.get("gpr")
            xmm = state.get("xmm")
            _require(isinstance(gpr, dict) and all(name in gpr for name in GPRS), "TRACE_STATE", f"incomplete GPR state at row {index}")
            _require(isinstance(xmm, dict) and all(f"xmm{i}" in xmm for i in range(16)), "TRACE_STATE", f"incomplete XMM state at row {index}")
        if index:
            _require(row["pre"] == rows[index - 1]["post"], "TRACE_STATE_LINK", f"state discontinuity at row {index}")
        _require(row.get("thread_ptid") == owner, "THREAD_CONTROL", f"owner thread changed at row {index}")
    _require(capture.get("final_chain") == previous_chain, "TRACE_SEQUENCE", "final chain mismatch")


def _validate_boundary_and_abi(
    capture: dict[str, Any], rows: list[dict[str, Any]], decoded: dict[int, str], writes: list[dict[str, Any]]
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    first_return = capture.get("first_step_return")
    second_entry = capture.get("second_step_entry")
    first_entry = capture.get("first_step_entry")
    _require(isinstance(first_return, dict) and isinstance(second_entry, dict) and isinstance(first_entry, dict), "CAPTURE_BOUNDARY", "boundary receipts missing")
    _require(first_return.get("instruction_sequence") == 0, "CAPTURE_BOUNDARY", "first return is not sequence zero")
    first_pre = first_return.get("pre")
    _require(isinstance(first_pre, dict) and first_pre.get("pc") == rows[0]["pc"] and first_pre.get("context") == rows[0]["pre"], "CAPTURE_BOUNDARY", "first return pre-state mismatch")
    _require(first_return.get("post_context") == rows[0]["post"], "CAPTURE_BOUNDARY", "first return post-state mismatch")
    _require(_parse_assembly(decoded[0])[0] == "ret", "CAPTURE_BOUNDARY", "corridor does not begin at RET")
    last = rows[-1]
    _require(_parse_assembly(decoded[last["sequence"]])[0] == "call", "CAPTURE_BOUNDARY", "corridor does not end at CALL")
    first_abi = first_entry.get("abi")
    second_abi = second_entry.get("abi")
    _require(isinstance(first_abi, dict) and isinstance(second_abi, dict), "ABI_BINDING", "ABI receipts missing")
    _require(last["next_pc"] == second_abi.get("entry_pc") and last["post"] == second_abi.get("context"), "ABI_BINDING", "second entry is not final CALL post-state")
    _require(first_abi.get("entry_pc") == second_abi.get("entry_pc"), "ABI_BINDING", "callee entry changed")
    for abi in (first_abi, second_abi):
        context = abi.get("context")
        pointers = abi.get("pointers")
        _require(isinstance(context, dict) and isinstance(pointers, dict), "ABI_BINDING", "ABI context/pointers missing")
        gpr = context["gpr"]
        _require(_hex_int(gpr["rdi"], "ABI_BINDING", "rdi") == abi.get("cpointer"), "ABI_BINDING", "cpointer mismatch")
        _require(_hex_int(gpr["rsi"], "ABI_BINDING", "rsi") == abi.get("n"), "ABI_BINDING", "n mismatch")
        _require(_hex_int(gpr["rdx"], "ABI_BINDING", "rdx") == abi.get("half_ndim"), "ABI_BINDING", "half_ndim mismatch")
        _require(_hex_int(gpr["rcx"], "ABI_BINDING", "rcx") == pointers.get("q"), "ABI_BINDING", "q pointer mismatch")
        _require(_hex_int(gpr["r8"], "ABI_BINDING", "r8") == pointers.get("full_v"), "ABI_BINDING", "full_v pointer mismatch")
        _require(_hex_int(gpr["r9"], "ABI_BINDING", "r9") == pointers.get("latent"), "ABI_BINDING", "latent pointer mismatch")
        _require(_bits(_reg_value(context, "%xmm0")[0], 8) == abi.get("t_bits"), "ABI_BINDING", "t register mismatch")
        _require(_bits(_reg_value(context, "%xmm1")[0], 8) == abi.get("dt_bits"), "ABI_BINDING", "dt register mismatch")
    _require(first_abi.get("n") == second_abi.get("n") == 1 and first_abi.get("half_ndim") == second_abi.get("half_ndim") == 2, "ABI_BINDING", "frozen regular dimensions changed")
    gradient_pointer = second_abi["pointers"]["gradient"]
    last_rsp = _reg_value(last["post"], "%rsp")[0]
    gradient_pushes = [write for write in writes if write["kind"] == "PUSH_STACK" and write["after_bits"] == _bits(gradient_pointer, 8)]
    _require(bool(gradient_pushes) and gradient_pushes[-1]["address"] == last_rsp + 8, "ABI_BINDING", "stack gradient argument not established")
    controlled = capture.get("controlled_stop_receipt")
    _require(isinstance(controlled, dict), "CAPTURE_BOUNDARY", "controlled-stop receipt missing")
    _require(controlled.get("stop_pc") == second_abi.get("entry_pc") and controlled.get("before_second_step_body") is True and controlled.get("second_step_body_instructions_executed") == 0 and controlled.get("inferior_terminated_by_debugger") is True and controlled.get("harness_completed_normally") is False, "CAPTURE_BOUNDARY", "invalid controlled-stop receipt")
    _require(capture.get("old_capture_continuation_present") is not True, "CAPTURE_BOUNDARY", "historical continuation falsely claimed")
    return first_abi, first_return, second_abi


def _validate_source_receipts(root: Path, capture_dir: Path, execution: dict[str, Any]) -> None:
    source_hashes = execution.get("source_sha256_before_execution")
    _require(source_hashes == SOURCE_RECEIPTS, "SOURCE_SET", "execution source hashes differ from literal source set")
    _require(execution.get("source_receipt_key_set") == sorted(SOURCE_RECEIPTS), "SOURCE_SET", "source receipt key set mismatch")
    source_pinset = _load_json(capture_dir / "source_pinset.json")
    _require(source_pinset.get("files") == SOURCE_RECEIPTS
             and source_pinset.get("exact_key_set") == sorted(SOURCE_RECEIPTS),
             "SOURCE_SET", "source pinset differs from literal source set")
    for relative, expected_hash in source_hashes.items():
        _require(isinstance(relative, str) and isinstance(expected_hash, str), "SOURCE_INTEGRITY", "bad execution source receipt")
        path = (root / relative).resolve()
        try:
            path.relative_to(root.resolve())
        except ValueError:
            _refuse("SOURCE_INTEGRITY", f"source path escapes root: {relative}")
        _require(path.is_file() and _sha_file(path) == expected_hash, "SOURCE_INTEGRITY", f"execution source hash mismatch: {relative}")
    _require(execution.get("packages_installed") == [] and execution.get("machine_mapping_used_during_acquisition") is False, "SOURCE_INTEGRITY", "execution environment changed or used machine mapping")
    harness_diff = _load_json(capture_dir / "harness_diff.json")
    old_path = root / "runtime_trace" / "harness.py"
    new_path = root / "runtime_trace" / "harness_nsteps2.py"
    _require(harness_diff.get("old_sha256") == _sha_file(old_path) and harness_diff.get("new_sha256") == _sha_file(new_path), "SOURCE_INTEGRITY", "harness hashes mismatch")
    _require(harness_diff.get("replacement") == "n_steps=1 -> n_steps=2" and harness_diff.get("replacement_count") == 1 and harness_diff.get("all_other_bytes_identical") is True, "SOURCE_INTEGRITY", "harness diff receipt mismatch")
    old_bytes = old_path.read_bytes()
    expected_new = old_bytes.replace(b"n_steps=1", b"n_steps=2")
    _require(old_bytes.count(b"n_steps=1") == 1 and new_path.read_bytes() == expected_new, "SOURCE_INTEGRITY", "harness is not the one-token sibling")
    wheel_path = root / "audit" / "gate2c1" / "vendor" / "gala-1.12.0-cp312-cp312-manylinux_2_24_x86_64.manylinux_2_28_x86_64.whl"
    wheel_sha = _sha_file(wheel_path)
    _require(wheel_sha == WHEEL_SHA256 and execution.get("frozen_wheel_sha256") == wheel_sha, "SOURCE_INTEGRITY", "frozen wheel identity mismatch")
    environment = execution.get("environment")
    _require(isinstance(environment, dict) and environment.get("python") == "3.12.3" and environment.get("packages", {}).get("gala") == "1.12.0", "SOURCE_INTEGRITY", "frozen Python/Gala version mismatch")


def _check_bundle_with_pins(
    capture_dir: Path | str,
    transition_path: Path | str,
    pins: TrustedCasePins,
    *,
    root: Path | str | None = None,
    objdump: str = "objdump",
) -> dict[str, Any]:
    """Check one frozen caller corridor and accepted producer transition."""

    root_path = Path(root).resolve() if root is not None else Path(__file__).resolve().parents[2]
    capture_directory = Path(capture_dir).resolve()
    transition_file = Path(transition_path).resolve()
    capture_path = capture_directory / "capture.json"
    trace_path = capture_directory / "caller_trace.jsonl"
    execution_path = capture_directory / "execution.json"
    seal_path = capture_directory / "acquisition_seal.json"
    _require(_sha_file(transition_file) == pins.transition_sha256, "TRUST_TRANSITION", "transition does not match immutable pin")
    _require(_sha_file(seal_path) == pins.seal_sha256, "TRUST_SEAL", "acquisition seal does not match immutable pin")
    seal = _load_json(seal_path)
    _require(seal.get("schema") == SEAL_SCHEMA and seal.get("antecedent_label") == pins.label,
             "TRUST_SEAL", "seal schema/label mismatch")
    _require(seal.get("sealed_files") == pins.sealed_files
             and seal.get("exact_file_name_set") == sorted(pins.sealed_files)
             and seal.get("file_count") == len(pins.sealed_files),
             "TRUST_FILE_SET", "sealed file set differs from immutable pin")
    actual_names = sorted(path.name for path in capture_directory.iterdir() if path.is_file() and path.name != "acquisition_seal.json")
    _require(actual_names == sorted(pins.sealed_files), "TRUST_FILE_SET", "raw acquisition file set differs")
    for name, expected_sha in pins.sealed_files.items():
        _require(_sha_file(capture_directory / name) == expected_sha, "TRUST_FILE_HASH", f"sealed file mismatch: {name}")
    transition = _load_json(transition_file)
    antecedent = transition.get("antecedent")
    _require(isinstance(antecedent, dict), "TRANSITION_STRUCTURE", "antecedent missing")
    label = antecedent.get("label")
    _require(label in ANTECEDENTS, "UNSUPPORTED_ANTECEDENT", f"unsupported antecedent: {label}")
    try:
        capture_bytes = capture_path.read_bytes()
    except OSError as exc:
        _refuse("CAPTURE_INTEGRITY", f"cannot read capture: {exc}")
    capture = _load_json(capture_path)
    execution = _load_json(execution_path)
    trace_bytes, rows = _read_trace(trace_path)
    _require(transition.get("schema") == TRANSITION_SCHEMA and transition.get("verdict") == "PRODUCED", "TRANSITION_STRUCTURE", "wrong transition schema/verdict")
    _require(capture.get("schema") == CAPTURE_SCHEMA and capture.get("verdict") == "CONTROLLED_STOP", "CAPTURE_INTEGRITY", "wrong capture schema/verdict")
    _require(capture.get("antecedent_label") == label == antecedent.get("capture_label"), "ANTECEDENT_IDENTITY", "capture/transition label mismatch")
    _require(antecedent.get("requested_label_matches_capture") is True, "ANTECEDENT_IDENTITY", "label-equality receipt missing")
    _require(execution.get("schema") == EXECUTION_SCHEMA, "EXECUTION_AUTH", "wrong execution schema")
    _require(execution.get("memory_observation_policy_id") == "all-explicit-and-implicit-control-stack-v1"
             and execution.get("segment_base_policy_id") == "per-row-fs-gs-base-v1"
             and execution.get("pre_memory_observation_failures") == 0,
             "EXECUTION_AUTH", "execution read/segment policy mismatch")
    _require(set(execution.get("frozen_module_sha256_set", [])) == MODULE_SHA256S
             and execution.get("frozen_module_manifest_sha256") == SOURCE_RECEIPTS["runtime_trace/caller_transition/frozen_modules/manifest.json"]
             and execution.get("frozen_wheel_sha256") == WHEEL_SHA256,
             "MODULE_SET", "execution module/wheel pins differ from literals")
    _require(capture.get("memory_observation_policy_id") == execution.get("memory_observation_policy_id")
             and capture.get("segment_base_policy_id") == execution.get("segment_base_policy_id")
             and capture.get("failed_pre_memory_observations") == [],
             "EXECUTION_AUTH", "capture read/segment policy mismatch")
    _require(execution.get("process_identity") == pins.process_identity
             and capture.get("process_identity") == pins.process_identity
             and transition.get("capture", {}).get("process_identity") == pins.process_identity,
             "EXECUTION_AUTH", "structured process identity mismatch")
    _require(execution.get("antecedent_label") == label and execution.get("inferior_pid") == capture.get("inferior_pid") == pins.process_identity["pid"], "ANTECEDENT_IDENTITY", "execution identity mismatch")
    _require(execution.get("harness_completed_normally") is False, "CAPTURE_BOUNDARY", "normal completion falsely claimed")
    _require(capture.get("gdb_version") == "15.1" and capture.get("wheel_sha256") == execution.get("frozen_wheel_sha256"), "SOURCE_INTEGRITY", "frozen GDB/wheel receipt mismatch")
    transition_capture = transition.get("capture")
    _require(isinstance(transition_capture, dict), "CAPTURE_INTEGRITY", "capture receipt missing")
    capture_sha = _sha_bytes(capture_bytes)
    trace_sha = _sha_bytes(trace_bytes)
    _require(capture_sha == pins.capture_sha256 and _sha_file(execution_path) == pins.execution_sha256,
             "EXECUTION_AUTH", "capture/execution immutable hash mismatch")
    _require(trace_sha == pins.trace_sha256 and capture.get("final_chain") == pins.trace_final_chain,
             "TRACE_INTEGRITY", "trace immutable hash/final-chain mismatch")
    authentication = transition.get("authentication")
    _require(isinstance(authentication, dict), "CAPTURE_INTEGRITY", "authentication receipt missing")
    _require(authentication.get("capture_sha256") == capture_sha
             and authentication.get("execution_sha256") == pins.execution_sha256
             and authentication.get("trace_sha256") == trace_sha == capture.get("trace_sha256")
             and authentication.get("final_chain") == pins.trace_final_chain
             and authentication.get("seal_sha256") == pins.seal_sha256
             and authentication.get("sealed_file_name_set") == sorted(pins.sealed_files),
             "CAPTURE_INTEGRITY", "transition authentication mismatch")
    _require(authentication.get("acquisition_directory") == pins.capture_directory
             and authentication.get("capture_path") == f"{pins.capture_directory}/capture.json"
             and authentication.get("execution_path") == f"{pins.capture_directory}/execution.json"
             and authentication.get("trace_path") == f"{pins.capture_directory}/caller_trace.jsonl"
             and authentication.get("seal_path") == f"{pins.capture_directory}/acquisition_seal.json"
             and authentication.get("antecedent_pinset") == {"numeric_ir": pins.ir_sha256, "correspondence": pins.correspondence_sha256},
             "CAPTURE_INTEGRITY", "authenticated path/antecedent identity mismatch")
    _validate_trace_structure(capture, transition_capture, rows)
    thread_count = _validate_threads(capture, rows)
    modules, decoded = _resolve_modules(root_path, capture, rows, objdump)
    _require({sha: item[2] for sha, item in modules.items()} == MODULE_LOAD_BASES,
             "MODULE_SET", "module load bases differ from immutable handoff")
    module_pinset = _load_json(capture_directory / "module_pinset.json")
    _require(set(module_pinset.get("exact_sha256_set", [])) == MODULE_SHA256S
             and set(module_pinset.get("modules", {})) == MODULE_SHA256S,
             "MODULE_SET", "module pinset differs from literal module set")
    load_bases = {sha: metadata[2] for sha, metadata in modules.items()}
    _validate_sequence_receipts(capture, transition, rows)
    _validate_control(rows, decoded, load_bases)
    writes = _validate_recorded_writes(rows, decoded)
    memory_summary = _validate_memory_observations(rows, decoded)
    _validate_register_semantics(rows, decoded)
    actual_counts = {
        "rows": len(rows),
        "pre_memory_observations": memory_summary["count"],
        "pre_memory_observation_failures": 0,
        "possible_memory_writes": len(writes),
        "same_value_writes": sum(write["value_changed"] is False for write in writes),
        "indirect_memory_controls": sum(1 for row in rows if _parse_assembly(decoded[row["sequence"]])[0] in {"jmp", "call"} and _parse_assembly(decoded[row["sequence"]])[1][0].startswith("*")),
        "returns": sum(1 for row in rows if _parse_assembly(decoded[row["sequence"]])[0] == "ret"),
        "pops": sum(1 for row in rows if _parse_assembly(decoded[row["sequence"]])[0] == "pop"),
        "leaves": sum(1 for row in rows if _parse_assembly(decoded[row["sequence"]])[0] == "leave"),
    }
    _require(capture.get("counts") == actual_counts, "EVIDENCE_COUNTS", "capture counts are not independently reproduced")
    readproof = transition.get("readproof")
    _require(isinstance(readproof, dict) and all(readproof.get(key) == value for key, value in actual_counts.items())
             and readproof.get("required_memory_observations_complete") is True
             and readproof.get("segment_bases_complete") is True,
             "EVIDENCE_COUNTS", "transition readproof counts/policies mismatch")
    final_observations = []
    for sequence in (718, 721, 722, 723, 724, 725, 726, 727):
        _require(sequence < len(rows), "ABI_PROVENANCE", "final ABI sequence absent")
        for observation in rows[sequence]["pre_memory_observations"]:
            final_observations.append({"sequence": sequence, **observation})
    _require(readproof.get("final_abi_source_observations") == final_observations,
             "ABI_PROVENANCE", "final ABI observation receipt mismatch")
    first_abi, first_return, second_abi = _validate_boundary_and_abi(capture, rows, decoded, writes)
    abi_origin_chains = _validate_origin_semantics(pins.case, capture, rows, decoded)
    _validate_source_receipts(root_path, capture_directory, execution)

    expected_ir_relative, expected_corr_relative = pins.ir_path, pins.correspondence_path
    ir_path = _safe_source(root_path, antecedent.get("numeric_ir_path"), expected_ir_relative)
    correspondence_path = _safe_source(root_path, antecedent.get("correspondence_path"), expected_corr_relative)
    ir_sha = _sha_file(ir_path)
    correspondence_sha = _sha_file(correspondence_path)
    _require(ir_sha == pins.ir_sha256 and correspondence_sha == pins.correspondence_sha256
             and antecedent.get("numeric_ir_sha256") == ir_sha
             and antecedent.get("correspondence_sha256") == correspondence_sha,
             "ANTECEDENT_PIN", "antecedent hash mismatch")
    ir = _load_json(ir_path)
    correspondence = _load_json(correspondence_path)
    _require(ir.get("schema") == IR_SCHEMA and correspondence.get("schema") == CORRESPONDENCE_SCHEMA, "SOURCE_INTEGRITY", "IR/correspondence schema mismatch")
    correspondence_source = correspondence.get("source")
    _require(isinstance(correspondence_source, dict), "SOURCE_INTEGRITY", "correspondence source missing")
    _require(correspondence_source.get("audited_input_label") == label and correspondence_source.get("numeric_ir_sha256") == ir_sha, "ANTECEDENT_IDENTITY", "correspondence source identity mismatch")
    values = ir.get("values")
    corr_values = correspondence.get("values")
    state_bindings = correspondence.get("state_bindings")
    _require(isinstance(values, list) and corr_values == values and isinstance(state_bindings, list), "SOURCE_INTEGRITY", "correspondence did not preserve IR values")
    values_by_id: dict[str, dict[str, Any]] = {}
    for value in values:
        _require(isinstance(value, dict) and isinstance(value.get("value_id"), str) and value["value_id"] not in values_by_id, "SOURCE_INTEGRITY", "duplicate/malformed IR value")
        values_by_id[value["value_id"]] = value
    states: dict[str, dict[str, Any]] = {}
    for state in state_bindings:
        _require(isinstance(state, dict) and isinstance(state.get("state_id"), str) and state["state_id"] not in states, "SOURCE_INTEGRITY", "duplicate/malformed state binding")
        states[state["state_id"]] = state

    bindings = transition.get("bindings")
    _require(isinstance(bindings, dict), "TRANSITION_STRUCTURE", "bindings missing")
    carry = bindings.get("carry")
    _require(isinstance(carry, list) and len(carry) == len(CARRY_LANES), "CARRY_SET", "carry set must contain six lanes")
    first_bits = first_return.get("post_component_bits")
    second_bits = second_abi.get("component_bits")
    _require(isinstance(first_bits, dict) and isinstance(second_bits, dict), "CAPTURE_BOUNDARY", "component bits missing")
    carry_ranges = [(first_abi["pointers"][component] + offset, 8) for component, offset in CARRY_LANES]
    carried_overlaps = [
        write for write in writes
        if any(_overlaps(write["address"], write["size"], start, width) for start, width in carry_ranges)
    ]
    _require(not carried_overlaps, "CARRY_BINDING", "caller write overlaps a carried lane")

    derived_carry: list[dict[str, Any]] = []
    for index, (component, offset) in enumerate(CARRY_LANES):
        lane = carry[index]
        _require(isinstance(lane, dict) and lane.get("component") == component and lane.get("byte_offset") == offset, "CARRY_SET", f"carry order/identity mismatch at lane {index}")
        terminal = _terminal_buffer_value(values, component, offset)
        immediate_source_id = _copy_source(terminal)
        direct_state, form_state = _form_binding(terminal, values_by_id, states)
        raw_bits = terminal.get("raw_bits")
        _require(raw_bits == first_bits[component][offset // 8] == second_bits[component][offset // 8], "CARRY_BINDING", f"native endpoint bits differ for {component}[{offset // 8}]")
        expected_fields = {
            "component": component,
            "byte_offset": offset,
            "center_bits": raw_bits,
            "endpoint_memory_value_id": terminal["value_id"],
            "endpoint_memory_state_id": None if direct_state is None else direct_state["state_id"],
            "copy_source_value_id": immediate_source_id,
            "form_source_state_id": form_state["state_id"],
            "old_endpoint_state_binding_present": direct_state is not None,
            "no_intervening_write": True,
            "transformation_class": "A_PURE_COPY",
        }
        for field, expected in expected_fields.items():
            _require(lane.get(field) == expected, "CARRY_BINDING", f"{field} mismatch for {component}[{offset // 8}]")
        _require(lane.get("form") == form_state.get("form"), "FORM_BINDING", f"Form mismatch for {component}[{offset // 8}]")
        derived_carry.append({**expected_fields, "form": form_state["form"]})

    pointer_identity = bindings.get("pointer_identity")
    _require(isinstance(pointer_identity, dict), "POINTER_IDENTITY", "pointer identity receipt missing")
    for component in ("q", "full_v", "latent", "gradient"):
        first_address = first_abi["pointers"][component]
        second_address = second_abi["pointers"][component]
        expected = {
            "first_step_address": first_address,
            "second_step_address": second_address,
            "same_memory_region": first_address == second_address,
        }
        _require(first_address == second_address and pointer_identity.get(component) == expected, "POINTER_IDENTITY", f"pointer identity mismatch for {component}")

    gradient_start = second_abi["pointers"]["gradient"]
    gradient_writes = [write for write in writes if _overlaps(write["address"], write["size"], gradient_start, 16)]
    _require(bool(gradient_writes), "GRADIENT_COVERAGE", "gradient has no observed write")
    old_gradient = first_bits.get("gradient")
    _require(isinstance(old_gradient, list) and len(old_gradient) == 2, "GRADIENT_COVERAGE", "old gradient endpoint bits missing")
    expected_old_gradient = "0x" + old_gradient[1][2:] + old_gradient[0][2:]
    _require(gradient_writes[0]["before_bits"] == expected_old_gradient, "GRADIENT_COVERAGE", "first zero store is not rooted in the old gradient bytes")
    coverage: set[int] = set()
    for write in gradient_writes:
        _require(int(write["after_bits"], 16) == 0, "GRADIENT_COVERAGE", "gradient write is not exact zero")
        coverage.update(range(max(write["address"], gradient_start), min(write["address"] + write["size"], gradient_start + 16)))
    _require(coverage == set(range(gradient_start, gradient_start + 16)), "GRADIENT_COVERAGE", "gradient zero coverage is incomplete")
    _require(any(write["value_changed"] is False for write in gradient_writes), "GRADIENT_COVERAGE", "same-value protected gradient store absent")
    _require(second_bits.get("gradient") == ["0x0000000000000000", "0x0000000000000000"], "GRADIENT_COVERAGE", "second-entry gradient is not zero")
    gradient_binding = bindings.get("gradient")
    _require(isinstance(gradient_binding, dict), "GRADIENT_COVERAGE", "gradient binding missing")
    _require(gradient_binding.get("center_bits") == second_bits["gradient"] and gradient_binding.get("form") == ZERO_FORM and gradient_binding.get("full_byte_coverage") is True and gradient_binding.get("root_kind") == "FRESH_EXACT_ZERO" and gradient_binding.get("write_sequences") == [write["sequence"] for write in gradient_writes], "GRADIENT_COVERAGE", "gradient fresh-root binding mismatch")

    time_receipt = _derive_scalar_load(rows, decoded, "%xmm0")
    dt_receipt = _derive_scalar_load(rows, decoded, "%xmm1")
    capture_sources = capture["second_step_entry"].get("argument_sources")
    _require(isinstance(capture_sources, dict) and capture_sources.get("t") == time_receipt, "TIME_PROVENANCE", "capture time-source receipt mismatch")
    _require(capture_sources.get("dt") == dt_receipt, "DT_PROVENANCE", "capture dt-source receipt mismatch")
    first_schedule_pointer = _hex_int(first_abi["context"]["gpr"]["r13"], "TIME_PROVENANCE", "first r13")
    schedule_base = first_schedule_pointer - 8
    delta = time_receipt["source_memory_address"] - schedule_base
    _require(delta >= 0 and delta % 8 == 0, "TIME_PROVENANCE", "time source is outside the observed schedule stride")
    schedule_index = delta // 8
    _require(schedule_index == 2 and time_receipt["source_bits"] == second_abi["t_bits"], "TIME_PROVENANCE", "time is not the observed t[2] load")
    _require(dt_receipt["source_bits"] == second_abi["dt_bits"], "DT_PROVENANCE", "dt load does not establish entry bits")
    time_binding = bindings.get("time")
    dt_binding = bindings.get("dt")
    _require(isinstance(time_binding, dict) and time_binding.get("actual_source_receipt") == time_receipt and time_binding.get("center_bits") == time_receipt["source_bits"] and time_binding.get("form") == ZERO_FORM and time_binding.get("root_kind") == "FRESH_SCHEDULE_LOAD" and time_binding.get("schedule_index") == schedule_index and time_binding.get("source_instruction_sequences") == [time_receipt["instruction_sequence"]], "TIME_PROVENANCE", "time transition binding mismatch")
    _require(isinstance(dt_binding, dict) and dt_binding.get("actual_source_receipt") == dt_receipt and dt_binding.get("center_bits") == dt_receipt["source_bits"] and dt_binding.get("form") == ZERO_FORM and dt_binding.get("root_kind") == "FRESH_ENTRY_ROOT" and dt_binding.get("provenance_kind") == "ACTUAL_CALL_ARGUMENT" and dt_binding.get("caller_change_sequences") == [dt_receipt["instruction_sequence"]], "DT_PROVENANCE", "dt transition binding mismatch")
    _require(bindings.get("entry_registers") == {"xmm0": {"inherits_prior_form": False, "root_kind": "FRESH_ENTRY_ROOT"}, "xmm1": {"inherits_prior_form": False, "root_kind": "FRESH_ENTRY_ROOT"}}, "ABI_BINDING", "entry XMM roots are not fresh")

    write_set = transition.get("write_set")
    _require(isinstance(write_set, dict), "WRITE_SET", "transition write-set receipt missing")
    expected_gradient_writes = [{key: value for key, value in write.items()} for write in gradient_writes]
    first_four_bits = [item["center_bits"] for item in derived_carry[:4]]
    save_candidates = [
        write for write in writes
        if write["kind"] == "EXPLICIT" and write["size"] == 8
        and write["after_bits"] in first_four_bits
        and not any(_overlaps(write["address"], write["size"], start, width) for start, width in carry_ranges)
    ]
    _require(write_set.get("all_possible_writes_recorded") is True and write_set.get("same_value_stores_included") is True and write_set.get("carried_region_overlaps") == [] and write_set.get("gradient_writes") == expected_gradient_writes and write_set.get("save_all_copy_candidates") == save_candidates, "WRITE_SET", "transition write-set semantics mismatch")

    controlled = capture["controlled_stop_receipt"]
    _require(transition_capture.get("controlled_stop_receipt") == controlled, "CAPTURE_BOUNDARY", "transition controlled-stop receipt mismatch")
    _require(transition.get("scope") == "prospective second-step input at native entry; second body excluded" and transition.get("native_execution_has_form_objects") is False and transition.get("second_step_body_executed") is False and transition.get("second_v2_block_imported_or_executed") is False, "TRANSITION_STRUCTURE", "claim boundary widened")
    producer_receipt = transition.get("producer")
    _require(isinstance(producer_receipt, dict) and producer_receipt.get("imports_or_executes_second_v2_block") is False, "TRANSITION_STRUCTURE", "second V2 block claimed")
    frozen_v2 = correspondence_source.get("frozen_v2")
    _require(isinstance(frozen_v2, dict), "FORM_BINDING", "frozen V2 source receipt missing")
    shared_basis = transition.get("shared_form_basis")
    expected_basis = {
        "conditional_on_externally_audited_endpoint_semantics": True,
        "k": frozen_v2.get("k"),
        "meaning": "computed-minus-true",
        "namespace": f"externally-audited:{label}:{correspondence_sha}",
        "preserved_across_all_six_carries": True,
        "reseeded": False,
    }
    _require(frozen_v2.get("k") == 4 and shared_basis == expected_basis, "FORM_BINDING", "shared Form basis mismatch")

    same_value_count = sum(write["value_changed"] is False for write in writes)
    module_hashes = {sha: _sha_file(metadata[0]) for sha, metadata in sorted(modules.items())}
    return {
        "schema": REPORT_SCHEMA,
        "verdict": "CHECKER_PASS",
        "antecedent_label": label,
        "inferior_pid": capture["inferior_pid"],
        "capture_sha256": capture_sha,
        "trace_sha256": trace_sha,
        "transition_sha256": _sha_file(transition_file),
        "checker_source_sha256": _sha_file(Path(__file__).resolve()),
        "numeric_ir_sha256": ir_sha,
        "correspondence_sha256": correspondence_sha,
        "module_sha256s": module_hashes,
        "module_count": len(modules),
        "record_count": len(rows),
        "decoded_instruction_count": len(decoded),
        "possible_write_count": len(writes),
        "same_value_write_count": same_value_count,
        "pre_memory_observation_count": memory_summary["count"],
        "memory_shadow_rooted_byte_count": memory_summary["rooted_bytes"],
        "indirect_control_count": sum(1 for row in rows if _parse_assembly(decoded[row["sequence"]])[0] in {"jmp", "call"} and _parse_assembly(decoded[row["sequence"]])[1][0].startswith("*")),
        "return_count": sum(1 for row in rows if _parse_assembly(decoded[row["sequence"]])[0] == "ret"),
        "carry_binding_count": len(derived_carry),
        "terminal_bindings": [
            {
                "component": lane["component"],
                "byte_offset": lane["byte_offset"],
                "center_bits": lane["center_bits"],
                "endpoint_memory_value_id": lane["endpoint_memory_value_id"],
                "endpoint_memory_state_id": lane["endpoint_memory_state_id"],
                "copy_source_value_id": lane["copy_source_value_id"],
                "form_source_state_id": lane["form_source_state_id"],
            }
            for lane in derived_carry
        ],
        "gradient_zero_coverage_bytes": len(coverage),
        "gradient_write_sequences": [write["sequence"] for write in gradient_writes],
        "time_source_receipt": time_receipt,
        "dt_source_receipt": dt_receipt,
        "abi_origin_chains": abi_origin_chains,
        "origin_provenance_complete": True,
        "thread_count": thread_count,
        "second_step_body_instructions_executed": controlled["second_step_body_instructions_executed"],
        "unknown_instruction_effects_refused": True,
        "conditional_on_external_form_audit": True,
        "external_audit_performed_by_checker": False,
        "machine_scope": execution.get("environment", {}).get("platform"),
        "process_independence_only": True,
        "limits": [
            "prospective second-step input only; second body not executed",
            "Form semantics are byte-pinned external antecedents, not native Form execution",
            "same-machine separate-process evidence only",
            "no trajectory, accumulated-error, physical-accuracy, or external-audit closure claim",
        ],
    }


def check_transition(
    capture_dir: Path | str,
    transition_path: Path | str,
    *,
    root: Path | str | None = None,
    objdump: str = "objdump",
) -> dict[str, Any]:
    """Public rigid path: only the two literal-pinned v2 acquisitions are accepted."""

    root_path = Path(root).resolve() if root is not None else Path(__file__).resolve().parents[2]
    capture = Path(capture_dir).resolve()
    transition = Path(transition_path).resolve()
    for pins in _PRODUCTION_CASE_PINS.values():
        if capture == (root_path / pins.capture_directory).resolve() and transition == (root_path / pins.transition_path).resolve():
            return _check_bundle_with_pins(capture, transition, pins, root=root_path, objdump=objdump)
    if (capture / "capture.json").is_file():
        candidate = _load_json(capture / "capture.json")
        if candidate.get("schema") == "gala-caller-transition-capture-v1":
            _refuse("SUPERSEDED_EVIDENCE", "v1 caller acquisitions are superseded")
    _refuse("TRUST_PATH", "capture/transition path is not a literal production case")


def check_to_directory(
    capture_dir: Path | str,
    transition_path: Path | str,
    out: Path | str,
    *,
    root: Path | str | None = None,
    objdump: str = "objdump",
) -> dict[str, Any]:
    report = check_transition(capture_dir, transition_path, root=root, objdump=objdump)
    output = Path(out)
    try:
        output.mkdir(parents=True, exist_ok=False)
        (output / "checker_report.json").write_bytes(_canonical(report))
    except FileExistsError:
        raise
    except Exception:
        try:
            if output.exists() and not any(output.iterdir()):
                output.rmdir()
        finally:
            raise
    return report


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture-dir", type=Path, required=True)
    parser.add_argument("--transition", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--root", type=Path)
    parser.add_argument("--objdump", default="objdump")
    args = parser.parse_args(argv)
    try:
        report = check_to_directory(
            args.capture_dir, args.transition, args.out, root=args.root, objdump=args.objdump
        )
    except CheckerRefused as exc:
        print(json.dumps({"verdict": "REFUSED", "code": exc.code, "reason": exc.reason}, sort_keys=True), file=sys.stderr)
        return 2
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
