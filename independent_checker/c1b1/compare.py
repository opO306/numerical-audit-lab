"""Exact value comparison, including failures and input mutation evidence."""
from dataclasses import dataclass, fields, is_dataclass
from fractions import Fraction
from .contracts import Ratio, LabRefusal, SCOPE, J_STATUS, SPEC_SHA256
from . import exact_slow, exact_fast


@dataclass(frozen=True)
class Outcome:
    value: object
    exception_type: str = ""
    scope: str = SCOPE
    j_status: str = J_STATUS


@dataclass(frozen=True)
class Comparison:
    match: bool
    differences: tuple
    slow: Outcome
    fast: Outcome
    scope: str = SCOPE
    j_status: str = J_STATUS
    spec_sha256: str = SPEC_SHA256


def capture(function, *args):
    try:
        return Outcome(function(*args))
    except LabRefusal as exc:
        return Outcome(exc.failure, type(exc).__name__)


def differences(left, right, path="result"):
    if isinstance(left, (Ratio, Fraction)) and isinstance(right, (Ratio, Fraction)):
        equal = left.numerator * right.denominator == right.numerator * left.denominator
        return () if equal else (path,)
    if type(left) is not type(right):
        return (path + ":type",)
    if is_dataclass(left):
        return tuple(item for field in fields(left) for item in
                     differences(getattr(left, field.name), getattr(right, field.name), path + "." + field.name))
    if isinstance(left, tuple):
        if len(left) != len(right):
            return (path + ":length",)
        return tuple(item for i, (a, b) in enumerate(zip(left, right)) for item in differences(a, b, f"{path}[{i}]"))
    return () if left == right else (path,)


def _compare(slow, fast, request, *args):
    before = repr(request)
    slow_result = capture(slow, request, *args)
    mutated_slow = repr(request) != before
    fast_before = repr(request)
    fast_result = capture(fast, request, *args)
    changed = differences(slow_result, fast_result)
    if mutated_slow:
        changed += ("slow:INPUT_MUTATED",)
    if repr(request) != fast_before:
        changed += ("fast:INPUT_MUTATED",)
    return Comparison(not changed, changed, slow_result, fast_result)


def compare_drift(request, threshold=None):
    if threshold is None:
        return _compare(exact_slow.drift, exact_fast.drift, request)
    return _compare(exact_slow.guarded_drift, exact_fast.guarded_drift, request, threshold)


def compare_kick(request):
    return _compare(exact_slow.kick, exact_fast.kick, request)
