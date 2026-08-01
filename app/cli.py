"""Command-line interface for ``bel``.

    bel start <config.toml> [--dry-run] [--volume 0.8] [--force]
    bel check <config.toml>
    bel sounds                 # list available sounds in assets/
    bel test-sound [file.mp3]  # play one sound to verify audio
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from . import __version__
from .audio import NullBackend, PygameBackend
from .config import load_timetable, validate_timetable
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

    backend = _make_backend(args)
    engine = BellScheduler(timetable, backend)
    engine.arm()
    _print_rundown(timetable)

    nxt = engine.next_bell_today()
    if nxt:
        day, bell = nxt
        log.info("bell berikutnya hari ini: %s %s (%s)", DAY_LABEL[day], bell.jam, bell.file)

    engine.run()
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
        backend = PygameBackend(volume=args.volume)
    except Exception as exc:
        print(f"Error: audio backend gagal diinisialisasi: {exc}", file=sys.stderr)
        return 2

    print(f"Memutar {name} ...")
    backend.play(path)
    import time as _t

    while backend.is_playing():
        _t.sleep(0.1)
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


def _make_backend(args: argparse.Namespace) -> object:
    log = logging.getLogger("app")
    if getattr(args, "dry_run", False):
        log.warning("mode --dry-run: tidak ada suara yang akan diputar")
        return NullBackend()
    try:
        return PygameBackend(volume=args.volume)
    except Exception as exc:
        # Audio failed (no device, etc.). Keep the scheduler alive and log what
        # WOULD have played — better than crashing on a school morning.
        log.error("audio backend gagal init (%s); menggunakan NullBackend", exc)
        return NullBackend()


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
