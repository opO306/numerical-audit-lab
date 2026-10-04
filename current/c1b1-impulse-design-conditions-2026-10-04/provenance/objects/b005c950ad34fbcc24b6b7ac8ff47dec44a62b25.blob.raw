"""C1-B1 exact impulse certificate CHECKER, format c1b1-exact-impulse-certificate-v1.

Spec: docs/active/C1B1_EXACT_IMPULSE_CERTIFICATE_SPEC_V1.md (designer-approved S1-S4, 2026-09-29).

WHAT IT DECIDES. Given a certificate it answers exactly one of
    VALID(m)   the exact impulse component J_k of the FROZEN C1-A model (retardation ON), for the stated relative
               position and kick interval, rounds to raw m on FX(96,80). Decided by STRICT separation of an exact
               rational enclosure from the two half-ulp boundaries of m, so no tie rule is ever used.
    INVALID    the certificate does not prove that claim (the reason is named). A wrong certificate, a malformed
               one, or one whose parameters are too coarse to separate.
    REFUSED    an operational limit was hit before a verdict. This says nothing about truth.
Operational limits affect availability, never truth: raising or lowering a limit can turn REFUSED into VALID or
INVALID, but never VALID into INVALID or the reverse.

INDEPENDENCE (designer P1b). This file imports only fractions, hashlib, json, math and time. It never imports the
executor, the C1-A evaluator, a_numeric or the exp enclosure, and it never calls C._model. The frozen constants are
written out below as decimal strings and bound to the frozen model by a fingerprint recomputed here. Tests (never this
file) compare it with a_reference.ar2_lang2024.parameter_fingerprint().

SCOPE. This checker judges a mathematical claim about the frozen model. It does NOT read or judge the run binding
(model/executor sources, profile, dt): that belongs to the runtime wrapper and the proof cache. It does not prove
that an executor enclosure contains the true value (A-EV).

ARITHMETIC. Every value is a closed interval of exact rationals (fractions.Fraction); nothing is rounded. Division
is only by intervals with a positive lower end. exp(-x) is enclosed by the geometric-tail series bound
    1/(S_n(x_hi)+U_n(x_hi)) <= exp(-x) <= 1/S_n(x_lo),   U_n(y) = y^(n+1)/(n+1)! * (n+2)/(n+2-y),  n+2 > y
(mode "full"), or by 0 < exp(-x) <= 1/S_n(x_lo) (mode "zero_floor", always sound, used where exp(-x) is far below
every ulp). The qualitative liveness argument rests on mode "full" only.
"""
import hashlib
import json
import math
import time
from fractions import Fraction

FORMAT = "c1b1-exact-impulse-certificate-v1"
METHOD = "rational-taylor-geomtail-v1"
CONTRACT = "c1a-ar2-lang2024-v1"
FROZEN_FINGERPRINT = "ada6153be05af3e582139fdc81b5697fffaf18d12f9f2de6e8d5ac2fdfe0839e"

BOHR_ANGSTROM = "0.529177210903"
R_MIN_ANGSTROM = "1.2"
POSITION_FRAC_BITS = 48
OUT_WIDTH, OUT_FRAC = 96, 80

# --- frozen constants (exact decimals of the published Fortran, as in the C1-A contract) --------------------------
SHORT = {
    "BO": [("6.92639712", {-1: "2.19578828e4", 0: "6.77672149e4", 1: "8.52129476e4", 2: "9.53252754e4"}),
           ("2.34781022", {-1: "-2.16338828e4", 0: "3.18311293e4", 1: "-8.18603449e3", 2: "8.37564742e2"})],
    "REL": [("1.66833595", {0: "-3.55673715e0", 1: "7.59367220e-1", 2: "-4.19874548e-2"}),
            ("3.07137482", {0: "-2.83560129e1", 1: "1.64892143e1", 2: "7.19542232e0"})],
    "QED": [("1.64936036", {0: "-1.2621862e-1", 1: "1.176436e-2", 2: "0"}),
            ("2.29848003", {0: "0", 1: "0", 2: "6.921721e-2"})],
}
LONG = {   # (eta, kadd, {k: C_2k})
    "BO": ("3.65946625", 1, {3: "64.2295222", 4: "1503.45262", 5: "49033", 6: "1828012", 7: "81913453",
                             8: "4294913366"}),
    "REL": ("1.05249333", 0, {2: "-9.43594504e-4", 3: "1.76276088e-1", 4: "3.99787449e-1"}),
    "QED": ("3.91638946", 0, {3: "-1.949525e-2", 4: "-4.8877359e-1"}),
}
RET_A = ("3.064827731712776e-01", "4.843969950480238e-03", "7.793815409352866e-06", "1.031221966985517e-14",
         "4.204140311858030e-12")
