"""Audio playback backends.

Why pygame ``mixer.music`` as the default:

* **mp3 out of the box** — SDL_mixer ships libmpg123, so mp3 (plus ogg/flac/wav,
  the "bonus" formats) decode without ffmpeg or any external binary.
* **Non-blocking** — ``music.play()`` hands off to SDL's audio thread and
  returns immediately, so the scheduler loop is never stalled and a long sound
  can never make us miss the next bell (the old blocking ``pydub`` bug).
* **Same on Windows & Linux**, and it bundles cleanly into PyInstaller.

``AudioBackend`` is a tiny Protocol so tests / a GUI can swap in a fake or a
different engine without touching the scheduler.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Protocol, runtime_checkable

log = logging.getLogger(__name__)


@runtime_checkable
class AudioBackend(Protocol):
    def play(self, path: Path) -> bool: ...
    def stop(self) -> None: ...
    def is_playing(self) -> bool: ...
    def set_volume(self, value: float) -> None: ...


class NullBackend:
    """No-op backend: logs what it *would* play. Used for ``--dry-run`` tests."""

    def play(self, path: Path) -> bool:
        log.info("[null] akan memutar %s", path.name)
        return True

    def stop(self) -> None:
        pass

    def is_playing(self) -> bool:
        return False

    def set_volume(self, value: float) -> None:
        pass


class PygameBackend:
    """Plays sounds via ``pygame.mixer.music`` (non-blocking, mp3-ready)."""

    def __init__(self, volume: float = 1.0) -> None:
        import os

        # We only need audio. Forcing the dummy video driver means the app also
        # works headless and stays light for a future background-service mode.
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

        import pygame  # imported lazily so `app` imports without pygame present

        pygame.mixer.pre_init(frequency=44100, size=-16, channels=2, buffer=512)
        pygame.mixer.init()
        self._music = pygame.mixer.music
        self._pygame = pygame  # keep a ref for stop()/volume safety
        self.set_volume(volume)
        log.debug("pygame mixer siap (driver audio SDL)")

    def play(self, path: Path) -> bool:
        """Load and start ``path``. Returns False if playback could not start."""
        try:
            self._music.load(str(path))
            self._music.play()
            log.info("memutar: %s", path.name)
            return True
        except Exception as exc:  # missing/unsupported file, hw issue, etc.
            log.error("gagal memutar %s: %s", path, exc)
            return False

    def stop(self) -> None:
        try:
            self._music.stop()
        except Exception:
            pass

    def is_playing(self) -> bool:
        try:
            return self._music.get_busy()
        except Exception:
            return False

    def set_volume(self, value: float) -> None:
        value = max(0.0, min(1.0, float(value)))
        try:
            self._music.set_volume(value)
        except Exception:
            pass
