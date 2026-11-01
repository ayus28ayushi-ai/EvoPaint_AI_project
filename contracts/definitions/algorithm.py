"""The Algorithm interface (contract 6.2). Owners: M1 to M4, one each."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, ClassVar

from contracts.definitions.params import ActionSpec, ParamSpec
from contracts.definitions.snapshot import Snapshot


@dataclass(frozen=True)
class AlgorithmInfo:
    """What session.list_algorithms() returns for each algorithm."""

    id: str
    display_name: str
    description: str
    param_specs: tuple[ParamSpec, ...]
    action_specs: tuple[ActionSpec, ...]


class Algorithm(ABC):
    """Base class every algorithm follows. Only the Session uses it.

    The constructor takes (problem, seed, params), creates its own
    random.Random from the seed, and never touches the global random module.
    Algorithms never edit a state, import Pygame, do file I/O or sleep.
    """

    id: ClassVar[str]
    display_name: ClassVar[str]
    description: ClassVar[str]

    @abstractmethod
    def __init__(
        self, problem: Any, seed: int, params: Mapping[str, Any] | None = None
    ) -> None:
        """Create the algorithm; params overrides the published defaults."""

    @staticmethod
    @abstractmethod
    def param_specs() -> list[ParamSpec]:
        """Return the algorithm-group parameters (must include step_scale)."""

    @staticmethod
    @abstractmethod
    def action_specs() -> list[ActionSpec]:
        """Return the one-shot actions (may be empty)."""

    @abstractmethod
    def advance(self, budget_evaluations: int) -> Snapshot:
        """Run until at least budget_evaluations were spent; return a Snapshot.

        Overshoot is at most one batch or one beam sweep.
        """

    @abstractmethod
    def set_param(self, name: str, value: Any) -> None:
        """Change a parameter; takes effect on the next evaluation."""

    @abstractmethod
    def trigger(self, action_name: str) -> None:
        """Perform a one-shot action."""

    @abstractmethod
    def inject(self, batch: Any) -> None:
        """Apply the batch to every state held, re-evaluate, reset the best."""

    @abstractmethod
    def current_snapshot(self) -> Snapshot:
        """Return the latest Snapshot without advancing."""
