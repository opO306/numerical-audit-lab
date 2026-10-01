"""A-Numeric VM 0.2 (docs/current/A_NUMERIC_EXECUTION_STACK_V1.md, section 3; 0.2 adds EXP, 3.9).

A small, slow, executable definition of what A's arithmetic means. It runs
straight-line programs over named registers under one number profile.

What is deliberately ABSENT (section 2: forbid by absence, not by detection):
no instruction reads a label or identity, draws a random number, reads a clock
or a thread index, or switches overflow checking off. Register names are only
addresses; no instruction can observe them.

Every program and input is checked completely before anything runs; a bad one
ends in the single canonical rejection VMRejected, never in a host error.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
from dataclasses import dataclass, field
from fractions import Fraction

from .profiles import VMHalt, VMRejected, _as_exact

ANVM_VERSION = "0.2"

# The meaning of each instruction, as frozen text. SPEC_HASH goes into every
# result so results of different meanings are never compared as if equal.
SPEC = {
    "version": ANVM_VERSION,
    "general": "every instruction computes the exact result of its represented inputs and rounds ONCE by the profile "
               "(FX: nearest-even on 2**F, range [-2**(W-1), 2**(W-1)-1]; A-Binary64-Finite: nearest-even to finite "
               "binary64, subnormals kept; EXACT: no rounding). Leaving the profile's range halts with a reason.",
    "CONST": "exact literal (int, Fraction, 'n/d'; never float/bool) rounded once",
    "ADD SUB MUL DIV": "exact binary result rounded once; DIV by zero halts",
    "NEG ABS": "exact; FX may halt at the negative end of the range",
    "SQRT": "exact square root rounded once; negative halts; sqrt(-0) = -0",
    "EXP": "deterministic_exp_v1: the exact mathematical e^x of the represented input, rounded once; overflow halts; "
           "a result below half the smallest step rounds to +0; exp(+-0) = 1. A value, not an algorithm. EXACT lacks it",
    "SUM": "exact sum of all represented terms, rounded once; order of terms cannot matter; "
           "binary64 zero sign: -0 only if every term is -0",
    "DOT": "exact products, exact sum, rounded once; order of axes cannot matter; "
           "binary64 zero sign: -0 only if every product is -0",
    "CMP": "exact comparison of the represented values; records represented_margin = |a - b| between the "
           "REPRESENTED values (not the mathematical values before rounding)",
    "absent": "no instruction reads labels, identities, randomness, clocks, thread or block indices",
}
SPEC_HASH = hashlib.sha256(json.dumps(SPEC, sort_keys=True).encode()).hexdigest()


def _implementation_digest() -> str:
    here = pathlib.Path(__file__).parent
    h = hashlib.sha256()
    for name in ("profiles.py", "vm.py", "exp.py"):
        h.update((here / name).read_bytes().replace(b"\r\n", b"\n"))
    return h.hexdigest()


IMPLEMENTATION_DIGEST = _implementation_digest()

OPCODES = frozenset({"CONST", "ADD", "SUB", "MUL", "DIV", "NEG", "ABS", "SQRT", "EXP", "CMP", "SUM", "DOT"})
_BINARY = {"ADD": "add", "SUB": "sub", "MUL": "mul", "DIV": "div"}
_UNARY = {"NEG": "neg", "ABS": "abs", "SQRT": "sqrt", "EXP": "exp"}
# capability each opcode needs from the profile (SUM and DOT are exact accumulations)
_NEEDS = {"CONST": set(), "SUM": {"ADD"}, "DOT": {"ADD", "MUL"}}


@dataclass(frozen=True)
class Instr:
    op: str
    dst: str | None
    args: tuple


@dataclass(frozen=True)
class Branch:
    """A comparison that could steer causality later. represented_margin is the exact
    distance between the two REPRESENTED values; whether rounding could have decided
    the branch needs an error bound from the reference calculator (R1) as well."""
    pc: int
    result: int
    represented_margin: Fraction


@dataclass
class RunResult:
    profile: str
    program_digest: str
    input_digest: str
    registers: dict
    branches: list = field(default_factory=list)
    halt: tuple | None = None            # (pc, reason) -- a halt is a canonical result
    op_count: dict = field(default_factory=dict)

    def canonical(self) -> dict:
        return {"vm_version": ANVM_VERSION, "spec_hash": SPEC_HASH, "profile": self.profile,
                "program_digest": self.program_digest, "input_digest": self.input_digest,
                "registers": dict(sorted(self.registers.items())),
                "branches": [[b.pc, b.result, f"{b.represented_margin.numerator}/{b.represented_margin.denominator}"]
                             for b in self.branches],
                "halt": list(self.halt) if self.halt else None}

    def digest(self) -> str:
        text = json.dumps(self.canonical(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(text.encode()).hexdigest()


def _digest(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def program_digest(program) -> str:
    return _digest([[i.op, i.dst, [list(a) if isinstance(a, tuple) else str(a) for a in i.args]] for i in program])


def _is_name(x) -> bool:
    return type(x) is str and x != ""


def validate(program, profile, inputs=None) -> None:
    """Refuse everything that could make a run end in a host error or depend on
    something outside A's meaning. Raises VMRejected(code)."""
    inputs = {} if inputs is None else inputs
    if not isinstance(inputs, dict):
        raise VMRejected("bad_inputs", "inputs must be a mapping of register -> raw value")
    for name, raw in inputs.items():
        if not _is_name(name):
            raise VMRejected("bad_register", repr(name))
        if not profile.valid_raw(raw):
            raise VMRejected("bad_input_value", f"{name} = {raw!r} is not a finite in-range {profile.name} value")
    if not isinstance(program, (list, tuple)):
        raise VMRejected("bad_program", "a program is a sequence of Instr")
    defined = set(inputs)

    def reads(pc, names):
        for n in names:
            if not _is_name(n):
                raise VMRejected("bad_register", f"pc {pc}: {n!r}")
            if n not in defined:
                raise VMRejected("undefined_register", f"pc {pc}: {n}")

    for pc, ins in enumerate(program):
        if not isinstance(ins, Instr) or ins.op not in OPCODES or not isinstance(ins.args, tuple):
            raise VMRejected("unknown_instruction", f"pc {pc}: {ins!r}")
        missing = _NEEDS.get(ins.op, {ins.op}) - profile.capabilities
        if missing:
            raise VMRejected("unsupported_operation", f"pc {pc}: {ins.op} needs {sorted(missing)}; {profile.name} lacks it")
        if ins.op == "CMP":
            if ins.dst is not None:
                raise VMRejected("bad_destination", f"pc {pc}: CMP writes no register")
        elif not _is_name(ins.dst):
            raise VMRejected("bad_destination", f"pc {pc}: {ins.dst!r}")
        n = len(ins.args)
        if ins.op == "CONST":
            if n != 1:
                raise VMRejected("bad_arity", f"pc {pc}")
            try:
                _as_exact(ins.args[0])
            except (TypeError, ValueError, ZeroDivisionError) as e:
                raise VMRejected("bad_literal", f"pc {pc}: {e}") from None
        elif ins.op in _BINARY or ins.op == "CMP":
            if n != 2:
                raise VMRejected("bad_arity", f"pc {pc}")
            reads(pc, ins.args)
        elif ins.op in _UNARY:
            if n != 1:
                raise VMRejected("bad_arity", f"pc {pc}")
            reads(pc, ins.args)
        elif ins.op == "SUM":
            if n < 1:
                raise VMRejected("bad_arity", f"pc {pc}: SUM needs at least one term")
            reads(pc, ins.args)
        elif ins.op == "DOT":
            if n != 2 or not all(isinstance(v, tuple) for v in ins.args):
                raise VMRejected("bad_arity", f"pc {pc}: DOT takes two vectors")
            xs, ys = ins.args
            if len(xs) != len(ys) or not xs:
                raise VMRejected("bad_arity", f"pc {pc}: DOT needs two equal, non-empty vectors")
            reads(pc, xs + ys)
        if ins.dst is not None:
            defined.add(ins.dst)


