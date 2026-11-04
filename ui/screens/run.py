"""Run screen: 1 to 4 panels painting side by side, the stock-market chart, leaderboard,
live sliders and hotkeys (Contract 9).

Data flow every frame:
    session.tick(dt)                -> algorithms advance
    session.poll_events()           -> milestones/injections -> toasts, markers, audio, confetti
    session.snapshot/history/...    -> what we draw
    keys and sliders                -> session.send(Command)
The screen never runs an algorithm itself.
"""
from __future__ import annotations

import logging
import os
import time

import pygame

from ui import layout
from ui.compat import Navigation, get, make_command, parse_algorithm_info, parse_panel_info
from ui.chart_math import format_count
from ui.theme import draw_panel, draw_text, fit_text, load_square_surface, pil_to_surface, draw_tooltip
from ui.widgets.basic import Button
from ui.widgets.chart import StockChart
from ui.widgets.control_panel import ControlPanel
from ui.widgets.leaderboard import LeaderboardWidget

log = logging.getLogger("ui.run")
IMAGE_FPS = 15                  # panel pictures are refreshed this often (drawing is cheaper than rendering)
HISTORY_EVERY = 0.25            # seconds between chart data refreshes
HELP_LINES = [("Space", "Pause / resume"), ("+  -", "Speed (focused)"), ("1-4 / Tab", "Focus panel"),
              ("I", "Inject 50 shapes"), ("Shift+I", "Inject (focused)"), ("R", "Reheat / restart"),
              ("C", "Chart mode"), ("M", "Mute"), ("F", "Finish run"), ("S", "Screenshot"),
              ("T", "Show target"), ("Esc", "Back (press twice)")]


