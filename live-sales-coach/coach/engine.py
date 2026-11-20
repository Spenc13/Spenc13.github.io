"""Coaching engine: Anthropic Messages API with prompt caching and streaming.

Request layout (stable prefix first, so it caches):
  system[0] coach-instructions.md            (verbatim)
  system[1] playbook-hormozi-miner-voss.md
  system[2] offer-reference.md                <- cache breakpoint (caches all three)
  user      running summary + last N minutes of transcript + the ask
"""
from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Awaitable, Callable

from .config import Prompts

log = logging.getLogger(__name__)

FALLBACK_BETA = "server-side-fallback-2026-07-01"

# One rulebook for the live coach AND the post-call review, so the review never marks
# Spencer down for doing what the coach told him to do.
RECAP_RULE = (
    "Pain recap (restating the prospect's problem in their own words) belongs at only three moments: "
    "(1) once, right before asking for the appointment; (2) once in the final confirmation after the time is "
    "set; (3) during a presentation, when tying a feature back to their problem. Not after every answer: in "
    "discovery, a short acknowledgment (\"Gotcha.\" / \"Makes sense.\") and the next question is enough; don't "
    "restate what they just said. If Spencer already recapped for this ask, don't recap again."
)
SHARED_RULES = (
    "Coaching rules (the live coach and the post-call review use the same ones):\n"
    "- One question per line. An either/or choice of times (\"Thursday at 10 or Friday at 2?\", \"now, or later "
    "this week?\") is ONE question, not a compound question.\n"
    "- " + RECAP_RULE + "\n"
    "- When the prospect wants off the phone (says they have to go, firmly not interested, upset), ending the "
    "call politely is correct.\n"
    "- Once the appointment is set and confirmed, wrapping up is correct; no extra questions are needed."
)

LIVE_INSTRUCTION = (
    "Live coach mode: Spencer will read your \"Say this next\" line out loud, word for word, right now. "
    "Write it as his exact spoken words: first person, natural and conversational, 10 to 30 words "
    "(up to 40 when asking for a time or appointment), responding directly to what the prospect just said "
    "and fitting the call stage above. Ask at most ONE question: never two questions in the same line, and "
    "no compound questions joined with \"and\" or \"or else\". No question at all when the prospect wants to go or "
    "the call is wrapping up: then the line just ends the call politely. " + RECAP_RULE + " When the line "
    "asks for a time or appointment and no recap was given for it yet, open with a one-sentence recap of their pain "
    "in their own words, then ask for the time. "
    "Don't repeat a point he already made or ask for something already covered. No stage directions or "
    "quotation marks. If the prospect hasn't actually finished their thought, write exactly: "
    "Say this next: (Listening) . If the latest talk is a side conversation unrelated to the sale (someone "
    "else in the room, a personal errand, an unrelated tangent; not rapport), write exactly: "
    "Say this next: (Side conversation) . Keep Tactic and Watch-out to a few words each."
)

FORMAT_REMINDER = (
    "Reply in your default three-part format, one line each, with these exact labels:\n"
    "Say this next: ...\nTactic: ...\nWatch-out: ..."
)

_LABEL_RE = re.compile(
    r"^\s*(?:\d+[.)]\s*)?(?:[*_]{1,2})?\s*(say this next|tactic|watch[- ]?out)\s*(?:[*_]{1,2})?\s*[:\-–—]\s*(?:[*_]{1,2})?",
    re.I | re.M,
)


def parse_coach(text: str) -> dict[str, str]:
    """Split a (possibly partial) reply into say / tactic / watch.

    Anything before the first label, or a reply with no labels, lands in "say"
    so Spencer still sees it.
    """
    out = {"say": "", "tactic": "", "watch": ""}
    matches = list(_LABEL_RE.finditer(text))
    if not matches:
        out["say"] = text.strip()
        return out
    pre = text[: matches[0].start()].strip()
    for i, m in enumerate(matches):
        label = m.group(1).lower()
        key = "say" if label.startswith("say") else "tactic" if label.startswith("tac") else "watch"
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        chunk = text[m.end():end].strip().strip("*_ ").strip()
        out[key] = (out[key] + " " + chunk).strip() if out[key] else chunk
    if pre and not out["say"]:
        out["say"] = pre
    return out


_WORD = re.compile(r"[a-z0-9']+")
_STOP = {"the", "and", "that", "this", "with", "your", "you", "what", "would", "have", "about", "just",
         "it's", "that's", "there", "they", "them", "then", "from", "like", "know", "really", "so", "for", "are", "not", "can", "how", "but", "was", "all", "any", "our", "one", "get", "got", "yes", "yeah", "okay", "gotcha"}


