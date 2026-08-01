"""Load and validate TOML schedule configs.

Preserves the original legacy format:

    [[senin]]
    jam = '07:00'
    file = 'upacara_kurang_5_menit.mp3'

A day may be omitted entirely. As in the original script, ``rabu`` / ``kamis`` /
``sabtu`` inherit from ``selasa`` when absent, so a normal week needs only
``senin`` + ``selasa`` + ``jumat``.

Validation reports *every* problem in one pass (time format, missing sound
file, duplicate times) instead of stopping at the first error like the old
``cek_konfig.py`` did.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .models import DAYS, Bell, Timetable
from .paths import assets_dir

# Days that, when missing, copy another day's bells.
INHERIT_FROM: dict[str, str] = {
    "rabu": "selasa",
    "kamis": "selasa",
    "sabtu": "selasa",
}


@dataclass
class ValidationError:
    day: str
    message: str
    jam: str | None = None
    file: str | None = None


@dataclass
class ValidationResult:
    errors: list[ValidationError] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def load_timetable(path: str | Path) -> Timetable:
    """Read a TOML file and return a :class:`Timetable`."""
    with open(path, "rb") as fh:
        data = tomllib.load(fh)
    return parse_timetable(data)


def parse_timetable(data: dict) -> Timetable:
    """Build a Timetable from a parsed TOML dict (used by tests)."""
    raw: dict[str, list[Bell]] = {}
    for day in DAYS:
        entries = data.get(day)
        if not entries:
            continue
        bells: list[Bell] = []
        for e in entries:
            bells.append(Bell(jam=str(e["jam"]), file=str(e["file"])))
        raw[day] = bells

    # apply inheritance: e.g. rabu/kamis/sabtu <- selasa
    for day, src in INHERIT_FROM.items():
        if day not in raw and src in raw:
            raw[day] = list(raw[src])

    return Timetable(days=raw)


def is_valid_time(s: str) -> bool:
    """True if ``s`` is ``HH:MM`` (24h) with leading zeros tolerated."""
    try:
        datetime.strptime(s, "%H:%M")
        return True
    except (ValueError, TypeError):
        return False


def validate_timetable(timetable: Timetable) -> ValidationResult:
    """Check time format, sound-file existence and duplicate times.

    Collects ALL errors. Does not raise.
    """
    result = ValidationResult()
    assets = assets_dir()
    for day, bells in timetable:
        seen: dict[str, int] = {}
        for bell in bells:
            if not is_valid_time(bell.jam):
                result.errors.append(
                    ValidationError(
                        day=day,
                        jam=bell.jam,
                        file=bell.file,
                        message=f"Format jam tidak valid: {bell.jam!r} (harus HH:MM)",
                    )
                )
                continue
            if not (assets / bell.file).is_file():
                result.errors.append(
                    ValidationError(
                        day=day,
                        jam=bell.jam,
                        file=bell.file,
                        message=f"File suara tidak ditemukan: {bell.file!r}",
                    )
                )
            seen[bell.jam] = seen.get(bell.jam, 0) + 1

        for t, count in seen.items():
            if count > 1:
                result.errors.append(
                    ValidationError(
                        day=day,
                        jam=t,
                        message=f"Jam {t!r} muncul {count}× di hari {day} (duplikat)",
                    )
                )
    return result
