"""Qt controller that drives the scheduler from the GUI event loop."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal, Slot

from app.audio import AudioBackend, NullBackend, QtMultimediaBackend
from app.config import (
    load_timetable,
    resolve_sound_dir,
    validate_sound_files,
    validate_timetable,
)
from app.models import DAY_LABEL, Bell, Timetable
from app.paths import assets_dir
from app.scheduler import BellScheduler

BackendFactory = Callable[..., AudioBackend]


class BellController(QObject):
    """Own the active scheduler, audio backend, and one-second Qt timer.

    Every method runs on Qt's main thread. In particular, the timer invokes
    ``BellScheduler.tick()`` on the same thread that owns ``QMediaPlayer``.
    """

    status = Signal(str)
    next_bell = Signal(str, str, str)
    fired = Signal(str, str, str)
    error = Signal(str)
    running_changed = Signal(bool)

    def __init__(
        self,
        parent: QObject | None = None,
        *,
        backend_factory: BackendFactory = QtMultimediaBackend,
        sound_dir: str | Path | None = None,
    ) -> None:
        super().__init__(parent)
        self.timetable: Timetable | None = None
        self.config_path: Path | None = None
        self.scheduler: BellScheduler | None = None
        self.backend: AudioBackend = NullBackend()
        self._backend_factory = backend_factory
        self._backend_ready = False
        self.sound_dir = (
            Path(sound_dir).expanduser().resolve()
            if sound_dir is not None
            else assets_dir().resolve()
        )
        self._volume = 1.0
        self.last_error = ""

        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._on_tick)

    @property
    def is_running(self) -> bool:
        return self.scheduler is not None

    def load(self, path: str | Path) -> bool:
        """Load and validate a timetable, preserving the prior running state."""
        config_path = Path(path)
        self.last_error = ""
        try:
            timetable = load_timetable(config_path)
        except Exception as exc:
            self._report_error(f"Gagal membaca konfigurasi: {exc}")
            return False

        result = validate_timetable(timetable)
        if not result.ok:
            details = "\n".join(
                f"• [{DAY_LABEL.get(item.day, item.day)}] {item.message}"
                for item in result.errors
            )
            self._report_error(f"Konfigurasi tidak valid:\n{details}")
            return False

        was_running = self.is_running
        if was_running:
            self.stop()

        self.timetable = timetable
        self.config_path = config_path
        self.sound_dir = resolve_sound_dir(timetable)
        self.status.emit(
            f"Dimuat: {config_path.name} ({timetable.total} bell terjadwal)"
        )
        self._report_missing_sound_directory()
        if was_running:
            self.start()
        else:
            self._emit_next()
        return True

    def use_timetable(
        self,
        timetable: Timetable,
        path: str | Path | None = None,
    ) -> None:
        """Replace the working timetable, stopping any currently armed jobs."""
        if self.is_running:
            self.stop()
        self.timetable = timetable
        self.config_path = Path(path) if path is not None else None
        self.sound_dir = resolve_sound_dir(timetable)
        self.last_error = ""
        self.status.emit(
            f"Jadwal baru ({timetable.total} bell terjadwal)"
            if path is None
            else f"Dimuat: {Path(path).name} ({timetable.total} bell terjadwal)"
        )
        self._emit_next()

    @Slot()
    def start(self) -> None:
        if self.scheduler is not None:
            return
        if self.timetable is None:
            self._report_error("Belum ada jadwal yang dimuat.")
            return

        sound_result = validate_sound_files(self.timetable)
        if not sound_result.ok:
            details = "\n".join(f"• {item.message}" for item in sound_result.errors)
            self._report_error(f"Suara jadwal belum siap:\n{details}")
            return
        self.sound_dir = resolve_sound_dir(self.timetable)
        self._ensure_backend()

        self.scheduler = BellScheduler(
            self.timetable,
            self.backend,
            on_fire=self._on_fire,
            on_error=lambda day, bell, exc: self._report_error(
                f"Error bell {DAY_LABEL.get(day, day)} {bell.jam}: {exc}"
            ),
            sound_dir=self.sound_dir,
        )
        armed = self.scheduler.arm()
        self.scheduler.tick()
        self._timer.start()
        self.running_changed.emit(True)
        self.status.emit(f"Berjalan — {armed} bell terjadwal.")
        self._emit_next()

    @Slot()
    def stop(self) -> None:
        self._timer.stop()
        if self.scheduler is not None:
            self.scheduler.stop()
            self.scheduler = None
        try:
            self.backend.stop()
        except Exception:
            # Stopping must never prevent the UI from returning to idle.
            pass
        self.running_changed.emit(False)
        self.status.emit("Berhenti.")
        self._emit_next()

    def set_sound_dir(self, path: str | Path | None) -> None:
        """Set the schedule's absolute sound directory; empty selects default."""
        configured = str(path or "").strip()
        if configured:
            sound_dir = Path(configured).expanduser().resolve()
            if not sound_dir.is_dir():
                raise ValueError(f"Folder suara tidak ditemukan: {sound_dir}")
            configured = str(sound_dir)
        else:
            sound_dir = assets_dir().resolve()
        if self.is_running:
            self.stop()
        if self.timetable is not None:
            self.timetable.sound_dir = configured
        self.sound_dir = sound_dir
        self.status.emit(f"Folder suara: {sound_dir}")

    def _report_missing_sound_directory(self) -> None:
        if self.timetable is None:
            return
        configured = self.timetable.sound_dir.strip()
        if configured and not Path(configured).expanduser().is_absolute():
            self._report_error(
                "Folder suara pada konfigurasi harus menggunakan path absolut."
            )
        elif not self.sound_dir.is_dir():
            self._report_error(f"Folder suara tidak ditemukan: {self.sound_dir}")

    def preview_sound(self, path: str | Path) -> bool:
        """Play a sound immediately through the scheduler's shared backend."""
        sound_path = Path(path)
        if not sound_path.is_file():
            self._report_error(f"File suara tidak ditemukan: {sound_path.name}")
            return False
        if not self._ensure_backend():
            return False
        if not self.backend.play(sound_path):
            self._report_error(f"Gagal memutar pratinjau: {sound_path.name}")
            return False
        self.status.emit(f"Pratinjau suara: {sound_path.name}")
        return True

    @Slot(float)
    def set_volume(self, value: float) -> None:
        self._volume = max(0.0, min(1.0, float(value)))
        self.backend.set_volume(self._volume)

    def shutdown(self) -> None:
        """Stop scheduling/audio and release the retained shared backend."""
        self.stop()
        self.backend = NullBackend()
        self._backend_ready = False

    def _ensure_backend(self) -> bool:
        if self._backend_ready:
            return True
        try:
            self.backend = self._backend_factory(
                volume=self._volume,
                on_error=lambda message: self._report_error(
                    f"Error audio: {message}"
                ),
            )
            self._backend_ready = True
            if self.scheduler is not None:
                self.scheduler.backend = self.backend
            return True
        except Exception as exc:
            self.backend = NullBackend()
            self._backend_ready = False
            self._report_error(
                f"Audio gagal diinisialisasi ({exc}); berjalan tanpa suara."
            )
            return False

    @Slot()
    def _on_tick(self) -> None:
        if self.scheduler is None:
            return
        self.scheduler.tick()
        suffix = " (memutar…)" if self.backend.is_playing() else ""
        self.status.emit(f"Berjalan{suffix}")
        self._emit_next()

    def _on_fire(self, day: str, bell: Bell) -> None:
        self.fired.emit(DAY_LABEL.get(day, day), bell.jam, bell.file)

    def _report_error(self, message: str) -> None:
        self.last_error = message
        self.error.emit(message)

    def _emit_next(self) -> None:
        if self.scheduler is not None:
            upcoming = self.scheduler.next_bell_today()
            if upcoming is not None:
                day, bell = upcoming
                self.next_bell.emit(
                    DAY_LABEL.get(day, day), bell.jam, bell.file
                )
                return
        self.next_bell.emit("", "", "")
