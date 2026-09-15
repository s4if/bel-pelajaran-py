"""Sound preview selector and volume control."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QPushButton, QSlider, QWidget


class SoundPicker(QWidget):
    """Select an available MP3, preview it, and control shared audio volume."""

    preview_requested = Signal(str)
    volume_changed = Signal(float)

    def __init__(
        self,
        sounds: Callable[[], Sequence[str]],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._sounds = sounds

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(QLabel("Uji suara:"))

        self.combo = QComboBox()
        self.combo.setObjectName("previewSoundCombo")
        self.combo.setMinimumContentsLength(22)
        layout.addWidget(self.combo, 1)

        self.play_button = QPushButton("▶ Putar")
        self.play_button.setObjectName("previewSoundButton")
        self.play_button.clicked.connect(self._request_preview)
        layout.addWidget(self.play_button)

        layout.addSpacing(12)
        layout.addWidget(QLabel("Volume:"))
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setObjectName("volumeSlider")
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(100)
        self.volume_slider.setTickInterval(10)
        self.volume_slider.setMinimumWidth(130)
        self.volume_slider.valueChanged.connect(self._volume_updated)
        layout.addWidget(self.volume_slider)

        self.volume_label = QLabel("100%")
        self.volume_label.setMinimumWidth(38)
        layout.addWidget(self.volume_label)
        self.refresh()

    @property
    def selected_sound(self) -> str:
        return self.combo.currentText()

    @property
    def volume(self) -> float:
        return self.volume_slider.value() / 100.0

    def refresh(self) -> None:
        """Reload MP3 names while preserving the current selection if possible."""
        selected = self.selected_sound
        self.combo.clear()
        self.combo.addItems(list(self._sounds()))
        position = self.combo.findText(selected)
        if position >= 0:
            self.combo.setCurrentIndex(position)
        available = self.combo.count() > 0
        self.combo.setEnabled(available)
        self.play_button.setEnabled(available)

    def _request_preview(self) -> None:
        if self.selected_sound:
            self.preview_requested.emit(self.selected_sound)

    def _volume_updated(self, value: int) -> None:
        self.volume_label.setText(f"{value}%")
        self.volume_changed.emit(value / 100.0)
