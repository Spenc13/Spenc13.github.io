"""Deepgram live streaming STT over a raw WebSocket.

One connection per audio source (mic = Rep, loopback = Prospect), so speaker
labels come from the source, not from guessing. For a stereo WAV in replay mode
we use multichannel (left = Rep, right = Prospect). For a mono WAV we turn on
diarization and map Deepgram speaker 0/1 to Rep/Prospect.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from collections import Counter
from urllib.parse import urlencode

from .base import SpeechStream, SttEvent

log = logging.getLogger(__name__)

URL = "wss://api.deepgram.com/v1/listen"


class DeepgramStream(SpeechStream):
    def __init__(self, *args, channel_speakers: list[str] | None = None,
                 diarize_map: dict[int, str] | None = None, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.channel_speakers = channel_speakers      # stereo: ["rep", "prospect"]
        self.diarize_map = diarize_map                # mono diarized: {0: "rep", 1: "prospect"}
        self._closing = False
        self._conn_base = 0.0                         # stream audio-seconds at connection open
        self._last_send = time.monotonic()
        self.connected = asyncio.Event()

    def _params(self) -> str:
        o = self.options
        params: list[tuple[str, str]] = [
            ("model", o.get("model", "nova-3")),
            ("language", o.get("language", "en-US")),
            ("encoding", "linear16"),
            ("sample_rate", str(self.sample_rate)),
            ("channels", str(self.channels)),
            ("interim_results", "true"),
            ("punctuate", "true"),
            ("smart_format", "true"),
            ("endpointing", str(o.get("endpointing_ms", 300))),
            ("utterance_end_ms", str(o.get("utterance_end_ms", 1000))),
            ("vad_events", "true"),
        ]
        if self.channels > 1:
            params.append(("multichannel", "true"))
        if self.diarize_map:
            params.append(("diarize", "true"))
        if str(o.get("model", "nova-3")).startswith("nova-3"):
            for term in o.get("keyterms") or []:
                params.append(("keyterm", term))
        return URL + "?" + urlencode(params)

    async def run(self) -> None:
        import websockets

        key = os.environ.get("DEEPGRAM_API_KEY")
        if not key:
            await self.on_status("down", "Deepgram key missing (set DEEPGRAM_API_KEY)")
            return
        backoff = 1.0
        while not self._closing:
            try:
                async with websockets.connect(
                    self._params(),
                    additional_headers={"Authorization": f"Token {key}"},
                    ping_interval=10,
                    max_size=2**22,
                ) as ws:
                    # Drop stale audio buffered while disconnected.
                    while not self.queue.empty():
                        self.queue.get_nowait()
                    self._conn_base = self._audio_sent
                    self.connected.set()
                    backoff = 1.0
                    await self.on_status("ok", "Transcribing")
                    sender = asyncio.create_task(self._send_loop(ws))
                    try:
                        async for raw in ws:
                            await self._handle(raw)
                    finally:
                        sender.cancel()
                if self._closing:
                    return
                await self.on_status("down", "Speech-to-text disconnected, reconnecting")
            except asyncio.CancelledError:
                raise
            except Exception as e:  # network, auth, DNS...
                self.connected.clear()
                msg = str(e)
                if "401" in msg or "403" in msg:
                    await self.on_status("down", "Deepgram rejected the API key")
                    return
                await self.on_status("down", f"Speech-to-text unavailable, retrying ({type(e).__name__})")
                log.warning("Deepgram %s stream error: %s", self.speaker, type(e).__name__)
            if self._closing:
                return
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 15)

    async def _send_loop(self, ws) -> None:
        while True:
            try:
                chunk = await asyncio.wait_for(self.queue.get(), timeout=4.0)
            except asyncio.TimeoutError:
                await ws.send(json.dumps({"type": "KeepAlive"}))   # paused / silent
                continue
            if chunk is None:
                self._closing = True
                await ws.send(json.dumps({"type": "CloseStream"}))
                return
            await ws.send(chunk)

    async def _handle(self, raw) -> None:
        if isinstance(raw, bytes):
            return
        msg = json.loads(raw)
        if msg.get("type") != "Results":
            return
        alt = (msg.get("channel") or {}).get("alternatives") or [{}]
        alt = alt[0]
        text = (alt.get("transcript") or "").strip()
        if not text:
            return
        start = float(msg.get("start", 0.0))
        duration = float(msg.get("duration", 0.0))
        words = alt.get("words") or []
        if words:
            start = float(words[0].get("start", start))
            duration = max(0.0, float(words[-1].get("end", start + duration)) - start)
        speaker = self.speaker
        if self.channel_speakers:
            idx = (msg.get("channel_index") or [0])[0]
            if idx < len(self.channel_speakers):
                speaker = self.channel_speakers[idx]
        elif self.diarize_map and words:
            top = Counter(w.get("speaker", 0) for w in words).most_common(1)[0][0]
            speaker = self.diarize_map.get(int(top), self.speaker)
        stream_end = self._conn_base + start + duration
        await self.on_event(SttEvent(
            speaker=speaker,
            text=text,
            final=bool(msg.get("is_final")),
            start=self._conn_base + start,
            duration=duration,
            spoke_end_mono=self.wall_at(stream_end),
            speech_final=bool(msg.get("speech_final")),
        ))

    async def close(self) -> None:
        self._closing = True
        await self.queue.put(None)
