"""Landing the plane: track which outcome the call is heading for and what's missing.

Three ways to end a call well:

  Set the demo   1) date + time, by phone or Google Meet
                 2) decision maker confirmed (sole DM, or who else must join)
                 3) asked to accept the calendar invite, and to give reasonable
                    notice if they need to reschedule
  Go OTF         they have time now and Spencer is sending a Google Meet link
  Off the phone  no time within the next 48 business hours -> set a later date,
                 or they're not interested -> close politely

A background tracker (Claude, structured output) reads the transcript and fills
this in; Spencer can tick or untick any item by hand, and his choice wins.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

PATHS = ("set_demo", "otf", "later", "not_interested")

# Checklist items shown in the panel: key -> (path, label)
ITEMS = {
    "demo_time": ("set_demo", "Date & time confirmed (phone or Google Meet)"),
    "decision_maker": ("set_demo", "Decision maker confirmed"),
    "invite": ("set_demo", "Asked to accept the invite + give notice to reschedule"),
    "otf": ("otf", "Has time now · Google Meet link sent"),
    "followup": ("later", "No time in 48 business hrs · later date set"),
    "not_interested": ("not_interested", "Not interested · closed politely"),
}

TRACKER_SCHEMA = {
    "type": "object",
    "properties": {
        "path": {"type": "string", "enum": ["none", "set_demo", "otf", "later", "not_interested"]},
        "demo_time_confirmed": {"type": "boolean"},
        "demo_when": {"type": "string"},
        "demo_format": {"type": "string", "enum": ["unknown", "phone", "google_meet"]},
        "decision_maker": {"type": "string", "enum": ["unknown", "sole", "others_needed"]},
        "decision_maker_note": {"type": "string"},
        "invite_accept_asked": {"type": "boolean"},
        "reschedule_notice_asked": {"type": "boolean"},
        "otf_link_sent": {"type": "boolean"},
        "followup_set": {"type": "boolean"},
        "followup_when": {"type": "string"},
        "not_interested": {"type": "boolean"},
    },
    "required": ["path", "demo_time_confirmed", "demo_when", "demo_format", "decision_maker",
                 "decision_maker_note", "invite_accept_asked", "reschedule_notice_asked",
                 "otf_link_sent", "followup_set", "followup_when", "not_interested"],
    "additionalProperties": False,
}

TRACKER_PROMPT = (
    "Landing-the-plane tracker. Read the call above and report, as JSON, which outcome the call is heading "
    "for and which steps have actually happened (said out loud and agreed, not just mentioned).\n"
    "- path: set_demo (booking a later demo), otf (presenting right now over a Google Meet link), later "
    "(they have no time within the next 48 business hours, so a later follow-up date), not_interested, or none.\n"
    "- demo_time_confirmed: a specific date and time for the demo was agreed. demo_when: that date/time in "
    "short words (e.g. \"Thu 2pm\"), else \"\". demo_format: phone or google_meet if agreed, else unknown.\n"
    "- decision_maker: sole if the prospect confirmed they are the only/primary decision maker; "
    "others_needed if someone else must be involved (put who in decision_maker_note); else unknown.\n"
    "- invite_accept_asked: Spencer asked them to accept the calendar invite. reschedule_notice_asked: he "
    "asked them to let him know with reasonable notice if they need to reschedule.\n"
    "- otf_link_sent: they agreed to go now and Spencer is sending or has sent a Google Meet link.\n"
    "- followup_set: a later follow-up date/time was agreed (followup_when in short words, else \"\").\n"
    "- not_interested: the prospect clearly said they are not interested.\n"
    "Be strict: only mark something true if it clearly happened."
)

# Spencer starting to wrap up the call.
WRAP_UP = re.compile(
    r"\b(?:talk (?:to you )?soon|have a (?:great|good|nice) (?:one|day|night|weekend|afternoon|evening)|"
    r"thanks (?:so much )?for (?:your|the) time|appreciate (?:your|the) time|i'?ll let you go|"
    r"i'?ll let you get back|(?:take care|bye now|goodbye)|speak (?:to you )?soon|catch you later)\b",
    re.I,
)

# Words that suggest the close is being discussed: worth re-checking the tracker.
CLOSE_HINT = re.compile(
    r"\b(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|tomorrow|next week|this week|"
    r"\d{1,2}(?::\d{2})?\s?(?:am|pm|a\.m\.|p\.m\.)|o'?clock|morning|afternoon|calendar|invite|"
    r"reschedule|google meet|meet link|send (?:you )?(?:a |the )?link|zoom|screen ?share|right now|"
    r"have time|got time|a few minutes|decision|partner|wife|husband|owner|boss|business partner|"
    r"not interested|call (?:me |you )?back|follow up|circle back|next month|busy)\b",
    re.I,
)


@dataclass
class CloseState:
    path: str = "none"
    demo_time: bool = False
    demo_when: str = ""
    demo_format: str = "unknown"
    decision_maker: str = "unknown"          # unknown | sole | others_needed
    decision_maker_note: str = ""
    invite_accept: bool = False
    reschedule_notice: bool = False
    otf: bool = False
    followup: bool = False
    followup_when: str = ""
    not_interested: bool = False
    manual: dict = field(default_factory=dict)   # item key -> True/False set by Spencer

    # ---- item status -------------------------------------------------
    def auto_done(self, key: str) -> bool:
        return {
            "demo_time": self.demo_time,
            "decision_maker": self.decision_maker in ("sole", "others_needed"),
            "invite": self.invite_accept and self.reschedule_notice,
            "otf": self.otf,
            "followup": self.followup,
            "not_interested": self.not_interested,
        }[key]

    def done(self, key: str) -> bool:
        return self.manual[key] if key in self.manual else self.auto_done(key)

    def detail(self, key: str) -> str:
        if key == "demo_time":
            fmt = {"phone": "phone call", "google_meet": "Google Meet"}.get(self.demo_format, "")
            return " · ".join(x for x in (self.demo_when, fmt) if x)
        if key == "decision_maker":
            if self.decision_maker == "sole":
                return "Sole decision maker"
            if self.decision_maker == "others_needed":
                return "Also needs: " + (self.decision_maker_note or "someone else")
            return ""
        if key == "invite":
            if self.invite_accept or self.reschedule_notice:
                return ("invite ✓" if self.invite_accept else "invite ✗") + " · " + \
                       ("reschedule notice ✓" if self.reschedule_notice else "reschedule notice ✗")
            return ""
        if key == "followup":
            return self.followup_when
        return ""

    def active_path(self) -> str:
        """The path the call is on: Spencer's ticks first, then the tracker's view."""
        for key, (path, _) in ITEMS.items():
            if self.manual.get(key):
                return path
        if self.path in PATHS:
            return self.path
        for key, (path, _) in ITEMS.items():
            if self.auto_done(key):
                return path
        return "none"

    def missing(self, path: str | None = None) -> list[str]:
        path = path or self.active_path()
        if path == "set_demo":
            out = []
            if not self.done("demo_time"):
                out.append("lock a specific date and time, by phone or Google Meet")
            if not self.done("decision_maker"):
                out.append("confirm they're the only decision maker, or get the other decision maker on the invite")
            if not self.done("invite"):
                parts = []
                if not (self.manual.get("invite") or self.invite_accept):
                    parts.append("ask them to accept the calendar invite")
                if not (self.manual.get("invite") or self.reschedule_notice):
                    parts.append("ask them to give reasonable notice if they need to reschedule")
                out.append(" and ".join(parts) or "ask them to accept the invite")
            return out
        if path == "otf":
            return [] if self.done("otf") else ["send the Google Meet link and confirm they're joining now"]
        if path == "later":
            return [] if self.done("followup") else ["agree on a specific later date and time to reconnect"]
        if path == "not_interested":
            return []
        return ["pick an outcome: set the demo, go on-the-fly with a Meet link, or set a later date"]

    def complete(self) -> bool:
        path = self.active_path()
        if path == "not_interested":
            return self.done("not_interested")
        return path != "none" and not self.missing(path)

    # ---- updates ---------------------------------------------------------
    def apply_tracker(self, r: dict) -> None:
        """Merge a tracker result. Facts only move forward (a confirmed time stays confirmed)."""
        if r.get("path") in PATHS:
            self.path = r["path"]
        self.demo_time = self.demo_time or bool(r.get("demo_time_confirmed"))
        if r.get("demo_when"):
            self.demo_when = str(r["demo_when"])[:60]
        if r.get("demo_format") in ("phone", "google_meet"):
            self.demo_format = r["demo_format"]
        if r.get("decision_maker") in ("sole", "others_needed"):
            self.decision_maker = r["decision_maker"]
            self.decision_maker_note = str(r.get("decision_maker_note") or "")[:80]
        self.invite_accept = self.invite_accept or bool(r.get("invite_accept_asked"))
        self.reschedule_notice = self.reschedule_notice or bool(r.get("reschedule_notice_asked"))
        self.otf = self.otf or bool(r.get("otf_link_sent"))
        self.followup = self.followup or bool(r.get("followup_set"))
        if r.get("followup_when"):
            self.followup_when = str(r["followup_when"])[:60]
        self.not_interested = self.not_interested or bool(r.get("not_interested"))

    def mark(self, key: str, value: bool | None) -> None:
        """Spencer ticks (True), unticks (False), or hands back to auto (None)."""
        if key not in ITEMS:
            return
        if value is None:
            self.manual.pop(key, None)
        else:
            self.manual[key] = bool(value)

    # ---- outputs ----------------------------------------------------------
    def outcome_label(self) -> str:
        path = self.active_path()
        if path == "set_demo":
            if self.complete():
                return "Demo set" + (f": {self.demo_when}" if self.demo_when else "")
            n = sum(self.done(k) for k in ("demo_time", "decision_maker", "invite"))
            return f"Setting the demo ({n} of 3)"
        if path == "otf":
            return "OTF" if self.done("otf") else "Going OTF"
        if path == "later":
            return ("Follow-up" + (f": {self.followup_when}" if self.followup_when else " set")) \
                if self.done("followup") else "Scheduling later"
        if path == "not_interested":
            return "Not interested"
        return "No outcome yet"

    def score(self) -> int | None:
        """Next-step clarity from the outcome, or None if no outcome is in progress."""
        path = self.active_path()
        if path == "set_demo":
            return 40 + 20 * sum(self.done(k) for k in ("demo_time", "decision_maker", "invite"))
        if path == "otf":
            return 100 if self.done("otf") else 70
        if path == "later":
            return 85 if self.done("followup") else 50
        if path == "not_interested":
            return 70           # a clean, honest exit
        return None

    def status_text(self, minutes: float, land_after: float) -> str:
        """Context for every coach request."""
        path = self.active_path()
        lines = [
            "Landing the plane: Spencer must end the call with one outcome. (1) Set the demo: a specific date "
            "and time by phone or Google Meet; confirm they're the only decision maker or get the other decision "
            "maker on the invite; ask them to accept the calendar invite and to give reasonable notice if they "
            "need to reschedule. (2) Go on-the-fly: if they have time now, send a Google Meet link and present. "
            "(3) If they have no time within the next 48 business hours, set a specific later date; if they're "
            "not interested, close politely.",
            f"Outcome so far: {self.outcome_label()}.",
        ]
        missing = self.missing(path)
        if path != "none" and missing:
            lines.append("Still needed: " + "; ".join(missing) + ".")
        if path == "none" and minutes >= land_after:
            lines.append(f"It's {int(minutes)} minutes in with no outcome yet: start landing the plane now.")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "path": self.active_path(),
            "outcome": self.outcome_label(),
            "complete": self.complete(),
            "items": {k: {"path": p, "label": label, "done": self.done(k), "detail": self.detail(k),
                          "manual": k in self.manual}
                      for k, (p, label) in ITEMS.items()},
            "missing": self.missing() if self.active_path() != "none" else [],
            "demo_when": self.demo_when,
            "demo_format": self.demo_format,
            "decision_maker": self.decision_maker,
            "decision_maker_note": self.decision_maker_note,
            "followup_when": self.followup_when,
        }
