"""Pure rational geometry, given threshold. Physical unit binding is pending."""
from fractions import Fraction
from .contracts import (Ratio, GeometryResult, DriftResult, validate_ratio,
                        validate_drift, refuse)


def _fraction(value, field):
    if type(value) is Fraction:
        return value
    if type(value) is int:
        return Fraction(value)
    validate_ratio(value, field)
    return Fraction(value.numerator, value.denominator)


def _vector(value, field):
    if type(value) is not tuple or len(value) != 3:
        refuse("INPUT_SCHEMA", message=f"{field}: immutable three-lane tuple required")
    return tuple(_fraction(x, field) for x in value)


def _dot(a, b):
    return sum((x * y for x, y in zip(a, b)), Fraction(0))


def evaluate(q0, q1, stored_relative, r_min_squared):
    start = _vector(q0, "q0")
    end = _vector(q1, "q1")
    stored = _vector(stored_relative, "stored_relative")
    threshold = _fraction(r_min_squared, "r_min_squared")
    if threshold <= 0:
        refuse("RATIONAL_NONPOSITIVE", message="r_min_squared: must be positive")
    v = tuple(y - x for x, y in zip(start, end))
    A, B, C = _dot(start, start), _dot(start, v), _dot(v, v)
    if C == 0:
        tau, minimum = Fraction(0), A
    else:
        tau = max(Fraction(0), min(Fraction(1), -B / C))
        closest = tuple(x + tau * velocity for x, velocity in zip(start, v))
        minimum = _dot(closest, closest)
    stored_R2 = _dot(stored, stored)
    return GeometryResult(tau, minimum, stored_R2, threshold,
                          minimum < threshold, stored_R2 < threshold)


def guard_drift(request, result, threshold):
    validate_drift(request)
    validate_ratio(threshold, "r_min_squared", positive=True)
    if type(result) is not DriftResult or result.spec_sha256 != request.spec_sha256:
        refuse("INPUT_SCHEMA", message="guard requires Lab V1 DriftResult")
    scale = 1 << request.position_grid.frac_bits
    q0 = tuple(Fraction(a - b, scale) for a, b in zip(request.r_i, request.r_j))
    endpoints = tuple(_fraction(x, "endpoint") for x in result.endpoint)
    if len(endpoints) != 6:
        refuse("INPUT_SCHEMA", message="guard requires six exact endpoints")
    q1 = tuple(a - b for a, b in zip(endpoints[:3], endpoints[3:]))
    stored = tuple(Fraction(a - b, scale) for a, b in zip(result.r_i, result.r_j))
    geometry = evaluate(q0, q1, stored, threshold)
    if geometry.segment_intrusion:
        refuse("SEGMENT_INTRUSION", "segment_guard", message="exact segment crosses supplied threshold")
    if geometry.stored_intrusion:
        refuse("STORED_INTRUSION", "stored_guard", message="stored position crosses supplied threshold")
    return geometry
