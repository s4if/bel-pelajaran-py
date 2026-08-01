"""Resource path resolution — the single piece of exe groundwork.

Everything that needs an asset file goes through :func:`asset`, never through a
hard-coded ``"assets/" + name`` string. This makes the app behave identically in
three situations:

1. ``uv run`` / source  -> assets live next to the project root
2. ``pip install .``     -> handled by bundling (see BUILD.md) / not yet used
3. PyInstaller frozen    -> assets are unpacked into ``sys._MEIPASS``

The same trick keeps logs/configs writable even when the exe is installed into a
read-only location (e.g. ``C:\\Program Files``) by writing to the user home.
"""

from __future__ import annotations

import sys
from pathlib import Path

APP_NAME = "bel-pelajaran"


def is_frozen() -> bool:
    """True when running inside a PyInstaller bundle (``sys.frozen`` set)."""
    return getattr(sys, "frozen", False)


def app_root() -> Path:
    """Directory that contains bundled resources (``assets/``, ``configs/``).

    - Frozen: the temporary ``_MEIPASS`` extraction folder PyInstaller creates.
    - Source: the project root (parent of this ``app/`` package).
    """
    if is_frozen():
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass)
    # Dev/source mode: this file is app/paths.py -> root is its parent's parent.
    return Path(__file__).resolve().parent.parent


def assets_dir() -> Path:
    return app_root() / "assets"


def configs_dir() -> Path:
    return app_root() / "configs"


def asset(filename: str) -> Path:
    """Resolve a bare asset filename (e.g. ``"1.mp3"``) to an absolute path."""
    return assets_dir() / filename


def user_data_dir() -> Path:
    """An always-writable dir for logs and (future) user-edited schedules.

    Uses the user home so it works even when the app folder is read-only
    (typical for a Windows install in ``Program Files``).
    """
    base = Path.home() / f".{APP_NAME}"
    base.mkdir(parents=True, exist_ok=True)
    return base


def logs_dir() -> Path:
    d = user_data_dir() / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d
