"""Sound-directory helpers and settings dialog."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.paths import assets_dir


def find_sound_files(path: str | Path) -> list[Path]:
    """Return MP3 files in a directory, including upper-case extensions."""
    directory = Path(path)
    if not directory.is_dir():
        return []
    return sorted(
        (
            item
            for item in directory.iterdir()
            if item.is_file() and item.suffix.lower() == ".mp3"
        ),
        key=lambda item: item.name.lower(),
    )


class SoundDirectoryDialog(QDialog):
    """Choose the absolute sound directory stored in the current TOML file."""

    def __init__(self, current: str | Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Pengaturan Folder Suara")
        self.setMinimumWidth(560)

        layout = QVBoxLayout(self)
        description = QLabel(
            "Pilih folder yang berisi file MP3. Lokasi absolut disimpan di file "
            "jadwal; kosong berarti memakai folder assets bawaan."
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        path_row = QHBoxLayout()
        self.path_edit = QLineEdit(str(current))
        self.path_edit.setObjectName("soundDirectoryPath")
        self.path_edit.setPlaceholderText("Kosong = folder assets bawaan")
        path_row.addWidget(self.path_edit, 1)
        browse_button = QPushButton("Pilih…")
        browse_button.clicked.connect(self._browse)
        path_row.addWidget(browse_button)
        layout.addLayout(path_row)

        reset_button = QPushButton("Gunakan Folder Bawaan")
        reset_button.clicked.connect(lambda: self.path_edit.clear())
        layout.addWidget(reset_button)

        self.info_label = QLabel()
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)
        self.path_edit.textChanged.connect(self._update_info)
        self._update_info(self.path_edit.text())

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @property
    def configured_directory(self) -> str:
        """Return an absolute path for TOML, or empty for bundled assets."""
        value = self.path_edit.text().strip()
        return str(Path(value).expanduser().resolve()) if value else ""

    @property
    def selected_directory(self) -> Path:
        configured = self.configured_directory
        return Path(configured) if configured else assets_dir().resolve()

    def _browse(self) -> None:
        selected = QFileDialog.getExistingDirectory(
            self,
            "Pilih Folder Suara",
            str(self.selected_directory),
        )
        if selected:
            self.path_edit.setText(str(Path(selected).resolve()))

    def _update_info(self, value: str) -> None:
        if not value.strip():
            path = assets_dir().resolve()
            count = len(find_sound_files(path))
            self.info_label.setText(
                f"Folder bawaan: {path} ({count} file MP3)."
            )
            return
        path = Path(value).expanduser()
        if not path.is_absolute():
            self.info_label.setText("Path harus absolut.")
            return
        if not path.is_dir():
            self.info_label.setText("Folder belum ditemukan.")
            return
        count = len(find_sound_files(path))
        self.info_label.setText(f"{count} file MP3 ditemukan.")

    def accept(self) -> None:
        value = self.path_edit.text().strip()
        if value:
            path = Path(value).expanduser()
            if not path.is_absolute() or not path.is_dir():
                QMessageBox.warning(
                    self,
                    "Folder Tidak Valid",
                    "Pilih folder tersedia dengan path absolut, atau kosongkan "
                    "untuk memakai folder bawaan.",
                )
                return
        super().accept()
