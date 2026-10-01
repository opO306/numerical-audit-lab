"""Gate 1 system under test: the elastic-collision calculator as a numeric_core program.

Bugs M1-M7 (docs/GATE1_PLAN.md) are variants of this one program builder, each a
single local change. R1 is a rounding defect inside the binary64 profile.
"""
from __future__ import annotations

import contextlib
from fractions import Fraction

import numeric_core.profiles as P
from numeric_core import VMHalt

from lab.claim import Profile, decode
from lab.gate1_state import Out, State, SutHalt

from ..gate0.harness import Instr, execute

MUTANTS = ("M0", "M1", "M2", "M3", "M4", "M5", "M6", "M7")
EXACT, B64 = Profile("exact"), Profile("binary64")


def _lit(x: Fraction) -> str:
    x = Fraction(x)
    return f"{x.numerator}/{x.denominator}"


def program(s: State, mutant: str = "M0") -> list:
    if mutant not in MUTANTS:
        raise ValueError(mutant)
    I = Instr
    p = [I("CONST", n, (_lit(v),)) for n, v in (
        ("m1", s.m1), ("m2", s.m2), ("x1", s.r1[0]), ("y1", s.r1[1]), ("x2", s.r2[0]), ("y2", s.r2[1]),
        ("vx1", s.v1[0]), ("vy1", s.v1[1]), ("vx2", s.v2[0]), ("vy2", s.v2[1]),
        ("two", 2), ("half", Fraction(1, 2)), ("zero", 0))]
    if mutant == "M5":                                   # absolute coordinates: d = r2
        p += [I("SUB", "dx", ("x2", "zero")), I("SUB", "dy", ("y2", "zero"))]
    else:
        p += [I("SUB", "dx", ("x2", "x1")), I("SUB", "dy", ("y2", "y1"))]
    p += [I("SUB", "rvx", ("vx1", "vx2")), I("SUB", "rvy", ("vy1", "vy2")),
          I("DOT", "dd", (("dx", "dy"), ("dx", "dy")))]
    if mutant == "M3":                                   # x/y confusion
        p.append(I("DOT", "vn", (("rvx", "rvy"), ("dy", "dx"))))
    elif mutant == "M6":                                 # absolute velocity instead of relative
        p.append(I("DOT", "vn", (("vx1", "vy1"), ("dx", "dy"))))
    else:
        p.append(I("DOT", "vn", (("rvx", "rvy"), ("dx", "dy"))))
    p += [I("ADD", "M", ("m1", "m2")), I("DIV", "k", ("vn", "dd"))]
    m_for_1, m_for_2 = ("m1", "m2") if mutant == "M2" else ("m2", "m1")     # M2: mass factors swapped
    p += [I("MUL", "t1", ("two", m_for_1)), I("DIV", "c1", ("t1", "M")),
          I("MUL", "t2", ("two", m_for_2)), I("DIV", "c2", ("t2", "M")),
          I("MUL", "a1", ("c1", "k"))]
    if mutant == "M4":                                   # particle 2 alone uses v1.d
        p += [I("DOT", "vn2", (("vx1", "vy1"), ("dx", "dy"))), I("DIV", "k2", ("vn2", "dd")),
              I("MUL", "a2", ("c2", "k2"))]
    else:
        p.append(I("MUL", "a2", ("c2", "k")))
    p += [I("MUL", "i1x", ("a1", "dx")), I("MUL", "i1y", ("a1", "dy")),
          I("MUL", "i2x", ("a2", "dx")), I("MUL", "i2y", ("a2", "dy"))]
    one, two_ = ("ADD", "SUB") if mutant == "M1" else ("SUB", "ADD")         # M1: impulse sign flipped
    p += [I(one, "w1x", ("vx1", "i1x")), I(one, "w1y", ("vy1", "i1y")),
          I(two_, "w2x", ("vx2", "i2x")), I(two_, "w2y", ("vy2", "i2y"))]
    p += [I("DOT", "e1", (("w1x", "w1y"), ("w1x", "w1y"))), I("DOT", "e2", (("w2x", "w2y"), ("w2x", "w2y"))),
          I("MUL", "p1", ("m1", "e1")), I("MUL", "p2", ("m1" if mutant == "M7" else "m2", "e2")),   # M7: KE uses m1
          I("ADD", "pe", ("p1", "p2")), I("MUL", "ke", ("half", "pe"))]
    return p


def run(s: State, mutant: str = "M0", profile: Profile = EXACT):
    """Returns (Out, Execution). Raises SutHalt if the calculator stopped."""
    e = execute(program(s, mutant), profile, "ke")
    if e.halt:
        raise SutHalt(f"{e.halt[1]} at pc {e.halt[0]}")
    g = lambda n: decode(profile, e.registers[n])                            # noqa: E731
    return Out((g("w1x"), g("w1y")), (g("w2x"), g("w2y")), g("ke")), e


def sut(mutant: str = "M0", profile: Profile = EXACT):
    """The callable the checks receive: State -> Out."""
    return lambda s: run(s, mutant, profile)[0]


# --- R1: rounding defect in the binary64 profile (truncation) -----------------
# Same defect as A's mutant "M2 binary64 truncation" in tests/test_ported_hard_cases.py.

def _scaled(num, den, shift):
    k = num.bit_length() - den.bit_length()
    if not P._ge_pow2(num, den, k):
        k -= 1
    e = max(k + shift - 52, P._EMIN)
    t = shift - e
    return (num << t, den, e) if t >= 0 else (num, den << -t, e)


def _truncate(sign, num, den, shift):
    num, den, e = _scaled(num, den, shift)
    return P._encode(sign, num // den, e)


@contextlib.contextmanager
def rounding_defect_r1():
    orig = P._round
    P._round = _truncate
    try:
        yield
    finally:
        P._round = orig


__all__ = ["MUTANTS", "program", "run", "sut", "rounding_defect_r1", "VMHalt"]
