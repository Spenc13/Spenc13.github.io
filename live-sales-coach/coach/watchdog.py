"""Diagnostics: a log file, and a freeze recorder for the window.

If the window stops responding for FREEZE_SECONDS, Python's faulthandler writes
what every thread was doing to logs/freeze-log.txt. It runs in its own C thread,
so it works even when the app is completely stuck. Nothing about the call
(transcript, names, keys) goes into either file: only code locations and errors.
"""
from __future__ import annotations

import faulthandler
import logging
import logging.handlers
import time
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
FREEZE_SECONDS = 4.0

_freeze_file = None


def setup_file_log() -> Path | None:
    """Write coach INFO logs to logs/coach.log (rotated, small)."""
    try:
        LOG_DIR.mkdir(exist_ok=True)
        path = LOG_DIR / "coach.log"
        h = logging.handlers.RotatingFileHandler(path, maxBytes=1_000_000, backupCount=2, encoding="utf-8")
        h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(threadName)s %(name)s: %(message)s"))
        h.setLevel(logging.INFO)
        coach = logging.getLogger("coach")
        coach.setLevel(logging.INFO)
        coach.addHandler(h)
        return path
    except Exception:
        return None


class FreezeWatch:
    """Re-armed by a Qt timer on the window thread. If the window thread stops
    re-arming it, faulthandler dumps every thread's stack."""

    def __init__(self, seconds: float = FREEZE_SECONDS) -> None:
        global _freeze_file
        self.seconds = seconds
        self.ok = False
        try:
            LOG_DIR.mkdir(exist_ok=True)
            if _freeze_file is None:
                _freeze_file = open(LOG_DIR / "freeze-log.txt", "a", encoding="utf-8")
            _freeze_file.write(f"\n=== app started {time.strftime('%Y-%m-%d %H:%M:%S')} "
                               f"(a stack dump below this line means the window froze for {seconds:g}s+) ===\n")
            _freeze_file.flush()
            self.ok = True
        except Exception:
            self.ok = False

    def mark(self, what: str) -> None:
        """Note what the app is about to do, so a dump can be matched to it."""
        if self.ok:
            try:
                _freeze_file.write(f"{time.strftime('%H:%M:%S')} {what}\n")
                _freeze_file.flush()
            except Exception:
                pass

    def beat(self) -> None:
        if self.ok:
            faulthandler.dump_traceback_later(self.seconds, repeat=False, file=_freeze_file, exit=False)

    def stop(self) -> None:
        if self.ok:
            faulthandler.cancel_dump_traceback_later()
