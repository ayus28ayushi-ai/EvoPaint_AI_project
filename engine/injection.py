from __future__ import annotations

import random
from dataclasses import replace

from contracts.definitions import InjectionBatch, State

from .mutations import ShapeFactory


def make_injection(factory: ShapeFactory, seed: int, count: int) -> InjectionBatch:
    rng = random.Random(seed)
    shapes = tuple(factory.make(rng, i, 0.3, origin="injected", informed=False, max_size=0.3)
                   for i in range(max(0, int(count))))
    return InjectionBatch(seed=seed, shapes=shapes)


def apply_injection(state: State, batch: InjectionBatch) -> State:
    base = state.next_shape_id
    added = tuple(replace(s, shape_id=base + i, origin="injected") for i, s in enumerate(batch.shapes))
    return State(state.background, state.shapes + added, base + len(added))
