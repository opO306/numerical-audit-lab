"""Gate 2B: replay T properties in exact arithmetic (plan derivations 1 and 2), fixture integrity,
and non-vacuity of the checks."""
import shutil
import struct
from fractions import Fraction

import pytest

from benchmarks.gate2a.henon_heiles import exact_steps
from benchmarks.gate2b.gala_replay import Replay
from lab.gate2b_checks import (b3_mirror, b4_bounds, b4_force_law, bits, first_mismatch, grad_machine_order,
                               grad_source_order, host_leapfrog, qval)
from lab.gate2b_fixture import FIXTURE, load
from run_gate2b import w1_replay

V0 = {"regular": (Fraction(1, 4), Fraction(1, 8)), "chaotic": (Fraction(1, 2), Fraction(1, 4))}


def _exact_T(x, y, vx, vy, k):
    T = Replay(exact=True)
    vh = T.init(x, y, vx, vy)
    s, out = (x, y, vh["vhx"], vh["vhy"]), []
    for _ in range(k):
        o = T.step(*s)
        out.append((o["x1"], o["y1"], o["vox"], o["voy"]))
        s = (o["x1"], o["y1"], o["vhx1"], o["vhy1"])
    return out


@pytest.mark.parametrize("orbit", sorted(V0))
def test_derivation_2_T_equals_lab_verlet_exactly(orbit):
    vx, vy = V0[orbit]
    t = _exact_T(Fraction(0), Fraction(0), vx, vy, 5)
    v = exact_steps({"x": Fraction(0), "y": Fraction(0), "px": vx, "py": vy}, 5)
    assert t == [(s["x"], s["y"], s["px"], s["py"]) for s in v]


@pytest.mark.parametrize("orbit", sorted(V0))
def test_derivation_1_T_is_exactly_time_reversible(orbit):
    vx, vy = V0[orbit]
    k = 4
    x, y, ux, uy = _exact_T(Fraction(0), Fraction(0), vx, vy, k)[-1]
    assert _exact_T(x, y, -ux, -uy, k)[-1] == (0, 0, -vx, -vy)


def test_loader_refuses_a_changed_fixture(tmp_path):
    copy = tmp_path / "fx"
    shutil.copytree(FIXTURE, copy)
    p = copy / "regular_gradient.u64.gz"
    data = bytearray(p.read_bytes())
    data[-9] ^= 1
    p.write_bytes(bytes(data))
    with pytest.raises(RuntimeError, match="changed"):
        load("regular_gradient", copy)
    assert len(load("regular_mirror", copy)[0]) == 100_001      # untouched files still load


def test_w1_can_report_identity_and_catches_a_one_bit_change():
    T = Replay()
    b = lambda v: struct.unpack("<Q", struct.pack("<d", v))[0]
    x, y, vx, vy = b(0.0), b(0.0), b(0.25), b(0.125)
    vh = T.init(x, y, vx, vy)
    rows, s = [[x], [y], [vx], [vy]], (x, y, vh["vhx"], vh["vhy"])
    for _ in range(30):
        o = T.step(*s)
        for r, v in zip(rows, (o["x1"], o["y1"], o["vox"], o["voy"])):
            r.append(v)
        s = (o["x1"], o["y1"], o["vhx1"], o["vhy1"])
    assert w1_replay(rows, 30)["result"] == "BIT_IDENTICAL"
    rows[2][17] += 1
    assert w1_replay(rows, 30)["first_mismatch"]["step"] == 17


def test_b3_catches_a_one_bit_change_and_b4_catches_an_error_above_the_bound():
    fwd = host_leapfrog(0.0, 0.0, 0.25, 0.125, 50)
    mir = host_leapfrog(-0.0, 0.0, -0.25, 0.125, 50)
    assert b3_mirror(fwd, mir)["verdict"] == "PASS"
    mir[1][33] += 1
    r = b3_mirror(fwd, mir)
    assert (r["verdict"], r["first_mismatch"]) == ("FAIL", 33)
    grad = [[], []]
    for j in range(51):
        g = grad_machine_order(struct.unpack("<d", struct.pack("<Q", fwd[0][j]))[0],
                               struct.unpack("<d", struct.pack("<Q", fwd[1][j]))[0])
        grad[0].append(bits(g[0])); grad[1].append(bits(g[1]))
    assert b4_force_law(fwd, grad)["verdict"] == "PASS"
    grad[1][40] += 4                                          # 4 ulp > gamma_3 bound (about 3 ulp of the terms)
    assert b4_force_law(fwd, grad)["verdict"] == "FAIL"


def test_b4_bound_covers_both_evaluation_orders():
    """The B4 bound is order-independent: it must hold for the source order and the machine order."""
    pts = [(i / 97.0 - 0.5, (i * 37 % 101) / 101.0 - 0.5) for i in range(200)] + [(1e-160, 3e-160), (0.0, -0.0)]
    for x, y in pts:
        X, Y = Fraction(x), Fraction(y)
        exact = (X + 2 * X * Y, Y + X * X - Y * Y)
        bnd = b4_bounds(X, Y)
        for g in (grad_source_order(x, y), grad_machine_order(x, y)):
            for c in range(2):
                assert abs(Fraction(g[c]) - exact[c]) <= bnd[c], (x, y, c)


def test_machine_and_source_orders_really_differ_somewhere():
    """Non-vacuity of the W1 cause diagnostic: the two orders are not the same function on binary64."""
    diff = sum(grad_source_order(x, y)[1] != grad_machine_order(x, y)[1]
               for x, y in ((i / 97.0 - 0.5, (i * 37 % 101) / 101.0 - 0.5) for i in range(200)))
    assert diff > 0


def test_first_mismatch_none_on_equal_rows():
    rows = host_leapfrog(0.0, 0.0, 0.5, 0.25, 10)
    assert first_mismatch(rows, [list(r) for r in rows]) is None
    assert qval(bits(0.5)) == Fraction(1, 2)
