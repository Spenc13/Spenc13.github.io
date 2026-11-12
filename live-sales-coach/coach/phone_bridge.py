"""Local link to the "Olly Coach Bridge" Chrome extension.

The extension watches the HubSpot/Aloware dialer and POSTs call events here:
ringing, answered, ended (plus "hello" and "seen" for diagnostics). The server
listens on 127.0.0.1 only and accepts requests only from a Chrome extension
(Origin chrome-extension://...) carrying the X-Olly-Coach header, so ordinary
web pages can't trigger it.
"""
from __future__ import annotations

import json
import logging
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable

log = logging.getLogger(__name__)

EVENTS = {"hello", "ringing", "answered", "ended", "seen"}
MAX_BODY = 4096


def clean_event(data: dict) -> dict | None:
    """Keep only known, short, plain fields."""
    if not isinstance(data, dict):
        return None
    ev = str(data.get("event", ""))
    if ev not in EVENTS:
        return None
    out = {"event": ev}
    for k in ("phone", "contact", "direction", "callId", "type", "source"):
        v = data.get(k)
        if isinstance(v, (str, int)) and str(v).strip():
            out[k] = str(v).strip()[:120]
    if out.get("direction") not in (None, "inbound", "outbound"):
        out.pop("direction")
    return out


class PhoneBridge:
    def __init__(self, port: int, on_event: Callable[[dict], None], log_path: Path | None = None) -> None:
        self.port = port
        self.on_event = on_event
        self.log_path = log_path
        self.server: ThreadingHTTPServer | None = None
        self.error: str | None = None

    def _log_seen(self, ev: dict) -> None:
        if not self.log_path:
            return
        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps({"at": datetime.now().isoformat(timespec="seconds"),
                                    **{k: ev.get(k) for k in ("event", "type", "source")}}) + "\n")
        except OSError:
            pass

    def start(self) -> bool:
        bridge = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):  # keep the console quiet
                pass

            def _deny(self, code=403):
                self.send_response(code)
                self.send_header("Content-Length", "0")
                self.end_headers()

            def _allowed(self) -> bool:
                origin = self.headers.get("Origin", "")
                return origin.startswith("chrome-extension://") and self.headers.get("X-Olly-Coach") == "1"

            def do_OPTIONS(self):  # no CORS for web pages
                self._deny()

            def do_GET(self):
                self._deny(404)

            def do_POST(self):
                if self.path != "/phone" or not self._allowed():
                    return self._deny()
                try:
                    n = int(self.headers.get("Content-Length", "0"))
                except ValueError:
                    return self._deny(400)
                if n <= 0 or n > MAX_BODY:
                    return self._deny(400)
                try:
                    data = json.loads(self.rfile.read(n).decode("utf-8"))
                except (ValueError, UnicodeDecodeError):
                    return self._deny(400)
                ev = clean_event(data)
                if ev is None:
                    return self._deny(400)
                if ev["event"] in ("seen", "ringing", "answered", "ended"):
                    bridge._log_seen(ev)
                body = b'{"ok":true}'
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                if ev["event"] != "seen":
                    try:
                        bridge.on_event(ev)
                    except Exception:
                        log.exception("phone event handler failed")

        try:
            self.server = ThreadingHTTPServer(("127.0.0.1", self.port), Handler)
        except OSError as e:
            self.error = f"port {self.port} unavailable ({e.strerror or e})"
            log.warning("phone bridge not started: %s", self.error)
            return False
        threading.Thread(target=self.server.serve_forever, name="phone-bridge", daemon=True).start()
        return True

    def stop(self) -> None:
        if self.server:
            self.server.shutdown()
            self.server.server_close()