def _timeline_text(timeline: list | None, limit: int = 60) -> str:
    """Coaching cards shown during the call, for the post-call breakdown."""
    if not timeline:
        return "Coaching timeline: (none)"
    label = {"keep_going": "KEEP GOING", "redirect": "REDIRECT", "coach": "COACH", "wrap": "WRAP UP"}
    rows = [f"[{c['t']}] {label.get(c.get('mode'), 'COACH')} ({c.get('stage') or '?'})"
            f"{' SPENCER SAID THIS' if c.get('used') else ''}: {c.get('say', '')}"
            for c in timeline[-limit:]]
    return ("Coaching timeline (what the coach told Spencer, and whether he was on a roll). Lines marked SPENCER "
            "SAID THIS were read from the coach's card:\n" + "\n".join(rows))


def one_question(say: str) -> str:
    """Keep at most one question in a line: everything up to and including the first
    question mark. Statements before it stay ("Makes sense. What does one job profit you?")."""
    i = say.find("?")
    if i == -1 or "?" not in say[i + 1:]:
        return say
    return say[: i + 1].rstrip()


def said_it(suggestion: str, spoken: str) -> bool:
    """Did Spencer (roughly) say the suggested line? Matches on content words."""
    if suggestion.strip().startswith("("):        # "(Stay quiet...)" isn't a line to say
        return False
    want = {w for w in _WORD.findall(suggestion.lower()) if len(w) > 2 and w not in _STOP}
    if len(want) < 3:
        return False
    got = set(_WORD.findall(spoken.lower()))
    hits = sum(1 for w in want if w in got)
    need = 3 if len(want) >= 6 else 2          # short lines ("Thursday at ten or Friday at two?")
    return hits >= need and hits / len(want) >= 0.5


@dataclass
class CoachRequest:
    reason: str                  # "auto" | "ask" | "hotkey" | "suggestion"
    prompt: str                  # what we ask the coach
    question: str                # short label for the card header
    spoke_end_mono: float | None = None   # when the prospect stopped talking (auto only)
    detection: dict | None = None
    fast: bool = False                    # live coach: lowest-latency settings
    created_mono: float = field(default_factory=time.monotonic)


class CoachUnavailable(Exception):
    pass


