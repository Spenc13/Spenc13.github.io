"""Fast local check: does a prospect line look like an objection or a buying signal?

This only decides *whether* to call the coach. The coach decides *what* to say;
there are no canned replies here.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

OBJECTION = "objection"
BUYING = "buying_signal"
RISK = "risk_signal"


@dataclass(frozen=True)
class Rule:
    key: str
    kind: str
    label: str
    pattern: re.Pattern


def _r(key: str, kind: str, label: str, *alts: str) -> Rule:
    return Rule(key, kind, label, re.compile(r"\b(?:" + "|".join(alts) + r")", re.I))


# Ordered: the first match wins, so specific phrases come before broad ones.
RULES: list[Rule] = [
    _r("send_info", OBJECTION, "Send me something",
       r"send (?:me|us|over)? ?(?:something|some ?info|info|information|a deck|details|an email|it over)",
       r"email me", r"shoot me an? (?:email|something)", r"put (?:something|it) in writing"),
    _r("references", OBJECTION, "Wants references",
       r"references?", r"talk to (?:some|a few|other) (?:of your )?(?:clients|customers)"),
    _r("quote", OBJECTION, "Wants a quote",
       r"send (?:me )?a (?:quote|proposal|price sheet)", r"(?:get|give) me a (?:quote|proposal)"),
    _r("think", OBJECTION, "Needs to think",
       r"think (?:about|it over|on it)", r"need (?:some )?time", r"sleep on it", r"not (?:ready|sure) yet",
       r"get back to you", r"circle back"),
    _r("decision_maker", OBJECTION, "Decision-maker not present",
       r"(?:talk|speak|check|run it by) (?:to |with )?(?:my )?(?:wife|husband|partner|business partner|boss|owner|brother|dad|father|team|accountant)",
       r"my (?:wife|husband|partner) handles", r"not (?:my|the) decision"),
    _r("price", OBJECTION, "Too expensive",
       r"too (?:expensive|much|pricey|high)", r"(?:that'?s|that is|it'?s) (?:a lot|steep|pricey|expensive)",
       r"can'?t afford", r"out of (?:my|our) budget", r"cheaper", r"(?:lower|better) price", r"discount",
       r"don'?t have (?:the )?(?:money|budget)"),
    _r("burned", OBJECTION, "Burned by a past agency",
       r"tried (?:that|it|seo|marketing|an agency|ads|facebook)", r"(?:agency|company|guy|marketer)s? (?:before|last year|took|burned|ripped)",
       r"didn'?t work", r"waste of money", r"burned", r"ripped (?:us|me) off", r"never (?:saw|got) (?:any )?results"),
    _r("contract", OBJECTION, "Contract length",
       r"month[- ]to[- ]month", r"(?:long|12|twelve|six|6)[- ]month (?:contract|commitment|term)",
       r"locked in", r"(?:no|don'?t want a) contract", r"cancel (?:any ?time)?"),
    _r("pay_later", OBJECTION, "Pay after results",
       r"pay (?:later|after|when (?:i|we) see)", r"after (?:i|we) see results", r"performance[- ]based"),
    _r("guarantee", RISK, "Asks for a guarantee",
       r"guarantee", r"promise (?:me|results)"),
    _r("brush_off", OBJECTION, "Brush-off",
       r"not interested", r"(?:too|really|pretty) busy", r"bad time", r"we'?re (?:good|all set|fine)",
       r"already have (?:someone|a guy|an agency|a company)", r"word of mouth"),
    _r("price_q", BUYING, "Asking about price",
       r"how much", r"what(?:'?s| is| does| would) (?:it|this|that|the) (?:cost|price|run)",
       r"what(?:'?s| is| are) (?:the|your) (?:price|prices|pricing|packages|rates)", r"pricing",
       r"what (?:does|would) (?:it|that|this) (?:cost|run)"),
    _r("timeline_q", BUYING, "Asking about timing",
       r"when (?:can|could|would) (?:you|we) (?:start|begin|get going)", r"how (?:long|fast|soon|quick)",
       r"start date", r"get started", r"timeline"),
    _r("social_proof_q", BUYING, "Asking who else uses it",
       r"who else", r"other (?:roofers|remodelers|pool|contractors|companies)", r"(?:do you|you guys) work with"),
    _r("next_q", BUYING, "Asking what happens next",
       r"what(?:'?s| is| are| would be)? (?:the )?next steps?", r"what happens (?:next|after)", r"how does (?:it|this|onboarding) work",
       r"sign up", r"where do (?:i|we) sign"),
]


@dataclass
class Detection:
    key: str
    kind: str
    label: str
    text: str


def detect(text: str) -> Detection | None:
    for rule in RULES:
        if rule.pattern.search(text):
            return Detection(rule.key, rule.kind, rule.label, text)
    return None


class Debouncer:
    """Decide whether a detection should fire an automatic coach call."""

    def __init__(self, min_gap: float = 8.0, same_kind_cooldown: float = 45.0) -> None:
        self.min_gap = min_gap
        self.same_kind_cooldown = same_kind_cooldown
        self._last_fire: float | None = None
        self._last_by_key: dict[str, float] = {}

    def should_fire(self, det: Detection, now: float) -> bool:
        last_key = self._last_by_key.get(det.key)
        if last_key is not None and now - last_key < self.same_kind_cooldown:
            return False
        if self._last_fire is not None and now - self._last_fire < self.min_gap:
            return False
        self._last_fire = now
        self._last_by_key[det.key] = now
        return True

    def note_manual(self, now: float) -> None:
        """A manual ask also resets the gap so auto doesn't fire right on top of it."""
        self._last_fire = now
