"""Fail-closed AT&T instruction memory-write classification for acquisition.

The independent checker intentionally does not import this producer decoder.
"""
import re

from runtime_trace.semantics import effective_address, register_width, split_operands


class EffectsRefused(ValueError):
    pass


NO_MEMORY_WRITE = {
    "adc", "add", "and", "bt", "cmp", "cmpb", "cmpl", "cmpq", "comisd",
    "dec", "endbr64", "inc", "imul", "lea", "leave", "mov", "movabs",
    "movapd", "movaps", "movb", "movl", "movq", "movsd", "movslq", "movupd",
    "movups", "movw", "movzbl", "movzwl", "nop", "nopl", "nopw", "not",
    "or", "pcmpeqb", "pop", "popq", "pxor", "ret", "retq", "sar", "sbb",
    "seta", "setae", "setb", "setbe", "sete", "setg", "setge", "setl", "setle",
    "setne", "shl", "shr", "sub", "test", "testb", "testl", "testq", "ucomisd",
    "vmovd", "vmovq", "vmovdqa", "vmovdqu", "vmovdqu8", "vmovdqu64", "vmovups",
    "vpbroadcastb", "vpxor", "vpxord", "vpxorq", "vzeroupper", "xor", "xorpd",
    "xorps", "addsd", "subsd", "mulsd", "divsd", "cvtsi2sd", "cvttsd2si",
}
WRITES_DESTINATION = {
    "adc", "add", "and", "cmpxchg", "dec", "inc", "imul", "mov", "movabs", "movapd",
    "movaps", "movb", "movl", "movq", "movsd", "movupd", "movups", "movw",
    "neg", "not", "or", "pop", "popq", "sar", "sbb", "seta", "setae", "setb",
    "setbe", "sete", "setg", "setge", "setl", "setle", "setne", "shl", "shr",
    "sub", "vmovd", "vmovq", "vmovdqa", "vmovdqu", "vmovdqu8", "vmovdqu64",
    "vmovups", "xchg", "xor",
}
NO_DESTINATION_WRITE = {
    "bt", "cmp", "cmpb", "cmpl", "cmpq", "comisd", "lea", "test", "testb",
    "testl", "testq", "ucomisd",
}
FIXED_WIDTH = {
    "movb": 1, "movw": 2, "movl": 4, "movq": 8, "movsd": 8,
    "movapd": 16, "movaps": 16, "movupd": 16, "movups": 16, "vmovd": 4, "vmovq": 8,
    "cmpb": 1, "cmpl": 4, "cmpq": 8, "testb": 1, "testl": 4, "testq": 8,
}


def _clean(assembly):
    text = assembly.split("#", 1)[0].strip()
    text = re.sub(r"\s+<[^>]*>", "", text)
    words = text.split()
    while words and words[0] in {"data16", "cs", "ds", "ss", "addr32", "rex.W", "lock"}:
        words.pop(0)
    return " ".join(words)


def _width(opcode, operands):
    if opcode in FIXED_WIDTH:
        return FIXED_WIDTH[opcode]
    if opcode.startswith("set"):
        return 1
    if opcode.endswith("b") and opcode not in {"sub", "sbb"}:
        return 1
    if opcode.endswith("w"):
        return 2
    if opcode.endswith("l"):
        return 4
    if opcode.endswith("q"):
        return 8
    widths = []
    for operand in operands:
        if operand.startswith("%") and ":" not in operand:
            try:
                widths.append(register_width(operand[1:]))
            except Exception:
                pass
    if widths:
        return widths[0]
    raise EffectsRefused(f"unsupported memory width for {opcode}")


def _address(operand, registers, pc, length):
    try:
        return effective_address(operand, registers, pc, length)
    except Exception as exc:
        raise EffectsRefused(f"unsupported memory operand {operand}: {exc}") from exc


def possible_writes(assembly, registers, pc, length):
    text = _clean(assembly)
    if not text:
        raise EffectsRefused("unsupported empty instruction")
    opcode, _, tail = text.partition(" ")
    if opcode in {"rep", "repz", "repnz"}:
        string_opcode, _, operands_text = tail.partition(" ")
        if not string_opcode.startswith("stos"):
            raise EffectsRefused(f"unsupported string instruction {text}")
        operands = split_operands(operands_text)
        width = _width(string_opcode, operands)
        count = registers["rcx"]
        size = count * width
        if size > 1 << 20:
            raise EffectsRefused("unsupported string write larger than 1 MiB")
        if not size:
            return []
        direction = -1 if registers.get("eflags", 0) & (1 << 10) else 1
        start = registers["rdi"] if direction > 0 else registers["rdi"] - size + width
        return [{"address": start, "size": size, "kind": "STRING"}]
    operands = split_operands(tail)
    semantic_opcode = opcode
    if len(opcode) > 1 and opcode[-1] in "bwlq" and opcode[:-1] in {
        "adc", "add", "and", "cmpxchg", "dec", "inc", "neg", "not", "or",
        "pop", "push", "sbb", "shl", "shr", "sub", "xchg", "xor",
    }:
        semantic_opcode = opcode[:-1]
    if opcode in {"call", "callq"}:
        return [{"address": (registers["rsp"] - 8) & ((1 << 64) - 1),
                 "size": 8, "kind": "CALL_STACK"}]
    if opcode in {"push", "pushq"}:
        return [{"address": (registers["rsp"] - 8) & ((1 << 64) - 1),
                 "size": 8, "kind": "PUSH_STACK"}]
    if opcode.startswith("j") or opcode in {"ret", "retq", "leave", "endbr64", "vzeroupper"}:
        return []
    if semantic_opcode not in NO_MEMORY_WRITE and semantic_opcode not in WRITES_DESTINATION and semantic_opcode not in NO_DESTINATION_WRITE:
        raise EffectsRefused(f"unsupported instruction: {opcode}")
    if not operands:
        return []
    destination = operands[-1]
    if semantic_opcode in NO_DESTINATION_WRITE or destination.startswith("%") or destination.startswith("$"):
        return []
    if semantic_opcode not in WRITES_DESTINATION:
        return []
    width = _width(opcode, operands)
    return [{"address": _address(destination, registers, pc, length),
             "size": width, "kind": "EXPLICIT"}]
