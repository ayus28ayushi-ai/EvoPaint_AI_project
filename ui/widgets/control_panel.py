"""Live controls for the focused panel. Sliders are BUILT FROM the algorithm's parameter
specs (Contract 5.5), so a new algorithm gets its own sliders without any UI change."""
from __future__ import annotations

import logging

import pygame

from ui.compat import PanelInfo, SPEED_RANGE, get, make_command
from ui.theme import draw_panel, draw_text
from ui.widgets.basic import Button, Dropdown, Slider, Toggle

log = logging.getLogger("ui.controls")
ROW_H, HEADER_H = 34, 20


class ControlPanel:
    def __init__(self, rect, send):
        self.rect = pygame.Rect(rect)
        self.send = send                  # callable(Command): goes to Session.send
        self.panel = None
        self.title = "Controls"
        self.widgets: list = []
        self.headers: list = []           # (text, y)
        self._speed_slider = None

    # ------------------------------------------------------------------ building
    def rebuild(self, panel: int, info: PanelInfo, title: str) -> None:
        """(Re)create every widget for one panel. Called when focus or algorithm changes."""
        self.panel, self.title = panel, title
        self.widgets, self.headers = [], []
        x, w = self.rect.x + 14, self.rect.width - 28
        y = self.rect.y + 34
        reserve = 40 if info.action_specs else 4                 # keep room for the action buttons

        def add_slider(label, lo, hi, value, step, scale, is_int, on_change, tip):
            nonlocal y
            slider = Slider((x, y, w, ROW_H), label, lo, hi, value, on_change, step, scale, is_int, tip)
            self.widgets.append(slider)
            y += ROW_H
            return slider

        self._speed_slider = add_slider(
            "Speed (evaluations / second)", SPEED_RANGE[0], SPEED_RANGE[1], info.speed, 0, "log", False,
            lambda v: self.send(make_command("set_speed", panel=panel, speed=v)),
            "How fast this panel paints. Lower it to watch more slowly.")

        for group, heading in (("algorithm", "Algorithm"), ("painting", "Painting")):
            specs = [s for s in info.param_specs if get(s, "group", "algorithm") == group]
            if not specs:
                continue
            self.headers.append((heading, y + 2))
            y += HEADER_H
            for spec in specs:
                if y + ROW_H > self.rect.bottom - reserve:
                    log.warning("Control panel full: skipping %s", get(spec, "name"))
                    break
                y = self._add_spec_widget(spec, info, panel, group, x, y, w)

        if info.action_specs:                                     # one-shot buttons such as Reheat
            bx = x
            width = (w - 8 * (len(info.action_specs) - 1)) // len(info.action_specs)
            for action in info.action_specs:
                name = get(action, "name")
                self.widgets.append(Button((bx, y + 4, width, 30), get(action, "label", name),
                                           lambda n=name: self.send(make_command("trigger_action", panel=panel, action=n)),
                                           "accent", get(action, "help_text", "")))
                bx += width + 8

    def _add_spec_widget(self, spec, info, panel, group, x, y, w) -> int:
        name, kind = get(spec, "name"), get(spec, "kind", "float")
        default = get(spec, "default", 0)
        value = info.params.get(name, default)
        tip = get(spec, "help_text", "")

        def send_value(v, n=name):
            self.send(make_command("set_param", panel=panel, group=group, name=n, value=v))

        if kind == "bool":
            self.widgets.append(Toggle((x, y + 6, w, 24), get(spec, "label", name), bool(value), send_value, tip))
        elif kind == "choice":
            options = [(o, str(o)) for o in (get(spec, "options", []) or [])]
            self.widgets.append(Dropdown((x, y + 4, w, 30), options, value, send_value, tip))
        else:
            self.widgets.append(Slider((x, y, w, ROW_H), get(spec, "label", name), get(spec, "minimum", 0),
                                       get(spec, "maximum", 1), value, send_value, get(spec, "step", 0),
                                       get(spec, "scale", "linear"), kind == "int", tip))
        return y + ROW_H

    # ------------------------------------------------------------------ interaction
    def set_speed_display(self, speed: float) -> None:
        """Keep the speed slider in sync when the +/- hotkeys change the speed."""
        if self._speed_slider is not None:
            self._speed_slider.set_value(speed)

    def handle_event(self, event) -> bool:
        for widget in reversed(self.widgets):
            if widget.handle_event(event):
                return True
        return False

    def hovered_tooltip(self) -> str:
        mouse = pygame.mouse.get_pos()
        for widget in self.widgets:
            if widget.tooltip and widget.rect.collidepoint(mouse):
                return widget.tooltip
        return ""

    def draw(self, surface, skin, fonts) -> None:
        draw_panel(surface, skin, self.rect)
        draw_text(surface, fonts, self.title, (self.rect.x + 14, self.rect.y + 8), 16, skin.text, bold=True)
        for text, y in self.headers:
            draw_text(surface, fonts, text.upper(), (self.rect.x + 14, y), 12, skin.accent, bold=True)
        for widget in self.widgets:
            widget.draw(surface, skin, fonts)
        for widget in self.widgets:
            if isinstance(widget, Dropdown):
                widget.draw_popup(surface, skin, fonts)
