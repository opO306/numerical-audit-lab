"""Hard inputs for EXP (R1). Deterministic; mpmath only FINDS candidates, the judge decides.

  * near-midpoint: e^x within a tiny fraction of an ulp of a rounding midpoint --
    constructed (x = binary64 nearest to ln(midpoint) for small |x|, where e^x moves
    slowly) and searched (sha256 samples ranked by distance to 0.5 ulp);
  * edges: the overflow boundary 2^1024 - 2^970, the smallest finite results,
    half the smallest subnormal (rounds to +0 below it), the subnormal/normal
    boundary, |x| around 2^-53 (e^x rounds to 1 or its neighbours), +-0,
    and the VM's early-decision thresholds 1024 * 0.6932 and -1076 * 0.6932;
  * broad: sha256 patterns over the whole finite range.
"""
from __future__ import annotations

import hashlib
import math
from fractions import Fraction

import mpmath

from .exp_judge import ulp_position
from .hard_cases import nudge
from .oracle import OVERFLOW_AT, to_bits


def _nearest_bits(v) -> int:
    return to_bits(float(v))


def _ln(v: Fraction):
    mpmath.mp.prec = 200
    return mpmath.log(mpmath.mpf(v.numerator) / v.denominator)


def _sha(tag, n):
    for i in range(n):
        yield int.from_bytes(hashlib.sha256(f"{tag}:{i}".encode()).digest(), "little")


def constructed_near_midpoints(n: int = 400) -> list[int]:
    out = []
    for i, r in enumerate(_sha("expmid", n)):
        j = (r >> 8) % (1 << (8 + i % 30)) + 1
        if i % 2:
            m = 1 + Fraction(2 * j + 1, 2 ** 53)          # midpoints above 1 (gap 2^-52)
        else:
            m = 1 - Fraction(2 * j + 1, 2 ** 54)          # midpoints below 1 (gap 2^-53)
        out.append(_nearest_bits(_ln(m)))
    return out


def searched_near_midpoints(samples: int = 6000, keep: int = 150) -> list[int]:
    cand = []
    for r in _sha("expsearch", samples):
        x = (r % (1 << 50)) / (1 << 50) * 1454.0 - 745.0      # [-745, 709]
        b = to_bits(x)
        pos = ulp_position(b)
        cand.append((abs(pos - Fraction(1, 2)), b))
    cand.sort()
    return [b for _, b in cand[:keep]]


def edges() -> list[int]:
    pts = []
    for target in (OVERFLOW_AT, Fraction(2) ** 1023, Fraction(1, 2 ** 1075), Fraction(3, 2 ** 1076),
                   Fraction(1, 2 ** 1074), Fraction(1, 2 ** 1022), Fraction(1, 2 ** 1021)):
        pts.append(_nearest_bits(_ln(target)))
    pts += [to_bits(1024 * 0.6932), to_bits(-1076 * 0.6932), to_bits(709.0), to_bits(-700.0), to_bits(-745.0)]
    out = []
    for p in pts:
        out += [q for k in range(-4, 5) if (q := nudge(p, k)) is not None]
    for e in (52, 53, 54, 55, 60, 1074):
        for s in (1, -1):
            out.append(to_bits(s * 2.0 ** -e))
    out += [0, 1 << 63, 1, (1 << 63) | 1, to_bits(1.0), to_bits(-1.0), to_bits(0.5), to_bits(math.log(2))]
    return out


def broad(n: int = 600) -> list[int]:
    out = []
    for i, r in enumerate(_sha("expbroad", n)):
        if i % 3 == 0:
            out.append(r & ((1 << 64) - 1) & ~(0x7FF << 52) | (min((r >> 64) & 0x7FF, 0x7FE) << 52))
        else:
            field = 1023 + ((r >> 64) % 12) - 3            # |x| roughly 2^-3 .. 2^8
            out.append((((r >> 100) & 1) << 63) | (field << 52) | (r & ((1 << 52) - 1)))
    return out


def exp_cases() -> dict[str, list[int]]:
    return {"constructed_mid": constructed_near_midpoints(), "searched_mid": searched_near_midpoints(),
            "edges": edges(), "broad": broad()}
