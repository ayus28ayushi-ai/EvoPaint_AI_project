"""Skins (colors per theme id), fonts and small drawing helpers. M3 owns this look."""
from __future__ import annotations

import json
import os

import pygame

SKIN_DIR = os.path.join(os.path.dirname(__file__), "skins")
COLOR_KEYS = ["background", "background_alt", "panel", "panel_border", "text", "text_dim", "accent",
              "accent_text", "good", "bad", "grid", "button", "button_hover", "button_disabled",
              "slider_track", "slider_fill"]

# Built-in fallback so the app still runs if a skin file is missing or damaged (Contract 8:
# a missing slice falls back to full_color).
_FALLBACK = {
    "name": "Full Color", "corner_radius": 10,
    "background": "#f4f6fb", "background_alt": "#e8ecf5", "panel": "#ffffff", "panel_border": "#cfd6e4",
    "text": "#1d2433", "text_dim": "#6b7589", "accent": "#3b6cf6", "accent_text": "#ffffff",
    "good": "#1fa971", "bad": "#e5484d", "grid": "#e1e6f0", "button": "#e8ecf5",
    "button_hover": "#d9e0f0", "button_disabled": "#eef0f4", "slider_track": "#d5dbe8",
    "slider_fill": "#3b6cf6", "line_colors": ["#3b6cf6", "#f59f00", "#1fa971", "#d6409f"],
}


def _hex(value: str) -> tuple:
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


class Skin:
    """Colors and corner style for one theme. Colors are RGB tuples."""

    def __init__(self, data: dict, theme_id: str = "full_color"):
        self.theme_id = theme_id
        self.name = data.get("name", theme_id)
        self.corner_radius = int(data.get("corner_radius", 10))
        for key in COLOR_KEYS:
            setattr(self, key, _hex(data.get(key, _FALLBACK[key])))
        self.line_colors = [_hex(c) for c in data.get("line_colors", _FALLBACK["line_colors"])]
        while len(self.line_colors) < 4:                       # always four panel colors
            self.line_colors.append(self.accent)

    @classmethod
    def load(cls, theme_id: str) -> "Skin":
        try:
            with open(os.path.join(SKIN_DIR, f"{theme_id}.json"), encoding="utf-8") as f:
                return cls(json.load(f), theme_id)
        except (OSError, ValueError):
            return cls(_FALLBACK, "full_color")


class Fonts:
    """Caches fonts by (size, bold) so we never rebuild them every frame."""

    def __init__(self):
        self._cache = {}

    def get(self, size: int, bold: bool = False) -> pygame.font.Font:
        key = (size, bold)
        if key not in self._cache:
            try:
                self._cache[key] = pygame.font.SysFont("segoeui,helveticaneue,arial,dejavusans", size, bold=bold)
            except Exception:                                  # no system fonts: use Pygame's default
                self._cache[key] = pygame.font.Font(None, size + 6)
        return self._cache[key]


def draw_text(surface, fonts: Fonts, text: str, pos, size: int = 16, color=(0, 0, 0),
              anchor: str = "topleft", bold: bool = False) -> pygame.Rect:
    """Draw text and return its rectangle. `anchor` says which corner/edge `pos` refers to."""
    image = fonts.get(size, bold).render(str(text), True, color)
    rect = image.get_rect()
    setattr(rect, anchor, pos)
    surface.blit(image, rect)
    return rect


def fit_text(fonts: Fonts, text: str, size: int, max_width: int, bold: bool = False) -> str:
    """Shorten text with '...' so it fits in max_width pixels."""
    font = fonts.get(size, bold)
    if font.size(text)[0] <= max_width:
        return text
    while text and font.size(text + "...")[0] > max_width:
        text = text[:-1]
    return text + "..."


def draw_panel(surface, skin: Skin, rect, fill=None, border=None, radius=None) -> None:
    """A rounded card with a thin border."""
    radius = skin.corner_radius if radius is None else radius
    pygame.draw.rect(surface, fill or skin.panel, rect, border_radius=radius)
    pygame.draw.rect(surface, border or skin.panel_border, rect, width=1, border_radius=radius)


def draw_tooltip(surface, skin: Skin, fonts: Fonts, text: str, mouse_pos) -> None:
    """Small hint box near the mouse (kept inside the 1280 x 800 window)."""
    if not text:
        return
    font = fonts.get(14)
    width, height = font.size(text)
    x = min(mouse_pos[0] + 14, surface.get_width() - width - 14)
    y = min(mouse_pos[1] + 18, surface.get_height() - height - 12)
    box = pygame.Rect(x - 6, y - 4, width + 12, height + 8)
    pygame.draw.rect(surface, skin.text, box, border_radius=6)
    surface.blit(font.render(text, True, skin.background), (x, y))


# ------------------------------------------------------------------ image helpers
def pil_to_surface(image) -> pygame.Surface:
    """Convert a Pillow image to a Pygame surface (copying the pixels)."""
    image = image.convert("RGB")
    make = getattr(pygame.image, "frombytes", None) or pygame.image.fromstring   # new name, old fallback
    return make(image.tobytes(), image.size, "RGB")


_SQUARE_CACHE: dict = {}


def load_square_surface(path: str, size: int):
    """Load an image file, center-crop it to a square and scale it. Returns None if unreadable.
    Results are cached so thumbnails are not rebuilt every frame."""
    key = (path, size)
    if key in _SQUARE_CACHE:
        return _SQUARE_CACHE[key]
    surface = None
    try:
        from PIL import Image
        with Image.open(path) as img:
            img = img.convert("RGB")
            side = min(img.size)
            left, top = (img.width - side) // 2, (img.height - side) // 2
            img = img.crop((left, top, left + side, top + side)).resize((size, size))
            surface = pil_to_surface(img)
    except Exception:                                            # missing or broken file: show a placeholder
        surface = None
    _SQUARE_CACHE[key] = surface
    return surface
