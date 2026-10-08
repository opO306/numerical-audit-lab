"""Fail-closed pre-instruction memory-read classification for the v2 capture.

This is acquisition code.  The independent checker must decode the pinned
instruction bytes and derive reads without importing this module.
"""
import re

from runtime_trace.semantics import effective_address, register_width, split_operands


class ReadsRefused(ValueError):
    pass


FIXED_WIDTH = {
    "movb": 1, "movw": 2, "movl": 4, "movq": 8, "movsd": 8,
    "movzbl": 1, "movzwl": 2, "movslq": 4,
    "cmpb": 1, "cmpl": 4, "cmpq": 8,
    "testb": 1, "testl": 4, "testq": 8,
    "addb": 1, "addl": 4, "addq": 8,
    "subb": 1, "subl": 4, "subq": 8,
    "andb": 1, "andl": 4, "andq": 8,
    "orb": 1, "orl": 4, "orq": 8,
    "xorb": 1, "xorl": 4, "xorq": 8,
    "vmovd": 4, "vmovq": 8,
}
MOVES = {
    "mov", "movb", "movw", "movl", "movq", "movsd", "movzbl", "movzwl",
    "movslq", "movapd", "movaps", "movupd", "movups", "vmovd", "vmovq",
    "vmovdqa", "vmovdqu", "vmovdqu8", "vmovdqu64", "vmovups",
}
READ_ALL_MEMORY = {
    "adc", "adcb", "adcl", "adcq", "add", "addb", "addl", "addq",
    "and", "andb", "andl", "andq", "cmp", "cmpb", "cmpl", "cmpq",
    "cmpxchg", "cmpxchgb", "cmpxchgl", "cmpxchgq", "dec", "decl", "decq",
    "inc", "incl", "incq", "neg", "negl", "negq", "not", "notl", "notq",
    "or", "orb", "orl", "orq", "sar", "sarl", "sarq", "sbb", "sbbl", "sbbq",
    "shl", "shll", "shlq", "shr", "shrl", "shrq", "sub", "subb", "subl",
    "subq", "test", "testb", "testl", "testq", "xchg", "xchgl", "xchgq",
    "xor", "xorb", "xorl", "xorq",
}
NO_MEMORY_READ = {
    "bt", "call", "callq", "endbr64", "ja", "jb", "jbe", "je", "jge", "jle",
    "jmp", "jne", "lea", "mov", "movb", "movl", "movq", "movsd", "movw",
    "nop", "nopl", "nopw", "or", "pop", "popq", "push", "pushq", "ret", "retq",
    "seta", "setae", "setb", "setbe", "sete", "setg", "setge", "setl", "setle",
    "setne", "vpbroadcastb", "vzeroupper", "xor",
}


def _clean(assembly):
    text = re.sub(r"\s+<[^>]*>", "", assembly.split("#", 1)[0].strip())
    words = text.split()
    while words and words[0] in {"data16", "cs", "ds", "ss", "addr32", "rex.W", "lock"}:
        words.pop(0)
    if not words:
        raise ReadsRefused("empty instruction")
    return " ".join(words)


def _is_memory(operand):
    text = operand.lstrip("*")
    return text.startswith(("%fs:", "%gs:")) or "(" in text


def _width(opcode, operands):
    if opcode in FIXED_WIDTH:
        return FIXED_WIDTH[opcode]
    if opcode == "vpbroadcastb":
        return 1
    if opcode.startswith("set"):
        return 1
    suffix = opcode[-1:] if opcode else ""
    stem = opcode[:-1]
    if suffix in "bwlq" and stem in {
        "adc", "add", "and", "cmpxchg", "dec", "inc", "neg", "not", "or",
        "sar", "sbb", "shl", "shr", "sub", "xchg", "xor",
    }:
        return {"b": 1, "w": 2, "l": 4, "q": 8}[suffix]
    widths = []
    for operand in operands:
        if operand.startswith("%") and not operand.startswith(("%fs:", "%gs:")):
            try:
                widths.append(register_width(operand[1:]))
            except Exception:
                pass
    if widths:
        return min(widths)
    raise ReadsRefused(f"unsupported read width for {opcode}")


