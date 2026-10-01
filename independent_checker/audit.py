"""Run an executor over the hard cases and collect every disagreement with the judge.

An executor is any object with methods add sub mul div sqrt (patterns in,
pattern out), sum(list) and dot(xs, ys). A halt is reported by returning the
halt reason as a str. The audit never imports the thing it audits.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from .hard_cases import Case, binary64_cases, exact_of, fx_exhaustive_pairs, fx_wide_ties
from .oracle import SIGN, judge, judge_fx, judge_fx_sqrt, judge_sqrt, value


@dataclass(frozen=True)
class Finding:
    case: Case | tuple
    got: object
    problem: str


def _zero_sign(case: Case) -> int:
    """Sign bit an exact-zero result must carry (IEEE for + - * /, the VM spec for SUM/DOT)."""
    a = case.args
    neg0 = lambda b: b == SIGN                                    # noqa: E731
    if case.op == "add":
        return int(neg0(a[0]) and neg0(a[1]))
    if case.op == "sub":
        return int(neg0(a[0]) and a[1] == 0)
    if case.op in ("mul", "div"):
        return (a[0] >> 63) ^ (a[1] >> 63)
    if case.op == "sum":
        return int(all(neg0(b) for b in a))
    if case.op == "dot":
        xs, ys = a
        return int(all(value(p) * value(q) == 0 and (p >> 63) ^ (q >> 63) for p, q in zip(xs, ys)))
    raise ValueError(case.op)


def check_case(case: Case, got) -> str | None:
    halted = isinstance(got, str)
    if halted and got != "overflow" and not (case.op == "sqrt" and got == "sqrt_of_negative"):
        return f"unexpected halt {got!r}"
    result = None if halted else got
    exact = exact_of(case)
    if case.op == "sqrt":
        if halted and got == "sqrt_of_negative":
            return None if exact < 0 else "sqrt_of_negative on a non-negative radicand"
        if exact == 0 and result is not None and result != case.args[0]:
            return "sqrt(+-0) must keep the zero's sign"
        return judge_sqrt(exact, result)
    problem = judge(exact, result)
    if problem is None and exact == 0 and result >> 63 != _zero_sign(case):
        problem = "wrong sign of zero"
    return problem


def audit_binary64(executor, cases: list[Case] | None = None) -> list[Finding]:
    findings = []
    for case in binary64_cases() if cases is None else cases:
        if case.op == "dot":
            got = executor.dot(*case.args)
        elif case.op == "sum":
            got = executor.sum(list(case.args))
        else:
            got = getattr(executor, case.op)(*case.args)
        problem = check_case(case, got)
        if problem:
            findings.append(Finding(case, got, problem))
    return findings


def _fx_check(op, a, b, got, width, frac_bits):
    x = Fraction(a, 2 ** frac_bits)
    if op == "sqrt":
        if got == "sqrt_of_negative":
            return None if x < 0 else "sqrt_of_negative on a non-negative radicand"
        if isinstance(got, str) and got != "overflow":
            return f"unexpected halt {got!r}"
        return judge_fx_sqrt(x, None if isinstance(got, str) else got, width, frac_bits)
    if op == "div" and b == 0:
        return None if got == "division_by_zero" else "division by zero must halt"
    if isinstance(got, str) and got != "overflow":
        return f"unexpected halt {got!r}"
    y = Fraction(b, 2 ** frac_bits)
    exact = x * y if op == "mul" else x / y
    return judge_fx(exact, None if isinstance(got, str) else got, width, frac_bits)


def audit_fx_exhaustive(executor, width: int, frac_bits: int) -> list[Finding]:
    """Every pair of a small format: MUL, DIV; every value: SQRT."""
    findings = []
    lo, hi = -(1 << (width - 1)), (1 << (width - 1)) - 1
    for a, b in fx_exhaustive_pairs(width):
        for op in ("mul", "div"):
            got = getattr(executor, op)(a, b)
            problem = _fx_check(op, a, b, got, width, frac_bits)
            if problem:
                findings.append(Finding((op, a, b), got, problem))
    for a in range(lo, hi + 1):
        got = executor.sqrt(a)
        problem = _fx_check("sqrt", a, None, got, width, frac_bits)
        if problem:
            findings.append(Finding(("sqrt", a), got, problem))
    return findings


def audit_fx_wide(executor, width: int, frac_bits: int) -> list[Finding]:
    findings = []
    for op, a, b in fx_wide_ties(width, frac_bits):
        got = getattr(executor, op)(a, b)
        problem = _fx_check(op, a, b, got, width, frac_bits)
        if problem:
            findings.append(Finding((op, a, b), got, problem))
    return findings
