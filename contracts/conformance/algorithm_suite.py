from __future__ import annotations

import pickle
import random
import re
from typing import Any

from contracts.definitions.algorithm import Algorithm
from contracts.definitions.snapshot import Snapshot


def check_snapshot(snap: Snapshot, problem: Any) -> None:
    assert isinstance(snap, Snapshot)
    assert snap.evaluations >= 0 and snap.iteration >= 0
    assert 0.0 <= snap.similarity <= 100.0
    assert snap.best_cost <= snap.cost + 1e-9
    assert snap.best_similarity >= snap.similarity - 1e-9
    assert abs(snap.similarity - problem.similarity(snap.cost)) < 1e-6
    assert abs(snap.best_similarity - problem.similarity(snap.best_cost)) < 1e-6
    assert snap.proposed_total >= snap.accepted_total >= snap.worse_accepted_total >= 0
    assert snap.state is not None and snap.best_state is not None
    for key, value in snap.extras.items():
        assert isinstance(key, str) and isinstance(value, (int, float))


class AlgorithmConformance:

    algorithm_class: type[Algorithm]

    def make_problem(self) -> Any:
        raise NotImplementedError

    def make_injection_batch(self, count: int = 50) -> Any:
        return self.problem.make_injection(123, count)

    def setup_method(self, method: Any = None) -> None:
        self.problem = self.make_problem()

    def make(self, seed: int = 0, params: dict[str, Any] | None = None) -> Algorithm:
        return self.algorithm_class(self.problem, seed, params)

    def test_class_attributes(self) -> None:
        cls = self.algorithm_class
        assert re.fullmatch(r"[a-z][a-z0-9_]*", cls.id)
        assert cls.display_name and cls.description

    def test_step_scale_is_published(self) -> None:
        specs = {s.name: s for s in self.algorithm_class.param_specs()}
        s = specs["step_scale"]
        got = (s.kind, s.minimum, s.maximum, s.default, s.scale, s.group)
        assert got == ("float", 0.01, 1.0, 0.3, "log", "algorithm")

    def test_param_specs_are_well_formed(self) -> None:

        specs = self.algorithm_class.param_specs()
        assert len({s.name for s in specs}) == len(specs)
        for s in specs:
            if s.kind in ("float", "int"):
                assert s.minimum <= s.default <= s.maximum

    def test_deterministic_per_seed(self) -> None:

        a, b = self.make(seed=7), self.make(seed=7)
        for _ in range(3):
            assert a.advance(200) == b.advance(200)

    def test_advance_spends_the_budget(self) -> None:
        a = self.make()
        first = a.advance(100)
        assert first.evaluations >= 100
        second = a.advance(100)
        assert second.evaluations >= first.evaluations + 100

    def test_snapshots_are_valid(self) -> None:
        a = self.make()
        check_snapshot(a.current_snapshot(), self.problem)
        for _ in range(3):
            check_snapshot(a.advance(150), self.problem)

    def test_current_snapshot_does_not_advance(self) -> None:
        """current_snapshot is a pure read."""
        a = self.make()
        advanced = a.advance(100)
        assert a.current_snapshot() == advanced
        assert a.current_snapshot() == a.current_snapshot()

    def test_state_is_never_edited(self) -> None:
        a = self.make()
        snap = a.advance(100)
        frozen = pickle.dumps((snap.state, snap.best_state))
        a.advance(500)
        assert pickle.dumps((snap.state, snap.best_state)) == frozen

    def test_states_are_picklable(self) -> None:
        snap = self.make().advance(100)
        assert pickle.loads(pickle.dumps(snap.state)) == snap.state

    def test_global_random_is_untouched(self) -> None:
        a = self.make()
        random.seed(99)
        before = random.getstate()
        a.advance(300)
        assert random.getstate() == before

    def test_set_param_accepts_every_published_value(self) -> None:
        for spec in self.algorithm_class.param_specs():
            a = self.make()
            a.advance(50)
            values = [spec.default]
            if spec.kind in ("float", "int"):
                cast = int if spec.kind == "int" else float
                values += [cast(spec.minimum), cast(spec.maximum)]
            for value in values:
                a.set_param(spec.name, value)
                check_snapshot(a.advance(50), self.problem)

    def test_set_param_is_deterministic(self) -> None:
        runs = []
        for _ in range(2):
            a = self.make(seed=3)
            a.advance(100)
            a.set_param("step_scale", 0.8)
            a.advance(100)
            runs.append(a.advance(100))
        assert runs[0] == runs[1]

    def test_accepts_injection_and_resets_best(self) -> None:
        a = self.make()
        a.advance(200)
        a.inject(self.make_injection_batch())
        snap = a.current_snapshot()
        check_snapshot(snap, self.problem)
        assert snap.best_cost == snap.cost
        check_snapshot(a.advance(100), self.problem)

    def test_actions_can_be_triggered(self) -> None:
        for spec in self.algorithm_class.action_specs():
            a = self.make()
            a.advance(100)
            a.trigger(spec.name)
            check_snapshot(a.current_snapshot(), self.problem)
            check_snapshot(a.advance(50), self.problem)
