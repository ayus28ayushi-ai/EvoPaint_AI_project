"""Fake Algorithm that plays a scripted similarity curve (contract 11). Owner: M2.

No images and no real search: similarity climbs along a fixed curve, so the
Session, UI and media code can be built before any real algorithm exists.
"""

from __future__ import annotations

import math
import random
from collections.abc import Mapping
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

from contracts.definitions.algorithm import Algorithm
from contracts.definitions.params import ActionSpec, ParamSpec
from contracts.definitions.snapshot import Snapshot

BATCH = 25  # evaluations per iteration
REFERENCE_STEP = 0.3  # step_scale at which progress equals evaluations
START_SIMILARITY = 60.0
END_SIMILARITY = 97.0
TAU = 5000.0  # progress units for the curve to drop by a factor of e


def cost_from_similarity(similarity: float) -> float:
    """Invert the contract's similarity formula."""
    return (255.0 * (1.0 - similarity / 100.0)) ** 2


@dataclass(frozen=True)
class FakeState:
    """A fake painting: plain data only, so it is picklable."""

    progress: float
    penalty: float
    cost: float


class ScriptedProblem:
    """The few Problem methods the fakes need (similarity, injection, shapes)."""

    def similarity(self, cost: float) -> float:
        """Apply the contract formula: 100 * (1 - sqrt(cost) / 255)."""
        return 100.0 * (1.0 - math.sqrt(max(cost, 0.0)) / 255.0)

    def make_injection(self, seed: int, count: int) -> Any:
        """Return a stand-in injection batch."""
        return SimpleNamespace(seed=seed, count=count, origin="injected")

    def state_to_dict(self, state: FakeState) -> dict:
        """Return the state's fields as a plain dict."""
        return {"progress": state.progress, "penalty": state.penalty, "cost": state.cost}

    def render(self, state: FakeState, size: int) -> Any:
        """Return a gray square whose brightness follows the state's cost."""
        from PIL import Image

        level = int(2.55 * self.similarity(state.cost))
        return Image.new("RGB", (size, size), (level, level, level))

    def target_image(self, size: int) -> Any:
        """Return a white square standing in for the target."""
        from PIL import Image

        return Image.new("RGB", (size, size), (255, 255, 255))

    def param_specs(self) -> list[ParamSpec]:
        """Publish no painting parameters."""
        return []

    def set_param(self, name: str, value: Any) -> None:
        """Ignore painting parameters."""

    def shape_count(self, state: FakeState) -> int:
        """Pretend one shape per hundred units of progress."""
        return int(state.progress // 100)


class FakeAlgorithm(Algorithm):
    """Plays a noisy exponential curve from 60 percent toward 97 percent."""

    id = "fake"
    display_name = "Fake (scripted)"
    description = "Plays a scripted similarity curve. For stubs and tests only."

    def __init__(
        self, problem: Any, seed: int, params: Mapping[str, Any] | None = None
    ) -> None:
        """Create the fake with its own seeded generator."""
        self._problem = problem
        self._rng = random.Random(seed)
        self._params: dict[str, Any] = {s.name: s.default for s in self.param_specs()}
        self._params.update(params or {})
        self._progress = 0.0
        self._penalty = 0.0
        self._evaluations = 0
        self._iteration = 0
        self._proposed = 0
        self._accepted = 0
        self._worse = 0
        self._state = self._make_state(0.0)
        self._best = self._state

    @staticmethod
    def param_specs() -> list[ParamSpec]:
        """Publish step_scale only."""
        return [
            ParamSpec(
                name="step_scale",
                label="Step scale",
                kind="float",
                default=0.3,
                minimum=0.01,
                maximum=1.0,
                scale="log",
                group="algorithm",
                help_text="Larger values make the scripted curve climb faster.",
            )
        ]

    @staticmethod
    def action_specs() -> list[ActionSpec]:
        """Publish one action so action handling can be tested."""
        return [ActionSpec("poke", "Poke", "Adds a temporary cost penalty.")]

    def _curve(self) -> float:
        """Return the noise-free cost at the current progress."""
        start = cost_from_similarity(START_SIMILARITY)
        end = cost_from_similarity(END_SIMILARITY)
        return end + (start - end) * math.exp(-self._progress / TAU)

    def _make_state(self, noise: float) -> FakeState:
        """Build a state at the current progress with the given noise."""
        cost = self._curve() * (1.0 + self._penalty) * (1.0 + noise)
        return FakeState(self._progress, self._penalty, cost)

    def advance(self, budget_evaluations: int) -> Snapshot:
        """Spend at least budget_evaluations, one batch of BATCH at a time."""
        spent = 0
        while spent < budget_evaluations:
            self._iteration += 1
            self._progress += BATCH * float(self._params["step_scale"]) / REFERENCE_STEP
            self._penalty *= 0.9
            candidate = self._make_state(self._rng.uniform(0.0, 0.02))
            self._proposed += BATCH
            self._accepted += BATCH // 5
            if candidate.cost > self._state.cost:
                self._worse += 1
            self._state = candidate
            if candidate.cost < self._best.cost:
                self._best = candidate
            self._evaluations += BATCH
            spent += BATCH
        return self.current_snapshot()

    def set_param(self, name: str, value: Any) -> None:
        """Change a parameter; step_scale is clamped to its range."""
        if name not in self._params:
            raise KeyError(name)
        self._params[name] = min(1.0, max(0.01, float(value))) if name == "step_scale" else value

    def trigger(self, action_name: str) -> None:
        """Perform the poke action."""
        if action_name != "poke":
            raise ValueError(f"unknown action: {action_name!r}")
        self._penalty += 0.3

    def inject(self, batch: Any) -> None:
        """Pretend the injected shapes hurt, then reset the best."""
        self._penalty += 0.5
        self._evaluations += 1
        self._state = self._make_state(0.0)
        self._best = self._state

    def current_snapshot(self) -> Snapshot:
        """Return the latest Snapshot without advancing."""
        sim = self._problem.similarity
        return Snapshot(
            algorithm_id=self.id,
            iteration=self._iteration,
            evaluations=self._evaluations,
            cost=self._state.cost,
            similarity=sim(self._state.cost),
            best_cost=self._best.cost,
            best_similarity=sim(self._best.cost),
            state=self._state,
            best_state=self._best,
            proposed_total=self._proposed,
            accepted_total=self._accepted,
            worse_accepted_total=self._worse,
            extras={"penalty": self._penalty},
        )
