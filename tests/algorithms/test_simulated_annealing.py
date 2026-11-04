"""Tests for algorithms/simulated_annealing.py using a toy problem, so M3 needs nobody else.

The toy problem: a 'painting' is a single number x, and the cost is how far x is from 3,
plus a small bump so there are local optima to escape.
"""
import math
from collections import namedtuple

from algorithms.simulated_annealing import SimulatedAnnealing

Proposal = namedtuple("Proposal", "state cost kind")


class ToyProblem:
    """Minimal stand-in for the engine's Problem (Contract 6.1)."""

    def initial_state(self):
        return 10.0

    def evaluate(self, state):
        return (state - 3.0) ** 2 + 2.0 * (math.sin(5 * state) + 1)

    def propose(self, state, rng, step_scale):
        new = state + rng.uniform(-1, 1) * step_scale * 5   # never edits the old state
        return Proposal(new, self.evaluate(new), "move")

    def similarity(self, cost):
        return max(0.0, 100.0 * (1 - math.sqrt(cost) / 255))

    def apply_injection(self, state, batch):
        return state + sum(batch)


def make(seed=1, **params):
    return SimulatedAnnealing(ToyProblem(), seed, params)


def test_metadata_matches_contract():
    names = {s.name for s in SimulatedAnnealing.param_specs()}
    assert names == {"step_scale", "start_temperature_scale", "cooling_rate"}
    assert [a.name for a in SimulatedAnnealing.action_specs()] == ["reheat"]
    assert SimulatedAnnealing.id == "simulated_annealing"


def test_same_seed_gives_same_result():
    a, b = make(seed=5), make(seed=5)
    sa, sb = a.advance(500), b.advance(500)
    assert (sa.cost, sa.best_cost, sa.worse_accepted_total) == (sb.cost, sb.best_cost, sb.worse_accepted_total)


def test_advance_spends_at_least_the_budget_and_improves():
    algo = make()
    start_cost = algo.cost
    snap = algo.advance(1000)
    assert snap.evaluations >= 1000
    assert snap.best_cost < start_cost
    assert snap.best_cost <= snap.cost            # best is never worse than current


def test_accepts_worse_moves_when_hot():
    snap = make(start_temperature_scale=5.0).advance(2000)
    assert snap.worse_accepted_total > 0
    assert snap.accepted_total >= snap.worse_accepted_total


def test_cooling_lowers_temperature():
    algo = make()
    first = algo.advance(100).extras["temperature"]
    later = algo.advance(2000).extras["temperature"]
    assert later < first


def test_set_param_clamps_and_rejects_unknown():
    algo = make()
    assert algo.set_param("cooling_rate", 5.0) is True
    assert algo.params["cooling_rate"] == 0.99999     # clamped to the spec maximum
    assert algo.set_param("not_a_param", 1) is False


def test_start_temperature_slider_rescales_live():
    algo = make()
    algo.advance(100)
    before = algo.temperature
    algo.set_param("start_temperature_scale", 2.0)    # default is 1.0, so T should double
    assert math.isclose(algo.temperature, before * 2.0, rel_tol=1e-9)


def test_reheat_raises_temperature():
    algo = make(cooling_rate=0.9990)
    algo.advance(3000)                                 # cool down a lot
    cold = algo.temperature
    algo.trigger("reheat")
    assert algo.temperature > cold


def test_inject_resets_best_and_counts_an_evaluation():
    algo = make()
    algo.advance(500)
    evals = algo.evaluations
    algo.inject([4.0, 4.0])
    snap = algo.current_snapshot()
    assert snap.evaluations == evals + 1
    assert snap.best_cost == snap.cost                 # baseline restarts after injection


def test_snapshot_has_contract_fields():
    snap = make().advance(10)
    for name in ("algorithm_id", "iteration", "evaluations", "cost", "similarity", "best_cost",
                 "best_similarity", "state", "best_state", "proposed_total", "accepted_total",
                 "worse_accepted_total", "extras"):
        assert hasattr(snap, name), name
    assert "temperature" in snap.extras
