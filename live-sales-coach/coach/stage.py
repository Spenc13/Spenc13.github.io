"""Call stage: Cold / Discovery, Presenting, Confirming an appointment, Side conversation.

Detected from the conversation (by the background call-state check) and pinnable
from the header with one click. The stage decides what the coach focuses on:

  discovery   NEPQ questions; no pitching, no scheduling
  presenting  checking-for-agreement questions, problem recap in their words, transitions
  confirming  calendar invite, decision-maker and approval steps, reschedule notice
  side        off-topic (someone else in the room, a personal errand): coaching paused

Rapport (small talk that builds the relationship) is business-adjacent, not a side
conversation, and never a reason to suggest closing.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

STAGES = ("discovery", "presenting", "confirming", "side")
LABELS = {"discovery": "Cold / Discovery", "presenting": "Presenting", "confirming": "Confirming appointment",
          "side": "Side conversation"}

# Words that suggest the stage may have changed: re-check soon.
STAGE_HINT = re.compile(
    r"\b(?:share (?:my|the) screen|sharing my screen|can you see my screen|let me (?:show|pull up|walk you through)|"
    r"pull(?:ing)? up|on (?:my|the) screen|presentation|demo|slide|package|pricing page|proposal|"
    r"calendar|invite|book(?:ed)?|scheduled?|appointment|confirm(?:ed)?|"
    r"hold on|one sec(?:ond)?|be right back|hang on|excuse me|sorry about that)\b",
    re.I,
)

GUIDANCE = {
    "discovery": (
        "Call stage: Cold call / Discovery. Ask NEPQ discovery questions (situation, problem, consequence, "
        "qualifying, budget). No pain recaps here: acknowledge briefly and ask the next question. Don't pitch features yet. Don't give scheduling advice unless the prospect raises it. "
        "These are blue-collar home-service owners: favor plain, money-and-jobs questions like these (pick the one "
        "that fits the moment and isn't already answered; adapt the wording):\n{questions}"
    ),
    "presenting": (
        "Call stage: Presenting. Spencer is presenting or demoing. Focus only on: checking-for-agreement "
        "questions (aim for about {target} per presentation; {done} so far), tying features back to the prospect's problems in "
        "their own words, and smooth transitions. Do NOT suggest discovery questions or scheduling."
    ),
    "confirming": (
        "Call stage: Confirming an appointment. When first asking for the time (if no recap was given yet), recap their pain in their own "
        "words (one sentence, from what they said on this call), then ask for the time, so the reason to show up "
        "sticks. Focus only on locking the appointment: the calendar invite "
        "(ask them to accept it), the decision maker and any approval steps (for example a franchisor or partner "
        "that must sign off), and asking for reasonable notice if they need to reschedule, then a warm wrap. "
        "Do NOT suggest pitch content or discovery."
    ),
    "side": "Call stage: Side conversation. Don't coach.",
}
# Default blue-collar discovery questions (override with coach.discovery_questions in config.yaml).
DISCOVERY_QUESTIONS = [
    "How much does one job profit you, after materials and labor?",
    "What types of jobs are you looking for more of right now?",
    "How much are you investing in marketing right now?",
    "Where is that marketing money going today?",
    "Where do most of your jobs come from right now?",
    "How many jobs a month do you need to keep your crews busy?",
    "What does a slow month cost you?",
    "Who answers the phone when you're out on a job?",
    "What's your busy season, and what happens to calls in the slow season?",
    "How far out are you willing to drive for the right job?",
]

SCRIPT_GUIDANCE = (
    "Call stage: Cold call / Discovery. Spencer's own discovery questions are in your context: a bank to draw "
    "from, not a script, so there's no required order. Pick whichever question fits this moment best and "
    "hasn't been answered yet (check the transcript and \"Already covered\"), and use his wording. No pain recaps in discovery: acknowledge briefly and ask. Fill the "
    "[brackets] with what the prospect actually said (their service, job counts, job value, competitor names). "
    "When you know the extra jobs they want and what a job is worth, the revenue-gap question is a strong one "
    "(extra jobs x job value = money left on the table per week or month). Where a line lists several questions, "
    "use just one. His questions mark the decision-maker check as critical, so make sure it gets asked at some "
    "point before the presentation. Don't pitch features yet."
)

KEEP_GOING = (
    "Momentum: the conversation is going well (the prospect is engaged and it's moving forward). Don't "
    "redirect Spencer or change his approach, so he keeps his train of thought. Start \"Say this next\" with brief "
    "encouragement (\"You're doing great.\" or \"Great conversation.\") and then ONE point to mention next, tied to "
    "something the prospect just said (\"Mention the review tool, since he said customers check reviews.\")."
)
STALLED = ("Momentum: the conversation is stalling (circling, short answers, or an objection left hanging). Help "
           "Spencer move it forward with one clear question.")

RAPPORT = ("The conversation is rapport / small talk right now. Match it briefly and naturally; "
           "never push the sale or suggest closing during rapport.")


@dataclass
class StageState:
    auto: str = "discovery"
    pinned: str | None = None
    mode: str = "business"            # business | rapport | side
    meeting_agreed: bool = False
    momentum: str = "neutral"         # productive | neutral | stalled
    side_since: float | None = None   # call seconds when the current off-sale stretch began
    _quick_side_until: float = -1.0   # live coach flagged a side conversation (until the next check)

    def effective(self) -> str:
        return self.pinned or self.auto

    def is_side(self, now: float) -> bool:
        if self.pinned:
            return self.pinned == "side"
        return self.auto == "side" or self.mode == "side" or now < self._quick_side_until

    def pin(self, stage: str | None) -> None:
        self.pinned = stage if stage in STAGES else None

    def quick_side(self, now: float, hold: float = 25.0) -> None:
        """The live coach saw a side conversation: pause until the next stage check says otherwise."""
        self._quick_side_until = now + hold
        if self.side_since is None:
            self.side_since = now

    def apply(self, r: dict, now: float) -> tuple[str, str]:
        """Merge a call-state check. Returns (old_stage, new_stage) for the effective stage."""
        old = self.effective_for(now)
        st = r.get("stage")
        if st in STAGES:
            self.auto = st
        md = r.get("conversation_mode")
        if md in ("business", "rapport", "side"):
            self.mode = md
        self.meeting_agreed = self.meeting_agreed or bool(r.get("meeting_agreed"))
        if r.get("momentum") in ("productive", "neutral", "stalled"):
            self.momentum = r["momentum"]
        off_sale = self.auto == "side" or self.mode == "side"
        if off_sale:
            if self.side_since is None:
                self.side_since = now
        else:
            self.side_since = None
            self._quick_side_until = -1.0
        return old, self.effective_for(now)

    def effective_for(self, now: float) -> str:
        return "side" if self.is_side(now) and not (self.pinned and self.pinned != "side") else self.effective()

    def off_sale_seconds(self, now: float) -> float:
        """How long the conversation has been off the sale (rapport doesn't count)."""
        return 0.0 if self.side_since is None else max(0.0, now - self.side_since)

    def guidance(self, now: float, checkins: int, target: int, questions: list[str] | None = None,
                 script: bool = False) -> str:
        st = self.effective_for(now)
        qs = "\n".join(f"- {q}" for q in (questions or DISCOVERY_QUESTIONS))
        if st == "discovery" and script:
            text = SCRIPT_GUIDANCE
        else:
            text = GUIDANCE[st].format(target=target, done=checkins, questions=qs)
        if self.mode == "rapport" and st != "side":
            text += " " + RAPPORT
        if st != "side":
            if self.momentum == "productive":
                text += "\n" + KEEP_GOING
            elif self.momentum == "stalled":
                text += "\n" + STALLED
        return text
