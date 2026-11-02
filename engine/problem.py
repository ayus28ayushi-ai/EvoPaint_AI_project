"""PaintingProblem: the engine's implementation of the Problem contract (6.1).

Speed: every state that passes through the engine keeps its rendered canvas, its exact integer error
and its shape bounding boxes in a small cache. A neighbour is then scored by re-rendering only the
region that changed, and the result equals a full evaluation exactly (tests check this).
"""
from __future__ import annotations

import logging
import random
from collections import OrderedDict
from typing import Any

import numpy as np
from PIL import Image

from contracts.definitions import (SHAPE_KINDS, WORKING_SIZE, InjectionBatch, ParamSpec, Problem, Proposal,
                                   Shape, ShapeConfig, State)

from . import injection as _inj
from .cost import cost_from_sse, similarity_from_cost, sse
from .mutations import Mutation, ShapeFactory, plan_mutation
from .palettes import get_rule
from .render import paint_region, render_state
from .shapes import bbox_row

log = logging.getLogger(__name__)
W = WORKING_SIZE
_CACHE_SIZE = 64
try:
    _LANCZOS = Image.Resampling.LANCZOS
except AttributeError:  # pragma: no cover
    _LANCZOS = Image.LANCZOS


class _Entry:
    """Cached render of one state: canvas array, exact integer error, bounding boxes."""

    __slots__ = ("state", "arr", "sse", "bb")

    def __init__(self, state: State, arr: np.ndarray, err: int, bb: np.ndarray) -> None:
        self.state, self.arr, self.sse, self.bb = state, arr, err, bb


def _union(*rows) -> tuple | None:
    rows = [r for r in rows if r[2] > r[0] and r[3] > r[1]]
    if not rows:
        return None
    return (min(r[0] for r in rows), min(r[1] for r in rows), max(r[2] for r in rows), max(r[3] for r in rows))


