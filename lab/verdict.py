"""Verdict vocabulary. Excerpt of A's c1b1_replay/types.py (see PROVENANCE.json).

Only the three-way verdict and the two exception kinds are kept. A computational
VALID is not designer approval.
"""
from enum import Enum


class Verdict(str, Enum):
    VALID = "VALID"
    INVALID = "INVALID"
    REFUSED = "REFUSED"


class Invalid(Exception):
    pass


class Refused(Exception):
    pass
