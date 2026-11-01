"""Algorithm interface (contract 6.2). Owner: M2 - PLACEHOLDER with the exact contract names;
if M2 pushes their own version, keep theirs."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from .snapshot import Snapshot


class Algorithm(ABC):
    """A local search algorithm. Never edits a state, never imports Pygame, never reads files."""

    id: str = ""
    display_name: str = ""
    description: str = ""

    @abstractmethod
    def __init__(self, problem: Any, seed: int, params: dict | None = None) -> None:
        """Creates its own random generator from the seed."""

    @staticmethod
    @abstractmethod
    def param_specs() -> list:
        """Algorithm-group ParamSpecs. MUST include step_scale."""

    @staticmethod
    @abstractmethod
    def action_specs() -> list:
        """One-shot ActionSpecs (may be empty)."""

    @abstractmethod
    def advance(self, budget_evaluations: int) -> Snapshot:
        """Spend at least that many evaluations and return a Snapshot."""

    @abstractmethod
    def set_param(self, name: str, value: Any) -> None:
        """Live parameter change, effective on the next evaluation."""

    @abstractmethod
    def trigger(self, action_name: str) -> None:
        """Perform a one-shot action."""

    @abstractmethod
    def inject(self, batch: Any) -> None:
        """Apply the batch to every held state, re-evaluate, reset best to the new current."""

    @abstractmethod
    def current_snapshot(self) -> Snapshot:
        """Latest Snapshot without advancing."""
