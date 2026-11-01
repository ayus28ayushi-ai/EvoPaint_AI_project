"""The ONE place where the UI touches other members' code.

Why this file exists: the UI must work before M1/M2/M4 have finished (and survive small
naming differences). Everything the UI needs from the outside goes through here:

  * get()              - read a field from an object OR a dict (contract objects may be either)
  * Command helpers    - build commands for Session.send (Contract 5.9)
  * RunConfig & friends- local copies with the contract's field names (Contract 5.3, 5.4)
  * parse_panel_info   - tolerant reader for Session.panel_info (key names not frozen)
  * load_backend()     - finds the real entry points (Contract 4), or falls back to fakes

If the kickoff contract differs from what is guessed here, EDIT THIS FILE ONLY.
"""
from __future__ import annotations

import importlib
import logging
from dataclasses import dataclass, field
from typing import Any, Callable

log = logging.getLogger("ui.compat")

# Frozen theme ids and display names (Contract 8)
THEMES = [
    ("full_color", "Full Color"), ("black_white", "Black and White"), ("sepia", "Sepia"),
    ("neon", "Neon"), ("pastel", "Pastel"), ("ocean", "Ocean"), ("sunset", "Sunset"),
    ("retro_8bit", "Retro 8-bit"),
]
SPEED_RANGE = (50.0, 10000.0)           # evaluations per second (Contract 2)
BUDGET_RANGE = (10000, 1000000)         # evaluations per panel (Contract 2)
MAX_PANELS = 4


