"""Reading the room: when the prospect wants off the phone, or the call is already done.

The coach is built to keep good conversations going, but it must take the hint:

  wants out (soft)   the prospect says once that they have to go / it's a bad time
                     -> no new questions; offer one quick callback time (or a short
                        wrap if a time is already set)
  wants out (firm)   they've said it twice, said they're not interested twice, told
                     Spencer to stop calling, or are angry
                     -> give the polite line that ends the call, then stay quiet
  done               the appointment is set and Spencer is wrapping up
                     -> no more questions; stay quiet (a warm goodbye at most)

A local check catches the words right away; the background tracker can also flag
"wants out" and clear it if the prospect re-engages.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

GOTTA_GO = re.compile(
    r"\b(?:(?:i|we)\s*(?:'ve|have)?\s*(?:got|gotta|have|need|needa)\s*(?:to)?\s*(?:go|run|get going|get off|hop off|jump off|"
    r"get back to (?:work|it|the job))|"
    r"i'?m (?:driving|on a (?:job|roof|site|ladder)|on the road|in the middle of (?:something|a job)|"
    r"with a (?:customer|client)|about to (?:go|walk) in|(?:really |kinda |pretty )?busy(?: right now)?)|"
    r"(?:can'?t|cannot) talk(?: right now)?|(?:this is |it'?s )?(?:a )?(?:bad|not a good) time|"
    r"call (?:me )?back (?:later|another time|tomorrow|next week)|let me (?:go|call you back)|"
    r"i (?:really )?(?:gotta|have to|need to) (?:go|run|hop off|get off)|wrap (?:this|it) up|make it quick)\b",
    re.I,
)

NOT_INTERESTED = re.compile(
    r"\b(?:not interested|no thanks?(?: you)?|no,? thank you|(?:i|we) don'?t need (?:it|that|this|any)|"
    r"we'?re (?:good|all set|fine|covered)|already (?:have|got) (?:someone|a company|a guy|that covered)|"
    r"not (?:looking|right now|for us)|pass on (?:it|that|this))\b",
    re.I,
)

HOSTILE = re.compile(
    r"\b(?:stop calling|quit calling|don'?t (?:ever )?call (?:me|us|here|again)|take (?:me|us|my number) off|"
    r"remove (?:me|us|my number)|do not call|leave (?:me|us) alone|(?:i|i'?m) (?:said|told you|telling you) (?:no|not interested)|"
    r"how (?:did|'d) you get (?:this|my) number|what part of no|f+u+c+k+|f\*+|shit|damn it|go to hell|piss off|"
    r"scam(?:mer)?|i'?m hanging up|hanging up now)\b",
    re.I,
)

GOODBYE = re.compile(r"\b(?:bye|goodbye|take care|have a good (?:one|day|night)|talk (?:to you )?(?:soon|later)|see ya)\b", re.I)

SOFT = ("The prospect just said they have to go (or it's a bad time). Take the hint: no new discovery questions and "
        "no pitch. If a meeting time is already set, give a short, warm line to wrap up the call. Otherwise give "
        "ONE short line that respects their time and offers a specific callback time (or asks when is better), and "
        "that's it.")
FIRM = ("The prospect wants off the phone: they've said they have to go more than once, said they're not interested "
        "again, told Spencer to stop calling, or are getting upset. End the call now. Give ONE short, polite line "
        "that ends the call: thank them for their time and say goodbye. No question, no rebuttal, no pitch, no "
        "\"before you go\". Only if they didn't say not interested or stop calling, you may add that Spencer will "
        "follow up at a better time.")
DONE = ("The appointment is set and Spencer is wrapping up the call. Don't suggest another question or any new "
        "topic. At most, a short warm goodbye.")
MEETING_SET = ("A meeting time is already agreed. Don't go back to discovery or ask new questions: only the "
               "remaining confirmation steps (if any are missing), then a warm wrap.")


@dataclass
class ExitState:
    gotta_go: int = 0
    not_interested: int = 0
    hostile: bool = False
    tracker_out: bool = False        # the background tracker says the prospect wants out
    wrapping: bool = False           # Spencer said goodbye after the appointment was set
    firm_sent: bool = False          # the "end the call" card was already shown
    last_t: float = -1e9

    def level(self) -> int:
        """0 = no hint, 1 = soft (wants to go once), 2 = firm (end the call)."""
        if self.hostile or self.gotta_go >= 2 or self.not_interested >= 2 or self.tracker_out:
            return 2
        if self.gotta_go or self.not_interested:
            return 1
        return 0

    def hear_prospect(self, text: str, t: float) -> int:
        """Count exit signals in a prospect line. Returns the new level if it went up, else 0."""
        before = self.level()
        if HOSTILE.search(text):
            self.hostile = True
        if GOTTA_GO.search(text):
            self.gotta_go += 1
        if NOT_INTERESTED.search(text):
            self.not_interested += 1
        if self.level() > before:
            self.last_t = t
            return self.level()
        return 0

    def apply_tracker(self, r: dict) -> None:
        wants = r.get("prospect_wants_out")
        if wants is True:
            self.tracker_out = True
        elif wants is False and r.get("momentum") == "productive" and not self.hostile:
            # They re-engaged (sharing real detail again): let the coach help again.
            self.tracker_out = False
            self.gotta_go = self.not_interested = 0
            self.firm_sent = False

    def quiet(self) -> bool:
        """No more automatic live cards: the end-the-call card was shown, or the call is wrapped."""
        return self.wrapping or (self.level() >= 2 and self.firm_sent)

    def guidance(self, meeting_set: bool) -> str:
        lvl = self.level()
        if lvl >= 2:
            return FIRM
        if self.wrapping:
            return DONE
        if lvl == 1:
            return SOFT
        if meeting_set:
            return MEETING_SET
        return ""

    def to_dict(self) -> dict:
        return {"level": self.level(), "wrapping": self.wrapping, "gotta_go": self.gotta_go,
                "not_interested": self.not_interested, "hostile": self.hostile}
