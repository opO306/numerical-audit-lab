"""Gate 0 benchmark 1: Rump's catastrophic-cancellation example.

f(a, b) = 333.75 b^6 + a^2 (11 a^2 b^2 - b^6 - 121 b^4 - 2) + 5.5 b^8 + a / (2b)
at a = 77617, b = 33096. True value -54767/66192 (about -0.8273960599).

The huge terms cancel almost completely, so any arithmetic that rounds the
big intermediate products loses every correct digit.
"""
from __future__ import annotations

from fractions import Fraction

import mpmath

from lab.claim import agree_digits

from .harness import Instr

NAME = "rump"
A, B = 77617, 33096
LITERATURE_VALUE = Fraction(-54767, 66192)
LITERATURE_NOTE = "Rump's example (1988), in the form popularised by Loh & Walster (2002); exact value -54767/66192"
OUT = "f"


def program(final: str = "sequential") -> list:
    """final="sequential": ((t1 + t2) + t3) + t4, one rounding per addition.
    final="sum": the VM's SUM -- exact sum of the four (already rounded) terms, rounded once."""
    I = Instr
    p = [I("CONST", "a", (A,)), I("CONST", "b", (B,)),
         I("MUL", "b2", ("b", "b")), I("MUL", "b4", ("b2", "b2")), I("MUL", "b6", ("b4", "b2")),
         I("MUL", "b8", ("b4", "b4")), I("MUL", "a2", ("a", "a")),
         I("CONST", "c333_75", ("1335/4",)), I("MUL", "t1", ("c333_75", "b6")),
         I("CONST", "c11", (11,)), I("MUL", "u1", ("c11", "a2")), I("MUL", "u2", ("u1", "b2")),
         I("SUB", "u3", ("u2", "b6")),
         I("CONST", "c121", (121,)), I("MUL", "w", ("c121", "b4")), I("SUB", "u4", ("u3", "w")),
         I("CONST", "c2", (2,)), I("SUB", "u5", ("u4", "c2")),
         I("MUL", "t2", ("a2", "u5")),
         I("CONST", "c5_5", ("11/2",)), I("MUL", "t3", ("c5_5", "b8")),
         I("MUL", "two_b", ("c2", "b")), I("DIV", "t4", ("a", "two_b"))]
    if final == "sequential":
        p += [I("ADD", "r1", ("t1", "t2")), I("ADD", "r2", ("r1", "t3")), I("ADD", OUT, ("r2", "t4"))]
    elif final == "sum":
        p += [I("SUM", OUT, ("t1", "t2", "t3", "t4"))]
    else:
        raise ValueError(final)
    return p


def exact_direct() -> Fraction:
    """Independent of the VM: the formula written straight in Python rationals."""
    a, b = Fraction(A), Fraction(B)
    return (Fraction(1335, 4) * b**6 + a**2 * (11 * a**2 * b**2 - b**6 - 121 * b**4 - 2)
            + Fraction(11, 2) * b**8 + a / (2 * b))


def mp_eval(prec_bits: int):
    """Same evaluation order as program('sequential'), every operation rounded to prec_bits."""
    with mpmath.workprec(prec_bits):
        a, b = mpmath.mpf(A), mpmath.mpf(B)
        b2 = b * b; b4 = b2 * b2; b6 = b4 * b2; b8 = b4 * b4; a2 = a * a
        t1 = mpmath.mpf(1335) / 4 * b6
        u5 = ((11 * a2) * b2 - b6) - 121 * b4 - 2
        t2 = a2 * u5
        t3 = mpmath.mpf(11) / 2 * b8
        t4 = a / (2 * b)
        return +(((t1 + t2) + t3) + t4)


def oracle_inputs():
    # Declared loss 0: in this evaluation order every intermediate is an integer below
    # 2**130 or an exact quarter/half, so a 686-bit run is exact except a/(2b)
    # (measured error 3.1e-207). Same tolerance as the original rule (200 - 10).
    digits = 200
    hp = mp_eval(int(digits * 3.33) + 20)
    return ({"literature": LITERATURE_VALUE, "direct_rational": exact_direct()},
            (f"mpmath_{digits}_digits", hp, agree_digits(digits, 0)))
