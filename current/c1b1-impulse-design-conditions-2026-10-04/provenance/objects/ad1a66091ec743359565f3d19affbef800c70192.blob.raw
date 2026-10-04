"""C1-B1 exact impulse certificate CHECKER V2, format c1b1-exact-impulse-certificate-v2 (outward dyadic rounding).

Design: docs/active/C1B1_EXACT_IMPULSE_CHECKER_V2_DESIGN.md. The trusted V1 checker (c1b1_exact_impulse_checker) is the
reference and is not modified; this module neither imports it nor shares code with it, so the two can cross-check.

WHAT IT DECIDES (same claim as V1). VALID(m): the exact impulse component J_k of the FROZEN C1-A model (retardation ON)
for the stated relative position and kick interval rounds to raw m on FX(96,80), decided by STRICT separation of an
enclosure from the two half-ulp boundaries of m. INVALID: the certificate does not prove it (reason named).
REFUSED: an operational limit was hit. Operational limits affect availability, never truth.

WHAT CHANGES FROM V1. V1 carries exact rationals to the end, so numbers grow like (exp order) x (sqrt bits). V2 rounds
interval END POINTS at chosen points to `work_bits` significant bits, ALWAYS OUTWARD: a lower end goes down (towards
-infinity, a mathematical floor, also for negative numbers), an upper end goes up. The bits cut off are not assumed
away: moving the ends outward absorbs them into the width, so every rounding keeps
    new_lo <= old_lo <= true value <= old_hi <= new_hi.
A too-wide enclosure only fails safely (not_separated). This rounding is a proof representation only: it does not
round the world state and changes nothing in the executor.

WHERE IT ROUNDS (design section 3): after every product, quotient and reciprocal, after every step of the exp and
damping series, once per assembled term and on non-dyadic constants. Not after negation, not after the fixed small
additions inside one term, not in the sqrt enclosure (already dyadic), not in the final exact J = G * (dr_k * dt).

INDEPENDENCE. Imports only fractions, hashlib, json, math, time. No executor, no C1-A evaluator, no a_numeric, no V1.
"""
import hashlib
import json
import math
import time
from fractions import Fraction

FORMAT = "c1b1-exact-impulse-certificate-v2"
METHOD = "dyadic-outward-taylor-v2"
CONTRACT = "c1a-ar2-lang2024-v1"
FROZEN_FINGERPRINT = "ada6153be05af3e582139fdc81b5697fffaf18d12f9f2de6e8d5ac2fdfe0839e"

BOHR_ANGSTROM = "0.529177210903"
R_MIN_ANGSTROM = "1.2"
POSITION_FRAC_BITS = 48
OUT_WIDTH, OUT_FRAC = 96, 80

# --- frozen constants (exact decimals of the published Fortran), an independent copy bound by the fingerprint -----
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

RATE_ORDER = (("BO", "short", 0), ("BO", "short", 1), ("REL", "short", 0), ("REL", "short", 1),
              ("QED", "short", 0), ("QED", "short", 1), ("BO", "long", 0), ("REL", "long", 0), ("QED", "long", 0))


def rates():
    return [Fraction(SHORT[c][i][0]) if kind == "short" else Fraction(LONG[c][0]) for c, kind, i in RATE_ORDER]


def fingerprint():
    """sha256 over the frozen constants in the layout of the C1-A parameter fingerprint."""
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


# --- verdict plumbing ---------------------------------------------------------------------------------------------

class _Invalid(Exception):
    pass


class _Refused(Exception):
    pass


class Limits:
    """Operational limits. Hitting one gives REFUSED, never INVALID."""

    def __init__(self, sqrt_bits_max=65536, work_bits_max=65536, order_max=200000, bits_max=4_000_000,
                 seconds_max=600.0, digits_max=4300):
        self.sqrt_bits_max, self.work_bits_max, self.order_max = sqrt_bits_max, work_bits_max, order_max
        self.bits_max, self.seconds_max, self.digits_max = bits_max, seconds_max, digits_max

    def as_dict(self):
        return {"sqrt_bits_max": self.sqrt_bits_max, "work_bits_max": self.work_bits_max, "order_max": self.order_max,
                "bits_max": self.bits_max, "seconds_max": self.seconds_max, "digits_max": self.digits_max}


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
        self.limits, self.t0, self.max_bits, self.max_mantissa = limits, time.monotonic(), 0, 0

    def tick(self):
        if time.monotonic() - self.t0 > self.limits.seconds_max:
            raise _Refused("time_limit")

    def note(self, *fracs):
        """Track sizes. max_bits: the largest numerator or denominator (memory). max_mantissa: the significant bits of
        a dyadic (odd part of the numerator); the exponent of a tiny dyadic lives in its denominator, not here."""
        for f in fracs:
            b = max(f.numerator.bit_length(), f.denominator.bit_length())
            if b > self.max_bits:
                self.max_bits = b
            n = abs(f.numerator)
            mant = (n >> ((n & -n).bit_length() - 1)).bit_length() if n else 0
            if mant > self.max_mantissa:
                self.max_mantissa = mant
        if self.max_bits > self.limits.bits_max:
            raise _Refused("size_limit")