def _address(operand, registers, segment_bases, pc, length):
    text = operand.lstrip("*")
    segment = None
    for name in ("fs", "gs"):
        prefix = f"%{name}:"
        if text.startswith(prefix):
            segment = name
            text = text[len(prefix):]
            break
    try:
        address = effective_address(text, registers, pc, length)
    except Exception as exc:
        raise ReadsRefused(f"unsupported memory operand {operand}: {exc}") from exc
    if segment is not None:
        address = (address + segment_bases[f"{segment}_base"]) & ((1 << 64) - 1)
    return address


def required_reads(assembly, registers, segment_bases, pc, length):
    """Return every architecturally required pre-instruction memory range."""
    text = _clean(assembly)
    opcode, _, tail = text.partition(" ")
    operands = split_operands(tail.strip())
    result = []

    def add(address, size, kind, operand):
        item = {"address": address, "size": size, "kind": kind, "operand": operand}
        if item not in result:
            result.append(item)

    if opcode in {"ret", "retq"}:
        add(registers["rsp"], 8, "IMPLICIT_RET", "(%rsp)")
        return result
    if opcode in {"pop", "popq"}:
        add(registers["rsp"], 8, "IMPLICIT_POP", "(%rsp)")
        return result
    if opcode == "leave":
        add(registers["rbp"], 8, "IMPLICIT_LEAVE", "(%rbp)")
        return result
    if opcode in {"jmp", "call", "callq"} or opcode.startswith("j"):
        if operands and operands[0].startswith("*") and _is_memory(operands[0]):
            add(_address(operands[0], registers, segment_bases, pc, length),
                8, "INDIRECT_CONTROL", operands[0])
        return result
    if opcode in {"push", "pushq"}:
        if len(operands) != 1:
            raise ReadsRefused("push operand count")
        if _is_memory(operands[0]):
            add(_address(operands[0], registers, segment_bases, pc, length),
                8, "EXPLICIT", operands[0])
        return result
    if opcode.startswith("nop") or opcode == "lea":
        return result
    if opcode in MOVES:
        if len(operands) != 2:
            raise ReadsRefused("move operand count")
        if _is_memory(operands[0]):
            add(_address(operands[0], registers, segment_bases, pc, length),
                _width(opcode, operands), "EXPLICIT", operands[0])
        return result
    if opcode == "vpbroadcastb":
        if len(operands) != 2:
            raise ReadsRefused("broadcast operand count")
        if _is_memory(operands[0]):
            add(_address(operands[0], registers, segment_bases, pc, length),
                1, "EXPLICIT", operands[0])
        return result
    if opcode in READ_ALL_MEMORY:
        width = _width(opcode, operands)
        destination = operands[-1] if operands else None
        for operand in operands:
            if _is_memory(operand):
                comparison = opcode in {"cmp", "cmpb", "cmpl", "cmpq", "test", "testb", "testl", "testq"}
                kind = "READ_MODIFY_WRITE" if operand == destination and not comparison else "EXPLICIT"
                add(_address(operand, registers, segment_bases, pc, length), width, kind, operand)
        return result
    if opcode in NO_MEMORY_READ or opcode.startswith("set"):
        return result
    if any(_is_memory(operand) for operand in operands):
        raise ReadsRefused(f"unsupported instruction with possible memory read: {opcode}")
    # The write classifier separately closes all instruction effects.  This
    # branch only covers recognized register/immediate-only opcodes.
    if opcode in {
        "add", "addl", "and", "cmp", "cmpb", "cmpq", "movl", "movzbl", "or",
        "setne", "shl", "shr", "sub", "subl", "test", "vmovd", "vpbroadcastb",
        "xchg", "xor",
    }:
        return result
    raise ReadsRefused(f"unsupported instruction: {opcode}")
