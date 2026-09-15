"""First-launch initialization for writable user schedules."""

from __future__ import annotations

import shutil
from pathlib import Path

from app.paths import configs_dir, schedules_dir

DEFAULT_SCHEDULE_NAME = "konfig.toml"


def ensure_user_default_schedule(
    *,
    source: str | Path | None = None,
    destination_dir: str | Path | None = None,
) -> Path:
    """Copy the factory schedule once and return its writable user path.

    Existing user schedules are never overwritten. The exclusive destination
    open also makes concurrent first launches safe. If copying fails midway,
    the incomplete destination is removed before the exception is re-raised.
    """
    factory = Path(source) if source is not None else configs_dir() / DEFAULT_SCHEDULE_NAME
    target_dir = Path(destination_dir) if destination_dir is not None else schedules_dir()
    destination = target_dir / DEFAULT_SCHEDULE_NAME

    if destination.exists():
        if not destination.is_file():
            raise IsADirectoryError(f"Path jadwal pengguna bukan file: {destination}")
        return destination
    if not factory.is_file():
        raise FileNotFoundError(f"Jadwal bawaan tidak ditemukan: {factory}")

    target_dir.mkdir(parents=True, exist_ok=True)
    try:
        with factory.open("rb") as source_file, destination.open("xb") as target_file:
            shutil.copyfileobj(source_file, target_file)
    except FileExistsError:
        # Another process completed initialization between exists() and open().
        if destination.is_file():
            return destination
        raise IsADirectoryError(f"Path jadwal pengguna bukan file: {destination}")
    except OSError:
        try:
            destination.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    return destination
