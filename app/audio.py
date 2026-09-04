"""Audio playback backends.

The production backend uses Qt Multimedia. PySide6 is imported lazily so the
configuration checker, tests, and dry-run mode do not require Qt to be
installed. ``QMediaPlayer`` playback is asynchronous and must be used from the
Qt thread on which the backend was created.

``AudioBackend`` is a tiny Protocol so tests / a GUI can swap in a fake or a
different engine without touching the scheduler.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable, Protocol, runtime_checkable

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


class QtMultimediaBackend:
    """Play audio through Qt Multimedia's asynchronous ``QMediaPlayer``.

    The backend must be constructed and used on the thread running a Qt
    application. PySide6 imports intentionally live in ``__init__`` so merely
    importing :mod:`app.audio` remains Qt-free.
    """

    def __init__(
        self,
        volume: float = 1.0,
        on_error: Callable[[str], None] | None = None,
    ) -> None:
        try:
            from PySide6.QtCore import QCoreApplication, QUrl
            from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
        except ImportError as exc:
            raise RuntimeError(
                "PySide6 diperlukan untuk audio; install dengan `uv sync --extra qt`"
            ) from exc

        if QCoreApplication.instance() is None:
            raise RuntimeError(
                "QtMultimediaBackend memerlukan QCoreApplication/QApplication yang aktif"
            )

        self._QUrl = QUrl
        self._player = QMediaPlayer()
        self._output = QAudioOutput()
        self._player.setAudioOutput(self._output)
        self._playing_state = QMediaPlayer.PlaybackState.PlayingState
        self._on_error = on_error
        if on_error is not None:
            self._player.errorOccurred.connect(self._handle_error)
        self.set_volume(volume)
        log.debug("Qt Multimedia siap")

    @property
    def player(self):
        """The underlying player, for the startup self-test and Qt integration."""
        return self._player

    def _handle_error(self, _code, message: str) -> None:
        log.error("gagal memutar audio: %s", message)
        if self._on_error is not None:
            try:
                self._on_error(str(message))
            except Exception:
                log.exception("callback error audio")

    def play(self, path: Path) -> bool:
        """Request playback; decode errors are reported asynchronously."""
        try:
            self._player.setSource(self._QUrl.fromLocalFile(str(path)))
            self._player.play()
            log.info("memutar: %s", path.name)
            return True
        except Exception as exc:
            log.error("gagal meminta pemutaran %s: %s", path, exc)
            return False

    def stop(self) -> None:
        try:
            self._player.stop()
        except Exception:
            pass

    def is_playing(self) -> bool:
        try:
            return self._player.playbackState() == self._playing_state
        except Exception:
            return False

    def set_volume(self, value: float) -> None:
        value = max(0.0, min(1.0, float(value)))
        try:
            self._output.setVolume(value)
        except Exception:
            pass
