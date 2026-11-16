"""What counts as a real turn.

Backchannels ("mhmm", "yeah", "okay", "right?") aren't turns: they don't count as
talk time, don't trigger cards, and don't break up the other speaker's turn.
A prospect turn is "finished" when it's a complete sentence or after ~1.5 s of silence.
"""
from __future__ import annotations

import re

_BACKCHANNEL_WORDS = (
    r"m+[\s-]?h+m+|m+-?m+|uh-?huh|uh-?hum|yeah|yea|yep|yup|yes|yah|okay|ok|k|right|sure|"
    r"got it|gotcha|correct|absolutely|exactly|totally|for sure|i see|oh|ah|wow|cool|nice|"
    r"true|alright|all right|perfect|great|good|definitely|of course|no doubt|fair|fair enough|sounds good"
)
BACKCHANNEL = re.compile(
    rf"^\s*(?:(?:{_BACKCHANNEL_WORDS})[\s,.!?-]*){{1,3}}$", re.I
)
CHECKIN = re.compile(
    r"\b(?:does that make sense|make sense|do you see how|can you see how|what are your thoughts|"
    r"how does that sound|how does that look|does that sound|is that fair|fair enough\?|"
    r"would that help|could that help|do you like (?:that|how)|what do you think|are you with me|"
    r"does that work|is that something|you know what i mean)\b|(?:\b(?:right|correct|yeah|okay|fair)\?\s*$)",
    re.I,
)
_DANGLING = {"and", "but", "so", "because", "or", "um", "uh", "like", "the", "a", "an", "to", "of",
             "with", "if", "that", "which", "is", "was", "for", "my", "our", "your"}


def is_backchannel(text: str) -> bool:
    t = text.strip()
    return bool(t) and len(t.split()) <= 4 and bool(BACKCHANNEL.match(t))


def is_complete(text: str) -> bool:
    """A finished sentence: ends in . ? or !, has a few words, and doesn't trail off."""
    t = text.strip()
    if len(t.split()) < 3 or not t or t[-1] not in ".?!":
        return False
    last = re.sub(r"[^a-z']", "", t.split()[-1].lower())
    return last not in _DANGLING


def is_checkin(text: str) -> bool:
    return bool(CHECKIN.search(text))
