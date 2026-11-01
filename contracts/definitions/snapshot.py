"""Snapshot (contract 5.7). Owner: M2 - PLACEHOLDER with the exact contract names;
if M2 pushes their own version, keep theirs."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Snapshot:
    """State of one algorithm at one moment."""

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
    extras: dict = field(default_factory=dict)
    panel_index: int = 0  # filled by the Session
    elapsed_seconds: float = 0.0  # filled by the Session
