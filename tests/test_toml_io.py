"""Round-trip tests for GUI TOML persistence."""

import tomllib

from app.config import load_timetable
from app.gui.toml_io import read_defined_days, save_timetable
from app.models import Bell, Timetable


def test_save_timetable_round_trips(tmp_path):
    timetable = Timetable(
        days={
            "senin": [Bell("07:00", "1.mp3")],
            "jumat": [Bell("11:45", "akhir_pelajaran.mp3")],
        }
    )
    destination = tmp_path / "saved.toml"

    save_timetable(timetable, destination)
    loaded = load_timetable(destination)

    assert loaded.days == timetable.days


def test_save_preserves_untouched_inheritance(tmp_path):
    source = tmp_path / "source.toml"
    source.write_text(
        '[[selasa]]\njam = "08:00"\nfile = "1.mp3"\n',
        encoding="utf-8",
    )
    timetable = load_timetable(source)
    timetable.days["selasa"][0] = Bell("09:15", "2.mp3")
    for day in ("rabu", "kamis", "sabtu"):
        timetable.days[day] = list(timetable.days["selasa"])
    destination = tmp_path / "saved.toml"

    save_timetable(
        timetable,
        destination,
        defined_days=read_defined_days(source),
    )

    with destination.open("rb") as file:
        raw = tomllib.load(file)
    assert set(raw) == {"sound_dir", "selasa"}
    assert raw["sound_dir"] == ""
    loaded = load_timetable(destination)
    for day in ("selasa", "rabu", "kamis", "sabtu"):
        assert loaded.bells_for(day) == [Bell("09:15", "2.mp3")]


def test_save_writes_absolute_sound_directory(tmp_path):
    sound_dir = tmp_path / "sounds"
    sound_dir.mkdir()
    timetable = Timetable(sound_dir=str(sound_dir))
    destination = tmp_path / "saved.toml"

    save_timetable(timetable, destination)
    loaded = load_timetable(destination)

    assert loaded.sound_dir == str(sound_dir.resolve())


def test_save_explicit_empty_day_blocks_inheritance(tmp_path):
    timetable = Timetable(
        days={
            "selasa": [Bell("08:00", "1.mp3")],
            "rabu": [],
        }
    )
    destination = tmp_path / "saved.toml"

    save_timetable(
        timetable,
        destination,
        defined_days={"selasa", "rabu"},
    )
    loaded = load_timetable(destination)

    assert loaded.bells_for("rabu") == []
    assert loaded.bells_for("kamis") == [Bell("08:00", "1.mp3")]
