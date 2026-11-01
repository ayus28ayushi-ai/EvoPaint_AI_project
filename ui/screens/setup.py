"""Setup screen: choose theme, shapes, number of panels and each panel's algorithm and
parameters, then press Start. Builds the RunConfig (Contract 5.4) and hands it to `run`.

Parameter widgets are generated from each algorithm's parameter specs, so any new
algorithm shows up here with its own sliders automatically.
"""
from __future__ import annotations

import math
import os
import time

import pygame

from ui import layout
from ui.compat import (BUDGET_RANGE, MAX_PANELS, SPEED_RANGE, THEMES, Navigation, PanelConfig,
                       RunConfig, ShapeConfig, get, parse_algorithm_info)
from ui.theme import draw_panel, draw_text, draw_tooltip, fit_text, load_square_surface
from ui.widgets.basic import Button, Dropdown, Segmented, Slider, Toggle

PREFERRED_ORDER = ["hill_climbing", "simulated_annealing", "stochastic_hc", "iterative_hc"]


class SetupScreen:
    screen_id = "setup"

    def __init__(self, ctx):
        self.ctx = ctx
        self._nav = None
        # --- the user's choices (they persist between visits to this screen) ---
        self.target_path = ""
        self.theme_id = "full_color"
        self.mode = "random"                       # "random" or "chosen"
        self.allowed: set = set()                  # shape ids ticked in "chosen" mode
        self.shape_limit = 300
        self.informed = True
        self.seed = int(time.time()) % 100000
        self.budget = 200000
        self.count = 2
        self.panels: list = []                     # one dict per possible panel: algo, speed, params
        self.error = ""
        # --- widgets, rebuilt whenever the structure changes ---
        self.algos: list = []
        self.shape_types: list = []
        self.labels: list = []
        self.left: list = []
        self.card_widgets: list = []
        self.cards: list = []
        self.card_texts: list = []
        self._dirty = True

    # ------------------------------------------------------------------ screen interface
    def on_enter(self, payload=None) -> None:
        backend = self.ctx.backend
        self._nav, self.error = None, ""
        self.algos = [parse_algorithm_info(a) for a in backend.list_algorithms()]
        self.shape_types = [(get(s, "id", s[0] if isinstance(s, (tuple, list)) else s),
                             get(s, "display_name", s[1] if isinstance(s, (tuple, list)) else str(s)))
                            for s in backend.list_shape_types()]
        if not self.allowed:
            self.allowed = {sid for sid, _ in self.shape_types}      # start with everything ticked
        path = get(payload, "target_path") if payload else None
        if path:
            self.target_path = path
        elif not self.target_path:
            self.target_path = self.ctx.sample_image()
        self.theme_id = self.ctx.theme_id
        self._ensure_panels()
        self._dirty = True

    def take_navigation(self):
        nav, self._nav = self._nav, None
        return nav

    # ------------------------------------------------------------------ state helpers
    def _go(self, screen_id, payload=None) -> None:
        self._nav = Navigation(screen_id, payload)

    def _algo(self, algo_id: str):
        return next((a for a in self.algos if a.id == algo_id), self.algos[0])

    def _defaults_for(self, algo_id: str) -> dict:
        """Starting values of an algorithm's own parameters (the 'algorithm' group)."""
        return {get(s, "name"): get(s, "default") for s in self._algo(algo_id).param_specs
                if get(s, "group", "algorithm") == "algorithm"}

    def _ensure_panels(self) -> None:
        ids = [a.id for a in self.algos]
        order = [i for i in PREFERRED_ORDER if i in ids] + [i for i in ids if i not in PREFERRED_ORDER]
        while len(self.panels) < MAX_PANELS and order:
            algo_id = order[len(self.panels) % len(order)]
            self.panels.append({"algo": algo_id, "speed": 1000.0, "params": self._defaults_for(algo_id)})

    # --- callbacks (structural changes only flag a rebuild; we never rebuild mid-event) ---
    def _on_theme(self, value) -> None:
        self.theme_id = value
        self.ctx.set_theme(value)                  # the whole screen re-skins immediately

    def _on_mode(self, value) -> None:
        self.mode, self._dirty = value, True

    def _toggle_shape(self, shape_id, on) -> None:
        (self.allowed.add if on else self.allowed.discard)(shape_id)

    def _on_count(self, value) -> None:
        self.count, self._dirty = value, True

    def _on_algo(self, index, algo_id) -> None:
        self.panels[index]["algo"] = algo_id
        self.panels[index]["params"] = self._defaults_for(algo_id)
        self._dirty = True

    def _new_seed(self) -> None:
        self.seed = int(time.time() * 1000) % 100000

    # ------------------------------------------------------------------ building widgets
    def _build(self) -> None:
        self._dirty = False
        self._build_left()
        self._build_cards()

    def _build_left(self) -> None:
        region = pygame.Rect(layout.setup_regions()["left"])
        x, w, y = region.x + 14, region.width - 28, region.y + 12
        self.labels, self.left = [], []

        def heading(text):
            nonlocal y
            self.labels.append((text, (x, y), 16, True, "text"))
            y += 26

        heading("1. Target image")
        self.thumb = pygame.Rect(x, y, 112, 112)
        self.name_pos = (x + 124, y + 6)
        self.left.append(Button((x + 124, y + 72, w - 124, 38), "Change image", lambda: self._go("upload"),
                                "normal", "Pick or drop another image"))
        y += 124

        heading("2. Theme")
        self.left.append(Dropdown((x, y, w, 32), list(THEMES), self.theme_id, self._on_theme,
                                  "Changes the look, the sound and the colors the AI may use"))
        y += 38
        self.swatch_pos = (x, y)
        y += 28

        heading("3. Shapes")
        self.left.append(Segmented((x, y, w, 32), [("random", "Random mix"), ("chosen", "I choose")],
                                   self.mode, self._on_mode, "Random mix uses every shape type"))
        y += 40
        if self.mode == "chosen":
            for i, (shape_id, label) in enumerate(self.shape_types):
                col, row = i % 2, i // 2
                self.left.append(Toggle((x + col * (w // 2), y + row * 26, w // 2 - 4, 24), label,
                                        shape_id in self.allowed,
                                        lambda on, s=shape_id: self._toggle_shape(s, on)))
            y += 26 * math.ceil(len(self.shape_types) / 2) + 6
        else:
            self.labels.append(("Every shape type may be used.", (x, y), 14, False, "text_dim"))
            y += 24
        self.left.append(Slider((x, y, w, 38), "Shape limit", 10, 1000, self.shape_limit,
                                lambda v: setattr(self, "shape_limit", int(v)), 10, "linear", True,
                                "Maximum number of shapes in a painting"))
        y += 40
        self.left.append(Toggle((x, y, w, 26), "Informed colors (smarter new shapes)", self.informed,
                                lambda on: setattr(self, "informed", on),
                                "New shapes copy the target's color at their position"))
        y += 34

        heading("4. Run")
        self.seed_pos = (x, y + 6)
        self.left.append(Button((x + w - 120, y, 120, 30), "New seed", self._new_seed, "normal",
                                "Same seed = same random choices, so runs are comparable"))
        y += 38
        self.left.append(Slider((x, y, w, 38), "Evaluation budget per panel", BUDGET_RANGE[0], BUDGET_RANGE[1],
                                self.budget, lambda v: setattr(self, "budget", int(v)), 0, "log", True,
                                "How long each painter works before the run ends"))
        y += 42

        heading("5. Panels side by side")
        self.left.append(Segmented((x, y, w, 32), [(n, str(n)) for n in range(1, MAX_PANELS + 1)],
                                   self.count, self._on_count, "Run 1 to 4 painters at once"))

        by = region.bottom - 56
        self.error_pos = (x, by - 26)
        self.left.append(Button((x, by, 100, 42), "Back", lambda: self._go("home")))
        self.left.append(Button((x + 112, by, w - 112, 42), "Start painting", self._start, "accent"))

    def _build_cards(self) -> None:
        region = layout.setup_regions()["cards"]
        self.cards = [pygame.Rect(c) for c in layout.panel_grid(self.count, region, gap=12)]
        self.card_widgets, self.card_texts = [], []
        for i, card in enumerate(self.cards):
            panel = self.panels[i]
            algo = self._algo(panel["algo"])
            x, w, y = card.x + 14, card.width - 28, card.y + 40
            self.card_widgets.append(Dropdown((x, y, w, 32), [(a.id, a.display_name) for a in self.algos],
                                              panel["algo"], lambda v, i=i: self._on_algo(i, v),
                                              "Which algorithm paints in this panel"))
            y += 38
            self.card_texts.append((algo.description, (x, y), 13))
            y += 24
            self.card_widgets.append(Slider(
                (x, y, w, 38), "Speed (evaluations / second)", SPEED_RANGE[0], SPEED_RANGE[1], panel["speed"],
                lambda v, i=i: self.panels[i].__setitem__("speed", v), 0, "log", False,
                "How fast this painter works"))
            y += 40
            for spec in algo.param_specs:
                if get(spec, "group", "algorithm") != "algorithm":
                    continue                                     # painting params are set on the left
                name, kind = get(spec, "name"), get(spec, "kind", "float")
                value = panel["params"].get(name, get(spec, "default"))
                setter = lambda v, i=i, n=name: self.panels[i]["params"].__setitem__(n, v)
                tip = get(spec, "help_text", "")
                if kind == "bool":
                    self.card_widgets.append(Toggle((x, y + 6, w, 24), get(spec, "label", name), bool(value), setter, tip))
                elif kind == "choice":
                    options = [(o, str(o)) for o in (get(spec, "options", []) or [])]
                    self.card_widgets.append(Dropdown((x, y + 4, w, 30), options, value, setter, tip))
                else:
                    self.card_widgets.append(Slider(
                        (x, y, w, 38), get(spec, "label", name), get(spec, "minimum", 0), get(spec, "maximum", 1),
                        value, setter, get(spec, "step", 0), get(spec, "scale", "linear"), kind == "int", tip))
                y += 40

    # ------------------------------------------------------------------ starting a run
    def _start(self) -> None:
        if not self.target_path or not os.path.exists(self.target_path):
            self.error = "Pick a target image first."
            return
        if self.mode == "chosen" and not self.allowed:
            self.error = "Tick at least one shape type."
            return
        shape_config = ShapeConfig(
            mode=self.mode, allowed_types=sorted(self.allowed) if self.mode == "chosen" else [],
            shape_limit=self.shape_limit)
        panels = [PanelConfig(algorithm_id=p["algo"], speed=float(p["speed"]),
                              algorithm_params=dict(p["params"]),
                              painting_params={"informed_colors": self.informed, "shape_limit": self.shape_limit})
                  for p in self.panels[:self.count]]
        config = RunConfig(target_path=self.target_path, theme_id=self.theme_id, shape_config=shape_config,
                           seed=self.seed, max_evaluations=self.budget, panels=panels)
        self.error = ""
        self._go("run", {"run_config": config})

    # ------------------------------------------------------------------ events and drawing
    def _all_widgets(self) -> list:
        return self.left + self.card_widgets

    def handle_events(self, events):
        for event in events:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self._go("home")
                elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    self._start()
                continue
            widgets = self._all_widgets()
            open_list = next((w for w in widgets if isinstance(w, Dropdown) and w.is_open), None)
            if open_list is not None:                            # an open dropdown gets the click first
                open_list.handle_event(event)
                continue
            for widget in reversed(widgets):
                if widget.handle_event(event):
                    break
        if self._dirty:                                          # rebuild AFTER the event loop (safe)
            self._build()
        return self.take_navigation()

    def update(self, dt: float) -> None:
        if self._dirty:
            self._build()

    def draw(self, surface) -> None:
        if self._dirty:
            self._build()
        skin, fonts = self.ctx.skin, self.ctx.fonts
        surface.fill(skin.background)
        draw_panel(surface, skin, pygame.Rect(layout.setup_regions()["left"]))
        for text, pos, size, bold, color in self.labels:
            draw_text(surface, fonts, text, pos, size, getattr(skin, color), bold=bold)

        # target thumbnail and file name
        image = load_square_surface(self.target_path, self.thumb.width) if self.target_path else None
        if image is not None:
            surface.blit(image, self.thumb)
        else:
            pygame.draw.rect(surface, skin.button, self.thumb, border_radius=skin.corner_radius)
            draw_text(surface, fonts, "No image", self.thumb.center, 14, skin.text_dim, "center")
        draw_text(surface, fonts, fit_text(fonts, os.path.basename(self.target_path) or "(none)", 14, 180),
                  self.name_pos, 14, skin.text_dim)

        # palette swatches describing the chosen theme
        sx, sy = self.swatch_pos
        for color in self.ctx.backend.get_palette_swatches(self.theme_id)[:12]:
            pygame.draw.rect(surface, tuple(color), (sx, sy, 22, 22), border_radius=4)
            sx += 26
        draw_text(surface, fonts, f"Seed: {self.seed}", self.seed_pos, 15, skin.text)

        for widget in self.left:
            widget.draw(surface, skin, fonts)

        # one card per panel
        for i, card in enumerate(self.cards):
            draw_panel(surface, skin, card)
            pygame.draw.rect(surface, skin.line_colors[i % len(skin.line_colors)], (card.x + 14, card.y + 12, 6, 22),
                             border_radius=3)
            draw_text(surface, fonts, f"Panel {i + 1}", (card.x + 28, card.y + 10), 18, skin.text, bold=True)
        for text, pos, size in self.card_texts:
            draw_text(surface, fonts, fit_text(fonts, text, size, self.cards[0].width - 40), pos, size, skin.text_dim)
        for widget in self.card_widgets:
            widget.draw(surface, skin, fonts)
        for widget in self._all_widgets():                      # open dropdown lists float on top
            if isinstance(widget, Dropdown):
                widget.draw_popup(surface, skin, fonts)

        if self.error:
            draw_text(surface, fonts, self.error, self.error_pos, 15, skin.bad, bold=True)
        mouse = pygame.mouse.get_pos()
        tip = next((w.tooltip for w in self._all_widgets() if w.tooltip and w.rect.collidepoint(mouse)), "")
        draw_tooltip(surface, skin, fonts, tip, mouse)
