"""Command-line interface for ``bel``.

    bel start <config.toml> [--dry-run] [--volume 0.8] [--force]
    bel check <config.toml>
    bel sounds                 # list available sounds in assets/
    bel test-sound [file.mp3]  # play one sound to verify audio

``check``, ``sounds``, and ``--dry-run`` remain Qt-free. Real playback uses a
Qt event loop so Qt Multimedia can deliver asynchronous audio events.
"""

from __future__ import annotations

import argparse
import signal
import sys
from pathlib import Path

from . import __version__
from .audio import NullBackend
from .config import (
    load_timetable,
    resolve_sound_dir,
    validate_sound_files,
    validate_timetable,
)
from .logging_setup import setup_logging
from .models import DAY_LABEL, Timetable
from .paths import asset, assets_dir
from .scheduler import BellScheduler


def _print_rundown(timetable: Timetable) -> None:
    print("\n=== Rundown Mingguan ===")
    for day, bells in timetable:
        print(f"\n|| Hari {DAY_LABEL[day]}")
        if not bells:
            print("  (tidak ada bell)")
        for i, b in enumerate(bells, 1):
            print(f"   {i:>2}. {b.jam}  ->  {b.file}")
    print("\n" + "=" * 40)


# ---------------------------------------------------------------- commands
def cmd_check(args: argparse.Namespace) -> int:
    setup_logging()
    timetable, err = _load(args.config)
    if err:
        return err
    result = validate_timetable(timetable)
    if result.ok:
        print(f"✓ Konfig valid — {timetable.total} bell terjadwalkan.")
        _print_rundown(timetable)
        return 0
    print(f"✗ Ditemukan {len(result.errors)} error:", file=sys.stderr)
    for e in result.errors:
        print(f"   - [{e.day}] {e.message}", file=sys.stderr)
    return 1


def cmd_start(args: argparse.Namespace) -> int:
    log = setup_logging(verbose=args.verbose)
    log.info("bel-pelajaran %s", __version__)

    timetable, err = _load(args.config)
    if err:
        return err

    result = validate_timetable(timetable)
    if not result.ok and not args.force:
        print(
            f"Konfig punya {len(result.errors)} error. Perbaiki dulu atau ulangi "
            "dengan --force (bell bermasalah akan dilewati).",
            file=sys.stderr,
        )
        for e in result.errors:
            print(f"   - [{e.day}] {e.message}", file=sys.stderr)
        return 1
    if result.errors and args.force:
        log.warning("berjalan dengan %d error validasi (--force)", len(result.errors))

    if args.dry_run:
        log.warning("mode --dry-run: tidak ada suara yang akan diputar")
        backend = NullBackend()
        engine = BellScheduler(timetable, backend)
        engine.arm()
        _print_rundown(timetable)
        _log_next_bell(engine, log)
        engine.run()
        return 0

    try:
        from PySide6.QtCore import QCoreApplication, QTimer
        from .audio import QtMultimediaBackend
        from .gui.audio_selftest import self_test_audio
    except ImportError as exc:
        print(
            f"Audio Qt tidak tersedia: {exc}. Install dengan `uv sync --extra qt`.",
            file=sys.stderr,
        )
        return 2

    sound_result = validate_sound_files(timetable)
    if not sound_result.ok:
        print("Audio jadwal belum siap:", file=sys.stderr)
        for item in sound_result.errors:
            print(f"   - [{item.day}] {item.message}", file=sys.stderr)
        return 3

    sound_dir = resolve_sound_dir(timetable)
    samples = sorted(sound_dir.glob("*.mp3"))
    if not samples:
        print(f"Audio gagal: tidak ada file mp3 di {sound_dir}.", file=sys.stderr)
        return 3

    qt_app = QCoreApplication.instance() or QCoreApplication(sys.argv)
    ok, message = self_test_audio(
        lambda **kwargs: QtMultimediaBackend(volume=args.volume, **kwargs),
        samples[0],
    )
    if not ok:
        print(
            f"Audio gagal memutar mp3: {message}. Periksa perangkat audio dan "
            "codec/GStreamer.",
            file=sys.stderr,
        )
        return 3

    try:
        backend = QtMultimediaBackend(
            volume=args.volume,
            on_error=lambda message: log.error("audio: %s", message),
        )
    except Exception as exc:
        print(f"Error: audio backend gagal diinisialisasi: {exc}", file=sys.stderr)
        return 2

    engine = BellScheduler(
        timetable,
        backend,
        on_error=lambda day, bell, exc: log.error(
            "error bell %s %s: %s", day, bell.jam, exc
        ),
        sound_dir=sound_dir,
    )
    engine.arm()
    engine.tick()
    _print_rundown(timetable)
    _log_next_bell(engine, log)

    timer = QTimer()
    timer.setInterval(1000)
    timer.timeout.connect(engine.tick)
    timer.start()
    heartbeat = QTimer()
    heartbeat.setInterval(200)
    heartbeat.timeout.connect(lambda: None)
    heartbeat.start()

    previous_sigint = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, lambda *_: qt_app.quit())
    try:
        log.info("scheduler berjalan... (Ctrl+C untuk berhenti)")
        qt_app.exec()
    finally:
        signal.signal(signal.SIGINT, previous_sigint)
        timer.stop()
        heartbeat.stop()
        engine.stop()
        backend.stop()
    return 0


