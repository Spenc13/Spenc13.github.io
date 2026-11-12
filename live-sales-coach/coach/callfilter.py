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


def judge(transcript: Transcript, seconds: float, cfg: dict | None = None) -> Verdict:
    cfg = cfg or {}
    min_seconds = float(cfg.get("min_seconds", 45))
    min_words = int(cfg.get("min_prospect_words", 25))
    check_vm = bool(cfg.get("discard_voicemail", True))

    prospect = [u for u in transcript.finals if u.speaker == PROSPECT]
    words = sum(u.words for u in prospect)
    early = " ".join(u.text for u in prospect if u.t <= 45)
    voicemail = check_vm and bool(VOICEMAIL.search(early))

    if not transcript.finals:
        return Verdict(False, "nothing was said", words, seconds, voicemail)
    if voicemail and words < 80:
        return Verdict(False, "it reached voicemail", words, seconds, voicemail)
    if words < min_words:
        return Verdict(False, f"the prospect only said {words} word{'s' if words != 1 else ''}", words, seconds, voicemail)
    if seconds < min_seconds:
        return Verdict(False, f"it lasted only {int(seconds)} seconds", words, seconds, voicemail)
    return Verdict(True, "", words, seconds, voicemail)
