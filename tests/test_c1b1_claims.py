"""External plain-data, hand-authored claims; not original-executor compatibility."""
import copy
import json
import pytest
from independent_checker.c1b1.contracts import SPEC_SHA256, LabRefusal
from independent_checker.c1b1.claim_adapter import compare_claim


def ratio(n, d=1):
    return {"numerator": str(n), "denominator": str(d)}


def grid():
    return {"width": 8, "frac_bits": 0, "kind": "signed_fx", "rounding": "nearest_even", "overflow": "refuse"}


def envelope():
    return {"schema": "LAB_C1B1_CLAIM_V1", "spec_sha256": SPEC_SHA256,
        "scope": "ARITHMETIC_ONLY", "j_status": "J_NOT_VERIFIED", "acquisition_id": "HAND_DERIVED_TEST_ONLY",
        "record_id": "occurrence-1", "phase_id": "drift-1", "operation": "drift",
        "input": {"position_grid": grid(), "momentum_grid": grid(),
            "r_i": ["1", "0", "0"], "r_j": ["0", "0", "0"],
            "p_i": ["1", "0", "0"], "p_j": ["0", "0", "0"],
            "mass_i": ratio(1), "mass_j": ratio(1), "dt": ratio(1, 2)},
        "claim": {"type": "Outcome", "exception_type": "", "scope": "ARITHMETIC_ONLY", "j_status": "J_NOT_VERIFIED",
            "value": {"type": "DriftResult", "displacement": [ratio(1, 2)] + [ratio(0)] * 5,
                "endpoint": [ratio(3, 2)] + [ratio(0)] * 5,
                "delta_i": ["0"] * 3, "delta_j": ["0"] * 3, "r_i": ["1", "0", "0"], "r_j": ["0"] * 3,
                "checked_order": ["i.x", "i.y", "i.z", "j.x", "j.y", "j.z"],
                "scope": "ARITHMETIC_ONLY", "j_status": "J_NOT_VERIFIED", "spec_sha256": SPEC_SHA256}}}


def test_hand_authored_external_claim_and_distinct_occurrences():
    payload = envelope()
    before = copy.deepcopy(payload)
    for path, opt_in in (("exact_slow", False), ("exact_fast", True)):
        result = compare_claim(json.dumps(payload), path, opt_in=opt_in)
        assert result.status == "ARITHMETIC_MATCH"
        assert result.scope == "ARITHMETIC_ONLY" and result.j_status == "J_NOT_VERIFIED"
        assert result.external_compatibility == "NOT VERIFIED"
    payload["record_id"] = "occurrence-2"
    assert compare_claim(payload).record_id == "occurrence-2"
    assert before["record_id"] == "occurrence-1"


def test_same_stored_bits_wrong_exact_endpoint_is_rejected():
    payload = envelope()
    payload["claim"]["value"]["endpoint"][0] = ratio(1)
    assert compare_claim(payload).status == "ARITHMETIC_MISMATCH"


def test_hand_authored_kick_and_guarded_claims():
    p = envelope()
    p["operation"] = "kick"
    p["input"] = {"momentum_grid": grid(), "impulse_grid": grid(),
                  "p_i": ["1", "0", "0"], "p_j": ["0", "0", "0"], "J_raw": ["1", "0", "0"]}
    p["claim"]["value"] = {"type": "KickResult", "exact_momentum": [ratio(0)] * 3 + [ratio(1), ratio(0), ratio(0)],
        "p_i": ["0"] * 3, "p_j": ["1", "0", "0"], "checked_order": ["i.x", "i.y", "i.z", "j.x", "j.y", "j.z"],
        "scope": "ARITHMETIC_ONLY", "j_status": "J_NOT_VERIFIED", "spec_sha256": SPEC_SHA256}
    g = envelope()
    g["operation"] = "guarded_drift"
    g["input"].update(threshold=ratio(1, 4), domain_binding="EXACT_THRESHOLD_ONLY")
    g["claim"]["value"] = {"type": "GuardedResult", "drift": g["claim"]["value"],
        "geometry": {"type": "GeometryResult", "tau": ratio(0), "min_R2": ratio(1), "stored_R2": ratio(1),
            "threshold": ratio(1, 4), "segment_intrusion": False, "stored_intrusion": False,
            "domain": "EXACT_THRESHOLD_ONLY", "scope": "ARITHMETIC_ONLY", "j_status": "J_NOT_VERIFIED", "spec_sha256": SPEC_SHA256},
        "scope": "ARITHMETIC_ONLY", "j_status": "J_NOT_VERIFIED", "spec_sha256": SPEC_SHA256}
    for payload in (p, g):
        for path in ("exact_slow", "exact_fast"):
            assert compare_claim(payload, path, opt_in=True).status == "ARITHMETIC_MATCH"


def test_matching_refusal_is_not_an_accepted_transition():
    p = envelope()
    p["input"]["mass_i"] = ratio(0)
    p["claim"]["exception_type"] = "LabRefusal"
    p["claim"]["value"] = {"type": "Failure", "code": "RATIONAL_NONPOSITIVE", "phase": "input",
        "atom": "", "component": "", "message": "mass_i: must be positive",
        "scope": "ARITHMETIC_ONLY", "j_status": "J_NOT_VERIFIED", "spec_sha256": SPEC_SHA256}
    result = compare_claim(p)
    assert result.status == "ARITHMETIC_MATCH" and result.calculation_status == "REFUSED"


@pytest.mark.parametrize("edit", [
    lambda p: p["input"]["p_i"].__setitem__(0, True),
    lambda p: p["input"]["r_i"].__setitem__(0, "01"),
    lambda p: p["input"]["r_i"].__setitem__(0, "-0"),
    lambda p: p["input"].__setitem__("dt", ratio(2, 4)),
    lambda p: p.__setitem__("scope", "REPLAY_VERIFIED"),
    lambda p: p.__setitem__("surprise", "field"),
    lambda p: p["input"]["mass_i"].__setitem__("denominator", "-1"),
    lambda p: p["claim"]["value"]["r_i"].__setitem__(0, 1.0),
    lambda p: p.__setitem__("record_id", ""),
])
def test_invalid_wire_fails_closed(edit):
    payload = envelope()
    edit(payload)
    with pytest.raises(LabRefusal):
        compare_claim(payload)


def test_duplicate_nonfinite_oversize_and_fast_optin():
    for payload in ('{"schema":1,"schema":2}', '{"x":NaN}', b'\xff', ' ' * 1048577):
        with pytest.raises(LabRefusal):
            compare_claim(payload)
    with pytest.raises(LabRefusal) as caught:
        compare_claim(envelope(), "exact_fast")
    assert caught.value.failure.code == "FAST_OPTIN_REQUIRED"
