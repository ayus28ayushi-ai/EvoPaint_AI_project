from __future__ import annotations

from contracts.definitions import MILESTONE_LEVELS, MilestoneHit


class MilestoneTracker:

    def __init__(self) -> None:
        self.hits: dict[int, MilestoneHit] = {}

    def update(self, best_similarity: float, evaluations: int, seconds: float) -> list[int]:
        new = [
            level
            for level in MILESTONE_LEVELS
            if level not in self.hits and best_similarity >= level
        ]
        for level in new:
            self.hits[level] = MilestoneHit(evaluations, seconds)
        return new
