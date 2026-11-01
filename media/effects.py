"""Simple visual effects – confetti / glow on milestones."""

from __future__ import annotations

import random
from typing import Any

try:
    import pygame
except ImportError:
    pygame = None  # type: ignore


class Particle:
    def __init__(self, x: float, y: float, color: tuple[int, int, int]):
        self.x = x
        self.y = y
        self.vx = random.uniform(-3, 3)
        self.vy = random.uniform(-8, -2)
        self.life = random.uniform(0.8, 1.6)
        self.color = color
        self.size = random.randint(3, 7)

    def update(self, dt: float) -> bool:
        self.x += self.vx
        self.y += self.vy
        self.vy += 12 * dt  # gravity
        self.life -= dt
        return self.life > 0


class Effects:
    """Minimal Effects object that satisfies the contract."""

    def __init__(self) -> None:
        self.particles: list[Particle] = []
        self._theme_id = "full_color"
        self._colors = [
            (255, 80, 80),
            (80, 255, 120),
            (80, 160, 255),
            (255, 220, 60),
            (220, 100, 255),
        ]

    def on_event(self, event: Any, panel_rect: tuple[int, int, int, int] | None = None) -> None:
        """Spawn confetti when a milestone is reached."""
        etype = getattr(event, "type", None) or (event.get("type") if isinstance(event, dict) else None)
        if etype != "milestone_reached":
            return

        if panel_rect is None:
            # fallback centre of screen
            cx, cy = 400, 300
            w, h = 200, 200
        else:
            x, y, w, h = panel_rect
            cx, cy = x + w // 2, y + h // 2

        level = getattr(event, "level", 80)
        count = 25 if level < 90 else (40 if level < 95 else 60)

        for _ in range(count):
            color = random.choice(self._colors)
            self.particles.append(Particle(cx + random.randint(-w // 3, w // 3), cy, color))

    def update(self, seconds: float) -> None:
        dt = max(0.001, min(seconds, 0.05))
        self.particles = [p for p in self.particles if p.update(dt)]

    def draw(self, surface: Any) -> None:
        if pygame is None or not self.particles:
            return
        for p in self.particles:
            alpha = max(0, min(255, int(255 * p.life)))
            # simple filled circle
            try:
                pygame.draw.circle(surface, p.color, (int(p.x), int(p.y)), p.size)
            except Exception:
                pass

    def clear(self) -> None:
        self.particles.clear()

    def set_theme(self, theme_id: str) -> None:
        self._theme_id = theme_id


_effects_instance: Effects | None = None


def get_effects() -> Effects:
    """Public entry point."""
    global _effects_instance
    if _effects_instance is None:
        _effects_instance = Effects()
    return _effects_instance
