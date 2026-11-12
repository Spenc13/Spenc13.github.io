"""Speech-to-text providers.

A provider takes raw 16-bit PCM chunks for one speaker and calls back with
partial and final phrases. To add a provider (for example Wispr Flow, if it
offers a streaming API you have access to), subclass SpeechStream and register
it in make_stream().
"""
from __future__ import annotations

from .base import SpeechStream, SttEvent


def make_stream(provider: str, **kwargs) -> SpeechStream:
    if provider == "deepgram":
        from .deepgram import DeepgramStream

        return DeepgramStream(**kwargs)
    raise ValueError(f"Unknown STT provider: {provider!r}")


__all__ = ["SpeechStream", "SttEvent", "make_stream"]
