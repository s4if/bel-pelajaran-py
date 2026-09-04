"""Logging setup: console + rotating file under the user state directory."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from .paths import logs_dir

_FMT = logging.Formatter(
    "%(asctime)s [%(levelname)s] %(name)s: %(message)s", "%Y-%m-%d %H:%M:%S"
)


def setup_logging(verbose: bool = False) -> logging.Logger:
    """Idempotent: safe to call multiple times.

    Logs to console (INFO, or DEBUG with ``-v``) and to a rotating file in the
    platform-standard per-user state directory, always DEBUG, 1 MB x 3.
    """
    logger = logging.getLogger("app")
    if logger.handlers:  # already configured
        return logger

    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    level = logging.DEBUG if verbose else logging.INFO

    sh = logging.StreamHandler()
    sh.setLevel(level)
    sh.setFormatter(_FMT)
    logger.addHandler(sh)

    try:
        fh = RotatingFileHandler(logs_dir() / "bel.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(_FMT)
        logger.addHandler(fh)
    except Exception:
        # Logging must never crash the app; fall back to console-only.
        pass

    return logger