RET_B = ("3.064827731712776e-01", "4.858660928580025e-03", "1.156839432134599e-05", "1.670845939899731e-08",
         "2.151070686307512e-17", "8.769598859882065e-15")
SIGMA_BO = (("1.9", "6.29130076e-1"), ("6.81313900e-1", "9.85423065e-1"), ("5.76343421e-3", "2.56799977e-8"),
            ("2.56907367e-2", "2.93856722e-6"))
SIGMA_REL = (("1.05", "6.76919448e-5"), ("1.16451516e-2", "1.95220703e-8"), ("2.58221232e-1", "1.89517999e-3"),
             ("2.00658289e-3", "6.75730842e-10"))

# the nine exponential rates, in the fixed certificate order
RATE_ORDER = (("BO", "short", 0), ("BO", "short", 1), ("REL", "short", 0), ("REL", "short", 1),
              ("QED", "short", 0), ("QED", "short", 1), ("BO", "long", 0), ("REL", "long", 0), ("QED", "long", 0))


def rates():
    """The nine exponential rates as exact Fractions, in certificate order."""
    out = []
    for comp, kind, idx in RATE_ORDER:
        out.append(Fraction(SHORT[comp][idx][0]) if kind == "short" else Fraction(LONG[comp][0]))
    return out


def fingerprint():
    """sha256 over the frozen constants, written in the same layout as the C1-A parameter fingerprint."""
    parts = [CONTRACT, str(Fraction(BOHR_ANGSTROM)), str(Fraction(R_MIN_ANGSTROM))]
    for name in ("BO", "REL", "QED"):
        for j, (alpha, coefs) in enumerate(SHORT[name], start=1):
            parts.append(f"{name}.short.{j}:{Fraction(alpha)}:"
                         + ",".join(f"{i}={Fraction(c)}" for i, c in sorted(coefs.items())))
        eta, kadd, cs = LONG[name]
        parts.append(f"{name}.long:{Fraction(eta)}:{kadd}:"
                     + ",".join(f"{k}={Fraction(c)}" for k, c in sorted(cs.items())))
    parts.append("RET_A:" + ",".join(str(Fraction(x)) for x in RET_A))
    parts.append("RET_B:" + ",".join(str(Fraction(x)) for x in RET_B))
    for name, params in (("SIGMA_BO", SIGMA_BO), ("SIGMA_REL", SIGMA_REL)):
        parts.append(name + ":" + ",".join(f"{Fraction(a)}/{Fraction(s)}" for a, s in params))
    return hashlib.sha256("\n".join(parts).encode()).hexdigest()


# --- verdicts ---------------------------------------------------------------------------------------------------

class _Invalid(Exception):
    pass


class _Refused(Exception):
    pass


class Limits:
    """Operational limits. Hitting one gives REFUSED, never INVALID."""

    def __init__(self, sqrt_bits_max=4096, order_max=20000, bits_max=8_000_000, seconds_max=300.0, digits_max=4300):
        self.sqrt_bits_max, self.order_max = sqrt_bits_max, order_max
        self.bits_max, self.seconds_max, self.digits_max = bits_max, seconds_max, digits_max

    def as_dict(self):
        return {"sqrt_bits_max": self.sqrt_bits_max, "order_max": self.order_max, "bits_max": self.bits_max,
                "seconds_max": self.seconds_max, "digits_max": self.digits_max}


class Result:
    def __init__(self, status, raw, reason, stats):
        self.status, self.raw, self.reason, self.stats = status, raw, reason, stats

    def __repr__(self):
        return f"Result({self.status}, raw={self.raw}, reason={self.reason})"

    @property
    def valid(self):
        return self.status == "VALID"


