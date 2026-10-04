"""Opt-in integer Drift/Kick; no slow/original arithmetic dependencies."""
from .contracts import (Ratio, DriftResult, KickResult, GuardedResult, FAST_STATUS,
                        validate_drift, validate_kick, validate_ratio, refuse)

STATUS = FAST_STATUS


def nearest_even_ratio(numerator, denominator):
    q, remainder = divmod(numerator, denominator)
    twice = remainder * 2
    if twice < denominator:
        return q
    if twice > denominator:
        return q + 1
    return q if q % 2 == 0 else q + 1


def _coefficients(request, mass):
    a, b = request.dt.numerator, request.dt.denominator
    c, e = mass.numerator, mass.denominator
    return a * e, (1 << request.momentum_grid.frac_bits) * b * c


def drift(request):
    validate_drift(request)
    scale = 1 << request.position_grid.frac_bits
    minimum = -(1 << (request.position_grid.width - 1))
    maximum = (1 << (request.position_grid.width - 1)) - 1
    ds, ends, deltas, stored = [], [], [], []
    atoms = (("i", request.r_i, request.p_i, request.mass_i),
             ("j", request.r_j, request.p_j, request.mass_j))
    for atom, positions, momenta, mass in atoms:
        factor, denominator = _coefficients(request, mass)
        for axis, old_r, p_raw in zip("xyz", positions, momenta):
            numerator = p_raw * factor
            delta = nearest_even_ratio(numerator * scale, denominator)
            if not minimum <= delta <= maximum:
                refuse("DISPLACEMENT_OVERFLOW", "drift", atom, axis, "stored displacement outside signed position grid")
            updated = old_r + delta
            if updated < minimum or updated > maximum:
                refuse("POSITION_OVERFLOW", "drift", atom, axis, "stored position outside signed position grid")
            ds.append(Ratio(numerator, denominator))
            ends.append(Ratio(old_r * denominator + numerator * scale, denominator * scale))
            deltas.append(delta)
            stored.append(updated)
    return DriftResult(tuple(ds), tuple(ends), tuple(deltas[:3]), tuple(deltas[3:]),
                       tuple(stored[:3]), tuple(stored[3:]))


def kick(request):
    validate_kick(request)
    minimum = -(1 << (request.momentum_grid.width - 1))
    maximum = (1 << (request.momentum_grid.width - 1)) - 1
    scale = 1 << request.momentum_grid.frac_bits
    exact, updated = [], []
    for atom, p in (("i", request.p_i), ("j", request.p_j)):
        for axis, raw, impulse in zip("xyz", p, request.J_raw):
            value = raw - impulse if atom == "i" else raw + impulse
            if not minimum <= value <= maximum:
                refuse("MOMENTUM_OVERFLOW", "kick", atom, axis, "stored momentum outside signed momentum grid")
            exact.append(Ratio(value, scale))
            updated.append(value)
    return KickResult(tuple(exact), tuple(updated[:3]), tuple(updated[3:]))


def guarded_drift(request, threshold):
    validate_drift(request)
    validate_ratio(threshold, "r_min_squared", positive=True)
    from .exact_geometry import guard_drift
    result = drift(request)
    geometry = guard_drift(request, result, threshold)
    return GuardedResult(result, geometry)
