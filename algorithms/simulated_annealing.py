from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Any

# --- Contract definitions -------------------------------------------------------------
# After kickoff the real classes live in contracts.definitions. Until then (or when this
# file is run alone) we fall back to tiny local copies with the SAME field names
# (Contract 5.5 and 5.7). Once the contract package exists, this block can be deleted.
try:  # pragma: no cover - depends on the repository state
    from contracts.definitions import ActionSpec, Algorithm, ParamSpec, Snapshot
except ImportError:
    @dataclass
    class ParamSpec:
        name: str
        label: str
        kind: str = "float"
        minimum: float = 0.0
        maximum: float = 1.0
        default: float = 0.0
        step: float = 0.0
        scale: str = "linear"
        group: str = "algorithm"
        help_text: str = ""

    @dataclass
    class ActionSpec:
        name: str
        label: str
        help_text: str = ""

    @dataclass
    class Snapshot:
        algorithm_id: str
        iteration: int
        evaluations: int
        cost: float
        similarity: float
        best_cost: float
        best_similarity: float
        state: Any
        best_state: Any
        proposed_total: int
        accepted_total: int
        worse_accepted_total: int
        extras: dict = field(default_factory=dict)
        panel_index: int = 0          # filled in by the Session
        elapsed_seconds: float = 0.0  # filled in by the Session


