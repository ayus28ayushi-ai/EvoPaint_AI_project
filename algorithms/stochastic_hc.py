"""Algorithm 2: stochastic hill climbing."""

from __future__ import annotations

import random
from collections import deque
from collections.abc import Mapping
from typing import Any

from contracts.definitions import ActionSpec, Algorithm, ParamSpec, Snapshot

HIT_WINDOW = 50


class StochasticHillClimbing(Algorithm):
    """Proposes a batch of neighbors and moves to one improving neighbor, chosen at random."""

    id = "stochastic_hc"
    display_name = "Stochastic Hill Climbing"
    description = (
        "Tries a batch of neighbors each step and picks one of the improving ones at random. "
        "Never accepts a worse painting."
    )

    def __init__(
        self, problem: Any, seed: int, params: Mapping[str, Any] | None = None
    ) -> None:
        """Start from the problem's initial state."""
        self._problem = problem
        self._rng = random.Random(seed)
        self._params = {s.name: s.default for s in self.param_specs()}
        self._params.update(params or {})
        self._state = problem.initial_state()
        self._cost = problem.evaluate(self._state)
        self._evaluations = 0
        self._iteration = 0
        self._proposed = 0
        self._accepted = 0
        self._hits: deque[int] = deque(maxlen=HIT_WINDOW)

    @staticmethod
    def param_specs() -> list[ParamSpec]:
        """Publish step_scale and batch_size."""
        return [
            ParamSpec(
                name="step_scale",
                label="Step scale",
                kind="float",
                minimum=0.01,
                maximum=1.0,
                default=0.3,
                scale="log",
                help_text="How big each random change is.",
            ),
            ParamSpec(
                name="batch_size",
                label="Batch size",
                kind="int",
                minimum=2,
                maximum=20,
                default=5,
                step=1,
                help_text="Neighbors tried per step.",
            ),
        ]

    @staticmethod
    def action_specs() -> list[ActionSpec]:
        """This algorithm has no actions."""
        return []

    def advance(self, budget_evaluations: int) -> Snapshot:
        """Run whole batches until the budget is spent."""
        spent = 0
        while spent < budget_evaluations:
            spent += self._step()
        return self.current_snapshot()

    def _step(self) -> int:
        """Try one batch; move to a random improving proposal if there is one."""
        size = int(self._params["batch_size"])
        scale = float(self._params["step_scale"])
        batch = [self._problem.propose(self._state, self._rng, scale) for _ in range(size)]
        better = [p for p in batch if p.cost < self._cost]
        self._iteration += 1
        self._evaluations += size
        self._proposed += size
        self._hits.append(1 if better else 0)
        if better:
            chosen = self._rng.choice(better)
            self._state, self._cost = chosen.state, chosen.cost
            self._accepted += 1
        return size

    def set_param(self, name: str, value: Any) -> None:
        """Change a parameter, clamped to its range."""
        spec = next((s for s in self.param_specs() if s.name == name), None)
        if spec is None:
            raise KeyError(name)
        number = min(spec.maximum, max(spec.minimum, float(value)))
        self._params[name] = int(round(number)) if spec.kind == "int" else number

    def trigger(self, action_name: str) -> None:
        """No actions exist."""
        raise ValueError(f"unknown action: {action_name!r}")

    def inject(self, batch: Any) -> None:
        """Add the injected shapes, re-evaluate and restart from there."""
        self._state = self._problem.apply_injection(self._state, batch)
        self._cost = self._problem.evaluate(self._state)
        self._evaluations += 1

    def current_snapshot(self) -> Snapshot:
        """Return the latest Snapshot without advancing."""
        similarity = self._problem.similarity(self._cost)
        hit_rate = sum(self._hits) / len(self._hits) if self._hits else 0.0
        return Snapshot(
            algorithm_id=self.id,
            iteration=self._iteration,
            evaluations=self._evaluations,
            cost=self._cost,
            similarity=similarity,
            best_cost=self._cost,
            best_similarity=similarity,
            state=self._state,
            best_state=self._state,
            proposed_total=self._proposed,
            accepted_total=self._accepted,
            worse_accepted_total=0,
            extras={"batch_hit_rate": hit_rate},
        )
