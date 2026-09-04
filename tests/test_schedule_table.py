"""Tests for the editable daily schedule table model."""

from PySide6.QtCore import Qt

from app.gui.schedule_table import BellsModel
from app.models import Bell


def test_bells_model_displays_time_sound_and_headers():
    bells = [Bell("07:00", "1.mp3"), Bell("09:30", "istirahat.mp3")]
    model = BellsModel(bells)

    assert model.rowCount() == 2
    assert model.columnCount() == 2
    assert model.headerData(0, Qt.Orientation.Horizontal) == "Jam"
    assert model.headerData(1, Qt.Orientation.Horizontal) == "Suara"
    assert model.data(model.index(0, 0)) == "07:00"
    assert model.data(model.index(1, 1)) == "istirahat.mp3"
    assert model.flags(model.index(0, 0)) & Qt.ItemFlag.ItemIsEditable


def test_bells_model_can_switch_days():
    model = BellsModel([Bell("07:00", "1.mp3")])

    model.set_bells([Bell("11:45", "akhir_pelajaran.mp3")])

    assert model.rowCount() == 1
    assert model.bells == (Bell("11:45", "akhir_pelajaran.mp3"),)
    assert model.data(model.index(0, 0)) == "11:45"


def test_model_edits_backing_list_and_emits_changed():
    bells = [Bell("7:00", "1.mp3")]
    model = BellsModel(bells)
    changes = []
    model.changed.connect(lambda: changes.append(True))

    assert model.setData(model.index(0, 0), "08:15")
    assert model.setData(model.index(0, 1), "2.mp3")
    row = model.insert_bell(Bell("09:00", "3.mp3"))
    assert model.remove_bell(row)

    assert bells == [Bell("08:15", "2.mp3")]
    assert len(changes) == 4


def test_model_rejects_invalid_time():
    bells = [Bell("07:00", "1.mp3")]
    model = BellsModel(bells)

    assert not model.setData(model.index(0, 0), "25:00")
    assert bells == [Bell("07:00", "1.mp3")]


def test_model_highlights_and_clears_fired_bell():
    model = BellsModel(
        [Bell("07:00", "1.mp3"), Bell("09:30", "istirahat.mp3")]
    )

    row = model.highlight_bell("09:30", "istirahat.mp3")

    assert row == 1
    assert model.data(model.index(1, 0), Qt.ItemDataRole.BackgroundRole) is not None
    assert model.data(model.index(0, 0), Qt.ItemDataRole.BackgroundRole) is None

    model.clear_highlight()
    assert model.data(model.index(1, 0), Qt.ItemDataRole.BackgroundRole) is None
