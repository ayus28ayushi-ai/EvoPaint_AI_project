"""Run the conformance suites against the fakes, plus fake-specific checks."""

from __future__ import annotations

from contracts.conformance.algorithm_suite import AlgorithmConformance
from contracts.conformance.session_suite import SessionConformance
from contracts.definitions import commands
from contracts.definitions.session import Session
from contracts.stubs.fake_algorithm import FakeAlgorithm, ScriptedProblem
from contracts.stubs.fake_session import FakeSession


class TestFakeAlgorithm(AlgorithmConformance):
    """The fake must satisfy the same suite real algorithms will."""

    algorithm_class = FakeAlgorithm

    def make_problem(self) -> ScriptedProblem:
        """Return the scripted problem."""
        return ScriptedProblem()

    def test_larger_step_scale_climbs_faster(self) -> None:
        """Fake-only: step_scale visibly changes the scripted curve."""
        slow = self.make(params={"step_scale": 0.05}).advance(2000)
        fast = self.make(params={"step_scale": 1.0}).advance(2000)
        assert fast.best_similarity > slow.best_similarity


class TestFakeSession(SessionConformance):
    """The fake Session must satisfy the Session suite."""

    def make_session(self, panels: int = 2, max_evaluations: int = 20_000) -> FakeSession:
        """Return a fresh FakeSession."""
        return FakeSession(num_panels=panels, max_evaluations=max_evaluations)

    def test_matches_the_session_protocol(self) -> None:
        """Fake-only: it has every Session method."""
        assert isinstance(self.make_session(), Session)

    def test_leader_changes_to_the_faster_panel(self) -> None:
        """Fake-only: panel 1 climbs faster, so it takes the lead from panel 0."""
        s = self.make_session()
        s.tick(0.1)
        changes = self.events_of(s, "leader_changed")
        assert [(e.payload["old_panel"], e.payload["new_panel"]) for e in changes] == [(0, 1)]


class TestCommandValidation:
    """Commands and events reject malformed input."""

    def test_bad_commands_are_rejected(self) -> None:
        """Unknown types, missing keys and unknown groups raise ValueError."""
        for build in (
            lambda: commands.Command("explode"),
            lambda: commands.Command("set_speed", {"panel": 0}),
            lambda: commands.set_param(0, "wrong_group", "x", 1),
        ):
            try:
                build()
            except ValueError:
                continue
            raise AssertionError("expected ValueError")
