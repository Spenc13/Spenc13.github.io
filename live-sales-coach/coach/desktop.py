"""PySide6 desktop shell: QWebEngineView showing web/live-call-coach.html."""
from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path

from PySide6.QtCore import QFile, QIODevice, QObject, QSettings, Qt, QUrl, Signal, Slot
from PySide6.QtGui import QAction, QDesktopServices, QKeySequence, QShortcut
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineScript, QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QApplication, QFileDialog, QMainWindow

from .config import (APP_DIR, WEB_DIR, MissingPrompts, get, hotkey_for_platform, keys_status,
                     load_prompts)
from .hotkey import GlobalHotkey, pretty
from .replay import script_title
from .runner import AsyncRunner
from .session import CallSession
from .phone_bridge import PhoneBridge
from .storage import call_path, calls_root, list_calls, load_call

log = logging.getLogger(__name__)


def list_samples() -> list[dict]:
    out = []
    for p in sorted((APP_DIR / "samples").glob("*.txt")) + sorted((APP_DIR / "samples").glob("*.wav")):
        title = script_title(p.read_text(encoding="utf-8"), p.stem) if p.suffix == ".txt" else p.stem
        out.append({"path": str(p), "title": title})
    return out


class Page(QWebEnginePage):
    """Forward page console errors to the log (useful when editing the HTML)."""

    def javaScriptConsoleMessage(self, level, message, line, source):  # noqa: N802
        if level != QWebEnginePage.JavaScriptConsoleMessageLevel.InfoMessageLevel:
            log.warning("page: %s (line %s)", message, line)


def _webchannel_script() -> QWebEngineScript:
    """qwebchannel.js ships inside Qt; inject it so the file:// page can use it."""
    f = QFile(":/qtwebchannel/qwebchannel.js")
    if not f.open(QIODevice.ReadOnly):
        raise RuntimeError("qwebchannel.js not found in Qt resources")
    src = bytes(f.readAll()).decode("utf-8")
    f.close()
    script = QWebEngineScript()
    script.setName("qwebchannel")
    script.setSourceCode(src)
    script.setInjectionPoint(QWebEngineScript.DocumentCreation)
    script.setWorldId(QWebEngineScript.MainWorld)
    script.setRunsOnSubFrames(False)
    return script


class Bridge(QObject):
    """JS <-> Python. JS calls command(json); Python emits event(json)."""

    event = Signal(str)
    _relay = Signal(str)

    def __init__(self, window: "MainWindow") -> None:
        super().__init__()
        self.window = window
        self._relay.connect(self.event.emit, Qt.QueuedConnection)

    def post(self, kind: str, data: dict) -> None:
        """Safe to call from any thread."""
        self._relay.emit(json.dumps({"type": kind, "data": data}, default=str))

    @Slot(str)
    def command(self, payload: str) -> None:
        try:
            msg = json.loads(payload)
        except json.JSONDecodeError:
            return
        self.window.handle_command(msg)


def call_label(info: dict) -> str:
    phone = info.get("phone") or ""
    digits = "".join(ch for ch in phone if ch.isdigit())
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    pretty_phone = f"({digits[:3]}) {digits[3:6]}-{digits[6:]}" if len(digits) == 10 else phone
    name = info.get("contact")
    return f"{name} · {pretty_phone}" if name and pretty_phone else (name or pretty_phone or "HubSpot call")


