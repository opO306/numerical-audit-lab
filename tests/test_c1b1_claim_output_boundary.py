"""F-CLAIM-1: exact results must fit the canonical Claim V1 output wire.

Expectations use integer identities and hand-authored claims, never the target
serializer as an oracle. Removing the output guard must fail these probes.
"""
import copy
from fractions import Fraction
import json
import sys

import pytest

from independent_checker.c1b1 import contracts as C, exact_fast, exact_slow
from independent_checker.c1b1 import claim_adapter as adapter


LIMIT = 10 ** 4096


def false_zero_claim():
    """A valid small wire claim; the nonzero exact displacement makes it false."""
    x = 10 ** 2150
    grid = {"width": 8, "frac_bits": 0, "kind": "signed_fx",
            "rounding": "nearest_even", "overflow": "refuse"}
    zero = {"numerator": "0", "denominator": "1"}
    meta = {"scope": "ARITHMETIC_ONLY", "j_status": "J_NOT_VERIFIED"}
    return {"schema": "LAB_C1B1_CLAIM_V1", "spec_sha256": C.SPEC_SHA256,
        **meta, "acquisition_id": "F-CLAIM-1-REGRESSION",
        "record_id": "large-canonical-input", "phase_id": "drift", "operation": "drift",
        "input": {"position_grid": dict(grid), "momentum_grid": dict(grid),
            "r_i": ["0"] * 3, "r_j": ["0"] * 3,
            "p_i": ["1", "0", "0"], "p_j": ["0"] * 3,
            "mass_i": {"numerator": str(x + 3), "denominator": "1"},
            "mass_j": {"numerator": "1", "denominator": "1"},
            "dt": {"numerator": "1", "denominator": str(x + 1)}},
        "claim": {"type": "Outcome", "exception_type": "", **meta,
            "value": {"type": "DriftResult", **meta, "spec_sha256": C.SPEC_SHA256,
                "displacement": [dict(zero) for _ in range(6)],
                "endpoint": [dict(zero) for _ in range(6)],
                "delta_i": ["0"] * 3, "delta_j": ["0"] * 3,
                "r_i": ["0"] * 3, "r_j": ["0"] * 3,
                "checked_order": ["i.x", "i.y", "i.z", "j.x", "j.y", "j.z"]}}}


def assert_output_refusal(exc):
    assert type(exc).__name__ == "LabRefusal"
    assert exc.failure.code == "CLAIM_OUTPUT_LIMIT"
    assert exc.failure.phase == "claim_output"
    assert exc.failure.atom == exc.failure.component == ""
    assert exc.failure.scope == "ARITHMETIC_ONLY"
    assert exc.failure.j_status == "J_NOT_VERIFIED"
    assert exc.failure.spec_sha256 == C.SPEC_SHA256


def exercise_counterexample(module, wire_form="text"):
    """Shared by the regression and a real source mutant, without copied output."""
    payload = false_zero_claim()
    before = copy.deepcopy(payload)
    wire = json.dumps(payload, separators=(",", ":"))
    assert len(wire.encode()) < 1048576
    assert len(payload["input"]["mass_i"]["numerator"]) == 2151
    assert len(payload["input"]["dt"]["denominator"]) == 2151
    argument = {"dict": payload, "text": wire, "bytes": wire.encode()}[wire_form]
    limit_before = sys.get_int_max_str_digits()
    failures = []
    for path in ("exact_slow", "exact_fast"):
        try:
            module.compare_claim(argument, path, opt_in=(path == "exact_fast"))
        except Exception as exc:
            # A leaked plain ValueError is an assertion failure, not detection by
            # exception alone. The baseline must satisfy the exact refusal contract.
            assert_output_refusal(exc)
            failures.append(exc.failure)
        else:
            raise AssertionError("unrepresentable output was published")
        assert payload == before
        assert sys.get_int_max_str_digits() == limit_before
    assert failures[0] == failures[1]
    return failures


@pytest.mark.parametrize("wire_form", ["dict", "text", "bytes"])
def test_fclaim1_exact_reproduction_has_identical_structured_refusals(wire_form):
    x = 10 ** 2150
    denominator = (x + 1) * (x + 3)
    assert 10 ** 4300 <= denominator < 10 ** 4301  # Exactly 4301 digits, no str.
    request = C.DriftInput(C.Grid(8, 0), C.Grid(8, 0), (0, 0, 0), (0, 0, 0),
        (1, 0, 0), (0, 0, 0), C.Ratio(x + 3, 1), C.Ratio(1, 1), C.Ratio(1, x + 1))
    before = copy.deepcopy(request)
    for kernel in (exact_slow, exact_fast):
        result = kernel.drift(request)
        for lane in (result.displacement[0], result.endpoint[0]):
            assert lane.numerator == 1 and lane.denominator == denominator
        assert result.delta_i == result.delta_j == result.r_i == result.r_j == (0, 0, 0)
        assert result.scope == "ARITHMETIC_ONLY" and result.j_status == "J_NOT_VERIFIED"
        assert request == before
    exercise_counterexample(adapter, wire_form)


