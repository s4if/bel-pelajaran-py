"""Tests for schedule sound-directory settings."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.gui.settings import SoundDirectoryDialog, find_sound_files
from app.paths import assets_dir


def test_find_sound_files_accepts_case_insensitive_mp3_extension(tmp_path):
    (tmp_path / "Bell.MP3").touch()
    (tmp_path / "notes.txt").touch()

    assert [path.name for path in find_sound_files(tmp_path)] == ["Bell.MP3"]


def test_empty_dialog_value_selects_default_assets():
    QApplication.instance() or QApplication([])
    dialog = SoundDirectoryDialog("")

    assert dialog.configured_directory == ""
    assert dialog.selected_directory == assets_dir().resolve()
    dialog.close()


def test_dialog_normalizes_selected_directory_to_absolute(tmp_path):
    QApplication.instance() or QApplication([])
    dialog = SoundDirectoryDialog(str(tmp_path))

    assert dialog.configured_directory == str(tmp_path.resolve())
    dialog.close()
