"""R1-0: independent judge of A-Numeric arithmetic on hard inputs.

Must not import a_numeric or engine (tests/test_audit_numeric_hard_cases.py
enforces it): an executor is handed in as plain callables, so a defect in the
VM's rounding cannot also sit inside its judge.
"""
from .audit import Finding, audit_binary64, audit_fx_exhaustive, audit_fx_wide
from .hard_cases import Case, binary64_cases, exact_of
from .oracle import judge, judge_sqrt, tie_position

__all__ = ["Finding", "audit_binary64", "audit_fx_exhaustive", "audit_fx_wide", "Case", "binary64_cases",
           "exact_of", "judge", "judge_sqrt", "tie_position"]
