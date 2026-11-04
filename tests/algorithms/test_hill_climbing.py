"""Hill climbing against the Algorithm contract, on the toy problem and the real engine."""
import copy
import pytest

from algorithms.hill_climbing import HillClimbing
from contracts.definitions import ShapeConfig, Snapshot
from contracts.stubs.toy_problem import ToyProblem
from engine import create_problem

IMG = "tests/engine/data/m1_test_target.png"
MAKERS = {"toy": lambda: ToyProblem(seed=1), "engine": lambda: create_problem(IMG, ShapeConfig(), "full_color", 1)}


@pytest.fixture(params=list(MAKERS))
def prob(request):
    return MAKERS[request.param]()


def test_identity_and_specs():
    assert HillClimbing.id == "hill_climbing" and HillClimbing.display_name and HillClimbing.description
    names = [s.name for s in HillClimbing.param_specs()]
    assert names == ["step_scale"] and HillClimbing.action_specs() == []
    spec = HillClimbing.param_specs()[0]
    assert (spec.minimum, spec.maximum, spec.default, spec.scale, spec.group) == (0.01, 1.0, 0.3, "log", "algorithm")


def test_deterministic_per_seed(prob):
    a = HillClimbing(prob, 5).advance(300)
    b = HillClimbing(MAKERS["toy"]() if isinstance(prob, ToyProblem) else MAKERS["engine"](), 5).advance(300)
    assert (a.cost, a.evaluations, a.accepted_total) == (b.cost, b.evaluations, b.accepted_total)
    c = HillClimbing(prob, 6).advance(300)
    assert c.cost != a.cost


def test_valid_snapshot_and_counters(prob):
    algo = HillClimbing(prob, 1)
    s0 = algo.current_snapshot()
    assert isinstance(s0, Snapshot) and s0.evaluations == 0 and s0.algorithm_id == "hill_climbing"
    s = algo.advance(200)
    assert s.evaluations == s.proposed_total == s.iteration == 200
    assert 0 <= s.accepted_total <= 200 and s.worse_accepted_total == 0
    assert s.cost <= s0.cost and s.best_cost <= s.cost + 1e-12
    assert s.similarity == prob.similarity(s.cost)
    assert algo.advance(0).evaluations == 200


def test_cost_never_increases(prob):
    algo, last = HillClimbing(prob, 2), float("inf")
    for _ in range(10):
        c = algo.advance(50).cost
        assert c <= last
        last = c


def test_never_edits_given_state(prob):
    algo = HillClimbing(prob, 3)
    s = algo.advance(50).state
    frozen = copy.deepcopy(s)
    algo.advance(100)
    assert s == frozen


def test_set_param_is_honored_and_clamped(prob):
    algo = HillClimbing(prob, 1)
    algo.set_param("step_scale", 0.8)
    assert algo.current_snapshot().extras["step_scale"] == 0.8
    algo.set_param("step_scale", 99)
    assert algo.current_snapshot().extras["step_scale"] == 1.0
    algo.set_param("nonsense", 1)  # ignored
    with pytest.raises(ValueError):
        algo.trigger("reheat")


def test_inject_resets_best(prob):
    algo = HillClimbing(prob, 1)
    algo.advance(200)
    before = algo.current_snapshot()
    algo.inject(prob.make_injection(4, 20))
    after = algo.current_snapshot()
    assert after.cost != before.cost and after.best_cost == after.cost
    assert algo.advance(100).cost <= after.cost
