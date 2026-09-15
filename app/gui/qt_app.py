"""Shared Qt application setup for the desktop GUI."""

from __future__ import annotations

import signal
import sys
from collections.abc import Sequence

from PySide6.QtCore import QCoreApplication, QTimer
from PySide6.QtWidgets import QApplication


def get_qapp(argv: Sequence[str] | None = None) -> QApplication:
    """Return the process-wide :class:`QApplication` and wire clean SIGINT.

    The heartbeat timer lets Python periodically process ``Ctrl+C`` while Qt's
    event loop is running (notably needed on Windows). The timer is parented to
    the application so it remains alive for the entire GUI session.
    """
    instance = QCoreApplication.instance()
    if instance is None:
        app = QApplication(list(argv) if argv is not None else sys.argv)
    elif isinstance(instance, QApplication):
        app = instance
    else:
        raise RuntimeError(
            "QCoreApplication sudah dibuat; GUI memerlukan QApplication sejak awal"
        )

    _install_sigint_handler(app)
    return app


def _install_sigint_handler(app: QApplication) -> None:
    if getattr(app, "_bel_sigint_installed", False):
        return

    heartbeat = QTimer(app)
    heartbeat.setInterval(200)
    heartbeat.timeout.connect(lambda: None)
    heartbeat.start()

    try:
        previous_handler = signal.getsignal(signal.SIGINT)

        def handle_sigint(*_args) -> None:
            app.quit()

        signal.signal(signal.SIGINT, handle_sigint)
    except ValueError:
        # ``signal.signal`` is restricted to Python's main thread. GUI launchers
        # run there, but embedding the app elsewhere should still be possible.
        previous_handler = None
        handle_sigint = None

    app._bel_sigint_installed = True
    app._bel_sigint_heartbeat = heartbeat
    app._bel_previous_sigint = previous_handler
    app._bel_sigint_handler = handle_sigint

    def cleanup() -> None:
        heartbeat.stop()
        if handle_sigint is not None and signal.getsignal(signal.SIGINT) is handle_sigint:
            signal.signal(signal.SIGINT, previous_handler)

    app.aboutToQuit.connect(cleanup)
