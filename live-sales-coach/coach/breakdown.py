"""Call Breakdown: review uploaded calls, let the rep explain, leave with action steps.

Flow
  1. Add calls: audio (transcribed by Deepgram, speakers diarized), transcripts
     (.txt), or saved calls from calls/. The rep's speaker is guessed and can be swapped.
  2. Analyze: strengths and improvements per call (timestamp + quote), patterns
     across calls, and progress on the rep's previous action steps.
  3. Open forum: the rep writes why they said what they said, per improvement and overall.
  4. Finalize: the coach reads the reflections and returns 3 to 5 action steps,
     which are saved to the rep's plan and checked at the next breakdown.

Everything is stored locally under breakdowns/<rep>/ (gitignored).
"""
from __future__ import annotations

import asyncio
import itertools
import json
import os
import re
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime
from pathlib import Path

from .config import APP_DIR, get

AUDIO_EXT = {".wav", ".mp3", ".m4a", ".aac", ".ogg", ".oga", ".webm", ".flac", ".mp4", ".mov", ".wma"}
TEXT_EXT = {".txt", ".md"}
_ids = itertools.count(1)

CATEGORIES = ["intro", "rapport", "discovery_question", "pain", "revenue_gap", "value", "objection",
              "presentation", "decision_maker", "time_set", "confirmation", "pain_recap", "closing",
              "pacing", "talk_ratio", "other"]


def slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (name or "rep").lower()).strip("-")
    return s or "rep"


def root(cfg: dict) -> Path:
    p = Path(get(cfg, "breakdown.dir", "breakdowns"))
    return p if p.is_absolute() else APP_DIR / p


def _clock(sec: float) -> str:
    sec = max(0, int(sec))
    return f"{sec // 60:02d}:{sec % 60:02d}"


# ---------------------------------------------------------------- reading calls
_OURS = re.compile(r"^\[(\d{1,3}):(\d{2})\]\s+([^:]{1,40}):\s?(.*)$")
_LABELED = re.compile(r"^(?:\[?(\d{1,3}):(\d{2})(?::\d{2})?\]?\s*[-–]?\s*)?([A-Z][\w .'-]{0,30}):\s+(.+)$")
REP_CUES = re.compile(r"\b(?:olly olly|this is \w+ (?:with|from)|calling (?:from|with)|my name is|"
                      r"thanks for (?:taking|making|picking)|reason (?:for|i'?m) (?:my )?call)", re.I)


def parse_text(text: str) -> list[dict]:
    """Lines -> [{t, speaker, text}] for our format or generic "Name: text" transcripts."""
    rows: list[dict] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = _OURS.match(line) or _LABELED.match(line)
        if m:
            mm, ss, who, body = m.groups()
            t = int(mm) * 60 + int(ss) if mm is not None else (rows[-1]["t"] if rows else 0)
            who = who.strip()
            if who.lower().startswith("spencer (typed)"):
                continue
            rows.append({"t": t, "speaker": who, "text": body.strip()})
        elif rows:
            rows[-1]["text"] += " " + line
    return rows


def guess_rep(rows: list[dict], rep_name: str = "") -> str | None:
    """Which speaker label is the rep: 'Rep' if present, the rep's name, intro cues, or most questions."""
    labels = [r["speaker"] for r in rows]
    if not labels:
        return None
    uniq = list(dict.fromkeys(labels))
    for want in ("Rep", "Spencer", rep_name.split(" ")[0] if rep_name else ""):
        for u in uniq:
            if want and u.lower() == want.lower():
                return u
    score: Counter = Counter()
    for r in rows[:40]:
        if REP_CUES.search(r["text"]):
            score[r["speaker"]] += 3
        score[r["speaker"]] += r["text"].count("?") * 0.5
    return score.most_common(1)[0][0] if score else uniq[0]


def normalize(rows: list[dict], rep_label: str | None) -> str:
    """Our standard transcript: [mm:ss] Rep/Prospect: text (anyone not the rep is the prospect side)."""
    out = []
    for r in rows:
        who = "Rep" if r["speaker"] == rep_label else ("Prospect" if r["speaker"] != "Prospect" else "Prospect")
        out.append(f"[{_clock(r['t'])}] {who}: {r['text']}")
    return "\n".join(out)