def run(program, profile, inputs=None) -> RunResult:
    validate(program, profile, inputs)
    regs = dict(inputs or {})
    result = RunResult(profile.name, program_digest(program),
                       _digest({k: profile.encode(v) for k, v in regs.items()}), {})
    counts: dict = {}
    for pc, ins in enumerate(program):
        counts[ins.op] = counts.get(ins.op, 0) + 1
        try:
            if ins.op == "CONST":
                regs[ins.dst] = profile.from_exact(ins.args[0])
            elif ins.op in _BINARY:
                regs[ins.dst] = getattr(profile, _BINARY[ins.op])(regs[ins.args[0]], regs[ins.args[1]])
            elif ins.op in _UNARY:
                regs[ins.dst] = getattr(profile, _UNARY[ins.op])(regs[ins.args[0]])
            elif ins.op == "SUM":
                regs[ins.dst] = profile.sum([regs[a] for a in ins.args])
            elif ins.op == "DOT":
                xs, ys = ins.args
                regs[ins.dst] = profile.dot([regs[a] for a in xs], [regs[a] for a in ys])
            elif ins.op == "CMP":
                a, b = regs[ins.args[0]], regs[ins.args[1]]
                margin = abs(profile.to_exact(a) - profile.to_exact(b))
                result.branches.append(Branch(pc, profile.cmp(a, b), margin))
        except VMHalt as halt:
            result.halt = (pc, halt.reason)
            break
    result.registers = {k: profile.encode(v) for k, v in regs.items()}
    result.op_count = counts
    return result
