from __future__ import annotations

from contracts.definitions import SHAPE_KINDS, Problem, ShapeConfig

from .palettes import get_rule
from .problem import PaintingProblem

_DISPLAY = {"circle": "Circle", "ellipse": "Ellipse", "triangle": "Triangle", "rectangle": "Rectangle",
            "rotated_rectangle": "Rotated rectangle", "pentagon": "Pentagon", "line": "Line stroke"}


def create_problem(image_path: str, shape_config: ShapeConfig, theme_id: str, seed: int) -> Problem:
    return PaintingProblem(image_path, shape_config, theme_id, seed)


def list_shape_types() -> list:
    return [(k, _DISPLAY[k]) for k in SHAPE_KINDS]


def get_palette_swatches(theme_id: str) -> list:
    return get_rule(theme_id).swatches()


__all__ = ["create_problem", "list_shape_types", "get_palette_swatches"]