@pytest.mark.parametrize("kind", [C.Ratio, Fraction], ids=["unreduced-pair", "Fraction"])
@pytest.mark.parametrize("field", ["numerator", "denominator"])
@pytest.mark.parametrize("sign", [1, -1], ids=["positive", "negative"])
@pytest.mark.parametrize("offset", [-1, 0, 1], ids=["below-limit", "at-limit", "above-limit"])
def test_canonical_output_integer_boundary(kind, field, sign, offset):
    integer = LIMIT + offset
    n, d = (sign * integer, 1) if field == "numerator" else (sign, integer)
    value = kind(n, d)
    limit_before = sys.get_int_max_str_digits()
    if offset == -1:
        result = adapter.canonical_data(value)
        if field == "numerator":
            assert result == {"numerator": ("-" if sign < 0 else "") + "9" * 4096,
                              "denominator": "1"}
        else:
            assert result == {"numerator": "-1" if sign < 0 else "1",
                              "denominator": "9" * 4096}
    else:
        with pytest.raises(C.LabRefusal) as caught:
            adapter.canonical_data(value)
        assert_output_refusal(caught.value)
    assert sys.get_int_max_str_digits() == limit_before


@pytest.mark.parametrize("n,d,want", [
    (0, 10 ** 5000, {"numerator": "0", "denominator": "1"}),
    (2 * 10 ** 5000, 6 * 10 ** 5000, {"numerator": "1", "denominator": "3"}),
    (-2 * 10 ** 5000, 6 * 10 ** 5000, {"numerator": "-1", "denominator": "3"}),
], ids=["canonical-zero", "reduce-before-limit-positive", "reduce-before-limit-negative"])
def test_output_limit_applies_after_exact_reduction(n, d, want):
    pair = C.Ratio(n, d)
    assert adapter.canonical_data(pair) == want
    assert pair.numerator == n and pair.denominator == d


@pytest.mark.parametrize("value,want", [(0, "0"), (LIMIT - 1, "9" * 4096),
                                      (1 - LIMIT, "-" + "9" * 4096)],
                         ids=["zero", "positive", "negative"])
def test_computed_raw_integer_uses_same_wire_boundary(value, want):
    assert adapter.canonical_data(value) == want


@pytest.mark.parametrize("value", [LIMIT, LIMIT + 1, -LIMIT, -LIMIT - 1],
                         ids=["positive-at", "positive-above", "negative-at", "negative-above"])
def test_computed_raw_integer_limit_is_structured(value):
    with pytest.raises(C.LabRefusal) as caught:
        adapter.canonical_data(value)
    assert_output_refusal(caught.value)


@pytest.mark.parametrize("value", [C.Ratio(10 ** 5000 + 1, 1), C.Ratio(1, 10 ** 5000 + 1)],
                         ids=["numerator", "denominator"])
def test_rejection_precedes_python_decimal_conversion(value):
    with pytest.raises(C.LabRefusal) as caught:
        adapter.canonical_data(value)
    assert_output_refusal(caught.value)


def test_at_wire_boundary_slow_fast_reduce_before_check_and_preserve_scope():
    payload = false_zero_claim()
    payload["input"]["mass_i"] = {"numerator": "1", "denominator": "1"}
    payload["input"]["dt"] = {"numerator": "1", "denominator": "9" * 4096}
    # Expected values are authored directly. The fast zero lanes carry a huge
    # unreduced denominator, but their canonical values must remain 0/1.
    for field in ("displacement", "endpoint"):
        payload["claim"]["value"][field][0] = {"numerator": "1", "denominator": "9" * 4096}
    before = copy.deepcopy(payload)
    results = [adapter.compare_claim(payload, path, opt_in=(path == "exact_fast"))
               for path in ("exact_slow", "exact_fast")]
    assert all(r.status == "ARITHMETIC_MATCH" and r.calculation_status == "COMPUTED" for r in results)
    assert all(r.scope == "ARITHMETIC_ONLY" and r.j_status == "J_NOT_VERIFIED" for r in results)
    assert results[0].computed_json == results[1].computed_json
    assert payload == before


@pytest.mark.parametrize("field", ["numerator", "denominator"])
@pytest.mark.parametrize("sign", [1, -1], ids=["positive", "negative"])
def test_actual_drift_numerator_or_denominator_overflow_refuses_identically(field, sign):
    payload = false_zero_claim()
    x = 10 ** 2150
    if field == "numerator":
        # Both inputs fit the wire, and the stored displacement fits Grid(4096,0).
        # Canonical N has 4301 digits; canonical D has only 4096 digits.
        payload["input"]["position_grid"]["width"] = 4096
        payload["input"]["mass_i"] = {"numerator": "1", "denominator": str(x + 3)}
        payload["input"]["dt"] = {"numerator": str(sign * (x + 1)), "denominator": "1" + "0" * 4095}
        n, d = sign * (x + 1) * (x + 3), 10 ** 4095
    else:
        payload["input"]["dt"]["numerator"] = str(sign)
        n, d = sign, (x + 1) * (x + 3)
    request = C.DriftInput(C.Grid(payload["input"]["position_grid"]["width"], 0), C.Grid(8, 0),
        (0, 0, 0), (0, 0, 0), (1, 0, 0), (0, 0, 0),
        C.Ratio(int(payload["input"]["mass_i"]["numerator"]), int(payload["input"]["mass_i"]["denominator"])),
        C.Ratio(1, 1), C.Ratio(int(payload["input"]["dt"]["numerator"]), int(payload["input"]["dt"]["denominator"])))
    before = copy.deepcopy(payload)
    failures = []
    for path, kernel in (("exact_slow", exact_slow), ("exact_fast", exact_fast)):
        result = kernel.drift(request)
        assert result.displacement[0].numerator == n and result.displacement[0].denominator == d
        with pytest.raises(C.LabRefusal) as caught:
            adapter.compare_claim(payload, path, opt_in=(path == "exact_fast"))
        assert_output_refusal(caught.value)
        failures.append(caught.value.failure)
        assert payload == before
    assert failures[0] == failures[1]
