"""Transcript model shared by live STT, replay, metrics, and the coach."""
from __future__ import annotations

import itertools
import time
from dataclasses import dataclass, field, asdict

REP = "rep"
PROSPECT = "prospect"
LABELS = {REP: "Rep", PROSPECT: "Prospect"}

_ids = itertools.count(1)


def fmt_clock(seconds: float) -> str:
    seconds = max(0, int(seconds))
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


@dataclass
class Utterance:
    speaker: str                 # "rep" | "prospect"
    text: str
    t: float                     # call-relative seconds when the phrase started
    duration: float              # seconds of speech (from STT word timings, or estimated)
    final: bool = True
    # time.monotonic() when the speaker stopped talking (for latency measurement)
    spoke_end_mono: float = field(default_factory=time.monotonic)
    id: int = field(default_factory=lambda: next(_ids))

    @property
    def words(self) -> int:
        return len(self.text.split())

    @property
    def end(self) -> float:
        return self.t + self.duration

    def line(self) -> str:
        return f"[{fmt_clock(self.t)}] {LABELS[self.speaker]}: {self.text}"

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("spoke_end_mono", None)
        return d


class Transcript:
    def __init__(self) -> None:
        self.finals: list[Utterance] = []

    def add(self, utt: Utterance) -> None:
        self.finals.append(utt)

    def since(self, call_seconds: float) -> list[Utterance]:
        return [u for u in self.finals if u.end >= call_seconds]

    def before(self, call_seconds: float) -> list[Utterance]:
        return [u for u in self.finals if u.end < call_seconds]

    def text(self, utts: list[Utterance] | None = None) -> str:
        return "\n".join(u.line() for u in (self.finals if utts is None else utts))

    def last_end(self) -> float:
        return self.finals[-1].end if self.finals else 0.0
