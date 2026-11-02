"""Conformance suite for the Session interface (contract 11). Owner: M2.

Use it by subclassing in a test file and implementing make_session:

    class TestRealSession(SessionConformance):
        def make_session(self, panels=2, max_evaluations=20_000): ...
"""

from __future__ import annotations

from typing import Any

from contracts.definitions import commands
from contracts.definitions.outcome import AWARD_IDS, WINNER_CATEGORIES
from contracts.definitions.session import MAX_HISTORY_POINTS, STATUS_VALUES

RECORD_FIELDS = (
    "run_id", "created_at", "contract_version", "config",
    "results", "winners", "awards", "events", "history",
)  # fmt: skip


class SessionConformance:
    """Mixin with the shared Session tests."""

    tick_seconds = 0.1
    max_ticks = 5000

    def make_session(self, panels: int = 2, max_evaluations: int = 20_000) -> Any:
        """Return a fresh Session with the given number of panels and budget."""
        raise NotImplementedError

    def run_ticks(self, session: Any, count: int) -> None:
        """Tick the session count times."""
        for _ in range(count):
            session.tick(self.tick_seconds)

    def events_of(self, session: Any, type_: str) -> list[Any]:
        """Drain events and keep those of one type."""
        return [e for e in session.poll_events() if e.type == type_]

    def test_tick_advances_every_panel(self) -> None:
        """Each unfinished panel makes progress and carries its own index."""
        s = self.make_session(panels=3)
        self.run_ticks(s, 5)
        for i in range(3):
            snap = s.snapshot(i)
            assert snap.panel_index == i
            assert snap.evaluations > 0
            assert snap.elapsed_seconds > 0

    def test_status_is_a_known_value(self) -> None:
        """status is one of running, paused or finished."""
        s = self.make_session()
        assert s.status() in STATUS_VALUES

    def test_pause_and_resume(self) -> None:
        """Paused sessions do not advance; resume continues."""
        s = self.make_session()
        self.run_ticks(s, 3)
        before = s.snapshot(0).evaluations
        s.send(commands.pause())
        self.run_ticks(s, 3)
        assert s.status() == "paused"
        assert s.snapshot(0).evaluations == before
        s.send(commands.resume())
        self.run_ticks(s, 3)
        assert s.status() == "running"
        assert s.snapshot(0).evaluations > before

    def test_speed_controls_progress(self) -> None:
        """A faster panel spends more evaluations than a slower one."""
        s = self.make_session()
        s.send(commands.set_speed(0, 200))
        s.send(commands.set_speed(1, 2000))
        self.run_ticks(s, 10)
        assert s.panel_info(0).speed == 200
        assert s.panel_info(1).speed == 2000
        assert s.snapshot(1).evaluations > s.snapshot(0).evaluations

    def test_set_param_updates_panel_and_emits_event(self) -> None:
        """set_param changes panel_info and emits param_changed."""
        s = self.make_session()
        s.send(commands.set_param(0, "algorithm", "step_scale", 0.5))
        s.tick(self.tick_seconds)
        events = self.events_of(s, "param_changed")
        assert len(events) == 1
        assert events[0].panel == 0
        assert events[0].payload["name"] == "step_scale"
        assert events[0].payload["new_value"] == 0.5
        assert s.panel_info(0).params["step_scale"] == 0.5

    def test_trigger_action_is_accepted(self) -> None:
        """Every published action can be triggered through a command."""
        s = self.make_session()
        for action in s.panel_info(0).action_specs:
            s.send(commands.trigger_action(0, action.name))
        self.run_ticks(s, 2)
        assert s.snapshot(0).evaluations > 0

    def test_inject_all_then_one_panel(self) -> None:
        """inject reaches all panels or only the listed ones, and emits events."""
        s = self.make_session()
        self.run_ticks(s, 5)
        s.poll_events()
        s.send(commands.inject())
        s.tick(self.tick_seconds)
        events = self.events_of(s, "shapes_injected")
        assert sorted(e.panel for e in events) == [0, 1]
        assert all(e.payload["count"] == 50 for e in events)
        s.send(commands.inject(count=10, panels=[1]))
        s.tick(self.tick_seconds)
        events = self.events_of(s, "shapes_injected")
        assert [e.panel for e in events] == [1]
        assert events[0].payload["count"] == 10

    def test_milestone_events_and_leaderboard_hits(self) -> None:
        """Reaching 80 percent emits one event and shows up on the leaderboard."""
        s = self.make_session()
        seen: list[Any] = []
        for _ in range(self.max_ticks):
            s.tick(self.tick_seconds)
            seen += s.poll_events()
            if any(e.type == "milestone_reached" for e in seen):
                break
        hits = [e for e in seen if e.type == "milestone_reached"]
        assert hits and hits[0].payload["level"] == 80
        entry = next(e for e in s.leaderboard() if e.panel_index == hits[0].panel)
        assert 80 in entry.milestones
        assert entry.milestones[80].evaluations > 0

    def test_leaderboard_is_ordered(self) -> None:
        """Ranks run 1..n, sorted by best similarity, ties by panel index."""
        s = self.make_session(panels=3)
        self.run_ticks(s, 20)
        entries = s.leaderboard()
        assert [e.rank for e in entries] == [1, 2, 3]
        assert sorted(e.panel_index for e in entries) == [0, 1, 2]
        keys = [(-e.best_similarity, e.panel_index) for e in entries]
        assert keys == sorted(keys)
        assert all(isinstance(e.rank_change, int) for e in entries)

    def test_poll_events_drains(self) -> None:
        """Events are returned once."""
        s = self.make_session()
        self.run_ticks(s, 5)
        s.poll_events()
        assert s.poll_events() == []

    def test_history_is_bounded_and_ordered(self) -> None:
        """history respects max_points and is ordered by evaluations."""
        s = self.make_session()
        self.run_ticks(s, 30)
        points = s.history(0, 10)
        assert 1 <= len(points) <= 10
        evals = [p.evaluations for p in points]
        assert evals == sorted(evals)
        assert len(s.history(0, 10**6)) <= MAX_HISTORY_POINTS
        assert all(0.0 <= p.acceptance_rate <= 1.0 for p in points)

    def test_budget_end_finishes_the_run(self) -> None:
        """When every panel spends its budget the run finishes by itself."""
        s = self.make_session(max_evaluations=2000)
        seen: list[Any] = []
        for _ in range(self.max_ticks):
            s.tick(self.tick_seconds)
            seen += s.poll_events()
            if s.status() == "finished":
                break
        assert s.status() == "finished"
        finished = [e for e in seen if e.type == "panel_finished"]
        assert sorted(e.panel for e in finished) == [0, 1]
        assert all(e.payload["reason"] == "budget" for e in finished)
        run_done = [e for e in seen if e.type == "run_finished"]
        assert len(run_done) == 1 and run_done[0].payload["reason"] == "budget"
        evals = s.snapshot(0).evaluations
        self.run_ticks(s, 3)
        assert s.snapshot(0).evaluations == evals

    def test_finish_returns_a_complete_record(self) -> None:
        """finish stops the run and returns a full record, idempotently."""
        s = self.make_session()
        self.run_ticks(s, 10)
        record = s.finish()
        assert s.status() == "finished"
        for name in RECORD_FIELDS:
            assert hasattr(record, name), name
        assert len(record.results) == 2
        assert all(r.outcome.total_evaluations > 0 for r in record.results)
        assert set(record.winners) == set(WINNER_CATEGORIES)
        assert all(w is None or w in (0, 1) for w in record.winners.values())
        assert set(record.awards) <= set(AWARD_IDS) - {"solo_artist"}
        runs = [e for e in record.events if e.type == "run_finished"]
        assert [e.payload["reason"] for e in runs] == ["user"]
        assert s.finish() is record

    def test_single_panel_gets_only_solo_artist(self) -> None:
        """A one-panel run has no rivals, so solo_artist replaces all awards."""
        s = self.make_session(panels=1)
        self.run_ticks(s, 10)
        assert s.finish().awards == {"solo_artist": 0}
