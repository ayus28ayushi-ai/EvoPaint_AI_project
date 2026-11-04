from __future__ import annotations
from typing import Any


class TimelapseRecorder:
    def __init__(self, max_frames: int = 60, size: int = 256):
        self.max_frames = max_frames
        self.size = size

    def feed(self, session: Any) -> None:
        pass

    def build_gifs(self, out_dir: Any = None) -> tuple[dict, Any]:
        return {}, None


def new_recorder(session: Any) -> TimelapseRecorder:
    return TimelapseRecorder()