class _Ctx:
    def __init__(self, limits):
        self.limits, self.t0, self.max_bits = limits, time.monotonic(), 0

    def tick(self):
        if time.monotonic() - self.t0 > self.limits.seconds_max:
            raise _Refused("time_limit")

    def note(self, *fracs):
        for f in fracs:
            b = max(f.numerator.bit_length(), f.denominator.bit_length())
            if b > self.max_bits:
                self.max_bits = b
        if self.max_bits > self.limits.bits_max:
            raise _Refused("size_limit")


# --- exact interval arithmetic -----------------------------------------------------------------------------------

class _Iv:
    __slots__ = ("lo", "hi")

    def __init__(self, lo, hi=None):
        self.lo = Fraction(lo)
        self.hi = Fraction(lo if hi is None else hi)
        if self.lo > self.hi:
            raise _Invalid("interval_order")

    def add(self, o):
        return _Iv(self.lo + o.lo, self.hi + o.hi)

    def sub(self, o):
        return _Iv(self.lo - o.hi, self.hi - o.lo)

    def neg(self):
        return _Iv(-self.hi, -self.lo)

    def mul(self, o):
        p = (self.lo * o.lo, self.lo * o.hi, self.hi * o.lo, self.hi * o.hi)
        return _Iv(min(p), max(p))

    def scale(self, c):
        a, b = self.lo * c, self.hi * c
        return _Iv(min(a, b), max(a, b))

    def div(self, o):
        if not o.lo > 0:
            raise _Invalid("division_by_nonpositive")
        q = (self.lo / o.lo, self.lo / o.hi, self.hi / o.lo, self.hi / o.hi)
        return _Iv(min(q), max(q))


def _rpow(R, i):
    """R^i for an integer i, R.lo > 0."""
    if i >= 0:
        return _Iv(R.lo ** i, R.hi ** i)
    return _Iv(R.hi ** i, R.lo ** i)


def _poly(R, coefs):
    out = _Iv(0)
    for i, c in coefs.items():
        c = Fraction(c)
        if c != 0:
            out = out.add(_rpow(R, i).scale(c))
    return out


def _dpoly(R, coefs):
    out = _Iv(0)
    for i, c in coefs.items():
        c = Fraction(c)
        if c != 0 and i != 0:
            out = out.add(_rpow(R, i - 1).scale(c * i))
    return out


# --- exp(-x) enclosure -------------------------------------------------------------------------------------------

def _series(y, n, ctx):
    """(S_n(y), t_{n+1}(y)) exactly: S_n = sum_{k<=n} y^k/k!, t_{n+1} = y^(n+1)/(n+1)!. Horner on unreduced integers."""
    p, q = y.numerator, y.denominator
    num, den = 1, 1
    for j in range(n, 0, -1):
        num, den = q * j * den + p * num, q * j * den
        if j % 64 == 0:
            ctx.tick()
    S = Fraction(num, den)
    t = Fraction(p ** (n + 1), q ** (n + 1) * math.factorial(n + 1))
    ctx.note(S, t)
    return S, t


def _exp_interval(rate, r, mode, n, ctx):
    """Enclosure of exp(-rate*R) for R in r. Conditions are properties of the certificate (INVALID); size is a limit."""
    x_lo, x_hi = rate * r.lo, rate * r.hi
    if mode == "full" and not Fraction(n + 2) > x_hi:
        raise _Invalid("exp_condition")
    if n > ctx.limits.order_max:
        raise _Refused("order_limit")
    est = (n + 1) * (max(x_hi.numerator.bit_length(), x_hi.denominator.bit_length()) + 12)
    if est > ctx.limits.bits_max:
        raise _Refused("size_limit")
    S_lo, _ = _series(x_lo, n, ctx)
    upper = 1 / S_lo
    if mode == "zero_floor":
        return _Iv(0, upper)
    S_hi, t_hi = _series(x_hi, n, ctx)
    U_hi = t_hi * (n + 2) / (n + 2 - x_hi)
    lower = 1 / (S_hi + U_hi)
    return _Iv(lower, upper)


# --- dV/dR of the frozen model (retardation ON) ------------------------------------------------------------------

