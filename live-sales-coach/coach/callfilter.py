"""Decide whether a finished call is worth saving and grading.

No answer, a quick hang-up, or a voicemail greeting isn't a sales conversation,
so it isn't saved and doesn't cost a summary request. Spencer can still keep one
with "Save anyway".
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
    voicemail: bool


def judge(transcript: Transcript, seconds: float, cfg: dict | None = None, is_set: bool = False) -> Verdict:
    """Keep a call only if an appointment was set, or the conversation ran long enough
    (10 minutes by default). Everything else is discarded unless Spencer clicks Save anyway."""
    cfg = cfg or {}
    min_minutes = float(cfg.get("min_minutes", 10))
    keep_if_set = bool(cfg.get("keep_if_set", True))

    prospect = [u for u in transcript.finals if u.speaker == PROSPECT]
    words = sum(u.words for u in prospect)
    early = " ".join(u.text for u in prospect if u.t <= 45)
    voicemail = bool(VOICEMAIL.search(early))

    if not transcript.finals:
        return Verdict(False, "nothing was said", words, seconds, voicemail)
    if keep_if_set and is_set:
        return Verdict(True, "", words, seconds, voicemail)
    if seconds >= min_minutes * 60:
        return Verdict(True, "", words, seconds, voicemail)
    mins = f"{min_minutes:g} minute{'s' if min_minutes != 1 else ''}"
    why = f"it was under {mins} and no appointment was set"
    if voicemail:
        why += " (it reached voicemail)"
    return Verdict(False, why, words, seconds, voicemail)
