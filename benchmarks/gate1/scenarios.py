"""Gate 1 scenarios S1-S6, exactly as sealed in docs/GATE1_PLAN.md."""
from fractions import Fraction as Q

from lab.gate1_state import State, add, dot, sub, vec


def _s(m1, m2, r1, d, v1, v2) -> State:
    r1 = vec(*r1)
    return State(Q(m1), Q(m2), r1, add(r1, vec(*d)), vec(*v1), vec(*v2))


SCENARIOS = {
    "S1": _s(3, 5, (Q(7, 3), Q(-5, 2)), (3, 4), (Q(5, 2), Q(1, 3)), (-1, Q(3, 4))),
    "S2": _s(1, 1, (0, 0), (2, 0), (1, 0), (-1, 0)),
    "S3": _s(2, 2, (-4, Q(9, 2)), (5, -12), (3, -2), (Q(1, 2), Q(7, 5))),
    "S4": _s(1, 1000, (11, -7), (-8, 15), (-2, 5), (Q(1, 10), Q(-1, 20))),
    "S5": _s(2, 7, (0, 0), (1, 1), (3, 1), (0, 0)),
    "S6": _s(Q(7, 2), Q(4, 3), (10**6 + Q(1, 7), Q(-10**6, 3)), (Q(-12, 5), 1), (Q(-1, 3), 2), (Q(4, 5), Q(-3, 2))),
}

for _name, _st in SCENARIOS.items():
    assert dot(sub(_st.v1, _st.v2), sub(_st.r2, _st.r1)) > 0, f"{_name}: discs are not approaching"
