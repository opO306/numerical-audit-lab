"""Gate 2B replay T: gala 1.12.0's Cython leapfrog + HenonHeilesPotential gradient, transcribed
operation by operation into a numeric_core program (docs/GATE2B_PLAN.md, W1).

Source transcribed (sdist 68d80d4f..., read-only):
  builtin_potentials.cpp   grad[0] = grad[0] + q[0] + 2*q[0]*q[1]
                           grad[1] = grad[1] + q[1] + q[0]*q[0] - q[1]*q[1]      (grad zeroed first)
  leapfrog.pyx  init       v_half = v - grad*dt/2.
                step       x = x + v_half*dt ; grad(x) ; v_out = v_half - grad*dt/2. ; v_half = v_half - grad*dt
C evaluates left to right: ((g + q0) + ((2*q0)*q1)), (((g + q1) + q0*q0) - q1*q1), ((grad*dt)/2.).
(grad*dt)/2. is written as MUL by 1/2: both round the same exact value x/2 (exact unless subnormal).
"""
from __future__ import annotations

from fractions import Fraction

from numeric_core import Binary64Finite, Exact, Instr, run

DT = Fraction(1, 64)


def _grad(sx, sy, t):
    I = Instr
    return [I("ADD", f"a{t}", ("gz", sx)), I("MUL", f"tx{t}", ("two", sx)), I("MUL", f"txy{t}", (f"tx{t}", sy)),
            I("ADD", f"g0{t}", (f"a{t}", f"txy{t}")),
            I("ADD", f"b{t}", ("gz", sy)), I("MUL", f"xx{t}", (sx, sx)), I("ADD", f"c{t}", (f"b{t}", f"xx{t}")),
            I("MUL", f"yy{t}", (sy, sy)), I("SUB", f"g1{t}", (f"c{t}", f"yy{t}"))]


def _consts():
    I = Instr
    return [I("CONST", "dt", ("1/64",)), I("CONST", "half", ("1/2",)), I("CONST", "two", (2,)), I("CONST", "gz", (0,))]


def init_program() -> list:
    """(x, y, vx, vy) -> v_half (vhx, vhy)."""
    I = Instr
    p = _consts() + _grad("x", "y", "i")
    p += [I("MUL", "gdx", ("g0i", "dt")), I("MUL", "kx", ("gdx", "half")), I("SUB", "vhx", ("vx", "kx")),
          I("MUL", "gdy", ("g1i", "dt")), I("MUL", "ky", ("gdy", "half")), I("SUB", "vhy", ("vy", "ky"))]
    return p


def step_program() -> list:
    """(x, y, vhx, vhy) -> x1, y1, vox, voy (gala's output velocity), vhx1, vhy1."""
    I = Instr
    p = _consts()
    p += [I("MUL", "dxs", ("vhx", "dt")), I("ADD", "x1", ("x", "dxs")),
          I("MUL", "dys", ("vhy", "dt")), I("ADD", "y1", ("y", "dys"))]
    p += _grad("x1", "y1", "s")
    p += [I("MUL", "gdx", ("g0s", "dt")), I("MUL", "kx", ("gdx", "half")), I("SUB", "vox", ("vhx", "kx")),
          I("SUB", "vhx1", ("vhx", "gdx")),
          I("MUL", "gdy", ("g1s", "dt")), I("MUL", "ky", ("gdy", "half")), I("SUB", "voy", ("vhy", "ky")),
          I("SUB", "vhy1", ("vhy", "gdy"))]
    return p


def structure(program: list) -> list:
    return [(i.op, i.dst, i.args if i.op != "CONST" else (), str(i.args[0]) if i.op == "CONST" else None)
            for i in program]


class Replay:
    """binary64 (bit patterns in/out) or exact (Fractions in/out) execution of T."""

    def __init__(self, exact: bool = False):
        self.prof = Exact() if exact else Binary64Finite()
        self.exact = exact
        self.init_p, self.step_p = init_program(), step_program()

    def _run(self, prog, inputs):
        r = run(prog, self.prof, inputs)
        if r.halt:
            raise RuntimeError(f"VM halted: {r.halt}")
        if self.exact:
            return {k: Fraction(v) for k, v in r.registers.items()}
        return {k: int(v, 16) for k, v in r.registers.items()}

    def init(self, x, y, vx, vy) -> dict:
        return self._run(self.init_p, {"x": x, "y": y, "vx": vx, "vy": vy})

    def step(self, x, y, vhx, vhy) -> dict:
        return self._run(self.step_p, {"x": x, "y": y, "vhx": vhx, "vhy": vhy})
