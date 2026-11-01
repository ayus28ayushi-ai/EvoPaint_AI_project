"""Small reusable widgets. Each has handle_event(event) -> bool (True = event used) and
draw(surface, skin, fonts). Colors always come from the active Skin, so themes just work."""
from __future__ import annotations

import pygame

from ui.layout import WINDOW_SIZE
from ui.theme import draw_text, fit_text
from ui.widgets import slider_math as sm


class Widget:
    """Common bits: a rectangle, an optional tooltip and an enabled flag."""

    def __init__(self, rect, tooltip: str = ""):
        self.rect = pygame.Rect(rect)
        self.tooltip = tooltip
        self.enabled = True

    def hovered(self) -> bool:
        return self.rect.collidepoint(pygame.mouse.get_pos())

    def handle_event(self, event) -> bool:
        return False

    def draw(self, surface, skin, fonts) -> None:
        pass


def _left_click(event) -> bool:
    return event.type == pygame.MOUSEBUTTONDOWN and getattr(event, "button", 1) == 1


class Button(Widget):
    def __init__(self, rect, label: str, on_click, kind: str = "normal", tooltip: str = ""):
        super().__init__(rect, tooltip)
        self.label, self.on_click, self.kind = label, on_click, kind   # kind: normal / accent / danger

    def handle_event(self, event) -> bool:
        if self.enabled and _left_click(event) and self.rect.collidepoint(event.pos):
            self.on_click()
            return True
        return False

    def draw(self, surface, skin, fonts) -> None:
        if not self.enabled:
            fill, text = skin.button_disabled, skin.text_dim
        elif self.kind == "accent":
            fill, text = skin.accent, skin.accent_text
        elif self.kind == "danger":
            fill, text = skin.bad, skin.accent_text
        else:
            fill, text = (skin.button_hover if self.hovered() else skin.button), skin.text
        pygame.draw.rect(surface, fill, self.rect, border_radius=skin.corner_radius)
        if self.enabled and self.kind == "normal":
            pygame.draw.rect(surface, skin.panel_border, self.rect, 1, border_radius=skin.corner_radius)
        label = fit_text(fonts, self.label, 16, self.rect.width - 12, bold=True)
        draw_text(surface, fonts, label, self.rect.center, 16, text, "center", bold=True)


