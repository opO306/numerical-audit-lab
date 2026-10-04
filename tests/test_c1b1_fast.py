from dataclasses import replace
import pytest
from independent_checker.c1b1 import exact_fast as fast
from independent_checker.c1b1.contracts import Grid, Ratio, DriftInput, KickInput, LabRefusal


def request(**changes):
    return replace(DriftInput(Grid(8, 0), Grid(8, 0), (1, 0, 0), (0, 0, 0),
        (1, 0, 0), (0, 0, 0), Ratio(1, 1), Ratio(1, 1), Ratio(1, 2)), **changes)


@pytest.mark.parametrize("n,d,raw", [(0, 7, 0), (1, 2, 0), (3, 2, 2),
    (-1, 2, 0), (-3, 2, -2), (-5, 2, -2), (49, 100, 0), (51, 100, 1),
    (-49, 100, 0), (-51, 100, -1), (300, 200, 2)])
def test_integer_rounding_hand_cases(n, d, raw):
    assert fast.nearest_even_ratio(n, d) == raw


def test_unrounded_and_stored_are_distinct():
    result = fast.drift(request())
    assert result.r_i == (1, 0, 0) and result.delta_i == (0, 0, 0)
    assert result.endpoint[0].numerator * 2 == result.endpoint[0].denominator * 3
    assert result.displacement[0].numerator * 2 == result.displacement[0].denominator
    assert fast.STATUS == "EXPERIMENTAL / OPT-IN"


def test_exact_signed_kick():
    k = KickInput(Grid(8, 3), Grid(8, 3), (1, -2, 3), (4, 5, -6), (7, -8, 0))
    result = fast.kick(k)
    assert result.p_i == (-6, 6, 3) and result.p_j == (11, -3, -6)
    assert k.p_i == (1, -2, 3)


def test_displacement_and_final_position_range_are_separate():
    # The final mathematical raw -4+4=0 is in range, but displacement +4 is not.
    with pytest.raises(LabRefusal) as caught:
        fast.drift(request(position_grid=Grid(3, 0), r_i=(-4, 0, 0),
                           p_i=(4, 0, 0), dt=Ratio(1, 1)))
    assert caught.value.failure.code == "DISPLACEMENT_OVERFLOW"


def test_i_component_order_and_input_immutability():
    req = request(position_grid=Grid(3, 0), r_i=(3, 0, 0), p_i=(1, 10, 0), dt=Ratio(1, 1))
    before = repr(req)
    with pytest.raises(LabRefusal) as caught:
        fast.drift(req)
    assert (caught.value.failure.atom, caught.value.failure.component) == ("i", "x")
    assert caught.value.failure.code == "POSITION_OVERFLOW"
    assert repr(req) == before


def test_kick_multi_fault_first_failure_and_no_publication():
    req = KickInput(Grid(3, 0), Grid(3, 0), (-4, -4, 0), (3, 3, 0), (1, 1, 0))
    before = repr(req)
    with pytest.raises(LabRefusal) as caught:
        fast.kick(req)
    assert (caught.value.failure.code, caught.value.failure.atom, caught.value.failure.component) == ("MOMENTUM_OVERFLOW", "i", "x")
    assert repr(req) == before


@pytest.mark.parametrize("changes,code", [
    ({"momentum_grid": Grid(8, 2)}, "GRID_MISMATCH"),
    ({"J_raw": (128, 0, 0)}, "RAW_RANGE"),
    ({"J_raw": (False, 0, 0)}, "INPUT_SCHEMA"),
    ({"impulse_grid": Grid(8, 3, rounding="away")}, "PROFILE_UNSUPPORTED"),
])
def test_invalid_kick_inputs(changes, code):
    req = replace(KickInput(Grid(8, 3), Grid(8, 3), (0, 0, 0), (0, 0, 0), (0, 0, 0)), **changes)
    with pytest.raises(LabRefusal) as caught:
        fast.kick(req)
    assert caught.value.failure.code == code
