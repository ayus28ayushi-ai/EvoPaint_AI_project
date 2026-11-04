"""The RunRecord returned by Session.finish (contract 5.14, in memory)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, fields, is_dataclass
from datetime import datetime
from typing import Any

from contracts.definitions import Event, HistoryPoint, Outcome

CONTRACT_VERSION = "1.0"


@dataclass
class Injection:
    """One injection, filled in as the panel recovers."""

    evaluation_index: int
    cost_before: float
    cost_after: float
    recovery_evaluations: int | None = None


@dataclass(frozen=True)
class PanelResult:
    """Outcome plus the final and best states of one panel."""

    outcome: Outcome
    final_state: Any
    best_state: Any


def to_plain(value: Any) -> Any:
    """Turn dataclasses, namespaces and tuples into dicts and lists that JSON accepts."""
    if is_dataclass(value) and not isinstance(value, type):
        return {f.name: to_plain(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, Mapping):
        return {k: to_plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [to_plain(v) for v in value]
    if hasattr(value, "__dict__"):
        return {k: to_plain(v) for k, v in vars(value).items() if not k.startswith("_")}
    return value


@dataclass
class RunRecord:
    """Everything M4 needs to save a run. config is plain data; images are Pillow images."""

    run_id: str
    created_at: str
    contract_version: str
    config: Any
    results: list[PanelResult]
    winners: dict[str, int | None]
    awards: dict[str, int]
    events: list[Event]
    history: dict[int, list[HistoryPoint]]
    images: dict[str, Any] = field(default_factory=dict)  # "target", "result_0", "result_1", ...
    shapes: dict[int, dict] = field(default_factory=dict)  # Problem.state_to_dict of each best state

    def to_dict(self) -> dict[str, Any]:
        """Return every saved field as JSON-ready plain data (images excluded)."""
        return {
            "run_id": self.run_id,
            "created_at": self.created_at,
            "contract_version": self.contract_version,
            "config": self.config,
            "winners": self.winners,
            "awards": self.awards,
            "outcomes": {i: to_plain(r.outcome) for i, r in enumerate(self.results)},
            "events": to_plain(self.events),
            "history": to_plain(self.history),
            "shapes": to_plain(self.shapes),
        }


def make_run_id(seed: int, now: datetime) -> str:
    """Name a run by date, time and seed, as the gallery folder expects."""
    return f"{now:%Y%m%d_%H%M%S}_{seed}"
