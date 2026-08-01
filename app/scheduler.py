"""The scheduling engine.

Decoupled from the config source and the audio backend:

    timetable = config.load_timetable("configs/konfig.toml")
    backend   = audio.PygameBackend()
    engine    = scheduler.BellScheduler(timetable, backend)
    engine.arm()
    engine.run()                 # blocking loop, for the CLI
    # or, from a GUI:
    engine.start_in_thread()     # daemon thread + callbacks

Robustness (Phase 0 hardening):

* Playback is delegated to the (non-blocking) backend, so a long clip never
  delays or skips the next bell.
* Each job is wrapped in try/except, so one bad/missing file cannot crash the
  whole day.
* Arming is per-bell try/except, so a single malformed entry is skipped, not
  fatal.
* All fires, skips and errors are logged.
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from typing import Callable

import schedule as sched_lib

from .audio import AudioBackend
from .models import WEEKDAY_INDEX_TO_DAY, WEEKDAY_TOKEN, Bell, Timetable
from .paths import asset

log = logging.getLogger(__name__)


class BellScheduler:
    def __init__(self, timetable: Timetable, backend: AudioBackend) -> None:
        self.timetable = timetable
        self.backend = backend
        self._stop = threading.Event()

    # ------------------------------------------------------------------ arm
    def arm(self) -> int:
        """Register every bell with the `schedule` library.

        Returns the number of bells successfully armed.
        """
        sched_lib.clear()
        armed = 0
        for day, bells in self.timetable:
            token = WEEKDAY_TOKEN.get(day)
            if token is None:
                continue
            for bell in bells:
                try:
                    getattr(sched_lib.every(), token).at(bell.jam).do(
                        self._fire, day=day, bell=bell
                    )
                    armed += 1
                    log.info("dijadwalkan: %s %s -> %s", day, bell.jam, bell.file)
                except Exception as exc:
                    # e.g. malformed time with --force; skip, don't crash.
                    log.error("lewati bell tidak valid: %s %s (%s)", day, bell.jam, exc)
        log.info("total bell terjadwalkan: %d", armed)
        return armed

    # ----------------------------------------------------------------- fire
    def _fire(self, day: str, bell: Bell) -> None:
        """Job callback. Must never raise — a crash here stops the whole day."""
        try:
            path = asset(bell.file)
            log.info(">>> BELL  [%s %s]  %s", day, bell.jam, bell.file)
            if not self.backend.play(path):
                log.error("bell tidak terputar: %s %s (%s)", day, bell.jam, bell.file)
        except Exception as exc:  # pragma: no cover - defensive
            log.exception("error tak terduga saat membunyikan bell: %s", exc)

    # ------------------------------------------------------------------ run
    def run(self, interval: float = 1.0) -> None:
        """Blocking scheduler loop. Call after :meth:`arm`.

        Catches KeyboardInterrupt for a clean shutdown.
        """
        log.info("scheduler berjalan... (Ctrl+C untuk berhenti)")
        self._stop.clear()
        try:
            while not self._stop.is_set():
                try:
                    sched_lib.run_pending()
                except Exception:
                    log.exception("error pada run_pending (dilanjutkan)")
                self._stop.wait(interval)
        except KeyboardInterrupt:
            log.info("dihentikan oleh pengguna")
        finally:
            try:
                self.backend.stop()
            except Exception:
                pass

    def stop(self) -> None:
        self._stop.set()

    def start_in_thread(self, interval: float = 1.0) -> threading.Thread:
        """Run :meth:`run` in a daemon thread (for a GUI)."""
        t = threading.Thread(target=self.run, args=(interval,), daemon=True, name="bell-scheduler")
        t.start()
        return t

    # --------------------------------------------------------- introspection
    def next_bell_today(self) -> tuple[str, Bell] | None:
        """Return ``(day, bell)`` for the next upcoming bell today, or None.

        Returns None on a day off (Sunday) or when today's bells are spent.
        """
        idx = datetime.now().weekday()
        day = WEEKDAY_INDEX_TO_DAY.get(idx)
        if day is None:
            return None
        now = datetime.now().strftime("%H:%M")
        for bell in sorted(self.timetable.bells_for(day), key=lambda b: b.jam):
            if bell.jam > now:
                return day, bell
        return None
