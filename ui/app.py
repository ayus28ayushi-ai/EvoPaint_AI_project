"""The app shell: opens the window, finds every screen, moves between them, runs the loop.

Screens are DISCOVERED, not registered: any class with a `screen_id` inside ui/screens/ or
media/screens/ is picked up automatically (Contract 3). Navigation requests returned by a
screen are (screen_id, payload) pairs (Contract 6.4).
"""
from __future__ import annotations

import importlib
import inspect
import logging
import os
import pkgutil

import pygame

from ui.compat import Backend, get, load_backend, parse_navigation
from ui.layout import WINDOW_SIZE
from ui.theme import Fonts, Skin, draw_text

log = logging.getLogger("ui.app")
SCREEN_PACKAGES = ("ui.screens", "media.screens")          # where screens live (M3 and M4)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class AppContext:
    """Shared things every screen may use. Passed to screens that ask for it."""

    def __init__(self, backend: Backend, surface: pygame.Surface):
        self.backend = backend
        self.surface = surface
        self.fonts = Fonts()
        self.theme_id = "full_color"
        self.skin = Skin.load(self.theme_id)
        self.audio = backend.get_audio()                   # media.get_audio() (Contract 6.5)
        self.effects = backend.get_effects()               # media.get_effects() (Contract 6.6)
        self.notice = ""                                   # one-line message shown on the home screen
        self.go = lambda screen_id, payload=None: None     # replaced by App
        self.quit = lambda: None                           # replaced by App

    def set_theme(self, theme_id: str) -> None:
        """Switch the look AND the sound/effects pack together (one theme id, three slices)."""
        self.theme_id = theme_id
        self.skin = Skin.load(theme_id)
        self.audio.set_theme(theme_id)
        self.effects.set_theme(theme_id)

    def sample_image(self) -> str:
        """First example image in samples/images (used by 'Quick start'). Empty if none."""
        folder = os.path.join(ROOT, "samples", "images")
        if os.path.isdir(folder):
            for name in sorted(os.listdir(folder)):
                if name.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".bmp")):
                    return os.path.join(folder, name)
        return ""


class PlaceholderScreen:
    """Shown when a screen that someone else owns does not exist yet (keeps the app usable)."""

    def __init__(self, ctx: AppContext, screen_id: str):
        self.ctx, self.screen_id = ctx, screen_id

    def handle_events(self, events):
        for e in events:
            if e.type == pygame.KEYDOWN and e.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_SPACE):
                return ("home", None)
            if e.type == pygame.MOUSEBUTTONDOWN:
                return ("home", None)
        return None

    def update(self, dt):
        pass

    def draw(self, surface):
        skin, fonts = self.ctx.skin, self.ctx.fonts
        surface.fill(skin.background)
        cx, cy = surface.get_width() // 2, surface.get_height() // 2
        draw_text(surface, fonts, f"The '{self.screen_id}' screen is not available yet", (cx, cy - 20), 28,
                  skin.text, "center", bold=True)
        draw_text(surface, fonts, "It belongs to another team member. Click or press Esc to go home.",
                  (cx, cy + 20), 18, skin.text_dim, "center")


def _instantiate(cls, ctx: AppContext):
    """Create a screen. Supports constructors with no arguments or with one (the context)."""
    params = [p for p in inspect.signature(cls).parameters.values()
              if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD) and p.default is p.empty]
    screen = cls(ctx) if params else cls()
    if not hasattr(screen, "ctx"):
        screen.ctx = ctx                                   # let screens that skipped the argument still find it
    return screen


def discover_screens(ctx: AppContext) -> dict:
    """Import every module in the screen packages and instantiate each class with a screen_id."""
    screens = {}
    for package_name in SCREEN_PACKAGES:
        try:
            package = importlib.import_module(package_name)
        except ImportError:
            log.info("No screens package %s yet", package_name)
            continue
        for info in pkgutil.iter_modules(package.__path__):
            try:
                module = importlib.import_module(f"{package_name}.{info.name}")
            except Exception:                              # one broken screen must not stop the app
                log.exception("Could not load screen module %s.%s", package_name, info.name)
                continue
            for _, cls in inspect.getmembers(module, inspect.isclass):
                if cls.__module__ == module.__name__ and hasattr(cls, "screen_id"):
                    screens[cls.screen_id] = _instantiate(cls, ctx)
    return screens


class App:
    def __init__(self, start_screen: str = "home", payload=None, use_fakes: bool = False):
        pygame.init()
        pygame.display.set_caption("Evolving an Image")
        try:
            surface = pygame.display.set_mode(WINDOW_SIZE, pygame.SCALED)   # fixed canvas, scaled to fit
        except pygame.error:
            surface = pygame.display.set_mode(WINDOW_SIZE)
        self.clock = pygame.time.Clock()
        self.running = True
        self.ctx = AppContext(load_backend(use_fakes), surface)
        self.ctx.go, self.ctx.quit = self.go, self.quit
        self.screens = discover_screens(self.ctx)
        self.current = None
        self.go(start_screen, payload)

    # ------------------------------------------------------------------ navigation
    def quit(self) -> None:
        self.running = False

    def go(self, screen_id: str, payload=None) -> None:
        """Leave the current screen and enter another."""
        if screen_id not in self.screens:
            if screen_id == "upload":                      # M4's screen is missing: skip straight to setup
                return self.go("setup", {"target_path": self.ctx.sample_image()})
            self.screens[screen_id] = PlaceholderScreen(self.ctx, screen_id)
        if self.current is not None and hasattr(self.current, "on_leave"):
            self.current.on_leave()
        self.current = self.screens[screen_id]
        if hasattr(self.current, "on_enter"):
            self.current.on_enter(payload)

    def _follow(self, request) -> None:
        nav = parse_navigation(request)
        if nav is not None:
            self.go(*nav)

    # ------------------------------------------------------------------ main loop
    def step(self, events: list, dt: float) -> None:
        """One frame: events -> update -> draw. Kept separate from run() so tests can drive it."""
        for event in events:
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_F11:
                pygame.display.toggle_fullscreen()           # UI-only key, no command involved
        screen = self.current
        self._follow(screen.handle_events(events))
        if self.current is screen:                           # the screen did not navigate away
            screen.update(dt)
            self._follow(getattr(screen, "take_navigation", lambda: None)())
        self.current.draw(self.ctx.surface)

    def run(self) -> None:
        while self.running:
            dt = min(self.clock.tick(60) / 1000.0, 0.1)      # cap so a stall never causes a huge jump
            self.step(pygame.event.get(), dt)
            pygame.display.flip()
        pygame.quit()
