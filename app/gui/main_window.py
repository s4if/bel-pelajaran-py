"""Main desktop window for viewing, editing, and running bell schedules."""

from __future__ import annotations

from datetime import datetime
from math import ceil
from pathlib import Path

from PySide6.QtCore import QEvent, QItemSelection, QModelIndex, QTime, QTimer
from PySide6.QtGui import QAction, QCloseEvent, QIcon, QKeySequence
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QStyle,
    QSystemTrayIcon,
    QTableView,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.config import validate_timetable
from app.models import DAYS, DAY_LABEL, Bell, Timetable
from app.paths import assets_dir, configs_dir, schedules_dir

from .controller import BellController
from .schedule_table import BellsModel, SoundDelegate, TimeDelegate
from .settings import SoundDirectoryDialog, find_sound_files
from .sound_picker import SoundPicker
from .toml_io import read_defined_days, save_timetable


def format_countdown(time_text: str, now: datetime | None = None) -> str:
    """Format the remaining time until today's ``HH:MM`` bell."""
    current = now or datetime.now()
    target_time = datetime.strptime(time_text, "%H:%M").time()
    target = datetime.combine(current.date(), target_time)
    seconds = max(0, ceil((target - current).total_seconds()))
    if seconds == 0:
        return "sekarang"

    hours, remainder = divmod(seconds, 3600)
    minutes, remaining_seconds = divmod(remainder, 60)
    if hours:
        return f"dalam {hours} jam {minutes} mnt"
    if minutes:
        return f"dalam {minutes} mnt {remaining_seconds} dtk"
    return f"dalam {remaining_seconds} dtk"


