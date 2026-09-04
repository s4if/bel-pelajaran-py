"""Editable schedule table model and delegates for one day's bells."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QRect, Qt, QTime, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QComboBox, QStyledItemDelegate, QTimeEdit, QWidget

from app.config import is_valid_time
from app.models import Bell


class BellsModel(QAbstractTableModel):
    """Present and mutate a day's Bell list as Jam/Suara columns."""

    HEADERS = ("Jam", "Suara")
    changed = Signal()

    def __init__(
        self,
        bells: Sequence[Bell] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._rows = bells if isinstance(bells, list) else list(bells or ())
        self._highlighted_row: int | None = None

    @property
    def bells(self) -> tuple[Bell, ...]:
        return tuple(self._rows)

    def set_bells(self, bells: list[Bell]) -> None:
        """Display and directly edit the supplied timetable day list."""
        self.beginResetModel()
        self._rows = bells
        self._highlighted_row = None
        self.endResetModel()

    def insert_bell(self, bell: Bell, row: int | None = None) -> int:
        position = len(self._rows) if row is None else max(0, min(row, len(self._rows)))
        self.beginInsertRows(QModelIndex(), position, position)
        self._rows.insert(position, bell)
        self.endInsertRows()
        self.changed.emit()
        return position

    def remove_bell(self, row: int) -> bool:
        if not 0 <= row < len(self._rows):
            return False
        self.beginRemoveRows(QModelIndex(), row, row)
        del self._rows[row]
        if self._highlighted_row == row:
            self._highlighted_row = None
        elif self._highlighted_row is not None and self._highlighted_row > row:
            self._highlighted_row -= 1
        self.endRemoveRows()
        self.changed.emit()
        return True

    def highlight_bell(self, jam: str, filename: str) -> int | None:
        """Highlight the matching fired bell and return its row."""
        row = next(
            (
                index
                for index, bell in enumerate(self._rows)
                if bell.jam == jam and bell.file == filename
            ),
            None,
        )
        self._set_highlighted_row(row)
        return row

    def clear_highlight(self) -> None:
        self._set_highlighted_row(None)

    def _set_highlighted_row(self, row: int | None) -> None:
        old_row = self._highlighted_row
        if row == old_row:
            return
        self._highlighted_row = row
        for changed_row in {old_row, row} - {None}:
            assert changed_row is not None
            if 0 <= changed_row < len(self._rows):
                self.dataChanged.emit(
                    self.index(changed_row, 0),
                    self.index(changed_row, self.columnCount() - 1),
                    [Qt.ItemDataRole.BackgroundRole],
                )

    def rowCount(self, parent=QModelIndex()) -> int:  # noqa: N802 - Qt API
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent=QModelIndex()) -> int:  # noqa: N802 - Qt API
        return 0 if parent.isValid() else len(self.HEADERS)

    def headerData(  # noqa: N802 - Qt API
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ):
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            if 0 <= section < len(self.HEADERS):
                return self.HEADERS[section]
            return None
        if orientation == Qt.Orientation.Vertical:
            return str(section + 1)
        return None

    def data(
        self,
        index: QModelIndex,
        role: int = Qt.ItemDataRole.DisplayRole,
    ):
        if not index.isValid() or not 0 <= index.row() < len(self._rows):
            return None

        bell = self._rows[index.row()]
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            return bell.jam if index.column() == 0 else bell.file
        if role == Qt.ItemDataRole.TextAlignmentRole and index.column() == 0:
            return Qt.AlignmentFlag.AlignCenter
        if role == Qt.ItemDataRole.BackgroundRole and index.row() == self._highlighted_row:
            return QColor("#fff0a6")
        if role == Qt.ItemDataRole.ToolTipRole and index.column() == 1:
            return bell.file
        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        flags = super().flags(index)
        if index.isValid():
            flags |= Qt.ItemFlag.ItemIsEditable
        return flags

    def setData(  # noqa: N802 - Qt API
        self,
        index: QModelIndex,
        value,
        role: int = Qt.ItemDataRole.EditRole,
    ) -> bool:
        if (
            role != Qt.ItemDataRole.EditRole
            or not index.isValid()
            or not 0 <= index.row() < len(self._rows)
        ):
            return False

        bell = self._rows[index.row()]
        if index.column() == 0:
            text = str(value)
            if not is_valid_time(text):
                return False
            text = datetime.strptime(text, "%H:%M").strftime("%H:%M")
            replacement = Bell(text, bell.file)
        elif index.column() == 1:
            text = str(value).strip()
            if not text:
                return False
            replacement = Bell(bell.jam, text)
        else:
            return False

        if replacement == bell:
            return True
        self._rows[index.row()] = replacement
        self.dataChanged.emit(
            index,
            index,
            [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole],
        )
        self.changed.emit()
        return True


class TimeDelegate(QStyledItemDelegate):
    """Use a 24-hour QTimeEdit for the Jam column."""

    def createEditor(self, parent, _option, _index):  # noqa: N802 - Qt API
        editor = QTimeEdit(parent)
        editor.setDisplayFormat("HH:mm")
        return editor

    def setEditorData(self, editor: QTimeEdit, index: QModelIndex) -> None:  # noqa: N802
        value = str(index.model().data(index, Qt.ItemDataRole.EditRole))
        try:
            parsed = datetime.strptime(value, "%H:%M")
            editor.setTime(QTime(parsed.hour, parsed.minute))
        except ValueError:
            editor.setTime(QTime.currentTime())

    def setModelData(self, editor: QTimeEdit, model, index: QModelIndex) -> None:  # noqa: N802
        model.setData(index, editor.time().toString("HH:mm"), Qt.ItemDataRole.EditRole)

    def updateEditorGeometry(  # noqa: N802 - Qt API
        self,
        editor: QWidget,
        option,
        _index: QModelIndex,
    ) -> None:
        editor.setGeometry(QRect(option.rect))


class SoundDelegate(QStyledItemDelegate):
    """Use a non-editable dropdown for the Suara column."""

    def __init__(
        self,
        sounds: Callable[[], Sequence[str]],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._sounds = sounds

    def createEditor(self, parent, _option, _index):  # noqa: N802 - Qt API
        editor = QComboBox(parent)
        editor.setEditable(False)
        editor.addItems(list(self._sounds()))
        return editor

    def setEditorData(self, editor: QComboBox, index: QModelIndex) -> None:  # noqa: N802
        value = str(index.model().data(index, Qt.ItemDataRole.EditRole))
        position = editor.findText(value)
        if position < 0 and value:
            # Keep stale filenames visible instead of silently replacing them
            # with the first file from a newly selected sound directory.
            editor.insertItem(0, value)
            position = 0
            editor.setItemData(
                position,
                "File belum ditemukan; pilih pengganti atau perbaiki folder suara.",
                Qt.ItemDataRole.ToolTipRole,
            )
        if position >= 0:
            editor.setCurrentIndex(position)

    def setModelData(self, editor: QComboBox, model, index: QModelIndex) -> None:  # noqa: N802
        model.setData(index, editor.currentText(), Qt.ItemDataRole.EditRole)

    def updateEditorGeometry(  # noqa: N802 - Qt API
        self,
        editor: QWidget,
        option,
        _index: QModelIndex,
    ) -> None:
        editor.setGeometry(QRect(option.rect))
