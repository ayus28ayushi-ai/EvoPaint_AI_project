"""Frozen data and interface definitions (contract v1.0)."""
from .algorithm import Algorithm
from .params import ActionSpec, ParamSpec
from .problem import (
    MUTATION_KINDS,
    SHAPE_KINDS,
    WORKING_SIZE,
    InjectionBatch,
    Problem,
    Proposal,
    Shape,
    ShapeConfig,
    State,
)
from .snapshot import Snapshot

__all__ = [
    "Algorithm", "ActionSpec", "ParamSpec", "Problem", "Proposal", "Shape", "ShapeConfig",
    "State", "InjectionBatch", "Snapshot", "SHAPE_KINDS", "MUTATION_KINDS", "WORKING_SIZE",
]
