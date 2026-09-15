"""Offscreen tests for the QTimer-driven GUI controller."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import schedule
from PySide6.QtWidgets import QApplication

from app.gui.controller import BellController
from app.models import Timetable


class FakeBackend:
    def __init__(self, *, volume=1.0, on_error=None):
        self.volume = volume
        self.on_error = on_error
        self.stopped = False
        self.played = []

    def play(self, path):
        self.played.append(path)
        return True

    def stop(self):
        self.stopped = True

    def is_playing(self):
        return False

    def set_volume(self, value):
        self.volume = value


def test_controller_load_start_and_stop(tmp_path):
    app = QApplication.instance() or QApplication([])
    config = tmp_path / "jadwal.toml"
    config.write_text(
        '[[senin]]\njam = "07:00"\nfile = "1.mp3"\n',
        encoding="utf-8",
    )
    statuses = []
    running = []
    controller = BellController(backend_factory=FakeBackend)
    controller.status.connect(statuses.append)
    controller.running_changed.connect(running.append)

    assert controller.load(config)
    controller.start()

    backend = controller.backend
    assert controller.is_running
    assert controller._timer.isActive()
    assert running == [True]
    assert any("Berjalan" in message for message in statuses)

    controller.stop()

    assert not controller.is_running
    assert not controller._timer.isActive()
    assert backend.stopped
    assert running == [True, False]
    app.processEvents()
    schedule.clear()


def test_controller_rejects_invalid_schedule_without_replacing_current(tmp_path):
    QApplication.instance() or QApplication([])
    valid_config = tmp_path / "valid.toml"
    valid_config.write_text(
        '[[senin]]\njam = "07:00"\nfile = "1.mp3"\n',
        encoding="utf-8",
    )
    invalid_config = tmp_path / "invalid.toml"
    invalid_config.write_text(
        '[[senin]]\njam = "bukan-jam"\nfile = "tidak-ada.mp3"\n',
        encoding="utf-8",
    )
    controller = BellController(backend_factory=FakeBackend)

    assert controller.load(valid_config)
    original_timetable = controller.timetable
    assert not controller.load(invalid_config)

    assert controller.timetable is original_timetable
    assert "Konfigurasi tidak valid" in controller.last_error
    assert "Format jam tidak valid" in controller.last_error


def test_preview_and_scheduler_share_backend(tmp_path):
    QApplication.instance() or QApplication([])
    sound = tmp_path / "preview.mp3"
    sound.touch()
    controller = BellController(backend_factory=FakeBackend)
    controller.set_volume(0.35)

    assert controller.preview_sound(sound)
    backend = controller.backend
    assert isinstance(backend, FakeBackend)
    assert backend.volume == 0.35
    assert backend.played == [sound]

    controller.use_timetable(Timetable())
    controller.start()

    assert controller.backend is backend
    assert controller.scheduler is not None
    assert controller.scheduler.backend is backend
    controller.shutdown()
    schedule.clear()


def test_preview_rejects_missing_file():
    QApplication.instance() or QApplication([])
    controller = BellController(backend_factory=FakeBackend)

    assert not controller.preview_sound("does-not-exist.mp3")
    assert "tidak ditemukan" in controller.last_error


def test_missing_configured_folder_loads_and_retains_sound_value(tmp_path):
    QApplication.instance() or QApplication([])
    missing = (tmp_path / "missing-sounds").resolve()
    config = tmp_path / "missing-folder.toml"
    config.write_text(
        f'sound_dir = "{missing.as_posix()}"\n'
        '[[senin]]\njam = "07:00"\nfile = "tetap.mp3"\n',
        encoding="utf-8",
    )
    controller = BellController(backend_factory=FakeBackend)

    assert controller.load(config)
    assert controller.timetable is not None
    assert controller.timetable.bells_for("senin")[0].file == "tetap.mp3"
    assert "Folder suara tidak ditemukan" in controller.last_error

    controller.start()
    assert controller.scheduler is None
    assert "Suara jadwal belum siap" in controller.last_error


def test_controller_passes_configured_sound_directory_to_scheduler(tmp_path):
    QApplication.instance() or QApplication([])
    sound_dir = tmp_path / "sounds"
    sound_dir.mkdir()
    controller = BellController(
        backend_factory=FakeBackend,
        sound_dir=sound_dir,
    )
    controller.use_timetable(Timetable(sound_dir=str(sound_dir.resolve())))

    controller.start()

    assert controller.scheduler is not None
    assert controller.scheduler.sound_dir == sound_dir.resolve()
    controller.shutdown()
    schedule.clear()
