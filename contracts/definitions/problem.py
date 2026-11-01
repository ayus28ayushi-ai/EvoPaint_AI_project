"""Problem-side data definitions and the Problem interface (contract v1.0, Sections 5.1-5.3, 5.6, 6.1)."""
from __future__ import annotations

import random
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

WORKING_SIZE = 96
SHAPE_KINDS = ("circle", "ellipse", "triangle", "rectangle", "rotated_rectangle", "pentagon", "line")
MUTATION_KINDS = ("add", "move", "resize", "recolor", "alpha", "reorder", "remove")


@dataclass(frozen=True)
class Shape:
    """One shape (5.1). Coordinates 0..1 from top left, size is a fraction of image width."""

    shape_id: int
    kind: str
    x: float
    y: float
    size: float
    aspect: float = 1.0
    rotation: float = 0.0
    points: tuple = ()  # tuple of (x, y) tuples: triangle corners or line end points
    red: int = 0
    green: int = 0
    blue: int = 0
    alpha: float = 1.0
    origin: str = "evolved"  # evolved or injected


@dataclass(frozen=True)
class State:
    """A painting (5.2): background colour plus ordered shapes (first drawn first).

    next_shape_id is an additive field so shape ids are never reused after a removal.
    """

    background: tuple
    shapes: tuple = ()
    next_shape_id: int = 0

    def __post_init__(self) -> None:
        need = max((s.shape_id for s in self.shapes), default=-1) + 1
        if self.next_shape_id < need:
            object.__setattr__(self, "next_shape_id", need)


@dataclass(frozen=True)
class ShapeConfig:
    """Which shapes may be used (5.3)."""

    mode: str = "random"  # random or chosen
    allowed_types: tuple = SHAPE_KINDS
    shape_limit: int = 300
    alpha_min: float = 0.2
    alpha_max: float = 1.0


@dataclass(frozen=True)
class Proposal:
    """One neighbour (5.6): the new state, its cost and the kind of change."""

    state: State
    cost: float
    kind: str


@dataclass(frozen=True)
class InjectionBatch:
    """Deterministic batch of intruder shapes (6.1). Shape ids are placeholders."""

    seed: int
    shapes: tuple


class Problem(ABC):
    """The engine's side of the contract (6.1)."""

    @abstractmethod
    def initial_state(self) -> State:
        """Background is the average colour of the processed target, no shapes."""

    @abstractmethod
    def evaluate(self, state: State) -> float:
        """Full cost (mean squared error) of a state."""

    @abstractmethod
    def propose(self, state: State, rng: random.Random, step_scale: float) -> Proposal:
        """One neighbour of state. Never edits state. Counts as one evaluation."""

    @abstractmethod
    def similarity(self, cost: float) -> float:
        """100 * (1 - sqrt(cost) / 255)."""

    @abstractmethod
    def render(self, state: State, size: int) -> Any:
        """Pillow image of the state at the requested size."""

    @abstractmethod
    def target_image(self, size: int) -> Any:
        """Pillow image of the processed target."""

    @abstractmethod
    def make_injection(self, seed: int, count: int) -> InjectionBatch:
        """Deterministic intruder shapes (random positions and colours)."""

    @abstractmethod
    def apply_injection(self, state: State, batch: InjectionBatch) -> State:
        """Adds the batch on top. The shape limit does not apply to the injection itself."""

    @abstractmethod
    def state_to_dict(self, state: State) -> dict:
        """Plain dict for saving."""

    @abstractmethod
    def state_from_dict(self, data: dict) -> State:
        """Inverse of state_to_dict."""

    @abstractmethod
    def param_specs(self) -> list:
        """The painting group of ParamSpecs (Section 7)."""

    @abstractmethod
    def set_param(self, name: str, value: Any) -> None:
        """Live change of a painting parameter."""

    @abstractmethod
    def shape_count(self, state: State) -> int:
        """Number of shapes in the state."""
