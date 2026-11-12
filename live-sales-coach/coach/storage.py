"""Save each call to calls/YYYY-MM-DD_HH-MM/ (local only; the folder is gitignored)."""
from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

from .config import APP_DIR


class CallStore:
    """Writes into a hidden in-progress folder; finalize() either names it
    calls/YYYY-MM-DD_HH-MM/ (kept) or deletes it (call that went nowhere)."""

    def __init__(self, calls_dir: str = "calls", started: datetime | None = None) -> None:
        base = Path(calls_dir)
        if not base.is_absolute():
            base = APP_DIR / base
        self.base = base
        self.started = started or datetime.now()
        self.name = self.started.strftime("%Y-%m-%d_%H-%M")
        tmp = base / f".in-progress-{self.started.strftime('%Y%m%d-%H%M%S-%f')}"
        tmp.mkdir(parents=True, exist_ok=True)
        self.dir = tmp
        self.kept: bool | None = None
        self._coaching = open(tmp / "coaching.jsonl", "a", encoding="utf-8")

    def finalize(self, keep: bool) -> Path | None:
        """Keep: move to calls/<date_time>/ and return it. Discard: delete everything."""
        self.close()
        if self.kept is not None:
            return self.dir if self.kept else None
        if not keep:
            shutil.rmtree(self.dir, ignore_errors=True)
            self.kept = False
            return None
        path = self.base / self.name
        n = 2
        while path.exists():                  # two calls in the same minute
            path = self.base / f"{self.name}_{n}"
            n += 1
        self.dir.rename(path)
        self.dir = path
        self.kept = True
        return path

    def write_transcript(self, text: str) -> None:
        (self.dir / "transcript.txt").write_text(text + ("\n" if text else ""), encoding="utf-8")

    def log_coaching(self, record: dict, stamp: bool = True) -> None:
        if stamp:
            record = {"timestamp": datetime.now().isoformat(timespec="seconds"), **record}
        self._coaching.write(json.dumps(record, ensure_ascii=False) + "\n")
        self._coaching.flush()

    def write_metrics(self, metrics: dict) -> None:
        (self.dir / "metrics.json").write_text(json.dumps(metrics, indent=2, default=str), encoding="utf-8")

    def write_summary(self, summary: dict | None, meta: dict, error: str | None = None) -> None:
        lines = [f"# Call summary: {meta.get('title', 'Call')}", ""]
        lines.append(f"- Date: {meta.get('started', '')}")
        lines.append(f"- Length: {meta.get('length', '')}")
        lines.append(f"- Mode: {meta.get('mode', '')}")
        lines.append(f"- Overall score: {meta.get('overall', '–')}")
        lines.append("")
        if summary:
            if summary.get("overview"):
                lines += [summary["overview"], ""]
            for title, key in (("Key wins", "key_wins"), ("Missed opportunities", "missed_opportunities"),
                               ("Next steps", "next_steps")):
                lines.append(f"## {title}")
                lines += [f"- {x}" for x in summary.get(key) or []] or ["- (none)"]
                lines.append("")
        else:
            lines.append(f"Summary unavailable: {error or 'unknown error'}")
        (self.dir / "summary.md").write_text("\n".join(lines), encoding="utf-8")

    def close(self) -> None:
        if not self._coaching.closed:
            self._coaching.close()


# ---------------------------------------------------------------- browsing past calls
def calls_root(calls_dir: str = "calls") -> Path:
    base = Path(calls_dir)
    return base if base.is_absolute() else APP_DIR / base


def call_path(calls_dir: str, name: str) -> Path | None:
    """Resolve a call folder by name, refusing anything outside the calls folder."""
    root = calls_root(calls_dir).resolve()
    if not name or "/" in name or "\\" in name or name.startswith("."):
        return None
    p = (root / name).resolve()
    return p if p.parent == root and p.is_dir() else None


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def list_calls(calls_dir: str = "calls", limit: int = 200) -> list[dict]:
    """Newest first: name, title, start time, length, overall score, objections, questions."""
    root = calls_root(calls_dir)
    if not root.exists():
        return []
    out = []
    for d in sorted((p for p in root.iterdir() if p.is_dir() and not p.name.startswith(".")),
                    key=lambda p: p.name, reverse=True)[:limit]:
        m = _read_json(d / "metrics.json")
        meta = m.get("meta", {})
        out.append({
            "name": d.name,
            "title": meta.get("title") or "Call",
            "started": meta.get("started") or d.name,
            "length": meta.get("length") or "",
            "mode": meta.get("mode") or "",
            "overall": m.get("overall"),
            "objections": m.get("objection_count"),
            "questions": m.get("questions"),
            "has_summary": (d / "summary.md").exists(),
        })
    return out


def load_call(calls_dir: str, name: str) -> dict | None:
    d = call_path(calls_dir, name)
    if d is None:
        return None

    def text(fname: str) -> str:
        try:
            return (d / fname).read_text(encoding="utf-8")
        except OSError:
            return ""

    metrics = _read_json(d / "metrics.json")
    coaching = []
    for line in text("coaching.jsonl").splitlines():
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        coaching.append({k: rec.get(k) for k in ("timestamp", "call_time", "question", "say", "tactic", "watch", "latency_s")})
    return {
        "name": d.name,
        "path": str(d),
        "summary_md": text("summary.md"),
        "transcript": text("transcript.txt"),
        "metrics": {k: metrics.get(k) for k in ("meta", "scores", "score_details", "overall", "rep_share_pct",
                                                 "rep_wpm", "questions", "objection_count", "recommendations")},
        "coaching": coaching,
    }
