"""Gate 2A: an independent host-float implementation of the same discrete program (K5),
written from the plan's operation order, plus the twin-trajectory orbit classifier (plan section 3).
Checker side: never imports numeric_core.
"""
from __future__ import annotations

H, HH = 1.0 / 64.0, 1.0 / 128.0


def step(x: float, y: float, px: float, py: float, defect=None) -> tuple:
    ax = (-x) - 2.0 * (x * y)
    ay = ((-y) - x * x) + y * y
    pxh, pyh = px + HH * ax, py + HH * ay
    x1, y1 = x + H * pxh, y + H * pyh
    ax1 = (-x1) - 2.0 * (x1 * y1)
    ay1 = ((-y1) - x1 * x1) + y1 * y1
    return x1, y1, pxh + HH * ax1, pyh + HH * ay1


def classify(px0: float, py0: float, n: int) -> dict:
    """Plan section 3: twin trajectories, px perturbed by 2^-30; max componentwise separation."""
    a = (0.0, 0.0, px0, py0)
    b = (0.0, 0.0, px0 + 2.0 ** -30, py0)
    sep = 0.0
    for _ in range(n):
        a, b = step(*a), step(*b)
        sep = max(sep, max(abs(u - v) for u, v in zip(a, b)))
    label = "chaotic" if sep >= 2.0 ** -5 else "regular" if sep < 2.0 ** -15 else "unclassified"
    return {"max_separation": sep, "label": label}
