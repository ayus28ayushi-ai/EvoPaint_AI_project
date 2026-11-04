"""Events read through Session.poll_events (contract 5.10). Owner: M2."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

EVENT_PAYLOAD_KEYS: dict[str, tuple[str, ...]] = {
    "milestone_reached": ("level",),
    "leader_changed": ("old_panel", "new_panel"),
    "shapes_injected": ("count", "cost_before", "cost_after"),
    "worse_move_burst": ("count",),
    "param_changed": ("name", "old_value", "new_value"),
    "panel_finished": ("reason",),  # budget or user
    "panel_throttled": ("requested_speed", "achieved_speed"),
    "run_finished": ("reason",),
}

EVENT_TYPES = tuple(EVENT_PAYLOAD_KEYS)


@dataclass(frozen=True)
class Event:
    """Common fields plus a type-specific payload. panel is None if run-wide."""

    type: str
    panel: int | None
    evaluations: int
    elapsed_seconds: float
    payload: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Reject unknown types and payloads missing required keys."""
        if self.type not in EVENT_TYPES:
            raise ValueError(f"unknown event type: {self.type!r}")
        missing = [k for k in EVENT_PAYLOAD_KEYS[self.type] if k not in self.payload]
        if missing:
            raise ValueError(f"{self.type} is missing payload keys: {missing}")