class MainWindow(QMainWindow):
    """Edit a weekly schedule and control the in-process bell engine."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Bel Pembelajaran")
        self.setMinimumSize(720, 560)

        self.controller = BellController(self)
        self.schedule_model = BellsModel(parent=self)
        self._defined_days: set[str] = set()
        self._dirty = False
        self._normalization_warning_shown = False
        self._audio_available = True
        self._quitting = False
        self._tray_notice_shown = False
        self._tray_available = False
        self._fire_flash_timer = QTimer(self)
        self._fire_flash_timer.setSingleShot(True)
        self._fire_flash_timer.setInterval(3000)
        self._fire_flash_timer.timeout.connect(self._clear_fire_flash)
        self._build_actions()
        self._build_ui()
        self._connect_controller()
        self._setup_tray()
        self._load_schedule(configs_dir() / "example.toml", show_dialog=False)

    def _build_actions(self) -> None:
        self.new_action = QAction("&Jadwal Baru", self)
        self.new_action.setShortcut(QKeySequence.StandardKey.New)
        self.new_action.triggered.connect(self._new_schedule)

        self.open_action = QAction("&Buka Jadwal…", self)
        self.open_action.setObjectName("openScheduleAction")
        self.open_action.setShortcut(QKeySequence.StandardKey.Open)
        self.open_action.setStatusTip("Buka file jadwal TOML")
        self.open_action.triggered.connect(self._open_schedule)

        self.save_action = QAction("&Simpan", self)
        self.save_action.setShortcut(QKeySequence.StandardKey.Save)
        self.save_action.triggered.connect(self._save_schedule)

        self.save_as_action = QAction("Simpan Sebagai…", self)
        self.save_as_action.setShortcut(QKeySequence.StandardKey.SaveAs)
        self.save_as_action.triggered.connect(self._save_schedule_as)

        self.sound_settings_action = QAction("Folder &Suara…", self)
        self.sound_settings_action.setStatusTip("Pilih folder yang berisi file MP3")
        self.sound_settings_action.triggered.connect(self._open_sound_settings)

        self.minimize_to_tray_action = QAction("Minimalkan ke &Tray", self)
        self.minimize_to_tray_action.triggered.connect(self._hide_to_tray)

        self.quit_action = QAction("&Keluar Sepenuhnya", self)
        self.quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        self.quit_action.setStatusTip("Hentikan bel dan keluar dari aplikasi")
        self.quit_action.triggered.connect(self._quit_application)

        file_menu = self.menuBar().addMenu("&File")
        file_menu.addAction(self.new_action)
        file_menu.addAction(self.open_action)
        file_menu.addSeparator()
        file_menu.addAction(self.save_action)
        file_menu.addAction(self.save_as_action)

        application_menu = self.menuBar().addMenu("&Aplikasi")
        application_menu.addAction(self.sound_settings_action)
        application_menu.addSeparator()
        application_menu.addAction(self.minimize_to_tray_action)
        application_menu.addSeparator()
        application_menu.addAction(self.quit_action)

    def _build_ui(self) -> None:
        central = QWidget(self)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        heading_row = QHBoxLayout()
        title = QLabel("Bel Pembelajaran")
        title.setStyleSheet("font-size: 22px; font-weight: 600;")
        heading_row.addWidget(title)
        heading_row.addStretch()
        open_button = QPushButton("Buka Jadwal…")
        open_button.setObjectName("openScheduleButton")
        open_button.clicked.connect(self._open_schedule)
        heading_row.addWidget(open_button)
        save_button = QPushButton("Simpan")
        save_button.clicked.connect(self._save_schedule)
        heading_row.addWidget(save_button)
        layout.addLayout(heading_row)

        self.config_label = QLabel("Belum ada jadwal yang dimuat")
        self.config_label.setWordWrap(True)
        layout.addWidget(self.config_label)

        day_row = QHBoxLayout()
        day_row.addWidget(QLabel("Hari:"))
        self.day_selector = QComboBox()
        self.day_selector.setObjectName("daySelector")
        for day in DAYS:
            self.day_selector.addItem(DAY_LABEL[day], day)
        self.day_selector.currentIndexChanged.connect(self._refresh_selected_day)
        day_row.addWidget(self.day_selector)
        day_row.addStretch()
        self.day_count_label = QLabel("0 bell")
        day_row.addWidget(self.day_count_label)
        layout.addLayout(day_row)

        self.schedule_table = QTableView()
        self.schedule_table.setObjectName("scheduleTable")
        self.schedule_table.setModel(self.schedule_model)
        self.schedule_table.setAlternatingRowColors(True)
        self.schedule_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.schedule_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        # Editing is opened explicitly so the current row's sound file can be
        # checked immediately beforehand without rejecting stale filenames.
        self._schedule_edit_triggers = QAbstractItemView.EditTrigger.NoEditTriggers
        self.schedule_table.setEditTriggers(self._schedule_edit_triggers)
        self.schedule_table.doubleClicked.connect(self._edit_index)
        self.schedule_table.setItemDelegateForColumn(0, TimeDelegate(self.schedule_table))
        self.schedule_table.setItemDelegateForColumn(
            1,
            SoundDelegate(self._sound_names, self.schedule_table),
        )
        self.schedule_table.verticalHeader().setVisible(False)
        header = self.schedule_table.horizontalHeader()
        # QTimeEdit adds spin buttons while editing, so the time column needs
        # more room than its short display text (for example, "07:00").
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.schedule_table.setColumnWidth(0, 130)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.schedule_table, 1)

        edit_row = QHBoxLayout()
        self.add_button = QPushButton("Tambah Bell")
        self.add_button.clicked.connect(self._add_bell)
        edit_row.addWidget(self.add_button)
        self.edit_button = QPushButton("Ubah Pilihan")
        self.edit_button.setEnabled(False)
        self.edit_button.clicked.connect(self._edit_selected)
        edit_row.addWidget(self.edit_button)
        self.delete_button = QPushButton("Hapus Bell")
        self.delete_button.setEnabled(False)
        self.delete_button.clicked.connect(self._delete_selected)
        edit_row.addWidget(self.delete_button)
        edit_row.addStretch()
        layout.addLayout(edit_row)

        self.sound_picker = SoundPicker(self._sound_names, self)
        self.sound_picker.setToolTip(f"Folder suara: {self.controller.sound_dir}")
        layout.addWidget(self.sound_picker)

        self.state_label = QLabel("Berhenti.")
        self.state_label.setObjectName("stateLabel")
        self.state_label.setStyleSheet("font-size: 16px; color: #666666;")
        layout.addWidget(self.state_label)

        self.next_label = QLabel("Bell berikutnya hari ini: —")
        self.next_label.setWordWrap(True)
        layout.addWidget(self.next_label)

        self.last_fired_label = QLabel("Terakhir berbunyi: —")
        layout.addWidget(self.last_fired_label)

        self.notice_frame = QFrame()
        self.notice_frame.setObjectName("noticeFrame")
        self.notice_frame.setStyleSheet(
            "QFrame#noticeFrame { background: #8b1a1a; border-radius: 3px; }"
            "QFrame#noticeFrame QLabel { color: white; }"
            "QFrame#noticeFrame QToolButton { color: white; font-weight: 700; "
            "border: none; padding: 4px 7px; }"
            "QFrame#noticeFrame QToolButton:hover { background: #a52a2a; }"
        )
        notice_layout = QHBoxLayout(self.notice_frame)
        notice_layout.setContentsMargins(10, 7, 6, 7)
        self.error_label = QLabel()
        self.error_label.setWordWrap(True)
        notice_layout.addWidget(self.error_label, 1)
        self.dismiss_notice_button = QToolButton()
        self.dismiss_notice_button.setObjectName("dismissNoticeButton")
        self.dismiss_notice_button.setText("×")
        self.dismiss_notice_button.setToolTip("Tutup pemberitahuan")
        self.dismiss_notice_button.setAccessibleName("Tutup pemberitahuan")
        self.dismiss_notice_button.clicked.connect(self._dismiss_notice)
        notice_layout.addWidget(self.dismiss_notice_button)
        self.notice_frame.hide()
        layout.addWidget(self.notice_frame)

        self.start_button = QPushButton("Mulai")
        self.start_button.setObjectName("startStopButton")
        self.start_button.setMinimumHeight(38)
        self.start_button.setEnabled(False)
        self.start_button.clicked.connect(self._toggle_running)
        layout.addWidget(self.start_button)

        self.setCentralWidget(central)
        status_bar = self.statusBar()
        status_bar.showMessage("Siap")
        self.status_next_label = QLabel("Berikutnya: —")
        self.status_next_label.setObjectName("statusNextBell")
        status_bar.addPermanentWidget(self.status_next_label, 1)
        self.running_indicator = QLabel("○ Berhenti")
        self.running_indicator.setObjectName("runningIndicator")
        self.running_indicator.setStyleSheet("color: #666666; font-weight: 600;")
        status_bar.addPermanentWidget(self.running_indicator)

    def _connect_controller(self) -> None:
        self.controller.status.connect(self._show_status)
        self.controller.next_bell.connect(self._show_next_bell)
        self.controller.fired.connect(self._show_fired)
        self.controller.error.connect(self._show_error)
        self.controller.running_changed.connect(self._show_running_state)
        self.schedule_model.changed.connect(self._on_model_changed)
        self.sound_picker.preview_requested.connect(self._preview_sound)
        self.sound_picker.volume_changed.connect(self.controller.set_volume)
        self.schedule_table.selectionModel().selectionChanged.connect(
            self._update_edit_buttons
        )

    def _setup_tray(self) -> None:
        app_icon = QIcon(str(assets_dir() / "app_icon.svg"))
        if app_icon.isNull():
            app_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_MediaVolume)
        tray_icon = QIcon(str(assets_dir() / "tray_icon.svg"))
        if tray_icon.isNull():
            tray_icon = app_icon
        self.setWindowIcon(app_icon)
        application = QApplication.instance()
        if application is not None:
            application.setWindowIcon(app_icon)

        self.tray_icon = QSystemTrayIcon(tray_icon, self)
        self.tray_icon.setToolTip("Bel Pembelajaran")
        tray_menu = QMenu(self)
        self.restore_action = tray_menu.addAction("Buka Bel Pembelajaran")
        self.restore_action.triggered.connect(self._restore_from_tray)
        self.tray_start_action = tray_menu.addAction("Mulai Bell")
        self.tray_start_action.triggered.connect(self._toggle_running)
        tray_menu.addSeparator()
        tray_menu.addAction(self.quit_action)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self._tray_activated)

        self._tray_available = QSystemTrayIcon.isSystemTrayAvailable()
        self.minimize_to_tray_action.setEnabled(self._tray_available)
        if self._tray_available:
            application = QApplication.instance()
            if application is not None:
                application.setQuitOnLastWindowClosed(False)
            self.tray_icon.show()
        else:
            self.minimize_to_tray_action.setStatusTip(
                "System tray tidak tersedia di desktop ini"
            )

    def _hide_to_tray(self) -> None:
        if not self._tray_available:
            return
        self.hide()
        if not self._tray_notice_shown:
            self.tray_icon.showMessage(
                "Bel Pembelajaran tetap berjalan",
                "Buka kembali lewat ikon tray. Pilih 'Keluar Sepenuhnya' untuk berhenti.",
                QSystemTrayIcon.MessageIcon.Information,
                4000,
            )
            self._tray_notice_shown = True

    def _restore_from_tray(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self._restore_from_tray()

    def _quit_application(self) -> None:
        if not self._confirm_unsaved_changes():
            return
        if not self._confirm_stop_running(
            "Bell sedang berjalan. Hentikan bell dan keluar dari aplikasi?"
        ):
            return
        self._quitting = True
        self.tray_icon.hide()
        self.controller.shutdown()
        application = QApplication.instance()
        if application is not None:
            application.quit()

    def _confirm_unsaved_changes(self) -> bool:
        if not self._dirty:
            return True
        answer = QMessageBox.warning(
            self,
            "Perubahan Belum Disimpan",
            "Jadwal memiliki perubahan yang belum disimpan. Simpan sekarang?",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )
        if answer == QMessageBox.StandardButton.Save:
            return self._save_schedule()
        return answer == QMessageBox.StandardButton.Discard

    def _confirm_stop_running(self, message: str) -> bool:
        if not self.controller.is_running:
            return True
        answer = QMessageBox.question(
            self,
            "Hentikan Bell",
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return False
        self.controller.stop()
        return True

    def _sound_names(self) -> list[str]:
        return [path.name for path in find_sound_files(self.controller.sound_dir)]

    def _open_sound_settings(self) -> None:
        timetable = self.controller.timetable
        configured = timetable.sound_dir if timetable is not None else ""
        dialog = SoundDirectoryDialog(configured, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        selected = dialog.configured_directory
        if selected == configured:
            return
        if not self._confirm_stop_running(
            "Mengganti folder suara akan menghentikan bell. Lanjutkan?"
        ):
            return
        try:
            self.controller.set_sound_dir(selected)
            sound_dir = self.controller.sound_dir
        except (OSError, ValueError) as exc:
            QMessageBox.critical(
                self,
                "Gagal Menyimpan Pengaturan",
                str(exc),
            )
            return

        self._dirty = True
        self._update_window_title()
        self.sound_picker.refresh()
        self.sound_picker.setToolTip(f"Folder suara: {sound_dir}")
        sounds = self._sound_names()
        self.statusBar().showMessage(f"Folder suara: {sound_dir}", 5000)
        if not sounds:
            self._show_error(f"Tidak ada file MP3 di folder suara: {sound_dir}")
            return

        self.notice_frame.hide()

    def _new_schedule(self) -> None:
        if not self._confirm_unsaved_changes():
            return
        if not self._confirm_stop_running(
            "Bell sedang berjalan. Hentikan bell dan buat jadwal baru?"
        ):
            return
        self.controller.use_timetable(Timetable())
        self._defined_days.clear()
        self._dirty = False
        self._normalization_warning_shown = True
        self.config_label.setText("Jadwal baru — belum disimpan")
        self.config_label.setToolTip("")
        self.sound_picker.refresh()
        self.sound_picker.setToolTip(
            f"Folder suara: {self.controller.sound_dir}"
        )
        self.start_button.setEnabled(self._audio_available)
        self._refresh_selected_day()
        self._update_window_title()

    def _open_schedule(self) -> None:
        initial_dir = (
            self.controller.config_path.parent
            if self.controller.config_path is not None
            else configs_dir()
        )
        filename, _selected_filter = QFileDialog.getOpenFileName(
            self,
            "Buka Jadwal",
            str(initial_dir),
            "Jadwal TOML (*.toml);;Semua File (*)",
        )
        if not filename:
            return
        if not self._confirm_unsaved_changes():
            return
        if not self._confirm_stop_running(
            "Bell sedang berjalan. Hentikan bell dan buka jadwal lain?"
        ):
            return
        self._load_schedule(Path(filename), show_dialog=True)

    def _load_schedule(self, path: Path, *, show_dialog: bool) -> bool:
        if not self.controller.load(path):
            self.start_button.setEnabled(
                self.controller.timetable is not None and self._audio_available
            )
            if show_dialog:
                QMessageBox.critical(
                    self,
                    "Gagal Membuka Jadwal",
                    self.controller.last_error or "Jadwal tidak dapat dimuat.",
                )
            return False

        try:
            self._defined_days = read_defined_days(path)
        except Exception as exc:
            self._show_error(f"Gagal membaca struktur jadwal: {exc}")
            return False
        self._dirty = False
        self._normalization_warning_shown = False
        if not self.controller.last_error:
            self.notice_frame.hide()
        self.config_label.setText(f"Jadwal aktif: {path.name}")
        self.config_label.setToolTip(str(path.resolve()))
        self.sound_picker.refresh()
        self.sound_picker.setToolTip(
            f"Folder suara: {self.controller.sound_dir}"
        )
        self.start_button.setEnabled(self._audio_available)
        self._refresh_selected_day()
        self._update_window_title()
        return True

    def _refresh_selected_day(self, _index: int | None = None) -> None:
        timetable = self.controller.timetable
        day = self.day_selector.currentData()
        if timetable is None or not day:
            bells: list[Bell] = []
        else:
            bells = timetable.days.setdefault(day, [])
        self.schedule_model.set_bells(bells)
        self.day_count_label.setText(f"{len(bells)} bell")
        self._update_edit_buttons()

    def _add_bell(self) -> None:
        if self.controller.is_running:
            return
        sounds = self._sound_names()
        if not sounds:
            QMessageBox.warning(
                self,
                "Tidak Ada Suara",
                "Tambahkan file MP3 ke folder suara yang dipilih di pengaturan.",
            )
            return

        used = {bell.jam for bell in self.schedule_model.bells}
        candidate = QTime.currentTime()
        for _minute in range(24 * 60):
            text = candidate.toString("HH:mm")
            if text not in used:
                break
            candidate = candidate.addSecs(60)
        row = self.schedule_model.insert_bell(Bell(text, sounds[0]))
        index = self.schedule_model.index(row, 0)
        self.schedule_table.setCurrentIndex(index)
        self.schedule_table.scrollTo(index)
        self.schedule_table.edit(index)

    def _edit_selected(self) -> None:
        self._edit_index(self.schedule_table.currentIndex())

    def _edit_index(self, index: QModelIndex) -> None:
        if self.controller.is_running or not index.isValid():
            return
        bell = self.schedule_model.bells[index.row()]
        sound_dir = self.controller.sound_dir
        configured = (
            self.controller.timetable.sound_dir.strip()
            if self.controller.timetable is not None
            else ""
        )
        if configured and not Path(configured).expanduser().is_absolute():
            self._show_error(
                "Folder suara harus menggunakan path absolut. "
                f"Nilai suara {bell.file!r} tetap dipertahankan."
            )
        elif not sound_dir.is_dir():
            self._show_error(
                f"Folder suara tidak ditemukan: {sound_dir}. "
                f"Nilai suara {bell.file!r} tetap dipertahankan."
            )
        elif not (sound_dir / bell.file).is_file():
            self._show_error(
                f"File suara {bell.file!r} tidak ditemukan di {sound_dir}. "
                "Nilainya tetap dipertahankan agar dapat diperbaiki."
            )
        self.schedule_table.edit(index)

    def _delete_selected(self) -> None:
        if self.controller.is_running:
            return
        index = self.schedule_table.currentIndex()
        if not index.isValid():
            return
        bell = self.schedule_model.bells[index.row()]
        answer = QMessageBox.question(
            self,
            "Hapus Bell",
            f"Hapus bell {bell.jam} → {bell.file}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.schedule_model.remove_bell(index.row())

    def _on_model_changed(self) -> None:
        day = self.day_selector.currentData()
        if day:
            self._defined_days.add(day)
        if self.controller.is_running:
            self.controller.stop()
            self.statusBar().showMessage("Jadwal berubah; bel dihentikan sampai dimulai lagi.")
        self._dirty = True
        self.day_count_label.setText(f"{self.schedule_model.rowCount()} bell")
        self._update_window_title()

    def _preview_sound(self, filename: str) -> None:
        self.notice_frame.hide()
        self.controller.preview_sound(self.controller.sound_dir / filename)

    def show_audio_selftest_error(self, message: str) -> None:
        """Disable audio actions and surface a mandatory startup failure."""
        self._audio_available = False
        text = (
            "Audio tidak dapat memutar mp3 — periksa perangkat audio dan "
            f"GStreamer/plugin codec.\nDetail: {message}"
        )
        self._show_error(text)
        self.start_button.setEnabled(False)
        self.tray_start_action.setEnabled(False)
        self.sound_picker.setEnabled(False)
        QMessageBox.critical(self, "Audio Tidak Tersedia", text)

    def _update_edit_buttons(
        self,
        _selected: QItemSelection | None = None,
        _deselected: QItemSelection | None = None,
    ) -> None:
        has_selection = (
            self.schedule_table.currentIndex().isValid()
            and not self.controller.is_running
        )
        self.edit_button.setEnabled(has_selection)
        self.delete_button.setEnabled(has_selection)

    def _save_schedule(self) -> bool:
        if self.controller.config_path is None:
            return self._save_schedule_as()
        return self._write_schedule(self.controller.config_path)

    def _save_schedule_as(self) -> bool:
        schedule_dir = schedules_dir()
        current = self.controller.config_path
        default_name = current.name if current is not None else "jadwal_baru.toml"
        filename, _selected_filter = QFileDialog.getSaveFileName(
            self,
            "Simpan Jadwal Sebagai",
            str(schedule_dir / default_name),
            "Jadwal TOML (*.toml)",
        )
        if not filename:
            return False
        path = Path(filename)
        if path.suffix.lower() != ".toml":
            path = path.with_suffix(".toml")
        return self._write_schedule(path)

    def _write_schedule(self, path: Path) -> bool:
        timetable = self.controller.timetable
        if timetable is None:
            return False
        result = validate_timetable(timetable)
        if not result.ok:
            details = "\n".join(
                f"• [{DAY_LABEL.get(error.day, error.day)}] {error.message}"
                for error in result.errors
            )
            QMessageBox.critical(
                self,
                "Jadwal Tidak Valid",
                f"Perbaiki jadwal sebelum menyimpan:\n{details}",
            )
            return False

        if not self._normalization_warning_shown and self.controller.config_path:
            answer = QMessageBox.warning(
                self,
                "Format TOML Akan Dinormalisasi",
                "Menyimpan akan merapikan ulang file TOML dan menghapus komentar. "
                "Lanjutkan?",
                QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if answer != QMessageBox.StandardButton.Save:
                return False
            self._normalization_warning_shown = True

        try:
            save_timetable(
                timetable,
                path,
                defined_days=self._defined_days,
            )
        except Exception as exc:
            QMessageBox.critical(self, "Gagal Menyimpan", f"Jadwal gagal disimpan: {exc}")
            return False

        self.controller.config_path = path
        self._dirty = False
        self.config_label.setText(f"Jadwal aktif: {path.name}")
        self.config_label.setToolTip(str(path.resolve()))
        self.statusBar().showMessage(f"Jadwal disimpan: {path}", 5000)
        self._update_window_title()
        return True

    def _update_window_title(self) -> None:
        path = self.controller.config_path
        name = path.name if path is not None else "Jadwal Baru"
        marker = " *" if self._dirty else ""
        self.setWindowTitle(f"Bel Pembelajaran — {name}{marker}")

    def _toggle_running(self) -> None:
        self.notice_frame.hide()
        if self.controller.is_running:
            self._confirm_stop_running("Hentikan bell yang sedang berjalan?")
            return
        timetable = self.controller.timetable
        if timetable is not None:
            result = validate_timetable(timetable)
            if not result.ok:
                QMessageBox.critical(
                    self,
                    "Jadwal Tidak Valid",
                    "Perbaiki jadwal sebelum menjalankan bel.",
                )
                return
        self.controller.start()

    def _show_status(self, message: str) -> None:
        self.state_label.setText(message)
        if not self._fire_flash_timer.isActive():
            self.statusBar().showMessage(message)

    def _show_next_bell(self, day: str, time: str, filename: str) -> None:
        if day:
            countdown = format_countdown(time)
            self.next_label.setText(
                f"Bell berikutnya: {day} {time} → {filename} ({countdown})"
            )
            self.status_next_label.setText(
                f"Berikutnya: {day} {time} ({countdown})"
            )
        else:
            self.next_label.setText("Bell berikutnya hari ini: —")
            self.status_next_label.setText("Berikutnya: —")

    def _show_fired(self, day: str, time: str, filename: str) -> None:
        fired_at = datetime.now().strftime("%H:%M:%S")
        self.last_fired_label.setText(
            f"Terakhir berbunyi: {day} {time} → {filename} ({fired_at})"
        )
        self.last_fired_label.setStyleSheet(
            "background: #fff0a6; color: #4d3b00; padding: 5px; font-weight: 600;"
        )
        self.statusBar().showMessage(
            f"Bell berbunyi: {day} {time} → {filename}",
            3000,
        )
        self.schedule_model.clear_highlight()
        if self.day_selector.currentText() == day:
            row = self.schedule_model.highlight_bell(time, filename)
            if row is not None:
                self.schedule_table.scrollTo(self.schedule_model.index(row, 0))
        self._fire_flash_timer.start()

    def _clear_fire_flash(self) -> None:
        self.schedule_model.clear_highlight()
        self.last_fired_label.setStyleSheet("")
        message = "Berjalan" if self.controller.is_running else "Berhenti"
        self.statusBar().showMessage(message)

    def _show_error(self, message: str) -> None:
        self.error_label.setText(message)
        self.notice_frame.show()
        self.statusBar().showMessage(message)

    def _dismiss_notice(self) -> None:
        self.notice_frame.hide()
        self.statusBar().clearMessage()

    def _show_running_state(self, running: bool) -> None:
        self.start_button.setText("Berhenti" if running else "Mulai")
        color = "#188038" if running else "#666666"
        self.state_label.setStyleSheet(f"font-size: 16px; color: {color};")
        self.running_indicator.setText("● Berjalan" if running else "○ Berhenti")
        self.running_indicator.setStyleSheet(
            f"color: {color}; font-weight: 600;"
        )
        self.tray_start_action.setText("Berhenti Bell" if running else "Mulai Bell")
        self.add_button.setEnabled(not running)
        self.schedule_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
            if running
            else self._schedule_edit_triggers
        )
        self._update_edit_buttons()

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802 - Qt API
        super().changeEvent(event)
        if (
            event.type() == QEvent.Type.WindowStateChange
            and self.isMinimized()
            and self._tray_available
        ):
            QTimer.singleShot(0, self._hide_to_tray)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 - Qt API
        if self._tray_available and not self._quitting:
            event.ignore()
            self._hide_to_tray()
            return
        if not self._quitting:
            if not self._confirm_unsaved_changes():
                event.ignore()
                return
            if not self._confirm_stop_running(
                "Bell sedang berjalan. Hentikan bell dan keluar dari aplikasi?"
            ):
                event.ignore()
                return
        self._quitting = True
        self.controller.shutdown()
        self.tray_icon.hide()
        event.accept()
