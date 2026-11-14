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
    cfg["coach"]["live_mode"] = False          # keyword-trigger mode
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
    s1.finalize(keep=True)
    s2 = CallStore(str(tmp_path), datetime(2026, 11, 11, 14, 30))
    s2.finalize(keep=True)

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


# ---------------------------------------------------------------- calls that go nowhere
def _t(lines):
    from coach.transcript import Transcript
    tr = Transcript()
    for sp, text, t in lines:
        tr.add(Utterance(sp, text, t, max(1.0, len(text.split()) / 2.7)))
    return tr


def test_call_filter():
    from coach.callfilter import judge
    real = _t([(REP, "Hi Dana, what got you looking at marketing?", 0),
               (PROSPECT, "Our leads have dried up and we need about six good kitchen jobs a month to keep both crews "
                          "booked through the winter, honestly we are worried", 4)])
    assert judge(real, 120).keep
    assert not judge(_t([]), 30).keep
    vm = judge(_t([(PROSPECT, "Hi, you've reached Mike's Roofing. Please leave a message after the tone.", 2),
                   (REP, "Hey Mike, Spencer with Olly Olly, give me a call back.", 8)]), 50)
    assert not vm.keep and vm.reason == "it reached voicemail"
    hangup = judge(_t([(PROSPECT, "Not interested, thanks.", 1)]), 20)
    assert not hangup.keep and "only said 3 words" in hangup.reason
    short = judge(real, 20)
    assert not short.keep and "20 seconds" in short.reason


def test_store_discard_and_keep(tmp_path):
    from coach.storage import CallStore, list_calls
    a = CallStore(str(tmp_path))
    a.log_coaching({"say": "x"})
    assert list_calls(str(tmp_path)) == []            # in-progress folders are hidden
    assert a.finalize(keep=False) is None
    assert list(tmp_path.iterdir()) == []             # nothing left behind
    b = CallStore(str(tmp_path))
    b.write_transcript("[00:00] Rep: hi")
    final = b.finalize(keep=True)
    assert final.name == b.name and (final / "transcript.txt").exists()
    assert [c["name"] for c in list_calls(str(tmp_path))] == [b.name]


def test_short_call_is_discarded_then_saved_anyway(tmp_path):
    script = tmp_path / "hangup.txt"
    script.write_text("Rep: Hey Mike, it's Spencer with Olly Olly.\nProspect: Not interested, thanks.\n")
    cfg = load_config()
    cfg["storage"]["calls_dir"] = str(tmp_path / "calls")
    cfg["replay"]["speed"] = 40
    events = []

    async def run():
        s = CallSession(cfg, PROMPTS, lambda k, d: events.append((k, d)), "replay_text", str(script))
        s.engine.client = _FakeClient(REPLY)
        await s.start()
        await asyncio.wait_for(s.wait_ended(), timeout=30)
        assert not (tmp_path / "calls").exists() or not any(
            p for p in (tmp_path / "calls").iterdir() if not p.name.startswith("."))
        assert s.engine.client.messages.calls == [] or all("Return: a 2-sentence" not in str(c) for c in s.engine.client.messages.calls)
        await s.save_anyway()
        return s

    s = asyncio.run(run())
    disc = [d for k, d in events if k == "summary" and d.get("state") == "discarded"]
    assert disc and "only said 3 words" in disc[0]["reason"]
    saved = [d for k, d in events if k == "summary" and d.get("state") == "done"]
    assert saved, "save anyway should write the call and summarize it"
    folder = Path(saved[0]["dir"])
    assert {p.name for p in folder.iterdir()} >= {"transcript.txt", "metrics.json", "summary.md", "coaching.jsonl"}


