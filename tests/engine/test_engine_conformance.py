"""Runs the shared Problem conformance suite on the toy stub and on the real engine."""
import pytest

from contracts.conformance.problem_suite import ALL_CHECKS
from contracts.definitions import ShapeConfig
from contracts.stubs.toy_problem import ToyProblem
from engine import create_problem

IMG = "tests/engine/data/m1_test_target.png"
FACTORIES = {
    "toy": lambda: ToyProblem(seed=1),
    "engine_full_color": lambda: create_problem(IMG, ShapeConfig(), "full_color", 1),
    "engine_neon": lambda: create_problem(IMG, ShapeConfig(), "neon", 1),
}


@pytest.mark.parametrize("check", ALL_CHECKS, ids=lambda c: c.__name__)
@pytest.mark.parametrize("name", list(FACTORIES))
def test_problem_conformance(name, check):
    check(FACTORIES[name])
