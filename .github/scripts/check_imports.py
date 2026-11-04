"""CI check: domain import rule (contract Section 4) and the no-Pygame rule."""

from __future__ import annotations

import ast
import sys
from pathlib import Path


PUBLIC = {
    "engine": {
        "create_problem": {"session"},
        "list_shape_types": {"ui"},
        "get_palette_swatches": {"ui"},
    },
    "session": {"create_session": {"ui"}, "list_algorithms": {"ui"}},
    "media": {
        "get_audio": {"ui"},
        "get_effects": {"ui"},
        "new_recorder": {"ui"},
        "save_run": {"ui"},
    },
    "ui": {"run_app": {"main"}},
    "algorithms": {},
}
NO_PYGAME = {"engine", "algorithms", "session"}


def domain_of(path: Path) -> str | None:
    """Return the domain a file belongs to, or None for tests, tools and contracts."""
    if path.name == "main.py" and len(path.parts) == 1:
        return "main"
    return path.parts[0] if path.parts and path.parts[0] in PUBLIC else None


def check_file(path: Path) -> list[str]:
    """Return the rule violations found in one file."""
    domain = domain_of(path)
    if domain is None:
        return []
    errors = []
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            targets = [(a.name, ()) for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            targets = [(node.module, tuple(a.name for a in node.names))]
        else:
            continue
        for module, names in targets:
            root = module.split(".")[0]
            if root == "pygame" and domain in NO_PYGAME:
                errors.append(f"{path}:{node.lineno}: {domain} must not import pygame")
            if root not in PUBLIC or root == domain:
                continue
            if domain == "session" and module == "algorithms":
                continue
            allowed = module == root and names and all(domain in PUBLIC[root].get(n, ()) for n in names)
            if not allowed:
                errors.append(f"{path}:{node.lineno}: {domain} may not import {module} {names}")
    return errors


def main() -> None:
    """Check every Python file under the repo root and exit 1 on violations."""
    errors = [e for p in sorted(Path(".").rglob("*.py")) for e in check_file(p)]
    print("\n".join(errors) or "import rules ok")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
