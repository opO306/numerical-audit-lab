"""Gate 0 benchmark 3: a frozen GenDot fixture (n = 50, c = 1e25). docs/BENCHMARK3_SELECTION.md.

The fixture is loaded only if its SHA-256 matches; it is never regenerated.
The oracle is the exact dot product computed here from the frozen bits, by two
different exact code paths. The generator's own rounded result `d` is NOT used
as the oracle; it is judged like any other claim.
"""
from __future__ import annotations

import hashlib
import json
import struct
from fractions import Fraction
from pathlib import Path

import mpmath

from lab.claim import agree_digits

from .harness import Instr

NAME = "gendot"
FIXTURE = Path(__file__).parent / "fixtures" / "gendot_n50_c1e25_v1.json"
FIXTURE_SHA256 = "b9c971502f5d96a3afb043a0748de34e82ac899d0b999569815b057a0bce5582"
OUT = "s"


def load() -> dict:
    raw = FIXTURE.read_bytes().replace(b"\r\n", b"\n")
    got = hashlib.sha256(raw).hexdigest()
    if got != FIXTURE_SHA256:
        raise RuntimeError(f"frozen fixture changed: sha256 {got}")
    return json.loads(raw)


def _bits(fx: dict) -> tuple:
    return [int(b, 16) for b in fx["x_bits"]], [int(b, 16) for b in fx["y_bits"]]


def _literal(bits: int) -> str:
    f = Fraction(struct.unpack(">d", bits.to_bytes(8, "big"))[0])
    return f"{f.numerator}/{f.denominator}"


def program(kind: str = "naive") -> list:
    """naive: x_i*y_i rounded, then added left to right, one rounding each (an ordinary loop).
    vm_dot: the calculator's DOT -- exact products, exact sum, rounded once (its specification)."""
    xb, yb = _bits(load())
    n = len(xb)
    p = [Instr("CONST", f"x{i}", (_literal(xb[i]),)) for i in range(n)]
    p += [Instr("CONST", f"y{i}", (_literal(yb[i]),)) for i in range(n)]
    if kind == "naive":
        p += [Instr("MUL", f"p{i}", (f"x{i}", f"y{i}")) for i in range(n)]
        acc = "p0"
        for i in range(1, n):
            dst = OUT if i == n - 1 else f"s{i}"
            p.append(Instr("ADD", dst, (acc, f"p{i}")))
            acc = dst
    elif kind == "vm_dot":
        p.append(Instr("DOT", OUT, (tuple(f"x{i}" for i in range(n)), tuple(f"y{i}" for i in range(n)))))
    else:
        raise ValueError(kind)
    return p


def exact_fraction() -> Fraction:
    """Exact path 1: host float -> Fraction (exact), then rational sum."""
    xb, yb = _bits(load())
    f = lambda b: Fraction(struct.unpack(">d", b.to_bytes(8, "big"))[0])      # noqa: E731
    return sum((f(a) * f(b) for a, b in zip(xb, yb)), Fraction(0))


def _split(bits: int) -> tuple:
    """(signed integer mantissa, exponent) with value = m * 2**e, from the bit fields only."""
    sign, ex, frac = bits >> 63, (bits >> 52) & 0x7FF, bits & ((1 << 52) - 1)
    if ex == 0x7FF:
        raise ValueError("not finite")
    m, e = (frac, -1074) if ex == 0 else (frac | (1 << 52), ex - 1075)
    return (-m if sign else m), e


def exact_integer() -> Fraction:
    """Exact path 2: no Fraction and no float until the end -- integer products aligned
    to the smallest exponent and summed as one big integer."""
    xb, yb = _bits(load())
    terms = []
    for a, b in zip(xb, yb):
        (ma, ea), (mb, eb) = _split(a), _split(b)
        terms.append((ma * mb, ea + eb))
    low = min(e for _, e in terms)
    total = sum(m << (e - low) for m, e in terms)
    return Fraction(total, 1) * Fraction(2) ** low


def term_exponent_span() -> int:
    xb, yb = _bits(load())
    es = []
    for a, b in zip(xb, yb):
        (ma, ea), (mb, eb) = _split(a), _split(b)
        if ma * mb:
            es += [ea + eb, ea + eb + (abs(ma * mb)).bit_length()]
    return max(es) - min(es)


def oracle_inputs():
    # Declared loss 0: mpmath's fdot is exact when the working precision covers the
    # whole exponent span of the 50 products; that is checked here, not assumed.
    digits = 300
    prec = int(digits * 3.33) + 20
    span = term_exponent_span()
    if span + 64 > prec:
        raise RuntimeError(f"exponent span {span} bits does not fit {prec}-bit fdot")
    xb, yb = _bits(load())
    with mpmath.workprec(prec):
        to = lambda b: mpmath.mpf(struct.unpack(">d", b.to_bytes(8, "big"))[0])   # noqa: E731
        hp = mpmath.fdot([to(a) for a in xb], [to(b) for b in yb])
    return ({"exact_fraction": exact_fraction(), "exact_integer": exact_integer()},
            (f"mpmath_fdot_{digits}_digits", hp, agree_digits(digits, 0)))


def hardware_naive_bits() -> str:
    """The same naive loop in the host's own float64, for comparison with the calculator."""
    xb, yb = _bits(load())
    f = lambda b: struct.unpack(">d", b.to_bytes(8, "big"))[0]                   # noqa: E731
    s = f(xb[0]) * f(yb[0])
    for a, b in zip(xb[1:], yb[1:]):
        s = s + f(a) * f(b)
    return f"{int.from_bytes(struct.pack('>d', s), 'big'):016x}"


def condition_number() -> Fraction:
    xb, yb = _bits(load())
    f = lambda b: Fraction(struct.unpack(">d", b.to_bytes(8, "big"))[0])      # noqa: E731
    return 2 * sum((abs(f(a) * f(b)) for a, b in zip(xb, yb)), Fraction(0)) / abs(exact_integer())