def _retardation(R):
    """g(R) and g'(R) as intervals, g = Nr/Dn."""
    Nr, dNr, Dn, dDn = _Iv(1), _Iv(0), _Iv(1), _Iv(0)
    for m, a in enumerate(RET_A):
        Nr = Nr.add(_rpow(R, m + 1).scale(Fraction(a)))
        dNr = dNr.add(_rpow(R, m).scale(Fraction(a) * (m + 1)))
    for m, b in enumerate(RET_B):
        Dn = Dn.add(_rpow(R, m + 1).scale(Fraction(b)))
        dDn = dDn.add(_rpow(R, m).scale(Fraction(b) * (m + 1)))
    g = Nr.div(Dn)
    dg = dNr.mul(Dn).sub(Nr.mul(dDn)).div(Dn.mul(Dn))
    return g, dg


def _dv(R, E, ctx):
    """dV/dR (retardation ON) as an interval over R. E[slot] encloses exp(-rate*R), slots as in RATE_ORDER."""
    total = _Iv(0)
    g, dg = _retardation(R)
    for name in ("BO", "REL", "QED"):
        for idx, (alpha, coefs) in enumerate(SHORT[name]):
            alpha = Fraction(alpha)
            e = E[RATE_ORDER.index((name, "short", idx))]
            term = e.mul(_dpoly(R, coefs).sub(_poly(R, coefs).scale(alpha)))
            total = total.add(term)
        eta, kadd, cs = LONG[name]
        eta = Fraction(eta)
        e = E[RATE_ORDER.index((name, "long", 0))]
        x = R.scale(eta)
        kmin, done = min(cs), 0
        cum_lo = cum_hi = Fraction(1)
        term_lo = term_hi = Fraction(1)
        for k in sorted(cs):
            n = 2 * k + kadd
            for i in range(done + 1, n + 1):
                term_lo = term_lo * x.lo / i
                term_hi = term_hi * x.hi / i
                cum_lo += term_lo
                cum_hi += term_hi
            done = n
            T = e.mul(_Iv(cum_lo, cum_hi))
            base = e.mul(_Iv(term_lo, term_hi)).scale(eta)
            if name == "BO" and k == kmin:
                D, dD = g.sub(T), base.add(dg)
            elif name == "REL" and k == kmin:
                D, dD = T.neg(), base
            else:
                D, dD = _Iv(1).sub(T), base
            c = Fraction(cs[k])
            total = total.sub(dD.mul(_rpow(R, -2 * k)).scale(c))
            total = total.add(D.mul(_rpow(R, -2 * k - 1)).scale(c * 2 * k))
            ctx.tick()
    return total


# --- certificate parsing -----------------------------------------------------------------------------------------

def _int_syntax(s, what):
    """The digits of a canonical decimal integer string (optional leading '-'), or INVALID. Syntax only: no conversion,
    so the length of the string can never make this raise anything but INVALID."""
    if not isinstance(s, str) or not s or s != s.strip():
        raise _Invalid("bad_integer:" + what)
    body = s[1:] if s[0] == "-" else s
    if not (body.isascii() and body.isdigit()) or (len(body) > 1 and body[0] == "0"):
        raise _Invalid("bad_integer:" + what)
    return body


def _big_int(s, what, ctx):
    """A syntactically valid integer string is converted unless it is operationally too long: then REFUSED.
    Python also refuses to convert very long decimal strings (sys.set_int_max_str_digits); that limit is a resource
    limit of the process, not a property of the certificate, so it is REFUSED too (never a leaked ValueError)."""
    body = _int_syntax(s, what)
    if len(body) > ctx.limits.digits_max:
        raise _Refused("integer_size_limit")
    try:
        return int(s)
    except ValueError:                       # the syntax is already checked: only the process conversion limit is left
        raise _Refused("integer_size_limit")


def _small_int(v, what):
    if type(v) is not int:
        raise _Invalid("bad_integer:" + what)
    return v


def _rational_syntax(s, what):
    if not isinstance(s, str) or s != s.strip():
        raise _Invalid("bad_rational:" + what)
    parts = s.split("/")
    if len(parts) > 2:
        raise _Invalid("bad_rational:" + what)
    for part in parts:
        _int_syntax(part, what)
    if len(parts) == 2 and (parts[1].startswith("-") or parts[1] == "0"):
        raise _Invalid("bad_rational:" + what)
    return parts


