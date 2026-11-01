from __future__ import annotations
import subprocess, sys
from pathlib import Path
from typing import Any
from PIL import Image

try:
    import pygame
except ImportError:
    pygame = None

from media.gallery import UPLOADS_ROOT


class UploadScreen:
    screen_id = "upload"

    def __init__(self) -> None:
        self.msg = "Drop image or click button"
        self.btn = None

    def handle_events(self, events: list) -> dict | None:
        if pygame is None:
            return None
        for e in events:
            if e.type == pygame.DROPFILE:
                path = self._save(e.file)
                if path:
                    return {"target": "setup", "payload": {"target_path": path}}
                self.msg = "Failed to load file"
            elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 and self.btn and self.btn.collidepoint(e.pos):
                path = self._dialog()
                if path:
                    saved = self._save(path)
                    if saved:
                        return {"target": "setup", "payload": {"target_path": saved}}
                    self.msg = "Failed to load file"
            elif e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                return {"target": "home", "payload": None}
        return None

    def update(self, dt: float) -> None:
        pass

    def draw(self, surface: Any) -> None:
        if pygame is None:
            return
        surface.fill((30, 30, 45))
        font = pygame.font.SysFont("Arial", 24)
        small = pygame.font.SysFont("Arial", 18)
        surface.blit(font.render("Upload Target", True, (220, 220, 255)), (surface.get_width()//2 - 80, 100))
        surface.blit(small.render(self.msg, True, (180, 180, 200)), (surface.get_width()//2 - 100, 160))

        self.btn = pygame.Rect(surface.get_width()//2 - 100, 240, 200, 45)
        pygame.draw.rect(surface, (60, 110, 180), self.btn, border_radius=6)
        surface.blit(small.render("Choose File", True, (255, 255, 255)), (self.btn.x + 55, self.btn.y + 12))
        surface.blit(small.render("Esc = home", True, (130, 130, 150)), (surface.get_width()//2 - 40, 320))

    def _dialog(self) -> str | None:
        try:
            if sys.platform == "darwin":
                r = subprocess.run(["osascript", "-e", 'POSIX path of (choose file of type {"public.image"})'],
                                   capture_output=True, text=True, timeout=60)
                return r.stdout.strip() or None
            if sys.platform.startswith("linux"):
                for cmd in (["zenity", "--file-selection"], ["kdialog", "--getopenfilename"]):
                    try:
                        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                        if r.stdout.strip():
                            return r.stdout.strip()
                    except FileNotFoundError:
                        continue
            else:
                import tkinter as tk
                from tkinter import filedialog
                root = tk.Tk(); root.withdraw()
                p = filedialog.askopenfilename(filetypes=[("Images", "*.png *.jpg *.jpeg *.bmp")])
                root.destroy()
                return p or None
        except Exception:
            return None
        return None

    def _save(self, path: str) -> str | None:
        try:
            img = Image.open(path).convert("RGB")
            w, h = img.size
            side = min(w, h)
            img = img.crop(((w-side)//2, (h-side)//2, (w+side)//2, (h+side)//2))
            if side > 1024:
                img = img.resize((1024, 1024), Image.Resampling.LANCZOS)
            UPLOADS_ROOT.mkdir(parents=True, exist_ok=True)
            out = UPLOADS_ROOT / f"upload_{Path(path).stem}.png"
            img.save(out)
            return str(out)
        except Exception:
            return None