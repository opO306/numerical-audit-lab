"""Gate 1 state and exact transforms (checker side; never imports numeric_core).

All values are Fractions; vectors are (x, y) tuples. Nothing here computes a
collision -- that is the job of the system under test and of each reference.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

Vec = tuple


class SutHalt(Exception):
    """The system under test stopped without an answer (e.g. division by zero)."""


@dataclass(frozen=True)
class State:
    m1: Fraction
    m2: Fraction
    r1: Vec
    r2: Vec
    v1: Vec
    v2: Vec


@dataclass(frozen=True)
class Out:
    v1: Vec
    v2: Vec
    ke: Fraction


def F(x) -> Fraction:
    return x if isinstance(x, Fraction) else Fraction(x)


def vec(x, y) -> Vec:
    return (F(x), F(y))


def add(a, b): return (a[0] + b[0], a[1] + b[1])
def sub(a, b): return (a[0] - b[0], a[1] - b[1])
def scale(c, a): return (c * a[0], c * a[1])
def neg(a): return (-a[0], -a[1])
def dot(a, b): return a[0] * b[0] + a[1] * b[1]
def cross(a, b): return a[0] * b[1] - a[1] * b[0]
def rot90(a): return (-a[1], a[0])


# --- transforms used by the metamorphic checks --------------------------------

def swap(s: State) -> State:
    return State(s.m2, s.m1, s.r2, s.r1, s.v2, s.v1)


def translate(s: State, a: Vec) -> State:
    return State(s.m1, s.m2, add(s.r1, a), add(s.r2, a), s.v1, s.v2)


def rotate(s: State) -> State:
    return State(s.m1, s.m2, rot90(s.r1), rot90(s.r2), rot90(s.v1), rot90(s.v2))


def boost(s: State, V: Vec) -> State:
    return State(s.m1, s.m2, s.r1, s.r2, add(s.v1, V), add(s.v2, V))


def reversed_after(s: State, o: Out) -> State:
    """Same contact positions, post-collision velocities reversed."""
    return State(s.m1, s.m2, s.r1, s.r2, neg(o.v1), neg(o.v2))
