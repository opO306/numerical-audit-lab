"""Gate 2A checker side: N1 step audit, rule-V1 running bound, local force-law check.

Never imports numeric_core. Receives the step program as plain tuples and every
register as a binary64 bit pattern. Bounds are kept as floats rounded UPWARD after
every operation (rule V1 section 2 allows upward-rounded interval storage; exact
rationals grow without limit over long runs). Local rounding errors rho are exact.
"""
from __future__ import annotations

import math
from fractions import Fraction

from independent_checker.oracle import judge, value

INF = math.inf


def up(v: float) -> float:
    if v != v:                       # inf * 0 once a bound has overflowed: an upper bound of "unknown" is +inf
        return INF
    return math.nextafter(v, INF)


def up_q(q: Fraction) -> float:
    """Smallest-ish float >= q (q >= 0)."""
    f = float(q)
    return f if Fraction(f) >= q else math.nextafter(f, INF)


class StepAudit:
    """Audits one VM step: returns (n1_failures, e_out, force_check) and updates nothing global."""

    STATE = ("x", "y", "px", "py")
    OUT = {"x": "x1", "y": "y1", "px": "px1", "py": "py1"}

    def __init__(self, structure: list):
        self.structure = structure

    def run(self, regs: dict, e_in: dict) -> dict:
        val = {k: value(b) for k, b in regs.items()}                    # exact Fractions of binary64 values
        fval = {k: float(v) for k, v in val.items()}
        e = dict(e_in)
        e_loc = {s: 0.0 for s in self.STATE}                             # K3: errors with exact positions
        e_loc.update({"x1": 0.0, "y1": 0.0})
        n1_bad = []
        for op, dst, args, lit in self.structure:
            z = val[dst]
            if op == "CONST":
                exact = Fraction(lit)
                prop = loc = 0.0
            elif op == "NEG":
                (a,) = args
                exact = -val[a]
                prop, loc = e[a], e_loc.get(a, 0.0)
            else:
                a, b = args
                x, y = val[a], val[b]
                ex, ey = e[a], e[b]
                lx, ly = e_loc.get(a, 0.0), e_loc.get(b, 0.0)
                ax_, ay_ = abs(fval[a]), abs(fval[b])
                if op == "ADD":
                    exact, prop, loc = x + y, up(ex + ey), up(lx + ly)
                elif op == "SUB":
                    exact, prop, loc = x - y, up(ex + ey), up(lx + ly)
                elif op == "MUL":
                    exact = x * y
                    prop = up(up(up(ax_ * ey) + up(ay_ * ex)) + up(ex * ey))
                    loc = up(up(up(ax_ * ly) + up(ay_ * lx)) + up(lx * ly))
                else:
                    raise ValueError(f"op {op} not covered by the Gate 2A audit")
            problem = judge(exact, regs[dst])                             # N1: correctly rounded?
            if problem is not None:
                n1_bad.append((dst, problem))
            rho = up_q(abs(z - exact))
            e[dst] = up(prop + rho) if rho else prop
            e_loc[dst] = up(loc + rho) if rho else loc
            if op == "CONST":
                e[dst] = e_loc[dst] = up_q(abs(z - exact))
            if dst in ("x1", "y1"):
                e_loc[dst] = 0.0                                          # K3 judges the law AT these positions
        return {"n1_bad": n1_bad, "e_out": {s: e[self.OUT[s]] for s in self.STATE},
                "force": self._force_check(val, e_loc), "val": val}

    @staticmethod
    def _force_check(val: dict, e_loc: dict) -> list:
        """K3: SUT force vs exact -grad V at the SUT's own positions, within the local rounding bound."""
        out = []
        for t, (px_, py_) in (("0", ("x", "y")), ("1", ("x1", "y1"))):
            x, y = val[px_], val[py_]
            for name, exact in ((f"ax{t}", -x - 2 * x * y), (f"ay{t}", -y - x * x + y * y)):
                r = abs(val[name] - exact)
                out.append((name, r <= Fraction(e_loc[name]), float(r), e_loc[name]))
        return out


def verdict(residuals: list, bounds: list, scale: Fraction) -> tuple:
    """Rule V1 section 0. residuals: exact Fractions; bounds: floats; scale S: Fraction."""
    if any(not math.isfinite(b) for b in bounds):
        return "REFUSED", "bound is not finite"
    if max(bounds) >= scale:
        return "REFUSED", f"bound {max(bounds):.3e} >= scale {float(scale):.3e} (no power)"
    over = [i for i, (r, b) in enumerate(zip(residuals, bounds)) if abs(r) > Fraction(b)]
    if over:
        return "FAIL", f"residual exceeds bound in component(s) {over}"
    return "PASS", "residual explained by rounding"


# --- Hamiltonian, exactly and over a box (M1) ---------------------------------

def H(x, y, px, py) -> Fraction:
    return (px * px + py * py) / 2 + (x * x + y * y) / 2 + x * x * y - y ** 3 / 3


class Iv:
    """Exact rational interval."""

    def __init__(self, lo, hi=None):
        self.lo, self.hi = Fraction(lo), Fraction(lo if hi is None else hi)

    def __add__(self, o): o = o if isinstance(o, Iv) else Iv(o); return Iv(self.lo + o.lo, self.hi + o.hi)
    def __sub__(self, o): o = o if isinstance(o, Iv) else Iv(o); return Iv(self.lo - o.hi, self.hi - o.lo)

    def __mul__(self, o):
        o = o if isinstance(o, Iv) else Iv(o)
        c = (self.lo * o.lo, self.lo * o.hi, self.hi * o.lo, self.hi * o.hi)
        return Iv(min(c), max(c))

    def sq(self):
        if self.lo >= 0:
            return Iv(self.lo ** 2, self.hi ** 2)
        if self.hi <= 0:
            return Iv(self.hi ** 2, self.lo ** 2)
        return Iv(0, max(self.lo ** 2, self.hi ** 2))


def energy_rounding_part(state: dict, e: dict) -> Fraction:
    """Upper bound on |H(s_hat) - H(s)| for any s with |s - s_hat| <= e (componentwise).
    An infinite state bound gives an infinite (unknown) energy rounding part."""
    if any(not math.isfinite(v) for v in e.values()):
        return INF
    b = {k: Iv(state[k] - Fraction(e[k]), state[k] + Fraction(e[k])) for k in state}
    x, y, px, py = b["x"], b["y"], b["px"], b["py"]
    h = (px.sq() + py.sq()) * Fraction(1, 2) + (x.sq() + y.sq()) * Fraction(1, 2) + x.sq() * y - y.sq() * y * Fraction(1, 3)
    c = H(state["x"], state["y"], state["px"], state["py"])
    return max(c - h.lo, h.hi - c)
