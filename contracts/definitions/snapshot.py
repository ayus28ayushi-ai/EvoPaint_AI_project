"""Snapshot, HistoryPoint and LeaderboardEntry (contract 5.7, 5.8, 5.11)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from contracts.definitions.outcome import MilestoneHit


@dataclass(frozen=True)
class Snapshot:
    """What an algorithm reports after advancing.

    The Session fills panel_index and elapsed_seconds; algorithms leave the
    defaults. best_* is the best since the start or since the last injection.
    """

    algorithm_id: str
    iteration: int
    evaluations: int
    cost: float
    similarity: float
    best_cost: float
    best_similarity: float
    state: Any
    best_state: Any
    proposed_total: int = 0
    accepted_total: int = 0
    worse_accepted_total: int = 0
    extras: dict[str, float] = field(default_factory=dict)
    panel_index: int | None = None
    elapsed_seconds: float = 0.0


@dataclass(frozen=True)
class HistoryPoint:
    """One point on a panel's chart. acceptance_rate is 0 to 1."""

    evaluations: int
    elapsed_seconds: float
    similarity: float
    best_similarity: float
    cost: float
    acceptance_rate: float
    extras: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class LeaderboardEntry:
    """One row of the leaderboard. Positive rank_change means moved up."""

    rank: int
    panel_index: int
    algorithm_id: str
    best_similarity: float
    evaluations: int
    rank_change: int
    finished: bool
    milestones: dict[int, MilestoneHit] = field(default_factory=dict)
