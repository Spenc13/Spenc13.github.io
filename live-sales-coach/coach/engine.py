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


@dataclass
class CoachRequest:
    reason: str                  # "auto" | "ask" | "hotkey" | "suggestion"
    prompt: str                  # what we ask the coach
    question: str                # short label for the card header
    spoke_end_mono: float | None = None   # when the prospect stopped talking (auto only)
    detection: dict | None = None
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
        self.prompts = prompts
        self.client = None
        if api_key_present:
            from anthropic import AsyncAnthropic

            self.client = AsyncAnthropic(max_retries=1, timeout=30.0)

    # ---- request building ---------------------------------------------
    def system_blocks(self) -> list[dict]:
        return [
            {"type": "text", "text": self.prompts.instructions},
            {"type": "text", "text": "# Playbook\n\n" + self.prompts.playbook},
            {
                "type": "text",
                "text": "# Offer reference\n\n" + self.prompts.offer,
                "cache_control": {"type": "ephemeral"},
            },
        ]

    def _common(self, max_tokens: int, effort: str | None = None) -> dict:
        kw: dict = {
            "model": self.model,
            "max_tokens": max_tokens,
            "system": self.system_blocks(),
            "output_config": {"effort": effort or self.effort},
        }
        if self.thinking == "between_tools":
            kw["thinking"] = {"type": "between_tools"}
        else:
            kw["thinking"] = {"type": "adaptive"}
        return kw

    @staticmethod
    def build_user_message(summary: str, recent: str, ask: str) -> str:
        parts = []
        parts.append("Call summary so far:\n" + (summary.strip() or "(call just started)"))
        parts.append("Recent transcript:\n" + (recent.strip() or "(nothing transcribed yet)"))
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
    ) -> dict:
        """Stream a coaching reply. Calls on_text(full_text_so_far) as it grows."""
        if self.client is None:
            raise CoachUnavailable("ANTHROPIC_API_KEY is not set")
        kw = self._common(self.max_tokens)
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

    async def post_call_summary(self, transcript: str, metrics: dict, coaching_count: int) -> dict:
        if self.client is None:
            raise CoachUnavailable("ANTHROPIC_API_KEY is not set")
        schema = {
            "type": "object",
            "properties": {
                "overview": {"type": "string"},
                "key_wins": {"type": "array", "items": {"type": "string"}},
                "missed_opportunities": {"type": "array", "items": {"type": "string"}},
                "next_steps": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["overview", "key_wins", "missed_opportunities", "next_steps"],
            "additionalProperties": False,
        }
        kw = self._common(self.post_call_max_tokens, effort="medium")
        kw["output_config"]["format"] = {"type": "json_schema", "schema": schema}
        kw["messages"] = [{
            "role": "user",
            "content": (
                "The call has ended. Review it as Spencer's coach.\n\n"
                f"Computed call metrics (JSON):\n{json.dumps(metrics, indent=2)}\n\n"
                f"Coaching cards shown during the call: {coaching_count}\n\n"
                f"Full transcript:\n{transcript or '(empty)'}\n\n"
                "Return: a 2-sentence overview; 2 to 4 key wins; 2 to 4 missed opportunities "
                "(cite the moment); and 2 to 4 concrete next steps for Spencer with this prospect. "
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
            return {"overview": raw.strip(), "key_wins": [], "missed_opportunities": [], "next_steps": []}