# ------------------------------------------------------------------ tolerant field access
def get(obj: Any, name: str, default: Any = None) -> Any:
    """Read `name` from a dict or an object. Contract objects may be either."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _first(obj: Any, names: tuple, default: Any = None) -> Any:
    """First non-None value among several possible field names."""
    for n in names:
        value = get(obj, n)
        if value is not None:
            return value
    return default


# ------------------------------------------------------------------ spec dataclasses
@dataclass
class ParamSpec:                         # Contract 5.5 (used by the fakes)
    name: str
    label: str
    kind: str = "float"
    minimum: float = 0.0
    maximum: float = 1.0
    default: float = 0.0
    step: float = 0.0
    scale: str = "linear"
    group: str = "algorithm"
    help_text: str = ""
    options: list = field(default_factory=list)


@dataclass
class ActionSpec:
    name: str
    label: str
    help_text: str = ""


# ------------------------------------------------------------------ configuration objects
@dataclass
class ShapeConfig:                       # Contract 5.3
    mode: str = "random"                 # "random" or "chosen"
    allowed_types: list = field(default_factory=list)
    shape_limit: int = 300
    alpha_min: float = 0.2
    alpha_max: float = 1.0


@dataclass
class PanelConfig:                       # Contract 5.4
    algorithm_id: str = "hill_climbing"
    speed: float = 1000.0
    algorithm_params: dict = field(default_factory=dict)
    painting_params: dict = field(default_factory=dict)


@dataclass
class RunConfig:                         # Contract 5.4
    target_path: str = ""
    theme_id: str = "full_color"
    shape_config: ShapeConfig = field(default_factory=ShapeConfig)
    seed: int = 1
    max_evaluations: int = 200000
    panels: list = field(default_factory=list)


# ------------------------------------------------------------------ commands (Contract 5.9)
@dataclass
class Command:
    """`type` plus a payload. Payload keys are readable as attributes (command.panel)."""
    type: str
    payload: dict = field(default_factory=dict)

    def __getattr__(self, name):         # only called when normal lookup fails
        payload = self.__dict__.get("payload", {})
        if name in payload:
            return payload[name]
        raise AttributeError(name)


def make_command(kind: str, **payload) -> Command:
    """Build a command. If the real contract Command has another shape, change only this."""
    return Command(kind, payload)


# ------------------------------------------------------------------ navigation (Contract 6.4)
@dataclass
class Navigation:
    screen_id: str
    payload: Any = None


def parse_navigation(request: Any):
    """Turn whatever a screen returned into (screen_id, payload), or None."""
    if request is None:
        return None
    if isinstance(request, str):
        return request, None
    if isinstance(request, (tuple, list)) and request:
        return request[0], (request[1] if len(request) > 1 else None)
    screen_id = _first(request, ("screen_id", "target", "screen"))
    if screen_id is None:
        return None
    return screen_id, get(request, "payload")


# ------------------------------------------------------------------ panel info
@dataclass
class PanelInfo:
    algorithm_id: str = ""
    params: dict = field(default_factory=dict)       # current values by name (both groups)
    param_specs: list = field(default_factory=list)
    action_specs: list = field(default_factory=list)
    speed: float = 1000.0
    throttled: bool = False


def parse_panel_info(info: Any) -> PanelInfo:
    """Session.panel_info key names are not frozen, so accept the likely spellings.
    Suggested names to agree with M2: algorithm_id, param_values, param_specs,
    action_specs, speed, throttled."""
    return PanelInfo(
        algorithm_id=_first(info, ("algorithm_id", "algorithm", "id"), ""),
        params=dict(_first(info, ("param_values", "params", "parameters", "values"), {}) or {}),
        param_specs=list(_first(info, ("param_specs", "specs", "parameter_specs"), []) or []),
        action_specs=list(_first(info, ("action_specs", "actions"), []) or []),
        speed=float(_first(info, ("speed",), 1000.0)),
        throttled=bool(_first(info, ("throttled", "is_throttled"), False)),
    )


# ------------------------------------------------------------------ algorithm info
@dataclass
class AlgInfo:
    id: str
    display_name: str
    description: str = ""
    param_specs: list = field(default_factory=list)
    action_specs: list = field(default_factory=list)


def parse_algorithm_info(info: Any) -> AlgInfo:
    """Read one entry of list_algorithms() (Contract 4: id, display name, description,
    parameter specs, action specs). Field names are accepted in a few spellings."""
    algo_id = _first(info, ("id", "algorithm_id"), "")
    return AlgInfo(
        id=algo_id,
        display_name=_first(info, ("display_name", "name", "label"), algo_id),
        description=_first(info, ("description",), ""),
        param_specs=list(_first(info, ("param_specs", "specs"), []) or []),
        action_specs=list(_first(info, ("action_specs", "actions"), []) or []),
    )


# ------------------------------------------------------------------ backend loading
@dataclass
class Backend:
    """Every outside entry point the UI uses (Contract 4)."""
    create_session: Callable
    list_algorithms: Callable
    list_shape_types: Callable
    get_palette_swatches: Callable
    get_audio: Callable
    get_effects: Callable
    new_recorder: Callable
    save_run: Callable
    fakes_in_use: list = field(default_factory=list)   # which parts are stand-ins


def _try_import(package: str, name: str):
    try:
        return getattr(importlib.import_module(package), name)
    except (ImportError, AttributeError):
        return None


def load_backend(use_fakes: bool = False) -> Backend:
    """Use the real entry points when they exist, fakes otherwise (or when forced)."""
    from ui import dev_fakes as fk

    wanted = {   # name: (package, fallback)
        "create_session": ("session", fk.FakeSession),
        "list_algorithms": ("session", fk.fake_list_algorithms),
        "list_shape_types": ("engine", fk.fake_list_shape_types),
        "get_palette_swatches": ("engine", fk.fake_palette_swatches),
        "get_audio": ("media", fk.fake_get_audio),
        "get_effects": ("media", fk.fake_get_effects),
        "new_recorder": ("media", fk.fake_new_recorder),
        "save_run": ("media", fk.fake_save_run),
    }
    chosen, fakes = {}, []
    for name, (package, fallback) in wanted.items():
        real = None if use_fakes else _try_import(package, name)
        if real is None:
            fakes.append(name)
        chosen[name] = real or fallback
    if fakes:
        log.warning("UI is using stand-ins for: %s", ", ".join(fakes))
    return Backend(fakes_in_use=fakes, **chosen)
