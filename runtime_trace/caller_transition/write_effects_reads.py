"""Segment-aware write classification for the v2 read-proof acquisition."""

from runtime_trace.semantics import effective_address, split_operands
from runtime_trace.caller_transition.write_effects import (
    EffectsRefused,
    NO_DESTINATION_WRITE,
    NO_MEMORY_WRITE,
    WRITES_DESTINATION,
    _clean,
    _width,
)


def _is_memory(operand):
    text = operand.lstrip("*")
    return text.startswith(("%fs:", "%gs:")) or "(" in text


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
        raise EffectsRefused(f"unsupported memory operand {operand}: {exc}") from exc
    if segment is not None:
        address = (address + segment_bases[f"{segment}_base"]) & ((1 << 64) - 1)
    return address


def possible_writes(assembly, registers, segment_bases, pc, length):
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
        size = registers["rcx"] * width
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
    if (semantic_opcode not in NO_MEMORY_WRITE and semantic_opcode not in WRITES_DESTINATION
            and semantic_opcode not in NO_DESTINATION_WRITE):
        raise EffectsRefused(f"unsupported instruction: {opcode}")
    if not operands:
        return []
    destination = operands[-1]
    if semantic_opcode in NO_DESTINATION_WRITE or not _is_memory(destination):
        return []
    if semantic_opcode not in WRITES_DESTINATION:
        return []
    return [{"address": _address(destination, registers, segment_bases, pc, length),
             "size": _width(opcode, operands), "kind": "EXPLICIT"}]
