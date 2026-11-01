"""Shared Problem conformance checks (owner: M1). Each check takes a zero-argument factory returning a
fresh Problem and raises AssertionError on failure. Run via tests/engine/test_engine_conformance.py."""
from __future__ import annotations

import copy
import math
import pickle
import random

from contracts.definitions import Problem, Proposal, State

KINDS = {"add", "move", "resize", "recolor", "alpha", "reorder", "remove"}


def _walk(p: Problem, n: int = 60, seed: int = 3):
    rng, s = random.Random(seed), p.initial_state()
    c = p.evaluate(s)
    for _ in range(n):
        pr = p.propose(s, rng, 0.3)
        if pr.cost < c:
            s, c = pr.state, pr.cost
    return s


def check_initial_state(make) -> None:
    p = make()
    s = p.initial_state()
    assert isinstance(s, State) and len(s.background) == 3
    assert p.shape_count(s) == 0 or p.shape_count(s) >= 0
    assert p.evaluate(s) >= 0


def check_deterministic(make) -> None:
    a, b = make(), make()
    sa, sb = a.initial_state(), b.initial_state()
    ra, rb = random.Random(11), random.Random(11)
    for _ in range(30):
        pa, pb = a.propose(sa, ra, 0.3), b.propose(sb, rb, 0.3)
        assert pa.cost == pb.cost and pa.kind == pb.kind and pa.state == pb.state
        sa, sb = pa.state, pb.state


def check_input_never_edited(make) -> None:
    p = make()
    s = _walk(p)
    before = copy.deepcopy(s)
    rng = random.Random(2)
    for _ in range(40):
        pr = p.propose(s, rng, 0.5)
        assert isinstance(pr, Proposal) and pr.kind in KINDS
    assert s == before


def check_similarity_formula(make) -> None:
    p = make()
    assert p.similarity(0.0) == 100.0
    for c in (1.0, 100.0, 5000.0, 65025.0):
        assert abs(p.similarity(c) - 100.0 * (1.0 - math.sqrt(c) / 255.0)) < 1e-9


def check_injection_deterministic(make) -> None:
    a, b = make(), make()
    assert a.make_injection(5, 20) == b.make_injection(5, 20)
    assert a.make_injection(5, 20) != a.make_injection(6, 20)
    assert len(a.make_injection(5, 20).shapes) == 20


def check_injection_applies(make) -> None:
    p = make()
    s = _walk(p)
    batch = p.make_injection(9, 10)
    t = p.apply_injection(s, batch)
    assert t is not s and p.evaluate(t) >= 0
    assert any(sh.origin == "injected" for sh in t.shapes), "injected shapes must be marked origin=injected"
    ids = [sh.shape_id for sh in t.shapes]
    assert len(ids) == len(set(ids)), "shape ids must stay unique"


def check_roundtrip(make) -> None:
    p = make()
    s = _walk(p)
    t = p.state_from_dict(p.state_to_dict(s))
    assert abs(p.evaluate(t) - p.evaluate(s)) < 1e-9


def check_picklable_state(make) -> None:
    p = make()
    s = _walk(p)
    assert pickle.loads(pickle.dumps(s)) == s


def check_render_and_target(make) -> None:
    p = make()
    s = _walk(p)
    for size in (96, 256):
        assert p.render(s, size).size == (size, size)
        assert p.target_image(size).size == (size, size)


ALL_CHECKS = [check_initial_state, check_deterministic, check_input_never_edited, check_similarity_formula,
              check_injection_deterministic, check_injection_applies, check_roundtrip, check_picklable_state,
              check_render_and_target]
