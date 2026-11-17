from __future__ import annotations

import math

import numpy as np


def sse(a: np.ndarray, b: np.ndarray) -> int:
    d = a.astype(np.int32) - b.astype(np.int32)
    return int((d * d).sum(dtype=np.int64))


def cost_from_sse(total: int, pixels_channels: int) -> float:

    return total / pixels_channels


def similarity_from_cost(cost: float) -> float:
    return max(0.0, 100.0 * (1.0 - math.sqrt(max(cost, 0.0)) / 255.0))