class SimulatedAnnealing(Algorithm):
    # Class attributes required by the contract (6.2)
    id = "simulated_annealing"
    display_name = "Simulated Annealing"
    description = ("Accepts some worse paintings while it is 'hot', then cools down and "
                   "settles. Explores early, refines late.")

    # Tuning constants (kept here so they are easy to find and explain)
    USE_RELATIVE_DELTA = True      # see the module docstring, decision 1
    CALIBRATION_SAMPLES = 60       # sample moves used to calibrate the start temperature
    TARGET_ACCEPT = 0.8            # a typical worse move is accepted 80% of the time at the start
    REHEAT_FRACTION = 0.5          # "reheat" jumps back to 50% of the start temperature
    MIN_TEMPERATURE = 0.001        # frozen below this until the user reheats

    # ---------------------------------------------------------------- contract metadata
    @staticmethod
    def param_specs() -> list:
        """Sliders the UI will build for this algorithm (names reserved in Contract 7)."""
        return [
            ParamSpec(name="step_scale", label="Step size", kind="float", minimum=0.01,
                      maximum=1.0, default=0.3, step=0.01, scale="log", group="algorithm",
                      help_text="How big each random change is."),
            ParamSpec(name="start_temperature_scale", label="Start temperature", kind="float",
                      minimum=0.1, maximum=5.0, default=1.0, step=0.1, scale="log",
                      group="algorithm",
                      help_text="Multiplier on the automatically calibrated start temperature."),
            ParamSpec(name="cooling_rate", label="Cooling rate", kind="float",
                      minimum=0.9990, maximum=0.99999, default=0.9995, step=0.00001,
                      scale="log", group="algorithm",
                      help_text="Temperature is multiplied by this after every evaluation. "
                                "Closer to 1 cools slower."),
        ]

    @staticmethod
    def action_specs() -> list:
        return [ActionSpec(name="reheat", label="Reheat",
                           help_text="Raise the temperature again to escape a stuck painting.")]

    # ---------------------------------------------------------------- construction
    def __init__(self, problem, seed: int, params: dict | None = None):
        self.problem = problem
        self.rng = random.Random(seed)            # our own generator (Contract 2: no global random)
        self._specs = {s.name: s for s in self.param_specs()}
        self.params = {name: spec.default for name, spec in self._specs.items()}

        # Search state. States are never edited, only replaced (Contract 2).
        self.state = problem.initial_state()
        self.cost = problem.evaluate(self.state)   # initial evaluation is not counted
        self.best_state, self.best_cost = self.state, self.cost

        # Counters (cumulative, as the Snapshot expects)
        self.iteration = 0
        self.evaluations = 0
        self.proposed_total = 0
        self.accepted_total = 0
        self.worse_accepted_total = 0

        # Temperature is unknown until the first advance() calibrates it.
        self.t0: float | None = None              # calibrated start temperature (before the scale slider)
        self.temperature: float | None = None
        self.last_accept_probability = 1.0

        for name, value in (params or {}).items():
            self.set_param(name, value)

    # ---------------------------------------------------------------- helpers
    def _delta_scale(self) -> float:
        """Divide deltas by this. Current cost when relative, 1.0 when absolute."""
        return max(self.cost, 1e-12) if self.USE_RELATIVE_DELTA else 1.0

    def _calibrate(self) -> int:
        """Pick the start temperature from sample moves. Returns evaluations spent."""
        deltas = []
        scale = self._delta_scale()
        for _ in range(self.CALIBRATION_SAMPLES):
            proposal = self.problem.propose(self.state, self.rng, self.params["step_scale"])
            deltas.append((proposal.cost - self.cost) / scale)
        self.evaluations += self.CALIBRATION_SAMPLES   # calibration is honest: it costs budget

        uphill = [d for d in deltas if d > 0]
        if len(uphill) >= 5:
            typical = sum(uphill) / len(uphill)                    # average worsening
        else:                                                      # almost every move improved
            typical = sum(abs(d) for d in deltas) / max(len(deltas), 1)
        if typical <= 0:
            typical = 0.01
        # Solve exp(-typical / T0) = TARGET_ACCEPT for T0.
        self.t0 = typical / -math.log(self.TARGET_ACCEPT)
        self.temperature = self.t0 * self.params["start_temperature_scale"]
        return self.CALIBRATION_SAMPLES

    def _accept(self, delta: float) -> bool:
        """Metropolis rule: always accept better, sometimes accept worse."""
        if delta <= 0:
            return True
        x = delta / self._delta_scale() / self.temperature
        probability = math.exp(-x) if x < 700 else 0.0
        self.last_accept_probability = probability
        return self.rng.random() < probability

    # ---------------------------------------------------------------- contract methods
    def advance(self, budget_evaluations: int) -> Snapshot:
        """Spend at least `budget_evaluations` evaluations, then report."""
        spent = 0
        if self.t0 is None:
            spent += self._calibrate()
        cooling = self.params["cooling_rate"]
        step_scale = self.params["step_scale"]

        while spent < budget_evaluations:
            if self.temperature <= self.MIN_TEMPERATURE:   # frozen: stop searching until Reheat
                self.evaluations += budget_evaluations - spent
                break
            proposal = self.problem.propose(self.state, self.rng, step_scale)
            spent += 1
            self.evaluations += 1
            self.iteration += 1
            self.proposed_total += 1

            delta = proposal.cost - self.cost
            if self._accept(delta):
                self.accepted_total += 1
                if delta > 0:
                    self.worse_accepted_total += 1     # we accepted a worse painting on purpose
                self.state, self.cost = proposal.state, proposal.cost
                if self.cost < self.best_cost:         # remember the best painting ever seen
                    self.best_state, self.best_cost = self.state, self.cost

            # Cool down a little after every evaluation (read live, so the slider works).
            cooling = self.params["cooling_rate"]
            self.temperature = max(self.temperature * cooling, self.MIN_TEMPERATURE)

        return self.current_snapshot()

    def set_param(self, name: str, value) -> bool:
        """Live parameter change. Returns False for unknown names."""
        spec = self._specs.get(name)
        if spec is None:
            return False
        value = float(value)
        value = min(max(value, spec.minimum), spec.maximum)   # clamp to the slider range
        if name == "start_temperature_scale" and self.temperature is not None:
            # Keep the current temperature proportional when the slider moves.
            self.temperature *= value / self.params[name]
        self.params[name] = value
        return True

    def trigger(self, action_name: str) -> None:
        """One-shot actions. Only 'reheat' exists."""
        if action_name == "reheat" and self.t0 is not None:
            hot = self.t0 * self.params["start_temperature_scale"] * self.REHEAT_FRACTION
            self.temperature = max(self.temperature, hot)

    def inject(self, batch) -> None:
        """Shapes were thrown onto the canvas: adopt them and restart the 'best' baseline."""
        self.state = self.problem.apply_injection(self.state, batch)
        self.cost = self.problem.evaluate(self.state)
        self.evaluations += 1
        self.best_state, self.best_cost = self.state, self.cost   # Contract 6.2

    def current_snapshot(self) -> Snapshot:
        temperature = self.temperature if self.temperature is not None else 0.0
        return Snapshot(
            algorithm_id=self.id,
            iteration=self.iteration,
            evaluations=self.evaluations,
            cost=self.cost,
            similarity=self.problem.similarity(self.cost),
            best_cost=self.best_cost,
            best_similarity=self.problem.similarity(self.best_cost),
            state=self.state,
            best_state=self.best_state,
            proposed_total=self.proposed_total,
            accepted_total=self.accepted_total,
            worse_accepted_total=self.worse_accepted_total,
            extras={
                "temperature": temperature,                        # relative units (see docstring)
                "temperature_abs": temperature * self._delta_scale(),
                "accept_probability": self.last_accept_probability,
                "start_temperature": (self.t0 or 0.0) * self.params["start_temperature_scale"],
            },
        )