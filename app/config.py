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
        if day not in data:
            continue
        entries = data[day]
        bells: list[Bell] = []
        for e in entries:
            bells.append(Bell(jam=str(e["jam"]), file=str(e["file"])))
        # Keep explicitly empty days. This lets ``rabu = []`` override Selasa
        # inheritance, which is required when the GUI deletes every Rabu bell.
        raw[day] = bells

    # apply inheritance: e.g. rabu/kamis/sabtu <- selasa
    for day, src in INHERIT_FROM.items():
        if day not in raw and src in raw:
            raw[day] = list(raw[src])

    return Timetable(days=raw, sound_dir=str(data.get("sound_dir", "") or "").strip())


def is_valid_time(s: str) -> bool:
    """True if ``s`` is ``HH:MM`` (24h) with leading zeros tolerated."""
    try:
        datetime.strptime(s, "%H:%M")
        return True
    except (ValueError, TypeError):
        return False


def validate_timetable(timetable: Timetable) -> ValidationResult:
    """Check schedule values without touching the filesystem.

    Sound locations are deliberately verified only immediately before starting
    playback or editing a row, so a schedule with a stale path can still open
    and retain every configured filename.
    """
    result = ValidationResult()
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


def resolve_sound_dir(timetable: Timetable) -> Path:
    """Resolve the configured absolute sound path or the bundled default."""
    configured = timetable.sound_dir.strip()
    if not configured:
        return assets_dir().resolve()
    return Path(configured).expanduser().resolve()


def validate_sound_files(timetable: Timetable) -> ValidationResult:
    """Verify the configured sound directory and every referenced audio file."""
    result = ValidationResult()
    configured = timetable.sound_dir.strip()
    if configured and not Path(configured).expanduser().is_absolute():
        result.errors.append(
            ValidationError(
                day="umum",
                message="Folder suara harus menggunakan path absolut.",
            )
        )
        return result

    sound_dir = resolve_sound_dir(timetable)
    if not sound_dir.is_dir():
        result.errors.append(
            ValidationError(
                day="umum",
                message=f"Folder suara tidak ditemukan: {sound_dir}",
            )
        )
        return result

    for day, bells in timetable:
        for bell in bells:
            if not (sound_dir / bell.file).is_file():
                result.errors.append(
                    ValidationError(
                        day=day,
                        jam=bell.jam,
                        file=bell.file,
                        message=(
                            f"File suara tidak ditemukan: {bell.file!r} "
                            f"di {sound_dir}"
                        ),
                    )
                )
    return result