def _rational(s, what, ctx):
    parts = _rational_syntax(s, what)
    num = _big_int(parts[0], what, ctx)
    den = _big_int(parts[1], what, ctx) if len(parts) == 2 else 1
    return Fraction(num, den)


def _keys(d, required, optional, where):
    if not isinstance(d, dict):
        raise _Invalid("not_an_object:" + where)
    if len(d) > len(required) + len(optional):          # too many keys: decided without looking at any of them
        raise _Invalid("keys:" + where)
    keys = set(d)
    if not set(required) <= keys or not keys <= set(required) | set(optional):
        raise _Invalid("keys:" + where)
    return d


# --- the check ---------------------------------------------------------------------------------------------------

def _prepass(cert):
    """Syntax before size. Every wrong key set and every malformed integer / rational string is INVALID here, before
    any operational size limit can answer REFUSED, whatever the lengths are. Nothing is converted.
    Shapes are checked before contents (key count, dr_raw length 3, exp length 9), so the work done here is bounded by
    the format, not by how large a malformed certificate is; only the strings themselves are read, once."""
    _keys(cert, ("format", "method", "model", "input", "output", "proof"), ("runtime_binding",), "certificate")
    inp = _keys(cert["input"], ("position_frac_bits", "dr_raw", "component", "dt_kick"), (), "input")
    if not isinstance(inp["dr_raw"], list) or len(inp["dr_raw"]) != 3:      # the shape first: never walk a wrong-sized list
        raise _Invalid("input")
    for v in inp["dr_raw"]:
        _int_syntax(v, "dr_raw")
    _rational_syntax(inp["dt_kick"], "dt_kick")
    _int_syntax(_keys(cert["output"], ("width", "frac_bits", "raw"), (), "output")["raw"], "raw")
    proof = _keys(cert["proof"], ("sqrt_bits", "exp"), (), "proof")
    _int_syntax(proof["sqrt_bits"], "sqrt_bits")
    if not isinstance(proof["exp"], list) or len(proof["exp"]) != len(RATE_ORDER):
        raise _Invalid("exp_list")
    for entry in proof["exp"]:
        _keys(entry, ("rate", "mode", "order"), (), "exp")
        _rational_syntax(entry["rate"], "rate")
        _int_syntax(entry["order"], "order")


def _sqrt_interval(R2, N):
    """[a/2^N, (a+1)/2^N] with a = isqrt(floor(R2 * 4^N)); contains sqrt(R2) (verified again by the caller)."""
    F = (R2.numerator << (2 * N)) // R2.denominator
    a = math.isqrt(F)
    return _Iv(Fraction(a, 1 << N), Fraction(a + 1, 1 << N))


def _decide_raw(J, m):
    """Strict separation: J must lie strictly inside the open rounding cell of raw m (no tie rule is used)."""
    ulp = Fraction(1, 1 << OUT_FRAC)
    cell_lo, cell_hi = (2 * m - 1) * ulp / 2, (2 * m + 1) * ulp / 2
    if cell_lo < J.lo and J.hi < cell_hi:
        return
    if J.hi < cell_lo or J.lo > cell_hi:
        raise _Invalid("raw_mismatch")
    raise _Invalid("not_separated")


