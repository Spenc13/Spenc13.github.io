"""Call metrics computed from the transcript. Nothing here is simulated.

Every score is either a number computed from what was said, or None when there
isn't enough of the call yet to judge (the UI shows "–" and leaves it out of
the overall score).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .transcript import PROSPECT, REP, Utterance

QUESTION_START = re.compile(
    r"^(?:what|how|why|when|where|who|which|do|does|did|is|are|was|were|can|could|would|will|should|have|has|tell me|walk me)\b",
    re.I,
)
OPEN_START = re.compile(r"^(?:what|how|why|tell me|walk me|describe|help me understand)\b", re.I)
NEXT_STEP = re.compile(
    r"\b(?:next step|calendar|calendar invite|book (?:a|the|some)|schedule|set up (?:a|the|some) (?:time|call|meeting)|"
    r"follow[- ]up (?:call|meeting)|kick ?off|onboarding call|get you started|send (?:you )?(?:the )?(?:agreement|contract|invite)|"
    r"sign (?:up|the)|lock (?:it|that) in|reconnect|hop on (?:a|another) call)\b",
    re.I,
)
SPECIFIC_TIME = re.compile(
    r"\b(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|tomorrow|next week|this week|"
    r"\d{1,2}(?::\d{2})?\s?(?:am|pm|a\.m\.|p\.m\.)|\d{1,2} o'?clock|noon|morning|afternoon)\b",
    re.I,
)
LABEL = re.compile(r"\b(?:it|that) (?:sounds|seems|looks|feels) like\b", re.I)
MEETING = re.compile(r"\b(?:call|meeting|demo|zoom|chat|walkthrough|appointment)\b", re.I)
AGREE = re.compile(
    r"\b(?:yes|yeah|yep|sure|sounds good|works|let'?s do it|okay|ok|perfect|deal|i'?m in|book it)\b",
    re.I,
)

TALK_TARGET = (40, 60)        # % of talk time for the rep
WPM_TARGET = (140, 170)
QUESTIONS_PER_5_MIN = 4.0
WORDS_PER_SECOND_EST = 2.7    # used only if STT gave no duration


def count_questions(text: str) -> tuple[int, int]:
    """Return (questions, open_questions) in one rep utterance."""
    sentences = [s.strip() for s in re.split(r"(?<=[.?!])\s+", text) if s.strip()]
    has_punct = any(s[-1] in ".?!" for s in sentences)
    q = o = 0
    for s in sentences:
        is_q = s.endswith("?") if has_punct else bool(QUESTION_START.match(s))
        if is_q:
            q += 1
            if OPEN_START.match(s):
                o += 1
    return q, o


@dataclass
class ObjectionRecord:
    key: str
    label: str
    t: float
    handled: bool | None = None   # None = waiting for Spencer's reply


@dataclass
class Metrics:
    rep_seconds: float = 0.0
    prospect_seconds: float = 0.0
    rep_words: int = 0
    prospect_words: int = 0
    questions: int = 0
    open_questions: int = 0
    objections: list[ObjectionRecord] = field(default_factory=list)
    next_step_asked: bool = False
    next_step_specific: bool = False
    next_step_agreed: bool = False
    _next_step_t: float | None = None
    elapsed: float = 0.0
    partial_after: float = 0.0     # >0: coaching joined this many seconds into the call

    # ---- updates -------------------------------------------------------
    def add_utterance(self, u: Utterance) -> None:
        dur = u.duration if u.duration > 0 else u.words / WORDS_PER_SECOND_EST
        if u.speaker == REP:
            self.rep_seconds += dur
            self.rep_words += u.words
            q, o = count_questions(u.text)
            self.questions += q
            self.open_questions += o
            # An objection is "handled" if, within 30 seconds, Spencer asks a question
            # (ask before you tell) or labels it (Voss). Otherwise tick() marks it missed.
            engaged = q > 0 or bool(LABEL.search(u.text))
            for ob in self.objections:
                if ob.handled is None and -1 <= u.t - ob.t <= 30 and engaged:
                    ob.handled = True
            if NEXT_STEP.search(u.text) or (SPECIFIC_TIME.search(u.text) and MEETING.search(u.text)):
                self.next_step_asked = True
                self._next_step_t = u.end
                if SPECIFIC_TIME.search(u.text):
                    self.next_step_specific = True
        else:
            self.prospect_seconds += dur
            self.prospect_words += u.words
            if self._next_step_t is not None and u.t - self._next_step_t <= 30:
                if AGREE.search(u.text):
                    self.next_step_agreed = True
                if SPECIFIC_TIME.search(u.text):
                    self.next_step_specific = True
        self.elapsed = max(self.elapsed, u.end)

    def add_objection(self, key: str, label: str, t: float) -> None:
        self.objections.append(ObjectionRecord(key, label, t))

    def tick(self, elapsed: float) -> None:
        self.elapsed = max(self.elapsed, elapsed)
        for ob in self.objections:
            if ob.handled is None and elapsed - ob.t > 30:
                ob.handled = False

    def finalize(self) -> None:
        """Call over: an objection still waiting for a reply was never answered."""
        for ob in self.objections:
            if ob.handled is None:
                ob.handled = False

    # ---- derived numbers ----------------------------------------------
    @property
    def rep_share(self) -> int | None:
        total = self.rep_seconds + self.prospect_seconds
        return round(100 * self.rep_seconds / total) if total > 0 else None

    @property
    def wpm(self) -> int | None:
        return round(self.rep_words / (self.rep_seconds / 60)) if self.rep_seconds >= 20 else None

    def scores(self) -> dict[str, int | None]:
        s: dict[str, int | None] = {}

        # Discovery: question rate vs. target, plus a bonus for open questions.
        minutes = self.elapsed / 60
        if minutes < 1 and self.questions == 0:
            s["Discovery"] = None
        else:
            target = QUESTIONS_PER_5_MIN * max(minutes, 1) / 5
            rate = min(1.0, self.questions / target) if target else 1.0
            open_ratio = self.open_questions / self.questions if self.questions else 0
            s["Discovery"] = round(80 * rate + 20 * open_ratio)

        # Listening: talk-to-listen ratio vs. the 40-60% band.
        share = self.rep_share
        if share is None or self.rep_seconds + self.prospect_seconds < 30:
            s["Listening"] = None
        else:
            lo, hi = TALK_TARGET
            off = 0 if lo <= share <= hi else (lo - share if share < lo else share - hi)
            s["Listening"] = max(0, 100 - 3 * off)

        # Objection handling: share of objections answered with a question.
        judged = [o for o in self.objections if o.handled is not None]
        s["Objection handling"] = round(100 * sum(o.handled for o in judged) / len(judged)) if judged else None

        # Pacing: rep words per minute vs. 140-170.
        w = self.wpm
        if w is None:
            s["Pacing"] = None
        else:
            lo, hi = WPM_TARGET
            off = 0 if lo <= w <= hi else (lo - w if w < lo else w - hi)
            s["Pacing"] = max(0, 100 - 2 * off)

        # Next-step clarity.
        if self.next_step_asked:
            s["Next-step clarity"] = 55 + (20 if self.next_step_specific else 0) + (25 if self.next_step_agreed else 0)
        elif self.elapsed >= 300:
            s["Next-step clarity"] = 25
        else:
            s["Next-step clarity"] = None
        return s

    def overall(self) -> int | None:
        vals = [v for v in self.scores().values() if v is not None]
        return round(sum(vals) / len(vals)) if vals else None

    def details(self) -> dict[str, str]:
        """Short raw values shown next to each bar."""
        judged = [o for o in self.objections if o.handled is not None]
        return {
            "Discovery": f"{self.questions} Qs ({self.open_questions} open)",
            "Listening": f"{self.rep_share}% you" if self.rep_share is not None else "",
            "Objection handling": f"{sum(o.handled for o in judged)}/{len(self.objections)} met with a question or label" if self.objections else "0 objections",
            "Pacing": f"{self.wpm} wpm" if self.wpm else "",
            "Next-step clarity": (
                "agreed" if self.next_step_agreed else "specific time" if self.next_step_specific
                else "asked" if self.next_step_asked else "not asked yet"
            ),
        }

    def recommendations(self) -> list[str]:
        recs: list[str] = []
        share = self.rep_share
        minutes = self.elapsed / 60
        if share is not None and share > TALK_TARGET[1] and self.rep_seconds + self.prospect_seconds >= 30:
            recs.append(f"You're at {share}% talk time. Ask one question and let them finish.")
        if share is not None and share < TALK_TARGET[0] and minutes >= 5:
            recs.append(f"You're at {share}% talk time. Summarize their problem and move toward a next step.")
        expected = QUESTIONS_PER_5_MIN * max(minutes, 1) / 5
        if minutes >= 2 and self.questions < expected:
            recs.append(f"{self.questions} questions in {minutes:.0f} min. Ask a situation or problem question.")
        if self.questions >= 3 and self.open_questions / self.questions < 0.5:
            recs.append("Most questions are yes/no. Start with what, how, or why.")
        missed = [o for o in self.objections if o.handled is False]
        if missed:
            recs.append(f"“{missed[-1].label}” got a statement, not a question. Ask before you tell.")
        w = self.wpm
        if w is not None and w > WPM_TARGET[1]:
            recs.append(f"Pace is {w} wpm. Slow down and pause after key points.")
        elif w is not None and w < WPM_TARGET[0] - 20:
            recs.append(f"Pace is {w} wpm. Tighten it up a bit.")
        if not self.next_step_asked and minutes >= 10:
            recs.append("No next step yet. Propose a specific day and time.")
        elif self.next_step_asked and not self.next_step_specific:
            recs.append("Next step is vague. Put a day and time on it.")
        if not recs and self.elapsed > 0:
            recs.append("On track. Keep asking before you tell.")
        return recs[:5]

    def snapshot(self) -> dict:
        return {
            "elapsed_seconds": round(self.elapsed, 1),
            "partial_call": self.partial_after > 0,
            "joined_after_seconds": round(self.partial_after) if self.partial_after else None,
            "rep_talk_seconds": round(self.rep_seconds, 1),
            "prospect_talk_seconds": round(self.prospect_seconds, 1),
            "rep_share_pct": self.rep_share,
            "prospect_share_pct": None if self.rep_share is None else 100 - self.rep_share,
            "rep_words": self.rep_words,
            "prospect_words": self.prospect_words,
            "rep_wpm": self.wpm,
            "questions": self.questions,
            "open_questions": self.open_questions,
            "objection_count": len(self.objections),
            "objections": [o.__dict__ for o in self.objections],
            "next_step": {
                "asked": self.next_step_asked,
                "specific": self.next_step_specific,
                "agreed": self.next_step_agreed,
            },
            "scores": self.scores(),
            "score_details": self.details(),
            "overall": self.overall(),
            "recommendations": self.recommendations(),
        }