class PaintingProblem(Problem):
    """Evolving-painting problem for one target image, one theme and one shape configuration."""

    def __init__(self, image_path: str, shape_config: ShapeConfig, theme_id: str, seed: int) -> None:
        self.seed, self.config, self.rule = seed, shape_config, get_rule(theme_id)
        kinds = shape_config.allowed_types if shape_config.mode == "chosen" else SHAPE_KINDS
        kinds = [k for k in kinds if k in SHAPE_KINDS] or list(SHAPE_KINDS)
        with Image.open(image_path) as im:
            im = im.convert("RGB")
            side = min(im.size)
            left, top = (im.width - side) // 2, (im.height - side) // 2
            crop = im.crop((left, top, left + side, top + side))
        self._crop = crop.resize((512, 512), _LANCZOS) if side != 512 else crop.copy()
        self._targets: dict = {}
        self._target96 = self._processed(W)
        self._t32 = self._target96.astype(np.int32)
        self._npix = W * W * 3
        self._shape_limit = int(shape_config.shape_limit)
        self._factory = ShapeFactory(kinds, self.rule, self._target96, shape_config.alpha_min, shape_config.alpha_max)
        self._cache: OrderedDict = OrderedDict()

    def __getstate__(self) -> dict:
        d = dict(self.__dict__)
        d["_cache"] = OrderedDict()
        return d

    # ---- target -------------------------------------------------------------------------------
    def _processed(self, size: int) -> np.ndarray:
        arr = self._targets.get(size)
        if arr is None:
            img = self._crop if size == 512 else self._crop.resize((size, size), _LANCZOS)
            arr = self._targets[size] = np.ascontiguousarray(self.rule.process_array(np.asarray(img, dtype=np.uint8)))
        return arr

    def target_image(self, size: int) -> Image.Image:
        """The processed target (palette rule applied) at the requested size."""
        return Image.fromarray(self._processed(int(size)))

    # ---- contract -----------------------------------------------------------------------------
    def initial_state(self) -> State:
        """Background = average colour of the processed target, no shapes."""
        avg = self._target96.reshape(-1, 3).mean(axis=0)
        return State(tuple(int(round(v)) for v in avg), (), 0)

    def similarity(self, cost: float) -> float:
        """100 * (1 - sqrt(cost) / 255)."""
        return similarity_from_cost(cost)

    def evaluate(self, state: State) -> float:
        """Cost of a state (uses the cache when the state was seen before)."""
        return cost_from_sse(self._entry(state).sse, self._npix)

    def evaluate_full(self, state: State) -> float:
        """Always renders from scratch (used by tests to verify the incremental path)."""
        return cost_from_sse(self._full_entry(state).sse, self._npix)

    def propose(self, state: State, rng: random.Random, step_scale: float) -> Proposal:
        """One neighbour of `state` with its exact cost. Never edits `state`."""
        parent = self._entry(state)
        mut = plan_mutation(state, rng, step_scale, self._factory, self._shape_limit, self._factory.max_shape_size)
        new_state, entry = self._apply(parent, mut)
        self._remember(entry)
        return Proposal(new_state, cost_from_sse(entry.sse, self._npix), mut.kind)

    def render(self, state: State, size: int) -> Image.Image:
        """Pillow image of the painting at `size` pixels."""
        return render_state(state, int(size), W)

    def make_injection(self, seed: int, count: int) -> InjectionBatch:
        """Deterministic intruder shapes for (seed, count)."""
        f = ShapeFactory(self._factory.kinds, self.rule, self._target96, self.config.alpha_min, self.config.alpha_max)
        return _inj.make_injection(f, seed, count)

    def apply_injection(self, state: State, batch: InjectionBatch) -> State:
        """Add the batch on top of the state."""
        return _inj.apply_injection(state, batch)

    def shape_count(self, state: State) -> int:
        """Number of shapes."""
        return len(state.shapes)

    def state_to_dict(self, state: State) -> dict:
        """Plain dict (JSON friendly)."""
        shapes = [{"shape_id": s.shape_id, "kind": s.kind, "x": s.x, "y": s.y, "size": s.size, "aspect": s.aspect,
                   "rotation": s.rotation, "points": [list(p) for p in s.points], "red": s.red, "green": s.green,
                   "blue": s.blue, "alpha": s.alpha, "origin": s.origin} for s in state.shapes]
        return {"background": list(state.background), "next_shape_id": state.next_shape_id, "shapes": shapes}

    def state_from_dict(self, data: dict) -> State:
        """Inverse of state_to_dict."""
        shapes = tuple(Shape(d["shape_id"], d["kind"], d["x"], d["y"], d["size"], d["aspect"], d["rotation"],
                             tuple(tuple(p) for p in d["points"]), d["red"], d["green"], d["blue"], d["alpha"],
                             d["origin"]) for d in data["shapes"])
        return State(tuple(data["background"]), shapes, data.get("next_shape_id", 0))

    def param_specs(self) -> list:
        """Painting-group parameters (Section 7)."""
        return [
            ParamSpec("shape_limit", "Shape limit", "int", 10, 1000, self.config.shape_limit, 10, "linear",
                      "painting", "Maximum number of shapes in the painting."),
            ParamSpec("max_shape_size", "Max shape size", "float", 0.05, 0.8, 0.5, 0.01, "linear", "painting",
                      "Largest size of a new shape as a fraction of the image width."),
            ParamSpec("informed_colors", "Informed colors", "bool", None, None, True, None, "linear", "painting",
                      "New shapes take their colour from the target at their position."),
        ]

    def set_param(self, name: str, value: Any) -> None:
        """Live change of a painting parameter."""
        if name == "shape_limit":
            self._shape_limit = int(min(1000, max(10, value)))
        elif name == "max_shape_size":
            self._factory.max_shape_size = float(min(0.8, max(0.05, value)))
        elif name == "informed_colors":
            self._factory.informed_colors = bool(value)
        else:
            log.warning("unknown painting parameter %r ignored", name)

    # ---- cache and incremental evaluation -----------------------------------------------------
    def _bb_array(self, shapes) -> np.ndarray:
        if not shapes:
            return np.zeros((0, 4), dtype=np.int32)
        return np.array([bbox_row(s, W) for s in shapes], dtype=np.int32)

    def _full_entry(self, state: State) -> _Entry:
        img = paint_region(state.shapes, state.background, W, (0, 0, W, W))
        arr = np.array(img, dtype=np.uint8)
        return _Entry(state, arr, sse(arr, self._t32), self._bb_array(state.shapes))

    def _remember(self, entry: _Entry) -> None:
        self._cache[id(entry.state)] = entry
        if len(self._cache) > _CACHE_SIZE:
            self._cache.popitem(last=False)

    def _entry(self, state: State) -> _Entry:
        e = self._cache.get(id(state))
        if e is not None and e.state is state:
            self._cache.move_to_end(id(state))
            return e
        e = self._full_entry(state)
        self._remember(e)
        return e

    def _apply(self, p: _Entry, m: Mutation) -> tuple:
        """Build the neighbour state and its cache entry by re-rendering only the changed region."""
        st, shapes, bb, k = p.state, p.state.shapes, p.bb, m.kind
        next_id = st.next_shape_id
        base_only = False
        if k == "add":
            row = bbox_row(m.shape, W)
            new_shapes, new_bb = shapes + (m.shape,), np.concatenate([bb, np.array([row], dtype=np.int32)])
            region, base_only, next_id = _union(row), True, next_id + 1
        elif k in ("move", "resize", "recolor", "alpha"):
            i = m.index
            row = bbox_row(m.shape, W)
            new_shapes, new_bb = shapes[:i] + (m.shape,) + shapes[i + 1:], bb.copy()
            new_bb[i] = row
            region = _union(tuple(bb[i]), row)
        elif k == "remove":
            i = m.index
            new_shapes, new_bb = shapes[:i] + shapes[i + 1:], np.delete(bb, i, axis=0)
            region = _union(tuple(bb[i]))
        else:  # reorder
            i, j = m.index, m.to_index
            order = list(range(len(shapes)))
            order.insert(j, order.pop(i))
            new_shapes, new_bb = tuple(shapes[t] for t in order), bb[order]
            region = _union(tuple(bb[i]))
        new_state = State(st.background, new_shapes, next_id)
        if region is None:  # nothing visible changed
            return new_state, _Entry(new_state, p.arr, p.sse, new_bb)
        x0, y0, x1, y1 = region
        if base_only:
            crop = paint_region(new_shapes, st.background, W, region, [len(new_shapes) - 1], base=p.arr[y0:y1, x0:x1])
        else:
            hit = np.nonzero((new_bb[:, 0] < x1) & (new_bb[:, 2] > x0) & (new_bb[:, 1] < y1) & (new_bb[:, 3] > y0)
                             & (new_bb[:, 2] > new_bb[:, 0]))[0]
            crop = paint_region(new_shapes, st.background, W, region, hit.tolist())
        patch = np.asarray(crop)
        arr = p.arr.copy()
        arr[y0:y1, x0:x1] = patch
        tgt = self._t32[y0:y1, x0:x1]
        err = p.sse - sse(p.arr[y0:y1, x0:x1], tgt) + sse(patch, tgt)
        return new_state, _Entry(new_state, arr, err, new_bb)
