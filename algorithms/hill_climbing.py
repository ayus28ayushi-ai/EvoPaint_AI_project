"""Hill climbing (contract id hill_climbing, owner M1): keep a neighbour only if its cost strictly drops."""
from __future__ import annotations

import logging
import random
from typing import Any

from contracts.definitions import Algorithm, ParamSpec, Snapshot

log = logging.getLogger(__name__)
STEP_MIN, STEP_MAX = 0.01, 1.0


class HillClimbing(Algorithm):
    """Greedy local search. One iteration is one evaluation, so iterations == evaluations."""

    id = "hill_climbing"
    display_name = "Hill Climbing"
    description = "Keeps a random change only if the painting gets closer to the target. Fast, but can get stuck."

    def __init__(self, problem: Any, seed: int, params: dict | None = None) -> None:
        self._problem = problem
        self._rng = random.Random(seed)
        self._params = {"step_scale": 0.3}
        for k, v in (params or {}).items():
            self.set_param(k, v)
        self._state = problem.initial_state()
        self._cost = problem.evaluate(self._state)  # setup evaluation, not counted in the budget
        self._best_state, self._best_cost = self._state, self._cost
        self._iteration = self._evaluations = self._proposed = self._accepted = 0

    @staticmethod
    def param_specs() -> list:
        """step_scale is the only algorithm parameter."""
        return [ParamSpec("step_scale", "Step size", "float", STEP_MIN, STEP_MAX, 0.3, 0.01, "log", "algorithm",
                          "How big each random change is. Small values refine details, large values sketch.")]

    @staticmethod
    def action_specs() -> list:
        """Hill climbing has no one-shot actions."""
        return []

    def advance(self, budget_evaluations: int) -> Snapshot:
        """Spend exactly `budget_evaluations` evaluations (one proposal each) and return a Snapshot."""
        prob = self._problem
        for _ in range(max(0, int(budget_evaluations))):
            prop = prob.propose(self._state, self._rng, self._params["step_scale"])
            self._proposed += 1
            self._evaluations += 1
            self._iteration += 1
            if prop.cost < self._cost:
                self._state, self._cost = prop.state, prop.cost
                self._accepted += 1
                if self._cost < self._best_cost:
                    self._best_state, self._best_cost = self._state, self._cost
        return self.current_snapshot()

    def set_param(self, name: str, value: Any) -> None:
        """Live change of step_scale (clamped to its range). Unknown names are ignored with a warning."""
        if name == "step_scale":
            self._params["step_scale"] = float(min(STEP_MAX, max(STEP_MIN, value)))
        else:
            log.warning("hill_climbing: unknown parameter %r ignored", name)

    def trigger(self, action_name: str) -> None:
        """No actions exist."""
        raise ValueError(f"hill_climbing has no action {action_name!r}")

    def inject(self, batch: Any) -> None:
        """Apply the batch, re-evaluate, and reset the best to the new current state."""
        self._state = self._problem.apply_injection(self._state, batch)
        self._cost = self._problem.evaluate(self._state)
        self._best_state, self._best_cost = self._state, self._cost

    def current_snapshot(self) -> Snapshot:
        """Latest Snapshot without advancing."""
        p = self._problem
        return Snapshot(
            algorithm_id=self.id, iteration=self._iteration, evaluations=self._evaluations,
            cost=self._cost, similarity=p.similarity(self._cost),
            best_cost=self._best_cost, best_similarity=p.similarity(self._best_cost),
            state=self._state, best_state=self._best_state,
            proposed_total=self._proposed, accepted_total=self._accepted, worse_accepted_total=0,
            extras={"step_scale": self._params["step_scale"], "shapes": float(len(self._state.shapes))},
        )
