"""Launch the Bel Pembelajaran desktop GUI."""

from __future__ import annotations

import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QMessageBox

from app.audio import QtMultimediaBackend
from app.logging_setup import setup_logging

from .audio_selftest import self_test_audio
from .first_run import ensure_user_default_schedule
from .main_window import MainWindow
from .qt_app import get_qapp
from .settings import find_sound_files


def _run_startup_audio_test(window: MainWindow) -> None:
    samples = find_sound_files(window.controller.sound_dir)
    if not samples:
        window.show_audio_selftest_error(
            "tidak ada file MP3 di folder suara yang dikonfigurasi: "
            f"{window.controller.sound_dir}"
        )
        return
    ok, message = self_test_audio(QtMultimediaBackend, samples[0])
    if not ok:
        window.show_audio_selftest_error(message)


def main() -> int:
    setup_logging()
    app = get_qapp()
    app.setApplicationName("Bel Pembelajaran")
    try:
        initial_schedule = ensure_user_default_schedule()
    except OSError as exc:
        QMessageBox.critical(
            None,
            "Gagal Menyiapkan Jadwal",
            "Jadwal bawaan tidak dapat disalin ke folder konfigurasi pengguna.\n"
            f"Detail: {exc}",
        )
        return 2
    window = MainWindow(initial_schedule=initial_schedule)
    app.aboutToQuit.connect(window.controller.shutdown)
    window.show()
    QTimer.singleShot(0, lambda: _run_startup_audio_test(window))
    return int(app.exec())


if __name__ == "__main__":
    sys.exit(main())
