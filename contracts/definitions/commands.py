"""Commands sent to the Session (contract 5.9). Owner: M2.

Queued commands are applied at the start of the next tick, before advancing.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

COMMAND_TYPES = (
    "pause",
    "resume",
    "finish",
    "set_speed",
    "set_param",
    "trigger_action",
    "inject",
)

PARAM_GROUPS = ("algorithm", "painting")

REQUIRED_KEYS: dict[str, tuple[str, ...]] = {
    "set_speed": ("panel", "speed"),
    "set_param": ("panel", "group", "name", "value"),
    "trigger_action": ("panel", "action"),
}


@dataclass(frozen=True)
class Command:
    """A command type plus its payload. Validated on creation."""

    type: str
    payload: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Reject unknown types, missing keys and unknown parameter groups."""
        if self.type not in COMMAND_TYPES:
            raise ValueError(f"unknown command type: {self.type!r}")
        required = REQUIRED_KEYS.get(self.type, ())
        missing = [k for k in required if k not in self.payload]
        if missing:
            raise ValueError(f"{self.type} is missing payload keys: {missing}")
        if self.type == "set_param" and self.payload["group"] not in PARAM_GROUPS:
            raise ValueError(f"unknown parameter group: {self.payload['group']!r}")


def pause() -> Command:
    """Build a pause command."""
    return Command("pause")


def resume() -> Command:
    """Build a resume command."""
    return Command("resume")


def finish() -> Command:
    """Build a finish command."""
    return Command("finish")


def set_speed(panel: int, speed: float) -> Command:
    """Build a set_speed command."""
    return Command("set_speed", {"panel": panel, "speed": speed})


def set_param(panel: int, group: str, name: str, value: Any) -> Command:
    """Build a set_param command."""
    payload = {"panel": panel, "group": group, "name": name, "value": value}
    return Command("set_param", payload)


def trigger_action(panel: int, action: str) -> Command:
    """Build a trigger_action command."""
    return Command("trigger_action", {"panel": panel, "action": action})


def inject(count: int = 50, panels: str | list[int] = "all") -> Command:
    """Build an inject command; panels is "all" or a list of panel indexes."""
    return Command("inject", {"count": count, "panels": panels})