def deepgram_transcribe(path: Path, model: str = "nova-3", timeout: float = 600) -> list[dict]:
    """Prerecorded transcription with diarization (blocking; run in a thread)."""
    key = os.environ.get("DEEPGRAM_API_KEY")
    if not key:
        raise RuntimeError("DEEPGRAM_API_KEY not set: audio can't be transcribed (transcripts still work)")
    q = urllib.parse.urlencode({"model": model, "smart_format": "true", "punctuate": "true",
                                "diarize": "true", "utterances": "true"})
    data = path.read_bytes()
    ctype = {".mp3": "audio/mpeg", ".m4a": "audio/mp4", ".mp4": "audio/mp4", ".wav": "audio/wav",
             ".ogg": "audio/ogg", ".webm": "audio/webm", ".flac": "audio/flac"}.get(path.suffix.lower(), "audio/*")
    req = urllib.request.Request(f"https://api.deepgram.com/v1/listen?{q}", data=data, method="POST",
                                 headers={"Authorization": f"Token {key}", "Content-Type": ctype})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    utts = (body.get("results") or {}).get("utterances") or []
    return [{"t": float(u.get("start", 0)), "speaker": f"Speaker {int(u.get('speaker', 0)) + 1}",
             "text": (u.get("transcript") or "").strip()} for u in utts if (u.get("transcript") or "").strip()]


def load_call_folder(folder: Path) -> tuple[list[dict], str]:
    text = (folder / "transcript.txt").read_text(encoding="utf-8")
    title = folder.name
    try:
        meta = json.loads((folder / "metrics.json").read_text(encoding="utf-8")).get("meta", {})
        title = f"{meta.get('title') or 'Call'} ({folder.name})"
    except (OSError, json.JSONDecodeError):
        pass
    return parse_text(text), title


async def load_upload(path: Path, rep_name: str, cfg: dict) -> dict:
    """One call ready for analysis: rows, rep label guess, speakers with sample lines."""
    path = Path(path)
    if path.is_dir():
        rows, title = load_call_folder(path)
        source = "past call"
    elif path.suffix.lower() in AUDIO_EXT:
        rows = await asyncio.to_thread(deepgram_transcribe, path, get(cfg, "stt.model", "nova-3"))
        title, source = path.stem, "recording"
    else:
        rows = parse_text(path.read_text(encoding="utf-8", errors="replace"))
        title, source = path.stem, "transcript"
    if not rows:
        raise RuntimeError(f"No conversation found in {path.name}")
    rep = guess_rep(rows, rep_name)
    speakers = []
    for s in dict.fromkeys(r["speaker"] for r in rows):
        lines = [r["text"] for r in rows if r["speaker"] == s and len(r["text"].split()) >= 4][:2]
        speakers.append({"label": s, "sample": " / ".join(lines)[:220]})
    return {"id": next(_ids), "title": title, "source": source, "path": str(path), "rows": rows,
            "rep": rep, "speakers": speakers, "minutes": round((rows[-1]["t"] if rows else 0) / 60, 1)}


# ---------------------------------------------------------------- the rep's plan
def plan_path(cfg: dict, rep: str) -> Path:
    return root(cfg) / slug(rep) / "plan.json"


def load_plan(cfg: dict, rep: str) -> dict:
    try:
        return json.loads(plan_path(cfg, rep).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"rep": rep, "steps": []}


def save_plan(cfg: dict, plan: dict) -> None:
    p = plan_path(cfg, plan.get("rep", "rep"))
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(plan, indent=2), encoding="utf-8")


def active_steps(plan: dict) -> list[dict]:
    return [s for s in plan.get("steps", []) if s.get("status") in ("active", "needs_training")]


def apply_progress(plan: dict, progress: list[dict], breakdown_id: str) -> list[dict]:
    """Record how each earlier step went. Two 'improved' in a row = mastered;
    two 'not_yet' in a row (with a chance to show it) = needs training."""
    by_id = {s["id"]: s for s in plan.get("steps", [])}
    changes = []
    for p in progress:
        s = by_id.get(p.get("step_id"))
        if not s or s.get("status") not in ("active", "needs_training"):
            continue
        s.setdefault("history", []).append({"breakdown": breakdown_id, "status": p.get("status"),
                                            "evidence": p.get("evidence", ""), "time": p.get("time", "")})
        recent = [h["status"] for h in s["history"] if h["status"] != "no_opportunity"][-2:]
        before = s["status"]
        if recent == ["improved", "improved"]:
            s["status"] = "mastered"
        elif recent == ["not_yet", "not_yet"]:
            s["status"] = "needs_training"
        elif recent and recent[-1] in ("improved", "partial") and s["status"] == "needs_training":
            s["status"] = "active"
        if s["status"] != before:
            changes.append({"id": s["id"], "text": s["text"], "from": before, "to": s["status"]})
    return changes


