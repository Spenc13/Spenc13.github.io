"""CallSession: one call, live or replayed, from consent to saved summary.

Pipeline (the same for live audio, WAV replay, and text replay):

  audio/replay -> STT events -> transcript + metrics -> local trigger check
               -> (debounced) coach request -> streamed coaching card
  end call     -> post-call summary -> calls/YYYY-MM-DD_HH-MM/
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Callable

from .config import Prompts, get, keys_status
from .engine import CoachEngine, CoachRequest, CoachUnavailable, parse_coach
from .metrics import Metrics
from .storage import CallStore
from .stt import make_stream
from .stt.base import SttEvent
from .transcript import LABELS, PROSPECT, REP, Transcript, Utterance, fmt_clock
from .triggers import BUYING, OBJECTION, Debouncer, detect

log = logging.getLogger(__name__)

Emit = Callable[[str, dict], None]

SUGGESTIONS = {
    "deeper": "Give Spencer one deeper discovery question for this exact moment.",
    "listen": "Spencer has been talking a lot. Give him one short question that hands the floor back to the prospect.",
    "pain": "Help Spencer restate the prospect's main problem in the prospect's own words and check for agreement.",
}


class CallSession:
    def __init__(self, cfg: dict, prompts: Prompts, emit: Emit, mode: str = "live",
                 replay_path: str | None = None) -> None:
        self.cfg = cfg
        self.prompts = prompts
        self.emit = emit
        self.mode = mode                      # "live" | "replay_text" | "replay_wav"
        self.replay_path = Path(replay_path) if replay_path else None
        self.keys = keys_status()
        self.engine = CoachEngine(cfg, prompts, self.keys["anthropic"])
        self.transcript = Transcript()
        self.metrics = Metrics()
        self.debouncer = Debouncer(
            float(get(cfg, "triggers.min_gap_seconds", 8)),
            float(get(cfg, "triggers.same_kind_cooldown_seconds", 45)),
        )
        self.auto = bool(get(cfg, "triggers.auto", True))
        self.window_s = float(get(cfg, "coach.transcript_window_minutes", 4)) * 60
        self.summary_every = float(get(cfg, "coach.summary_refresh_seconds", 90))
        self.lookback = float(get(cfg, "hotkey.lookback_seconds", 20))

        self.store: CallStore | None = None
        self.started_at: datetime | None = None
        self.title = "Live call"
        self.running = False
        self.paused = False
        self._accum = 0.0
        self._resume_mono = 0.0
        self._tasks: list[asyncio.Task] = []
        self._coach_task: asyncio.Task | None = None
        self._summary_task: asyncio.Task | None = None
        self._streams = []
        self._captures = []
        self._replay = None
        self._open_turn: dict[str, Utterance | None] = {REP: None, PROSPECT: None}
        self._partial: dict[str, str] = {REP: "", PROSPECT: ""}
        self._running_summary = ""
        self._summarized_upto = 0.0
        self._last_summary_mono = 0.0
        self._coaching_count = 0
        self._ended = asyncio.Event()
        self.health = {
            "stt": {"state": "idle", "message": ""},
            "coach": {"state": "ok" if self.keys["anthropic"] else "down",
                      "message": "" if self.keys["anthropic"] else "ANTHROPIC_API_KEY not set: transcript only"},
        }

    # ------------------------------------------------------------ clock
    def elapsed(self) -> float:
        if self.mode == "replay_text" and self._replay is not None:
            return self._replay._clock          # script time, so sped-up replays read true
        if not self.running or self.paused:
            return self._accum
        return self._accum + (time.monotonic() - self._resume_mono)

    # ------------------------------------------------------------ health
    def _set_health(self, part: str, state: str, message: str = "") -> None:
        self.health[part] = {"state": state, "message": message}
        self.emit("health", self.health)

    async def _stt_status(self, speaker: str, state: str, message: str) -> None:
        if state == "ok":
            others_down = any(getattr(s, "_last_state", "ok") == "down" for s in self._streams if s.speaker != speaker)
            for s in self._streams:
                if s.speaker == speaker:
                    s._last_state = "ok"
            if not others_down:
                self._set_health("stt", "ok", "")
        else:
            for s in self._streams:
                if s.speaker == speaker:
                    s._last_state = "down"
            who = LABELS.get(speaker, speaker)
            self._set_health("stt", "down", f"{who} audio: {message}")

    # ------------------------------------------------------------ lifecycle
    async def start(self) -> None:
        self.started_at = datetime.now()
        self.store = CallStore(get(self.cfg, "storage.calls_dir", "calls"), self.started_at)
        self.running = True
        self.paused = False
        self._resume_mono = time.monotonic()
        loop = asyncio.get_running_loop()

        if self.mode == "replay_text":
            from .replay import TextReplay

            self._replay = TextReplay(
                self.replay_path, self.on_stt,
                wpm=float(get(self.cfg, "replay.words_per_minute", 165)),
                speed=float(get(self.cfg, "replay.speed", 1.0)),
            )
            self.title = f"Replay: {self._replay.title}"
            self._set_health("stt", "ok", "Text replay (no speech-to-text needed)")
            self._tasks.append(asyncio.create_task(self._run_replay()))
        elif self.mode == "replay_wav":
            from .replay import WavReplay

            stt_cfg = dict(self.cfg.get("stt") or {})
            provider = stt_cfg.pop("provider", "deepgram")

            def mk(channels, rate, channel_speakers, diarize_map):
                s = make_stream(
                    provider,
                    speaker=REP, sample_rate=rate, channels=channels,
                    on_event=self.on_stt,
                    on_status=lambda st, m: self._stt_status(REP, st, m),
                    channel_speakers=channel_speakers, diarize_map=diarize_map,
                    **stt_cfg,
                )
                self._streams.append(s)
                return s

            self._replay = WavReplay(self.replay_path, mk, int(get(self.cfg, "audio.chunk_ms", 100)),
                                     float(get(self.cfg, "replay.speed", 1.0)))
            self.title = f"Replay: {self._replay.title}"
            self._set_health("stt", "connecting", "Connecting to Deepgram")
            self._tasks.append(asyncio.create_task(self._run_replay()))
        else:
            self.title = "Live call"
            await self._start_live(loop)

        self._tasks.append(asyncio.create_task(self._tick()))
        self.emit("call", {"state": "live", "title": self.title, "mode": self.mode,
                           "dir": str(self.store.dir)})
        self.emit("health", self.health)

    async def _start_live(self, loop: asyncio.AbstractEventLoop) -> None:
        from .audio import open_loopback, open_mic

        audio_cfg = self.cfg.get("audio") or {}
        stt_cfg = dict(self.cfg.get("stt") or {})
        provider = stt_cfg.pop("provider", "deepgram")
        self._set_health("stt", "connecting", "Connecting to speech-to-text")

        for speaker, opener in ((REP, open_mic), (PROSPECT, open_loopback)):
            holder: dict = {}

            def on_chunk(pcm: bytes, holder=holder) -> None:   # audio thread
                s = holder.get("stream")
                if s is not None:
                    loop.call_soon_threadsafe(s.feed, pcm)

            try:
                cap = opener(audio_cfg, on_chunk)
            except Exception as e:
                self._set_health("stt", "down", f"{LABELS[speaker]} audio device: {e}")
                self.emit("toast", {"level": "error", "text": f"{LABELS[speaker]} audio: {e}"})
                continue
            stream = make_stream(
                provider, speaker=speaker, sample_rate=cap.rate, channels=1,
                on_event=self.on_stt,
                on_status=lambda st, m, sp=speaker: self._stt_status(sp, st, m),
                **stt_cfg,
            )
            holder["stream"] = stream
            self._streams.append(stream)
            self._tasks.append(asyncio.create_task(stream.run()))
            stream.set_paused(False)
            try:
                cap.start()
            except Exception as e:
                self._set_health("stt", "down", f"{LABELS[speaker]} audio device: {e}")
                continue
            self._captures.append(cap)
            self.emit("toast", {"level": "info", "text": f"{LABELS[speaker]}: {cap.device_name} @ {cap.rate} Hz"})
        if not self.keys["deepgram"]:
            self._set_health("stt", "down", "DEEPGRAM_API_KEY not set: no live transcript")

    async def _run_replay(self) -> None:
        try:
            await self._replay.run()
        except Exception as e:
            self._set_health("stt", "down", f"Replay error: {e}")
            self.emit("toast", {"level": "error", "text": f"Replay stopped: {e}"})
            return
        if self.running:
            await asyncio.sleep(1.5)
            await self.end()

    def pause(self) -> None:
        if not self.running or self.paused:
            return
        self._accum = self.elapsed()
        self.paused = True
        for s in self._streams:
            s.set_paused(True)
        if self._replay is not None:
            self._replay.paused.clear()
        self.emit("call", {"state": "paused", "title": self.title, "mode": self.mode})

    def resume(self) -> None:
        if not self.running or not self.paused:
            return
        self.paused = False
        self._resume_mono = time.monotonic()
        for s in self._streams:
            s.set_paused(False)
        if self._replay is not None:
            self._replay.paused.set()
        self.emit("call", {"state": "live", "title": self.title, "mode": self.mode})

    async def end(self) -> None:
        if not self.running:
            return
        self._accum = self.elapsed()
        self.running = False
        self.paused = False
        self.emit("call", {"state": "ending", "title": self.title, "mode": self.mode})
        for cap in self._captures:
            try:
                cap.stop()
            except Exception:
                pass
        for s in self._streams:
            try:
                await asyncio.wait_for(s.close(), timeout=2)
            except Exception:
                pass
        await asyncio.sleep(0.8 if self._streams else 0)   # last finals
        current = asyncio.current_task()
        for t in self._tasks:
            if t is not current:
                t.cancel()
        if self._coach_task and not self._coach_task.done():
            try:
                await asyncio.wait_for(asyncio.shield(self._coach_task), timeout=8)
            except Exception:
                pass
        for sp in (REP, PROSPECT):
            self._close_turn(sp)
        self.metrics.tick(self._accum)
        self.metrics.finalize()
        snap = self.metrics.snapshot()
        self.emit("metrics", snap)

        meta = {
            "title": self.title,
            "mode": self.mode,
            "started": self.started_at.isoformat(timespec="seconds") if self.started_at else "",
            "length": fmt_clock(self._accum),
            "overall": snap.get("overall"),
            "replay_file": str(self.replay_path) if self.replay_path else None,
            "coach_model": self.engine.model,
            "coaching_cards": self._coaching_count,
            "consent_confirmed": True,
        }
        full = self.transcript.text()
        self.store.write_transcript(full)
        self.store.write_metrics({"meta": meta, **snap})

        self.emit("summary", {"state": "pending"})
        summary, err = None, None
        if not self.transcript.finals:
            err = "No transcript was captured."
        else:
            try:
                summary = await self.engine.post_call_summary(full, snap, self._coaching_count)
            except CoachUnavailable as e:
                err = str(e)
            except Exception as e:
                err = f"Claude API error ({type(e).__name__})"
                log.warning("post-call summary failed: %s", type(e).__name__)
        self.store.write_summary(summary, meta, err)
        self.store.close()
        self.emit("summary", {"state": "done" if summary else "error", "summary": summary, "error": err,
                              "meta": meta, "dir": str(self.store.dir)})
        self.emit("call", {"state": "ended", "title": self.title, "mode": self.mode, "dir": str(self.store.dir)})
        self._ended.set()

    async def wait_ended(self) -> None:
        await self._ended.wait()

    # ------------------------------------------------------------ transcript
    def _close_turn(self, speaker: str) -> None:
        turn = self._open_turn.get(speaker)
        if turn is not None:
            self.emit("line", {"id": turn.id, "speaker": speaker, "text": turn.text,
                               "t": fmt_clock(turn.t), "final": True})
        self._open_turn[speaker] = None
        self._partial[speaker] = ""

    async def on_stt(self, ev: SttEvent) -> None:
        if not self.running:
            return
        sp = ev.speaker
        other = PROSPECT if sp == REP else REP
        if ev.final or ev.text:
            # The other speaker started talking: their open turn is done.
            if self._open_turn.get(other) is not None and not self._partial.get(other):
                self._close_turn(other)

        turn = self._open_turn.get(sp)
        if not ev.final:
            self._partial[sp] = ev.text
            base = turn.text + " " if turn else ""
            line_id = turn.id if turn else f"p-{sp}"
            self.emit("line", {"id": line_id, "speaker": sp, "text": base + ev.text,
                               "t": fmt_clock(turn.t if turn else ev.start), "final": False})
            return

        received = time.monotonic()
        self._partial[sp] = ""
        seg = Utterance(sp, ev.text, ev.start, ev.duration, True, ev.spoke_end_mono)
        self.metrics.add_utterance(seg)
        if turn is None:
            turn = Utterance(sp, ev.text, ev.start, ev.duration, True, ev.spoke_end_mono)
            self.transcript.add(turn)
            self._open_turn[sp] = turn
            self.emit("line", {"id": turn.id, "speaker": sp, "text": turn.text, "t": fmt_clock(turn.t),
                               "final": True, "replaces": f"p-{sp}"})
        else:
            turn.text = f"{turn.text} {ev.text}".strip()
            turn.duration = max(turn.duration, ev.start + ev.duration - turn.t)
            turn.spoke_end_mono = ev.spoke_end_mono
            self.emit("line", {"id": turn.id, "speaker": sp, "text": turn.text, "t": fmt_clock(turn.t), "final": True})
        if ev.speech_final:
            self._close_turn(sp)

        if sp == PROSPECT:
            det = detect(ev.text)
            if det:
                if det.kind == OBJECTION:
                    self.metrics.add_objection(det.key, det.label, ev.start)
                self.emit("signal", {"kind": det.kind, "label": det.label, "quote": ev.text})
                if self.auto and self.debouncer.should_fire(det, ev.start + ev.duration):
                    kind_word = "buying signal" if det.kind == BUYING else det.kind.replace("_", " ")
                    await self.request_coach(CoachRequest(
                        reason="auto",
                        question=f"{det.label} ({kind_word})",
                        prompt=(f'The prospect just said: "{ev.text}"\n'
                                f"A local keyword check flagged this as a {kind_word}: {det.label}. "
                                "Coach Spencer on what to say next."),
                        spoke_end_mono=ev.spoke_end_mono,
                        detection={"key": det.key, "kind": det.kind, "label": det.label,
                                   "stt_latency_s": round(received - ev.spoke_end_mono, 2)},
                    ))
        self.emit("metrics", self.metrics.snapshot())

    # ------------------------------------------------------------ coaching
    async def ask(self, question: str) -> None:
        question = question.strip()
        if not question:
            return
        self.debouncer.note_manual(self.elapsed())
        await self.request_coach(CoachRequest(
            reason="ask", question=question, prompt=f"Spencer asks: {question}"))

    async def hotkey(self) -> None:
        self.debouncer.note_manual(self.elapsed())
        now = self.elapsed()
        recent = [u for u in self.transcript.finals if u.end >= now - self.lookback]
        partial = " / ".join(f"{LABELS[s]} (still talking): {t}" for s, t in self._partial.items() if t)
        last = self.transcript.text(recent) + (("\n" + partial) if partial else "")
        await self.request_coach(CoachRequest(
            reason="hotkey",
            question=f"Hotkey: last {int(self.lookback)} seconds",
            prompt=(f"Spencer pressed the coach hotkey. Focus on the last {int(self.lookback)} seconds of the call:\n"
                    f"{last or '(nothing in the last few seconds)'}\n\nWhat should he say next?"),
        ))

    async def suggestion(self, key: str) -> None:
        prompt = SUGGESTIONS.get(key)
        if prompt:
            self.debouncer.note_manual(self.elapsed())
            await self.request_coach(CoachRequest(reason="suggestion", question=prompt.split(".")[0], prompt=prompt))

    async def request_coach(self, req: CoachRequest) -> None:
        # Newest moment wins: an in-flight card about an older line is cancelled.
        if self._coach_task and not self._coach_task.done():
            self._coach_task.cancel()
        self._coach_task = asyncio.create_task(self._run_coach(req))

    def _recent_transcript(self) -> str:
        cutoff = self.elapsed() - self.window_s
        utts = self.transcript.since(cutoff)
        text = self.transcript.text(utts)
        partial = "\n".join(f"{LABELS[s]} (still talking): {t}" for s, t in self._partial.items() if t)
        return text + (("\n" + partial) if partial else "")

    async def _run_coach(self, req: CoachRequest) -> None:
        self.emit("coach", {"state": "thinking", "question": req.question, "reason": req.reason})
        if self.engine.client is None:
            self.emit("coach", {"state": "error", "question": req.question,
                                "error": "Coach offline: ANTHROPIC_API_KEY is not set. Transcript and scoring still run."})
            return
        user = self.engine.build_user_message(self._running_summary, self._recent_transcript(), req.prompt)
        t0 = time.monotonic()
        anchor = req.spoke_end_mono or req.created_mono
        first_card: dict = {}

        def on_text(text: str) -> None:
            parsed = parse_coach(text)
            if parsed["say"] and "latency" not in first_card:
                first_card["latency"] = time.monotonic() - anchor
            self.emit("coach", {"state": "streaming", "question": req.question, **parsed,
                                "latency_s": round(first_card.get("latency", 0), 2) or None})

        try:
            result = await self.engine.stream_coaching(user, on_text)
        except asyncio.CancelledError:
            raise
        except CoachUnavailable as e:
            self._set_health("coach", "down", str(e))
            self.emit("coach", {"state": "error", "question": req.question, "error": str(e)})
            return
        except Exception as e:
            name = type(e).__name__
            status = getattr(e, "status_code", None)
            msg = f"Claude API unavailable ({name}{' ' + str(status) if status else ''}). Transcript continues."
            self._set_health("coach", "down", msg)
            self.emit("coach", {"state": "error", "question": req.question, "error": msg})
            log.warning("coach request failed: %s %s", name, status or "")
            return

        if self.health["coach"]["state"] != "ok":
            self._set_health("coach", "ok", "")
        done = time.monotonic()
        parsed = parse_coach(result["text"])
        if result.get("stop_reason") == "refusal":
            parsed = {"say": "(The coach declined this one. Ask again in different words.)", "tactic": "", "watch": ""}
        latency_first = first_card.get("latency", done - anchor)
        record = {
            "reason": req.reason,
            "question": req.question,
            "detection": req.detection,
            "call_time": fmt_clock(self.elapsed()),
            **parsed,
            "raw": result["text"],
            "latency_s": round(latency_first, 2),
            "latency_complete_s": round(done - anchor, 2),
            "api_seconds": round(done - t0, 2),
            "model": result.get("model"),
            "stop_reason": result.get("stop_reason"),
            "cache_read_tokens": result.get("cache_read_tokens"),
            "cache_write_tokens": result.get("cache_write_tokens"),
        }
        self._coaching_count += 1
        if self.store:
            self.store.log_coaching(record)
        self.emit("coach", {"state": "done", "question": req.question, **parsed,
                            "latency_s": record["latency_s"], "latency_complete_s": record["latency_complete_s"],
                            "measured_from": "prospect stopped talking" if req.spoke_end_mono else "your request",
                            "stt_latency_s": (req.detection or {}).get("stt_latency_s"),
                            "cached": bool(result.get("cache_read_tokens"))})

    # ------------------------------------------------------------ background
    async def _tick(self) -> None:
        while self.running:
            await asyncio.sleep(1.0)
            el = self.elapsed()
            self.metrics.tick(el)
            self.emit("timer", {"elapsed": fmt_clock(el)})
            if int(el) % 5 == 0:
                self.emit("metrics", self.metrics.snapshot())
            if (self.engine.client is not None and not self.paused
                    and time.monotonic() - self._last_summary_mono >= self.summary_every
                    and (self._summary_task is None or self._summary_task.done())):
                cutoff = el - self.window_s
                older = [u for u in self.transcript.before(cutoff) if u.end > self._summarized_upto]
                if older:
                    self._last_summary_mono = time.monotonic()
                    self._summary_task = asyncio.create_task(self._refresh_summary(older))

    async def _refresh_summary(self, older: list[Utterance]) -> None:
        try:
            self._running_summary = await self.engine.update_summary(
                self._running_summary, self.transcript.text(older))
            self._summarized_upto = older[-1].end
        except Exception as e:
            log.info("running summary skipped: %s", type(e).__name__)
