"""The Session interface (contract 6.3). Owner: M2.

Decisions made here (flag in review):
- send() queues; queued commands apply at the start of the next tick.
- finish() is idempotent: calling it again returns the same RunRecord.
- leaderboard rank_change is the change since the previous tick.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from contracts.definitions.commands import Command
from contracts.definitions.events import Event
from contracts.definitions.params import ActionSpec, ParamSpec
from contracts.definitions.snapshot import HistoryPoint, LeaderboardEntry, Snapshot

STATUS_VALUES = ("running", "paused", "finished")
MAX_HISTORY_POINTS = 2000


@dataclass(frozen=True)
class PanelInfo:
    """Static and live facts about one panel."""

    algorithm_id: str
    params: dict[str, Any]
    param_specs: tuple[ParamSpec, ...]
    action_specs: tuple[ActionSpec, ...]
    speed: float
    throttled: bool


@runtime_checkable
class Session(Protocol):
    """The object M3's run screen talks to. RunRecord is defined by M4."""

    def tick(self, seconds: float) -> None:
        """Advance every unfinished panel according to its speed."""

    def send(self, command: Command) -> None:
        """Queue a command."""

    def snapshot(self, panel: int) -> Snapshot:
        """Return the latest Snapshot of a panel."""

    def history(self, panel: int, max_points: int) -> list[HistoryPoint]:
        """Return at most max_points history points, oldest first."""

    def leaderboard(self) -> list[LeaderboardEntry]:
        """Return entries sorted by rank."""

    def poll_events(self) -> list[Event]:
        """Return events since the last call."""

    def panel_info(self, panel: int) -> PanelInfo:
        """Return algorithm id, parameter values, specs, speed, throttle flag."""

    def render(self, panel: int, size: int) -> Any:
        """Return a Pillow image of the panel's current state."""

    def status(self) -> str:
        """Return running, paused or finished."""

    def finish(self) -> Any:
        """Stop the run and return the RunRecord."""
