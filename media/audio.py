from __future__ import annotations
from typing import Any
import numpy as np

try:
    import pygame
    import pygame.sndarray
except ImportError:
    pygame = None


class Audio:
    def __init__(self) -> None:
        self._muted = False
        self._ok = False
        if pygame is not None:
            try:
                if not pygame.mixer.get_init():
                    pygame.mixer.pre_init(22050, -16, 1, 512)
                    pygame.mixer.init()
                self._ok = True
            except Exception:
                pass

    def _tone(self, freq: float, duration: float = 0.15, vol: float = 0.4):
        if not self._ok or pygame is None:
            return None
        t = np.linspace(0, duration, int(22050 * duration), False)
        wave = (np.sin(2 * np.pi * freq * t) * 32767 * vol).astype(np.int16)
        channels = pygame.mixer.get_init()[2] if pygame.mixer.get_init() else 1
        if channels == 2:
            wave = np.column_stack((wave, wave))
        return pygame.sndarray.make_sound(wave)

    def on_event(self, event: Any) -> None:
        if self._muted or not self._ok:
            return
        etype = getattr(event, "type", None) or (event.get("type") if isinstance(event, dict) else None)
        if etype == "milestone_reached":
            snd = self._tone(660, 0.12, 0.45)          # clear beep
            if snd:
                snd.play()
        elif etype == "run_finished":
            # rising tone so it is obviously different from the beep
            for f in (440, 554, 659):
                snd = self._tone(f, 0.12, 0.4)
                if snd:
                    snd.play()

    def set_theme(self, theme_id: str) -> None:
        pass

    def set_volume(self, master: float, music: float = 1.0, effects: float = 1.0) -> None:
        pass

    def set_muted(self, flag: bool) -> None:
        self._muted = bool(flag)

    def start_music(self) -> None:
        pass

    def stop_music(self) -> None:
        pass

    def update(self, seconds: float) -> None:
        pass


_audio = None

def get_audio() -> Audio:
    global _audio
    if _audio is None:
        _audio = Audio()
    return _audio