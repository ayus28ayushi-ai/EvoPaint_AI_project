"""Runs the Session alone against the contract stubs: python -m session.demo"""

from __future__ import annotations

import logging
from types import SimpleNamespace

from contracts.definitions import commands
from contracts.stubs.fake_algorithm import FakeAlgorithm, ScriptedProblem
from session.session import Session, build_panel

log = logging.getLogger(__name__)


def main() -> None:
    """Run three fake panels, inject once, and print the standings and awards."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    steps = [0.2, 0.4, 0.8]
    panels = [
        build_panel(i, ScriptedProblem(), FakeAlgorithm, 1, 1000.0, {"step_scale": s}, {}, 20_000)
        for i, s in enumerate(steps)
    ]
    session = Session(panels, 1, SimpleNamespace(panels=[SimpleNamespace(algorithm_id="fake")] * 3))
    for tick in range(1, 301):
        if tick == 100:
            session.send(commands.inject())
        session.tick(0.1)
        for event in session.poll_events():
            log.info("t=%3d  %-18s panel=%s %s", tick, event.type, event.panel, dict(event.payload))
        if session.status() == "finished":
            break
        if tick % 100 == 0:
            for e in session.leaderboard():
                log.info("  #%d panel %d  %.1f%%  (%d evals)", e.rank, e.panel_index, e.best_similarity, e.evaluations)
    record = session.finish()
    log.info("winners: %s", record.winners)
    log.info("awards:  %s", record.awards)


if __name__ == "__main__":
    main()
