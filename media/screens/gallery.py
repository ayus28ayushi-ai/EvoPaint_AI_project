from __future__ import annotations
from typing import Any
from pathlib import Path

try:
    import pygame
except ImportError:
    pygame = None

from media.gallery import delete_run, list_runs


class GalleryScreen:
    screen_id = "gallery"
    ICON = 140         # thumbnail size
    PAD = 18
    ROW_H = 170

    def __init__(self) -> None:
        self.runs = list_runs()
        self.selected = 0
        self._thumbs: dict[str, Any] = {}   # run_id -> pygame surface

    def on_enter(self, payload=None) -> None:
        self.runs = list_runs()
        self.selected = min(self.selected, max(0, len(self.runs) - 1))
        self._thumbs.clear()

    def _thumb(self, run: dict) -> Any:
        """Load and cache a thumbnail surface."""
        rid = run["run_id"]
        if rid in self._thumbs:
            return self._thumbs[rid]
        path = run.get("thumb")
        surf = None
        if path and Path(path).exists() and pygame:
            try:
                img = pygame.image.load(str(path)).convert()
                surf = pygame.transform.smoothscale(img, (self.ICON, self.ICON))
            except Exception:
                pass
        self._thumbs[rid] = surf
        return surf

    def handle_events(self, events: list) -> dict | None:
        if pygame is None:
            return None
        for e in events:
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    return {"target": "home", "payload": None}
                if e.key in (pygame.K_RIGHT, pygame.K_d, pygame.K_DOWN, pygame.K_s):
                    self.selected = min(self.selected + 1, max(0, len(self.runs) - 1))
                if e.key in (pygame.K_LEFT, pygame.K_a, pygame.K_UP, pygame.K_w):
                    self.selected = max(self.selected - 1, 0)
                if e.key == pygame.K_RETURN and self.runs:
                    return {"target": "entry", "payload": {"run_id": self.runs[self.selected]["run_id"]}}
                if e.key == pygame.K_DELETE and self.runs:
                    delete_run(self.runs[self.selected]["run_id"])
                    self.runs = list_runs()
                    self.selected = min(self.selected, max(0, len(self.runs) - 1))
                    self._thumbs.clear()
        return None

    def update(self, dt: float) -> None:
        pass

    def draw(self, surface: Any) -> None:
        if pygame is None:
            return
        surface.fill((25, 25, 40))
        font = pygame.font.SysFont("Arial", 40)
        small = pygame.font.SysFont("Arial", 30)
        tiny = pygame.font.SysFont("Arial", 22)

        surface.blit(font.render("Gallery", True, (220, 220, 255)), (30, 12))

        if not self.runs:
            surface.blit(small.render("No runs yet. Finish a painting to see it here.", True, (160, 160, 180)), (30, 80))
            return

        # Visible window around selection
        max_vis = max(1, (surface.get_height() - 120) // self.ROW_H)
        start = max(0, self.selected - max_vis // 2)
        end = min(len(self.runs), start + max_vis)
        start = max(0, end - max_vis)

        y = 60
        for i in range(start, end):
            run = self.runs[i]
            selected = i == self.selected
            # background highlight
            if selected:
                pygame.draw.rect(surface, (40, 55, 85), (20, y - 6, surface.get_width() - 40, self.ROW_H - 8), border_radius=8)

            # icon
            thumb = self._thumb(run)
            ix, iy = 36, y + 4
            if thumb:
                surface.blit(thumb, (ix, iy))
            else:
                pygame.draw.rect(surface, (50, 50, 70), (ix, iy, self.ICON, self.ICON))
            if selected:
                pygame.draw.rect(surface, (100, 180, 255), (ix - 2, iy - 2, self.ICON + 4, self.ICON + 4), 2)

            # text next to icon
            tx = ix + self.ICON + 16
            name = run["run_id"]
            # show shorter name if very long
            if len(name) > 22:
                name = name[:19] + "..."
            color = (100, 180, 255) if selected else (200, 200, 210)
            surface.blit(small.render(name, True, color), (tx, y + 30))
            theme = run.get("theme_id", "")
            surface.blit(tiny.render(f"theme: {theme}", True, (140, 140, 160)), (tx, y + 80))
            y += self.ROW_H

        # Instructions – bottom
        help1 = "← →  or  A D   select     Enter open     Del delete     Esc home"
        help_surf = tiny.render(help1, True, (130, 130, 150))
        surface.blit(help_surf, (30, surface.get_height() - 38))