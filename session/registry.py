"""Finds algorithms by scanning the algorithms/ folder."""

from __future__ import annotations

import importlib
import inspect
import logging
import pkgutil

import algorithms
from contracts.definitions import Algorithm, AlgorithmInfo

log = logging.getLogger(__name__)


def find_algorithms() -> dict[str, type[Algorithm]]:
    """Return every Algorithm class in algorithms/, keyed by id."""
    found: dict[str, type[Algorithm]] = {}
    for info in pkgutil.iter_modules(algorithms.__path__):
        try:
            module = importlib.import_module(f"algorithms.{info.name}")
        except Exception:
            log.exception("could not import algorithms.%s", info.name)
            continue
        for _, cls in inspect.getmembers(module, inspect.isclass):
            if issubclass(cls, Algorithm) and cls.__module__ == module.__name__:
                found[cls.id] = cls
    return found


def get_algorithm(algorithm_id: str) -> type[Algorithm]:
    """Return the class for an id, or raise KeyError listing the known ids."""
    found = find_algorithms()
    if algorithm_id not in found:
        raise KeyError(f"unknown algorithm {algorithm_id!r}; known: {sorted(found)}")
    return found[algorithm_id]


def list_algorithms() -> list[AlgorithmInfo]:
    """Return one AlgorithmInfo per algorithm, sorted by id."""
    return [
        AlgorithmInfo(
            cls.id,
            cls.display_name,
            cls.description,
            tuple(cls.param_specs()),
            tuple(cls.action_specs()),
        )
        for _, cls in sorted(find_algorithms().items())
    ]
