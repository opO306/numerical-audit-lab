"""Gate 2A: the facts the sealed plan relies on, checked at small sizes."""
import math
from fractions import Fraction

import pytest

from benchmarks.gate2a.henon_heiles import OUT, STATE, Binary64Stepper, bits, exact_steps, structure
from lab.gate2a_audit import StepAudit, energy_rounding_part, up, verdict, H
from lab.gate2a_hostfloat import step as host_step
from run_gate2a import Runner, fv, q

START = {"x": Fraction(0), "y": Fraction(0), "px": Fraction(1, 4), "py": Fraction(1, 8)}
START_BITS = {s: bits(float(v)) for s, v in START.items()}
ZERO = {s: 0.0 for s in STATE}


def test_verlet_is_exactly_time_reversible_in_exact_arithmetic():
    """K1 is class I: forward k steps, flip momenta, k steps back = start with momenta flipped."""
    fwd = exact_steps(dict(START), 5)[-1]
    back = exact_steps({"x": fwd["x"], "y": fwd["y"], "px": -fwd["px"], "py": -fwd["py"]}, 5)[-1]
    assert back == {"x": START["x"], "y": START["y"], "px": -START["px"], "py": -START["py"]}


def test_reversibility_holds_even_for_a_wrong_position_force_law():
    """The plan's disclosed blind spot: K1 cannot see force-law defect D3."""
    fwd = exact_steps(dict(START), 4, "D3")[-1]
    back = exact_steps({"x": fwd["x"], "y": fwd["y"], "px": -fwd["px"], "py": -fwd["py"]}, 4, "D3")[-1]
    assert back["x"] == 0 and back["px"] == -START["px"]


def test_mirror_symmetry_is_exact_in_exact_arithmetic():
    base = exact_steps(dict(START), 5)[-1]
    mir = exact_steps({"x": -START["x"], "y": START["y"], "px": -START["px"], "py": START["py"]}, 5)[-1]
    assert mir == {"x": -base["x"], "y": base["y"], "px": -base["px"], "py": base["py"]}


def test_host_float_implementation_is_bit_identical_to_the_vm():
    st, hf = dict(START_BITS), tuple(float(v) for v in START.values())
    s = Binary64Stepper()
    for _ in range(50):
        regs = s.step(st)
        st = {k: regs[OUT[k]] for k in STATE}
        hf = host_step(*hf)
        assert tuple(bits(v) for v in hf) == tuple(st[k] for k in STATE)


@pytest.mark.parametrize("k", [1, 3, 6])
def test_rule_v1_bound_really_bounds_the_actual_error(k):
    exact = exact_steps(dict(START), k)[-1]
    (st, e), _, _ = Runner().go(START_BITS, k, ZERO)
    for s in STATE:
        assert abs(q(st[s]) - exact[s]) <= Fraction(e[s])


def test_correct_program_passes_n1_and_force_law_check():
    r = Runner()
    _, _, stats = r.go(START_BITS, 30, ZERO)
    assert r.n1_bad == 0 and stats["k3_failed_checks"] == 0


@pytest.mark.parametrize("defect,detector", [("D1", "n1"), ("D3", "k3")])
def test_planted_defects_are_caught_by_their_layer(defect, detector):
    r = Runner(defect)
    _, _, stats = r.go(START_BITS, 20, ZERO)
    if detector == "n1":
        assert r.n1_bad > 0
    else:
        assert stats["k3_failed_checks"] > 0 and r.n1_bad == 0


def test_bound_arithmetic_never_returns_nan():
    assert up(math.inf * 0.0) == math.inf
    assert verdict([Fraction(0)], [math.inf], Fraction(1))[0] == "REFUSED"
    assert verdict([Fraction(1, 10)], [0.05], Fraction(1))[0] == "FAIL"
    assert verdict([Fraction(1, 100)], [0.05], Fraction(1))[0] == "PASS"
    assert verdict([Fraction(0)], [2.0], Fraction(1))[0] == "REFUSED"


def test_energy_rounding_part_contains_every_corner_of_the_box():
    st = {"x": Fraction(1, 10), "y": Fraction(-1, 7), "px": Fraction(1, 3), "py": Fraction(1, 5)}
    e = {s: 1e-3 for s in STATE}
    b = energy_rounding_part(st, e)
    h0 = H(st["x"], st["y"], st["px"], st["py"])
    import itertools
    for signs in itertools.product((-1, 1), repeat=4):
        c = {s: st[s] + sg * Fraction(e[s]) for s, sg in zip(STATE, signs)}
        assert abs(H(c["x"], c["y"], c["px"], c["py"]) - h0) <= b


def test_structure_is_plain_data_for_the_checker():
    for op, dst, args, lit in structure():
        assert isinstance(op, str) and isinstance(dst, str) and isinstance(args, tuple)


def test_energy_rounding_part_is_infinite_when_the_state_bound_is():
    st = {s: Fraction(0) for s in STATE}
    assert energy_rounding_part(st, {"x": math.inf, "y": 0.0, "px": 0.0, "py": 0.0}) == math.inf
