"""Routes a Command to the Session method that handles it."""

from __future__ import annotations

import logging
from typing import Any

from contracts.definitions import Command

log = logging.getLogger(__name__)


def apply_command(session: Any, command: Command) -> None:
    """Run the matching _cmd_<type> method; a bad command is logged, never raised."""
    handler = getattr(session, f"_cmd_{command.type}")
    try:
        handler(**command.payload)
    except (IndexError, KeyError, ValueError, TypeError):
        log.warning("ignored bad command %s %s", command.type, dict(command.payload))
