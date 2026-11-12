"""Save each call to calls/YYYY-MM-DD_HH-MM/ (local only; the folder is gitignored)."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .config import APP_DIR


class CallStore:
    def __init__(self, calls_dir: str = "calls", started: datetime | None = None) -> None:
        base = Path(calls_dir)
        if not base.is_absolute():
            base = APP_DIR / base
        started = started or datetime.now()
        name = started.strftime("%Y-%m-%d_%H-%M")
        path = base / name
        n = 2
        while path.exists():                  # two calls in the same minute
            path = base / f"{name}_{n}"
            n += 1
        path.mkdir(parents=True, exist_ok=True)
        self.dir = path
        self._coaching = open(path / "coaching.jsonl", "a", encoding="utf-8")

    def write_transcript(self, text: str) -> None:
        (self.dir / "transcript.txt").write_text(text + ("\n" if text else ""), encoding="utf-8")

    def log_coaching(self, record: dict) -> None:
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
