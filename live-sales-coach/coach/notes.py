"""Spencer's selling notes: proposed after each call, saved only when he approves.

Approved notes live in spencer-selling-style.md (gitignored: personal coaching
material) and load into the coach's context before every call, separate from
the playbook.
"""
from __future__ import annotations

import itertools
from datetime import datetime
from pathlib import Path

from .config import APP_DIR, get

HEADER = ("# Spencer's selling notes\n\n"
          "Standing rules and habits, approved by Spencer after calls. Loaded into every call.\n\n")
_ids = itertools.count(1)


def style_path(cfg: dict) -> Path:
    p = Path(get(cfg, "notes.style_file", "spencer-selling-style.md"))
    return p if p.is_absolute() else APP_DIR / p


def load_style(cfg: dict) -> str:
    p = style_path(cfg)
    try:
        return p.read_text(encoding="utf-8")
    except OSError:
        return ""


def save_note(cfg: dict, text: str, call_name: str | None, timestamp: str | None) -> Path:
    """Append one approved note with its citation."""
    p = style_path(cfg)
    if not p.exists():
        p.write_text(HEADER, encoding="utf-8")
    cite = []
    if call_name:
        cite.append(f"call {call_name}")
    if timestamp:
        cite.append(f"at {timestamp}")
    date = datetime.now().strftime("%Y-%m-%d")
    line = f"- {' '.join(text.split())}" + (f" _(from {' '.join(cite)}; approved {date})_" if cite else
                                            f" _(approved {date})_")
    with open(p, "a", encoding="utf-8") as f:
        f.write(line + "\n")
    return p


def new_proposal(note: dict, call_name: str | None) -> dict:
    """Shape a proposal for the review UI."""
    return {
        "id": next(_ids),
        "text": str(note.get("text", "")).strip(),
        "source": note.get("source", "transcript"),
        "timestamp": str(note.get("timestamp", "")).strip("[] "),
        "quote": str(note.get("quote", "")).strip(),
        "flagged": bool(note.get("conflicts_with_transcript")),
        "reason": str(note.get("conflict_reason", "")).strip(),
        "call": call_name,
        "status": "flagged" if note.get("conflicts_with_transcript") else "proposed",
    }
