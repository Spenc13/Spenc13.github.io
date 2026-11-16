"""Transcript model shared by live STT, replay, metrics, and the coach."""
from __future__ import annotations

import bisect
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
    # Backchannels from the other speaker during this turn: [(speaker, text)]
    asides: list = field(default_factory=list)
    typed: bool = False                  # Spencer typed this (ground truth)

    @property
    def words(self) -> int:
        return len(self.text.split())

    @property
    def end(self) -> float:
        return self.t + self.duration

    def line(self) -> str:
        who = "Spencer (typed)" if self.typed else LABELS[self.speaker]
        extra = "".join(f" [{LABELS[s]}: {t}]" for s, t in self.asides)
        return f"[{fmt_clock(self.t)}] {who}: {self.text}{extra}"

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("spoke_end_mono", None)
        return d


class Transcript:
    def __init__(self) -> None:
        self.finals: list[Utterance] = []

    def add(self, utt: Utterance) -> None:
        """Insert in audio-time order (the two streams' results can arrive out of order)."""
        keys = [u.t for u in self.finals]
        self.finals.insert(bisect.bisect_right(keys, utt.t), utt)

    def merge_target(self, speaker: str, start: float, max_gap: float = 12.0) -> Utterance | None:
        """The turn a new segment continues: the same speaker's latest turn before it,
        with no turn by the other speaker in between (typed notes don't count)."""
        for u in reversed(self.finals):
            if u.t > start or u.typed:
                continue
            if u.speaker != speaker:
                return None
            return u if start - u.end <= max_gap else None
        return None

    def since(self, call_seconds: float) -> list[Utterance]:
        return [u for u in self.finals if u.end >= call_seconds]

    def before(self, call_seconds: float) -> list[Utterance]:
        return [u for u in self.finals if u.end < call_seconds]

    def text(self, utts: list[Utterance] | None = None) -> str:
        return "\n".join(u.line() for u in (self.finals if utts is None else utts))

    def last_end(self) -> float:
        return self.finals[-1].end if self.finals else 0.0
