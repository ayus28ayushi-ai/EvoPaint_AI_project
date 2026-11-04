"""Outcomes, winners and awards."""

from __future__ import annotations

from contracts.definitions import (
    WINNER_CATEGORIES,
    HistoryPoint,
    InjectionRecord,
    MilestoneHit,
    Outcome,
    Snapshot,
)
from session.record import Injection


def best_index(values: dict[int, float], largest: bool) -> int | None:
    """Return the winning panel index; ties go to the lowest index."""
    winner = None
    for i in sorted(values):
        if winner is None or (values[i] > values[winner] if largest else values[i] < values[winner]):
            winner = i
    return winner


def build_outcome(
    snap: Snapshot,
    points: list[HistoryPoint],
    hits: dict[int, MilestoneHit],
    injections: list[Injection],
    budget: int,
    shape_count: int,
) -> Outcome:
    """Summarise one panel at the end of the run."""
    area = sum(
        (a.best_similarity + b.best_similarity) / 2 * (b.evaluations - a.evaluations)
        for a, b in zip(points, points[1:])
    )
    seconds = snap.elapsed_seconds
    gained = snap.best_similarity - points[0].best_similarity
    return Outcome(
        final_similarity=snap.best_similarity,
        total_evaluations=snap.evaluations,
        total_seconds=seconds,
        time_to_80=hits.get(80),
        time_to_90=hits.get(90),
        time_to_95=hits.get(95),
        auc_similarity=area / budget,
        efficiency=gained / seconds if seconds > 0 else 0.0,
        acceptance_rate=snap.accepted_total / snap.proposed_total if snap.proposed_total else 0.0,
        worse_accepted_total=snap.worse_accepted_total,
        shape_count=shape_count,
        injections=tuple(
            InjectionRecord(i.evaluation_index, i.cost_before, i.cost_after, i.recovery_evaluations)
            for i in injections
        ),
    )


def pick_winners(outcomes: list[Outcome]) -> dict[str, int | None]:
    """Choose a winner per category. Speed to a level is measured in evaluations."""

    def reached(level: int) -> dict[int, float]:
        hits = {i: getattr(o, f"time_to_{level}") for i, o in enumerate(outcomes)}
        return {i: h.evaluations for i, h in hits.items() if h is not None}

    recoveries = {}
    for i, o in enumerate(outcomes):
        times = [r.recovery_evaluations for r in o.injections if r.recovery_evaluations is not None]
        if times:
            recoveries[i] = min(times)
    winners = {
        "fastest_to_80": best_index(reached(80), False),
        "fastest_to_90": best_index(reached(90), False),
        "fastest_to_95": best_index(reached(95), False),
        "best_final": best_index({i: o.final_similarity for i, o in enumerate(outcomes)}, True),
        "best_auc": best_index({i: o.auc_similarity for i, o in enumerate(outcomes)}, True),
        "most_efficient": best_index({i: o.efficiency for i, o in enumerate(outcomes)}, True),
        "fastest_recovery": best_index(recoveries, False),
    }
    return {name: winners[name] for name in WINNER_CATEGORIES}


def pick_awards(outcomes: list[Outcome], winners: dict[str, int | None]) -> dict[str, int]:
    """Derive awards; a one-panel run only gets solo_artist."""
    if len(outcomes) == 1:
        return {"solo_artist": 0}
    risky = {i: float(o.worse_accepted_total) for i, o in enumerate(outcomes) if o.worse_accepted_total}
    awards = {
        "risk_taker": best_index(risky, True),
        "sprinter": winners["fastest_to_80"],
        "marathoner": winners["best_final"],
        "comeback_kid": winners["fastest_recovery"],
        "efficient_artist": winners["most_efficient"],
    }
    return {name: panel for name, panel in awards.items() if panel is not None}