class Toggle(Widget):
    def __init__(self, rect, label: str, value: bool, on_change, tooltip: str = ""):
        super().__init__(rect, tooltip)
        self.label, self.value, self.on_change = label, bool(value), on_change

    def handle_event(self, event) -> bool:
        if self.enabled and _left_click(event) and self.rect.collidepoint(event.pos):
            self.value = not self.value
            self.on_change(self.value)
            return True
        return False

    def draw(self, surface, skin, fonts) -> None:
        box = pygame.Rect(self.rect.x, self.rect.centery - 9, 18, 18)
        pygame.draw.rect(surface, skin.slider_fill if self.value else skin.slider_track, box,
                         border_radius=max(skin.corner_radius // 3, 0))
        if self.value:                                          # a simple tick mark
            pygame.draw.lines(surface, skin.accent_text, False,
                              [(box.x + 4, box.centery), (box.x + 8, box.bottom - 5), (box.right - 4, box.y + 5)], 2)
        draw_text(surface, fonts, fit_text(fonts, self.label, 15, self.rect.width - 28), (box.right + 8, self.rect.centery),
                  15, skin.text, "midleft")


class Slider(Widget):
    """Horizontal slider. Supports linear, log and 'rate-like' log scales (see slider_math)."""

    def __init__(self, rect, label, minimum, maximum, value, on_change, step=0.0, scale="linear",
                 is_int=False, tooltip=""):
        super().__init__(rect, tooltip)
        self.label, self.minimum, self.maximum = label, minimum, maximum
        self.on_change, self.step, self.scale, self.is_int = on_change, step, scale, is_int
        self.value = min(max(value, minimum), maximum)
        self.dragging = False

    # The track is the thin line near the bottom of the widget's rectangle.
    def _track(self) -> pygame.Rect:
        return pygame.Rect(self.rect.x + 8, self.rect.bottom - 12, self.rect.width - 16, 6)

    def _set_from_x(self, x: int) -> None:
        track = self._track()
        t = (x - track.x) / max(track.width, 1)
        value = sm.from_unit(t, self.minimum, self.maximum, self.scale, self.step, self.is_int)
        if value != self.value:
            self.value = value
            self.on_change(value)

    def set_value(self, value) -> None:
        """Change the shown value without calling on_change (used when syncing from outside)."""
        self.value = min(max(value, self.minimum), self.maximum)

    def handle_event(self, event) -> bool:
        if not self.enabled:
            return False
        if _left_click(event) and self.rect.inflate(0, 6).collidepoint(event.pos):
            self.dragging = True
            self._set_from_x(event.pos[0])
            return True
        if event.type == pygame.MOUSEMOTION and self.dragging:
            self._set_from_x(event.pos[0])
            return True
        if event.type == pygame.MOUSEBUTTONUP and self.dragging:
            self.dragging = False
            return True
        return False

    def draw(self, surface, skin, fonts) -> None:
        draw_text(surface, fonts, fit_text(fonts, self.label, 14, self.rect.width - 90),
                  (self.rect.x, self.rect.y), 14, skin.text)
        draw_text(surface, fonts, sm.format_value(self.value, self.is_int),
                  (self.rect.right, self.rect.y), 14, skin.text_dim, "topright")
        track = self._track()
        t = sm.to_unit(self.value, self.minimum, self.maximum, self.scale)
        pygame.draw.rect(surface, skin.slider_track, track, border_radius=3)
        pygame.draw.rect(surface, skin.slider_fill, (track.x, track.y, int(track.width * t), track.height),
                         border_radius=3)
        knob = (track.x + int(track.width * t), track.centery)
        pygame.draw.circle(surface, skin.slider_fill, knob, 8)
        pygame.draw.circle(surface, skin.panel, knob, 3)


class Dropdown(Widget):
    """Click to open a list below (or above when there is no room). Draw order matters: call
    draw() for all widgets first, then draw_popup() last so the list floats on top."""

    def __init__(self, rect, options: list, value, on_change, tooltip: str = ""):
        super().__init__(rect, tooltip)
        self.options, self.value, self.on_change = list(options), value, on_change   # options: (value, label)
        self.is_open = False

    def _label(self) -> str:
        return next((label for v, label in self.options if v == self.value), str(self.value))

    def _popup_rect(self) -> pygame.Rect:
        height = self.rect.height * len(self.options)
        below = self.rect.bottom + 2
        y = below if below + height <= WINDOW_SIZE[1] else self.rect.y - height - 2
        return pygame.Rect(self.rect.x, y, self.rect.width, height)

    def handle_event(self, event) -> bool:
        if not self.enabled or not _left_click(event):
            return False
        if self.is_open:
            popup = self._popup_rect()
            self.is_open = False
            if popup.collidepoint(event.pos):
                index = (event.pos[1] - popup.y) // self.rect.height
                value = self.options[min(max(index, 0), len(self.options) - 1)][0]
                if value != self.value:
                    self.value = value
                    self.on_change(value)
                return True
            return self.rect.collidepoint(event.pos)           # clicking the button itself just closes
        if self.rect.collidepoint(event.pos):
            self.is_open = True
            return True
        return False

    def draw(self, surface, skin, fonts) -> None:
        fill = skin.button_hover if (self.hovered() or self.is_open) else skin.button
        pygame.draw.rect(surface, fill, self.rect, border_radius=skin.corner_radius)
        pygame.draw.rect(surface, skin.panel_border, self.rect, 1, border_radius=skin.corner_radius)
        draw_text(surface, fonts, fit_text(fonts, self._label(), 15, self.rect.width - 34),
                  (self.rect.x + 10, self.rect.centery), 15, skin.text, "midleft")
        cx, cy = self.rect.right - 16, self.rect.centery            # little down-arrow
        pygame.draw.polygon(surface, skin.text_dim, [(cx - 5, cy - 3), (cx + 5, cy - 3), (cx, cy + 4)])

    def draw_popup(self, surface, skin, fonts) -> None:
        if not self.is_open:
            return
        popup = self._popup_rect()
        pygame.draw.rect(surface, skin.panel, popup, border_radius=skin.corner_radius)
        pygame.draw.rect(surface, skin.accent, popup, 1, border_radius=skin.corner_radius)
        mouse = pygame.mouse.get_pos()
        for i, (value, label) in enumerate(self.options):
            row = pygame.Rect(popup.x, popup.y + i * self.rect.height, popup.width, self.rect.height)
            if row.collidepoint(mouse):
                pygame.draw.rect(surface, skin.button_hover, row.inflate(-4, -2), border_radius=4)
            color = skin.accent if value == self.value else skin.text
            draw_text(surface, fonts, fit_text(fonts, label, 15, row.width - 20), (row.x + 10, row.centery),
                      15, color, "midleft")


class Segmented(Widget):
    """A row of connected buttons where exactly one is selected."""

    def __init__(self, rect, options: list, value, on_change, tooltip: str = ""):
        super().__init__(rect, tooltip)
        self.options, self.value, self.on_change = list(options), value, on_change   # options: (value, label)

    def _cell(self, i: int) -> pygame.Rect:
        width = self.rect.width / len(self.options)
        return pygame.Rect(int(self.rect.x + i * width), self.rect.y, int(width) - 2, self.rect.height)

    def handle_event(self, event) -> bool:
        if not self.enabled or not _left_click(event) or not self.rect.collidepoint(event.pos):
            return False
        for i, (value, _) in enumerate(self.options):
            if self._cell(i).collidepoint(event.pos):
                if value != self.value:
                    self.value = value
                    self.on_change(value)
                return True
        return False

    def draw(self, surface, skin, fonts) -> None:
        for i, (value, label) in enumerate(self.options):
            cell = self._cell(i)
            chosen = value == self.value
            fill = skin.accent if chosen else (skin.button_hover if cell.collidepoint(pygame.mouse.get_pos()) else skin.button)
            pygame.draw.rect(surface, fill, cell, border_radius=skin.corner_radius)
            draw_text(surface, fonts, fit_text(fonts, label, 15, cell.width - 8), cell.center, 15,
                      skin.accent_text if chosen else skin.text, "center", bold=chosen)
