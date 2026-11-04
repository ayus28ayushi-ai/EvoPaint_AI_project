"""Cost (mean squared error over every pixel and channel) and similarity (contract Section 2)."""
from __future__ import annotations

import math

import numpy as np


def sse(a: np.ndarray, b: np.ndarray) -> int:
    """Exact integer sum of squared differences between two uint8/int32 arrays of equal shape."""
    d = a.astype(np.int32) - b.astype(np.int32)
    return int((d * d).sum(dtype=np.int64))


def cost_from_sse(total: int, pixels_channels: int) -> float:
    """Mean squared error from an integer sum."""
    return total / pixels_channels


def similarity_from_cost(cost: float) -> float:
    """100 * (1 - sqrt(cost) / 255); 100 is a perfect copy."""
    return max(0.0, 100.0 * (1.0 - math.sqrt(max(cost, 0.0)) / 255.0))
