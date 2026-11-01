"""Toy Problem stub (owner: M1). A state holds K numbers (the x of K circles); cost is the squared
distance to a hidden target vector. Lets M2/M3/M4 develop and test without the real engine."""
from __future__ import annotations

import math
import random
from dataclasses import replace
from typing import Any

from PIL import Image, ImageDraw

from contracts.definitions import InjectionBatch, Problem, Proposal, Shape, State

K = 8


class ToyProblem(Problem):
    """Numeric stand-in for the painting engine."""

    def __init__(self, seed: int = 0, k: int = K) -> None:
        r = random.Random(seed)
        self.k = k
        self.hidden = [round(r.random(), 3) for _ in range(k)]

    def _mk(self, i: int, x: float) -> Shape:
        return Shape(i, "circle", x, 0.5, 0.05, 1.0, 0.0, (), 90, 140, 220, 1.0, "evolved")

    def initial_state(self) -> State:
        return State((240, 240, 240), tuple(self._mk(i, 0.5) for i in range(self.k)), self.k)

    def evaluate(self, state: State) -> float:
        err = sum((s.x - t) ** 2 for s, t in zip(state.shapes, self.hidden)) / self.k
        return err * 255.0 ** 2

    def propose(self, state: State, rng: random.Random, step_scale: float) -> Proposal:
        i = rng.randrange(len(state.shapes))
        x = min(1.0, max(0.0, state.shapes[i].x + rng.gauss(0, 0.2 * step_scale)))
        shapes = state.shapes[:i] + (replace(state.shapes[i], x=x),) + state.shapes[i + 1:]
        new = State(state.background, shapes, state.next_shape_id)
        return Proposal(new, self.evaluate(new), "move")

    def similarity(self, cost: float) -> float:
        return max(0.0, 100.0 * (1.0 - math.sqrt(max(cost, 0.0)) / 255.0))

    def _bars(self, values: list, size: int) -> Image.Image:
        img = Image.new("RGB", (size, size), (240, 240, 240))
        d = ImageDraw.Draw(img)
        bw = size / max(1, len(values))
        for i, v in enumerate(values):
            d.rectangle((i * bw + 2, size * (1 - v), (i + 1) * bw - 2, size), fill=(90, 140, 220))
        return img

    def render(self, state: State, size: int) -> Image.Image:
        return self._bars([s.x for s in state.shapes], int(size))

    def target_image(self, size: int) -> Image.Image:
        return self._bars(self.hidden, int(size))

    def make_injection(self, seed: int, count: int) -> InjectionBatch:
        r = random.Random(seed)
        return InjectionBatch(seed, tuple(self._mk(i, r.random()) for i in range(count)))

    def apply_injection(self, state: State, batch: InjectionBatch) -> State:
        shapes = tuple(replace(s, x=min(1.0, max(0.0, s.x + (batch.shapes[i % len(batch.shapes)].x - 0.5) * 0.5)),
                               origin="injected") for i, s in enumerate(state.shapes)) if batch.shapes else state.shapes
        return State(state.background, shapes, state.next_shape_id)

    def state_to_dict(self, state: State) -> dict:
        return {"background": list(state.background), "next_shape_id": state.next_shape_id,
                "xs": [s.x for s in state.shapes]}

    def state_from_dict(self, data: dict) -> State:
        return State(tuple(data["background"]), tuple(self._mk(i, x) for i, x in enumerate(data["xs"])),
                     data["next_shape_id"])

    def param_specs(self) -> list:
        return []

    def set_param(self, name: str, value: Any) -> None:
        return None

    def shape_count(self, state: State) -> int:
        return len(state.shapes)
