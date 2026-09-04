"""Offscreen tests for unsaved-change and stop confirmations."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMessageBox

from app.gui.main_window import MainWindow


def _window():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    return app, window


def _close_without_prompt(window):
    window._dirty = False
    window._quitting = True
    window.controller.scheduler = None
    window.close()


def test_unsaved_changes_can_cancel_or_discard(monkeypatch):
    _app, window = _window()
    window._dirty = True
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *_args, **_kwargs: QMessageBox.StandardButton.Cancel,
    )
    assert not window._confirm_unsaved_changes()

    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *_args, **_kwargs: QMessageBox.StandardButton.Discard,
    )
    assert window._confirm_unsaved_changes()
    _close_without_prompt(window)


def test_unsaved_changes_save_option_calls_save(monkeypatch):
    _app, window = _window()
    window._dirty = True
    saved = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *_args, **_kwargs: QMessageBox.StandardButton.Save,
    )
    monkeypatch.setattr(window, "_save_schedule", lambda: saved.append(True) or True)

    assert window._confirm_unsaved_changes()
    assert saved == [True]
    _close_without_prompt(window)


def test_running_scheduler_requires_stop_confirmation(monkeypatch):
    _app, window = _window()
    window.controller.scheduler = object()
    stops = []

    def stop():
        stops.append(True)
        window.controller.scheduler = None

    monkeypatch.setattr(window.controller, "stop", stop)
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *_args, **_kwargs: QMessageBox.StandardButton.No,
    )
    assert not window._confirm_stop_running("Hentikan?")
    assert stops == []

    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *_args, **_kwargs: QMessageBox.StandardButton.Yes,
    )
    assert window._confirm_stop_running("Hentikan?")
    assert stops == [True]
    _close_without_prompt(window)


def test_svg_application_and_tray_icons_load():
    _app, window = _window()

    assert not window.windowIcon().isNull()
    assert not window.tray_icon.icon().isNull()
    _close_without_prompt(window)


def test_error_notice_can_be_dismissed():
    _app, window = _window()

    window._show_error("Contoh error")
    assert not window.notice_frame.isHidden()
    assert window.error_label.text() == "Contoh error"

    window.dismiss_notice_button.click()
    assert not window.notice_frame.isVisible()
    _close_without_prompt(window)
