"""Judge claimed results against an oracle, and audit every step of a run.

This module is on the CHECKER side: it must not import numeric_core
(tests/test_independence.py enforces it). Runs reach it only as plain
encoded strings, so a rounding defect in the calculator cannot also sit
inside its judge.

Encodings (the calculator's own text format, decoded here independently):
  binary64 -> 16 hex digits of the bit pattern
  fx       -> decimal raw integer v meaning v / 2**F
  exact    -> "numerator/denominator"
  None     -> the run halted, no value was produced
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

import mpmath

from independent_checker.oracle import judge, judge_fx, value

from .verdict import Refused, Verdict


@dataclass(frozen=True)
class Profile:
    kind: str                     # "binary64" | "fx" | "exact"
    width: int = 0
    frac_bits: int = 0

    @property
    def label(self) -> str:
        return f"FX({self.width},{self.frac_bits})" if self.kind == "fx" else self.kind


def decode(profile: Profile, encoded: str) -> Fraction:
    if profile.kind == "binary64":
        return value(int(encoded, 16))
    if profile.kind == "fx":
        return Fraction(int(encoded), 1 << profile.frac_bits)
    if profile.kind == "exact":
        return Fraction(encoded)
    raise ValueError(profile.kind)


# ---------------------------------------------------------------------------
# Oracle: several independent ways to the true value must agree, or we refuse.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Oracle:
    value: Fraction
    angles: dict                  # name -> str description of what each angle produced


def settle_oracle(exact_angles: dict, mp_angle: tuple) -> Oracle:
    """exact_angles: name -> Fraction (each from a different derivation).
    mp_angle: (name, mpf value, agree_digits). The benchmark states how many
    digits its high-precision run is expected to keep, leaving headroom for
    error amplification (e.g. Muller's recurrence multiplies rounding error by
    about 20 per step). All exact angles must be identical, and the
    high-precision angle must agree with them to agree_digits. Otherwise REFUSED: the checker
    never picks one of several disagreeing answers."""
    if len(exact_angles) < 2:
        raise Refused("need at least two exact derivations")
    vals = set(exact_angles.values())
    if len(vals) != 1 or not all(isinstance(v, Fraction) for v in vals):
        raise Refused("exact derivations disagree: " + ", ".join(f"{k}={v}" for k, v in exact_angles.items()))
    target = vals.pop()
    name, mp_value, agree_digits = mp_angle
    with mpmath.workdps(agree_digits + 20):
        t = mpmath.mpf(target.numerator) / target.denominator
        tol = mpmath.mpf(10) ** (-agree_digits) * max(abs(t), mpmath.mpf(1))
        if not abs(mpmath.mpf(mp_value) - t) <= tol:
            raise Refused(f"high-precision angle {name} disagrees with exact derivations")
    angles = {k: f"{v.numerator}/{v.denominator}" for k, v in exact_angles.items()}
    angles[name] = mpmath.nstr(mp_value, 25)
    return Oracle(target, angles)


# ---------------------------------------------------------------------------
# Final-value claims
# ---------------------------------------------------------------------------

def judge_claim(oracle: Fraction, profile: Profile, claimed: str | None) -> tuple:
    """Claim: "`claimed` is the profile's correctly rounded value of the true answer".
    Returns (Verdict, reason)."""
    if claimed is None:
        return Verdict.REFUSED, "run halted; no value was claimed"
    if profile.kind == "exact":
        got = Fraction(claimed)
        return (Verdict.VALID, "equals oracle") if got == oracle else (Verdict.INVALID, f"exact claim {got} != oracle")
    if profile.kind == "binary64":
        problem = judge(oracle, int(claimed, 16))
    elif profile.kind == "fx":
        problem = judge_fx(oracle, int(claimed), profile.width, profile.frac_bits)
    else:
        raise ValueError(profile.kind)
    return (Verdict.VALID, "correctly rounded oracle") if problem is None else (Verdict.INVALID, problem)


# ---------------------------------------------------------------------------
# Step audit: was every single operation of the run correctly rounded?
# ---------------------------------------------------------------------------

_EXACT_OPS = {
    "ADD": lambda a, b: a + b,
    "SUB": lambda a, b: a - b,
    "MUL": lambda a, b: a * b,
    "DIV": lambda a, b: a / b,
}


def judge_step(profile: Profile, op: str, args: tuple, result: str) -> str | None:
    """None if `result` is the correctly rounded value of `op` applied EXACTLY to the
    represented inputs; otherwise the problem. args are encoded strings, except
    for CONST whose single arg is the literal ('n/d' or int)."""
    if op == "CONST":
        exact = Fraction(args[0])
    elif op in _EXACT_OPS:
        a, b = (decode(profile, x) for x in args)
        if op == "DIV" and b == 0:
            raise Refused("division by zero step")
        exact = _EXACT_OPS[op](a, b)
    elif op == "SUM":
        exact = sum((decode(profile, x) for x in args), Fraction(0))
    else:
        raise Refused(f"step audit does not cover {op}")
    if profile.kind == "exact":
        return None if Fraction(result) == exact else "exact step mismatch"
    if profile.kind == "binary64":
        return judge(exact, int(result, 16))
    return judge_fx(exact, int(result), profile.width, profile.frac_bits)


def audit_steps(profile: Profile, steps: list) -> list:
    """steps: [(op, args, result)]. Returns [(index, problem)] for every rejected step."""
    return [(i, p) for i, (op, args, res) in enumerate(steps) if (p := judge_step(profile, op, args, res)) is not None]
