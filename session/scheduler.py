
from __future__ import annotations


class Scheduler:

    def __init__(self, panels: int) -> None:
        self._carry = [0.0] * panels

    def owed(self, panel: int, speed: float, seconds: float) -> int:
        self._carry[panel] += speed * seconds
        return max(0, int(self._carry[panel]))

    def settle(self, panel: int, spent: int) -> bool:
        left = self._carry[panel] - spent
        throttled = left >= 1.0
        self._carry[panel] = 0.0 if throttled else left
        return throttled
