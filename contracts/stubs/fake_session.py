"""Fake Session that scripts a run and accepts every command (contract 11).

Owner: M2. Built on FakeAlgorithm, so it needs no engine, images or Pygame.
The RunRecord here is PROVISIONAL: M4 owns the real layout (Section 5.14).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Any

from contracts.definitions.commands import Command
from contracts.definitions.events import Event
from contracts.definitions.outcome import (
    AWARD_IDS,
    MILESTONE_LEVELS,
    WINNER_CATEGORIES,
    InjectionRecord,
    MilestoneHit,
    Outcome,
)
from contracts.definitions.params import ParamSpec
from contracts.definitions.session import MAX_HISTORY_POINTS, PanelInfo
from contracts.definitions.snapshot import HistoryPoint, LeaderboardEntry, Snapshot
from contracts.stubs.fake_algorithm import FakeAlgorithm, ScriptedProblem

log = logging.getLogger(__name__)

MIN_SPEED, MAX_SPEED = 50.0, 10000.0


@dataclass(frozen=True)
class PanelResult:
    """Provisional per-panel result stored in the record."""

    outcome: Outcome
    final_state: Any
    best_state: Any


@dataclass
class ProvisionalRunRecord:
    """Provisional RunRecord with the in-memory fields of Section 5.14."""

    run_id: str
    created_at: str
    contract_version: str
    config: dict[str, Any]
    results: list[PanelResult]
    winners: dict[str, int | None]
    awards: dict[str, int]
    events: list[Event]
    history: dict[int, list[HistoryPoint]]
    images: dict[str, Any] = field(default_factory=dict)


def _painting_specs() -> list[ParamSpec]:
    """Return the painting-group specs the fake pretends the engine publishes."""
    return [
        ParamSpec(
            name="shape_limit", label="Shape limit", kind="int",
            minimum=10, maximum=1000, default=300, step=10, group="painting",
        ),
        ParamSpec(
            name="max_shape_size", label="Max shape size", kind="float",
            minimum=0.05, maximum=0.8, default=0.5, group="painting",
        ),
        ParamSpec(name="informed_colors", label="Informed colors", kind="bool",
                  default=True, group="painting"),
    ]  # fmt: skip


def _best_panel(values: dict[int, float], largest: bool) -> int | None:
    """Return the winning panel index; ties go to the lowest index."""
    winner: int | None = None
    for index in sorted(values):
        if winner is None:
            winner = index
        elif (values[index] > values[winner]) if largest else (values[index] < values[winner]):
            winner = index
    return winner


class FakeSession:
    """A Session with scripted panels. Accepts every command in Section 5.9."""

    def __init__(
        self,
        num_panels: int = 2,
        seed: int = 0,
        max_evaluations: int = 20_000,
        speed: float = 1000.0,
    ) -> None:
        """Create num_panels fake panels; panel i climbs a little faster than i-1."""
        if not 1 <= num_panels <= 4:
            raise ValueError("a run has 1 to 4 panels")
        self._seed = seed
        self._max = max_evaluations
        self._problem = ScriptedProblem()
        n = num_panels
        self._algos = [
            FakeAlgorithm(self._problem, seed + i, {"step_scale": 0.3 + 0.1 * i})
            for i in range(n)
        ]
        self._speeds = [float(speed)] * n
        self._carry = [0.0] * n
        self._elapsed = [0.0] * n
        self._done = [False] * n
        self._milestones: list[dict[int, MilestoneHit]] = [{} for _ in range(n)]
        self._injections: list[list[dict[str, Any]]] = [[] for _ in range(n)]
        self._histories: list[list[HistoryPoint]] = [[] for _ in range(n)]
        self._params: list[dict[str, dict[str, Any]]] = [
            {
                "algorithm": {s.name: s.default for s in FakeAlgorithm.param_specs()},
                "painting": {s.name: s.default for s in _painting_specs()},
            }
            for _ in range(n)
        ]
        self._status = "running"
        self._queue: list[Command] = []
        self._pending: list[Event] = []
        self._log: list[Event] = []
        self._leader: int | None = None
        self._ranks: dict[int, int] = {}
        self._entries: list[LeaderboardEntry] = []
        self._record: ProvisionalRunRecord | None = None
        self._injection_count = 0
        for i in range(n):
            self._history_append(i, self._snap(i))
        self._update_leaderboard()

    # ---- Session interface -------------------------------------------------

    def tick(self, seconds: float) -> None:
        """Apply queued commands, then advance every unfinished panel."""
        queue, self._queue = self._queue, []
        for command in queue:
            self._handle(command)
        if self._status != "running":
            return
        for i, algo in enumerate(self._algos):
            if self._done[i]:
                continue
            self._carry[i] += self._speeds[i] * seconds
            whole = int(self._carry[i])
            if whole > 0:
                before = algo.current_snapshot().evaluations
                remaining = self._max - before
                after = algo.advance(min(whole, remaining)).evaluations
                self._carry[i] -= after - before
            self._elapsed[i] += seconds
            snap = self._snap(i)
            self._after_advance(i, snap)
            if snap.evaluations >= self._max:
                self._finish_panel(i, "budget")
        self._update_leaderboard()
        if all(self._done):
            self._end_run("budget")

    def send(self, command: Command) -> None:
        """Queue a command; it applies at the start of the next tick."""
        self._queue.append(command)

    def snapshot(self, panel: int) -> Snapshot:
        """Return the latest Snapshot of a panel."""
        return self._snap(panel)

    def history(self, panel: int, max_points: int) -> list[HistoryPoint]:
        """Return at most max_points points, evenly thinned, oldest first."""
        points = self._histories[panel]
        if len(points) <= max_points:
            return list(points)
        stride = len(points) / max_points
        return [points[int(k * stride)] for k in range(max_points)]

    def leaderboard(self) -> list[LeaderboardEntry]:
        """Return entries sorted by rank."""
        return list(self._entries)

    def poll_events(self) -> list[Event]:
        """Return events since the last call."""
        events, self._pending = self._pending, []
        return events

    def panel_info(self, panel: int) -> PanelInfo:
        """Return parameter values, specs, speed and throttle flag."""
        values = {**self._params[panel]["algorithm"], **self._params[panel]["painting"]}
        specs = tuple(FakeAlgorithm.param_specs()) + tuple(_painting_specs())
        return PanelInfo(
            algorithm_id=FakeAlgorithm.id,
            params=values,
            param_specs=specs,
            action_specs=tuple(FakeAlgorithm.action_specs()),
            speed=self._speeds[panel],
            throttled=False,
        )

    def render(self, panel: int, size: int) -> Any:
        """Return a flat gray image whose brightness follows similarity."""
        from PIL import Image

        level = int(2.55 * self._snap(panel).similarity)
        return Image.new("RGB", (size, size), (level, level, level))

    def status(self) -> str:
        """Return running, paused or finished."""
        return self._status

    def finish(self) -> ProvisionalRunRecord:
        """Stop the run and return the record; calling again returns the same one."""
        if self._record is None:
            for i in range(len(self._algos)):
                self._finish_panel(i, "user")
            if self._status != "finished":
                self._end_run("user")
            self._record = self._build_record()
        return self._record

    # ---- internals ---------------------------------------------------------

    def _snap(self, panel: int) -> Snapshot:
        """Algorithm snapshot with the Session's fields filled in."""
        snap = self._algos[panel].current_snapshot()
        return replace(snap, panel_index=panel, elapsed_seconds=self._elapsed[panel])

    def _emit(self, type_: str, panel: int | None, **payload: Any) -> None:
        """Log an event and queue it for poll_events."""
        snaps = [self._snap(i) for i in range(len(self._algos))]
        if panel is None:
            evaluations = max(s.evaluations for s in snaps)
            seconds = max(self._elapsed)
        else:
            evaluations = snaps[panel].evaluations
            seconds = self._elapsed[panel]
        event = Event(type_, panel, evaluations, seconds, payload)
        self._pending.append(event)
        self._log.append(event)

    def _handle(self, command: Command) -> None:
        """Apply one command."""
        p = command.payload
        if command.type == "pause" and self._status == "running":
            self._status = "paused"
        elif command.type == "resume" and self._status == "paused":
            self._status = "running"
        elif command.type == "finish":
            for i in range(len(self._algos)):
                self._finish_panel(i, "user")
            if self._status != "finished":
                self._end_run("user")
        elif command.type == "set_speed":
            self._speeds[p["panel"]] = min(MAX_SPEED, max(MIN_SPEED, float(p["speed"])))
        elif command.type == "set_param":
            self._set_param(p["panel"], p["group"], p["name"], p["value"])
        elif command.type == "trigger_action":
            try:
                self._algos[p["panel"]].trigger(p["action"])
            except ValueError:
                log.warning("unknown action %r ignored", p["action"])
        elif command.type == "inject":
            targets = range(len(self._algos)) if p.get("panels", "all") == "all" else p["panels"]
            for i in targets:
                self._inject(i, p.get("count", 50))

    def _set_param(self, panel: int, group: str, name: str, value: Any) -> None:
        """Change a parameter and emit param_changed."""
        old = self._params[panel][group].get(name)
        if group == "algorithm":
            try:
                self._algos[panel].set_param(name, value)
            except KeyError:
                log.warning("unknown parameter %r ignored", name)
                return
            value = self._algos[panel]._params[name]
        self._params[panel][group][name] = value
        self._emit("param_changed", panel, name=name, old_value=old, new_value=value)

    def _inject(self, panel: int, count: int) -> None:
        """Inject into one panel and record it for recovery tracking."""
        if self._done[panel]:
            return
        algo = self._algos[panel]
        before = algo.current_snapshot()
        self._injection_count += 1
        algo.inject(self._problem.make_injection(self._seed + self._injection_count, count))
        after = algo.current_snapshot()
        self._injections[panel].append(
            {"index": after.evaluations, "before": before.cost, "after": after.cost, "recovery": None}
        )
        self._emit(
            "shapes_injected", panel, count=count, cost_before=before.cost, cost_after=after.cost
        )

    def _history_append(self, panel: int, snap: Snapshot) -> None:
        """Append a history point, thinning the older half when over the cap."""
        rate = snap.accepted_total / snap.proposed_total if snap.proposed_total else 0.0
        points = self._histories[panel]
        points.append(
            HistoryPoint(
                snap.evaluations, snap.elapsed_seconds, snap.similarity,
                snap.best_similarity, snap.cost, rate, dict(snap.extras),
            )
        )
        if len(points) > MAX_HISTORY_POINTS:
            half = len(points) // 2
            self._histories[panel] = points[:half:2] + points[half:]

    def _after_advance(self, panel: int, snap: Snapshot) -> None:
        """Record history, milestones and injection recovery after a tick."""
        self._history_append(panel, snap)
        for level in MILESTONE_LEVELS:
            if snap.best_similarity >= level and level not in self._milestones[panel]:
                self._milestones[panel][level] = MilestoneHit(snap.evaluations, snap.elapsed_seconds)
                self._emit("milestone_reached", panel, level=level)
        for record in self._injections[panel]:
            if record["recovery"] is None and snap.cost <= record["before"]:
                record["recovery"] = snap.evaluations - record["index"]

    def _update_leaderboard(self) -> None:
        """Rebuild the leaderboard and emit leader_changed when the leader changes."""
        snaps = [self._snap(i) for i in range(len(self._algos))]
        order = sorted(range(len(snaps)), key=lambda i: (-snaps[i].best_similarity, i))
        entries = []
        for rank, i in enumerate(order, start=1):
            change = self._ranks[i] - rank if i in self._ranks else 0
            entries.append(
                LeaderboardEntry(
                    rank, i, snaps[i].algorithm_id, snaps[i].best_similarity,
                    snaps[i].evaluations, change, self._done[i], dict(self._milestones[i]),
                )
            )
        self._ranks = {e.panel_index: e.rank for e in entries}
        self._entries = entries
        leader = order[0]
        if self._leader is not None and leader != self._leader:
            self._emit("leader_changed", None, old_panel=self._leader, new_panel=leader)
        self._leader = leader

    def _finish_panel(self, panel: int, reason: str) -> None:
        """Mark a panel finished once."""
        if not self._done[panel]:
            self._done[panel] = True
            self._emit("panel_finished", panel, reason=reason)

    def _end_run(self, reason: str) -> None:
        """Mark the whole run finished once."""
        self._status = "finished"
        self._emit("run_finished", None, reason=reason)

    # ---- scoring -----------------------------------------------------------

    def _outcome(self, panel: int) -> Outcome:
        """Build a panel's Outcome from its history and counters."""
        snap = self._snap(panel)
        points = self._histories[panel]
        area = sum(
            (a.best_similarity + b.best_similarity) / 2 * (b.evaluations - a.evaluations)
            for a, b in zip(points, points[1:])
        )
        seconds = self._elapsed[panel]
        gained = snap.best_similarity - points[0].best_similarity
        hits = self._milestones[panel]
        return Outcome(
            final_similarity=snap.best_similarity,
            total_evaluations=snap.evaluations,
            total_seconds=seconds,
            time_to_80=hits.get(80),
            time_to_90=hits.get(90),
            time_to_95=hits.get(95),
            auc_similarity=area / self._max,
            efficiency=gained / seconds if seconds > 0 else 0.0,
            acceptance_rate=snap.accepted_total / snap.proposed_total if snap.proposed_total else 0.0,
            worse_accepted_total=snap.worse_accepted_total,
            shape_count=self._problem.shape_count(snap.state),
            injections=tuple(
                InjectionRecord(r["index"], r["before"], r["after"], r["recovery"])
                for r in self._injections[panel]
            ),
        )

    def _build_record(self) -> ProvisionalRunRecord:
        """Assemble outcomes, winners, awards, events and history."""
        outcomes = [self._outcome(i) for i in range(len(self._algos))]
        winners = _winners(outcomes)
        return ProvisionalRunRecord(
            run_id=f"fake-{self._seed}",
            created_at=datetime.now(timezone.utc).isoformat(),
            contract_version="1.0",
            config={"seed": self._seed, "max_evaluations": self._max},
            results=[
                PanelResult(o, self._snap(i).state, self._snap(i).best_state)
                for i, o in enumerate(outcomes)
            ],
            winners=winners,
            awards=_awards(outcomes, winners),
            events=list(self._log),
            history={i: list(h) for i, h in enumerate(self._histories)},
        )