def apply_final_steps(plan: dict, final: list[dict], carry_over: list[str], breakdown_id: str) -> None:
    """New action steps join the plan; earlier active steps not carried over are retired."""
    keep = set(carry_over or [])
    for s in plan.get("steps", []):
        if s.get("status") in ("active", "needs_training") and s["id"] not in keep:
            s["status"] = "retired"
    n = len(plan.get("steps", []))
    for i, f in enumerate(final):
        if f.get("carry_over_id") and any(s["id"] == f["carry_over_id"] for s in plan["steps"]):
            continue
        plan.setdefault("steps", []).append({
            "id": f"s{n + i + 1}", "text": f.get("step", ""), "why": f.get("why", ""),
            "how": f.get("how_to_practice", ""), "success": f.get("success_looks_like", ""),
            "created": datetime.now().strftime("%Y-%m-%d"), "from_breakdown": breakdown_id,
            "status": "active", "history": [],
        })


# ---------------------------------------------------------------- saving breakdowns
def save_breakdown(cfg: dict, rep: str, record: dict) -> Path:
    d = root(cfg) / slug(rep) / record["id"]
    d.mkdir(parents=True, exist_ok=True)
    (d / "breakdown.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    (d / "breakdown.md").write_text(to_markdown(record), encoding="utf-8")
    return d


def list_breakdowns(cfg: dict, rep: str) -> list[dict]:
    base = root(cfg) / slug(rep)
    out = []
    if base.exists():
        for d in sorted((p for p in base.iterdir() if p.is_dir()), reverse=True):
            try:
                r = json.loads((d / "breakdown.json").read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            out.append({"id": r.get("id"), "date": r.get("date"), "calls": len(r.get("calls", [])),
                        "finished": bool(r.get("final")), "overview": (r.get("analysis") or {}).get("overview", "")})
    return out


def to_markdown(r: dict) -> str:
    a = r.get("analysis") or {}
    lines = [f"# Call breakdown: {r.get('rep')} ({r.get('date')})", ""]
    if a.get("overview"):
        lines += [a["overview"], ""]
    for c in a.get("calls", []):
        lines.append(f"## {c.get('title', 'Call')}")
        for s in c.get("strengths", []):
            lines.append(f"- ✅ [{s.get('time')}] {s.get('category')}: “{s.get('quote')}”. {s.get('why')}")
        for imp in c.get("improvements", []):
            lines.append(f"- ⚠️ [{imp.get('time')}] {imp.get('category')}: “{imp.get('quote')}”. "
                         f"{imp.get('issue')} Try: “{imp.get('try_instead')}”")
            take = (r.get("reflections") or {}).get(str(imp.get("id")))
            if take:
                lines.append(f"  - Rep's take: {take}")
        lines.append("")
    if a.get("patterns"):
        lines += ["## Patterns"] + [f"- {p}" for p in a["patterns"]] + [""]
    if a.get("step_progress"):
        lines.append("## Progress on earlier steps")
        for p in a["step_progress"]:
            lines.append(f"- {p.get('step')}: **{p.get('status')}** {p.get('evidence', '')}")
        lines.append("")
    if (r.get("reflections") or {}).get("general"):
        lines += ["## Rep's reflection", r["reflections"]["general"], ""]
    f = r.get("final") or {}
    if f:
        if f.get("response_to_rep"):
            lines += ["## Coach's response", f["response_to_rep"], ""]
        lines.append("## Action steps for the next calls")
        for i, s in enumerate(f.get("action_steps", []), 1):
            lines.append(f"{i}. **{s.get('step')}**: {s.get('why')} Practice: {s.get('how_to_practice')} "
                         f"Success looks like: {s.get('success_looks_like')}")
        for t in f.get("training_flags", []):
            lines.append(f"- \U0001f6a9 Needs more coaching: {t.get('area')}. {t.get('reason')}")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- prompts
_moment = lambda extra: {  # noqa: E731
    "type": "object", "additionalProperties": False,
    "properties": {"time": {"type": "string"}, "category": {"type": "string", "enum": CATEGORIES},
                   "quote": {"type": "string"}, **extra},
    "required": ["time", "category", "quote", *extra.keys()],
}
ANALYSIS_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "overview": {"type": "string"},
        "calls": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "properties": {
                "call_id": {"type": "integer"}, "title": {"type": "string"},
                "strengths": {"type": "array", "items": _moment({"why": {"type": "string"}})},
                "improvements": {"type": "array", "items": _moment(
                    {"issue": {"type": "string"}, "try_instead": {"type": "string"}})},
            },
            "required": ["call_id", "title", "strengths", "improvements"]}},
        "patterns": {"type": "array", "items": {"type": "string"}},
        "step_progress": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "properties": {"step_id": {"type": "string"}, "step": {"type": "string"},
                           "status": {"type": "string", "enum": ["improved", "partial", "not_yet", "no_opportunity"]},
                           "evidence": {"type": "string"}, "time": {"type": "string"}},
            "required": ["step_id", "step", "status", "evidence", "time"]}},
    },
    "required": ["overview", "calls", "patterns", "step_progress"],
}
FINAL_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "response_to_rep": {"type": "string"},
        "action_steps": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "properties": {"step": {"type": "string"}, "why": {"type": "string"},
                           "how_to_practice": {"type": "string"}, "success_looks_like": {"type": "string"},
                           "carry_over_id": {"type": "string"}},
            "required": ["step", "why", "how_to_practice", "success_looks_like", "carry_over_id"]}},
        "training_flags": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "properties": {"area": {"type": "string"}, "reason": {"type": "string"}},
            "required": ["area", "reason"]}},
        "carry_over": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["response_to_rep", "action_steps", "training_flags", "carry_over"],
}


