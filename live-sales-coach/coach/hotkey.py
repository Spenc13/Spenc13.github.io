"""System-wide hotkey (works while Google Meet or your dialer has focus)."""
from __future__ import annotations

import logging
from typing import Callable

log = logging.getLogger(__name__)


def pretty(combo: str) -> str:
    names = {"<ctrl>": "Ctrl", "<shift>": "Shift", "<space>": "Space", "<cmd>": "Cmd", "<alt>": "Alt"}
    return "+".join(names.get(p, p.strip("<>").title()) for p in combo.split("+"))


class GlobalHotkey:
    def __init__(self, combo: str, callback: Callable[[], None]) -> None:
        self.combo = combo
        self.callback = callback
        self.listener = None
        self.error: str | None = None

    def start(self) -> bool:
        try:
            from pynput import keyboard
        except Exception as e:   # not installed, or no display server
            self.error = f"pynput unavailable ({type(e).__name__})"
            return False
        try:
            self.listener = keyboard.GlobalHotKeys({self.combo: self.callback})
            self.listener.daemon = True
            self.listener.start()
            return True
        except Exception as e:
            self.error = f"{type(e).__name__}: {e}"
            log.warning("global hotkey unavailable: %s", self.error)
            return False

    def stop(self) -> None:
        if self.listener:
            self.listener.stop()
