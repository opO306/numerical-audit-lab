"""V2 error bound (docs/V2_ERROR_BOUND_PLAN.md, sealed): op-level affine arithmetic inside a
step, QR change of basis between steps with an exact-rational inverse.

Checker side: never imports numeric_core. Error convention delta = computed - true, where
"true" is the same discrete program run in exact arithmetic. Every relation is an exact
identity or an upward-rounded inequality; the choice of basis affects tightness only.
"""
from __future__ import annotations

import math
from fractions import Fraction

from independent_checker.oracle import value

INF = math.inf
TINY = 2.0 ** -1074
K = 4                                   # number of noise symbols = state dimension


def up(v: float) -> float:
    if v != v:
        return INF
    return math.nextafter(v, INF)


def up_q(q: Fraction) -> float:
    f = float(q)
    return f if Fraction(f) >= q else math.nextafter(f, INF)


def rnd_err(c: float) -> float:
    """Upper bound on the rounding error of one round-to-nearest float operation whose result is c."""
    return up(abs(c) * 2.0 ** -52 + TINY)


class Form:
    """delta = sum_j coef[j] * xi_j + [-box, box],  xi_j in [-1, 1]."""
    __slots__ = ("coef", "box")

    def __init__(self, coef, box):
        self.coef, self.box = coef, box

    def rad(self) -> float:
        s = self.box
        for c in self.coef:
            s = up(s + abs(c))
        return s


def _lin(a: Form, b: Form, sb: float, rho: float) -> Form:
    """delta_z = delta_a + sb * delta_b + rho-term   (sb = +1 or -1)."""
    coef, extra = [], 0.0
    for ca, cb in zip(a.coef, b.coef):
        c = ca + sb * cb
        coef.append(c)
        extra = up(extra + rnd_err(c))
    return Form(coef, up(up(up(a.box + b.box) + extra) + rho))


def _mul(xv: float, yv: float, a: Form, b: Form, rho: float) -> Form:
    """delta_z = x_hat*delta_y + y_hat*delta_x - delta_x*delta_y + r   (exact identity)."""
    coef, extra = [], 0.0
    for ca, cb in zip(a.coef, b.coef):
        t1, t2 = xv * cb, yv * ca
        c = t1 + t2
        coef.append(c)
        extra = up(up(extra + rnd_err(t1)) + up(rnd_err(t2) + rnd_err(c)))
    box = up(abs(xv) * b.box) + up(abs(yv) * a.box)
    box = up(up(box + up(a.rad() * b.rad())) + up(extra + rho))
    return Form(coef, box)


def step_forms(structure: list, regs: dict, inputs: dict) -> dict:
    """Propagate affine error forms through one straight-line step. inputs: state name -> Form."""
    val = {k: value(b) for k, b in regs.items()}
    fv = {k: float(v) for k, v in val.items()}
    f = dict(inputs)
    zero = [0.0] * K
    for op, dst, args, lit in structure:
        z = val[dst]
        if op == "CONST":
            f[dst] = Form(zero, up_q(abs(z - Fraction(lit))))
            continue
        if op == "NEG":
            a = f[args[0]]
            f[dst] = Form([-c for c in a.coef], a.box)              # exact: negation never rounds
            continue
        x, y = val[args[0]], val[args[1]]
        a, b = f[args[0]], f[args[1]]
        if op == "ADD":
            f[dst] = _lin(a, b, 1.0, up_q(abs(z - (x + y))))
        elif op == "SUB":
            f[dst] = _lin(a, b, -1.0, up_q(abs(z - (x - y))))
        elif op == "MUL":
            f[dst] = _mul(fv[args[0]], fv[args[1]], a, b, up_q(abs(z - x * y)))
        else:
            raise ValueError(f"V2 does not cover {op}")
    return f


# --- change of basis between steps ---------------------------------------------

def _qr_basis(M: list) -> list:
    """Columns of M sorted by norm, Gram-Schmidt in floats, completed with unit vectors.
    Only needs to be invertible; tightness, not soundness, depends on it."""
    cols = [[M[i][j] for i in range(K)] for j in range(K)]
    cols.sort(key=lambda c: -math.fsum(v * v for v in c))
    cand = cols + [[1.0 if i == j else 0.0 for i in range(K)] for j in range(K)]
    scale = max([math.sqrt(math.fsum(v * v for v in c)) for c in cols] + [1e-300])
    basis = []
    for v in cand:
        w = list(v)
        for _ in range(2):                                           # re-orthogonalise once
            for q in basis:
                d = math.fsum(a * b for a, b in zip(w, q))
                w = [a - d * b for a, b in zip(w, q)]
        n = math.sqrt(math.fsum(a * a for a in w))
        ref = math.sqrt(math.fsum(a * a for a in v)) or 1.0
        if n > 1e-8 * ref and n > 1e-300 * scale:
            basis.append([a / n for a in w])
        if len(basis) == K:
            break
    return [[basis[j][i] for j in range(K)] for i in range(K)]       # A[i][j]: column j is basis j


def _inverse(A: list) -> list:
    """Exact rational inverse (Gauss-Jordan)."""
    n = len(A)
    m = [[Fraction(A[i][j]) for j in range(n)] + [Fraction(int(i == j)) for j in range(n)] for i in range(n)]
    for c in range(n):
        p = next(r for r in range(c, n) if m[r][c] != 0)
        m[c], m[p] = m[p], m[c]
        piv = m[c][c]
        m[c] = [v / piv for v in m[c]]
        for r in range(n):
            if r != c and m[r][c] != 0:
                fac = m[r][c]
                m[r] = [a - fac * b for a, b in zip(m[r], m[c])]
    return [row[n:] for row in m]


def radii(A: list, M: list, w: list) -> list:
    """r_i >= |(A^-1 delta)_i| for every delta in M xi + [-w, w]  (exact, then rounded up)."""
    Ai = _inverse(A)
    Mq = [[Fraction(v) for v in row] for row in M]
    wq = [Fraction(v) for v in w]
    r = []
    for i in range(K):
        s = sum((abs(sum(Ai[i][k] * Mq[k][j] for k in range(K))) for j in range(K)), Fraction(0))
        s += sum((abs(Ai[i][k]) * wq[k] for k in range(K)), Fraction(0))
        r.append(up_q(s))
    return r


def rebase(out_forms: list) -> tuple:
    """out_forms: the 4 state Forms after a step (delta in M xi + [-w, w]).
    Returns (input Forms for the next step, componentwise bound E)."""
    M = [list(fm.coef) for fm in out_forms]
    w = [fm.box for fm in out_forms]
    if any(not math.isfinite(v) for row in M for v in row) or any(not math.isfinite(v) for v in w):
        return [Form([0.0] * K, INF) for _ in range(K)], [INF] * K
    A = _qr_basis(M)
    r = radii(A, M, w)
    forms, E = [], []
    for i in range(K):
        coef, box, e = [], 0.0, 0.0
        for j in range(K):
            c = A[i][j] * r[j]
            coef.append(c)
            box = up(box + rnd_err(c))
            e = up(e + up(abs(A[i][j]) * r[j]))
        forms.append(Form(coef, box))
        E.append(up(e + box))
    return forms, E


def zero_forms() -> list:
    return [Form([0.0] * K, 0.0) for _ in range(K)]
