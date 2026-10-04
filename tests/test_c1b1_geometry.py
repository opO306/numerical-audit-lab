from dataclasses import replace
from fractions import Fraction as F
import pytest
from independent_checker.c1b1.contracts import Grid, Ratio, DriftInput, LabRefusal
from independent_checker.c1b1.exact_geometry import evaluate
from independent_checker.c1b1 import exact_slow, exact_fast
from independent_checker.c1b1.compare import compare_drift


@pytest.mark.parametrize("q0,q1,tau,minimum", [
    ((3, 4, 0), (3, 4, 0), F(0), F(25)),
    ((1, 0, 0), (2, 0, 0), F(0), F(1)),
    ((2, 0, 0), (1, 0, 0), F(1), F(1)),
    ((-1, 1, 0), (1, 1, 0), F(1, 2), F(1)),
    ((-2, 1, 2), (4, 1, 2), F(1, 3), F(5)),
    ((F(-1, 3), F(1, 7), 0), (F(2, 3), F(1, 7), 0), F(1, 3), F(1, 49)),
])
def test_hand_derived_minima(q0, q1, tau, minimum):
    result = evaluate(q0, q1, (3, 0, 0), Ratio(1, 100))
    assert result.tau == tau and result.min_R2 == minimum
    assert result.stored_R2 == 9
    assert result.domain == "EXACT_THRESHOLD_ONLY"


def test_strict_threshold_equality_and_neighbors():
    for threshold, intrusion in ((F(999, 1000), False), (F(1), False), (F(1001, 1000), True)):
        result = evaluate((-1, 1, 0), (1, 1, 0), (1, 0, 0), threshold)
        assert result.segment_intrusion is intrusion
        assert result.stored_intrusion is intrusion


def test_geometry_inequality_from_different_polynomial_argument():
    # No call to geometry's dot or minimizer helper in the independent argument.
    q0, q1 = (-2, 1, 2), (4, 1, 2)
    result = evaluate(q0, q1, q1, F(1))
    assert result.min_R2 == 5
    for t in (F(-1), F(0), F(1, 7), F(1, 3), F(1, 2), F(1), F(2)):
        norm = (-2 + 6 * t) ** 2 + 1 + 4
        assert norm - result.min_R2 == 36 * (t - F(1, 3)) ** 2 >= 0


def request(**changes):
    return replace(DriftInput(Grid(8, 0), Grid(8, 0), (1, 0, 0), (0, 0, 0),
        (-1, 0, 0), (0, 0, 0), Ratio(1, 1), Ratio(1, 1), Ratio(1, 4)), **changes)


def test_rounded_endpoint_would_miss_real_intrusion():
    req = request()
    for module in (exact_slow, exact_fast):
        assert module.drift(req).r_i == (1, 0, 0)
        with pytest.raises(LabRefusal) as caught:
            module.guarded_drift(req, Ratio(81, 100))
        assert caught.value.failure.code == "SEGMENT_INTRUSION"
    assert compare_drift(req, Ratio(81, 100)).match


def test_stored_guard_is_separate_and_ordered_after_segment():
    # Relative exact endpoint .6 has R2=.36, stored endpoint 1 has R2=1.
    req = request(p_i=(1, 0, 0), r_i=(0, 0, 0), r_j=(-2, 0, 0),
                  p_j=(0, 0, 0), dt=Ratio(-7, 5))
    # relative exact endpoint .6, stored relative endpoint 1: choose threshold .81
    # The segment is first to refuse in this case.
    with pytest.raises(LabRefusal) as caught:
        exact_fast.guarded_drift(req, Ratio(81, 100))
    assert caught.value.failure.phase == "segment_guard"
    # A different configuration has exact endpoint 1.49 -> stored 1, threshold 1.21.
    req = request(r_i=(2, 0, 0), p_i=(-1, 0, 0), dt=Ratio(51, 100))
    assert compare_drift(req, Ratio(121, 100)).match
    with pytest.raises(LabRefusal) as caught:
        exact_slow.guarded_drift(req, Ratio(121, 100))
    assert caught.value.failure.code == "STORED_INTRUSION"


def test_input_validation_then_overflow_then_guard():
    req = request(position_grid=Grid(3, 0), r_i=(3, 0, 0), p_i=(1, 0, 0), dt=Ratio(1, 1))
    with pytest.raises(LabRefusal) as caught:
        exact_fast.guarded_drift(req, Ratio(1000, 1))
    assert caught.value.failure.code == "POSITION_OVERFLOW"
    with pytest.raises(LabRefusal) as caught:
        exact_fast.guarded_drift(req, Ratio(0, 1))
    assert caught.value.failure.code == "RATIONAL_NONPOSITIVE"


@pytest.mark.parametrize("q, threshold", [((True, 0, 0), F(1)), ((0.0, 0, 0), F(1)),
    ((0, 0), F(1)), ((0, 0, 0), 0), ((0, 0, 0), Ratio(1, -1))])
def test_invalid_geometry_is_refused(q, threshold):
    with pytest.raises(LabRefusal):
        evaluate(q, (1, 0, 0), (1, 0, 0), threshold)
