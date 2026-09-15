"""Typed data models for the bell schedule.

Kept dependency-free so they can be imported by tests, the config loader, the
scheduler, and (later) a GUI without pulling in Qt Multimedia.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterator

# Indonesian school-week day names, in order. Used everywhere as the canonical key.
DAYS: tuple[str, ...] = ("senin", "selasa", "rabu", "kamis", "jumat", "sabtu")

# Indo day -> schedule-library weekday token.
WEEKDAY_TOKEN: dict[str, str] = {
    "senin": "monday",
    "selasa": "tuesday",
    "rabu": "wednesday",
    "kamis": "thursday",
    "jumat": "friday",
    "sabtu": "saturday",
}

# Reverse lookup: schedule-library/English weekday index -> indo day.
# datetime.weekday(): Mon=0 .. Sun=6  (Sabtu=5, Minggu=6 = day off).
WEEKDAY_INDEX_TO_DAY: dict[int, str] = {i: d for i, d in enumerate(DAYS)}

DAY_LABEL: dict[str, str] = {
    "senin": "Senin",
    "selasa": "Selasa",
    "rabu": "Rabu",
    "kamis": "Kamis",
    "jumat": "Jum'at",
    "sabtu": "Sabtu",
}


@dataclass(frozen=True)
class Bell:
    """A single scheduled bell: a wall-clock time and a sound file.

    ``jam``  — ``"HH:MM"`` (24-hour), e.g. ``"07:00"``.
    ``file`` — bare filename inside the configured sound directory (the GUI
    defaults to ``assets/``), e.g. ``"1.mp3"``.
    """

    jam: str
    file: str


@dataclass
class Timetable:
    """A full week and its optional schedule-specific sound directory.

    Days not present are treated as having no bells. An empty ``sound_dir``
    selects the bundled default assets directory; non-empty values in TOML are
    absolute paths.
    """

    days: dict[str, list[Bell]] = field(default_factory=dict)
    sound_dir: str = ""

    def __iter__(self) -> Iterator[tuple[str, list[Bell]]]:
        """Yield (day, bells) for every school day in canonical order."""
        for day in DAYS:
            yield day, self.days.get(day, [])

    def bells_for(self, day: str) -> list[Bell]:
        return self.days.get(day, [])

    @property
    def total(self) -> int:
        return sum(len(b) for _, b in self)

    def all_bells(self) -> Iterator[tuple[str, Bell]]:
        for day, bells in self:
            for b in bells:
                yield day, b
