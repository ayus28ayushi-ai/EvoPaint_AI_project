"""Home screen: title, four buttons and a calm animated background."""
from __future__ import annotations

import math
import random

import pygame

from ui.compat import Navigation
from ui.theme import draw_text
from ui.widgets.basic import Button


class HomeScreen:
    screen_id = "home"

    def __init__(self, ctx):
        self.ctx = ctx
        self._nav = None
        self._time = 0.0
        rng = random.Random(7)                              # decorative drifting shapes (same every launch)
        self._blobs = [{"x": rng.random(), "y": rng.random(), "r": rng.randint(14, 60),
                        "speed": rng.uniform(0.01, 0.04), "phase": rng.random() * 6.28,
                        "kind": rng.choice(["circle", "triangle", "square"]), "color": rng.randrange(4)}
                       for _ in range(26)]
        cx, y, w, h = 640, 330, 340, 52
        go = lambda sid, payload=None: setattr(self, "_nav", Navigation(sid, payload))
        self.buttons = [
            Button((cx - w // 2, y, w, h), "New painting (upload an image)", lambda: go("upload"), "accent"),
            Button((cx - w // 2, y + 66, w, h), "Quick start with a sample", lambda: go("setup", {"target_path": ctx.sample_image()})),
            Button((cx - w // 2, y + 132, w, h), "Gallery of my paintings", lambda: go("gallery")),
            Button((cx - w // 2, y + 198, w, h), "Quit", ctx.quit),
        ]

    # --- screen interface ---------------------------------------------------------
    def on_enter(self, payload=None) -> None:
        self._nav = None
        self.ctx.audio.stop_music()

    def take_navigation(self):
        nav, self._nav = self._nav, None
        return nav

    def handle_events(self, events):
        for event in events:
            for button in self.buttons:
                if button.handle_event(event):
                    break
        return self.take_navigation()

    def update(self, dt: float) -> None:
        self._time += dt

    def draw(self, surface) -> None:
        skin, fonts = self.ctx.skin, self.ctx.fonts
        surface.fill(skin.background)
        for b in self._blobs:                               # slow floating shapes in the theme's colors
            x = (b["x"] + b["speed"] * self._time) % 1.1 * 1280
            y = (b["y"] * 800 + 24 * math.sin(self._time * 0.6 + b["phase"])) % 800
            color = skin.line_colors[b["color"]]
            faded = tuple(int(c * 0.22 + bg * 0.78) for c, bg in zip(color, skin.background))
            if b["kind"] == "circle":
                pygame.draw.circle(surface, faded, (int(x), int(y)), b["r"])
            elif b["kind"] == "square":
                pygame.draw.rect(surface, faded, (int(x), int(y), b["r"] * 2, b["r"] * 2), border_radius=skin.corner_radius)
            else:
                pygame.draw.polygon(surface, faded, [(x, y - b["r"]), (x + b["r"], y + b["r"]), (x - b["r"], y + b["r"])])
        draw_text(surface, fonts, "Evolving an Image", (640, 190), 60, skin.text, "center", bold=True)
        draw_text(surface, fonts, "Watch search algorithms learn to paint", (640, 250), 22, skin.text_dim, "center")
        for button in self.buttons:
            button.draw(surface, skin, fonts)
        if self.ctx.notice:                                 # e.g. 'saving failed'
            draw_text(surface, fonts, self.ctx.notice, (640, 600), 16, skin.bad, "center")
        fakes = getattr(self.ctx.backend, "fakes_in_use", [])
        if fakes:                                           # make stand-ins obvious during development
            draw_text(surface, fonts, "Dev mode - stand-ins in use: " + ", ".join(fakes), (640, 770), 13,
                      skin.text_dim, "center")
