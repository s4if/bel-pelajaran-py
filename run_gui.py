"""Thin GUI launcher suitable for development and PyInstaller."""

from app.gui.__main__ import main


if __name__ == "__main__":
    raise SystemExit(main())
