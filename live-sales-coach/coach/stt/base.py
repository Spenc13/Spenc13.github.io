from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Awaitable, Callable


@dataclass
class SttEvent:
    speaker: str            # "rep" | "prospect"
    text: str
    final: bool             # False = partial (still changing)
    start: float            # seconds into this stream's audio
    duration: float
    spoke_end_mono: float   # time.monotonic() when this phrase's audio ended
    speech_final: bool = False  # True when the speaker paused (end of turn)


EventCallback = Callable[[SttEvent], Awaitable[None]]
StatusCallback = Callable[[str, str], Awaitable[None]]   # (state, message)


class SpeechStream:
    """One streaming STT connection for one speaker."""

    def __init__(self, speaker: str, sample_rate: int, on_event: EventCallback,
                 on_status: StatusCallback, channels: int = 1, **options) -> None:
        self.speaker = speaker
        self.sample_rate = sample_rate
        self.channels = channels
        self.on_event = on_event
        self.on_status = on_status
        self.options = options
        self.queue: asyncio.Queue[bytes | None] = asyncio.Queue(maxsize=400)
        # Map audio-seconds to wall time so we know when a phrase actually ended,
        # even across pauses: list of (audio_seconds_at_segment_start, monotonic).
        self._segments: list[tuple[float, float]] = []
        self._audio_sent = 0.0
        self._paused = True
        self._resumed = True

    def feed(self, pcm: bytes) -> None:
        """Called on the event loop (the audio thread hands chunks over with
        loop.call_soon_threadsafe)."""
        if self._paused:
            return
        dur = len(pcm) / (2 * self.channels * self.sample_rate)
        if self._resumed:
            # First chunk after start/resume. Its audio began `dur` seconds ago.
            self._segments.append((self._audio_sent, time.monotonic() - dur))
            self._resumed = False
        self._audio_sent += dur
        try:
            self.queue.put_nowait(pcm)
        except asyncio.QueueFull:
            pass  # STT is down or slow; drop audio rather than block the mic

    def set_paused(self, paused: bool) -> None:
        if self._paused and not paused:
            self._resumed = True
        self._paused = paused

    def wall_at(self, audio_seconds: float) -> float:
        if not self._segments:
            return time.monotonic()
        seg = self._segments[0]
        for s in self._segments:
            if s[0] <= audio_seconds:
                seg = s
            else:
                break
        return seg[1] + (audio_seconds - seg[0])

    async def run(self) -> None:  # pragma: no cover - provider specific
        raise NotImplementedError

    async def close(self) -> None:
        await self.queue.put(None)
