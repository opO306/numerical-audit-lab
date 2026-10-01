"""Gate 2B checker side (docs/GATE2B_PLAN.md): B1-B4 on the frozen gala fixture, plus labelled
diagnostics for the W1 cause. Standard library only; never imports numeric_core (lab/independence.py).

Values arrive as uint64 bit patterns (lab/gate2b_fixture.py) and are judged exactly with Fractions.
"""
from __future__ import annotations

import struct
from fractions import Fraction

U = Fraction(1, 2 ** 53)               # unit roundoff, binary64 round-to-nearest
ETA = Fraction(1, 2 ** 1075)           # half the smallest subnormal: absolute error of an underflowing product
DT = 1.0 / 64.0


def fval(b: int) -> float:
    return struct.unpack("<d", struct.pack("<Q", b))[0]


def qval(b: int) -> Fraction:
    return Fraction(fval(b))


def bits(v: float) -> int:
    return struct.unpack("<Q", struct.pack("<d", v))[0]


def gamma(k: int) -> Fraction:
    return k * U / (1 - k * U)


def H(x, y, vx, vy) -> Fraction:
    return (vx * vx + vy * vy) / 2 + (x * x + y * y) / 2 + x * x * y - y ** 3 / 3


def fl(q: Fraction) -> float:
    return float(q)


# --- B1 energy (class II: no method-error bound, so REFUSED; values are information) ---------------

def b1_energy(fwd: list) -> dict:
    n = len(fwd[0])
    e0 = H(*(qval(fwd[c][0]) for c in range(4)))
    worst, at = Fraction(0), 0
    for j in range(n):
        d = abs(H(*(qval(fwd[c][j]) for c in range(4))) - e0)
        if d > worst:
            worst, at = d, j
    return {"verdict": "REFUSED", "reason": "class II: no rigorous method-error bound (layer B not certified)",
            "E0": fl(e0), "max_abs_dE": fl(worst), "max_rel_dE": fl(worst / e0) if e0 else None, "at_step": at}


# --- B2 time reversal (class I; derivation 1) -----------------------------------------------------

def b2_reversal(fwd: list, ends: list, Ls) -> list:
    target = [qval(fwd[0][0]), qval(fwd[1][0]), -qval(fwd[2][0]), -qval(fwd[3][0])]
    out = []
    for L, row in zip(Ls, ends):
        res = [qval(row[c]) - target[c] for c in range(4)]
        zero = all(r == 0 for r in res)
        out.append({"L": L, "residual": [fl(r) for r in res], "max_abs_residual": fl(max(abs(r) for r in res)),
                    "verdict": "PASS" if zero else "REFUSED",
                    "reason": "residual exactly 0" if zero else
                              "nonzero residual needs a bound; black box gives none (W3 needs W2)"})
    return out


# --- B3 mirror (class I: exact symmetry of round-to-nearest under x -> -x) --------------------------

def b3_mirror(fwd: list, mir: list) -> dict:
    sign = (-1, 1, -1, 1)
    n = len(fwd[0])
    first, count, signed_zero = None, 0, 0
    for j in range(n):
        bad = False
        for c in range(4):
            a, m = fval(fwd[c][j]), fval(mir[c][j])
            if m != sign[c] * a:                     # value comparison: -0.0 == 0.0
                bad = True
            elif m == 0.0 and bits(m) != bits(sign[c] * a):
                signed_zero += 1
        if bad:
            count += 1
            first = j if first is None else first
    return {"verdict": "PASS" if count == 0 else "FAIL", "steps_compared": n, "mismatched_steps": count,
            "first_mismatch": first, "signed_zero_bit_differences": signed_zero,
            "reason": "mirror equals reflected trajectory exactly at every step" if count == 0 else
                      "class I symmetry broken; must be reconfirmed before any defect claim"}


