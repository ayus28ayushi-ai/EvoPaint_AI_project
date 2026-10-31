from __future__ import annotations
from typing import Any

try:
    import pygame
except ImportError:
    pygame = None

from media.gallery import delete_run, list_runs


class GalleryScreen:
    screen_id = "gallery"

    def __init__(self) -> None:
        self.runs = list_runs()
        self.selected = 0

    def handle_events(self, events: list) -> dict | None:
        if pygame is None:
            return None
        for e in events:
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    return {"target": "home", "payload": None}
                if e.key in (pygame.K_RIGHT, pygame.K_d):
                    self.selected = min(self.selected + 1, max(0, len(self.runs) - 1))
                if e.key in (pygame.K_LEFT, pygame.K_a):
                    self.selected = max(self.selected - 1, 0)
                if e.key == pygame.K_RETURN and self.runs:
                    return {"target": "entry", "payload": {"run_id": self.runs[self.selected]["run_id"]}}
                if e.key == pygame.K_DELETE and self.runs:
                    delete_run(self.runs[self.selected]["run_id"])
                    self.runs = list_runs()
                    self.selected = min(self.selected, max(0, len(self.runs) - 1))
        return None

    def update(self, dt: float) -> None:
        pass

    def draw(self, surface: Any) -> None:
        if pygame is None:
            return
        surface.fill((25, 25, 40))
        font = pygame.font.SysFont("Arial", 22)
        small = pygame.font.SysFont("Arial", 16)

        surface.blit(font.render("Gallery", True, (220, 220, 255)), (30, 20))

        if not self.runs:
            surface.blit(small.render("No runs yet.", True, (160, 160, 180)), (30, 80))
            return

        y = 70
        for i, run in enumerate(self.runs[:15]):
            color = (100, 180, 255) if i == self.selected else (180, 180, 200)
            text = f"{'> ' if i == self.selected else '  '}{run['run_id']}"
            surface.blit(small.render(text, True, color), (30, y))
            y += 28

        surface.blit(small.render("Arrows select  Enter open  Del delete  Esc home", True, (130, 130, 150)), (30, surface.get_height() - 35))