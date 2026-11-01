from types import SimpleNamespace

from algorithms.stochastic_hc import StochasticHillClimbing
from session.session import TICK_LIMIT, Session, build_panel
from tests.toy_problem import ToyProblem


class FakeClock:
    def __init__(self, step=0.0002):
        self.t, self.step = 0.0, step

    def __call__(self):
        self.t += self.step
        return self.t


def build_session(panels=2, max_evaluations=20_000, clock=None, tick_limit=TICK_LIMIT, seed=5):
    built = [
        build_panel(
            i, ToyProblem(), StochasticHillClimbing, seed, 1000.0,
            {"batch_size": 5 + 5 * (i % 2)}, {}, max_evaluations,
        )
        for i in range(panels)
    ]  # fmt: skip
    config = SimpleNamespace(
        seed=seed,
        max_evaluations=max_evaluations,
        panels=[SimpleNamespace(algorithm_id="stochastic_hc")] * panels,
    )
    return Session(built, seed, config, clock=clock or FakeClock(), tick_limit=tick_limit)
