"""Independent checker for the frozen regular one-step caller transition.

The checker does not import acquisition, producer, module-resolver, adapter,
legacy-checker, or Form-evaluator proof logic.  It resolves the three pinned
ELFs itself, decodes their instructions with GNU objdump, derives the observed
x86-64 write/control effects, and traverses the frozen IR data as data.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable


CAPTURE_SCHEMA = "gala-caller-transition-capture-v1"
ROW_SCHEMA = "gala-caller-transition-instruction-v1"
TRANSITION_SCHEMA = "gala-caller-transition-v1"
IR_SCHEMA = "runtime-trace-numeric-ir-regular-1step-v1"
CORRESPONDENCE_SCHEMA = "numeric-ir-frozen-v2-regular-1step-v1"
REPORT_SCHEMA = "gala-caller-transition-independent-checker-v1"

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


def _effective_address(row: dict[str, Any], operand: str) -> int:
    match = _MEMORY.fullmatch(operand.strip())
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
    return address & ((1 << 64) - 1)


def _source_value(row: dict[str, Any], operand: str, size: int) -> int | None:
    operand = operand.strip()
    if operand.startswith("$"):
        return int(operand[1:], 0) & ((1 << (size * 8)) - 1)
    if operand.startswith("%"):
        return _reg_value(row["pre"], operand)[0] & ((1 << (size * 8)) - 1)
    if "(" in operand:
        return None
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
    memory_destination = bool(operands and "(" in operands[-1])
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
        recorded = row.get("possible_memory_writes")
        if isinstance(recorded, list) and len(recorded) == 1:
            before_text = recorded[0].get("before_bits")
            if isinstance(before_text, str) and re.fullmatch(rf"0x[0-9a-f]{{{size * 2}}}", before_text):
                before = int(before_text, 16)
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
    if any("(" in operand for operand in operands):
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


def _validate_control(rows: list[dict[str, Any]], decoded: dict[int, str], load_bases: dict[str, int]) -> None:
    conditional = {"ja", "jb", "jbe", "je", "jge", "jle", "jne"}
    for index, row in enumerate(rows):
        sequence = row["sequence"]
        assembly = decoded[sequence]
        mnemonic, _operands = _parse_assembly(assembly)
        base = mnemonic.removeprefix("lock ")
        length = len(bytes.fromhex(row["instruction_bytes"]))
        fallthrough = row["pc"] + length
        next_pc = row["next_pc"]
        _require(row["pre"]["gpr"]["rip"] == _bits(row["pc"], 8), "TRACE_STATE", f"pre RIP mismatch at sequence {sequence}")
        _require(row["post"]["gpr"]["rip"] == _bits(next_pc, 8), "TRACE_STATE", f"post RIP mismatch at sequence {sequence}")
        target = _direct_target(assembly, load_bases[row["module_sha256"]])
        if base in conditional:
            _require(target is not None and next_pc in {fallthrough, target}, "TRACE_CONTROL", f"conditional flow mismatch at sequence {sequence}")
        elif base == "jmp":
            if target is not None:
                _require(next_pc == target, "TRACE_CONTROL", f"direct jump mismatch at sequence {sequence}")
        elif base == "call":
            if target is not None:
                _require(next_pc == target, "TRACE_CONTROL", f"direct call mismatch at sequence {sequence}")
            _require(_reg_value(row["post"], "%rsp")[0] == (_reg_value(row["pre"], "%rsp")[0] - 8) & ((1 << 64) - 1), "TRACE_CONTROL", f"call RSP mismatch at sequence {sequence}")
        elif base == "ret":
            _require(_reg_value(row["post"], "%rsp")[0] == (_reg_value(row["pre"], "%rsp")[0] + 8) & ((1 << 64) - 1), "TRACE_CONTROL", f"ret RSP mismatch at sequence {sequence}")
        elif base == "push":
            _require(next_pc == fallthrough and _reg_value(row["post"], "%rsp")[0] == (_reg_value(row["pre"], "%rsp")[0] - 8) & ((1 << 64) - 1), "TRACE_CONTROL", f"push mismatch at sequence {sequence}")
        elif base == "pop":
            _require(next_pc == fallthrough and _reg_value(row["post"], "%rsp")[0] == (_reg_value(row["pre"], "%rsp")[0] + 8) & ((1 << 64) - 1), "TRACE_CONTROL", f"pop mismatch at sequence {sequence}")
        elif base == "leave":
            _require(next_pc == fallthrough and _reg_value(row["post"], "%rsp")[0] == (_reg_value(row["pre"], "%rbp")[0] + 8) & ((1 << 64) - 1), "TRACE_CONTROL", f"leave mismatch at sequence {sequence}")
        else:
            _require(next_pc == fallthrough, "TRACE_CONTROL", f"sequential flow mismatch at sequence {sequence}")
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
        "source_bits": _bits(_reg_value(row["post"], destination)[0], 8),
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
    _require(capture.get("old_capture_continuation_present") is False, "CAPTURE_BOUNDARY", "historical continuation falsely claimed")
    return first_abi, first_return, second_abi


def _validate_source_receipts(root: Path, capture_dir: Path, execution: dict[str, Any]) -> None:
    source_hashes = execution.get("source_sha256_before_execution")
    _require(isinstance(source_hashes, dict), "SOURCE_INTEGRITY", "execution source hashes missing")
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
    _require(wheel_sha == "cc5f0cf3bc63a966a3c130b93f6c05026271fe7178492a02c6266c243b5fc2f0" and execution.get("frozen_wheel_sha256") == wheel_sha, "SOURCE_INTEGRITY", "frozen wheel identity mismatch")
    environment = execution.get("environment")
    _require(isinstance(environment, dict) and environment.get("python") == "3.12.3" and environment.get("packages", {}).get("gala") == "1.12.0", "SOURCE_INTEGRITY", "frozen Python/Gala version mismatch")


def check_transition(
    capture_dir: Path | str,
    transition_path: Path | str,
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
    _require(execution.get("antecedent_label") == label and execution.get("inferior_pid") == capture.get("inferior_pid"), "ANTECEDENT_IDENTITY", "execution identity mismatch")
    _require(execution.get("harness_completed_normally") is False, "CAPTURE_BOUNDARY", "normal completion falsely claimed")
    _require(capture.get("gdb_version") == "15.1" and capture.get("wheel_sha256") == execution.get("frozen_wheel_sha256"), "SOURCE_INTEGRITY", "frozen GDB/wheel receipt mismatch")
    transition_capture = transition.get("capture")
    _require(isinstance(transition_capture, dict), "CAPTURE_INTEGRITY", "capture receipt missing")
    capture_sha = _sha_bytes(capture_bytes)
    trace_sha = _sha_bytes(trace_bytes)
    _require(transition_capture.get("capture_sha256") == capture_sha, "CAPTURE_INTEGRITY", "capture hash mismatch")
    _require(transition_capture.get("trace_sha256") == trace_sha == capture.get("trace_sha256"), "CAPTURE_INTEGRITY", "trace hash mismatch")
    _validate_trace_structure(capture, transition_capture, rows)
    thread_count = _validate_threads(capture, rows)
    modules, decoded = _resolve_modules(root_path, capture, rows, objdump)
    load_bases = {sha: metadata[2] for sha, metadata in modules.items()}
    _validate_control(rows, decoded, load_bases)
    writes = _validate_recorded_writes(rows, decoded)
    first_abi, first_return, second_abi = _validate_boundary_and_abi(capture, rows, decoded, writes)
    _validate_source_receipts(root_path, capture_directory, execution)

    expected_ir_relative, expected_corr_relative = ANTECEDENTS[label]
    ir_path = _safe_source(root_path, antecedent.get("numeric_ir_path"), expected_ir_relative)
    correspondence_path = _safe_source(root_path, antecedent.get("correspondence_path"), expected_corr_relative)
    ir_sha = _sha_file(ir_path)
    correspondence_sha = _sha_file(correspondence_path)
    _require(antecedent.get("numeric_ir_sha256") == ir_sha and antecedent.get("correspondence_sha256") == correspondence_sha, "SOURCE_INTEGRITY", "antecedent hash mismatch")
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
