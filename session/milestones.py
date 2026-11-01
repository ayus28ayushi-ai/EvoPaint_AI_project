"""Tracks when a panel first reaches 80, 90 and 95 percent."""

from __future__ import annotations

from contracts.definitions import MILESTONE_LEVELS, MilestoneHit


class MilestoneTracker:
    """Remembers the first time each level was reached."""

    def __init__(self) -> None:
        """Start with no hits."""
        self.hits: dict[int, MilestoneHit] = {}

    def update(self, best_similarity: float, evaluations: int, seconds: float) -> list[int]:
        """Record newly reached levels and return them."""
        new = [
            level
            for level in MILESTONE_LEVELS
            if level not in self.hits and best_similarity >= level
        ]
        for level in new:
            self.hits[level] = MilestoneHit(evaluations, seconds)
        return new
