"""Gate 2A system under test: velocity Verlet for the Henon-Heiles Hamiltonian, as a
numeric_core program (docs/GATE2A_PLAN.md section 2). One VM run = one step.

H = (px^2 + py^2)/2 + (x^2 + y^2)/2 + x^2 y - y^3/3   (Henon & Heiles 1964; Wikipedia)
Planted defects D2, D3 (plan section 5) are variants of the step program; D1 is the
binary64 rounding defect from Gate 1.
"""
from __future__ import annotations

import struct
from fractions import Fraction

from numeric_core import Binary64Finite, Exact, Instr, run

from ..gate1.collision import rounding_defect_r1

H_STEP = Fraction(1, 64)
STATE = ("x", "y", "px", "py")
OUT = {"x": "x1", "y": "y1", "px": "px1", "py": "py1"}
DEFECTS = (None, "D1", "D2", "D3")


def _force(sx, sy, t, defect):
    I = Instr
    p = [I("MUL", f"xy{t}", (sx, sy)), I("MUL", f"txy{t}", ("two", f"xy{t}")), I("NEG", f"nx{t}", (sx,)),
         I("SUB", f"ax{t}", (f"nx{t}", f"txy{t}")),
         I("MUL", f"xx{t}", (sx, sx)), I("MUL", f"yy{t}", (sy, sy)), I("NEG", f"ny{t}", (sy,)),
         I("SUB", f"u{t}", (f"ny{t}", f"xx{t}"))]
    p.append(I("SUB" if defect == "D3" else "ADD", f"ay{t}", (f"u{t}", f"yy{t}")))     # D3: -y - x^2 - y^2
    return p


def step_program(defect: str | None = None) -> list:
    if defect not in DEFECTS:
        raise ValueError(defect)
    I = Instr
    p = [I("CONST", "h", ("1/64",)), I("CONST", "hh", ("1/128",)), I("CONST", "two", (2,))]
    p += _force("x", "y", "0", defect)
    p += [I("MUL", "kx", ("hh", "ax0")), I("ADD", "pxh", ("px", "kx")),
          I("MUL", "ky", ("hh", "ay0")), I("ADD", "pyh", ("py", "ky"))]
    vx, vy = ("px", "py") if defect == "D2" else ("pxh", "pyh")                       # D2: drift with p, not p-half
    p += [I("MUL", "dx", ("h", vx)), I("ADD", "x1", ("x", "dx")),
          I("MUL", "dy", ("h", vy)), I("ADD", "y1", ("y", "dy"))]
    p += _force("x1", "y1", "1", defect)
    p += [I("MUL", "kx1", ("hh", "ax1")), I("ADD", "px1", ("pxh", "kx1")),
          I("MUL", "ky1", ("hh", "ay1")), I("ADD", "py1", ("pyh", "ky1"))]
    return p


def structure(defect: str | None = None) -> list:
    """The step program as plain tuples for the checker side: (op, dst, args, literal)."""
    return [(i.op, i.dst, i.args if i.op != "CONST" else (), str(i.args[0]) if i.op == "CONST" else None)
            for i in step_program(defect)]


def bits(v: float) -> int:
    return struct.unpack(">Q", struct.pack(">d", v))[0]


class Binary64Stepper:
    """Runs one VM step at a time; returns every register's binary64 bit pattern."""

    def __init__(self, defect: str | None = None):
        self.defect = defect
        self.program = step_program(defect)
        self.profile = Binary64Finite()

    def step(self, state_bits: dict) -> dict:
        if self.defect == "D1":
            with rounding_defect_r1():
                r = run(self.program, self.profile, state_bits)
        else:
            r = run(self.program, self.profile, state_bits)
        if r.halt:
            raise RuntimeError(f"VM halted: {r.halt}")
        return {k: int(v, 16) for k, v in r.registers.items()}


def exact_steps(state: dict, k: int, defect: str | None = None) -> list:
    """The same discrete program in exact arithmetic, k steps from an exact (Fraction) state."""
    import sys
    if hasattr(sys, "set_int_max_str_digits"):        # the VM encodes exact values as text; numerators grow ~2x per step
        sys.set_int_max_str_digits(0)
    prog, prof, out = step_program(defect), Exact(), []
    for _ in range(k):
        r = run(prog, prof, state)
        state = {s: Fraction(r.registers[OUT[s]]) for s in STATE}
        out.append(state)
    return out
