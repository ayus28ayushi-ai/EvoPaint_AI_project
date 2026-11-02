"""A tiny numeric Problem for tests: a state is 8 gray values to match a target."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Any

from PIL import Image

from contracts.definitions import ParamSpec

SIZE = 8


@dataclass(frozen=True)
class Proposal:
    state: tuple[float, ...]
    cost: float
    kind: str


class ToyProblem:
    """Implements the Problem methods that Session and algorithms use."""

    def __init__(self, seed: int = 1) -> None:
        rng = random.Random(seed)
        self._target = tuple(rng.uniform(0, 255) for _ in range(SIZE))
        self.painting: dict[str, Any] = {}

    def initial_state(self) -> tuple[float, ...]:
        return (128.0,) * SIZE

    def evaluate(self, state: tuple[float, ...]) -> float:
        return sum((a - b) ** 2 for a, b in zip(state, self._target)) / SIZE

    def similarity(self, cost: float) -> float:
        return 100.0 * (1.0 - math.sqrt(max(cost, 0.0)) / 255.0)

    def propose(self, state: tuple[float, ...], rng: random.Random, step_scale: float) -> Proposal:
        i = rng.randrange(SIZE)
        value = min(255.0, max(0.0, state[i] + rng.gauss(0, 1) * step_scale * 80))
        new = state[:i] + (value,) + state[i + 1 :]
        return Proposal(new, self.evaluate(new), "move")

    def make_injection(self, seed: int, count: int) -> tuple[tuple[int, float], ...]:
        rng = random.Random(seed)
        return tuple((rng.randrange(SIZE), rng.uniform(0, 255)) for _ in range(min(count, SIZE)))

    def apply_injection(self, state: tuple[float, ...], batch: Any) -> tuple[float, ...]:
        values = list(state)
        for i, v in batch:
            values[i] = v
        return tuple(values)

    def render(self, state: tuple[float, ...], size: int) -> Image.Image:
        return Image.new("L", (size, size), int(sum(state) / SIZE))

    def target_image(self, size: int) -> Image.Image:
        return self.render(self._target, size)

    def param_specs(self) -> list[ParamSpec]:
        return [
            ParamSpec(
                name="max_shape_size", label="Max shape size", kind="float",
                minimum=0.05, maximum=0.8, default=0.5, group="painting",
            )
        ]

    def set_param(self, name: str, value: Any) -> None:
        self.painting[name] = value

    def state_to_dict(self, state: tuple[float, ...]) -> dict:
        return {"values": list(state)}

    def state_from_dict(self, data: dict) -> tuple[float, ...]:
        return tuple(data["values"])

    def shape_count(self, state: tuple[float, ...]) -> int:
        return len(state)
