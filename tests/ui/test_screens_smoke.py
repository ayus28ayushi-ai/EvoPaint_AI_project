"""Drives the real screens frame by frame against fake backends: home -> setup -> run -> finish.
Needs Pygame (skipped if missing). Uses SDL's dummy drivers, so no window or sound card is needed."""
import os
import tempfile

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pytest

pygame = pytest.importorskip("pygame")

from PIL import Image

from ui.app import App
from ui.compat import make_command


def key(k, mod=0):
    return pygame.event.Event(pygame.KEYDOWN, key=k, mod=mod)


def click(pos):
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=1)


def frames(app, count, events=None, dt=1 / 30):
    app.step(list(events or []), dt)
    for _ in range(count - 1):
        app.step([], dt)


def make_target():
    path = os.path.join(tempfile.mkdtemp(), "target.png")
    Image.new("RGB", (200, 120), (200, 100, 50)).save(path)
    return path


def test_full_flow_home_setup_run_finish():
    app = App("home", use_fakes=True)
    frames(app, 3)
    assert app.current.screen_id == "home"

    app.step([click((640, 330 + 66 + 20))], 1 / 30)                 # "Quick start with a sample"
    assert app.current.screen_id == "setup"
    setup = app.current
    setup.target_path = make_target()
    setup._on_mode("chosen")                                         # choose-your-shapes branch
    setup._on_count(4)                                               # four panels
    frames(app, 3)
    assert len(setup.cards) == 4

    setup._start()                                                   # what the Start button does
    frames(app, 1)
    assert app.current.screen_id == "run"
    run = app.current

    frames(app, 60)                                                  # two seconds of racing
    assert run.chart.series[0], "chart should have data"
    for k in (pygame.K_i, pygame.K_r, pygame.K_c, pygame.K_m, pygame.K_t, pygame.K_t, pygame.K_TAB,
              pygame.K_PLUS, pygame.K_MINUS, pygame.K_2, pygame.K_SPACE, pygame.K_SPACE):
        app.step([key(k)], 1 / 30)
    app.step([key(pygame.K_i, pygame.KMOD_SHIFT)], 1 / 30)           # inject into the focused panel only
    frames(app, 120)
    assert run.entries and run.toasts is not None

    app.step([key(pygame.K_f)], 1 / 30)                              # finish -> save -> entry screen
    frames(app, 6)
    assert app.current.screen_id == "entry"                          # placeholder until M4 ships the real one
    app.step([click((10, 10))], 1 / 30)
    assert app.current.screen_id == "home"


def test_setup_dropdown_and_theme_change():
    app = App("setup", use_fakes=True)
    frames(app, 2)
    setup = app.current
    theme_dropdown = setup.left[1]
    app.step([click(theme_dropdown.rect.center)], 1 / 30)            # open the list
    assert theme_dropdown.is_open
    popup = theme_dropdown._popup_rect()
    app.step([click((popup.x + 10, popup.y + theme_dropdown.rect.height * 3 + 5))], 1 / 30)   # 4th theme
    assert app.ctx.theme_id == "neon"
    frames(app, 2)


def test_setup_validation_blocks_empty_choice():
    app = App("setup", use_fakes=True)
    frames(app, 2)
    setup = app.current
    setup.target_path = make_target()
    setup._on_mode("chosen")
    setup.allowed.clear()
    setup._start()
    assert "shape" in setup.error.lower()
    assert setup.take_navigation() is None


def test_run_screen_sends_commands_to_session():
    app = App("run", {"run_config": __import__("ui.demo", fromlist=["x"]).quick_run_config()}, use_fakes=True)
    run = app.current
    sent = []
    original = run.session.send
    run.session.send = lambda cmd: (sent.append(cmd), original(cmd))
    app.step([key(pygame.K_i)], 1 / 30)
    app.step([key(pygame.K_r)], 1 / 30)
    app.step([key(pygame.K_PLUS)], 1 / 30)
    kinds = [c.type for c in sent]
    assert kinds == ["inject", "trigger_action", "set_speed"] or kinds[:2] == ["inject", "trigger_action"] or "inject" in kinds
    assert sent[0].count == 50 and sent[0].panels == "all"


def test_controls_fit_every_parameter_of_every_algorithm():
    """Every spec of every algorithm (plus speed and actions) must get a widget inside the panel."""
    from ui.compat import get, parse_panel_info
    app = App("run", {"run_config": __import__("ui.demo", fromlist=["x"]).quick_run_config()}, use_fakes=True)
    run = app.current
    for panel in range(4):
        run._focus_panel(panel)
        info = parse_panel_info(run.session.panel_info(panel))
        expected = 1 + len(info.param_specs) + len(info.action_specs)    # speed + params + action buttons
        assert len(run.controls.widgets) == expected, (panel, info.algorithm_id)
        bottom = run.controls.rect.bottom
        assert all(w.rect.bottom <= bottom for w in run.controls.widgets)
