"""Offline tests: no API keys, no audio devices, no network."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from coach.config import Prompts, _instructions_body, load_config  # noqa: E402
from coach.engine import CoachEngine, parse_coach  # noqa: E402
from coach.metrics import Metrics, count_questions  # noqa: E402
from coach.replay import parse_script  # noqa: E402
from coach.session import CallSession  # noqa: E402
from coach.transcript import PROSPECT, REP, Utterance  # noqa: E402
from coach.triggers import BUYING, OBJECTION, Debouncer, detect  # noqa: E402

PROMPTS = Prompts(instructions="INSTRUCTIONS VERBATIM", playbook="PLAYBOOK", offer="OFFER")


# ---------------------------------------------------------------- parsing
def test_parse_three_part_reply():
    text = ("Say this next: What specifically do you want to see?\n"
            "Tactic: Miner: qualify before you send\n"
            "Watch-out: Don't send a generic deck.")
    p = parse_coach(text)
    assert p["say"] == "What specifically do you want to see?"
    assert p["tactic"] == "Miner: qualify before you send"
    assert p["watch"] == "Don't send a generic deck."


def test_parse_numbered_bold_and_partial():
    p = parse_coach("1. **Say this next:** \"What would one extra roof be worth?\"\n2. **Tactic:** Hormozi: val")
    assert p["say"].startswith('"What would one extra roof')
    assert p["tactic"] == "Hormozi: val"
    assert p["watch"] == ""
    assert parse_coach("Just plain advice")["say"] == "Just plain advice"


def test_instructions_body_uses_text_below_the_line():
    raw = "# Title\n\nPaste everything below the line.\n\n-----\n\nYou are a live sales coach."
    assert _instructions_body(raw) == "You are a live sales coach."


# ---------------------------------------------------------------- triggers
@pytest.mark.parametrize("line,key,kind", [
    ("Can you just send me something and I'll take a look?", "send_info", OBJECTION),
    ("Seven fifty a month? That's too expensive for us.", "price", OBJECTION),
    ("We tried an agency two years ago and it was a waste of money.", "burned", OBJECTION),
    ("I'll need to run it by my husband anyway.", "decision_maker", OBJECTION),
    ("Can I just do it month to month?", "contract", OBJECTION),
    ("When can you start?", "timeline_q", BUYING),
    ("So how much does it cost?", "price_q", BUYING),
    ("Who else in pools do you work with?", "social_proof_q", BUYING),
])
def test_detect(line, key, kind):
    d = detect(line)
    assert d is not None and d.key == key and d.kind == kind


def test_no_trigger_on_small_talk():
    assert detect("Yeah, the weather's been great for roofing this week.") is None
    assert detect("Someone with a budget over forty grand who's ready in three months.") is None


def test_debouncer():
    deb = Debouncer(min_gap=8, same_kind_cooldown=45)
    send = detect("send me something")
    price = detect("that's too expensive")
    assert deb.should_fire(send, 10)
    assert not deb.should_fire(price, 14)          # inside min gap
    assert deb.should_fire(price, 19)
    assert not deb.should_fire(send, 40)           # same kind within cooldown
    assert deb.should_fire(send, 60)


# ---------------------------------------------------------------- metrics
def test_question_counting():
    assert count_questions("What got you looking? How long has that been going on?") == (2, 2)
    assert count_questions("Is that right? Great.") == (1, 0)
    assert count_questions("how are calls coming in right now") == (1, 1)   # no punctuation


def test_metrics_from_transcript():
    m = Metrics()
    m.add_utterance(Utterance(REP, "What made you take the call today?", 0, 3))
    m.add_utterance(Utterance(PROSPECT, "The phone's not ringing like it used to and I'm worried about it.", 3, 5))
    m.add_objection("price", "Too expensive", 10)
    m.add_utterance(Utterance(REP, "What would one extra job a month be worth to you?", 12, 3))
    m.add_utterance(Utterance(REP, "Let's book a follow-up call Thursday at 10am.", 40, 3))
    m.add_utterance(Utterance(PROSPECT, "Sure, that works.", 44, 1))
    s = m.snapshot()
    assert s["questions"] == 2 and s["open_questions"] == 2
    assert s["objection_count"] == 1
    assert s["objections"][0]["handled"] is True
    assert s["next_step"] == {"asked": True, "specific": True, "agreed": True}
    assert s["scores"]["Next-step clarity"] == 100
    assert s["rep_share_pct"] == round(100 * 9 / 15)


def test_scores_are_none_until_there_is_data():
    m = Metrics()
    assert all(v is None for v in m.scores().values())
    assert m.overall() is None


def test_unanswered_objection_counts_against():
    m = Metrics()
    m.add_objection("price", "Too expensive", 5)
    m.add_utterance(Utterance(REP, "We could probably do month to month.", 7, 2))
    assert m.scores()["Objection handling"] is None      # still inside the 30 s window
    m.tick(40)
    assert m.scores()["Objection handling"] == 0


def test_voss_label_counts_as_handled():
    m = Metrics()
    m.add_objection("burned", "Burned by a past agency", 5)
    m.add_utterance(Utterance(REP, "It sounds like you got burned before.", 8, 2))
    assert m.objections[0].handled is True


# ---------------------------------------------------------------- engine request shape
class _FakeStream:
    def __init__(self, text):
        self.text = text

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    @property
    def text_stream(self):
        async def gen():
            for i in range(0, len(self.text), 7):
                await asyncio.sleep(0)
                yield self.text[i:i + 7]
        return gen()

    async def get_final_message(self):
        class U:
            cache_read_input_tokens = 3200
            cache_creation_input_tokens = 0
            input_tokens = 400
            output_tokens = 60

        class M:
            stop_reason = "end_turn"
            model = "claude-sonnet-5-5"
            usage = U()
        return M()


class _FakeMessages:
    def __init__(self, reply):
        self.reply = reply
        self.calls = []

    def stream(self, **kw):
        self.calls.append(kw)
        return _FakeStream(self.reply)

    async def create(self, **kw):
        self.calls.append(kw)

        class B:
            type = "text"
            text = json.dumps({"overview": "Solid discovery, weak close.", "key_wins": ["Asked consequence question"],
                               "missed_opportunities": ["Offered month-to-month too early"],
                               "next_steps": ["Book a call with Dana and her husband"]})

        class M:
            stop_reason = "end_turn"
            content = [B()]
        return M()


class _FakeClient:
    def __init__(self, reply):
        self.messages = _FakeMessages(reply)

        class Beta:
            pass
        self.beta = Beta()
        self.beta.messages = self.messages


REPLY = ("Say this next: What would one extra kitchen a month be worth to you?\n"
         "Tactic: Hormozi: value equation, then the payment waterfall\n"
         "Watch-out: Don't offer month-to-month before the waterfall.")


def test_request_uses_cache_and_verbatim_instructions():
    cfg = load_config()
    eng = CoachEngine(cfg, PROMPTS, api_key_present=False)
    eng.client = _FakeClient(REPLY)
    seen = []
    out = asyncio.run(eng.stream_coaching("hello", lambda t: seen.append(t)))
    kw = eng.client.messages.calls[0]
    assert kw["model"] == "claude-sonnet-5-5"
    assert kw["system"][0]["text"] == "INSTRUCTIONS VERBATIM"
    assert "cache_control" not in kw["system"][0]
    assert kw["system"][-1]["cache_control"] == {"type": "ephemeral"}
    assert "PLAYBOOK" in kw["system"][1]["text"] and "OFFER" in kw["system"][2]["text"]
    assert kw["output_config"]["effort"] == "low"
    assert kw["fallbacks"] == "default" and kw["betas"] == ["server-side-fallback-2026-07-01"]
    assert out["text"] == REPLY and len(seen) > 3
    assert out["cache_read_tokens"] == 3200


# ---------------------------------------------------------------- full pipeline
def test_replay_pipeline_saves_call(tmp_path):
    cfg = load_config()
    cfg["storage"]["calls_dir"] = str(tmp_path)
    cfg["replay"]["speed"] = 40
    cfg["triggers"]["min_gap_seconds"] = 5
    events = []

    def emit(kind, data):
        events.append((kind, data))

    async def run():
        s = CallSession(cfg, PROMPTS, emit, "replay_text", str(ROOT / "samples" / "remodeler_too_expensive.txt"))
        s.engine.client = _FakeClient(REPLY)
        await s.start()
        await asyncio.wait_for(s.wait_ended(), timeout=60)
        return s

    s = asyncio.run(run())
    call_dir = Path(s.store.dir)
    assert {p.name for p in call_dir.iterdir()} >= {"transcript.txt", "coaching.jsonl", "metrics.json", "summary.md"}
    transcript = (call_dir / "transcript.txt").read_text()
    assert "Prospect: Seven fifty a month?" in transcript and "Rep: Hi Dana" in transcript
    coaching = [json.loads(line) for line in (call_dir / "coaching.jsonl").read_text().splitlines()]
    assert coaching, "auto triggers should have produced coaching"
    first = coaching[0]
    assert first["reason"] == "auto" and first["say"].startswith("What would one extra kitchen")
    assert first["latency_s"] >= 0 and "timestamp" in first
    metrics = json.loads((call_dir / "metrics.json").read_text())
    assert metrics["objection_count"] >= 2 and metrics["questions"] >= 3
    assert metrics["meta"]["consent_confirmed"] is True
    summary = (call_dir / "summary.md").read_text()
    assert "Offered month-to-month too early" in summary
    kinds = {k for k, _ in events}
    assert {"line", "signal", "coach", "metrics", "summary", "timer"} <= kinds
    done = [d for k, d in events if k == "summary" and d.get("state") == "done"]
    assert done and done[0]["summary"]["next_steps"]
    # The coach request carried the recent transcript, not just the trigger line.
    user = s.engine.client.messages.calls[0]["messages"][0]["content"]
    assert "Recent transcript:" in user and "Rep: Hi Dana" in user


def test_script_parser():
    lines = parse_script("# c\nRep: Hi\nProspect: Hello\n[pause 2]\nrep: ok")
    assert [(l.speaker, l.text, l.pause) for l in lines] == [
        ("rep", "Hi", 0), ("prospect", "Hello", 0), (None, "", 2.0), ("rep", "ok", 0)]


# ---------------------------------------------------------------- past calls browser
def test_list_and_load_calls(tmp_path):
    from coach.storage import CallStore, call_path, list_calls, load_call
    from datetime import datetime

    s1 = CallStore(str(tmp_path), datetime(2026, 11, 10, 9, 5))
    s1.write_transcript("[00:01] Rep: Hi")
    s1.write_metrics({"meta": {"title": "Live call", "started": "2026-11-10T09:05:00", "length": "12:00"},
                      "overall": 81, "objection_count": 2, "questions": 9})
    s1.log_coaching({"question": "Too expensive", "say": "What's one extra job worth?", "latency_s": 1.9})
    s1.write_summary({"overview": "Good call.", "key_wins": ["a"], "missed_opportunities": [], "next_steps": ["b"]},
                     {"title": "Live call"})
    s1.close()
    s2 = CallStore(str(tmp_path), datetime(2026, 11, 11, 14, 30))
    s2.close()

    calls = list_calls(str(tmp_path))
    assert [c["name"] for c in calls] == ["2026-11-11_14-30", "2026-11-10_09-05"]     # newest first
    assert calls[1]["overall"] == 81 and calls[1]["has_summary"] and calls[1]["length"] == "12:00"
    d = load_call(str(tmp_path), "2026-11-10_09-05")
    assert "Good call." in d["summary_md"] and d["transcript"].startswith("[00:01]")
    assert d["coaching"][0]["say"] == "What's one extra job worth?"
    # Names can't escape the calls folder.
    for bad in ("..", "../..", "..\\x", "/etc", ".hidden", ""):
        assert call_path(str(tmp_path), bad) is None
        assert load_call(str(tmp_path), bad) is None
