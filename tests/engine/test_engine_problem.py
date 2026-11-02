"""Engine-specific tests: exact incremental cost, themes, shape limits, speed."""
import random
import time

import numpy as np
import pytest

from contracts.definitions import SHAPE_KINDS, ShapeConfig
from engine import create_problem, get_palette_swatches, list_shape_types

IMG = "tests/engine/data/m1_test_target.png"
THEMES = ["full_color", "black_white", "sepia", "neon", "pastel", "ocean", "sunset", "retro_8bit"]


@pytest.mark.parametrize("theme", THEMES)
def test_incremental_cost_equals_full_cost(theme):
    p = create_problem(IMG, ShapeConfig(), theme, 1)
    s, rng = p.initial_state(), random.Random(7)
    for _ in range(400):  # accept everything so every mutation path is exercised
        pr = p.propose(s, rng, 0.3)
        assert pr.cost == p.evaluate_full(pr.state)
        s = pr.state


def test_all_shape_kinds_render_and_stay_exact():
    for kind in SHAPE_KINDS:
        p = create_problem(IMG, ShapeConfig(mode="chosen", allowed_types=(kind,)), "full_color", 2)
        s, rng = p.initial_state(), random.Random(1)
        for _ in range(150):
            pr = p.propose(s, rng, 0.4)
            s = pr.state
        assert all(sh.kind == kind for sh in s.shapes)
        assert p.evaluate(s) == p.evaluate_full(s)


def test_shape_limit_respected_and_live_change():
    p = create_problem(IMG, ShapeConfig(shape_limit=20), "full_color", 1)
    s, rng = p.initial_state(), random.Random(4)
    for _ in range(400):
        s = p.propose(s, rng, 0.3).state
        assert p.shape_count(s) <= 20
    p.set_param("shape_limit", 40)
    for _ in range(400):
        s = p.propose(s, rng, 0.3).state
    assert 20 < p.shape_count(s) <= 40


def test_injection_ignores_shape_limit_and_ids_unique():
    p = create_problem(IMG, ShapeConfig(shape_limit=10), "full_color", 1)
    s = p.apply_injection(p.initial_state(), p.make_injection(1, 50))
    assert p.shape_count(s) == 50 and len({x.shape_id for x in s.shapes}) == 50
    assert p.evaluate(s) == p.evaluate_full(s)


@pytest.mark.parametrize("theme", ["neon", "retro_8bit", "pastel"])
def test_snap_themes_only_use_palette_colors(theme):
    p = create_problem(IMG, ShapeConfig(), theme, 1)
    allowed = set(get_palette_swatches(theme))
    s, rng = p.initial_state(), random.Random(2)
    for _ in range(200):
        s = p.propose(s, rng, 0.3).state
    assert {(x.red, x.green, x.blue) for x in s.shapes} <= allowed
    tgt = np.asarray(p.target_image(96)).reshape(-1, 3)
    assert {tuple(int(v) for v in c) for c in np.unique(tgt, axis=0)} <= allowed


def test_black_white_is_gray_and_opaque_themes_force_alpha_1():
    p = create_problem(IMG, ShapeConfig(), "black_white", 1)
    s, rng = p.initial_state(), random.Random(2)
    for _ in range(100):
        s = p.propose(s, rng, 0.3).state
    assert all(x.red == x.green == x.blue for x in s.shapes)
    q = create_problem(IMG, ShapeConfig(), "neon", 1)
    t = q.apply_injection(q.initial_state(), q.make_injection(3, 20))
    assert all(x.alpha == 1.0 for x in t.shapes)


def test_chosen_mode_uses_only_allowed_types():
    p = create_problem(IMG, ShapeConfig(mode="chosen", allowed_types=("circle", "triangle")), "full_color", 1)
    s, rng = p.initial_state(), random.Random(9)
    for _ in range(200):
        s = p.propose(s, rng, 0.3).state
    assert {x.kind for x in s.shapes} <= {"circle", "triangle"}


def test_background_is_average_target_colour():
    p = create_problem(IMG, ShapeConfig(), "full_color", 1)
    avg = np.asarray(p.target_image(96)).reshape(-1, 3).mean(axis=0)
    assert all(abs(a - b) <= 1 for a, b in zip(p.initial_state().background, avg))


def test_entry_points():
    assert [k for k, _ in list_shape_types()] == list(SHAPE_KINDS)
    for t in THEMES:
        assert get_palette_swatches(t)
    assert get_palette_swatches("no_such_theme")  # falls back to full_color


def test_proposal_speed_budget():
    """Contract budget is 1 ms per proposal; allow headroom for slow CI machines."""
    p = create_problem(IMG, ShapeConfig(), "full_color", 1)
    s, rng = p.initial_state(), random.Random(5)
    c = p.evaluate(s)
    for _ in range(300):  # grow the painting first so timing is realistic
        pr = p.propose(s, rng, 0.3)
        if pr.cost < c:
            s, c = pr.state, pr.cost
    t0 = time.perf_counter()
    for _ in range(500):
        p.propose(s, rng, 0.3)
    assert (time.perf_counter() - t0) / 500 < 0.003
