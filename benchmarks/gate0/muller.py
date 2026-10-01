"""Gate 0 benchmark 2: Muller's recurrence.

x0 = 4, x1 = 4.25, x(n+1) = 108 - (815 - 1500 / x(n-1)) / x(n).
Exact: x(n) = (3^(n+1) + 5^(n+1)) / (3^n + 5^n), which tends to 5.
The recurrence also admits a solution tending to 100; any rounding error
excites it and finite precision is pulled to 100.
"""
from __future__ import annotations

from fractions import Fraction

import mpmath

from lab.claim import agree_digits

from .harness import Instr

NAME = "muller"
N = 30
OUT = f"x{N}"


def program(n: int = N) -> list:
    I = Instr
    p = [I("CONST", "x0", (4,)), I("CONST", "x1", ("17/4",)),
         I("CONST", "c108", (108,)), I("CONST", "c815", (815,)), I("CONST", "c1500", (1500,))]
    for k in range(1, n):
        p += [I("DIV", f"d{k}", ("c1500", f"x{k-1}")), I("SUB", f"e{k}", ("c815", f"d{k}")),
              I("DIV", f"g{k}", (f"e{k}", f"x{k}")), I("SUB", f"x{k+1}", ("c108", f"g{k}"))]
    return p


def closed_form(n: int = N) -> Fraction:
    return Fraction(3 ** (n + 1) + 5 ** (n + 1), 3 ** n + 5 ** n)


def exact_iteration(n: int = N) -> list:
    """Independent of the VM: the recurrence in Python rationals. Returns x0..xn."""
    xs = [Fraction(4), Fraction(17, 4)]
    while len(xs) <= n:
        xs.append(108 - (815 - 1500 / xs[-2]) / xs[-1])
    return xs


def mp_iteration(prec_bits: int, n: int = N):
    with mpmath.workprec(prec_bits):
        xs = [mpmath.mpf(4), mpmath.mpf(17) / 4]
        while len(xs) <= n:
            xs.append(108 - (815 - 1500 / xs[-2]) / xs[-1])
        return [+x for x in xs]


# Declared loss, derived: the general solution is
#   x_n = (a 3^(n+1) + b 5^(n+1) + g 100^(n+1)) / (a 3^n + b 5^n + g 100^n),
# the true data have g = 0, and a rounding error of relative size u gives g ~ u, whose
# effect on x_n grows like (100/5)^n = 20^n. At n = 30 that is 10^39.03. Measured:
# |error| / u = 10^38.08 (686 bits) and 10^37.45 (1352 bits). Declared: 40 digits.
DECLARED_LOSS_DIGITS = 40


def oracle_inputs():
    digits = 400
    hp = mp_iteration(int(digits * 3.33) + 20)[N]
    return ({"closed_form": closed_form(), "direct_rational": exact_iteration()[N]},
            (f"mpmath_{digits}_digits", hp, agree_digits(digits, DECLARED_LOSS_DIGITS)))
