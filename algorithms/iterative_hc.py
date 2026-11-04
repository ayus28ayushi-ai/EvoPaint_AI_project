from __future__ import annotations
import random
from typing import Any
from types import SimpleNamespace


class IterativeHillClimbing:
    id = "iterative_hc"
    display_name = "Iterative Hill Climbing"
    description = "Hill climbing with random restarts"

    @staticmethod
    def param_specs():
        return [
            {"name": "step_scale", "label": "Step size", "kind": "float",
             "minimum": 0.01, "maximum": 1.0, "default": 0.3, "step": 0.01,
             "scale": "log", "group": "algorithm", "help_text": "Mutation size"},
            {"name": "restart_after", "label": "Restart after", "kind": "int",
             "minimum": 50, "maximum": 5000, "default": 500, "step": 50,
             "scale": "linear", "group": "algorithm", "help_text": "Evals without improvement before restart"},
        ]

    @staticmethod
    def action_specs():
        return [{"name": "restart", "label": "Restart now", "help_text": "Force restart"}]

    def __init__(self, problem, seed: int, params: dict):
        self.problem = problem
        self.rng = random.Random(seed)
        self.params = dict(params)
        self.current = problem.initial_state()
        self.current_cost = problem.evaluate(self.current)
        self.best = self.current
        self.best_cost = self.current_cost
        self.evaluations = self.iterations = self.proposed = self.accepted = self.worse_accepted = self.no_improve = 0

    def advance(self, budget_evaluations: int):
        start = self.evaluations
        step = self.params.get("step_scale", 0.3)
        limit = self.params.get("restart_after", 500)

        while self.evaluations - start < budget_evaluations:
            proposal = self.problem.propose(self.current, self.rng, step)
            self.evaluations += 1
            self.proposed += 1
            if proposal.cost < self.current_cost:
                self.current = proposal.state
                self.current_cost = proposal.cost
                self.accepted += 1
                self.no_improve = 0
                if proposal.cost < self.best_cost:
                    self.best = proposal.state
                    self.best_cost = proposal.cost
            else:
                self.no_improve += 1
            if self.no_improve >= limit:
                self._restart()
            self.iterations += 1

        return self.current_snapshot()

    def set_param(self, name, value):
        self.params[name] = value

    def trigger(self, action_name):
        if action_name == "restart":
            self._restart()

    def inject(self, batch):
        self.current = self.problem.apply_injection(self.current, batch)
        self.current_cost = self.problem.evaluate(self.current)
        self.evaluations += 1
        self.best = self.current
        self.best_cost = self.current_cost
        self.no_improve = 0

    def current_snapshot(self):
        return SimpleNamespace(
            algorithm_id=self.id,
            iteration=self.iterations,
            evaluations=self.evaluations,
            cost=self.current_cost,
            similarity=self.problem.similarity(self.current_cost),
            best_cost=self.best_cost,
            best_similarity=self.problem.similarity(self.best_cost),
            state=self.current,
            best_state=self.best,
            proposed_total=self.proposed,
            accepted_total=self.accepted,
            worse_accepted_total=self.worse_accepted,
            extras={"no_improve": self.no_improve},
            elapsed_seconds=0.0,
            panel_index=0,
        )

    def _restart(self):
        self.current = self.problem.initial_state()
        self.current_cost = self.problem.evaluate(self.current)
        self.evaluations += 1
        self.no_improve = 0