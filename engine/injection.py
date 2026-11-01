"""Deterministic injection batches (random positions and colours, origin injected)."""
from __future__ import annotations

import random
from dataclasses import replace

from contracts.definitions import InjectionBatch, State

from .mutations import ShapeFactory


def make_injection(factory: ShapeFactory, seed: int, count: int) -> InjectionBatch:
    """Same seed gives the same shapes. Colours are random, not target-informed. Ids are placeholders."""
    rng = random.Random(seed)
    shapes = tuple(factory.make(rng, i, 0.3, origin="injected", informed=False, max_size=0.3)
                   for i in range(max(0, int(count))))
    return InjectionBatch(seed=seed, shapes=shapes)


def apply_injection(state: State, batch: InjectionBatch) -> State:
    """Put the batch on top of the state with fresh shape ids (the shape limit does not apply)."""
    base = state.next_shape_id
    added = tuple(replace(s, shape_id=base + i, origin="injected") for i, s in enumerate(batch.shapes))
    return State(state.background, state.shapes + added, base + len(added))
