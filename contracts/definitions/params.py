from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ParamSpec:

    name: str
    label: str
    kind: str  # float, int, bool or choice
    minimum: Any = None
    maximum: Any = None
    default: Any = None
    step: Any = None
    scale: str = "linear"  # linear or log
    group: str = "algorithm"  # algorithm or painting
    help_text: str = ""
    options: tuple = ()  # for kind == "choice"


@dataclass(frozen=True)
class ActionSpec:

    name: str
    label: str
    help_text: str = ""
