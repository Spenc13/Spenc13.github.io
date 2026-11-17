"""Desktop-side state for the Call Breakdown tab (one breakdown at a time)."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable

from . import breakdown as bd
from .config import get
from .engine import CoachEngine, CoachUnavailable

log = logging.getLogger(__name__)


class BreakdownController:
    def __init__(self, cfg: dict, prompts, post: Callable[[str, dict], None], runner, keys_ok: bool) -> None:
        self.cfg = cfg
        self.prompts = prompts
        self.post = post
        self.runner = runner
        self.keys_ok = keys_ok
        self.rep = get(cfg, "rep_name", "Spencer Faircloth")
        self.reset()

    # ---- state -------------------------------------------------------------
    def reset(self) -> None:
        self.calls: list[dict] = []
        self.pending: dict[str, str] = {}        # path -> status while loading
        self.analysis: dict | None = None
        self.reflections: dict = {}
        self.final: dict | None = None
        self.changes: list[dict] = []
        self.busy = ""
        self.id = bd.new_breakdown_id()

    def snapshot(self) -> dict:
        plan = bd.load_plan(self.cfg, self.rep)
        return {
            "rep": self.rep,
            "calls": [{k: c[k] for k in ("id", "title", "source", "minutes", "rep", "speakers")} for c in self.calls],
            "pending": [{"path": Path(p).name, "status": s} for p, s in self.pending.items()],
            "analysis": self.analysis, "reflections": self.reflections, "final": self.final,
            "changes": self.changes, "busy": self.busy,
            "plan": [s for s in plan.get("steps", []) if s.get("status") != "retired"],
            "history": bd.list_breakdowns(self.cfg, self.rep)[:10],
            "can_analyze": bool(self.calls) and not self.busy and self.keys_ok and self.prompts is not None,
        }

    def publish(self) -> None:
        self.post("bd_state", self.snapshot())

    def _engine(self) -> CoachEngine:
        if self.prompts is None:
            raise CoachUnavailable("Prompt files are missing (see prompts/README.md)")
        return CoachEngine(self.cfg, self.prompts, self.keys_ok)

    def _save(self) -> None:
        if not self.analysis:
            return
        record = {"id": self.id, "rep": self.rep, "date": self.id[:16].replace("_", " "),
                  "calls": [{"id": c["id"], "title": c["title"], "source": c["source"], "path": c["path"],
                             "transcript": bd.normalize(c["rows"], c["rep"])} for c in self.calls],
                  "analysis": self.analysis, "reflections": self.reflections, "final": self.final,
                  "plan_changes": self.changes}
        bd.save_breakdown(self.cfg, self.rep, record)

    # ---- commands ----------------------------------------------------------
    def set_rep(self, name: str) -> None:
        name = " ".join((name or "").split())[:60]
        if name and name != self.rep:
            self.rep = name
            self.reset()
        self.publish()

    def add_paths(self, paths: list[str]) -> None:
        for p in paths:
            if not p or p in self.pending:
                continue
            self.pending[p] = "transcribing…" if Path(p).suffix.lower() in bd.AUDIO_EXT else "reading…"
            fut = self.runner.submit(bd.load_upload(Path(p), self.rep, self.cfg))

            def done(f, p=p):
                self.pending.pop(p, None)
                try:
                    self.calls.append(f.result())
                except Exception as e:
                    self.post("toast", {"level": "error", "text": f"{Path(p).name}: {e}"})
                self.publish()
            fut.add_done_callback(done)
        self.publish()

    def set_rep_speaker(self, call_id: int, label: str) -> None:
        for c in self.calls:
            if c["id"] == call_id and any(s["label"] == label for s in c["speakers"]):
                c["rep"] = label
        self.publish()

    def remove(self, call_id: int) -> None:
        self.calls = [c for c in self.calls if c["id"] != call_id]
        self.publish()

    def analyze(self) -> None:
        if not self.calls or self.busy:
            return
        self.busy = f"Breaking down {len(self.calls)} call{'s' if len(self.calls) != 1 else ''}…"
        self.analysis, self.final, self.reflections, self.changes = None, None, {}, []
        self.publish()
        plan = bd.load_plan(self.cfg, self.rep)
        steps = bd.active_steps(plan)

        async def go():
            return await self._engine().breakdown_analyze(self.rep, self.calls, steps)

        def done(f):
            self.busy = ""
            try:
                a = f.result()
                bd.number_improvements(a)
                self.analysis = a
                self.changes = bd.apply_progress(plan, a.get("step_progress", []), self.id)
                plan["rep"] = self.rep
                bd.save_plan(self.cfg, plan)
                self._save()
            except Exception as e:
                self.post("toast", {"level": "error", "text": f"Breakdown failed: {e}"})
            self.publish()
        self.runner.submit(go()).add_done_callback(done)

    def reflect(self, key: str, text: str) -> None:
        if self.analysis is None:
            return
        text = (text or "").strip()
        if text:
            self.reflections[str(key)] = text[:2000]
        else:
            self.reflections.pop(str(key), None)
        self._save()

    def finalize(self) -> None:
        if not self.analysis or self.busy:
            return
        self.busy = "Writing your action steps…"
        self.publish()
        plan = bd.load_plan(self.cfg, self.rep)
        steps = bd.active_steps(plan)

        async def go():
            return await self._engine().breakdown_finalize(self.rep, self.analysis, self.reflections, steps)

        def done(f):
            self.busy = ""
            try:
                fin = f.result()
                self.final = fin
                bd.apply_final_steps(plan, fin.get("action_steps", []), fin.get("carry_over", []), self.id)
                plan["rep"] = self.rep
                bd.save_plan(self.cfg, plan)
                self._save()
                self.post("toast", {"level": "info", "text": f"Action steps saved to {self.rep}'s plan."})
            except Exception as e:
                self.post("toast", {"level": "error", "text": f"Couldn't finish: {e}"})
            self.publish()
        self.runner.submit(go()).add_done_callback(done)
