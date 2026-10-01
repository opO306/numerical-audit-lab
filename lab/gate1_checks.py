"""Gate 1 checks C1-C10 (+C4b). docs/GATE1_PLAN.md (sealed) defines each one.

Checker side: never imports numeric_core. The system under test (SUT) is handed
in as a callable State -> Out that may raise SutHalt. Every check is its own
code path; none calls another check or a shared collision evaluator.

Each check returns (detected: bool, note: str). "Detected" means the check
raised an alarm; on the correct program it must never do so.
"""
from __future__ import annotations

from fractions import Fraction

from .gate1_state import (Out, State, SutHalt, add, boost, cross, dot, neg, reversed_after, rot90, rotate, scale,
                          sub, swap, translate)

SHIFT = (Fraction(101, 7), Fraction(-53, 3))
BOOST = (Fraction(13, 5), Fraction(-7, 4))
HALF = Fraction(1, 2)


def _same(o: Out, v1, v2, ke) -> bool:
    return o.v1 == v1 and o.v2 == v2 and o.ke == ke


# --- C1: reference by the impulse formula --------------------------------------

def reference_impulse(s: State) -> Out:
    d = sub(s.r2, s.r1)
    rel = sub(s.v1, s.v2)
    J = scale(2 * s.m1 * s.m2 / (s.m1 + s.m2) * dot(rel, d) / dot(d, d), d)     # impulse on particle 2
    v1 = sub(s.v1, scale(1 / s.m1, J))
    v2 = add(s.v2, scale(1 / s.m2, J))
    return Out(v1, v2, (s.m1 * dot(v1, v1) + s.m2 * dot(v2, v2)) / 2)


def c1_reference_impulse(s, sut, o):
    r = reference_impulse(s)
    return (not _same(o, r.v1, r.v2, r.ke), "differs from impulse-formula reference")


# --- C2: reference in the centre-of-mass frame ---------------------------------

def reference_com(s: State) -> Out:
    M = s.m1 + s.m2
    Vc = ((s.m1 * s.v1[0] + s.m2 * s.v2[0]) / M, (s.m1 * s.v1[1] + s.m2 * s.v2[1]) / M)
    n = (s.r2[0] - s.r1[0], s.r2[1] - s.r1[1])
    nn = n[0] * n[0] + n[1] * n[1]
    outs = []
    for v in (s.v1, s.v2):
        u = (v[0] - Vc[0], v[1] - Vc[1])
        un = (u[0] * n[0] + u[1] * n[1]) / nn
        outs.append((u[0] - 2 * un * n[0], u[1] - 2 * un * n[1]))           # mirror the normal part
    ke = M * (Vc[0] ** 2 + Vc[1] ** 2) / 2 + sum(m * (u[0] ** 2 + u[1] ** 2) for m, u in zip((s.m1, s.m2), outs)) / 2
    return Out((outs[0][0] + Vc[0], outs[0][1] + Vc[1]), (outs[1][0] + Vc[0], outs[1][1] + Vc[1]), ke)


def c2_reference_com(s, sut, o):
    r = reference_com(s)
    return (not _same(o, r.v1, r.v2, r.ke), "differs from centre-of-mass reference")


# --- C3, C4, C4b: conservation, no reference answer ----------------------------

def c3_momentum(s, sut, o):
    before = add(scale(s.m1, s.v1), scale(s.m2, s.v2))
    after = add(scale(s.m1, o.v1), scale(s.m2, o.v2))
    return (after != before, "total momentum changed")


def c4_kinetic_energy(s, sut, o):
    before = s.m1 * dot(s.v1, s.v1) + s.m2 * dot(s.v2, s.v2)
    after = s.m1 * dot(o.v1, o.v1) + s.m2 * dot(o.v2, o.v2)
    return (after != before, "kinetic energy (recomputed from SUT velocities) changed")


def c4b_reported_energy(s, sut, o):
    before = HALF * (s.m1 * dot(s.v1, s.v1) + s.m2 * dot(s.v2, s.v2))
    return (o.ke != before, "SUT-reported KE' differs from KE before")


# --- C5-C9: relations between SUT runs ----------------------------------------

def c5_swap(s, sut, o):
    w = sut(swap(s))
    return (not _same(w, o.v2, o.v1, o.ke), "relabelling the particles changed the physics")


def c6_translation(s, sut, o):
    w = sut(translate(s, SHIFT))
    return (not _same(w, o.v1, o.v2, o.ke), "moving both discs changed the result")


def c7_rotation(s, sut, o):
    w = sut(rotate(s))
    return (not _same(w, rot90(o.v1), rot90(o.v2), o.ke), "rotating the input did not rotate the output")


def c8_boost(s, sut, o):
    w = sut(boost(s, BOOST))
    P = add(scale(s.m1, o.v1), scale(s.m2, o.v2))
    ke = o.ke + dot(BOOST, P) + HALF * (s.m1 + s.m2) * dot(BOOST, BOOST)
    return (not _same(w, add(o.v1, BOOST), add(o.v2, BOOST), ke), "a moving observer sees different physics")


def c9_time_reversal(s, sut, o):
    w = sut(reversed_after(s, o))
    return (not _same(w, neg(s.v1), neg(s.v2), o.ke), "running the collision backwards does not undo it")


# --- C10: characterization -- conditions the answer must meet, no answer computed

def c10_characterization(s, sut, o):
    d = sub(s.r2, s.r1)
    along = cross(sub(o.v1, s.v1), d) == 0 and cross(sub(o.v2, s.v2), d) == 0
    restitution = dot(sub(o.v1, o.v2), d) == -dot(sub(s.v1, s.v2), d)
    if not along:
        return True, "velocity change not along the line of centres (friction-like)"
    return (not restitution, "normal relative velocity not exactly reversed (e != 1)")


CHECKS = {
    "C1": c1_reference_impulse, "C2": c2_reference_com, "C3": c3_momentum, "C4": c4_kinetic_energy,
    "C4b": c4b_reported_energy, "C5": c5_swap, "C6": c6_translation, "C7": c7_rotation, "C8": c8_boost,
    "C9": c9_time_reversal, "C10": c10_characterization,
}
ORACLE_FREE = ("C3", "C4", "C4b", "C5", "C6", "C7", "C8", "C9", "C10")


def run_check(name: str, s: State, sut) -> tuple:
    """(detected, note). A halt of the SUT on a valid input counts as detected."""
    try:
        o = sut(s)
        return CHECKS[name](s, sut, o)
    except SutHalt as h:
        return True, f"SUT halted: {h}"