def _shared_rules() -> str:
    from .engine import SHARED_RULES
    return SHARED_RULES


def analysis_prompt(rep: str, calls: list[dict], steps: list[dict]) -> str:
    plan = "\n".join(f"- {s['id']}: {s['text']} (status: {s['status']})" for s in steps) or "(none yet: first breakdown)"
    body = []
    for c in calls:
        body.append(f"=== Call {c['id']}: {c['title']} ===\n{normalize(c['rows'], c['rep'])}")
    return (
        f"Break down these sales calls for {rep}, a rep at Olly Olly, as his coach. Use the playbook, offer "
        "reference, and his discovery questions as the standard.\n"
        "For each call: 2 to 5 strengths (things to keep doing: a solid intro, great discovery questions, the "
        "revenue gap, a pain recap before asking for the time, setting a specific time, confirming the decision "
        "maker and responsible parties, handling an objection well) and 2 to 5 improvements, each with the "
        "[mm:ss] time, the exact quote, the issue, and a better line to try (one question, in plain spoken words). "
        "Then patterns across the calls (only if there's more than one, or a clear habit).\n"
        "Then step_progress: for EACH of his earlier action steps below, judge from these calls whether he "
        "improved, partly improved, hasn't yet, or had no opportunity to show it, with evidence and a timestamp. "
        "Return an empty list if there are no earlier steps.\n"
        "Be specific and fair; never invent quotes.\n"
        + _shared_rules() + "\nJudge by these rules: never call something an issue that they call for.\n\n"
        f"His earlier action steps:\n{plan}\n\n" + "\n\n".join(body)
    )


def final_prompt(rep: str, analysis: dict, reflections: dict, steps: list[dict]) -> str:
    takes = []
    for c in analysis.get("calls", []):
        for imp in c.get("improvements", []):
            t = (reflections or {}).get(str(imp.get("id")))
            if t:
                takes.append(f"- On [{imp.get('time')}] “{imp.get('quote')}” ({imp.get('issue')}): {t}")
    general = (reflections or {}).get("general", "")
    plan = "\n".join(f"- {s['id']}: {s['text']} (status: {s['status']}, history: "
                     f"{', '.join(h['status'] for h in s.get('history', [])) or 'none'})" for s in steps) or "(none)"
    return (
        f"You broke down {rep}'s calls (analysis below). He has now explained his thinking. Respond to him "
        "briefly and directly: acknowledge where his reasoning holds up, and where it doesn't, say why (the "
        "transcript wins on facts). Then give 3 to 5 ACTION STEPS for his next calls: specific, practicable, each "
        "with why, how to practice it, and what success looks like on the next calls. If an earlier step should "
        "continue, carry it over (put its id in carry_over_id and in carry_over; otherwise carry_over_id is \"\").\n"
        "training_flags: areas where he's shown no improvement across repeated breakdowns (an earlier step at "
        "needs_training, or not_yet again), so a manager should coach him further. Empty if none.\n\n"
        f"Earlier action steps:\n{plan}\n\n"
        f"His explanations:\n{chr(10).join(takes) or '(none)'}\n\nGeneral reflection:\n{general or '(none)'}\n\n"
        f"Analysis:\n{json.dumps(analysis, indent=1)}"
    )


def number_improvements(analysis: dict) -> None:
    """Give every improvement a stable id so the rep can respond to it."""
    n = 0
    for c in analysis.get("calls", []):
        for imp in c.get("improvements", []):
            n += 1
            imp["id"] = n


def new_breakdown_id() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