class MainWindow(QMainWindow):
    phone_event = Signal(object)

    def __init__(self, cfg: dict, start_replay: str | None = None) -> None:
        super().__init__()
        self.cfg = cfg
        self.start_replay = start_replay
        self.runner = AsyncRunner()
        self.session: CallSession | None = None
        self.calls_dir = get(cfg, "storage.calls_dir", "calls")
        self.pending_call: dict | None = None
        self.phone_linked = False
        self.phone_bridge: PhoneBridge | None = None
        self.phone_event.connect(self.handle_phone, Qt.QueuedConnection)
        if get(cfg, "phone_bridge.enabled", True):
            self.phone_bridge = PhoneBridge(
                int(get(cfg, "phone_bridge.port", 8765)),
                self.phone_event.emit,                      # called on the server thread
                calls_root(self.calls_dir) / ".phone-events.log",
            )
            self.phone_bridge.start()
        self.settings = QSettings("OllyOlly", "LiveSalesCoach")
        # Recording consent: "ask" = confirm before every recording;
        # "dialer" = the dialer already announces recording, so start right away.
        saved_consent = self.settings.value("consent_mode")
        self.consent_mode = saved_consent if saved_consent in ("ask", "dialer") else \
            ("dialer" if get(cfg, "recording.consent_mode", "ask") == "dialer" else "ask")
        saved_live = self.settings.value("live_mode")
        if saved_live is not None:
            cfg.setdefault("coach", {})["live_mode"] = saved_live in (True, "true")

        self.setWindowTitle("Live Sales Coach")
        self.resize(int(get(cfg, "window.width", 1440)), int(get(cfg, "window.height", 960)))
        geo = self.settings.value("geometry")
        if geo is not None:
            self.restoreGeometry(geo)       # comes back on the same (second) monitor

        self.view = QWebEngineView(self)
        self.view.setPage(Page(self.view))
        self.view.page().scripts().insert(_webchannel_script())
        s = self.view.settings()
        s.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)   # Google Fonts
        s.setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)     # spencer.png
        self.setCentralWidget(self.view)

        self.bridge = Bridge(self)
        self.channel = QWebChannel(self.view.page())
        self.channel.registerObject("bridge", self.bridge)
        self.view.page().setWebChannel(self.channel)
        self.view.load(QUrl.fromLocalFile(str(WEB_DIR / "live-call-coach.html")))

        # Menu: View > Stay on top
        on_top_saved = self.settings.value("on_top")
        on_top = bool(get(cfg, "window.stay_on_top", True)) if on_top_saved is None else on_top_saved in (True, "true")
        self.on_top_action = QAction("Stay on top", self, checkable=True)
        self.on_top_action.toggled.connect(self.set_on_top)
        view_menu = self.menuBar().addMenu("&View")
        view_menu.addAction(self.on_top_action)
        call_menu = self.menuBar().addMenu("&Call")
        self.combo = hotkey_for_platform(cfg)
        ask_action = QAction(f"Ask about the last few seconds ({pretty(self.combo)})", self)
        ask_action.triggered.connect(self.trigger_hotkey)
        call_menu.addAction(ask_action)
        focus_ask = QAction("Type a question", self)
        focus_ask.setShortcut(QKeySequence("Ctrl+K"))
        focus_ask.triggered.connect(lambda: self.bridge.post("focus_ask", {}))
        call_menu.addAction(focus_ask)
        call_menu.addSeparator()
        self.ask_consent_action = QAction("Ask before each recording", self, checkable=True)
        self.ask_consent_action.setChecked(self.consent_mode == "ask")
        self.ask_consent_action.toggled.connect(lambda on: self.set_consent_mode("ask" if on else "dialer"))
        call_menu.addAction(self.ask_consent_action)
        self.on_top_action.setChecked(on_top)
        self.set_on_top(on_top)

        # Hotkey: global if possible, else only while this window has focus.
        self.global_hotkey = None
        if get(cfg, "hotkey.global", True):
            gh = GlobalHotkey(self.combo, self.trigger_hotkey_from_thread)
            if gh.start():
                self.global_hotkey = gh
        if self.global_hotkey is None:
            seq = "Meta+Shift+Space" if sys.platform == "darwin" else "Ctrl+Shift+Space"
            QShortcut(QKeySequence(seq), self, activated=self.trigger_hotkey)

        try:
            self.prompts = load_prompts()
            self.prompts_error = None
        except MissingPrompts as e:
            self.prompts = None
            self.prompts_error = str(e)

    # ------------------------------------------------------------ window
    def set_on_top(self, on: bool) -> None:
        self.setWindowFlag(Qt.WindowStaysOnTopHint, bool(on))
        self.show()
        self.settings.setValue("on_top", bool(on))
        if self.on_top_action.isChecked() != bool(on):
            self.on_top_action.setChecked(bool(on))
        self.bridge.post("on_top", {"on_top": bool(on)})

    def set_consent_mode(self, mode: str) -> None:
        mode = "dialer" if mode == "dialer" else "ask"
        if mode == self.consent_mode:
            return
        self.consent_mode = mode
        self.settings.setValue("consent_mode", mode)
        if self.ask_consent_action.isChecked() != (mode == "ask"):
            self.ask_consent_action.setChecked(mode == "ask")
        self.bridge.post("consent_mode", {"mode": mode})
        self.bridge.post("toast", {"level": "info", "text": (
            "Recording starts right away now (your dialer announces it). Turn the prompt back on in Call menu → Ask before each recording."
            if mode == "dialer" else "You'll confirm the recording notice before each call again.")})

    def closeEvent(self, event) -> None:
        self.settings.setValue("geometry", self.saveGeometry())
        if self.session and self.session.running:
            fut = self.runner.submit(self.session.end())
            try:
                fut.result(timeout=60)
            except Exception:
                pass
        if self.global_hotkey:
            self.global_hotkey.stop()
        if self.phone_bridge:
            self.phone_bridge.stop()
        self.runner.stop()
        super().closeEvent(event)

    # ------------------------------------------------------------ hotkey
    def trigger_hotkey_from_thread(self) -> None:
        # pynput calls this on its own thread; the session lives on the asyncio thread.
        if self.session and self.session.running:
            self.runner.submit(self.session.hotkey())

    def trigger_hotkey(self) -> None:
        self.trigger_hotkey_from_thread()

    # ------------------------------------------------------------ dialer events
    def handle_phone(self, ev: dict) -> None:
        kind = ev.get("event")
        busy = bool(self.session and self.session.running)
        if kind == "hello":
            if not self.phone_linked:
                self.phone_linked = True
                self.bridge.post("phone_link", {"connected": True})
            return
        if not self.phone_linked:
            self.phone_linked = True
            self.bridge.post("phone_link", {"connected": True})
        info = {k: ev.get(k) for k in ("phone", "contact", "direction", "callId") if ev.get(k)}
        if kind == "ringing":
            if busy:
                return
            self.pending_call = {**(self.pending_call or {}), **info, "state": "ringing", "at": time.monotonic()}
            self.bridge.post("phone", {"state": "ringing", "label": call_label(self.pending_call)})
        elif kind == "answered":
            if busy:
                return
            self.pending_call = {**(self.pending_call or {}), **info, "state": "answered", "at": time.monotonic()}
            self.showNormal()
            self.raise_()
            self.activateWindow()
            auto = self.consent_mode == "dialer" and self.prompts is not None
            self.bridge.post("phone", {"state": "answered", "label": call_label(self.pending_call), "auto": auto})
            if auto:
                self.start_call({"mode": "live", "consent": True, "basis": "dialer"})
        elif kind == "ended":
            self.pending_call = None
            self.bridge.post("phone", {"state": "ended"})
            if busy and self.session.mode == "live":
                self.runner.submit(self.session.end())

    # ------------------------------------------------------------ commands from JS
    def handle_command(self, msg: dict) -> None:
        cmd = msg.get("cmd")
        if cmd == "ready":
            default_mode = "live"
            if self.start_replay:
                default_mode = "replay:" + str(Path(self.start_replay).resolve())
            samples = list_samples()
            if self.start_replay and not any(s["path"] == str(Path(self.start_replay).resolve()) for s in samples):
                p = Path(self.start_replay).resolve()
                samples.append({"path": str(p), "title": p.stem})
            self.bridge.post("init", {
                "rep_name": get(self.cfg, "rep_name", "Spencer Faircloth"),
                "rep_title": get(self.cfg, "rep_title", "Sales Rep"),
                "hotkey_label": pretty(self.combo) + ("" if self.global_hotkey else " (window only)"),
                "on_top": self.on_top_action.isChecked(),
                "samples": samples,
                "default_mode": default_mode,
                "keys": keys_status(),
                "prompts_ok": self.prompts is not None,
                "consent_mode": self.consent_mode,
                "live_mode": bool(get(self.cfg, "coach.live_mode", True)),
                "phone_bridge": {"enabled": self.phone_bridge is not None,
                                 "error": self.phone_bridge.error if self.phone_bridge else None,
                                 "linked": self.phone_linked},
                "prompts_error": self.prompts_error,
                "health": {"stt": {"state": "idle", "message": ""},
                           "coach": {"state": "ok" if keys_status()["anthropic"] else "down",
                                     "message": "" if keys_status()["anthropic"] else "ANTHROPIC_API_KEY not set"}},
            })
        elif cmd == "pick_replay":
            path, _ = QFileDialog.getOpenFileName(self, "Choose a replay file", str(APP_DIR / "samples"),
                                                  "Call recordings or scripts (*.wav *.txt)")
            self.bridge.post("picked", {"path": path, "name": Path(path).name if path else ""})
        elif cmd == "start":
            self.start_call(msg)
        elif cmd == "pause" and self.session:
            self.runner.call(self.session.pause)
        elif cmd == "resume" and self.session:
            self.runner.call(self.session.resume)
        elif cmd == "end" and self.session:
            self.runner.submit(self.session.end())
        elif cmd == "ask":
            if self.session and self.session.running:
                self.runner.submit(self.session.ask(msg.get("text", "")))
            else:
                self.bridge.post("toast", {"level": "info", "text": "Start a call (or a replay) first, then ask the coach."})
        elif cmd == "suggestion" and self.session and self.session.running:
            self.runner.submit(self.session.suggestion(msg.get("key", "")))
        elif cmd == "keep_call" and self.session and not self.session.running:
            self.runner.submit(self.session.save_anyway())
        elif cmd == "dismiss_phone":
            pass        # keep the caller's number in case coaching is started later in the call
        elif cmd == "consent_mode":
            self.set_consent_mode(str(msg.get("mode", "ask")))
        elif cmd == "list_calls":
            self.bridge.post("calls", {"calls": list_calls(self.calls_dir)})
        elif cmd == "get_call":
            detail = load_call(self.calls_dir, str(msg.get("name", "")))
            self.bridge.post("call_detail", detail or {"error": "That call folder wasn't found."})
        elif cmd == "open_folder":
            name = str(msg.get("name") or "")
            target = call_path(self.calls_dir, name) if name else calls_root(self.calls_dir)
            if target is None or not target.exists():
                self.bridge.post("toast", {"level": "error", "text": "That call folder wasn't found."})
            else:
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))
        elif cmd == "copy_summary":
            detail = load_call(self.calls_dir, str(msg.get("name", "")))
            if detail and detail["summary_md"]:
                QApplication.clipboard().setText(detail["summary_md"])
                self.bridge.post("toast", {"level": "info", "text": "Summary copied. Paste it into HubSpot notes."})
            else:
                self.bridge.post("toast", {"level": "error", "text": "No summary saved for that call."})
        elif cmd == "swap_speakers" and self.session and self.session.running:
            self.runner.call(self.session.swap_speakers)
        elif cmd == "live_mode":
            on = bool(msg.get("on"))
            self.cfg.setdefault("coach", {})["live_mode"] = on      # next calls too
            self.settings.setValue("live_mode", on)
            if self.session and self.session.running:
                self.runner.call(self.session.set_live_mode, on)
        elif cmd == "on_top":
            self.set_on_top(bool(msg.get("on")))

    def start_call(self, msg: dict) -> None:
        if not msg.get("consent") and self.consent_mode != "dialer":
            self.bridge.post("toast", {"level": "error", "text": "Confirm the recording notice first."})
            return
        basis = "dialer disclosure" if (msg.get("basis") == "dialer" or self.consent_mode == "dialer") else "rep confirmed"
        if self.prompts is None:
            self.bridge.post("toast", {"level": "error", "text": self.prompts_error})
            self.bridge.post("call", {"state": "idle"})
            return
        if self.session and self.session.running:
            return
        mode_value = msg.get("mode", "live")
        if mode_value.startswith("replay:"):
            path = mode_value[len("replay:"):]
            mode = "replay_wav" if path.lower().endswith(".wav") else "replay_text"
        else:
            path, mode = None, "live"
        info = None
        fresh = self.pending_call and time.monotonic() - self.pending_call.get("at", 0) < 2 * 3600
        if mode == "live" and fresh:
            info = {k: v for k, v in self.pending_call.items() if k not in ("state", "at")}
        self.session = CallSession(self.cfg, self.prompts, self.bridge.post, mode, path, info)
        self.session.consent_basis = basis
        if info and self.pending_call.get("state") == "answered":
            missed = time.monotonic() - self.pending_call.get("at", time.monotonic())
            if missed > 15:
                self.session.mark_joined_mid_call(missed)
        fut = self.runner.submit(self.session.start())

        def done(f):
            exc = f.exception()
            if exc:
                self.bridge.post("toast", {"level": "error", "text": f"Couldn't start: {exc}"})
                self.bridge.post("call", {"state": "idle"})
        fut.add_done_callback(done)


def run_desktop(cfg: dict, start_replay: str | None = None) -> int:
    QApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
    app = QApplication(sys.argv)
    app.setApplicationName("Live Sales Coach")
    win = MainWindow(cfg, start_replay)
    win.show()
    return app.exec()
