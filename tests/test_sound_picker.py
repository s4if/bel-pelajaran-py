"""Tests for the sound preview and volume widget."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.gui.schedule_table import BellsModel, SoundDelegate
from app.gui.sound_picker import SoundPicker
from app.models import Bell


def test_sound_picker_lists_previews_and_changes_volume():
    app = QApplication.instance() or QApplication([])
    available = ["1.mp3", "istirahat.mp3"]
    picker = SoundPicker(lambda: available)
    previews = []
    volumes = []
    picker.preview_requested.connect(previews.append)
    picker.volume_changed.connect(volumes.append)

    picker.combo.setCurrentIndex(1)
    picker.play_button.click()
    picker.volume_slider.setValue(40)

    assert previews == ["istirahat.mp3"]
    assert volumes == [0.4]
    assert picker.volume_label.text() == "40%"

    available[:] = ["istirahat.mp3", "baru.mp3"]
    picker.refresh()
    assert picker.selected_sound == "istirahat.mp3"
    app.processEvents()


def test_sound_editor_retains_missing_configured_value():
    QApplication.instance() or QApplication([])
    model = BellsModel([Bell("07:00", "lama.mp3")])
    index = model.index(0, 1)
    delegate = SoundDelegate(lambda: ["baru.mp3"])
    editor = delegate.createEditor(None, None, index)

    delegate.setEditorData(editor, index)

    assert editor.currentText() == "lama.mp3"
    assert editor.findText("baru.mp3") >= 0