# --- directed dyadic rounding (design section 1) ------------------------------------------------------------------

def down(x, P):
    """The largest dyadic m*2^e <= x whose mantissa has about P+1..P+2 bits. Mathematical floor (towards -infinity)."""
    x = Fraction(x)
    if x == 0:
        return x
    a, b = x.numerator, x.denominator
    e = abs(a).bit_length() - b.bit_length() - P - 1
    if e >= 0:
        return Fraction((a // (b << e)) << e)
    return Fraction((a << -e) // b, 1 << -e)


def up(x, P):
    """The smallest dyadic >= x with the same mantissa size (ceiling towards +infinity): -down(-x)."""
    return -down(-Fraction(x), P)


class _Iv:
    """Closed interval [lo, hi] of exact rationals. Every rounding method returns an interval CONTAINING self's
    exact result."""
    __slots__ = ("lo", "hi")

    def __init__(self, lo, hi=None):
        self.lo = Fraction(lo)
        self.hi = Fraction(lo if hi is None else hi)
        if self.lo > self.hi:
            raise _Invalid("interval_order")

    def rnd(self, P):
        return _Iv(down(self.lo, P), up(self.hi, P))

    def add(self, o):                     # exact (dyadic + dyadic is dyadic); rounded by the caller once per term
        return _Iv(self.lo + o.lo, self.hi + o.hi)

    def sub(self, o):
        return _Iv(self.lo - o.hi, self.hi - o.lo)

    def neg(self):
        return _Iv(-self.hi, -self.lo)

    def mul(self, o, P):
        p = (self.lo * o.lo, self.lo * o.hi, self.hi * o.lo, self.hi * o.hi)
        return _Iv(down(min(p), P), up(max(p), P))

    def div(self, o, P):
        if not o.lo > 0:
            raise _Invalid("division_by_nonpositive")
        q = (self.lo / o.lo, self.lo / o.hi, self.hi / o.lo, self.hi / o.hi)
        return _Iv(down(min(q), P), up(max(q), P))


def _const(c, P):
    """A rational constant as a tight outward dyadic interval (exact if c is already dyadic of small size)."""
    c = Fraction(c)
    return _Iv(down(c, P), up(c, P))


def _sqrt_interval(R2, N):
    """[a/2^N, (a+1)/2^N], a = isqrt(floor(R2 * 4^N)). Already dyadic: not rounded again."""
    F = (R2.numerator << (2 * N)) // R2.denominator
    a = math.isqrt(F)
    return _Iv(Fraction(a, 1 << N), Fraction(a + 1, 1 << N))


def _powers(R, P):
    """R^i for i in -17..6 as intervals (R.lo > 0): products of positive intervals, each rounded outward."""
    pw = {0: _Iv(1), 1: R}
    for i in range(2, 7):
        pw[i] = pw[i - 1].mul(R, P)
    inv = _Iv(down(1 / R.hi, P), up(1 / R.lo, P))
    pw[-1] = inv
    for i in range(2, 18):
        pw[-i] = pw[-(i - 1)].mul(inv, P)
    return pw


# --- exp(-x) enclosure (design section 6) -------------------------------------------------------------------------

def _series_lower(y, n, P, ctx):
    """A lower bound of S_n(y) = sum_{k<=n} y^k/k! for y > 0: every term and partial sum rounded down."""
    t = S = Fraction(1)
    for k in range(1, n + 1):
        t = down(t * y / k, P)
        S = down(S + t, P)
        if k % 256 == 0:
            ctx.tick()
    ctx.note(t, S)
    return S


def _series_upper(y, n, P, ctx):
    """Upper bounds of S_n(y) and of t_{n+1}(y) = y^(n+1)/(n+1)! for y > 0: every step rounded up."""
    t = S = Fraction(1)
    for k in range(1, n + 1):
        t = up(t * y / k, P)
        S = up(S + t, P)
        if k % 256 == 0:
            ctx.tick()
    t1 = up(t * y / (n + 1), P)
    ctx.note(t, S, t1)
    return S, t1


def _exp_combine(mode, n, x_hi, S_lo, S_hi, t_hi, P):
    """The last step of the exp enclosure, separated so each rounding direction can be tested against exact inputs.
    Given S_lo <= S_n(x.lo), S_hi >= S_n(x.hi) and t_hi >= t_{n+1}(x.hi):
        upper = up(1/S_lo)                                   >= 1/S_n(x.lo) >= exp(-x.lo)
        U_hi  = up(t_hi (n+2)/(n+2-x_hi))                    >= U_n(x.hi)   (n + 2 > x_hi)
        lower = down(1/(S_hi + U_hi))                        <= 1/(S_n + U_n)(x.hi) <= exp(-x.hi)"""
    upper = up(1 / S_lo, P)
    if mode == "zero_floor":
        return _Iv(0, upper)
    U_hi = up(t_hi * (n + 2) / (n + 2 - x_hi), P)
    lower = down(1 / (S_hi + U_hi), P)
    return _Iv(lower, upper)


def _exp_interval(x, mode, n, P, ctx):
    """Enclosure of exp(-v) for every v in x (x.lo > 0).
    full (n + 2 > x.hi):  [down(1/(S_n^+(x.hi) + U_n^+(x.hi))), up(1/S_n^-(x.lo))]
    zero_floor:           [0, up(1/S_n^-(x.lo))]"""
    if not x.lo > 0:
        raise _Invalid("exp_argument")
    if mode == "full" and not Fraction(n + 2) > x.hi:
        raise _Invalid("exp_condition")
    if n > ctx.limits.order_max:
        raise _Refused("order_limit")
    S_lo = _series_lower(x.lo, n, P, ctx)
    if mode == "zero_floor":
        return _exp_combine(mode, n, x.hi, S_lo, None, None, P)
    S_hi, t_hi = _series_upper(x.hi, n, P, ctx)
    out = _exp_combine(mode, n, x.hi, S_lo, S_hi, t_hi, P)
    ctx.note(out.lo, out.hi)
    return out


# --- dV/dR of the frozen model, retardation ON (design section 7) -------------------------------------------------

def _poly(pw, coefs, P):
    out = _Iv(0)
    for i, c in coefs.items():
        if Fraction(c) != 0:
            out = out.add(pw[i].mul(_const(c, P), P))
    return out.rnd(P)


def _dpoly(pw, coefs, P):
    out = _Iv(0)
    for i, c in coefs.items():
        c = Fraction(c)
        if c != 0 and i != 0:
            out = out.add(pw[i - 1].mul(_const(c * i, P), P))
    return out.rnd(P)


def _retardation(pw, P):
    Nr, dNr, Dn, dDn = _Iv(1), _Iv(0), _Iv(1), _Iv(0)
    for m, a in enumerate(RET_A):
        Nr = Nr.add(pw[m + 1].mul(_const(a, P), P))
        dNr = dNr.add(pw[m].mul(_const(Fraction(a) * (m + 1), P), P))
    for m, b in enumerate(RET_B):
        Dn = Dn.add(pw[m + 1].mul(_const(b, P), P))
        dDn = dDn.add(pw[m].mul(_const(Fraction(b) * (m + 1), P), P))
    Nr, dNr, Dn, dDn = Nr.rnd(P), dNr.rnd(P), Dn.rnd(P), dDn.rnd(P)
    g = Nr.div(Dn, P)
    dg = dNr.mul(Dn, P).sub(Nr.mul(dDn, P)).rnd(P).div(Dn.mul(Dn, P), P)
    return g, dg


def _dv(R, E, P, ctx):
    """dV/dR as an interval over R; E[slot] encloses exp(-rate*R) for R in R, slots as in RATE_ORDER."""
    pw = _powers(R, P)
    g, dg = _retardation(pw, P)
    total = _Iv(0)
    for name in ("BO", "REL", "QED"):
        for idx, (alpha, coefs) in enumerate(SHORT[name]):
            e = E[RATE_ORDER.index((name, "short", idx))]
            inner = _dpoly(pw, coefs, P).sub(_poly(pw, coefs, P).mul(_const(alpha, P), P)).rnd(P)
            total = total.add(e.mul(inner, P))
        eta, kadd, cs = LONG[name]
        eta_iv = _const(eta, P)
        e = E[RATE_ORDER.index((name, "long", 0))]
        x = R.mul(eta_iv, P)
        kmin, done = min(cs), 0
        cum_lo = cum_hi = term_lo = term_hi = Fraction(1)
        for k in sorted(cs):
            n = 2 * k + kadd
            for i in range(done + 1, n + 1):            # positive chains: lower rounded down, upper rounded up
                term_lo = down(term_lo * x.lo / i, P)
                term_hi = up(term_hi * x.hi / i, P)
                cum_lo = down(cum_lo + term_lo, P)
                cum_hi = up(cum_hi + term_hi, P)
            done = n
            T = e.mul(_Iv(cum_lo, cum_hi), P)
            base = e.mul(_Iv(term_lo, term_hi), P).mul(eta_iv, P)
            if name == "BO" and k == kmin:
                D, dD = g.sub(T), base.add(dg)
            elif name == "REL" and k == kmin:
                D, dD = T.neg(), base
            else:
                D, dD = _Iv(1).sub(T), base
            c = _const(cs[k], P)
            term = dD.mul(pw[-2 * k], P).mul(c, P).neg()
            term = term.add(D.mul(pw[-2 * k - 1], P).mul(c, P).mul(_const(2 * k, P), P))
            total = total.add(term.rnd(P))
            ctx.tick()
        total = total.rnd(P)
    return total


# --- certificate parsing (independent copy of the V1 rules; syntax before size, shape before contents) ------------

def _int_syntax(s, what):
    if not isinstance(s, str) or not s or s != s.strip():
        raise _Invalid("bad_integer:" + what)
    body = s[1:] if s[0] == "-" else s
    if not (body.isascii() and body.isdigit()) or (len(body) > 1 and body[0] == "0"):
        raise _Invalid("bad_integer:" + what)
    return body


def _big_int(s, what, ctx):
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
    if len(d) > len(required) + len(optional):
        raise _Invalid("keys:" + where)
    keys = set(d)
    if not set(required) <= keys or not keys <= set(required) | set(optional):
        raise _Invalid("keys:" + where)
    return d


def _prepass(cert):
    _keys(cert, ("format", "method", "model", "input", "output", "proof"), ("runtime_binding",), "certificate")
    inp = _keys(cert["input"], ("position_frac_bits", "dr_raw", "component", "dt_kick"), (), "input")
    if not isinstance(inp["dr_raw"], list) or len(inp["dr_raw"]) != 3:
        raise _Invalid("input")
    for v in inp["dr_raw"]:
        _int_syntax(v, "dr_raw")
    _rational_syntax(inp["dt_kick"], "dt_kick")
    _int_syntax(_keys(cert["output"], ("width", "frac_bits", "raw"), (), "output")["raw"], "raw")
    proof = _keys(cert["proof"], ("sqrt_bits", "work_bits", "exp"), (), "proof")
    _int_syntax(proof["sqrt_bits"], "sqrt_bits")
    _int_syntax(proof["work_bits"], "work_bits")
    if not isinstance(proof["exp"], list) or len(proof["exp"]) != len(RATE_ORDER):
        raise _Invalid("exp_list")
    for entry in proof["exp"]:
        _keys(entry, ("rate", "mode", "order"), (), "exp")
        _rational_syntax(entry["rate"], "rate")
        _int_syntax(entry["order"], "order")


def _decide_raw(J, m):
    ulp = Fraction(1, 1 << OUT_FRAC)
    cell_lo, cell_hi = (2 * m - 1) * ulp / 2, (2 * m + 1) * ulp / 2
    if cell_lo < J.lo and J.hi < cell_hi:
        return
    if J.hi < cell_lo or J.lo > cell_hi:
        raise _Invalid("raw_mismatch")
    raise _Invalid("not_separated")


def _compute(cert, ctx):
    """Parse and validate the certificate, then compute the enclosure J. Returns (m, plan, J); no decision yet."""
    _prepass(cert)
    if cert["format"] != FORMAT or cert["method"] != METHOD:
        raise _Invalid("format")
    if "runtime_binding" in cert and not isinstance(cert["runtime_binding"], dict):
        raise _Invalid("not_an_object:runtime_binding")
    model = _keys(cert["model"], ("contract", "parameter_fingerprint", "retardation"), (), "model")
    if model["contract"] != CONTRACT or model["retardation"] is not True:
        raise _Invalid("model_binding")
    if not (fingerprint() == FROZEN_FINGERPRINT == model["parameter_fingerprint"]):
        raise _Invalid("model_binding")

    inp = cert["input"]
    if _small_int(inp["position_frac_bits"], "position_frac_bits") != POSITION_FRAC_BITS:
        raise _Invalid("input")
    comp = _small_int(inp["component"], "component")
    if comp not in (0, 1, 2):
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

    out = cert["output"]
    if _small_int(out["width"], "width") != OUT_WIDTH or _small_int(out["frac_bits"], "frac_bits") != OUT_FRAC:
        raise _Invalid("output_profile")
    m = _big_int(out["raw"], "raw", ctx)
    if not -(1 << (OUT_WIDTH - 1)) <= m <= (1 << (OUT_WIDTH - 1)) - 1:
        raise _Invalid("out_of_range")

    proof = cert["proof"]
    N = _big_int(proof["sqrt_bits"], "sqrt_bits", ctx)
    P = _big_int(proof["work_bits"], "work_bits", ctx)
    if N < 1:
        raise _Invalid("sqrt_bits")
    if P < 8:
        raise _Invalid("work_bits")
    plan = []
    for entry, rate in zip(proof["exp"], rates()):
        if _rational(entry["rate"], "rate", ctx) != rate:
            raise _Invalid("exp_rate")
        if entry["mode"] not in ("full", "zero_floor"):
            raise _Invalid("exp_mode")
        order = _big_int(entry["order"], "order", ctx)
        if order < 0:
            raise _Invalid("exp_order")
        plan.append((rate, entry["mode"], order))

    # --- work from here on is limited by operational limits (REFUSED) ---
    if N > ctx.limits.sqrt_bits_max:
        raise _Refused("sqrt_limit")
    if P > ctx.limits.work_bits_max:
        raise _Refused("work_limit")
    r = _sqrt_interval(R2, N)
    if not (r.lo > 0 and r.lo * r.lo <= R2 <= r.hi * r.hi):
        raise _Invalid("sqrt_enclosure")
    xs = [r.mul(_const(rate, P), P) for rate, _, _ in plan]
    for (rate, mode, order), x in zip(plan, xs):          # certificate conditions (INVALID) before any limit
        if mode == "full" and not Fraction(order + 2) > x.hi:
            raise _Invalid("exp_condition")
    E = []
    for (rate, mode, order), x in zip(plan, xs):
        E.append(_exp_interval(x, mode, order, P, ctx))
        ctx.tick()
    dv = _dv(r, E, P, ctx)
    inv = _Iv(down(1 / r.hi, P), up(1 / r.lo, P))
    G = dv.neg().mul(inv, P)
    c = Fraction(dr[comp], 1 << POSITION_FRAC_BITS) * dt       # exact scalar; the final product is not rounded
    a, b = G.lo * c, G.hi * c
    J = _Iv(min(a, b), max(a, b))
    ctx.note(G.lo, G.hi)
    return m, plan, J


def _check(cert, ctx):
    m, plan, J = _compute(cert, ctx)
    _decide_raw(J, m)
    return m, plan, J


def enclosure(cert, limits=None):
    """DIAGNOSTIC (measurements only, never a verdict): the enclosure J of a structurally valid certificate and the
    run statistics, whether or not it separates. Raises what _compute raises."""
    ctx = _Ctx(limits or Limits())
    m, plan, J = _compute(cert, ctx)
    return J, {"seconds": round(time.monotonic() - ctx.t0, 3), "max_bits": ctx.max_bits,
               "max_mantissa_bits": ctx.max_mantissa, "orders": [o for _, _, o in plan]}


def check_certificate(cert, limits=None):
    """Decide one V2 certificate (a dict). Returns Result(status in VALID / INVALID / REFUSED, raw, reason, stats)."""
    limits = limits or Limits()
    ctx = _Ctx(limits)

    def stats():
        return {"seconds": round(time.monotonic() - ctx.t0, 3), "max_bits": ctx.max_bits,
                "max_mantissa_bits": ctx.max_mantissa, "limits": limits.as_dict()}
    try:
        m, plan, J = _check(cert, ctx)
        s = stats()
        s["orders"] = [o for _, _, o in plan]
        s["width_ulps"] = float((J.hi - J.lo) * (1 << OUT_FRAC))
        return Result("VALID", m, "strictly_separated", s)
    except _Invalid as e:
        return Result("INVALID", None, str(e), stats())
    except _Refused as e:
        return Result("REFUSED", None, str(e), stats())
    except MemoryError:
        return Result("REFUSED", None, "memory_limit", stats())
