"""Neighbour generation: add, move, resize, recolor, alpha, reorder, remove. Uses only the rng it is given."""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, replace

from contracts.definitions import Shape, State

from .palettes import ThemeRule


@dataclass(frozen=True)
class Mutation:
    """A planned change. `shape` is the new/changed shape, `index` the position it applies to."""

    kind: str
    index: int = -1
    shape: Shape | None = None
    to_index: int = -1


def _clamp(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else hi if v > hi else v


class ShapeFactory:
    """Creates random shapes according to the shape config, theme rule and painting parameters."""

    def __init__(self, kinds, rule: ThemeRule, target_arr, alpha_min: float, alpha_max: float) -> None:
        self.kinds, self.rule, self.target = tuple(kinds), rule, target_arr
        self.alpha_min, self.alpha_max = alpha_min, alpha_max
        self.max_shape_size = 0.5
        self.informed_colors = True

    def color_at(self, rng: random.Random, x: float, y: float, informed: bool) -> tuple:
        """Colour for a new shape: from the target at (x, y) if informed, else random, then palette-constrained."""
        if informed:
            h, w = self.target.shape[:2]
            px = self.target[min(h - 1, int(y * h)), min(w - 1, int(x * w))]
            return self.rule.constrain(int(px[0]), int(px[1]), int(px[2]))
        return self.rule.constrain(rng.randrange(256), rng.randrange(256), rng.randrange(256))

    def make(self, rng: random.Random, shape_id: int, step_scale: float, origin: str = "evolved",
             informed: bool | None = None, max_size: float | None = None) -> Shape:
        """One random shape. step_scale limits the size of new shapes (coarse to fine)."""
        informed = self.informed_colors if informed is None else informed
        kind = rng.choice(self.kinds)
        x, y = rng.random(), rng.random()
        top = (self.max_shape_size if max_size is None else max_size) * (0.25 + 0.75 * step_scale)
        size = 0.02 + max(0.0, top - 0.02) * rng.random() ** 2
        aspect = _clamp(math.exp(rng.gauss(0, 0.4)), 0.4, 2.5)
        rotation = rng.uniform(0, 180) if kind in ("rotated_rectangle", "pentagon") else 0.0
        points: tuple = ()
        if kind == "triangle":
            a0 = rng.uniform(0, 2 * math.pi)
            points = tuple((x + size * rng.uniform(0.6, 1.4) * math.cos(a0 + 2 * math.pi * i / 3),
                            y + size * rng.uniform(0.6, 1.4) * math.sin(a0 + 2 * math.pi * i / 3))
                           for i in range(3))
        elif kind == "line":
            a0 = rng.uniform(0, math.pi)
            dx, dy = size * math.cos(a0), size * math.sin(a0)
            points = ((x - dx, y - dy), (x + dx, y + dy))
            aspect = _clamp(aspect, 0.3, 3.0)
        r, g, b = self.color_at(rng, x, y, informed)
        alpha = 1.0 if self.rule.opaque else rng.uniform(self.alpha_min, self.alpha_max)
        return Shape(shape_id, kind, x, y, size, aspect, rotation, points, r, g, b, alpha, origin)


def _weights(n: int, can_add: bool, opaque: bool) -> list:
    if n == 0:
        return [("add", 1.0)]
    return [("add", (0.5 if n < 8 else 0.30) if can_add else 0.0), ("move", 0.18), ("resize", 0.18),
            ("recolor", 0.16), ("alpha", 0.0 if opaque else 0.08), ("reorder", 0.05 if n > 1 else 0.0),
            ("remove", 0.05)]


def plan_mutation(state: State, rng: random.Random, step_scale: float, factory: ShapeFactory,
                  shape_limit: int, max_shape_size: float) -> Mutation:
    """Choose and build one mutation of `state`."""
    n = len(state.shapes)
    table = _weights(n, n < shape_limit, factory.rule.opaque)
    pick = rng.random() * sum(w for _, w in table)
    kind = table[-1][0]
    for k, w in table:
        if pick < w:
            kind = k
            break
        pick -= w
    if kind == "add":
        return Mutation("add", n, factory.make(rng, state.next_shape_id, step_scale))
    i = rng.randrange(n)
    s = state.shapes[i]
    if kind == "remove":
        return Mutation("remove", i)
    if kind == "reorder":
        j = rng.randrange(n - 1)
        return Mutation("reorder", i, None, j + 1 if j >= i else j)
    if kind == "move":
        nx = _clamp(s.x + rng.gauss(0, 0.15 * step_scale), 0.0, 1.0)
        ny = _clamp(s.y + rng.gauss(0, 0.15 * step_scale), 0.0, 1.0)
        dx, dy = nx - s.x, ny - s.y
        pts = tuple((px + dx, py + dy) for px, py in s.points)
        return Mutation("move", i, replace(s, x=nx, y=ny, points=pts))
    if kind == "resize":
        f = math.exp(rng.gauss(0, 0.5 * step_scale))
        size = _clamp(s.size * f, 0.01, max(max_shape_size, s.size))
        f = size / s.size if s.size > 0 else 1.0
        pts = tuple((s.x + (px - s.x) * f + rng.gauss(0, 0.05 * step_scale * size),
                     s.y + (py - s.y) * f + rng.gauss(0, 0.05 * step_scale * size)) for px, py in s.points)
        aspect = _clamp(s.aspect * math.exp(rng.gauss(0, 0.3 * step_scale)), 0.25, 4.0)
        rot = (s.rotation + rng.gauss(0, 30 * step_scale)) % 360
        return Mutation("resize", i, replace(s, size=size, points=pts, aspect=aspect, rotation=rot))
    if kind == "recolor":
        pal = factory.rule.random_palette_color(rng)
        if pal is not None:
            r, g, b = pal
        else:
            sg = 60 * step_scale
            r, g, b = factory.rule.constrain(round(s.red + rng.gauss(0, sg)), round(s.green + rng.gauss(0, sg)),
                                             round(s.blue + rng.gauss(0, sg)))
        return Mutation("recolor", i, replace(s, red=r, green=g, blue=b))
    a = _clamp(s.alpha + rng.gauss(0, 0.3 * step_scale), factory.alpha_min, factory.alpha_max)
    return Mutation("alpha", i, replace(s, alpha=a))
