from __future__ import annotations
from typing import Any

try:
    import pygame
except ImportError:
    pygame = None

from media.gallery import get_run_folder, load_run


class EntryScreen:
    screen_id = "entry"

    def __init__(self, run_id: str | None = None) -> None:
        self.run_id = run_id
        self.record = None
        self.folder = None
        self.postcard = None
        if run_id:
            self._load(run_id)

    def _load(self, run_id: str) -> None:
        self.run_id = run_id
        self.record = load_run(run_id)
        self.folder = get_run_folder(run_id)
        self.postcard = None
        if self.folder and (self.folder / "postcard.png").exists() and pygame:
            try:
                self.postcard = pygame.image.load(str(self.folder / "postcard.png"))
            except Exception:
                pass

    def on_enter(self, payload=None) -> None:
        run_id = None
        if isinstance(payload, dict):
            run_id = payload.get("run_id")
        elif isinstance(payload, str):
            run_id = payload
        elif hasattr(payload, "run_id"):
            run_id = payload.run_id
        if run_id:
            self._load(run_id)

    def handle_events(self, events: list) -> dict | None:
        if pygame is None:
            return None
        for e in events:
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE or e.key == pygame.K_g:
                    return {"target": "gallery", "payload": None}
                if e.key == pygame.K_u and self.folder:
                    target = self.folder / "target.png"
                    if target.exists():
                        return {"target": "setup", "payload": {"target_path": str(target)}}
        return None

    def update(self, dt: float) -> None:
        pass

    def draw(self, surface: Any) -> None:
        if pygame is None:
            return
        surface.fill((20, 20, 35))
        font = pygame.font.SysFont("Arial", 22)
        small = pygame.font.SysFont("Arial", 16)

        if not self.record:
            surface.blit(font.render("Run not found", True, (255, 100, 100)), (30, 30))
            return

        surface.blit(font.render(f"Run: {self.run_id}", True, (220, 220, 255)), (30, 20))

        if self.postcard:
            # scale postcard to fit
            max_h = surface.get_height() - 100
            scale = min(0.5, max_h / self.postcard.get_height())
            w = int(self.postcard.get_width() * scale)
            h = int(self.postcard.get_height() * scale)
            scaled = pygame.transform.smoothscale(self.postcard, (w, h))
            surface.blit(scaled, (30, 60))

        surface.blit(small.render("U = use target again   G/Esc = gallery", True, (140, 140, 160)), (30, surface.get_height() - 35))