def _check(cert, ctx):
    _prepass(cert)
    if cert["format"] != FORMAT or cert["method"] != METHOD:
        raise _Invalid("format")
    if "runtime_binding" in cert and not isinstance(cert["runtime_binding"], dict):
        raise _Invalid("not_an_object:runtime_binding")

    model = _keys(cert["model"], ("contract", "parameter_fingerprint", "retardation"), (), "model")
    if model["contract"] != CONTRACT or model["retardation"] is not True:
        raise _Invalid("model_binding")
    computed = fingerprint()
    if not (computed == FROZEN_FINGERPRINT == model["parameter_fingerprint"]):
        raise _Invalid("model_binding")

    inp = _keys(cert["input"], ("position_frac_bits", "dr_raw", "component", "dt_kick"), (), "input")
    if _small_int(inp["position_frac_bits"], "position_frac_bits") != POSITION_FRAC_BITS:
        raise _Invalid("input")
    comp = _small_int(inp["component"], "component")
    if comp not in (0, 1, 2):
        raise _Invalid("input")
    if not isinstance(inp["dr_raw"], list) or len(inp["dr_raw"]) != 3:
        raise _Invalid("input")
    dr = [_big_int(v, "dr_raw", ctx) for v in inp["dr_raw"]]
    if any(abs(v) >= 1 << 96 for v in dr):
        raise _Invalid("input_range")
    dt = _rational(inp["dt_kick"], "dt_kick", ctx)
    if dt == 0:
        raise _Invalid("input")
    if dr[comp] == 0:
        raise _Invalid("not_a_decision")
    R2 = Fraction(sum(v * v for v in dr), 1 << (2 * POSITION_FRAC_BITS))
    bohr = Fraction(BOHR_ANGSTROM)
    if R2 * bohr * bohr < Fraction(R_MIN_ANGSTROM) ** 2:
        raise _Invalid("physics_domain")

    out = _keys(cert["output"], ("width", "frac_bits", "raw"), (), "output")
    if _small_int(out["width"], "width") != OUT_WIDTH or _small_int(out["frac_bits"], "frac_bits") != OUT_FRAC:
        raise _Invalid("output_profile")
    m = _big_int(out["raw"], "raw", ctx)
    if not -(1 << (OUT_WIDTH - 1)) <= m <= (1 << (OUT_WIDTH - 1)) - 1:
        raise _Invalid("out_of_range")

    proof = _keys(cert["proof"], ("sqrt_bits", "exp"), (), "proof")
    N = _big_int(proof["sqrt_bits"], "sqrt_bits", ctx)
    if N < 1:
        raise _Invalid("sqrt_bits")
    if not isinstance(proof["exp"], list) or len(proof["exp"]) != len(RATE_ORDER):
        raise _Invalid("exp_list")
    plan = []
    for entry, rate in zip(proof["exp"], rates()):
        _keys(entry, ("rate", "mode", "order"), (), "exp")
        if _rational(entry["rate"], "rate", ctx) != rate:
            raise _Invalid("exp_rate")
        if entry["mode"] not in ("full", "zero_floor"):
            raise _Invalid("exp_mode")
        order = _big_int(entry["order"], "order", ctx)
        if order < 0:
            raise _Invalid("exp_order")
        plan.append((rate, entry["mode"], order))

    # --- from here on, work is limited by operational limits (REFUSED) ---
    if N > ctx.limits.sqrt_bits_max:
        raise _Refused("sqrt_limit")

    r = _sqrt_interval(R2, N)
    if not (r.lo > 0 and r.lo * r.lo <= R2 <= r.hi * r.hi):
        raise _Invalid("sqrt_enclosure")

    # exp enclosures; conditions (INVALID) are examined before any limit that could hide them
    for rate, mode, order in plan:
        if mode == "full" and not Fraction(order + 2) > rate * r.hi:
            raise _Invalid("exp_condition")
    E = []
    for rate, mode, order in plan:
        E.append(_exp_interval(rate, r, mode, order, ctx))
        ctx.tick()

    dv = _dv(r, E, ctx)
    G = dv.neg().mul(_Iv(1 / r.hi, 1 / r.lo))
    J = G.scale(Fraction(dr[comp], 1 << POSITION_FRAC_BITS) * dt)
    ctx.note(J.lo, J.hi)

    _decide_raw(J, m)
    return m, plan


def check_certificate(cert, limits=None):
    """Decide one certificate (a dict). Returns Result(status in VALID / INVALID / REFUSED, raw, reason, stats)."""
    limits = limits or Limits()
    ctx = _Ctx(limits)

    def stats():
        return {"seconds": round(time.monotonic() - ctx.t0, 3), "max_bits": ctx.max_bits, "limits": limits.as_dict()}
    try:
        m, plan = _check(cert, ctx)
        s = stats()
        s["orders"] = [o for _, _, o in plan]
        return Result("VALID", m, "strictly_separated", s)
    except _Invalid as e:
        return Result("INVALID", None, str(e), stats())
    except _Refused as e:
        return Result("REFUSED", None, str(e), stats())
    except MemoryError:
        return Result("REFUSED", None, "memory_limit", stats())