def cmd_sounds(args: argparse.Namespace) -> int:
    setup_logging()
    sounds = sorted(p.name for p in assets_dir().glob("*.mp3"))
    if not sounds:
        print("Tidak ada file suara di assets/.", file=sys.stderr)
        return 1
    print(f"{len(sounds)} suara tersedia di assets/:")
    for s in sounds:
        print(f"   - {s}")
    return 0


def cmd_test_sound(args: argparse.Namespace) -> int:
    setup_logging()
    name = args.file
    if not name:
        mp3s = sorted(assets_dir().glob("*.mp3"))
        if not mp3s:
            print("Tidak ada file suara di assets/.", file=sys.stderr)
            return 1
        name = mp3s[0].name
    path = asset(name)
    if not path.is_file():
        print(f"Error: {name} tidak ditemukan di assets/.", file=sys.stderr)
        return 1

    try:
        from PySide6.QtCore import QCoreApplication, QTimer
        from .audio import QtMultimediaBackend
    except ImportError as exc:
        print(
            f"Error: PySide6 tidak tersedia: {exc}. "
            "Install dengan `uv sync --extra qt`.",
            file=sys.stderr,
        )
        return 2

    qt_app = QCoreApplication.instance() or QCoreApplication(sys.argv)
    errors: list[str] = []

    def on_backend_error(message: str) -> None:
        errors.append(str(message))
        qt_app.quit()

    try:
        backend = QtMultimediaBackend(
            volume=args.volume,
            on_error=on_backend_error,
        )
    except Exception as exc:
        print(f"Error: audio backend gagal diinisialisasi: {exc}", file=sys.stderr)
        return 2

    player = backend.player

    def on_media_status_changed(status) -> None:
        from PySide6.QtMultimedia import QMediaPlayer

        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            qt_app.quit()

    player.mediaStatusChanged.connect(on_media_status_changed)
    print(f"Memutar {name} ...")
    if not backend.play(path):
        backend.stop()
        print(f"Error: audio gagal memulai {name}.", file=sys.stderr)
        return 2

    heartbeat = QTimer()
    heartbeat.setInterval(200)
    heartbeat.timeout.connect(lambda: None)
    heartbeat.start()
    previous_sigint = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, lambda *_: qt_app.quit())
    try:
        qt_app.exec()
    finally:
        signal.signal(signal.SIGINT, previous_sigint)
        heartbeat.stop()
        backend.stop()

    if errors:
        print(f"Error: audio gagal memutar {name}: {errors[-1]}", file=sys.stderr)
        return 2
    return 0


# ----------------------------------------------------------------- helpers
def _load(config_path: str) -> tuple[Timetable | None, int]:
    """Load + parse a config file; returns (timetable, 0) or (None, exit_code)."""
    try:
        timetable = load_timetable(config_path)
    except FileNotFoundError:
        print(f"Error: file konfig tidak ditemukan: {config_path}", file=sys.stderr)
        return None, 2
    except Exception as exc:
        print(f"Error: gagal membaca konfig ({config_path}): {exc}", file=sys.stderr)
        return None, 2
    return timetable, 0


def _log_next_bell(engine: BellScheduler, log) -> None:
    nxt = engine.next_bell_today()
    if nxt:
        day, bell = nxt
        log.info("bell berikutnya hari ini: %s %s (%s)", DAY_LABEL[day], bell.jam, bell.file)


# -------------------------------------------------------------------- parser
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="bel",
        description="Bel Pembelajaran sekolah — jadwal bel otomatis.",
    )
    p.add_argument("--version", action="version", version=f"bel {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("start", help="Jalankan bell scheduler")
    sp.add_argument("config", help="File konfig .toml")
    sp.add_argument("--dry-run", action="store_true", help="Jangan bunyikan suara (simulasi)")
    sp.add_argument("--force", action="store_true", help="Jalan meski ada error validasi")
    sp.add_argument("--volume", type=float, default=1.0, help="Volume 0.0–1.0 (default 1.0)")
    sp.add_argument("-v", "--verbose", action="store_true", help="Logging DEBUG")
    sp.set_defaults(func=cmd_start)

    cp = sub.add_parser("check", help="Validasi file konfig")
    cp.add_argument("config", help="File konfig .toml")
    cp.set_defaults(func=cmd_check)

    sub.add_parser("sounds", help="Daftar suara di assets/").set_defaults(func=cmd_sounds)

    tp = sub.add_parser("test-sound", help="Putar sebuah file suara")
    tp.add_argument("file", nargs="?", help="Nama file (default: suara pertama di assets/)")
    tp.add_argument("--volume", type=float, default=1.0, help="Volume 0.0–1.0")
    tp.set_defaults(func=cmd_test_sound)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
