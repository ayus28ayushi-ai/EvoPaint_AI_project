from __future__ import annotations
from pathlib import Path
from typing import Any
from PIL import Image


class TimelapseRecorder:
    def __init__(self, max_frames: int = 60, size: int = 256):
        self.max_frames = max_frames
        self.size = size
        self.frames: dict[int, list[Image.Image]] = {}
        self.next_at: dict[int, int] = {}

    def feed(self, session: Any) -> None:
        """Called every frame. Captures when due."""
        try:
            for panel in range(4):
                try:
                    snap = session.snapshot(panel)
                except Exception:
                    continue
                if snap is None:
                    continue
                evals = getattr(snap, "evaluations", 0) or 0
                if panel not in self.frames:
                    self.frames[panel] = []
                    self.next_at[panel] = 0
                if evals >= self.next_at[panel] and len(self.frames[panel]) < self.max_frames:
                    try:
                        im = session.render(panel, self.size)
                        if im:
                            self.frames[panel].append(im.convert("RGB"))
                    except Exception:
                        pass
                    self.next_at[panel] = max(self.next_at[panel] * 2, self.next_at[panel] + 1)
        except Exception:
            pass

    def build_gifs(self, out_dir: Path) -> tuple[dict[int, Path], Path | None]:
        out_dir.mkdir(parents=True, exist_ok=True)
        gifs = {}
        lasts = []
        for panel, frames in sorted(self.frames.items()):
            if not frames:
                continue
            path = out_dir / f"timelapse_{panel}.gif"
            frames[0].save(path, save_all=True, append_images=frames[1:], duration=120, loop=0)
            gifs[panel] = path
            lasts.append(frames[-1])
        combined = None
        if len(lasts) >= 2:
            w = self.size * len(lasts)
            combo = Image.new("RGB", (w, self.size))
            for i, f in enumerate(lasts):
                combo.paste(f.resize((self.size, self.size)), (i * self.size, 0))
            combined = out_dir / "timelapse_combined.gif"
            combo.save(combined)
        return gifs, combined


def new_recorder(session: Any) -> TimelapseRecorder:
    return TimelapseRecorder()