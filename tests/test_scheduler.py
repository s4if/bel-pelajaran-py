"""Tests for the scheduler's event-loop and callback hooks."""

import schedule

from app.models import Bell, Timetable
from app.scheduler import BellScheduler


class RecordingBackend:
    def __init__(self, *, fail=False):
        self.played = []
        self.fail = fail

    def play(self, path):
        self.played.append(path)
        if self.fail:
            raise RuntimeError("backend failure")
        return True

    def stop(self):
        pass

    def is_playing(self):
        return False

    def set_volume(self, value):
        pass


def test_fire_calls_on_fire(monkeypatch, tmp_path):
    sample = tmp_path / "bell.mp3"
    sample.touch()
    monkeypatch.setattr("app.scheduler.asset", lambda filename: sample)
    backend = RecordingBackend()
    fired = []
    scheduler = BellScheduler(
        Timetable(days={"senin": [Bell("07:00", "bell.mp3")]}),
        backend,
        on_fire=lambda day, bell: fired.append((day, bell)),
    )

    scheduler._fire("senin", Bell("07:00", "bell.mp3"))

    assert backend.played == [sample]
    assert fired == [("senin", Bell("07:00", "bell.mp3"))]


def test_fire_calls_on_error_when_backend_raises(monkeypatch, tmp_path):
    sample = tmp_path / "bell.mp3"
    sample.touch()
    monkeypatch.setattr("app.scheduler.asset", lambda filename: sample)
    backend = RecordingBackend(fail=True)
    errors = []
    bell = Bell("07:00", "bell.mp3")
    scheduler = BellScheduler(
        Timetable(days={"senin": [bell]}),
        backend,
        on_error=lambda day, fired_bell, error: errors.append((day, fired_bell, error)),
    )

    scheduler._fire("senin", bell)

    assert len(errors) == 1
    assert errors[0][0:2] == ("senin", bell)
    assert isinstance(errors[0][2], RuntimeError)


def test_tick_runs_pending_jobs(monkeypatch):
    calls = []
    monkeypatch.setattr("app.scheduler.sched_lib.run_pending", lambda: calls.append(True))
    scheduler = BellScheduler(Timetable(), RecordingBackend())

    scheduler.tick()

    assert calls == [True]


def test_fire_uses_configured_sound_directory(tmp_path):
    sound_dir = tmp_path / "sounds"
    sound_dir.mkdir()
    backend = RecordingBackend()
    bell = Bell("07:00", "custom.mp3")
    scheduler = BellScheduler(Timetable(), backend, sound_dir=sound_dir)

    scheduler._fire("senin", bell)

    assert backend.played == [sound_dir / "custom.mp3"]


def teardown_function():
    # The schedule package stores jobs globally; do not leak jobs between tests.
    schedule.clear()
