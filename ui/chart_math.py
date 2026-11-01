"""Pure maths for the stock-market chart (no Pygame, so it is easy to test)."""
from __future__ import annotations

import math

from ui.compat import get


def thin(points: list, max_points: int) -> list:
    """Keep at most `max_points` points, evenly spaced, always keeping the last one."""
    if len(points) <= max_points or max_points < 2:
        return list(points)
    step = (len(points) - 1) / (max_points - 1)
    return [points[round(i * step)] for i in range(max_points)]


def value_of(point, mode: str) -> float:
    """What the chart plots: similarity (rises like a stock) or cost (error)."""
    return float(get(point, "similarity" if mode == "similarity" else "cost", 0.0))


def y_range(values: list, mode: str) -> tuple:
    """Auto-scale the vertical axis with a little padding."""
    if not values:
        return (0.0, 100.0) if mode == "similarity" else (0.0, 1.0)
    lo, hi = min(values), max(values)
    if mode == "similarity":
        lo, hi = max(0.0, lo - 3), min(100.0, hi + 3)
        if hi - lo < 8:                                   # never zoom in absurdly far
            mid = (lo + hi) / 2
            lo, hi = max(0.0, mid - 4), min(100.0, mid + 4)
        return lo, hi
    pad = (hi - lo) * 0.05 or 1.0
    return max(0.0, lo - pad), hi + pad


def use_log(values: list, mode: str) -> bool:
    """Error spans orders of magnitude, so switch to a log axis when it is that wide."""
    positive = [v for v in values if v > 0]
    return mode == "error" and bool(positive) and max(positive) / min(positive) > 30


def to_unit(value: float, lo: float, hi: float, log: bool = False) -> float:
    """Map a value to 0..1 inside [lo, hi] (optionally on a log scale)."""
    if log:
        lo, hi, value = math.log10(max(lo, 1e-9)), math.log10(max(hi, 1e-9)), math.log10(max(value, 1e-9))
    if hi == lo:
        return 0.5
    return min(max((value - lo) / (hi - lo), 0.0), 1.0)


def to_pixel(x, y, rect, x_range, y_range_, log=False) -> tuple:
    """Data coordinates -> screen pixel inside rect (y grows upward in the data)."""
    rx, ry, rw, rh = rect
    px = rx + to_unit(x, x_range[0], x_range[1]) * rw
    py = ry + rh - to_unit(y, y_range_[0], y_range_[1], log) * rh
    return int(px), int(py)


def ticker_change(points: list, mode: str, window_seconds: float = 5.0) -> tuple:
    """(latest value, change over the last `window_seconds`) for the little ticker."""
    if not points:
        return 0.0, 0.0
    last = points[-1]
    cutoff = float(get(last, "elapsed_seconds", 0.0)) - window_seconds
    earlier = points[0]
    for p in reversed(points):
        if float(get(p, "elapsed_seconds", 0.0)) <= cutoff:
            earlier = p
            break
    return value_of(last, mode), value_of(last, mode) - value_of(earlier, mode)


def nice_ticks(lo: float, hi: float, count: int = 4) -> list:
    """A few round-number gridline values between lo and hi."""
    if hi <= lo:
        return [lo]
    raw = (hi - lo) / count
    magnitude = 10 ** math.floor(math.log10(raw))
    step = min((m * magnitude for m in (1, 2, 5, 10) if m * magnitude >= raw), default=raw)
    first = math.ceil(lo / step) * step
    ticks, v = [], first
    while v <= hi + 1e-9:
        ticks.append(round(v, 10))
        v += step
    return ticks


def format_count(n: float) -> str:
    """1500 -> '1.5k', 2000000 -> '2.0M'."""
    n = float(n)
    if n >= 1e6:
        return f"{n / 1e6:.1f}M"
    if n >= 1e3:
        return f"{n / 1e3:.1f}k"
    return f"{n:.0f}"
