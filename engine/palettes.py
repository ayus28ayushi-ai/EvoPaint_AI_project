"""Theme palette rules (contract Section 8). Mechanisms: none, gradient_map, snap_palette."""
from __future__ import annotations

import logging
import random

import numpy as np

log = logging.getLogger(__name__)

_NEON = [(8, 0, 24), (255, 0, 255), (0, 255, 255), (57, 255, 20), (255, 255, 0),
         (255, 20, 147), (255, 95, 31), (0, 128, 255)]
_PASTEL = [(255, 179, 186), (255, 223, 186), (255, 255, 186), (186, 255, 201), (186, 225, 255),
           (218, 186, 255), (255, 214, 224), (200, 230, 215), (245, 235, 220), (210, 210, 235),
           (255, 240, 245), (225, 240, 255)]
_RETRO = [(0, 0, 0), (29, 43, 83), (126, 37, 83), (0, 135, 81), (171, 82, 54), (95, 87, 79),
          (194, 195, 199), (255, 241, 232), (255, 0, 77), (255, 163, 0), (255, 236, 39),
          (0, 228, 54), (41, 173, 255), (131, 118, 156), (255, 119, 168), (255, 204, 170)]

# theme_id -> (display name, mechanism, colours, opaque)
THEMES = {
    "full_color": ("Full Color", "none", [], False),
    "black_white": ("Black and White", "gradient_map", [(0, 0, 0), (255, 255, 255)], False),
    "sepia": ("Sepia", "gradient_map", [(44, 26, 10), (250, 240, 220)], False),
    "neon": ("Neon", "snap_palette", _NEON, True),
    "pastel": ("Pastel", "snap_palette", _PASTEL, False),
    "ocean": ("Ocean", "gradient_map", [(5, 20, 70), (0, 180, 200), (240, 255, 255)], False),
    "sunset": ("Sunset", "gradient_map", [(60, 10, 90), (220, 50, 60), (255, 220, 80)], False),
    "retro_8bit": ("Retro 8-bit", "snap_palette", _RETRO, True),
}
_NEUTRAL_SWATCHES = [(231, 76, 60), (243, 156, 18), (241, 196, 15), (46, 204, 113), (52, 152, 219), (155, 89, 182)]


def _luma(r: int, g: int, b: int) -> int:
    return (r * 299 + g * 587 + b * 114) // 1000


class ThemeRule:
    """The palette rule of one theme: how the target is processed and how colours are constrained."""

    def __init__(self, theme_id: str) -> None:
        if theme_id not in THEMES:
            log.warning("unknown theme %r, using full_color", theme_id)
            theme_id = "full_color"
        name, mech, colors, opaque = THEMES[theme_id]
        self.theme_id, self.display_name, self.mechanism, self.opaque = theme_id, name, mech, opaque
        self.colors = [tuple(c) for c in colors]
        self._cache: dict = {}
        self.palette = np.array(self.colors, dtype=np.int32) if mech == "snap_palette" else None
        self.lut = None
        if mech == "gradient_map":
            stops = np.linspace(0, 255, len(self.colors))
            self.lut = np.stack([np.interp(np.arange(256), stops, [c[k] for c in self.colors])
                                 for k in range(3)], axis=1).round().astype(np.uint8)

    def process_array(self, arr: np.ndarray) -> np.ndarray:
        """Apply the palette rule to a uint8 (H, W, 3) array."""
        if self.mechanism == "none":
            return arr
        a = arr.astype(np.int32)
        if self.mechanism == "gradient_map":
            lum = (a[..., 0] * 299 + a[..., 1] * 587 + a[..., 2] * 114) // 1000
            return self.lut[lum]
        best = np.full(a.shape[:2], np.iinfo(np.int32).max, dtype=np.int32)
        idx = np.zeros(a.shape[:2], dtype=np.int32)
        for k, c in enumerate(self.palette):
            d = ((a - c) ** 2).sum(axis=2)
            better = d < best
            best[better], idx[better] = d[better], k
        return self.palette[idx].astype(np.uint8)

    def constrain(self, r: int, g: int, b: int) -> tuple:
        """Nearest allowed colour for a shape colour."""
        r, g, b = int(min(255, max(0, r))), int(min(255, max(0, g))), int(min(255, max(0, b)))
        if self.mechanism == "none":
            return r, g, b
        key = (r, g, b)
        hit = self._cache.get(key)
        if hit is not None:
            return hit
        if self.mechanism == "gradient_map":
            out = tuple(int(v) for v in self.lut[_luma(r, g, b)])
        else:
            out = min(self.colors, key=lambda c: (c[0] - r) ** 2 + (c[1] - g) ** 2 + (c[2] - b) ** 2)
        if len(self._cache) < 50000:
            self._cache[key] = out
        return out

    def random_palette_color(self, rng: random.Random) -> tuple | None:
        """A random palette entry for snap themes, otherwise None."""
        return rng.choice(self.colors) if self.mechanism == "snap_palette" else None

    def swatches(self) -> list:
        """Short list of colours describing the palette."""
        if self.mechanism == "none":
            return list(_NEUTRAL_SWATCHES)
        if self.mechanism == "gradient_map":
            return [tuple(int(v) for v in self.lut[i]) for i in (0, 64, 128, 192, 255)]
        return list(self.colors)


_RULES: dict = {}


def get_rule(theme_id: str) -> ThemeRule:
    """Cached ThemeRule for a theme id (unknown ids fall back to full_color)."""
    rule = _RULES.get(theme_id)
    if rule is None:
        rule = _RULES[theme_id] = ThemeRule(theme_id)
    return rule
