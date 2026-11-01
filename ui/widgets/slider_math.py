"""Pure maths for sliders: value <-> position (0..1), including log sliders (no Pygame)."""
from __future__ import annotations

import math


def _is_rate_like(lo: float, hi: float) -> bool:
    """Values squeezed just below 1 (like cooling_rate 0.999..0.99999). On a plain log axis
    they would look linear, so we use log(1 - value) instead, which spreads them out."""
    return 0.5 < lo < hi < 1.0


def to_unit(value: float, lo: float, hi: float, scale: str = "linear") -> float:
    """Slider position (0..1) for a value."""
    value = min(max(value, lo), hi)
    if hi == lo:
        return 0.0
    if scale == "log" and _is_rate_like(lo, hi):
        a, b, v = math.log(1 - hi), math.log(1 - lo), math.log(1 - value)
        return (v - a) / (b - a)
    if scale == "log" and lo > 0:
        return (math.log(value) - math.log(lo)) / (math.log(hi) - math.log(lo))
    return (value - lo) / (hi - lo)


def from_unit(t: float, lo: float, hi: float, scale: str = "linear",
              step: float = 0.0, is_int: bool = False) -> float:
    """Value for a slider position (0..1), snapped to the step or to an integer."""
    t = min(max(t, 0.0), 1.0)
    if scale == "log" and _is_rate_like(lo, hi):
        a, b = math.log(1 - hi), math.log(1 - lo)
        value = 1 - math.exp(a + t * (b - a))
    elif scale == "log" and lo > 0:
        value = math.exp(math.log(lo) + t * (math.log(hi) - math.log(lo)))
    else:
        value = lo + t * (hi - lo)
        if step > 0:                                    # snap linear sliders to their step
            value = lo + round((value - lo) / step) * step
    if is_int:
        value = round(value)
    else:
        value = round(value, 10)                        # remove float noise such as 0.30000000000000004
    return min(max(value, lo), hi)


def format_value(value: float, is_int: bool = False) -> str:
    """Readable value text for the label next to a slider."""
    if is_int:
        return str(int(round(value)))
    if 0.5 < value < 1.0:
        return f"{value:.5f}"
    if abs(value) >= 100:
        return f"{value:.0f}"
    return f"{value:.3g}"
