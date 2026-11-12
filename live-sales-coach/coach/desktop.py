"""PySide6 desktop shell: QWebEngineView showing web/live-call-coach.html."""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

from PySide6.QtCore import QFile, QIODevice, QObject, QSettings, Qt, QUrl, Signal, Slot
from PySide6.QtGui import QAction, QKeySequence, QShortcut
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


class MainWindow(QMainWindow):
    def __init__(self, cfg: dict, start_replay: str | None = None) -> None:
        super().__init__()
        self.cfg = cfg
        self.start_replay = start_replay
        self.runner = AsyncRunner()
        self.session: CallSession | None = None
        self.settings = QSettings("OllyOlly", "LiveSalesCoach")

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
        self.runner.stop()
        super().closeEvent(event)

    # ------------------------------------------------------------ hotkey
    def trigger_hotkey_from_thread(self) -> None:
        # pynput calls this on its own thread; the session lives on the asyncio thread.
        if self.session and self.session.running:
            self.runner.submit(self.session.hotkey())

    def trigger_hotkey(self) -> None:
        self.trigger_hotkey_from_thread()

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
        elif cmd == "on_top":
            self.set_on_top(bool(msg.get("on")))

    def start_call(self, msg: dict) -> None:
        if not msg.get("consent"):
            self.bridge.post("toast", {"level": "error", "text": "Confirm the recording notice first."})
            return
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
        self.session = CallSession(self.cfg, self.prompts, self.bridge.post, mode, path)
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