# ---------------------------------------------------------------- dialer link
def test_phone_bridge_security_and_events():
    import socket
    import urllib.request
    from coach.phone_bridge import PhoneBridge

    with socket.socket() as sk:
        sk.bind(("127.0.0.1", 0))
        port = sk.getsockname()[1]
    got = []
    br = PhoneBridge(port, got.append)
    assert br.start()
    try:
        def post(body, origin="chrome-extension://abc", header=True, method="POST"):
            req = urllib.request.Request(f"http://127.0.0.1:{port}/phone", data=json.dumps(body).encode(), method=method)
            req.add_header("Content-Type", "application/json")
            if origin:
                req.add_header("Origin", origin)
            if header:
                req.add_header("X-Olly-Coach", "1")
            try:
                return urllib.request.urlopen(req, timeout=5).status
            except urllib.error.HTTPError as e:
                return e.code

        assert post({"event": "answered", "phone": "+15125550123", "callId": "c1", "junk": "x" * 999}) == 200
        assert post({"event": "answered"}, origin="https://evil.example") == 403      # web pages can't
        assert post({"event": "answered"}, header=False) == 403
        assert post({"event": "explode"}) == 400
        assert post({"event": "seen", "type": "callDisposition"}) == 200              # logged, not forwarded
        assert post({}, method="OPTIONS") == 403
        assert got == [{"event": "answered", "phone": "+15125550123", "callId": "c1"}]
    finally:
        br.stop()


# ---------------------------------------------------------------- live coach (parrot mode)
def test_said_it():
    from coach.engine import said_it
    line = "What would one extra kitchen job a month be worth to your business?"
    assert said_it(line, "So what would one extra kitchen job a month be worth to the business")
    assert not said_it(line, "Totally, I hear you on that.")
    assert not said_it("(Stay quiet. Let them finish.)", "stay quiet let them finish")


def test_live_mode_coaches_every_prospect_turn(tmp_path):
    cfg = load_config()
    cfg["storage"]["calls_dir"] = str(tmp_path)
    cfg["replay"]["speed"] = 12
    cfg["coach"]["live_mode"] = True
    events = []

    async def run():
        s = CallSession(cfg, PROMPTS, lambda k, d: events.append((k, d)), "replay_text",
                        str(ROOT / "samples" / "pool_burned_by_agency.txt"))
        s.engine.client = _FakeClient(REPLY)
        await s.start()
        await asyncio.wait_for(s.wait_ended(), timeout=60)
        return s

    s = asyncio.run(run())
    calls = [c for c in s.engine.client.messages.calls if "messages" in c and "stream" not in c]
    live = [c for c in calls if "Live coach mode" in c["messages"][0]["content"]]
    prospect_turns = [u for u in s.transcript.finals if u.speaker == PROSPECT and len(u.text.split()) >= 3]
    assert len(live) >= len(prospect_turns) - 1, (len(live), len(prospect_turns))
    first = live[0]
    assert first["thinking"] == {"type": "between_tools"} and first["output_config"]["effort"] == "low"
    assert 'The prospect just finished saying: "I\'ll be honest with you' in first["messages"][0]["content"]
    done = [d for k, d in events if k == "coach" and d.get("state") == "done"]
    assert done and all(d.get("live") for d in done)


# ---------------------------------------------------------------- speaker hygiene
def _live_session(events):
    import time as _time
    from coach.stt.base import SttEvent
    cfg = load_config()
    cfg["coach"]["live_mode"] = False
    cfg["audio"]["echo_hold_ms"] = 60
    s = CallSession(cfg, PROMPTS, lambda k, d: events.append((k, d)), "live")
    s.running = True
    s._resume_mono = _time.monotonic()

    def ev(sp, text, t, final=True, speech_final=True):
        return SttEvent(sp, text, final, t, len(text.split()) / 2.7, _time.monotonic(), speech_final)
    return s, ev


