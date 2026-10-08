"""Restricted AT&T operand grammar for the frozen regular one-step experiment.

No machine_mapping, replay graph, Numeric IR or V2 dependency. Unlisted forms refuse.
"""
import re


class Refused(Exception):
    pass


ARITHMETIC = {"addsd": "ADD", "subsd": "SUB", "mulsd": "MUL"}
COPIES = {"movsd": 8, "movapd": 16, "movaps": 16, "movupd": 16,
          "movups": 16, "movdqa": 16, "movdqu": 16, "movq": 8,
          "movb": 1, "movw": 2, "movl": 4, "vmovd": 4}
VECTOR_COPIES = {"vmovdqu", "vmovdqu8", "vmovdqu64", "vmovdqa", "vmovups"}
ZEROS = {"pxor", "xorps", "xorpd", "vpxor", "vpxord", "vpxorq"}
ROUTING = {"test", "testb", "testl", "testq", "cmp", "cmpb", "cmpl", "cmpq",
           "lea", "add", "sub", "and", "or", "xor", "shl", "shr", "sar",
           "inc", "dec", "not", "neg", "imul", "movslq", "movzbl", "movzwl",
           "endbr64", "vzeroupper", "xchg", "bt"}
GPRS = {"rax": (8, "rax"), "eax": (4, "rax"), "ax": (2, "rax"), "al": (1, "rax"),
        "rbx": (8, "rbx"), "ebx": (4, "rbx"), "bx": (2, "rbx"), "bl": (1, "rbx"),
        "rcx": (8, "rcx"), "ecx": (4, "rcx"), "cx": (2, "rcx"), "cl": (1, "rcx"),
        "rdx": (8, "rdx"), "edx": (4, "rdx"), "dx": (2, "rdx"), "dl": (1, "rdx")}
for full, half, word, byte in [("rsi", "esi", "si", "sil"), ("rdi", "edi", "di", "dil"),
                                ("rbp", "ebp", "bp", "bpl"), ("rsp", "esp", "sp", "spl")]:
    for name, width in [(full, 8), (half, 4), (word, 2), (byte, 1)]:
        GPRS[name] = (width, full)
for i in range(8, 16):
    for suffix, width in [("", 8), ("d", 4), ("w", 2), ("b", 1)]:
        GPRS[f"r{i}{suffix}"] = (width, f"r{i}")
GPRS["rip"] = (8, "rip")


def register_width(name):
    if name in GPRS:
        return GPRS[name][0]
    m = re.fullmatch(r"(xmm|ymm|zmm)(\d+)", name)
    if m and int(m[2]) < 32:
        return {"xmm": 16, "ymm": 32, "zmm": 64}[m[1]]
    raise Refused(f"unknown register: {name}")


def split_operands(text):
    parts, depth, start = [], 0, 0
    for i, char in enumerate(text):
        if char == "(": depth += 1
        elif char == ")": depth -= 1
        elif char == "," and depth == 0:
            parts.append(text[start:i].strip()); start = i + 1
        if depth < 0: raise Refused("operand parentheses")
    if depth: raise Refused("operand parentheses")
    if text.strip(): parts.append(text[start:].strip())
    return parts


