"""Tests for config parsing & validation (pure logic — no audio needed)."""

import pytest

from app.config import (
    is_valid_time,
    parse_timetable,
    validate_timetable,
)
from app.models import DAYS, Bell, Timetable


# --------------------------------------------------------------------- parse
def test_parse_basic():
    data = {
        "senin": [{"jam": "07:00", "file": "1.mp3"}, {"jam": "07:40", "file": "2.mp3"}],
    }
    tt = parse_timetable(data)
    assert [b.jam for b in tt.bells_for("senin")] == ["07:00", "07:40"]
    assert tt.total == 2


def test_parse_inherits_from_selasa():
    """rabu/kamis/sabtu absent -> copy selasa (legacy behaviour)."""
    data = {"selasa": [{"jam": "08:00", "file": "1.mp3"}]}
    tt = parse_timetable(data)
    for day in ("rabu", "kamis", "sabtu"):
        assert tt.bells_for(day) == [Bell("08:00", "1.mp3")]
    # senin/jumat absent stay empty
    assert tt.bells_for("senin") == []
    assert tt.bells_for("jumat") == []


def test_parse_explicit_day_overrides_inheritance():
    data = {
        "selasa": [{"jam": "08:00", "file": "1.mp3"}],
        "rabu": [{"jam": "09:00", "file": "2.mp3"}],
    }
    tt = parse_timetable(data)
    assert tt.bells_for("rabu") == [Bell("09:00", "2.mp3")]


def test_iteration_is_in_canonical_order():
    data = {"jumat": [{"jam": "07:00", "file": "1.mp3"}], "senin": [{"jam": "06:00", "file": "1.mp3"}]}
    tt = parse_timetable(data)
    days_yielded = [d for d, _ in tt]
    assert days_yielded == list(DAYS)


# --------------------------------------------------------------------- time
@pytest.mark.parametrize("s,expected", [
    ("07:00", True),
    ("00:00", True),
    ("23:59", True),
    ("9:00", True),     # strptime tolerates no leading zero
    ("24:00", False),
    ("07:60", False),
    ("abc", False),
    ("", False),
])
def test_is_valid_time(s, expected):
    assert is_valid_time(s) is expected


# --------------------------------------------------------------- validation
def _timetable(**days):
    return Timetable(days={d: [Bell(j, f) for j, f in entries] for d, entries in days.items()})


def test_validate_detects_bad_time():
    tt = _timetable(senin=[("7-00", "1.mp3")])
    errs = validate_timetable(tt).errors
    assert len(errs) == 1
    assert "tidak valid" in errs[0].message


def test_validate_detects_missing_file():
    tt = _timetable(senin=[("07:00", "does-not-exist-xyz.mp3")])
    errs = validate_timetable(tt).errors
    assert any("tidak ditemukan" in e.message for e in errs)
    # a real asset should pass
    tt_ok = _timetable(senin=[("07:00", "1.mp3")])
    assert validate_timetable(tt_ok).ok


def test_validate_detects_duplicate_times():
    tt = _timetable(senin=[("07:00", "1.mp3"), ("07:00", "2.mp3")])
    errs = validate_timetable(tt).errors
    assert any("duplikat" in e.message for e in errs)


def test_validate_reports_all_errors_not_just_first():
    tt = _timetable(senin=[("bad", "nope.mp3"), ("99:99", "also-nope.mp3")])
    errs = validate_timetable(tt).errors
    # at least 2 distinct problems reported in one pass
    assert len(errs) >= 2


def test_validate_clean_real_config_passes():
    tt = _timetable(senin=[("07:00", "1.mp3"), ("07:40", "2.mp3")])
    assert validate_timetable(tt).ok