def test_echo_of_rep_is_not_labeled_prospect():
    events = []

    async def run():
        s, ev = _live_session(events)
        line = "So what would one extra kitchen job a month be worth to you"
        await s.on_stt(ev(REP, line, 1))
        await s.on_stt(ev(PROSPECT, "what would one extra kitchen job a month be worth to you", 1.2))   # sidetone
        # Echo that lands before Spencer's own final: he's mid-sentence (partial only).
        await s.on_stt(ev(REP, "Does that make sense for", 6, final=False))
        await asyncio.gather(
            s.on_stt(ev(PROSPECT, "Does that make sense for your crews", 6.1)),
            s.on_stt(ev(REP, "Does that make sense for your crews", 6, final=True)),
        )
        s._rep_active_mono = 0                       # Spencer has gone quiet
        await s.on_stt(ev(PROSPECT, "Honestly we need about six more jobs a month", 9))
        await s.on_stt(ev(REP, "What happens if that doesn't change", 12))
        await s.on_stt(ev(PROSPECT, "Yeah it would be worth a lot to us", 12.3))   # real reply while he talks
        return s

    s = asyncio.run(run())
    who = [(u.speaker, u.text) for u in s.transcript.finals]
    assert (PROSPECT, "what would one extra kitchen job a month be worth to you") not in who
    assert (PROSPECT, "Does that make sense for your crews") not in who
    assert (PROSPECT, "Honestly we need about six more jobs a month") in who
    assert (PROSPECT, "Yeah it would be worth a lot to us") in who
    assert s.echo_dropped == 2


def test_swap_speakers_relabels_past_and_future():
    events = []

    async def run():
        s, ev = _live_session(events)
        await s.on_stt(ev(PROSPECT, "Hey Luis, Spencer with Olly Olly. What made you take the call?", 0))
        s._rep_active_mono = 0
        await s.on_stt(ev(REP, "We tried an agency and it was a waste of money.", 5))
        s.swap_speakers()
        await s.on_stt(ev(PROSPECT, "It sounds like you got burned before.", 9))   # mic stream, still reversed
        return s

    s = asyncio.run(run())
    assert [u.speaker for u in s.transcript.finals] == [REP, PROSPECT, REP]
    assert s.metrics.questions == 1 and s.metrics.rep_words > 0
    assert any(k == "transcript_reset" for k, _ in events)


# ---------------------------------------------------------------- joined mid-call
def test_joined_mid_call_is_marked_everywhere(tmp_path):
    cfg = load_config()
    cfg["storage"]["calls_dir"] = str(tmp_path)
    cfg["replay"]["speed"] = 40
    cfg["coach"]["live_mode"] = True

    async def run():
        s = CallSession(cfg, PROMPTS, lambda k, d: None, "replay_text",
                        str(ROOT / "samples" / "remodeler_too_expensive.txt"))
        s.engine.client = _FakeClient(REPLY)
        s.mark_joined_mid_call(130)
        await s.start()
        await asyncio.wait_for(s.wait_ended(), timeout=60)
        return s

    s = asyncio.run(run())
    contents = [c["messages"][0]["content"] for c in s.engine.client.messages.calls]
    assert any("coaching started about 02:10 into the call" in c for c in contents if "Live coach mode" in c)
    assert any("coaching started about 02:10" in c and "The call has ended" in c for c in contents)
    metrics = json.loads((Path(s.store.dir) / "metrics.json").read_text())
    assert metrics["partial_call"] is True and metrics["joined_after_seconds"] == 130
    assert metrics["meta"]["joined_mid_call_after"] == "02:10"


# ---------------------------------------------------------------- Google Meet
def test_warns_when_other_side_is_silent():
    events = []

    async def run():
        s, _ = _live_session(events)
        s._loopback_name = "Speakers (Realtek Audio)"
        s.elapsed = lambda: 30.0
        s._levels = {REP: 0.2, PROSPECT: 0.0}
        task = asyncio.create_task(s._level_loop())
        await asyncio.sleep(0.6)
        s.running = False
        await asyncio.sleep(0.3)
        task.cancel()

    asyncio.run(run())
    toasts = [d["text"] for k, d in events if k == "toast"]
    assert any("Not hearing the other side" in t and "Realtek" in t for t in toasts)
    assert len([t for t in toasts if "Not hearing" in t]) == 1        # warns once


def test_call_labels():
    from coach.desktop import call_label
    assert call_label({"phone": "+15125550123"}) == "(512) 555-0123"
    assert call_label({"source": "meet", "contact": "Mike's Roofing", "callId": "abc-defg-hij"}) == "Google Meet · Mike's Roofing"
    assert call_label({"source": "meet", "callId": "abc-defg-hij"}) == "Google Meet (abc-defg-hij)"
