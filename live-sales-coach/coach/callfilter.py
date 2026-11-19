"""Decide whether a finished call is worth saving and grading.

No answer, a quick hang-up, or a voicemail greeting isn't a sales conversation,
so it isn't saved and doesn't cost a summary request. Under 2 minutes: not saved.
2 to 3 minutes: Spencer is asked whether to save it. 3 minutes or more (or an
appointment set): saved automatically. "Save anyway" can still keep any call.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .transcript import PROSPECT, Transcript

VOICEMAIL = re.compile(
    r"\b(?:leave (?:a|your|me a) (?:brief |short )?message|voice ?mail|after the (?:tone|beep)|at the (?:tone|beep)|"
    r"(?:is|are) (?:not|un)available|not available to take|can'?t (?:come to|get to) the phone|mailbox|"
    r"record your message|the (?:person|party|number) you (?:are|have) (?:calling|called|dialed)|"
    r"has not been set up|please hang up|press (?:pound|one|1) (?:for|to))",
    re.I,
)


@dataclass
class Verdict:
    keep: bool
    reason: str               # plain words for the UI
    prospect_words: int
    seconds: float
    voicemail: bool = False
    ask: bool = False         # borderline length: ask Spencer whether to save


def judge(transcript: Transcript, seconds: float, cfg: dict | None = None, is_set: bool = False) -> Verdict:
    """Save a call if an appointment was set or it ran auto_save_minutes (3) or longer.
    Between min_minutes (2) and auto_save_minutes: ask Spencer. Shorter: discard."""
    cfg = cfg or {}
    min_minutes = float(cfg.get("min_minutes", 2))
    auto_minutes = max(min_minutes, float(cfg.get("auto_save_minutes", 3)))
    keep_if_set = bool(cfg.get("keep_if_set", True))

    prospect = [u for u in transcript.finals if u.speaker == PROSPECT]
    words = sum(u.words for u in prospect)
    early = " ".join(u.text for u in prospect if u.t <= 45)
    voicemail = bool(VOICEMAIL.search(early))

    if not transcript.finals:
        return Verdict(False, "nothing was said", words, seconds, voicemail)
    if keep_if_set and is_set:
        return Verdict(True, "", words, seconds, voicemail)
    if seconds >= auto_minutes * 60:
        return Verdict(True, "", words, seconds, voicemail)
    if seconds >= min_minutes * 60 and not voicemail:
        return Verdict(False, f"it ran {fmt_minutes(seconds)} with no appointment set", words, seconds,
                       voicemail, ask=True)
    mins = f"{min_minutes:g} minute{'s' if min_minutes != 1 else ''}"
    why = f"it was under {mins} and no appointment was set"
    if voicemail:
        why += " (it reached voicemail)"
    return Verdict(False, why, words, seconds, voicemail)


def fmt_minutes(seconds: float) -> str:
    m, sec = divmod(int(round(seconds)), 60)
    return f"{m}:{sec:02d}"
