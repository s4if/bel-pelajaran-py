"""Startup audio verification for the Qt Multimedia backend."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Any


def self_test_audio(
    make_backend: Callable[..., Any],
    sample: Path,
    timeout_ms: int = 3000,
) -> tuple[bool, str]:
    """Attempt to play ``sample`` and return ``(success, message)``.

    Qt Multimedia reports missing codecs and other decode failures
    asynchronously. The nested event loop gives those signals a chance to
    arrive before the timeout. Entering ``PlayingState`` is considered success;
    waiting for the complete clip would make a short startup check depend on
    the clip's duration.

    This function must run on the Qt application's main thread. ``make_backend``
    is injected to keep the check usable with a fake backend in tests, and must
    accept the optional ``on_error`` keyword argument.
    """
    try:
        from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer
        from PySide6.QtMultimedia import QMediaPlayer
    except ImportError as exc:
        return False, f"PySide6 tidak tersedia: {exc}"

    if QCoreApplication.instance() is None:
        return False, "Qt application belum dibuat"
    if not sample.is_file():
        return False, f"file sample tidak ditemukan: {sample}"
    if timeout_ms <= 0:
        return False, "timeout self-test harus lebih besar dari 0"

    result = {"ok": False, "done": False, "message": ""}
    loop = QEventLoop()
    backend = None

    def finish(ok: bool, message: str = "") -> None:
        # Signal handlers can run more than once (for example an error after a
        # timeout), so only the first result is significant.
        if result["done"]:
            return
        result["ok"] = ok
        result["done"] = True
        result["message"] = message
        loop.quit()

    def backend_error(message: str) -> None:
        finish(False, str(message) or "Qt Multimedia melaporkan error")

    try:
        backend = make_backend(on_error=backend_error)
        player = getattr(backend, "player", None)
        if player is None:
            return False, "backend tidak menyediakan QMediaPlayer"

        def on_state_changed(state) -> None:
            if state == QMediaPlayer.PlaybackState.PlayingState:
                finish(True, "ok")

        def on_media_status_changed(status) -> None:
            if status == QMediaPlayer.MediaStatus.EndOfMedia:
                finish(True, "ok")
            elif status == QMediaPlayer.MediaStatus.InvalidMedia:
                finish(False, "media tidak valid atau codec tidak tersedia")

        def on_player_error(*args) -> None:
            message = str(args[-1]) if args else "Qt Multimedia error"
            finish(False, message)

        player.playbackStateChanged.connect(on_state_changed)
        player.mediaStatusChanged.connect(on_media_status_changed)
        player.errorOccurred.connect(on_player_error)

        if not backend.play(sample):
            return False, "backend menolak permintaan pemutaran"
        # A test double may emit its state signal synchronously from play().
        if result["done"]:
            return bool(result["ok"]), result["message"] or "tidak ada respons"

        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(lambda: finish(False, "timeout menunggu playback"))
        timer.start(timeout_ms)
        loop.exec()
        return bool(result["ok"]), result["message"] or "tidak ada respons"
    except Exception as exc:
        return False, str(exc)
    finally:
        if backend is not None:
            try:
                backend.stop()
            except Exception:
                pass
