from dataclasses import replace
from fractions import Fraction
import random
import pytest
from independent_checker.c1b1.contracts import Grid, Ratio, DriftInput, KickInput
from independent_checker.c1b1 import exact_slow, exact_fast
from independent_checker.c1b1.compare import compare_drift, compare_kick, differences


def test_signed_ties_neighbors_and_unreduced_ratios():
    # Independent cell inequalities add a third check, rather than only agreement.
    count = 0
    for denominator in range(1, 38):
        for numerator in range(-113, 114):
            value = Fraction(numerator, denominator)
            a = exact_slow.nearest_even(value)
            b = exact_fast.nearest_even_ratio(numerator, denominator)
            assert a == b
            assert abs(value - a) <= Fraction(1, 2)
            if abs(value - a) == Fraction(1, 2):
                assert a % 2 == 0
            assert b == exact_fast.nearest_even_ratio(numerator * 1234567890, denominator * 1234567890)
            count += 1
    assert count == 8399


@pytest.mark.parametrize("pos,mom", [(Grid(5, 0), Grid(7, 3)), (Grid(16, 9), Grid(16, 5)),
    (Grid(96, 48), Grid(96, 80)), (Grid(256, 120), Grid(256, 160))])
def test_seeded_full_lane_success_and_refusal_matrix(pos, mom):
    rng = random.Random(20261004)
    successes = failures = 0
    def vector(grid, edge=False):
        low, high = -(1 << (grid.width - 1)), (1 << (grid.width - 1)) - 1
        choices = (low, low + 1, -1, 0, 1, high - 1, high)
        return tuple(rng.choice(choices) if edge else rng.randrange(low, high + 1) for _ in range(3))
    for index in range(400):
        req = DriftInput(pos, mom, vector(pos, index % 2 == 0), vector(pos, True),
            vector(mom, True), vector(mom), Ratio(rng.randrange(1, 13), rng.randrange(1, 13)),
            Ratio(rng.randrange(1, 13), rng.randrange(1, 13)), Ratio(rng.randrange(-12, 13), rng.randrange(1, 13)))
        result = compare_drift(req)
        assert result.match, result.differences
        if result.slow.exception_type:
            failures += 1
        else:
            successes += 1
        expanded = replace(req, dt=Ratio(req.dt.numerator * 1000003, req.dt.denominator * 1000003),
            mass_i=Ratio(req.mass_i.numerator * 999983, req.mass_i.denominator * 999983))
        expanded_result = compare_drift(expanded)
        assert expanded_result.match
        assert differences(result.slow, expanded_result.slow) == ()
        assert differences(result.fast, expanded_result.fast) == ()
        kick = KickInput(mom, mom, vector(mom, True), vector(mom, True), vector(mom, True))
        assert compare_kick(kick).match
    assert successes > 0 and failures > 0


def test_all_invalid_input_classes_and_kick_limits():
    pos, mom = Grid(8, 2), Grid(8, 5)
    base = DriftInput(pos, mom, (0, 0, 0), (1, 0, 0), (0, 0, 0), (0, 0, 0), Ratio(1, 1), Ratio(1, 1), Ratio(0, 1))
    invalid = ({"spec_sha256": "0" * 64}, {"position_grid": "FX"},
        {"r_i": [0, 0, 0]}, {"p_j": (0.0, 0, 0)}, {"p_i": (128, 0, 0)},
        {"mass_j": Ratio(-1, 1)}, {"dt": Ratio(1, -2)}, {"dt": Ratio(True, 1)},
        {"momentum_grid": Grid(5000, 0)}, {"position_grid": Grid(8, 2, overflow="wrap")})
    for changes in invalid:
        result = compare_drift(replace(base, **changes))
        assert result.match and result.slow.exception_type == "LabRefusal"
    for p_i, p_j, j in ((-128, 127, 0), (-127, 126, 1), (-128, 0, 1), (0, 127, 1), (127, 0, -1), (0, -128, -1)):
        assert compare_kick(KickInput(mom, mom, (p_i, 0, 0), (p_j, 0, 0), (j, 0, 0))).match


def test_comparison_distinguishes_equal_pairs_and_real_discrepancy():
    assert differences(Ratio(2, 4), Fraction(1, 2)) == ()
    assert differences(Ratio(2, 4), Fraction(1, 3)) == ("result",)
