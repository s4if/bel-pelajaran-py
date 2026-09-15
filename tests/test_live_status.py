"""Tests for live-status countdown formatting."""

from datetime import datetime

from app.gui.main_window import format_countdown


def test_format_countdown_minutes_and_seconds():
    now = datetime(2025, 1, 6, 9, 35, 30)

    assert format_countdown("09:40", now) == "dalam 4 mnt 30 dtk"


def test_format_countdown_hours():
    now = datetime(2025, 1, 6, 7, 15, 0)

    assert format_countdown("09:45", now) == "dalam 2 jam 30 mnt"


def test_format_countdown_at_or_after_target_is_now():
    assert format_countdown("09:40", datetime(2025, 1, 6, 9, 40, 0)) == "sekarang"
    assert format_countdown("09:40", datetime(2025, 1, 6, 9, 41, 0)) == "sekarang"
