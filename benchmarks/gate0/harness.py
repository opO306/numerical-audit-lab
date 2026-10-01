"""Test bench: runs a program on the calculator (numeric_core) and hands the
checker side (lab.claim) only encoded strings.

This is the ONE place where calculator and checker meet. The checker modules
themselves never import numeric_core.
"""
from __future__ import annotations

import time
import tracemalloc
from dataclasses import dataclass, field
from fractions import Fraction

from numeric_core import Binary64Finite, Exact, FixedPoint, Instr, run

from lab.claim import Profile


def make_profile(p: Profile):
    if p.kind == "binary64":
        return Binary64Finite()
    if p.kind == "exact":
        return Exact()
    return FixedPoint(p.width, p.frac_bits)


@dataclass
class Execution:
    profile: Profile
    final: str | None                 # encoded final register, None if halted
    halt: tuple | None
    steps: list                       # [(op, args, result)] encoded, checker-ready
    registers: dict
    op_count: dict
    wall_seconds: float
    peak_python_heap_bytes: int
    extra: dict = field(default_factory=dict)


def _assert_ssa(program: list) -> None:
    seen = set()
    for ins in program:
        if ins.dst is not None:
            if ins.dst in seen:
                raise ValueError(f"register {ins.dst} written twice; step audit needs single assignment")
            seen.add(ins.dst)


def execute(program: list, p: Profile, out: str) -> Execution:
    _assert_ssa(program)
    tracemalloc.start()
    t0 = time.perf_counter()
    res = run(program, make_profile(p))
    wall = time.perf_counter() - t0
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    regs = res.registers
    steps = []
    for ins in program:
        if ins.dst not in regs:          # not reached: the run halted before it
            break
        if ins.op == "CONST":
            lit = ins.args[0]
            steps.append(("CONST", (str(lit) if not isinstance(lit, Fraction) else f"{lit.numerator}/{lit.denominator}",),
                          regs[ins.dst]))
        elif ins.op == "DOT":
            xs, ys = ins.args
            steps.append(("DOT", (tuple(regs[a] for a in xs), tuple(regs[a] for a in ys)), regs[ins.dst]))
        else:
            steps.append((ins.op, tuple(regs[a] for a in ins.args), regs[ins.dst]))
    final = None if res.halt else regs[out]
    return Execution(p, final, res.halt, steps, regs, dict(res.op_count), wall, peak)


__all__ = ["Instr", "Execution", "execute", "make_profile"]
