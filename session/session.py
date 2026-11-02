"""The Session: runs 1 to 4 panels and gives the UI snapshots, events and a record."""

from __future__ import annotations

import logging
import math
import time
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Any

from contracts.definitions import (
    Algorithm,
    Command,
    Event,
    HistoryPoint,
    LeaderboardEntry,
    PanelInfo,
    ParamSpec,
    Snapshot,
)
from session.commands import apply_command
from session.history import History
from session.leaderboard import build_leaderboard
from session.milestones import MilestoneTracker
from session.record import (
    CONTRACT_VERSION,
    Injection,
    PanelResult,
    RunRecord,
    make_run_id,
    to_plain,
)
from session.registry import get_algorithm
from session.scheduler import Scheduler
from session.scoring import build_outcome, pick_awards, pick_winners

log = logging.getLogger(__name__)

TICK_LIMIT = 0.025
CHUNK = 50
SPEED_RANGE = (50.0, 10000.0)
EVENT_INTERVAL = 1.0
RESULT_SIZE = 512


@dataclass
class Panel:
    """Everything the Session keeps for one panel."""

    index: int
    problem: Any
    algo: Algorithm
    speed: float
    budget: int
    params: dict[str, dict[str, Any]]
    snap: Snapshot
    history: History = field(default_factory=History)
    milestones: MilestoneTracker = field(default_factory=MilestoneTracker)
    injections: list[Injection] = field(default_factory=list)
    elapsed: float = 0.0
    finished: bool = False
    throttled: bool = False
    worse_seen: int = 0
    burst: int = 0
    last_burst: float = -math.inf
    last_throttle: float = -math.inf


def clamp_speed(speed: float) -> float:
    """Keep speed inside the allowed range."""
    return min(SPEED_RANGE[1], max(SPEED_RANGE[0], float(speed)))


def coerce(spec: ParamSpec, value: Any) -> Any:
    """Cast a parameter value to its kind and clamp it to its range."""
    if spec.kind == "bool":
        return bool(value)
    if spec.kind == "choice":
        return value if value in spec.options else spec.default
    number = min(spec.maximum, max(spec.minimum, float(value)))
    return int(round(number)) if spec.kind == "int" else number


def build_panel(
    index: int,
    problem: Any,
    algorithm_class: type[Algorithm],
    seed: int,
    speed: float,
    algorithm_params: dict[str, Any] | None,
    painting_params: dict[str, Any] | None,
    budget: int,
) -> Panel:
    """Create a panel: apply painting params, build the algorithm, take a first snapshot."""
    for name, value in (painting_params or {}).items():
        problem.set_param(name, value)
    params = {
        "algorithm": {s.name: s.default for s in algorithm_class.param_specs()},
        "painting": {s.name: s.default for s in problem.param_specs()},
    }
    params["algorithm"].update(algorithm_params or {})
    params["painting"].update(painting_params or {})
    algo = algorithm_class(problem, seed, params["algorithm"])
    snap = replace(algo.current_snapshot(), panel_index=index)
    return Panel(index, problem, algo, clamp_speed(speed), budget, params, snap)


