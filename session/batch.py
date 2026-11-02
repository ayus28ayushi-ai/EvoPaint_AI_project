"""Headless runs and reports. The only place Matplotlib is allowed."""

from __future__ import annotations

import argparse
import csv
import logging
from collections.abc import Callable, Iterable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np

from contracts.definitions import ShapeConfig
from session.record import RunRecord
from session.registry import find_algorithms
from session.session import Session, create_session

log = logging.getLogger(__name__)

CSV_COLUMNS = (
    "evaluations", "elapsed_seconds", "similarity", "best_similarity", "cost", "acceptance_rate",
)  # fmt: skip


def run_to_end(session: Session, seconds: float = 1.0, max_ticks: int = 1_000_000) -> RunRecord:
    """Tick until every panel spends its budget, then return the record."""
    ticks = 0
    while session.status() != "finished" and ticks < max_ticks:
        session.tick(seconds)
        ticks += 1
    return session.finish()


def write_history_csv(record: RunRecord, out_dir: Path) -> list[Path]:
    """Write history_<panel>.csv for every panel."""
    paths = []
    for panel, points in record.history.items():
        path = out_dir / f"history_{panel}.csv"
        with path.open("w", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(CSV_COLUMNS)
            writer.writerows([getattr(p, c) for c in CSV_COLUMNS] for p in points)
        paths.append(path)
    return paths


def run_seeds(make_session: Callable[[int], Session], seeds: Iterable[int]) -> list[RunRecord]:
    """Run one full session per seed and return the records."""
    return [run_to_end(make_session(seed)) for seed in seeds]


def average_curves(
    records: list[RunRecord], points: int = 200
) -> tuple[np.ndarray, dict[int, np.ndarray]]:
    """Average each panel's best-similarity curve over seeds on a shared evaluation grid."""
    grid = np.linspace(0, records[0].config["max_evaluations"], points)
    curves = {}
    for panel in records[0].history:
        runs = [
            np.interp(
                grid,
                [p.evaluations for p in r.history[panel]],
                [p.best_similarity for p in r.history[panel]],
            )
            for r in records
        ]
        curves[panel] = np.mean(runs, axis=0)
    return grid, curves


def summarize(records: list[RunRecord]) -> list[dict[str, float]]:
    """Return one row of seed-averaged results per panel."""
    rows = []
    for panel in range(len(records[0].results)):
        outcomes = [r.results[panel].outcome for r in records]
        finals = np.array([o.final_similarity for o in outcomes])
        to_90 = [o.time_to_90.evaluations for o in outcomes if o.time_to_90]
        rows.append(
            {
                "panel": panel,
                "runs": len(outcomes),
                "final_mean": float(finals.mean()),
                "final_std": float(finals.std()),
                "auc_mean": float(np.mean([o.auc_similarity for o in outcomes])),
                "efficiency_mean": float(np.mean([o.efficiency for o in outcomes])),
                "reached_90": len(to_90),
                "evals_to_90_mean": float(np.mean(to_90)) if to_90 else float("nan"),
            }
        )
    return rows


def write_summary_csv(rows: list[dict[str, float]], out_dir: Path) -> Path:
    """Write summary.csv with one row per panel."""
    path = out_dir / "summary.csv"
    with path.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return path


def write_chart(
    grid: np.ndarray, curves: dict[int, np.ndarray], labels: list[str], runs: int, out_dir: Path
) -> Path:
    """Plot the seed-averaged best similarity against evaluations."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(7, 4))
    for panel, curve in curves.items():
        ax.plot(grid, curve, label=f"{panel}: {labels[panel]}")
    ax.set_xlabel("evaluations")
    ax.set_ylabel("best similarity (%)")
    ax.set_title(f"mean of {runs} run(s)")
    ax.legend()
    path = out_dir / "similarity.png"
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return path


def make_config(args: argparse.Namespace, seed: int) -> Any:
    """Build a RunConfig-shaped object from command-line flags."""
    ids = args.algorithms.split(",") if args.algorithms else sorted(find_algorithms())
    panels = [
        SimpleNamespace(algorithm_id=i, speed=10000.0, algorithm_params={}, painting_params={})
        for i in ids
    ]
    shape_config = ShapeConfig()
    return SimpleNamespace(
        target_path=args.target,
        theme_id=args.theme,
        shape_config=shape_config,
        seed=seed,
        max_evaluations=args.budget,
        panels=panels,
    )


def main(argv: list[str] | None = None) -> None:
    """Run all (or chosen) algorithms over several seeds and write averaged results."""
    parser = argparse.ArgumentParser(description=main.__doc__)
    parser.add_argument("--target", required=True)
    parser.add_argument("--algorithms", help="comma-separated ids; default is all")
    parser.add_argument("--seed", type=int, default=1, help="first seed")
    parser.add_argument("--runs", type=int, default=1, help="number of seeds to average")
    parser.add_argument("--budget", type=int, default=50_000)
    parser.add_argument("--theme", default="full_color")
    parser.add_argument("--out", default="out/batch")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    def make_session(seed: int) -> Session:
        return create_session(make_config(args, seed), tick_limit=float("inf"))

    records = run_seeds(make_session, range(args.seed, args.seed + args.runs))
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    write_history_csv(records[0], out_dir)
    labels = [p["algorithm_id"] for p in records[0].config["panels"]]
    write_chart(*average_curves(records), labels, args.runs, out_dir)
    rows = summarize(records)
    write_summary_csv(rows, out_dir)
    for row in rows:
        log.info(
            "panel %d %-16s final %.2f%% +/- %.2f  reached 90%%: %d/%d",
            row["panel"], labels[row["panel"]], row["final_mean"], row["final_std"],
            row["reached_90"], row["runs"],
        )  # fmt: skip
    log.info("report written to %s", out_dir)


if __name__ == "__main__":
    main()