def decode(assembly):
    text = assembly.split("#", 1)[0].strip()
    text = re.sub(r"\s+<[^>]*>", "", text)
    # These prefixes are allowed ONLY on a no-access alignment NOP.
    words = text.split()
    if words and words[0] in {"data16", "cs"}:
        while words and words[0] in {"data16", "cs"}: words.pop(0)
        if not words or not words[0].startswith("nop"):
            raise Refused("instruction prefix outside NOP")
        text = " ".join(words)
    if not text: raise Refused("empty decode")
    opcode, _, rest = text.partition(" ")
    operands = split_operands(rest.strip())
    if opcode in ARITHMETIC:
        if len(operands) != 2 or not re.fullmatch(r"%xmm\d+", operands[1]):
            raise Refused("scalar arithmetic form")
        return opcode, ARITHMETIC[opcode], operands, 8
    if opcode in COPIES or opcode == "mov" or opcode in VECTOR_COPIES:
        if len(operands) != 2: raise Refused("copy form")
        widths = [register_width(x[1:]) for x in operands if x.startswith("%")]
        if opcode in VECTOR_COPIES:
            if not widths: raise Refused("vector copy width")
            width = max(widths)
        else:
            width = COPIES.get(opcode, widths[0] if widths else None)
        if width is None: raise Refused("memory copy without explicit width")
        if opcode == "movsd" and not any(x.startswith("%xmm") for x in operands):
            raise Refused("MOVSD string instruction is outside scope")
        return opcode, "MOVE", operands, width
    if opcode in ZEROS:
        if len(operands) == 2 and operands[0] == operands[1]:
            return opcode, "ZERO", operands, register_width(operands[-1][1:])
        if len(operands) == 3 and operands[0] == operands[1]:
            return opcode, "ZERO", operands, register_width(operands[-1][1:])
        raise Refused("bitwise vector arithmetic other than identical-source zero")
    if opcode == "vpbroadcastb" and len(operands) == 2:
        return opcode, "ZERO_FILL", operands, register_width(operands[1][1:])
    if opcode in {"push", "pushq", "pop", "popq"}:
        if len(operands) != 1: raise Refused("stack transfer form")
        return opcode, "STACK", operands, 8
    if opcode in {"call", "callq", "ret", "retq"} or opcode.startswith("j"):
        return opcode, "CONTROL", operands, 8
    if opcode.startswith("nop") or opcode in ROUTING:
        return opcode, "ROUTING", operands, None
    raise Refused(f"unsupported instruction: {opcode}")


def effective_address(operand, registers, pc, length):
    text = operand.lstrip("*")
    if ":" in text: raise Refused("segment-relative addressing")
    m = re.fullmatch(r"([-+]?(?:0x[0-9a-fA-F]+|\d+))?\((%\w+)?(?:,(%\w+)?(?:,([1248]))?)?\)", text)
    if m:
        disp, base, index, scale = m.groups()
        value = int(disp, 0) if disp else 0
        for reg, factor in [(base, 1), (index, int(scale or 1))]:
            if reg:
                name = reg[1:]
                if name not in GPRS: raise Refused("address register")
                value += factor * (pc + length if name == "rip" else registers[GPRS[name][1]])
        return value & ((1 << 64) - 1)
    if re.fullmatch(r"0x[0-9a-fA-F]+", text): return int(text, 16)
    raise Refused(f"operand decode failed: {operand}")


def check_mxcsr(value):
    if value & ((3 << 13) | (1 << 15) | (1 << 6)):
        raise Refused(f"MXCSR rounding/FTZ/DAZ mismatch: {value:#x}")
    if (value & 0x1f80) != 0x1f80:
        raise Refused("unmasked FP exceptions")


def routing_widths(opcode, operands):
    """Logical operand widths; extension source width differs from destination."""
    extensions={"movslq":(4,8),"movzbl":(1,4),"movzwl":(2,4)}
    if opcode in extensions:
        if len(operands)!=2:raise Refused("integer extension form")
        return list(extensions[opcode])
    explicit={"cmpb":1,"testb":1,"cmpl":4,"testl":4,"cmpq":8,"testq":8}
    width=explicit.get(opcode)
    if width is None:
        widths=[register_width(t[1:]) for t in operands if t.startswith("%") and ":" not in t]
        if not widths and operands:raise Refused("integer memory width cannot be inferred")
        width=widths[-1] if widths else 8
    return [register_width(t[1:]) if t.startswith("%") else width for t in operands]


def check_finite(raw_bits):
    if (int(raw_bits, 16) >> 52) & 0x7ff == 0x7ff:
        raise Refused("nonfinite numerical value")