# --- B4 local force law (class I, source-informed bound) -------------------------------------------
# comp0 = q0 + 2 q0 q1 : one rounded product (doubling is exact), one rounded add (0 + q0 is exact)
# comp1 = q1 + q0^2 - q1^2 : two rounded products, two rounded adds/subs
# Any binary tree over three terms has depth <= 2, so these bounds hold for every evaluation order
# (the wheel's machine code reassociates comp1; see docs/GATE2B_RESULT.md). Underflow: each product
# may add ETA absolutely (gradual underflow; additions of subnormals are exact).

def b4_bounds(x: Fraction, y: Fraction) -> tuple:
    return (gamma(2) * (abs(x) + 2 * abs(x * y)) + 2 * ETA,
            gamma(3) * (abs(y) + x * x + y * y) + 3 * ETA)


def b4_force_law(fwd: list, grad: list) -> dict:
    n = len(fwd[0])
    viol, worst = 0, Fraction(0)
    first = None
    for j in range(n):
        x, y = qval(fwd[0][j]), qval(fwd[1][j])
        exact = (x + 2 * x * y, y + x * x - y * y)
        bnd = b4_bounds(x, y)
        for c in range(2):
            r = abs(qval(grad[c][j]) - exact[c])
            if r > bnd[c]:
                viol += 1
                first = (j, c) if first is None else first
            if bnd[c] and r / bnd[c] > worst:
                worst = r / bnd[c]
    return {"verdict": "PASS" if viol == 0 else "FAIL", "positions": n, "violations": viol, "first_violation": first,
            "max_residual_over_bound": fl(worst),
            "reason": "|gala gradient - exact gradient| <= local bound at every position" if viol == 0 else
                      "local bound exceeded; must be reconfirmed before any defect claim"}


# --- Diagnostics for the W1 cause (labelled; never a verdict) --------------------------------------

def grad_source_order(x: float, y: float) -> tuple:
    """Order written in builtin_potentials.cpp, evaluated left to right."""
    return (0.0 + x) + (2 * x) * y, ((0.0 + y) + x * x) - y * y


def grad_machine_order(x: float, y: float) -> tuple:
    """Order read from the wheel's machine code (cybuiltin .so, henon_heiles_gradient)."""
    return (0.0 + x) + 2 * (x * y), (x * x - y * y) + (0.0 + y)


def gradient_bit_agreement(fwd: list, grad: list) -> dict:
    out = {}
    for name, g in (("source_order", grad_source_order), ("machine_order", grad_machine_order)):
        same = [0, 0]
        for j in range(len(fwd[0])):
            v = g(fval(fwd[0][j]), fval(fwd[1][j]))
            for c in range(2):
                same[c] += bits(v[c]) == grad[c][j]
        out[name] = {"comp0_bit_equal": same[0], "comp1_bit_equal": same[1], "positions": len(fwd[0])}
    return out


def host_leapfrog(x: float, y: float, vx: float, vy: float, n: int, grad=grad_machine_order) -> list:
    """Host-float staggered leapfrog with the given gradient order; rows x, y, vx, vy (n + 1 columns)."""
    g0, g1 = grad(x, y)
    vhx, vhy = vx - g0 * (DT * 0.5), vy - g1 * (DT * 0.5)
    rows = [[bits(x)], [bits(y)], [bits(vx)], [bits(vy)]]
    for _ in range(n):
        x, y = x + DT * vhx, y + DT * vhy
        g0, g1 = grad(x, y)
        for r, v in zip(rows, (x, y, vhx - g0 * (DT * 0.5), vhy - g1 * (DT * 0.5))):
            r.append(bits(v))
        vhx, vhy = vhx - DT * g0, vhy - DT * g1
    return rows


def first_mismatch(a: list, b: list):
    n = min(len(a[0]), len(b[0]))
    for j in range(n):
        for c in range(4):
            if a[c][j] != b[c][j]:
                return {"step": j, "component": "x y vx vy".split()[c], "bit_pattern_diff": a[c][j] - b[c][j]}
    return None
