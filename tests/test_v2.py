"""V2-S1: the V2 rules contain every corner of their input sets (fixed, non-random cases),
plus end-to-end soundness against exact arithmetic."""
import itertools
import struct
from fractions import Fraction

import pytest

from benchmarks.gate2a.henon_heiles import STATE, bits, exact_steps
from lab.v2_bound import Form, _inverse, _lin, _mul, _qr_basis, radii, rebase, zero_forms
from run_v2 import V2Run
from run_gate2a import q

CORNERS = list(itertools.product((-1, 1), repeat=4))
A_FORM = Form([1e-10, -3e-11, 0.0, 2.5e-12], 4e-13)
B_FORM = Form([-2e-11, 5e-11, 7e-12, 0.0], 1e-12)


def _val(f: Form, xi, beta):
    return sum(Fraction(c) * s for c, s in zip(f.coef, xi)) + beta * Fraction(f.box)


@pytest.mark.parametrize("xv,yv", [(0.3, -0.7), (1.0 / 3.0, 0.1), (-2.5, 1e-3)])
def test_mul_rule_contains_every_corner(xv, yv):
    zhat = xv * yv
    rho = abs(Fraction(zhat) - Fraction(xv) * Fraction(yv))
    fz = _mul(xv, yv, A_FORM, B_FORM, float(rho) * 2)
    for xi in CORNERS:
        for ba, bb in itertools.product((-1, 1), repeat=2):
            dx, dy = _val(A_FORM, xi, ba), _val(B_FORM, xi, bb)
            true_z = (Fraction(xv) - dx) * (Fraction(yv) - dy)
            dz = Fraction(zhat) - true_z
            lin = sum(Fraction(c) * s for c, s in zip(fz.coef, xi))
            assert abs(dz - lin) <= Fraction(fz.box)


@pytest.mark.parametrize("sign", [1.0, -1.0])
def test_add_sub_rule_contains_every_corner(sign):
    fz = _lin(A_FORM, B_FORM, sign, 0.0)
    for xi in CORNERS:
        for ba, bb in itertools.product((-1, 1), repeat=2):
            dz = _val(A_FORM, xi, ba) + Fraction(sign) * _val(B_FORM, xi, bb)
            lin = sum(Fraction(c) * s for c, s in zip(fz.coef, xi))
            assert abs(dz - lin) <= Fraction(fz.box)


M_CASES = [
    [[1e-12, 2e-13, 0.0, 0.0], [-3e-13, 9e-13, 1e-14, 0.0], [0.0, 1e-14, 5e-13, -2e-13], [1e-15, 0.0, 3e-13, 7e-13]],
    [[0.0] * 4 for _ in range(4)],                                          # the very first step: no inherited error
    [[1e-10, 1e-10, 0.0, 0.0], [1e-10, 1e-10, 0.0, 0.0], [0.0, 0.0, 0.0, 0.0], [0.0, 0.0, 0.0, 1e-20]],  # rank deficient
]


@pytest.mark.parametrize("M", M_CASES)
def test_change_of_basis_contains_every_corner(M):
    w = [1e-16, 2e-16, 0.0, 5e-17]
    A = _qr_basis(M)
    r = radii(A, M, w)
    Ai = _inverse(A)
    forms, E = rebase([Form(list(row), wv) for row, wv in zip(M, w)])
    for xi in CORNERS:
        for beta in itertools.product((-1, 1), repeat=4):
            d = [sum(Fraction(M[i][j]) * xi[j] for j in range(4)) + beta[i] * Fraction(w[i]) for i in range(4)]
            for i in range(4):
                assert abs(sum(Ai[i][k] * d[k] for k in range(4))) <= Fraction(r[i])
                assert abs(d[i]) <= Fraction(E[i])
                rad = sum(abs(Fraction(c)) for c in forms[i].coef) + Fraction(forms[i].box)
                assert abs(d[i]) <= rad


@pytest.mark.parametrize("k", [1, 3, 6])
def test_v2_bound_really_bounds_the_actual_error(k):
    start = {"x": Fraction(0), "y": Fraction(0), "px": Fraction(1, 4), "py": Fraction(1, 8)}
    exact = exact_steps(dict(start), k)[-1]
    st, _, E, _, _ = V2Run().go({s: bits(float(v)) for s, v in start.items()}, k)
    for idx, s in enumerate(STATE):
        assert abs(q(st[s]) - exact[s]) <= Fraction(E[idx])


def test_v2_is_tighter_than_v1_on_a_few_hundred_steps():
    start = {"x": bits(0.0), "y": bits(0.0), "px": bits(0.25), "py": bits(0.125)}
    _, _, _, info, _ = V2Run(with_v1=True).go(start, 300, marks=(300,))
    row = info["rows"][0]
    assert row["v2_bound_max"] < row["v1_bound_max"]
