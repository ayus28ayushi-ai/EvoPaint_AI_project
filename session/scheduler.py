"""Turns speed (evaluations per second) into whole evaluations per tick."""

from __future__ import annotations


class Scheduler:
    """Carries fractions and overshoot between ticks for each panel."""

    def __init__(self, panels: int) -> None:
        """Create one carry per panel."""
        self._carry = [0.0] * panels

    def owed(self, panel: int, speed: float, seconds: float) -> int:
        """Return the whole evaluations the panel should run this tick."""
        self._carry[panel] += speed * seconds
        return max(0, int(self._carry[panel]))

    def settle(self, panel: int, spent: int) -> bool:
        """Charge spent evaluations; drop any backlog and return True if throttled."""
        left = self._carry[panel] - spent
        throttled = left >= 1.0
        self._carry[panel] = 0.0 if throttled else left
        return throttled