class CoachEngine:
    def __init__(self, cfg: dict, prompts: Prompts, api_key_present: bool) -> None:
        from .config import get

        self.model = get(cfg, "coach.model", "claude-sonnet-5-5")
        self.thinking = get(cfg, "coach.thinking", "adaptive")
        self.effort = get(cfg, "coach.effort", "low")
        self.max_tokens = int(get(cfg, "coach.max_tokens", 2000))
        self.post_call_max_tokens = int(get(cfg, "coach.post_call_max_tokens", 8000))
        self.use_fallback = bool(get(cfg, "coach.server_fallback", True))
        self.live_thinking = get(cfg, "coach.live_thinking", "between_tools")
        self.prompts = prompts
        self.style_notes = ""          # approved selling notes (spencer-selling-style.md)
        self.client = None
        if api_key_present:
            from anthropic import AsyncAnthropic

            self.client = AsyncAnthropic(max_retries=1, timeout=30.0)

    # ---- request building ---------------------------------------------
    def system_blocks(self) -> list[dict]:
        blocks = [
            {"type": "text", "text": self.prompts.instructions},
            {"type": "text", "text": "# Playbook\n\n" + self.prompts.playbook},
            {"type": "text", "text": "# Offer reference\n\n" + self.prompts.offer},
        ]
        if getattr(self.prompts, "discovery", "").strip():
            blocks.append({"type": "text", "text": (
                "# Spencer's discovery questions (his own questions and wording; a bank to draw from, "
                "not a sequence)\n\n"
                + self.prompts.discovery.strip())})
        if self.style_notes.strip():
            blocks.append({"type": "text", "text": (
                "# Spencer's selling notes (approved by Spencer; standing rules about how he sells)\n\n"
                + self.style_notes.strip())})
        blocks[-1]["cache_control"] = {"type": "ephemeral"}     # caches the whole stable prefix
        return blocks

    def _common(self, max_tokens: int, effort: str | None = None, thinking: str | None = None) -> dict:
        kw: dict = {
            "model": self.model,
            "max_tokens": max_tokens,
            "system": self.system_blocks(),
            "output_config": {"effort": effort or self.effort},
        }
        mode = thinking or self.thinking
        # "between_tools" (no extended thinking) exists only on Sonnet 5.5.
        if mode == "between_tools" and str(self.model).startswith("claude-sonnet-5-5"):
            kw["thinking"] = {"type": "between_tools"}
        else:
            kw["thinking"] = {"type": "adaptive"}
        return kw

    @staticmethod
    def build_user_message(summary: str, recent: str, ask: str, context: str = "") -> str:
        parts = []
        parts.append("Call summary so far:\n" + (summary.strip() or "(call just started)"))
        parts.append("Recent transcript:\n" + (recent.strip() or "(nothing transcribed yet)"))
        if context:
            parts.append(context.strip())
        parts.append(ask.strip())
        parts.append(FORMAT_REMINDER)
        return "\n\n".join(parts)

    # ---- calls ----------------------------------------------------------
    def _messages_api(self):
        """Use the beta namespace when server-side fallbacks are on."""
        return self.client.beta.messages if self.use_fallback else self.client.messages

    def _extra(self) -> dict:
        if self.use_fallback:
            return {"betas": [FALLBACK_BETA], "fallbacks": "default"}
        return {}

    async def stream_coaching(
        self,
        user_text: str,
        on_text: Callable[[str], Awaitable[None] | None],
        fast: bool = False,
    ) -> dict:
        """Stream a coaching reply. Calls on_text(full_text_so_far) as it grows.
        fast=True (live coach) uses the live_thinking setting and low effort."""
        if self.client is None:
            raise CoachUnavailable("ANTHROPIC_API_KEY is not set")
        kw = self._common(self.max_tokens, effort="low" if fast else None,
                          thinking=self.live_thinking if fast else None)
        kw["messages"] = [{"role": "user", "content": user_text}]
        try:
            return await self._do_stream(kw, self._extra(), on_text)
        except TypeError as e:
            # Older SDK without `fallbacks` / `betas`: drop them and carry on.
            if self.use_fallback and ("fallbacks" in str(e) or "betas" in str(e)):
                log.warning("SDK lacks server-side fallbacks; continuing without them")
                self.use_fallback = False
                return await self._do_stream(kw, {}, on_text)
            raise

    async def _do_stream(self, kw: dict, extra: dict, on_text) -> dict:
        text = ""
        api = self._messages_api()
        async with api.stream(**kw, **extra) as stream:
            async for delta in stream.text_stream:
                text += delta
                r = on_text(text)
                if hasattr(r, "__await__"):
                    await r
            final = await stream.get_final_message()
        usage = getattr(final, "usage", None)
        return {
            "text": text,
            "stop_reason": getattr(final, "stop_reason", None),
            "model": getattr(final, "model", self.model),
            "cache_read_tokens": getattr(usage, "cache_read_input_tokens", None) if usage else None,
            "cache_write_tokens": getattr(usage, "cache_creation_input_tokens", None) if usage else None,
            "input_tokens": getattr(usage, "input_tokens", None) if usage else None,
            "output_tokens": getattr(usage, "output_tokens", None) if usage else None,
        }

    async def _create(self, kw: dict):
        api = self._messages_api()
        try:
            return await api.create(**kw, **self._extra())
        except TypeError as e:
            if self.use_fallback and ("fallbacks" in str(e) or "betas" in str(e)):
                self.use_fallback = False
                return await self.client.messages.create(**kw)
            raise

    @staticmethod
    def _text_of(msg) -> str:
        return "".join(getattr(b, "text", "") for b in msg.content if getattr(b, "type", "") == "text")

    async def update_summary(self, previous: str, new_lines: str) -> str:
        """Fold older transcript lines into a short running summary."""
        if self.client is None:
            raise CoachUnavailable("ANTHROPIC_API_KEY is not set")
        kw = self._common(1500, effort="low")
        kw["messages"] = [{
            "role": "user",
            "content": (
                "Maintain a running summary of this live sales call for the coach. "
                "Keep it under 120 words: the prospect's business, problems, budget or price talk, "
                "objections raised, decision-makers, and any next step. Plain sentences, no headers.\n\n"
                f"Current summary:\n{previous or '(none)'}\n\nNew transcript lines:\n{new_lines}\n\n"
                "Return only the updated summary."
            ),
        }]
        msg = await self._create(kw)
        return self._text_of(msg).strip()

    async def track_close(self, summary: str, transcript: str) -> dict:
        """Landing-the-plane tracker: which outcome, and which steps happened (JSON)."""
        from .closing import TRACKER_PROMPT, TRACKER_SCHEMA

        if self.client is None:
            raise CoachUnavailable("ANTHROPIC_API_KEY is not set")
        kw = self._common(1500, effort="low", thinking=self.live_thinking)
        kw["output_config"]["format"] = {"type": "json_schema", "schema": TRACKER_SCHEMA}
        kw["messages"] = [{
            "role": "user",
            "content": (f"Call summary so far:\n{summary or '(none)'}\n\n"
                        f"Transcript:\n{transcript or '(empty)'}\n\n{TRACKER_PROMPT}"),
        }]
        msg = await self._create(kw)
        if getattr(msg, "stop_reason", None) == "refusal":
            return {}
        try:
            return json.loads(self._text_of(msg))
        except json.JSONDecodeError:
            return {}

    async def post_call_summary(self, transcript: str, metrics: dict, coaching_count: int,
                                note: str = "", timeline: list | None = None) -> dict:
        if self.client is None:
            raise CoachUnavailable("ANTHROPIC_API_KEY is not set")
        turning = {
            "type": "object",
            "properties": {
                "time": {"type": "string"},
                "what_happened": {"type": "string"},
                "worked": {"type": "boolean"},
                "why": {"type": "string"},
            },
            "required": ["time", "what_happened", "worked", "why"],
            "additionalProperties": False,
        }
        moment = {
            "type": "object",
            "properties": {
                "time": {"type": "string"},
                "quote": {"type": "string"},
                "missed": {"type": "string"},
                "better_line": {"type": "string"},
            },
            "required": ["time", "quote", "missed", "better_line"],
            "additionalProperties": False,
        }
        schema = {
            "type": "object",
            "properties": {
                "overview": {"type": "string"},
                "key_wins": {"type": "array", "items": {"type": "string"}},
                "missed_opportunities": {"type": "array", "items": {"type": "string"}},
                "missed_moments": {"type": "array", "items": moment},
                "turning_points": {"type": "array", "items": turning},
                "next_steps": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["overview", "key_wins", "missed_opportunities", "missed_moments", "turning_points",
                         "next_steps"],
            "additionalProperties": False,
        }
        kw = self._common(self.post_call_max_tokens, effort="medium")
        kw["output_config"]["format"] = {"type": "json_schema", "schema": schema}
        kw["messages"] = [{
            "role": "user",
            "content": (
                "The call has ended. Review it as Spencer's coach.\n\n"
                + (note + "\n\n" if note else "") +
                f"Computed call metrics (JSON):\n{json.dumps(metrics, indent=2)}\n\n"
                f"Coaching cards shown during the call: {coaching_count}\n"
                + _timeline_text(timeline) + "\n\n"
                f"Full transcript:\n{transcript or '(empty)'}\n\n"
                "Return: a 2-sentence overview; 2 to 4 key wins; 2 to 4 missed opportunities "
                "(cite the moment); missed_moments: up to 5 specific lines from the transcript where Spencer "
                "should have asked a consequence question or checked budget (or skipped another key step), each "
                "with its [mm:ss] time, the exact quote, what he missed, and the better line to use; and 2 to 4 "
                "concrete next steps for Spencer with this prospect. "
                "turning_points: 3 to 5 key moments (with [mm:ss]) where the call moved forward or stalled: what "
                "happened, whether it worked, and why. Use the coaching timeline (when the coach said keep going vs "
                "redirect, and what it suggested) and Spencer's typed notes to explain what he was going for and "
                "why it landed or didn't. "
                "Spencer's typed lines (labeled \"Spencer (typed)\") are ground truth. "
                + SHARED_RULES + "\n"
                "Judge Spencer by these same rules. Never list as a missed opportunity, missed moment, or "
                "stalled turning point anything these rules call for, or anything Spencer said by following a "
                "coach card (marked SPENCER SAID THIS, or clearly matching a card shown just before). Those "
                "were the coach's call, not his mistake. Don't suggest a better line that contradicts the rules "
                "(for example, adding a pain recap after every answer). "
                "Use only facts from the transcript, playbook, and offer reference. "
                "Do not invent prices, terms, or guarantees."
            ),
        }]
        msg = await self._create(kw)
        if getattr(msg, "stop_reason", None) == "refusal":
            raise CoachUnavailable("The summary request was declined")
        raw = self._text_of(msg)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"overview": raw.strip(), "key_wins": [], "missed_opportunities": [], "missed_moments": [],
                    "turning_points": [], "next_steps": []}

    # ---- call breakdown ------------------------------------------------------
    async def _json_request(self, prompt: str, schema: dict, max_tokens: int, effort: str = "medium") -> dict:
        if self.client is None:
            raise CoachUnavailable("ANTHROPIC_API_KEY is not set")
        kw = self._common(max_tokens, effort=effort)
        kw["output_config"]["format"] = {"type": "json_schema", "schema": schema}
        kw["messages"] = [{"role": "user", "content": prompt}]
        msg = await self._create(kw)
        if getattr(msg, "stop_reason", None) == "refusal":
            raise CoachUnavailable("The request was declined")
        try:
            return json.loads(self._text_of(msg))
        except json.JSONDecodeError:
            raise CoachUnavailable("The coach's reply couldn't be read; try again")

    async def breakdown_analyze(self, rep: str, calls: list[dict], steps: list[dict]) -> dict:
        from .breakdown import ANALYSIS_SCHEMA, analysis_prompt
        return await self._json_request(analysis_prompt(rep, calls, steps), ANALYSIS_SCHEMA, 16000)

    async def breakdown_finalize(self, rep: str, analysis: dict, reflections: dict, steps: list[dict]) -> dict:
        from .breakdown import FINAL_SCHEMA, final_prompt
        return await self._json_request(final_prompt(rep, analysis, reflections, steps), FINAL_SCHEMA, 8000)

    # ---- selling notes (after the call) --------------------------------------
    NOTE_SCHEMA = {
        "type": "object",
        "properties": {
            "text": {"type": "string"},
            "source": {"type": "string", "enum": ["transcript", "typed"]},
            "timestamp": {"type": "string"},
            "quote": {"type": "string"},
            "conflicts_with_transcript": {"type": "boolean"},
            "conflict_reason": {"type": "string"},
        },
        "required": ["text", "source", "timestamp", "quote", "conflicts_with_transcript", "conflict_reason"],
        "additionalProperties": False,
    }

    async def propose_notes(self, transcript: str, typed_rules: list[dict], existing: str) -> list[dict]:
        """Propose updates to Spencer's selling notes, each citing a transcript timestamp."""
        if self.client is None:
            raise CoachUnavailable("ANTHROPIC_API_KEY is not set")
        schema = {"type": "object", "properties": {"notes": {"type": "array", "items": self.NOTE_SCHEMA}},
                  "required": ["notes"], "additionalProperties": False}
        rules = "\n".join(f"[{r['t']}] {r['text']}" for r in typed_rules) or "(none)"
        kw = self._common(4000, effort="medium")
        kw["output_config"]["format"] = {"type": "json_schema", "schema": schema}
        kw["messages"] = [{"role": "user", "content": (
            "The call has ended. Propose updates to Spencer's selling notes: short standing notes about how he "
            "sells (habits that worked, habits to change, phrases that landed, rules he states) that will help "
            "coach him on future calls. Propose at most 5 from the transcript, plus every rule Spencer typed.\n"
            "- Each note cites the transcript timestamp [mm:ss] it came from and a short exact quote. Typed rules "
            "use source \"typed\" and the time he typed them.\n"
            "- Check every note against the transcript. If the transcript contradicts it, set "
            "conflicts_with_transcript true and say why: the transcript wins.\n"
            "- Don't repeat anything already in his existing notes.\n\n"
            f"Existing notes:\n{existing.strip() or '(none yet)'}\n\n"
            f"Rules Spencer typed during the call:\n{rules}\n\n"
            f"Transcript:\n{transcript or '(empty)'}"
        )}]
        msg = await self._create(kw)
        try:
            return list(json.loads(self._text_of(msg)).get("notes") or [])
        except json.JSONDecodeError:
            return []

    async def verify_note(self, text: str, transcript: str) -> dict:
        """Check an edited note against the transcript (the transcript wins)."""
        if self.client is None:
            raise CoachUnavailable("ANTHROPIC_API_KEY is not set")
        schema = {"type": "object", "properties": {
            "conflicts_with_transcript": {"type": "boolean"}, "conflict_reason": {"type": "string"},
            "timestamp": {"type": "string"}, "quote": {"type": "string"}},
            "required": ["conflicts_with_transcript", "conflict_reason", "timestamp", "quote"],
            "additionalProperties": False}
        kw = self._common(1500, effort="low")
        kw["output_config"]["format"] = {"type": "json_schema", "schema": schema}
        kw["messages"] = [{"role": "user", "content": (
            f"Spencer wants to save this selling note: \"{text}\"\n"
            "Does the transcript contradict it? If yes, set conflicts_with_transcript true and explain. Give the "
            "[mm:ss] timestamp and exact quote that best supports or contradicts it (\"\" if none).\n\n"
            f"Transcript:\n{transcript or '(empty)'}")}]
        msg = await self._create(kw)
        try:
            return json.loads(self._text_of(msg))
        except json.JSONDecodeError:
            return {"conflicts_with_transcript": False, "conflict_reason": "", "timestamp": "", "quote": ""}
