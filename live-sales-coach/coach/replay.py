"""Replay mode: feed a text script or a WAV file through the same pipeline as a live call.

Text script format (one turn per line):

    # Any line starting with # is a comment
    Rep: Hey Mike, thanks for making time.
    Prospect: Send me something and I'll look at it.
    [pause 2.5]

WAV files: stereo = left channel Rep, right channel Prospect (exact labels).
Mono = Deepgram diarization; the first voice heard is assumed to be the Rep.
WAV replay needs DEEPGRAM_API_KEY; text replay needs no STT at all.
"""
from __future__ import annotations

import asyncio
import re
import time
import wave
from dataclasses import dataclass
from pathlib import Path

from .stt.base import EventCallback, SttEvent
from .transcript import PROSPECT, REP

_TURN = re.compile(r"^\s*(rep|prospect|spencer|owner|customer)\s*:\s*(.+)$", re.I)
_PAUSE = re.compile(r"^\s*\[pause\s+([\d.]+)\s*\]\s*$", re.I)
_SPEAKER = {"rep": REP, "spencer": REP, "prospect": PROSPECT, "owner": PROSPECT, "customer": PROSPECT}


@dataclass
class ScriptLine:
    speaker: str | None    # None = pause
    text: str = ""
    pause: float = 0.0


def parse_script(text: str) -> list[ScriptLine]:
    out: list[ScriptLine] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = _PAUSE.match(line)
        if m:
            out.append(ScriptLine(None, pause=float(m.group(1))))
            continue
        m = _TURN.match(line)
        if m:
            out.append(ScriptLine(_SPEAKER[m.group(1).lower()], m.group(2).strip()))
        elif out and out[-1].speaker:
            out[-1].text += " " + line          # continuation line
    return out


def script_title(text: str, fallback: str) -> str:
    for raw in text.splitlines():
        m = re.match(r"^\s*#\s*title\s*:\s*(.+)$", raw, re.I)
        if m:
            return m.group(1).strip()
    return fallback


class TextReplay:
    """Plays a script in real time, emitting partials word by word, then a final."""

    def __init__(self, path: Path, on_event: EventCallback, wpm: float = 165, speed: float = 1.0,
                 turn_gap: float = 0.7) -> None:
        self.path = Path(path)
        self.lines = parse_script(self.path.read_text(encoding="utf-8"))
        self.title = script_title(self.path.read_text(encoding="utf-8"), self.path.stem)
        self.on_event = on_event
        self.wps = wpm / 60.0
        self.speed = max(0.1, speed)
        self.turn_gap = turn_gap
        self.paused = asyncio.Event()
        self.paused.set()            # set = running
        self._clock = 0.0            # simulated audio seconds

    async def _sleep(self, seconds: float) -> None:
        remaining = seconds / self.speed
        while remaining > 0:
            await self.paused.wait()
            step = min(0.05, remaining)
            await asyncio.sleep(step)
            remaining -= step

    async def run(self) -> None:
        for line in self.lines:
            if line.speaker is None:
                await self._sleep(line.pause)
                self._clock += line.pause
                continue
            words = line.text.split()
            start = self._clock
            per_word = 1.0 / self.wps
            for i in range(1, len(words) + 1):
                await self._sleep(per_word)
                if i < len(words) and i % 3 == 0:
                    await self.on_event(SttEvent(
                        speaker=line.speaker, text=" ".join(words[:i]), final=False,
                        start=start, duration=i * per_word, spoke_end_mono=time.monotonic(),
                    ))
            duration = len(words) * per_word
            self._clock = start + duration
            await self.on_event(SttEvent(
                speaker=line.speaker, text=line.text, final=True, start=start, duration=duration,
                spoke_end_mono=time.monotonic(), speech_final=True,
            ))
            await self._sleep(self.turn_gap)
            self._clock += self.turn_gap


class WavReplay:
    """Streams a WAV file to Deepgram in real time, as if it were live audio."""

    def __init__(self, path: Path, make_stream, chunk_ms: int = 100, speed: float = 1.0) -> None:
        self.path = Path(path)
        self.title = self.path.stem
        self.make_stream = make_stream   # (channels, rate, channel_speakers, diarize_map) -> SpeechStream
        self.chunk_ms = chunk_ms
        self.speed = max(0.5, min(speed, 2.0))   # Deepgram expects roughly real time
        self.paused = asyncio.Event()
        self.paused.set()
        self.stream = None

    async def run(self) -> None:
        with wave.open(str(self.path), "rb") as wf:
            if wf.getsampwidth() != 2:
                raise ValueError("WAV must be 16-bit PCM")
            channels, rate = wf.getnchannels(), wf.getframerate()
            if channels > 2:
                raise ValueError("WAV must be mono or stereo")
            if channels == 2:
                self.stream = self.make_stream(2, rate, [REP, PROSPECT], None)
            else:
                self.stream = self.make_stream(1, rate, None, {0: REP, 1: PROSPECT})
            runner = asyncio.create_task(self.stream.run())
            try:
                await asyncio.wait_for(self.stream.connected.wait(), timeout=15)
            except asyncio.TimeoutError:
                runner.cancel()
                raise RuntimeError("Could not connect to Deepgram for WAV replay")
            self.stream.set_paused(False)
            frames = int(rate * self.chunk_ms / 1000)
            while True:
                await self.paused.wait()
                data = wf.readframes(frames)
                if not data:
                    break
                self.stream.feed(data)
                await asyncio.sleep(self.chunk_ms / 1000 / self.speed)
            await asyncio.sleep(2.0)        # let the last finals arrive
            await self.stream.close()
            try:
                await asyncio.wait_for(runner, timeout=10)
            except asyncio.TimeoutError:
                runner.cancel()
