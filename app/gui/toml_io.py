"""TOML persistence helpers for GUI-edited schedules."""

from __future__ import annotations

import tomllib
from collections.abc import Iterable
from pathlib import Path

from app.models import DAYS, Timetable


def read_defined_days(path: str | Path) -> set[str]:
    """Return day keys explicitly present in a TOML schedule.

    The config loader expands inherited days. Keeping this separate set lets the
    GUI omit untouched inherited days when it writes the schedule back.
    """
    with Path(path).open("rb") as file:
        data = tomllib.load(file)
    return {day for day in DAYS if day in data}


def save_timetable(
    timetable: Timetable,
    path: str | Path,
    *,
    defined_days: Iterable[str] | None = None,
) -> Path:
    """Write a timetable as TOML and return the destination path.

    If ``defined_days`` is supplied, only those days are serialized. This
    preserves the loader's Selasa inheritance for untouched Rabu/Kamis/Sabtu.
    Comments and original formatting are intentionally not preserved.
    """
    try:
        import tomli_w
    except ImportError as exc:  # pragma: no cover - GUI extra always includes it
        raise RuntimeError(
            "tomli_w diperlukan untuk menyimpan jadwal; install extra `gui`"
        ) from exc

    destination = Path(path)
    selected = set(timetable.days) if defined_days is None else set(defined_days)
    configured_sound_dir = timetable.sound_dir.strip()
    if configured_sound_dir:
        configured_sound_dir = str(Path(configured_sound_dir).expanduser().resolve())
    data: dict[str, object] = {"sound_dir": configured_sound_dir}
    for day in DAYS:
        if day not in selected:
            continue
        data[day] = [
            {"jam": bell.jam, "file": bell.file}
            for bell in timetable.bells_for(day)
        ]

    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as file:
        tomli_w.dump(data, file)
    return destination