class RunScreen:
    screen_id = "run"

    def __init__(self, ctx):
        self.ctx = ctx
        self._nav = None
        self.session = None

    # ------------------------------------------------------------------ entering and leaving
    def on_enter(self, payload=None) -> None:
        ctx, backend = self.ctx, self.ctx.backend
        self.config = get(payload, "run_config", payload)
        self._nav, self.finishing, self._finish_frames = None, False, 0
        self.session = backend.create_session(self.config)
        ctx.set_theme(get(self.config, "theme_id", "full_color"))
        ctx.audio.start_music()

        algos = {a.id: a for a in map(parse_algorithm_info, backend.list_algorithms())}
        self.count = len(get(self.config, "panels", []))
        self.regions = layout.run_regions()
        self.cells = [pygame.Rect(c) for c in layout.panel_grid(self.count, self.regions["panels"])]
        self.names = {i: algos[get(p, "algorithm_id")].display_name if get(p, "algorithm_id") in algos else f"Panel {i + 1}"
                      for i, p in enumerate(get(self.config, "panels", []))}
        self.focus = 0
        self.entries: list = []
        self.surfaces: dict = {}
        self.toasts: list = []                                        # (text, expires_at, color_key)
        self._image_timer = self._history_timer = 0.0
        self._last_esc = 0.0
        self._throttle_toast: dict = {}
        self._show_target = False
        self.infos: dict = {}

        self.chart = StockChart()
        self.chart.names = {i: f"{i + 1}  {n}" for i, n in self.names.items()}
        self.leaderboard = LeaderboardWidget()
        self.controls = ControlPanel(self.regions["controls"], self.session.send)
        self._rebuild_controls()

        bar_y = 11
        self.pause_button = Button((780 - 20, bar_y, 104, 34), "Pause", self._toggle_pause, "normal", "Space")
        self.finish_button = Button((888 - 20, bar_y, 104, 34), "Finish", self._begin_finish, "accent",
                                    "Stop, save to the gallery and see the results (F)")
        self.muted = False
        self.leave_button = Button((1140, bar_y, 120, 34), "Home", self._leave_hint, "normal", "Esc, twice")

    def on_leave(self) -> None:
        self.ctx.audio.stop_music()
        self.ctx.effects.clear()

    def take_navigation(self):
        nav, self._nav = self._nav, None
        return nav

    # ------------------------------------------------------------------ small helpers
    def _send(self, kind: str, **payload) -> None:
        self.session.send(make_command(kind, **payload))

    def _toast(self, text: str, color: str = "text", seconds: float = 3.0) -> None:
        self.toasts.append((text, time.time() + seconds, color))
        self.toasts = self.toasts[-3:]

    def _rebuild_controls(self) -> None:
        info = parse_panel_info(self.session.panel_info(self.focus))
        self.controls.rebuild(self.focus, info, f"Controls - panel {self.focus + 1}: {self.names.get(self.focus, '')}")

    def _focus_panel(self, index: int) -> None:
        if 0 <= index < self.count and index != self.focus:
            self.focus = index
            self._rebuild_controls()

    def _toggle_pause(self) -> None:
        paused = self.session.status() == "paused"
        self._send("resume" if paused else "pause")

    def _leave_hint(self) -> None:
        now = time.time()
        if now - self._last_esc < 2.0:
            self._nav = Navigation("home")
        else:
            self._last_esc = now
            self._toast("Leaving discards this run. Press again to confirm.", "bad")

    def _begin_finish(self) -> None:
        if not self.finishing:
            self.finishing, self._finish_frames = True, 0            # draw 'Saving...' first, then save

    def _speed_step(self, factor: float) -> None:
        info = parse_panel_info(self.session.panel_info(self.focus))
        speed = min(max(info.speed * factor, 50.0), 10000.0)
        self._send("set_speed", panel=self.focus, speed=speed)
        self.controls.set_speed_display(speed)

    # ------------------------------------------------------------------ input
    def handle_events(self, events):
        for event in events:
            if self.finishing:
                break
            if event.type == pygame.KEYDOWN:
                self._on_key(event)
                continue
            if self.pause_button.handle_event(event) or self.finish_button.handle_event(event) \
                    or self.leave_button.handle_event(event):
                continue
            if self.controls.handle_event(event):
                continue
            if event.type == pygame.MOUSEBUTTONDOWN and getattr(event, "button", 1) == 1:
                for i, cell in enumerate(self.cells):                # click a panel to focus it
                    if cell.collidepoint(event.pos):
                        self._focus_panel(i)
        return self.take_navigation()

    def _on_key(self, event) -> None:
        key, shift = event.key, bool(getattr(event, "mod", 0) & pygame.KMOD_SHIFT)
        if key == pygame.K_SPACE:
            self._toggle_pause()
        elif key in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
            self._speed_step(1.25)
        elif key in (pygame.K_MINUS, pygame.K_KP_MINUS):
            self._speed_step(0.8)
        elif key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4):
            self._focus_panel(key - pygame.K_1)
        elif key == pygame.K_TAB:
            self._focus_panel((self.focus + 1) % self.count)
        elif key == pygame.K_i:
            if shift:
                self._send("inject", count=50, panels=[self.focus])
            else:
                self._send("inject", count=50, panels="all")
        elif key == pygame.K_r:
            info = parse_panel_info(self.session.panel_info(self.focus))
            if info.action_specs:                                    # first action = reheat / diversify
                self._send("trigger_action", panel=self.focus, action=get(info.action_specs[0], "name"))
        elif key == pygame.K_c:
            self.chart.toggle_mode()
        elif key == pygame.K_m:
            self.muted = not self.muted
            self.ctx.audio.set_muted(self.muted)
        elif key == pygame.K_f:
            self._begin_finish()
        elif key == pygame.K_s:
            self._screenshot()
        elif key == pygame.K_t:
            self._show_target = not self._show_target                # UI-only key, no command
        elif key == pygame.K_ESCAPE:
            self._leave_hint()

    def _screenshot(self) -> None:
        folder = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "out")
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, time.strftime("screenshot_%Y%m%d_%H%M%S.png"))
        pygame.image.save(self.ctx.surface, path)
        self._toast(f"Saved {os.path.basename(path)}")

    # ------------------------------------------------------------------ per-frame update
    def update(self, dt: float) -> None:
        if self.finishing:                                           # give the 'Saving...' frame time to show
            self._finish_frames += 1
            if self._finish_frames >= 3:
                self._save_and_leave()
            return

        self.session.tick(dt)
        self._handle_session_events(self.session.poll_events())
        self.entries = self.session.leaderboard()
        self.leaderboard.update(dt, self.entries)
        self.chart.update(dt)
        self.ctx.audio.update(dt)
        self.ctx.effects.update(dt)

        self._history_timer += dt
        if self._history_timer >= HISTORY_EVERY:                     # chart data is refreshed a few times a second
            self._history_timer = 0.0
            for i in range(self.count):
                self.chart.series[i] = self.session.history(i, 2000)
                self.infos[i] = parse_panel_info(self.session.panel_info(i))
        self._image_timer += dt
        if self._image_timer >= 1.0 / IMAGE_FPS or not self.surfaces:
            self._image_timer = 0.0
            self._refresh_images()

        now = time.time()
        self.toasts = [t for t in self.toasts if t[1] > now]
        if self.session.status() == "finished":
            self._begin_finish()

    def _refresh_images(self) -> None:
        """Ask the session for each panel's current picture and convert it for drawing."""
        for i, cell in enumerate(self.cells):
            _, image_rect, _ = layout.panel_inner(tuple(cell))
            try:
                self.surfaces[i] = pil_to_surface(self.session.render(i, image_rect[2]))
            except Exception:
                log.exception("Could not render panel %s", i)

    def _handle_session_events(self, events: list) -> None:
        for event in events:
            kind, panel = get(event, "type"), get(event, "panel")
            cell = self.cells[panel] if isinstance(panel, int) and 0 <= panel < self.count else self.cells[0]
            self.ctx.audio.on_event(event)                            # M4: sounds
            self.ctx.effects.on_event(event, cell)                    # M4: confetti over this panel
            name = self.names.get(panel, "Panel")
            level = get(event, "level") or get(get(event, "payload"), "level")
            if kind in ("milestone_reached", "shapes_injected"):
                self.chart.markers.append({"type": kind, "panel": panel, "evaluations": get(event, "evaluations", 0),
                                           "level": level})
            if kind == "milestone_reached":
                self._toast(f"{name} reached {level}%!", "good")
            elif kind == "shapes_injected":
                count = get(event, "count") or get(get(event, "payload"), "count", 50)
                self._toast(f"{count} random shapes injected into {name}", "bad")
            elif kind == "leader_changed":
                self._toast(f"{self.names.get(get(event, 'new_panel'), name)} takes the lead")
            elif kind == "panel_throttled":
                if time.time() - self._throttle_toast.get(panel, 0) > 10:
                    self._throttle_toast[panel] = time.time()
                    self._toast(f"{name} cannot keep up with its speed setting")
            elif kind == "panel_finished":
                self._toast(f"{name} used its whole budget")

    def _save_and_leave(self) -> None:
        """Finish the session, let media build GIFs + postcard + gallery entry, then open the entry."""
        try:
            record = self.session.finish()
            run_id = self.ctx.backend.save_run(record)
            self._nav = Navigation("entry", {"run_id": run_id})
        except Exception as error:                                   # never lose the app because saving failed
            log.exception("Saving the run failed")
            self.ctx.notice = f"Saving failed: {error}"
            self._nav = Navigation("home")
        self.finishing = False

    # ------------------------------------------------------------------ drawing
    def draw(self, surface) -> None:
        skin, fonts = self.ctx.skin, self.ctx.fonts
        surface.fill(skin.background)
        self._draw_top_bar(surface, skin, fonts)
        for i, cell in enumerate(self.cells):
            self._draw_panel(surface, i, cell, skin, fonts)
        self.chart.draw(surface, self.regions["chart"], skin, fonts)
        self.leaderboard.draw(surface, self.regions["leaderboard"], self.entries, self.names, skin, fonts)
        self.controls.draw(surface, skin, fonts)
        self._draw_help(surface, skin, fonts)
        self.ctx.effects.draw(surface)                                # confetti sits above everything
        self._draw_toasts(surface, skin, fonts)
        if self._show_target:
            self._draw_target_overlay(surface, skin, fonts)
        if self.finishing:
            self._draw_saving(surface, skin, fonts)
        mouse = pygame.mouse.get_pos()
        tip = self.controls.hovered_tooltip() or next(
            (w.tooltip for w in (self.pause_button, self.finish_button, self.leave_button) if w.tooltip and w.rect.collidepoint(mouse)), "")
        draw_tooltip(surface, skin, fonts, tip, mouse)

    def _draw_top_bar(self, surface, skin, fonts) -> None:
        bar = pygame.Rect(self.regions["top_bar"])
        pygame.draw.rect(surface, skin.background_alt, bar)
        thumb = load_square_surface(get(self.config, "target_path", ""), 40)
        if thumb is not None:                                         # tiny target preview (T for a big one)
            surface.blit(thumb, (14, 8))
        draw_text(surface, fonts, "Evolving an Image", (64, 8), 20, skin.text, bold=True)
        status = self.session.status()
        elapsed = float(get(self.session.snapshot(self.focus), "elapsed_seconds", 0.0)) if self.count else 0.0
        draw_text(surface, fonts, f"{status.upper()}  -  {elapsed:0.1f}s  -  theme: {skin.name}", (64, 33), 13, skin.text_dim)
        self.pause_button.label = "Resume" if status == "paused" else "Pause"
        for widget in (self.pause_button, self.finish_button, self.leave_button):
            widget.draw(surface, skin, fonts)

    def _draw_panel(self, surface, i, cell, skin, fonts) -> None:
        header, image_rect, footer = (pygame.Rect(r) for r in layout.panel_inner(tuple(cell)))
        focused = i == self.focus
        draw_panel(surface, skin, cell, border=skin.accent if focused else None)
        if focused:
            pygame.draw.rect(surface, skin.accent, cell, 2, border_radius=skin.corner_radius)
        snap = self.session.snapshot(i)
        color = skin.line_colors[i % len(skin.line_colors)]
        pygame.draw.rect(surface, color, (header.x + 10, header.y + 7, 5, 18), border_radius=2)
        draw_text(surface, fonts, fit_text(fonts, f"{i + 1}  {self.names.get(i, '')}", 15, header.width - 100),
                  (header.x + 22, header.centery), 15, skin.text, "midleft", bold=True)
        draw_text(surface, fonts, f"{float(get(snap, 'similarity', 0)):.1f}%", (header.right - 10, header.centery),
                  17, color, "midright", bold=True)
        picture = self.surfaces.get(i)
        if picture is not None:
            surface.blit(picture, image_rect)
        else:
            pygame.draw.rect(surface, skin.button, image_rect)
        pygame.draw.rect(surface, skin.panel_border, image_rect, 1)

        evals = format_count(get(snap, "evaluations", 0))
        proposed = max(get(snap, "proposed_total", 0), 1)
        rate = 100.0 * get(snap, "accepted_total", 0) / proposed
        extras = get(snap, "extras", {}) or {}
        text = f"{evals} evals   {rate:.0f}% accepted"
        if "temperature" in extras:
            text += f"   T {extras['temperature']:.3f}"
        draw_text(surface, fonts, fit_text(fonts, text, 12, footer.width - 70), (footer.x + 10, footer.centery), 12, skin.text_dim, "midleft")
        info = self.infos.get(i)
        if info is not None and info.throttled:
            draw_text(surface, fonts, "SLOW", (footer.right - 10, footer.centery), 12, skin.bad, "midright", bold=True)

    def _draw_help(self, surface, skin, fonts) -> None:
        rect = pygame.Rect(self.regions["help"])
        draw_panel(surface, skin, rect)
        half = (len(HELP_LINES) + 1) // 2
        for n, (keys, what) in enumerate(HELP_LINES):
            col, row = divmod(n, half)
            x, y = rect.x + 12 + col * (rect.width // 2), rect.y + 8 + row * 17
            draw_text(surface, fonts, keys, (x, y), 12, skin.accent, bold=True)
            draw_text(surface, fonts, what, (x + 62, y), 12, skin.text_dim)

    def _draw_toasts(self, surface, skin, fonts) -> None:
        y = self.regions["chart"][1] - 34
        for text, _, color in reversed(self.toasts):
            width = fonts.get(15, True).size(text)[0] + 28
            box = pygame.Rect(self.regions["panels"][0] + (self.regions["panels"][2] - width) // 2, y, width, 30)
            pygame.draw.rect(surface, skin.panel, box, border_radius=skin.corner_radius)
            pygame.draw.rect(surface, getattr(skin, color), box, 2, border_radius=skin.corner_radius)
            draw_text(surface, fonts, text, box.center, 15, skin.text, "center", bold=True)
            y -= 36

    def _draw_target_overlay(self, surface, skin, fonts) -> None:
        shade = pygame.Surface(surface.get_size())
        shade.set_alpha(170)
        surface.blit(shade, (0, 0))
        side = 480
        picture = load_square_surface(get(self.config, "target_path", ""), side)
        box = pygame.Rect((surface.get_width() - side) // 2, (surface.get_height() - side) // 2, side, side)
        if picture is not None:
            surface.blit(picture, box)
        pygame.draw.rect(surface, skin.accent, box.inflate(8, 8), 3)
        draw_text(surface, fonts, "Target (press T to close)", (box.centerx, box.bottom + 22), 16, (255, 255, 255), "center")

    def _draw_saving(self, surface, skin, fonts) -> None:
        shade = pygame.Surface(surface.get_size())
        shade.set_alpha(200)
        surface.blit(shade, (0, 0))
        draw_text(surface, fonts, "Saving your painting...", (surface.get_width() // 2, surface.get_height() // 2 - 10),
                  32, (255, 255, 255), "center", bold=True)
        draw_text(surface, fonts, "Building your postcard", (surface.get_width() // 2, surface.get_height() // 2 + 26),
                  16, (220, 220, 220), "center")