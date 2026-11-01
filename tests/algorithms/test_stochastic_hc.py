from contracts.conformance.algorithm_suite import AlgorithmConformance
from algorithms.stochastic_hc import StochasticHillClimbing
from tests.toy_problem import ToyProblem


class TestStochasticHC(AlgorithmConformance):
    algorithm_class = StochasticHillClimbing

    def make_problem(self):
        return ToyProblem()

    def test_never_gets_worse(self):
        a = self.make()
        costs = [a.advance(50).cost for _ in range(30)]
        assert costs == sorted(costs, reverse=True)
        assert a.current_snapshot().worse_accepted_total == 0

    def test_improves_the_painting(self):
        a = self.make()
        start = a.current_snapshot().similarity
        assert a.advance(2000).similarity > start + 5

    def test_batch_size_sets_step_length(self):
        snap = self.make(params={"batch_size": 10}).advance(1)
        assert (snap.iteration, snap.evaluations) == (1, 10)

    def test_batch_size_is_clamped(self):
        a = self.make()
        a.set_param("batch_size", 99)
        assert a.advance(1).evaluations == 20

    def test_reports_batch_hit_rate(self):
        a = self.make()
        assert 0.0 <= a.advance(500).extras["batch_hit_rate"] <= 1.0
