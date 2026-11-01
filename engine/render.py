"""Off-screen rendering with Pillow. Shapes are composited in order, only inside the region asked for."""
from __future__ import annotations

from functools import lru_cache

import numpy as np
from PIL import Image, ImageDraw

from contracts.definitions import WORKING_SIZE, State

from .shapes import geometry

try:  # Pillow >= 9.1
    _BOX = Image.Resampling.BOX
except AttributeError:  # pragma: no cover
    _BOX = Image.BOX


def _make_mask(s, w: int):
    """Rasterise one shape in its own fixed frame (its full clipped bounding box) -> (mask, bbox) or None.

    Using one fixed frame per shape makes region renders identical to full renders.
    """
    g = geometry(s, w)
    if g is None:
        return None
    draw, coords, width, bb = g
    fill = int(round(min(1.0, max(0.0, s.alpha)) * 255))
    if fill <= 0:
        return None
    ox, oy = bb[0], bb[1]
    mask = Image.new("L", (bb[2] - ox, bb[3] - oy), 0)
    d = ImageDraw.Draw(mask)
    if draw == "ellipse":
        d.ellipse((coords[0] - ox, coords[1] - oy, coords[2] - ox, coords[3] - oy), fill=fill)
    elif draw == "polygon":
        d.polygon([(px - ox, py - oy) for px, py in coords], fill=fill)
    else:
        d.line([(px - ox, py - oy) for px, py in coords], fill=fill, width=width)
    return mask, bb


_cached_mask = lru_cache(maxsize=16384)(_make_mask)  # used for the working size, where shapes are re-drawn often


def paint_region(shapes, bg, w: int, region, indices=None, base: np.ndarray | None = None) -> Image.Image:
    """Render `region` (x0, y0, x1, y1) of the painting. `indices` limits which shapes are drawn.

    If `base` (a uint8 array of the region) is given, shapes are drawn on top of it instead of the background.
    """
    x0, y0, x1, y1 = region
    if base is None:
        crop = Image.new("RGB", (x1 - x0, y1 - y0), tuple(bg))
    else:
        crop = Image.fromarray(np.ascontiguousarray(base))
    make = _cached_mask if w == WORKING_SIZE else _make_mask
    for i in (range(len(shapes)) if indices is None else indices):
        s = shapes[i]
        got = make(s, w)
        if got is None:
            continue
        mask, bb = got
        ix0, iy0, ix1, iy1 = max(bb[0], x0), max(bb[1], y0), min(bb[2], x1), min(bb[3], y1)
        if ix0 >= ix1 or iy0 >= iy1:
            continue
        if (ix0, iy0, ix1, iy1) != bb:
            mask = mask.crop((ix0 - bb[0], iy0 - bb[1], ix1 - bb[0], iy1 - bb[1]))
        crop.paste((s.red, s.green, s.blue), (ix0 - x0, iy0 - y0, ix1 - x0, iy1 - y0), mask)
    return crop


def render_state(state: State, size: int, working_size: int) -> Image.Image:
    """Render a whole state at `size`. Sizes other than the working size are supersampled 2x for smooth edges."""
    ss = 1 if (size == working_size or size > 1024) else 2
    w = size * ss
    img = paint_region(state.shapes, state.background, w, (0, 0, w, w))
    return img.resize((size, size), _BOX) if ss > 1 else img
