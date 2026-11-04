"""Tests for the UI's pure modules (layout, chart math, slider math, compat). No Pygame needed."""
import math

from ui import chart_math as cm
from ui import layout
from ui.compat import (Command, make_command, parse_algorithm_info, parse_navigation,
                       parse_panel_info, load_backend, RunConfig, PanelConfig, get)
from ui.widgets import slider_math as sm


# ---------------------------------------------------------------- layout
def test_panel_grid_fits_and_never_overlaps():
    region = layout.run_regions()["panels"]
    rx, ry, rw, rh = region
    for n in (1, 2, 3, 4):
        cells = layout.panel_grid(n, region)
        assert len(cells) == n
        for c in cells:
            assert c[0] >= rx and c[1] >= ry and c[0] + c[2] <= rx + rw and c[1] + c[3] <= ry + rh
        for i in range(n):
            for j in range(i + 1, n):
                assert not layout.rects_overlap(cells[i], cells[j])


def test_run_regions_do_not_overlap_and_fit_window():
    regions = layout.run_regions()
    names = [k for k in regions if k != "top_bar"]
    w, h = layout.WINDOW_SIZE
    for k in names:
        x, y, rw, rh = regions[k]
        assert x >= 0 and y >= 0 and x + rw <= w and y + rh <= h, k
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            assert not layout.rects_overlap(regions[a], regions[b]), (a, b)


def test_panel_inner_is_square_inside_cell():
    cell = (0, 0, 420, 400)
    header, image, footer = layout.panel_inner(cell)
    assert image[2] == image[3]
    assert image[1] >= header[1] + header[3]
    assert footer[1] >= image[1] + image[3] - 1


def test_setup_regions_fit():
    regions = layout.setup_regions()
    assert not layout.rects_overlap(regions["left"], regions["cards"])


# ---------------------------------------------------------------- chart math
def test_thin_keeps_last_and_limit():
    pts = list(range(1000))
    out = cm.thin(pts, 100)
    assert len(out) == 100 and out[-1] == 999 and out[0] == 0
    assert cm.thin([1, 2, 3], 100) == [1, 2, 3]


def test_y_range_never_collapses():
    lo, hi = cm.y_range([50.0, 50.0], "similarity")
    assert hi - lo >= 8
    assert 0 <= lo <= hi <= 100


def test_ticker_change_uses_time_window():
    pts = [{"elapsed_seconds": t, "similarity": 10 + t} for t in range(0, 21)]
    value, delta = cm.ticker_change(pts, "similarity", window_seconds=5)
    assert value == 30 and math.isclose(delta, 5)


def test_to_pixel_corners():
    rect = (100, 50, 200, 100)
    assert cm.to_pixel(0, 0, rect, (0, 10), (0, 100)) == (100, 150)     # bottom-left
    assert cm.to_pixel(10, 100, rect, (0, 10), (0, 100)) == (300, 50)   # top-right


def test_nice_ticks_and_format():
    assert cm.nice_ticks(0, 100, 4)[0] == 0
    assert cm.format_count(1500) == "1.5k" and cm.format_count(2_000_000) == "2.0M" and cm.format_count(7) == "7"
    assert cm.use_log([1, 1000], "error") and not cm.use_log([1, 5], "error")


# ---------------------------------------------------------------- slider math
def test_slider_round_trip_linear_log_and_rate():
    for lo, hi, scale in [(0, 10, "linear"), (0.01, 1.0, "log"), (0.9990, 0.99999, "log"), (50, 10000, "log")]:
        for t in (0.0, 0.25, 0.5, 1.0):
            value = sm.from_unit(t, lo, hi, scale)
            assert lo <= value <= hi
            assert math.isclose(sm.to_unit(value, lo, hi, scale), t, abs_tol=1e-6), (lo, hi, scale, t)


def test_slider_int_and_step_snapping():
    assert sm.from_unit(0.5, 2, 20, "linear", step=1, is_int=True) == 11
    assert sm.from_unit(0.33, 0, 1, "linear", step=0.1) == 0.3
    assert sm.format_value(0.9995) == "0.99950" and sm.format_value(5, is_int=True) == "5"


# ---------------------------------------------------------------- compat
def test_get_works_for_objects_and_dicts():
    class Obj:
        a = 1
    assert get(Obj(), "a") == 1 and get({"a": 2}, "a") == 2 and get(None, "a", 9) == 9


def test_commands_expose_payload_as_attributes():
    cmd = make_command("set_param", panel=1, group="algorithm", name="cooling_rate", value=0.9999)
    assert isinstance(cmd, Command) and cmd.type == "set_param"
    assert cmd.panel == 1 and cmd.name == "cooling_rate"


def test_parse_navigation_variants():
    assert parse_navigation(None) is None
    assert parse_navigation("home") == ("home", None)
    assert parse_navigation(("setup", {"target_path": "x"})) == ("setup", {"target_path": "x"})
    assert parse_navigation({"screen_id": "run", "payload": 5}) == ("run", 5)


def test_parse_panel_info_accepts_alternative_key_names():
    info = parse_panel_info({"algorithm": "x", "params": {"a": 1}, "specs": [1], "actions": [2],
                             "speed": 500, "is_throttled": True})
    assert info.algorithm_id == "x" and info.params == {"a": 1} and info.throttled and info.speed == 500.0


def test_parse_algorithm_info_alternative_names():
    info = parse_algorithm_info({"id": "a", "name": "Alpha", "specs": [1]})
    assert info.display_name == "Alpha" and info.param_specs == [1]


# ---------------------------------------------------------------- the fake session end to end
def _config(n=3):
    names = ["hill_climbing", "simulated_annealing", "iterative_hc", "stochastic_hc"]
    panels = [PanelConfig(algorithm_id=names[i], speed=5000) for i in range(n)]
    return RunConfig(target_path="x.png", seed=3, max_evaluations=20000, panels=panels)


def test_fake_session_runs_and_obeys_commands():
    backend = load_backend(use_fakes=True)
    session = backend.create_session(_config(3))
    for _ in range(60):
        session.tick(1 / 30)
    assert session.snapshot(0).evaluations > 0
    assert len(session.history(0, 100)) > 0
    board = session.leaderboard()
    assert [r["rank"] for r in board] == [1, 2, 3]
    session.send(make_command("inject", count=50, panels="all"))
    kinds = {e["type"] for e in session.poll_events()}
    assert "shapes_injected" in kinds
    session.send(make_command("pause"))
    before = session.snapshot(0).evaluations
    session.tick(1.0)
    assert session.snapshot(0).evaluations == before            # paused means no progress
    session.send(make_command("resume"))
    session.send(make_command("finish"))
    assert session.status() == "finished"
    assert session.finish().run_id
    img = session.render(0, 200)
    assert img.size == (200, 200)


def test_fake_session_runs_to_completion_and_emits_events():
    session = load_backend(use_fakes=True).create_session(_config(2))
    seen = set()
    for _ in range(400):
        session.tick(0.1)
        seen |= {e["type"] for e in session.poll_events()}
    assert session.status() == "finished"
    assert {"milestone_reached", "panel_finished", "run_finished"} <= seen
    info = parse_panel_info(session.panel_info(1))
    assert info.algorithm_id == "simulated_annealing" and any(get(s, "name") == "cooling_rate" for s in info.param_specs)
