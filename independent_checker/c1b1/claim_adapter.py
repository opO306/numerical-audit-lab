"""Strict plain-data arithmetic claims. Supplied J is never physically verified."""
from dataclasses import dataclass, fields, is_dataclass
from fractions import Fraction
import json
from math import gcd
import re
from .contracts import (Grid, Ratio, DriftInput, KickInput, SCOPE, J_STATUS,
                        SPEC_SHA256, FAST_STATUS, refuse)
from .compare import capture
from . import exact_slow, exact_fast

INTEGER = re.compile(r"(?:0|-[1-9][0-9]*|[1-9][0-9]*)\Z")
SCHEMA = "LAB_C1B1_CLAIM_V1"


@dataclass(frozen=True)
class ClaimComparison:
    status: str
    acquisition_id: str
    record_id: str
    phase_id: str
    computed_json: str
    path: str
    calculation_status: str = "COMPUTED"
    fast_status: str = FAST_STATUS
    scope: str = SCOPE
    j_status: str = J_STATUS
    spec_sha256: str = SPEC_SHA256
    external_compatibility: str = "NOT VERIFIED"


def _keys(value, names):
    if type(value) is not dict or set(value) != set(names):
        refuse("CLAIM_SCHEMA", message="plain-data object has missing or unexpected keys")


def _integer(value):
    if type(value) is not str or len(value.lstrip("-")) > 4096 or not INTEGER.fullmatch(value):
        refuse("CLAIM_SCHEMA", message="canonical decimal integer string required")
    return int(value)


def _ratio(value):
    _keys(value, ("numerator", "denominator"))
    n, d = _integer(value["numerator"]), _integer(value["denominator"])
    if d <= 0 or gcd(n, d) != 1:
        refuse("CLAIM_SCHEMA", message="canonical rational pair with positive denominator required")
    return Ratio(n, d)


def _grid(value):
    _keys(value, ("width", "frac_bits", "kind", "rounding", "overflow"))
    return Grid(**value)


def _vector(value):
    if type(value) is not list or len(value) != 3:
        refuse("CLAIM_SCHEMA", message="wire vector requires three lanes")
    return tuple(_integer(x) for x in value)


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            refuse("CLAIM_SCHEMA", message="duplicate JSON key")
        result[key] = value
    return result


def _constant(value):
    refuse("CLAIM_SCHEMA", message="non-finite JSON number")


def decode(payload):
    if type(payload) is dict:
        return payload
    if type(payload) not in (str, bytes):
        refuse("CLAIM_SCHEMA", message="JSON bytes/text or plain dict required")
    if len(payload.encode("utf-8") if type(payload) is str else payload) > 1048576:
        refuse("CLAIM_SCHEMA", message="claim exceeds V1 byte cap")
    try:
        return json.loads(payload, object_pairs_hook=_pairs, parse_constant=_constant)
    except (UnicodeError, ValueError, RecursionError) as exc:
        from .contracts import LabRefusal
        if isinstance(exc, LabRefusal):
            raise
        refuse("CLAIM_SCHEMA", message="invalid JSON claim")


def canonical_data(value):
    """Normalize only the public artifact boundary; never an arithmetic helper."""
    if isinstance(value, (Ratio, Fraction)):
        divisor = gcd(value.numerator, value.denominator)
        return {"numerator": str(value.numerator // divisor), "denominator": str(value.denominator // divisor)}
    if is_dataclass(value):
        return {"type": type(value).__name__, **{f.name: canonical_data(getattr(value, f.name)) for f in fields(value)}}
    if type(value) is int:
        return str(value)
    if isinstance(value, tuple):
        return [canonical_data(x) for x in value]
    if type(value) in (str, bool) or value is None:
        return value
    raise TypeError("unsupported artifact value")


def _claim_shape(claim, expected):
    if type(claim) is not type(expected):
        refuse("CLAIM_SCHEMA", message="claim value type differs from V1 artifact schema")
    if type(expected) is dict:
        _keys(claim, expected)
        for key in expected:
            _claim_shape(claim[key], expected[key])
    elif type(expected) is list:
        if len(claim) != len(expected):
            refuse("CLAIM_SCHEMA", message="claim vector length differs from V1 schema")
        for a, b in zip(claim, expected):
            _claim_shape(a, b)
    elif type(expected) is str and INTEGER.fullmatch(expected):
        _integer(claim)


def compare_claim(payload, path="exact_slow", *, opt_in=False):
    envelope = decode(payload)
    _keys(envelope, ("schema", "spec_sha256", "scope", "j_status", "acquisition_id", "record_id", "phase_id", "operation", "input", "claim"))
    if (envelope["schema"] != SCHEMA or envelope["spec_sha256"] != SPEC_SHA256
            or envelope["scope"] != SCOPE or envelope["j_status"] != J_STATUS):
        refuse("SPEC_MISMATCH", message="Lab V1 arithmetic-only claim binding required")
    for key in ("acquisition_id", "record_id", "phase_id"):
        if type(envelope[key]) is not str or not 1 <= len(envelope[key]) <= 256:
            refuse("CLAIM_SCHEMA", message="nonempty bounded acquisition/record/phase IDs required")
    if path == "exact_slow":
        module = exact_slow
    elif path == "exact_fast" and opt_in is True:
        module = exact_fast
    else:
        refuse("FAST_OPTIN_REQUIRED", message="explicit exact_slow or opt-in exact_fast required")
    operation, data = envelope["operation"], envelope["input"]
    if operation in ("drift", "guarded_drift"):
        names = ("position_grid", "momentum_grid", "r_i", "r_j", "p_i", "p_j", "mass_i", "mass_j", "dt")
        _keys(data, names + (("threshold", "domain_binding") if operation == "guarded_drift" else ()))
        request = DriftInput(_grid(data["position_grid"]), _grid(data["momentum_grid"]),
            _vector(data["r_i"]), _vector(data["r_j"]), _vector(data["p_i"]), _vector(data["p_j"]),
            _ratio(data["mass_i"]), _ratio(data["mass_j"]), _ratio(data["dt"]))
        if operation == "guarded_drift":
            if data["domain_binding"] != "EXACT_THRESHOLD_ONLY":
                refuse("CLAIM_SCHEMA", message="physical r_min binding is not approved")
            computed = capture(module.guarded_drift, request, _ratio(data["threshold"]))
        else:
            computed = capture(module.drift, request)
    elif operation == "kick":
        _keys(data, ("momentum_grid", "impulse_grid", "p_i", "p_j", "J_raw"))
        request = KickInput(_grid(data["momentum_grid"]), _grid(data["impulse_grid"]),
                            _vector(data["p_i"]), _vector(data["p_j"]), _vector(data["J_raw"]))
        computed = capture(module.kick, request)
    else:
        refuse("CLAIM_SCHEMA", message="unsupported arithmetic operation")
    expected = canonical_data(computed)
    _claim_shape(envelope["claim"], expected)
    status = "ARITHMETIC_MATCH" if envelope["claim"] == expected else "ARITHMETIC_MISMATCH"
    return ClaimComparison(status, envelope["acquisition_id"], envelope["record_id"], envelope["phase_id"],
                           json.dumps(expected, sort_keys=True, separators=(",", ":")), path,
                           calculation_status="REFUSED" if computed.exception_type else "COMPUTED")
