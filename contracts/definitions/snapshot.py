from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from contracts.definitions.outcome import MilestoneHit


@dataclass(frozen=True)
class Snapshot:

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

    evaluations: int
    elapsed_seconds: float
    similarity: float
    best_similarity: float
    cost: float
    acceptance_rate: float
    extras: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class LeaderboardEntry:

    rank: int
    panel_index: int
    algorithm_id: str
    best_similarity: float
    evaluations: int
    rank_change: int
    finished: bool
    milestones: dict[int, MilestoneHit] = field(default_factory=dict)