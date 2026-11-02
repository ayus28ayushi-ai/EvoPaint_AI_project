import numpy as np

from session.batch import average_curves, run_seeds, summarize
from tests.session.helpers import build_session


def make_session(seed):
    return build_session(panels=2, max_evaluations=3000, tick_limit=float("inf"), seed=seed)


class TestBatch:
    def test_runs_every_seed_to_the_end(self):
        records = run_seeds(make_session, [1, 2, 3])
        assert len(records) == 3
        assert all(r.events[-1].type == "run_finished" for r in records)

    def test_different_seeds_give_different_runs(self):
        a, b = run_seeds(make_session, [1, 2])
        assert a.results[0].outcome.final_similarity != b.results[0].outcome.final_similarity

    def test_average_curve_is_on_one_grid_and_never_falls(self):
        records = run_seeds(make_session, [1, 2, 3])
        grid, curves = average_curves(records, points=50)
        assert len(grid) == 50 and grid[-1] == 3000
        for curve in curves.values():
            assert len(curve) == 50
            assert np.all(np.diff(curve) >= -1e-9)
            assert 0 <= curve.min() and curve.max() <= 100

    def test_summary_has_one_row_per_panel(self):
        rows = summarize(run_seeds(make_session, [1, 2, 3]))
        assert [r["panel"] for r in rows] == [0, 1]
        assert all(0 <= r["final_mean"] <= 100 and r["final_std"] >= 0 for r in rows)
