"""Live leaderboard: rank, who, similarity, which milestones were reached, rank changes."""
from __future__ import annotations

import pygame

from ui.compat import get
from ui.theme import draw_panel, draw_text, fit_text

MEDALS = [(242, 193, 46), (176, 184, 196), (205, 127, 50), (120, 130, 150)]   # gold, silver, bronze, other
LEVELS = (80, 90, 95)


class LeaderboardWidget:
    def __init__(self):
        self._flash: dict = {}            # panel -> [seconds_left, direction]

    def update(self, dt: float, entries: list) -> None:
        for e in entries:
            panel, change = get(e, "panel_index"), get(e, "rank_change", 0) or 0
            if change:                                           # someone moved: highlight the row
                self._flash[panel] = [1.5, 1 if change > 0 else -1]
        for panel in list(self._flash):
            self._flash[panel][0] -= dt
            if self._flash[panel][0] <= 0:
                del self._flash[panel]

    def draw(self, surface, rect, entries, names, skin, fonts) -> None:
        rect = pygame.Rect(rect)
        draw_panel(surface, skin, rect)
        draw_text(surface, fonts, "Leaderboard", (rect.x + 14, rect.y + 8), 16, skin.text, bold=True)
        y = rect.y + 34
        for e in entries[:4]:
            panel = get(e, "panel_index", 0)
            row = pygame.Rect(rect.x + 8, y, rect.width - 16, 34)
            flash = self._flash.get(panel)
            if flash:                                            # fade green (up) or red (down)
                tint = skin.good if flash[1] > 0 else skin.bad
                pygame.draw.rect(surface, tint, row, 2, border_radius=skin.corner_radius)
            rank = int(get(e, "rank", 1))
            pygame.draw.circle(surface, MEDALS[min(rank - 1, 3)], (row.x + 16, row.centery), 12)
            draw_text(surface, fonts, str(rank), (row.x + 16, row.centery), 15, (30, 30, 30), "center", bold=True)
            pygame.draw.rect(surface, skin.line_colors[panel % len(skin.line_colors)], (row.x + 36, row.y + 6, 5, 22),
                             border_radius=2)
            draw_text(surface, fonts, fit_text(fonts, names.get(panel, f"Panel {panel + 1}"), 15, 150),
                      (row.x + 48, row.centery), 15, skin.text, "midleft")
            draw_text(surface, fonts, f"{float(get(e, 'best_similarity', 0)):.1f}%", (row.right - 120, row.centery),
                      17, skin.text, "midright", bold=True)
            milestones = get(e, "milestones", {}) or {}
            for i, level in enumerate(LEVELS):                   # three tiny boxes: 80 / 90 / 95
                reached = level in milestones or str(level) in milestones
                box = pygame.Rect(row.right - 110 + i * 36, row.centery - 9, 32, 18)
                pygame.draw.rect(surface, skin.good if reached else skin.slider_track, box, border_radius=4)
                draw_text(surface, fonts, str(level), box.center, 11,
                          skin.accent_text if reached else skin.text_dim, "center", bold=reached)
            y += 36
