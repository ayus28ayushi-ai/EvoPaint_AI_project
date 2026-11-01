"""Shape geometry: turns a Shape into integer pixel geometry plus a clipped bounding box."""
from __future__ import annotations

import math
from functools import lru_cache

from contracts.definitions import Shape


@lru_cache(maxsize=32768)
def geometry(shape: Shape, w: int):
    """Return (draw_kind, coords, line_width, bbox) for a canvas of w pixels, or None if invisible.

    draw_kind is ellipse, polygon or line. Coordinates are integers so rasterisation is identical
    whether a whole image or only a region is drawn. bbox is (x0, y0, x1, y1), end exclusive, clipped.
    """
    k, cx, cy, r = shape.kind, shape.x * w, shape.y * w, shape.size * w
    width = 0
    if k in ("circle", "ellipse"):
        s = math.sqrt(max(shape.aspect, 1e-3)) if k == "ellipse" else 1.0
        hw, hh = r * s, r / s
        box = (round(cx - hw), round(cy - hh), round(cx + hw), round(cy + hh))
        draw, coords = "ellipse", box
        xs, ys = (box[0], box[2]), (box[1], box[3])
    else:
        if k in ("rectangle", "rotated_rectangle"):
            s = math.sqrt(max(shape.aspect, 1e-3))
            hw, hh = r * s, r / s
            a = math.radians(shape.rotation if k == "rotated_rectangle" else 0.0)
            ca, sa = math.cos(a), math.sin(a)
            pts = [(cx + dx * ca - dy * sa, cy + dx * sa + dy * ca)
                   for dx, dy in ((-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh))]
        elif k == "pentagon":
            a0 = math.radians(shape.rotation) - math.pi / 2
            pts = [(cx + r * math.cos(a0 + 2 * math.pi * i / 5), cy + r * math.sin(a0 + 2 * math.pi * i / 5))
                   for i in range(5)]
        elif k in ("triangle", "line"):
            pts = [(px * w, py * w) for px, py in shape.points]
            if k == "line":
                width = max(1, round(0.12 * shape.size * shape.aspect * w))
        else:
            return None
        coords = tuple((round(px), round(py)) for px, py in pts)
        draw = "line" if k == "line" else "polygon"
        xs, ys = [p[0] for p in coords], [p[1] for p in coords]
    pad = width // 2 + 1 if draw == "line" else 0
    x0, x1 = max(0, min(xs) - pad), min(w, max(xs) + 1 + pad)
    y0, y1 = max(0, min(ys) - pad), min(w, max(ys) + 1 + pad)
    if x0 >= x1 or y0 >= y1:
        return None
    return draw, coords, width, (x0, y0, x1, y1)


def bbox_row(shape: Shape, w: int) -> tuple:
    """Bounding box of a shape or (0, 0, 0, 0) when it is invisible."""
    g = geometry(shape, w)
    return g[3] if g else (0, 0, 0, 0)