def _winners(outcomes: list[Outcome]) -> dict[str, int | None]:
    """Pick a winner per category by evaluations; ties go to the lowest index."""
    def reached(level: str) -> dict[int, float]:
        hits = {i: getattr(o, f"time_to_{level}") for i, o in enumerate(outcomes)}
        return {i: h.evaluations for i, h in hits.items() if h is not None}

    recovery = {
        i: min(r.recovery_evaluations for r in o.injections if r.recovery_evaluations is not None)
        for i, o in enumerate(outcomes)
        if any(r.recovery_evaluations is not None for r in o.injections)
    }
    final = {i: o.final_similarity for i, o in enumerate(outcomes)}
    auc = {i: o.auc_similarity for i, o in enumerate(outcomes)}
    efficiency = {i: o.efficiency for i, o in enumerate(outcomes)}
    winners = {
        "fastest_to_80": _best_panel(reached("80"), largest=False),
        "fastest_to_90": _best_panel(reached("90"), largest=False),
        "fastest_to_95": _best_panel(reached("95"), largest=False),
        "best_final": _best_panel(final, largest=True),
        "best_auc": _best_panel(auc, largest=True),
        "most_efficient": _best_panel(efficiency, largest=True),
        "fastest_recovery": _best_panel(recovery, largest=False),
    }
    assert tuple(winners) == WINNER_CATEGORIES
    return winners


def _awards(outcomes: list[Outcome], winners: dict[str, int | None]) -> dict[str, int]:
    """Derive awards from winners; a one-panel run only gets solo_artist."""
    if len(outcomes) == 1:
        return {"solo_artist": 0}
    risky = {i: float(o.worse_accepted_total) for i, o in enumerate(outcomes) if o.worse_accepted_total >= 1}
    candidates = {
        "risk_taker": _best_panel(risky, largest=True),
        "sprinter": winners["fastest_to_80"],
        "marathoner": winners["best_final"],
        "comeback_kid": winners["fastest_recovery"],
        "efficient_artist": winners["most_efficient"],
    }
    awards = {k: v for k, v in candidates.items() if v is not None}
    assert set(awards) <= set(AWARD_IDS)
    return awards
