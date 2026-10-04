"""Hand-derived oracle checks before fast is introduced."""
from dataclasses import replace
from fractions import Fraction
import pytest
from independent_checker.c1b1.contracts import Grid, Ratio, DriftInput, KickInput, LabRefusal
from independent_checker.c1b1 import exact_slow as slow


def request(**changes):
    base = DriftInput(Grid(8, 0), Grid(8, 0), (1, 0, 0), (0, 0, 0),
                      (1, 0, 0), (0, 0, 0), Ratio(1, 1), Ratio(1, 1), Ratio(1, 2))
    return replace(base, **changes)


@pytest.mark.parametrize("value, expected", [
    (Fraction(0), 0), (Fraction(1, 2), 0), (Fraction(3, 2), 2),
    (Fraction(5, 2), 2), (Fraction(-1, 2), 0), (Fraction(-3, 2), -2),
    (Fraction(-5, 2), -2), (Fraction(499, 1000), 0), (Fraction(501, 1000), 1),
    (Fraction(-501, 1000), -1), (Fraction(-499, 1000), 0),
])
def test_fraction_distances(value, expected):
    assert slow.nearest_even(value) == expected


def test_displacement_rounding_is_separate_from_endpoint():
    result = slow.drift(request())
    assert result.delta_i == (0, 0, 0)
    assert result.r_i == (1, 0, 0)
    assert result.displacement[0] == Fraction(1, 2)
    assert result.endpoint[0] == Fraction(3, 2)
    assert result.scope == "ARITHMETIC_ONLY" and result.j_status == "J_NOT_VERIFIED"


def test_nontrivial_mass_dt_scales_and_all_lanes():
    result = slow.drift(request(position_grid=Grid(12, 3), momentum_grid=Grid(12, 5),
        r_i=(3, -2, 0), r_j=(0, 0, 0), p_i=(32, -64, 0), p_j=(16, 32, -16),
        mass_i=Ratio(3, 2), mass_j=Ratio(5, 3), dt=Ratio(7, 4)))
    assert result.displacement == (Fraction(7, 6), Fraction(-7, 3), Fraction(0),
                                  Fraction(21, 40), Fraction(21, 20), Fraction(-21, 40))
    assert result.delta_i == (9, -19, 0) and result.delta_j == (4, 8, -4)
    assert result.r_i == (12, -21, 0)


def test_kick_signed_hand_values():
    k = KickInput(Grid(8, 3), Grid(8, 3), (1, -2, 3), (4, 5, -6), (7, -8, 0))
    result = slow.kick(k)
    assert result.p_i == (-6, 6, 3) and result.p_j == (11, -3, -6)
    assert result.exact_momentum == tuple(Fraction(n, 8) for n in (-6, 6, 3, 11, -3, -6))
    assert k.p_i == (1, -2, 3)


@pytest.mark.parametrize("changes, code, component", [
    ({"position_grid": Grid(3, 0), "r_i": (3, 0, 0), "p_i": (2, 0, 0), "dt": Ratio(1, 1)}, "POSITION_OVERFLOW", "x"),
    ({"position_grid": Grid(3, 0), "p_i": (4, 0, 0), "dt": Ratio(1, 1)}, "DISPLACEMENT_OVERFLOW", "x"),
    ({"r_i": (True, 0, 0)}, "INPUT_SCHEMA", "x"),
    ({"mass_i": Ratio(0, 1)}, "RATIONAL_NONPOSITIVE", ""),
    ({"dt": Ratio(1, 0)}, "RATIONAL_INVALID", ""),
])
def test_refusals_leave_input_intact(changes, code, component):
    req = request(**changes)
    before = repr(req)
    with pytest.raises(LabRefusal) as caught:
        slow.drift(req)
    assert caught.value.failure.code == code
    assert caught.value.failure.component == component
    assert repr(req) == before


def test_first_component_position_failure_precedes_later_displacement():
    with pytest.raises(LabRefusal) as caught:
        slow.drift(request(position_grid=Grid(3, 0), r_i=(3, 0, 0),
                           p_i=(1, 10, 0), dt=Ratio(1, 1)))
    assert (caught.value.failure.code, caught.value.failure.atom, caught.value.failure.component) == ("POSITION_OVERFLOW", "i", "x")
