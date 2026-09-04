"""Resolve bundled resources and per-user application directories.

Bundled assets and example configurations are read from :func:`app_root`.
Writable files use the platform's standard per-user locations instead of the
installation directory, so a frozen app can run from a read-only location.

On Linux and other XDG platforms:

* configuration: ``$XDG_CONFIG_HOME/bel-pelajaran``
* data: ``$XDG_DATA_HOME/bel-pelajaran``
* state/logs: ``$XDG_STATE_HOME/bel-pelajaran``

On Windows, configuration uses ``%APPDATA%`` and data/state use
``%LOCALAPPDATA%``. macOS uses its conventional Application Support and Logs
folders.
"""

from __future__ import annotations

import os
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


def _ensure_directory(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def _xdg_home(variable: str, fallback: str) -> Path:
    """Return a valid absolute XDG base directory.

    The XDG specification requires these variables to contain absolute paths;
    invalid or unset values use the specified default under the user's home.
    """
    value = os.environ.get(variable, "").strip()
    if value:
        candidate = Path(value).expanduser()
        if candidate.is_absolute():
            return candidate
    return Path.home() / fallback


def _windows_home(variable: str, fallback: str) -> Path:
    value = os.environ.get(variable, "").strip()
    if value:
        candidate = Path(value).expanduser()
        if candidate.is_absolute():
            return candidate
    return Path.home() / fallback


def config_dir() -> Path:
    """Return the per-user configuration directory for the application.

    Linux follows ``XDG_CONFIG_HOME`` (default ``~/.config``). Windows uses
    ``%APPDATA%`` and macOS uses ``~/Library/Application Support``.
    """
    if sys.platform == "win32":
        base = _windows_home("APPDATA", "AppData/Roaming")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = _xdg_home("XDG_CONFIG_HOME", ".config")
    return _ensure_directory(base / APP_NAME)


def data_dir() -> Path:
    """Return the per-user application data directory."""
    if sys.platform == "win32":
        base = _windows_home("LOCALAPPDATA", "AppData/Local")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = _xdg_home("XDG_DATA_HOME", ".local/share")
    return _ensure_directory(base / APP_NAME)


def state_dir() -> Path:
    """Return the per-user state directory, used for logs."""
    if sys.platform == "win32":
        base = _windows_home("LOCALAPPDATA", "AppData/Local")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Logs"
    else:
        base = _xdg_home("XDG_STATE_HOME", ".local/state")
    return _ensure_directory(base / APP_NAME)


def schedules_dir() -> Path:
    """Return the per-user directory for GUI-created schedule files."""
    return _ensure_directory(config_dir() / "schedules")


def user_data_dir() -> Path:
    """Backward-compatible alias for the per-user configuration directory.

    New code should use :func:`config_dir`, :func:`data_dir`, or
    :func:`state_dir` according to the type of file being stored.
    """
    return config_dir()


def logs_dir() -> Path:
    """Return the platform-standard per-user directory for application logs."""
    return _ensure_directory(state_dir() / "logs")