class Session:
    """Advances panels on tick, applies queued commands and keeps the run log."""

    def __init__(
        self,
        panels: list[Panel],
        seed: int,
        config: Any,
        clock: Callable[[], float] = time.monotonic,
        tick_limit: float = TICK_LIMIT,
    ) -> None:
        """Wrap ready-made panels; clock and tick_limit exist for tests and batch runs."""
        self.panels = panels
        self.seed = seed
        self.config = config
        self._clock = clock
        self._tick_limit = tick_limit
        self._scheduler = Scheduler(len(panels))
        self._status = "running"
        self._queue: list[Command] = []
        self._pending: list[Event] = []
        self._log: list[Event] = []
        self._ranks: dict[int, int] = {}
        self._leader: int | None = None
        self._board: list[LeaderboardEntry] = []
        self._injection_count = 0
        self._record: RunRecord | None = None
        for panel in panels:
            panel.history.add(panel.snap)
        self._update_leaderboard()

    def tick(self, seconds: float) -> None:
        """Apply queued commands, then advance every unfinished panel."""
        queue, self._queue = self._queue, []
        for command in queue:
            apply_command(self, command)
        if self._status != "running":
            return
        active = [p for p in self.panels if not p.finished]
        for panel in active:
            self._advance(panel, seconds, len(active))
        self._update_leaderboard()
        if all(p.finished for p in self.panels):
            self._end_run("budget")

    def send(self, command: Command) -> None:
        """Queue a command for the next tick."""
        self._queue.append(command)

    def snapshot(self, panel: int) -> Snapshot:
        """Return the latest Snapshot of a panel."""
        return self.panels[panel].snap

    def history(self, panel: int, max_points: int) -> list[HistoryPoint]:
        """Return at most max_points history points."""
        return self.panels[panel].history.sample(max_points)

    def leaderboard(self) -> list[LeaderboardEntry]:
        """Return the ranked leaderboard."""
        return list(self._board)

    def poll_events(self) -> list[Event]:
        """Return events since the last call."""
        events, self._pending = self._pending, []
        return events

    def panel_info(self, panel: int) -> PanelInfo:
        """Return parameter values, specs, speed and the throttled flag."""
        p = self.panels[panel]
        return PanelInfo(
            algorithm_id=p.algo.id,
            params={**p.params["algorithm"], **p.params["painting"]},
            param_specs=tuple(p.algo.param_specs()) + tuple(p.problem.param_specs()),
            action_specs=tuple(p.algo.action_specs()),
            speed=p.speed,
            throttled=p.throttled,
        )

    def render(self, panel: int, size: int) -> Any:
        """Return a Pillow image of the panel's current state."""
        p = self.panels[panel]
        return p.problem.render(p.snap.state, size)

    def status(self) -> str:
        """Return running, paused or finished."""
        return self._status

    def finish(self) -> RunRecord:
        """Stop the run and return the record; later calls return the same record."""
        if self._record is None:
            self._cmd_finish()
            self._record = self._build_record()
        return self._record

    def _advance(self, panel: Panel, seconds: float, sharing: int) -> None:
        """Run one panel for this tick without exceeding its share of the time limit."""
        owed = self._scheduler.owed(panel.index, panel.speed, seconds)
        want = min(owed, max(0, panel.budget - panel.snap.evaluations))
        deadline = self._clock() + self._tick_limit / sharing
        spent = 0
        while spent < want and (spent == 0 or self._clock() < deadline):
            started = self._clock()
            snap = panel.algo.advance(min(CHUNK, want - spent))
            panel.elapsed += self._clock() - started
            spent += snap.evaluations - panel.snap.evaluations
            panel.snap = replace(snap, panel_index=panel.index, elapsed_seconds=panel.elapsed)
        panel.throttled = self._scheduler.settle(panel.index, spent)
        if spent:
            self._record_progress(panel)
        now = self._clock()
        if panel.throttled and not panel.finished and now - panel.last_throttle >= EVENT_INTERVAL:
            panel.last_throttle = now
            achieved = spent / seconds if seconds > 0 else 0.0
            self._emit(
                "panel_throttled", panel.index, requested_speed=panel.speed, achieved_speed=achieved
            )

    def _record_progress(self, panel: Panel) -> None:
        """Update history, milestones, recoveries and events after a panel advanced."""
        snap = panel.snap
        panel.history.add(snap)
        for level in panel.milestones.update(snap.best_similarity, snap.evaluations, panel.elapsed):
            self._emit("milestone_reached", panel.index, level=level)
        for injection in panel.injections:
            if injection.recovery_evaluations is None and snap.best_cost <= injection.cost_before:
                injection.recovery_evaluations = snap.evaluations - injection.evaluation_index
        panel.burst += max(0, snap.worse_accepted_total - panel.worse_seen)
        panel.worse_seen = snap.worse_accepted_total
        now = self._clock()
        if panel.burst and now - panel.last_burst >= EVENT_INTERVAL:
            self._emit("worse_move_burst", panel.index, count=panel.burst)
            panel.burst, panel.last_burst = 0, now
        if snap.evaluations >= panel.budget:
            self._finish_panel(panel, "budget")

    def _refresh(self, panel: Panel) -> None:
        """Re-read the algorithm's snapshot after a command changed it."""
        snap = panel.algo.current_snapshot()
        panel.snap = replace(snap, panel_index=panel.index, elapsed_seconds=panel.elapsed)

    def _emit(self, type_: str, panel: int | None, **payload: Any) -> None:
        """Log an event and queue it for poll_events."""
        chosen = self.panels if panel is None else [self.panels[panel]]
        evaluations = max(p.snap.evaluations for p in chosen)
        seconds = max(p.elapsed for p in chosen)
        event = Event(type_, panel, evaluations, seconds, payload)
        self._pending.append(event)
        self._log.append(event)

    def _update_leaderboard(self) -> None:
        """Rebuild the leaderboard and announce a new leader."""
        self._board = build_leaderboard(
            [p.snap for p in self.panels],
            [p.finished for p in self.panels],
            [p.milestones.hits for p in self.panels],
            self._ranks,
        )
        self._ranks = {e.panel_index: e.rank for e in self._board}
        leader = self._board[0].panel_index
        if self._leader is not None and leader != self._leader:
            self._emit("leader_changed", None, old_panel=self._leader, new_panel=leader)
        self._leader = leader

    def _finish_panel(self, panel: Panel, reason: str) -> None:
        """Mark a panel finished once."""
        if not panel.finished:
            panel.finished = True
            self._emit("panel_finished", panel.index, reason=reason)

    def _end_run(self, reason: str) -> None:
        """Mark the run finished once."""
        if self._status != "finished":
            self._status = "finished"
            self._emit("run_finished", None, reason=reason)

    def _cmd_pause(self) -> None:
        """Pause a running session."""
        if self._status == "running":
            self._status = "paused"

    def _cmd_resume(self) -> None:
        """Resume a paused session."""
        if self._status == "paused":
            self._status = "running"

    def _cmd_finish(self) -> None:
        """Finish every panel and the run."""
        for panel in self.panels:
            self._finish_panel(panel, "user")
        self._end_run("user")

    def _cmd_set_speed(self, panel: int, speed: float) -> None:
        """Set a panel's target speed."""
        self.panels[panel].speed = clamp_speed(speed)

    def _cmd_set_param(self, panel: int, group: str, name: str, value: Any) -> None:
        """Change an algorithm or painting parameter and announce it."""
        p = self.panels[panel]
        owner = p.algo if group == "algorithm" else p.problem
        spec = next((s for s in owner.param_specs() if s.name == name), None)
        if spec is None:
            raise KeyError(name)
        value = coerce(spec, value)
        old = p.params[group][name]
        owner.set_param(name, value)
        p.params[group][name] = value
        self._emit("param_changed", panel, name=name, old_value=old, new_value=value)

    def _cmd_trigger_action(self, panel: int, action: str) -> None:
        """Run a one-shot algorithm action."""
        p = self.panels[panel]
        if action not in [a.name for a in p.algo.action_specs()]:
            raise KeyError(action)
        p.algo.trigger(action)
        self._refresh(p)

    def _cmd_inject(self, count: int = 50, panels: str | list[int] = "all") -> None:
        """Inject one batch of random shapes into all panels or the listed ones."""
        chosen = self.panels if panels == "all" else [self.panels[i] for i in panels]
        targets = [p for p in chosen if not p.finished]
        if not targets:
            return
        self._injection_count += 1
        batch = targets[0].problem.make_injection(self.seed + self._injection_count, count)
        for p in targets:
            before = p.snap.cost
            p.algo.inject(batch)
            self._refresh(p)
            p.injections.append(Injection(p.snap.evaluations, before, p.snap.cost))
            p.history.add(p.snap)
            self._emit(
                "shapes_injected", p.index, count=count, cost_before=before, cost_after=p.snap.cost
            )

    def _build_record(self) -> RunRecord:
        """Assemble outcomes, winners, awards, events, history and images."""
        outcomes = [
            build_outcome(
                p.snap,
                p.history.points,
                p.milestones.hits,
                p.injections,
                p.budget,
                p.problem.shape_count(p.snap.best_state),
            )
            for p in self.panels
        ]
        winners = pick_winners(outcomes)
        now = datetime.now(timezone.utc)
        first = self.panels[0].problem
        return RunRecord(
            run_id=make_run_id(self.seed, now),
            created_at=now.isoformat(),
            contract_version=CONTRACT_VERSION,
            config=to_plain(self.config),
            results=[
                PanelResult(o, p.snap.state, p.snap.best_state)
                for o, p in zip(outcomes, self.panels)
            ],
            winners=winners,
            awards=pick_awards(outcomes, winners),
            events=list(self._log),
            history={p.index: list(p.history.points) for p in self.panels},
            images={
                "target": first.target_image(RESULT_SIZE),
                **{
                    f"result_{p.index}": p.problem.render(p.snap.best_state, RESULT_SIZE)
                    for p in self.panels
                },
            },
            shapes={p.index: p.problem.state_to_dict(p.snap.best_state) for p in self.panels},
        )


def create_session(run_config: Any, tick_limit: float = TICK_LIMIT) -> Session:
    """Build a Session from a RunConfig: one Problem and one algorithm per panel."""
    from engine import create_problem  # imported late so session loads without the engine

    if not 1 <= len(run_config.panels) <= 4:
        raise ValueError("a run has 1 to 4 panels")
    panels = []
    for i, cfg in enumerate(run_config.panels):
        problem = create_problem(
            run_config.target_path, run_config.shape_config, run_config.theme_id, run_config.seed
        )
        panels.append(
            build_panel(
                i,
                problem,
                get_algorithm(cfg.algorithm_id),
                run_config.seed,
                cfg.speed,
                cfg.algorithm_params,
                cfg.painting_params,
                run_config.max_evaluations,
            )
        )
    return Session(panels, run_config.seed, run_config, tick_limit=tick_limit)
