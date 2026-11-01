"""Outcome, winners and awards (contract 5.12 and 5.13). Owner: M2."""

from __future__ import annotations

from dataclasses import dataclass

MILESTONE_LEVELS = (80, 90, 95)

WINNER_CATEGORIES = (
    "fastest_to_80",
    "fastest_to_90",
    "fastest_to_95",
    "best_final",
    "best_auc",
    "most_efficient",
    "fastest_recovery",
)

AWARD_IDS = (
    "risk_taker",
    "sprinter",
    "marathoner",
    "comeback_kid",
    "efficient_artist",
    "solo_artist",
)

# Winners: category -> panel index, or None if nobody qualified.
# Awards: award id -> panel index (absent if nobody earned it).
Winners = dict[str, "int | None"]
Awards = dict[str, int]


@dataclass(frozen=True)
class MilestoneHit:
    """When a similarity level was first reached."""

    evaluations: int
    seconds: float


@dataclass(frozen=True)
class InjectionRecord:
    """One injection and how long the panel took to recover from it."""

    evaluation_index: int
    cost_before: float
    cost_after: float
    recovery_evaluations: int | None = None  # None if never recovered


@dataclass(frozen=True)
class Outcome:
    """Per-panel result, created by the Session at the end of a run."""

    final_similarity: float
    total_evaluations: int
    total_seconds: float
    time_to_80: MilestoneHit | None
    time_to_90: MilestoneHit | None
    time_to_95: MilestoneHit | None
    auc_similarity: float
    efficiency: float  # similarity points gained per second
    acceptance_rate: float
    worse_accepted_total: int
    shape_count: int
    injections: tuple[InjectionRecord, ...] = ()
