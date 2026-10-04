"""New Fraction oracle: distance-to-neighbours rounding, no fast helpers."""
from fractions import Fraction
from .contracts import (DriftResult, KickResult, GuardedResult, validate_drift,
                        validate_kick, validate_ratio, refuse)


def nearest_even(value: Fraction) -> int:
    lower = value.numerator // value.denominator
    upper = lower + 1
    distance_lower = value - lower
    distance_upper = upper - value
    if distance_lower < distance_upper:
        return lower
    if distance_upper < distance_lower:
        return upper
    return lower if lower % 2 == 0 else upper


def drift(request):
    validate_drift(request)
    position_scale = 2 ** request.position_grid.frac_bits
    momentum_scale = 2 ** request.momentum_grid.frac_bits
    limit = 2 ** (request.position_grid.width - 1)
    dt = Fraction(request.dt.numerator, request.dt.denominator)
    displacements, endpoints, deltas, positions = [], [], [], []
    for atom, r, p, mass in (
        ("i", request.r_i, request.p_i, request.mass_i),
        ("j", request.r_j, request.p_j, request.mass_j),
    ):
        m = Fraction(mass.numerator, mass.denominator)
        for axis, old_r, old_p in zip("xyz", r, p):
            displacement = (Fraction(old_p, momentum_scale) * dt) / m
            endpoint = Fraction(old_r, position_scale) + displacement
            delta = nearest_even(displacement * position_scale)
            if delta < -limit or delta >= limit:
                refuse("DISPLACEMENT_OVERFLOW", "drift", atom, axis, "stored displacement outside signed position grid")
            stored_exact = Fraction(old_r, position_scale) + Fraction(delta, position_scale)
            stored_raw = (stored_exact * position_scale).numerator
            if not -limit <= stored_raw < limit:
                refuse("POSITION_OVERFLOW", "drift", atom, axis, "stored position outside signed position grid")
            displacements.append(displacement)
            endpoints.append(endpoint)
            deltas.append(delta)
            positions.append(stored_raw)
    return DriftResult(tuple(displacements), tuple(endpoints), tuple(deltas[:3]),
                       tuple(deltas[3:]), tuple(positions[:3]), tuple(positions[3:]))


def kick(request):
    validate_kick(request)
    scale = 2 ** request.momentum_grid.frac_bits
    lower = -(2 ** (request.momentum_grid.width - 1))
    upper = -lower - 1
    exact_values, raws = [], []
    impulses = tuple(Fraction(raw, scale) for raw in request.J_raw)
    for atom, momentum in (("i", request.p_i), ("j", request.p_j)):
        for axis, raw, impulse in zip("xyz", momentum, impulses):
            p = Fraction(raw, scale)
            exact = p - impulse if atom == "i" else p + impulse
            result = nearest_even(exact * scale)
            if result < lower or result > upper:
                refuse("MOMENTUM_OVERFLOW", "kick", atom, axis, "stored momentum outside signed momentum grid")
            exact_values.append(exact)
            raws.append(result)
    return KickResult(tuple(exact_values), tuple(raws[:3]), tuple(raws[3:]))


def guarded_drift(request, threshold):
    validate_drift(request)
    validate_ratio(threshold, "r_min_squared", positive=True)
    from .exact_geometry import guard_drift
    result = drift(request)
    geometry = guard_drift(request, result, threshold)
    return GuardedResult(result, geometry)
