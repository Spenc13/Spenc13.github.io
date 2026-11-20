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
    assert count_questions("Is that right? Great.") == (0, 0)                 # tag question: not discovery
    assert count_questions("Do you handle the marketing yourself? Right?") == (1, 0)
    assert count_questions("how are calls coming in right now") == (1, 1)   # no punctuation
    assert count_questions("Make sense?") == (0, 0)


def test_metrics_from_transcript():
    m = Metrics()
    m.add_utterance(Utterance(REP, "What made you take the call today?", 0, 3))
    m.add_utterance(Utterance(PROSPECT, "The phone's not ringing like it used to and I'm worried about it.", 3, 5))
    m.add_objection("price", "Too expensive", 10)
    m.add_utterance(Utterance(REP, "What would one extra job a month be worth to you?", 12, 3))
    m.mark_card_for_objection("price", 11)                 # a coach card responded
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


def test_voss_label_counts_as_handled_when_coaching_is_off():
    m = Metrics(cards_mark_handled=False)
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
    cfg["call_filter"]["min_minutes"] = 0      # this test checks saving, not the keep rule
    cfg["call_filter"]["auto_save_minutes"] = 0
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
    talk = _t([(REP, "Hi Dana, what got you looking at marketing?", 0),
               (PROSPECT, "Our leads have dried up and we need about six good kitchen jobs a month.", 4)])
    short = judge(talk, 90)                                    # under 2 minutes, nothing set
    assert not short.keep and not short.ask and short.reason == "it was under 2 minutes and no appointment was set"
    mid = judge(talk, 150)                                     # 2-3 minutes: ask
    assert not mid.keep and mid.ask and mid.reason == "it ran 2:30 with no appointment set"
    assert judge(talk, 180).keep                               # 3+ minutes: saved automatically
    assert judge(talk, 60, is_set=True).keep                   # a set: kept, however short
    assert not judge(talk, 60, {"keep_if_set": False}, is_set=True).keep
    assert judge(talk, 400, {"min_minutes": 5, "auto_save_minutes": 6}).keep   # configurable
    assert judge(talk, 330, {"min_minutes": 5, "auto_save_minutes": 6}).ask
    assert not judge(_t([]), 900).keep                         # nothing said
    vm = judge(_t([(PROSPECT, "Hi, you've reached Mike's Roofing. Please leave a message after the tone.", 2)]), 50)
    assert not vm.keep and "voicemail" in vm.reason

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
    assert disc and disc[0]["reason"] == "it was under 2 minutes and no appointment was set"
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
    cfg["call_filter"]["min_minutes"] = 0
    cfg["call_filter"]["auto_save_minutes"] = 0
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


def test_echo_filter_keeps_real_replies_by_timing():
    import time as _time
    from coach.stt.base import SttEvent
    events = []

    async def run():
        s, _ = _live_session(events)
        t0 = _time.monotonic()

        def at(sp, text, start_offset, dur):
            # A line that started start_offset s after t0 and lasted dur s.
            return SttEvent(sp, text, True, start_offset, dur, t0 + start_offset + dur, True)

        await s.on_stt(at(REP, "What would one extra job a month be worth to you?", 0, 3.0))
        # Real reply that mirrors his words, starting 0.6 s after he finished: kept.
        await s.on_stt(at(PROSPECT, "One extra job a month would be worth a lot to us", 3.6, 3.0))
        await s.on_stt(at(REP, "Can you hear me okay?", 8, 1.2))
        await s.on_stt(at(PROSPECT, "Yes I can hear you", 9.8, 1.0))          # short reply: kept
        # True echo: overlaps his speech (sidetone).
        await s.on_stt(at(REP, "Let me walk you through how the tracking reports work", 12, 3.0))
        await s.on_stt(at(PROSPECT, "Let me walk you through how the tracking reports work", 12.1, 3.0))
        return s

    s = asyncio.run(run())
    pros = [u.text for u in s.transcript.finals if u.speaker == PROSPECT]
    assert "One extra job a month would be worth a lot to us" in pros
    assert "Yes I can hear you" in pros
    assert "Let me walk you through how the tracking reports work" not in pros
    assert s.echo_dropped == 1 and any(k == "echo" and d["hidden"] == 1 for k, d in events)


# ---------------------------------------------------------------- Start doesn't freeze the window
def test_audio_system_starts_once(monkeypatch):
    import types
    import coach.audio as audio

    inits = []
    devices = [
        {"index": 0, "name": "Headset Microphone (Jabra)", "maxInputChannels": 1, "maxOutputChannels": 0,
         "defaultSampleRate": 48000, "hostApi": 0},
        {"index": 1, "name": "Headset Earphone (Jabra) [Loopback]", "maxInputChannels": 2, "maxOutputChannels": 0,
         "defaultSampleRate": 48000, "hostApi": 0, "isLoopbackDevice": True},
    ]

    class FakeStream:
        def start_stream(self): pass
        def stop_stream(self): pass
        def close(self): pass

    class FakePA:
        def __init__(self):
            inits.append(1)
            self.terminated = False
        def get_device_count(self): return len(devices)
        def get_device_info_by_index(self, i): return devices[i]
        def get_host_api_info_by_index(self, i): return {"name": "Windows WASAPI"}
        def get_host_api_info_by_type(self, t): return {"defaultInputDevice": 0}
        def get_default_wasapi_loopback(self): return devices[1]
        def open(self, **kw): return FakeStream()
        def terminate(self): self.terminated = True

    fake = types.SimpleNamespace(PyAudio=FakePA, paWASAPI=13, paInt16=8, paContinue=0)
    monkeypatch.setitem(sys.modules, "pyaudiowpatch", fake)
    audio.shutdown()

    audio.warm_up("wasapi")                                  # app opens
    for _ in range(3):                                       # three calls
        mic = audio.open_mic({"backend": "wasapi"}, lambda b: None)
        lb = audio.open_loopback({"backend": "wasapi"}, lambda b: None)
        mic.start(); lb.start(); mic.stop(); lb.stop()
    assert len(inits) == 1, "audio system should start once, not on every call"
    assert mic.device_name.startswith("Headset Microphone") and "Loopback" in lb.device_name

    devices.append({"index": 2, "name": "USB Headset Mic", "maxInputChannels": 1, "maxOutputChannels": 0,
                    "defaultSampleRate": 16000, "hostApi": 0})
    mic2 = audio.open_mic({"backend": "wasapi", "mic_device": "USB Headset"}, lambda b: None)
    assert mic2.device_name == "USB Headset Mic" and len(inits) == 2     # rescanned once for the new device
    audio.shutdown()


# ---------------------------------------------------------------- follow the call audio
def test_follower_finds_the_speaker_with_the_other_person(monkeypatch):
    import types
    import numpy as _np
    import coach.audio as audio

    devices = [
        {"index": 0, "name": "Headset Microphone (Jabra)", "maxInputChannels": 1, "maxOutputChannels": 0,
         "defaultSampleRate": 16000, "hostApi": 0},
        {"index": 1, "name": "Headphones (Jabra Stereo) [Loopback]", "maxInputChannels": 2, "maxOutputChannels": 0,
         "defaultSampleRate": 48000, "hostApi": 0, "isLoopbackDevice": True},
        {"index": 2, "name": "Headset (Jabra Hands-Free) [Loopback]", "maxInputChannels": 1, "maxOutputChannels": 0,
         "defaultSampleRate": 16000, "hostApi": 0, "isLoopbackDevice": True},
        {"index": 3, "name": "Speakers (Realtek) [Loopback]", "maxInputChannels": 2, "maxOutputChannels": 0,
         "defaultSampleRate": 44100, "hostApi": 0, "isLoopbackDevice": True},
    ]
    callbacks = {}

    class FakeStream:
        def start_stream(self): pass
        def stop_stream(self): pass
        def close(self): pass

    class FakePA:
        def get_device_count(self): return len(devices)
        def get_device_info_by_index(self, i): return devices[i]
        def get_host_api_info_by_index(self, i): return {"name": "Windows WASAPI"}
        def get_host_api_info_by_type(self, t): return {"defaultInputDevice": 0}
        def get_default_wasapi_loopback(self): return devices[1]        # Windows default = stereo headphones
        def open(self, input_device_index, stream_callback, **kw):
            callbacks[input_device_index] = (stream_callback, kw["channels"], kw["rate"])
            return FakeStream()
        def terminate(self): pass

    monkeypatch.setitem(sys.modules, "pyaudiowpatch",
                        types.SimpleNamespace(PyAudio=FakePA, paWASAPI=13, paInt16=8, paContinue=0))
    audio.shutdown()
    fed = []
    f = audio.CallAudioFollower(fed.append, chunk_ms=100)
    f.HOLD_S = 0
    f.start()
    assert f.active == 1 and set(callbacks) == {1, 2, 3}

    def chunk(idx, loud):
        cb, ch, rate = callbacks[idx]
        n = int(rate * 0.1)
        a = (_np.sin(_np.arange(n * ch) / 7) * (8000 if loud else 0)).astype(_np.int16)
        cb(a.tobytes(), n, None, 0)

    mic_loud = (_np.ones(1600) * 6000).astype(_np.int16).tobytes()
    for turn in range(6):
        for _ in range(10):                     # Spencer talks: his sidetone hits the stereo device
            f.note_mic(audio._rms(mic_loud))
            chunk(1, True); chunk(2, False); chunk(3, False)
        for _ in range(10):                     # colleague talks on the Hands-Free device, mic quiet
            f.note_mic(0.0); f._mic = 0.0
            chunk(1, False); chunk(2, True); chunk(3, False)
        if f.pick():
            break
    assert f.active == 2, f.scores               # followed the colleague, not the sidetone
    fed.clear()
    chunk(2, True)
    assert len(fed) == 1 and len(fed[0]) == 1600 * 2       # 100 ms at 16 kHz, mono
    chunk(1, True)
    assert len(fed) == 1                         # other speakers aren't sent to speech-to-text
    f.set_active(3)                              # manual pick locks it
    for _ in range(30):
        f._mic = 0.0; chunk(2, True)
    assert not f.pick() and f.active == 3 and f.locked
    f.set_active(None)
    assert not f.locked
    names = [d["name"] for d in f.device_list()]
    assert "Headset (Jabra Hands-Free)" in names and all("[Loopback]" not in n for n in names)
    f.stop()
    audio.shutdown()


# ---------------------------------------------------------------- landing the plane
def test_close_state_rules():
    from coach.closing import CloseState
    c = CloseState()
    assert c.active_path() == "none" and c.score() is None and c.outcome_label() == "No outcome yet"
    assert "start landing the plane now" in c.status_text(11, 10)
    c.apply_tracker({"path": "set_demo", "demo_time_confirmed": True, "demo_when": "Thu 2pm",
                     "demo_format": "google_meet", "decision_maker": "others_needed",
                     "decision_maker_note": "franchisor must approve all marketing, process unknown so far",
                     "decision_maker_confirmed": False, "invite_accept_asked": True})
    assert c.outcome_label() == "Setting the demo (1 of 3)"          # unconfirmed DM doesn't count
    assert c.detail("decision_maker").endswith("(not confirmed yet)") and "\u2026" not in c.detail("decision_maker")[:5]
    c.apply_tracker({"path": "set_demo", "decision_maker": "sole", "decision_maker_confirmed": True})
    assert c.outcome_label() == "Setting the demo (2 of 3)" and c.score() == 80
    assert c.missing() == ["ask them to give reasonable notice if they need to reschedule"]
    assert c.detail("demo_time") == "Thu 2pm · Google Meet"
    c.apply_tracker({"path": "set_demo", "demo_time_confirmed": False})   # facts don't go backwards
    assert c.done("demo_time")
    c.mark("invite", True)                                                 # Spencer ticks it
    assert c.complete() and c.outcome_label() == "Demo set: Thu 2pm" and c.score() == 100
    c.mark("invite", None)
    assert not c.complete()
    o = CloseState()
    o.mark("otf", True)
    assert o.active_path() == "otf" and o.complete() and o.outcome_label() == "OTF"
    n = CloseState()
    n.apply_tracker({"path": "not_interested", "not_interested": True})
    assert n.complete() and n.score() == 70


class _CloseFakeMessages(_FakeMessages):
    """Tracker answers from what's in the transcript so far."""

    async def create(self, **kw):
        content = kw["messages"][0]["content"]
        if "Landing-the-plane tracker" in content:
            self.calls.append(kw)
            res = {"path": "none", "demo_time_confirmed": False, "demo_when": "", "demo_format": "unknown",
                   "decision_maker": "unknown", "decision_maker_note": "", "invite_accept_asked": False,
                   "reschedule_notice_asked": False, "otf_link_sent": False, "followup_set": False,
                   "followup_when": "", "not_interested": False, "decision_maker_confirmed": False,
                   "stage": "discovery", "conversation_mode": "business", "meeting_agreed": False}
            if "Thursday at two works" in content:
                res.update(path="set_demo", demo_time_confirmed=True, demo_when="Thu 2pm", demo_format="google_meet",
                           stage="confirming", meeting_agreed=True)
            if "It's just me" in content:
                res.update(decision_maker="sole", decision_maker_confirmed=True)
            if "accept it" in content:
                res.update(invite_accept_asked=True)

            class B:
                type = "text"
                text = json.dumps(res)

            class M:
                stop_reason = "end_turn"
                content = [B()]
            return M()
        return await super().create(**kw)


def test_landing_the_plane_end_to_end(tmp_path):
    cfg = load_config()
    cfg["storage"]["calls_dir"] = str(tmp_path)
    cfg["replay"]["speed"] = 20
    cfg["coach"]["live_mode"] = True
    cfg["landing"]["tracker_delay_seconds"] = 0
    events = []

    async def run():
        s = CallSession(cfg, PROMPTS, lambda k, d: events.append((k, d)), "replay_text",
                        str(ROOT / "samples" / "set_demo_practice.txt"))
        client = _FakeClient(REPLY)
        client.messages = client.beta.messages = _CloseFakeMessages(REPLY)
        s.engine.client = client
        await s.start()
        await asyncio.wait_for(s.wait_ended(), timeout=60)
        return s

    s = asyncio.run(run())
    c = s.closing
    assert c.active_path() == "set_demo" and c.done("demo_time") and c.decision_maker == "sole"
    assert not c.complete() and "reschedule" in c.missing()[0]
    # The coach got the landing status, and the goodbye triggered the guard.
    contents = [k["messages"][0]["content"] for k in s.engine.client.messages.calls]
    live_prompts = [t for t in contents if "Live coach mode" in t]
    assert "Landing the plane:" not in live_prompts[0]            # discovery: no scheduling prompts
    assert "Call stage: Cold call / Discovery" in live_prompts[0]
    assert any("Landing the plane:" in t and "Call stage: Confirming" in t for t in live_prompts)
    assert any(k == "stage" and d["stage"] == "confirming" for k, d in events)
    # A time is set, so his goodbye ends the coaching: no "one more thing" nudge.
    assert not any("starting to wrap up the call" in t for t in contents)
    assert s.exit.wrapping
    assert any(k == "closing" for k, _ in events)
    metrics = json.loads((Path(s.store.dir) / "metrics.json").read_text())
    assert metrics["outcome"]["outcome"] == "Setting the demo (2 of 3)"
    assert metrics["scores"]["Next-step clarity"] == 80
    assert any("Before you hang up" in r for r in metrics["recommendations"])
    summary_md = (Path(s.store.dir) / "summary.md").read_text()
    assert "- Outcome: Setting the demo (2 of 3)" in summary_md and "[x] Date & time confirmed" in summary_md
    summary_req = [t for t in contents if "The call has ended" in t][0]
    assert "Not done before the call ended" in summary_req
    from coach.storage import list_calls
    assert list_calls(str(tmp_path))[0]["outcome"] == "Setting the demo (2 of 3)"


def test_one_outcome_path_at_a_time():
    from coach.closing import CloseState
    c = CloseState()
    c.apply_tracker({"path": "set_demo", "demo_time_confirmed": True, "followup_set": True,
                     "followup_when": "Fri Dec 11", "otf_link_sent": False})
    d = c.to_dict()
    assert d["path"] == "set_demo" and d["items"]["demo_time"]["done"]
    assert not d["items"]["followup"]["done"] and not d["items"]["otf"]["done"]   # other paths never show done
    c.mark("otf", True)                                    # Spencer switches to OTF
    assert c.active_path() == "otf" and not c.to_dict()["items"]["demo_time"]["done"]
    c.mark("demo_time", True)                              # ...and back: the OTF tick is dropped
    assert c.active_path() == "set_demo" and "otf" not in c.manual


# ================================================================ v2 (11/16 review)
def _ev(sp, text, start, dur=None, final=True, speech_final=True):
    import time as _time
    from coach.stt.base import SttEvent
    d = dur if dur is not None else max(0.4, len(text.split()) / 2.7)
    return SttEvent(sp, text, final, start, d, _time.monotonic(), speech_final)


def _v2_session(events, live=False, **cfgset):
    import time as _time
    cfg = load_config()
    cfg["coach"]["live_mode"] = live
    cfg["live_coach"]["turn_end_wait_ms"] = 150
    for k, v in cfgset.items():
        a, b = k.split("__")
        cfg[a][b] = v
    s = CallSession(cfg, PROMPTS, lambda k, d: events.append((k, d)), "replay_text")
    s.running = True
    s._resume_mono = _time.monotonic()
    s.engine.style_notes = ""
    return s


def test_backchannels_merging_and_audio_order():
    events = []

    async def run():
        s = _v2_session(events)
        await s.on_stt(_ev(REP, "So walk me through how calls come in right now.", 0.0))
        await s.on_stt(_ev(PROSPECT, "Mhmm.", 2.0))                                   # backchannel
        await s.on_stt(_ev(REP, "And who answers the phone when you're on a roof?", 4.0))  # same speaker: merges
        await s.on_stt(_ev(PROSPECT, "Usually me, or my wife if I'm stuck on a job.", 7.0))
        # A late-arriving rep line that was actually spoken before the prospect's line:
        await s.on_stt(_ev(REP, "Got it, makes sense.", 6.0))
        return s

    s = asyncio.run(run())
    finals = s.transcript.finals
    assert [u.t for u in finals] == sorted(u.t for u in finals)                 # sorted by audio time
    first = finals[0]
    assert first.speaker == REP and "who answers the phone" in first.text       # merged across "mhmm"
    assert first.asides == [(PROSPECT, "Mhmm.")]                                # backchannel kept as an aside
    assert "[Prospect: Mhmm.]" in s.transcript.text()
    assert s.metrics.backchannels == 1 and s.metrics.prospect_words == len(
        "Usually me, or my wife if I'm stuck on a job.".split())                 # "Mhmm" isn't talk
    assert not any(u.text == "Mhmm." for u in finals)


def test_cards_only_after_a_finished_prospect_turn():
    events = []

    async def run():
        s = _v2_session(events, live=True)
        s.engine.client = _FakeClient(REPLY)
        await s.on_stt(_ev(PROSPECT, "We tried an agency and", 0, speech_final=True))   # fragment
        await asyncio.sleep(0.05)
        n_after_fragment = len(s.engine.client.messages.calls)
        await s.on_stt(_ev(PROSPECT, "it was a waste of money.", 2, speech_final=True))  # completes the turn
        await asyncio.sleep(0.3)
        await s.on_stt(_ev(PROSPECT, "Yeah.", 5))                                          # backchannel: never a card
        await asyncio.sleep(0.3)
        return s, n_after_fragment

    s, n_frag = asyncio.run(run())
    calls = s.engine.client.messages.calls
    assert n_frag == 0
    assert len(calls) == 1 and 'We tried an agency and it was a waste of money.' in calls[0]["messages"][0]["content"]
    assert any(k == "coach" and d.get("state") == "listening" for k, d in events)


def test_stay_quiet_reply_becomes_a_listening_status():
    events = []
    quiet = "Say this next: (Listening)\nTactic: wait\nWatch-out: let them finish"

    async def run():
        s = _v2_session(events, live=True)
        s.engine.client = _FakeClient(quiet)
        await s.on_stt(_ev(PROSPECT, "Honestly the phone has been really quiet this fall.", 0))
        await asyncio.sleep(0.3)
        return s

    s = asyncio.run(run())
    assert s._coaching_count == 0
    assert not any(k == "coach" and d.get("state") in ("done", "streaming") for k, d in events)
    assert any(k == "coach" and d.get("state") == "listening" for k, d in events)


def test_typed_input_is_ground_truth_and_labeled():
    events = []

    async def run():
        s = _v2_session(events)
        s.engine.client = _FakeClient(REPLY)
        await s.on_stt(_ev(PROSPECT, "Send me something and I'll look at it.", 0))
        await s.ask("He said his partner Fred Terry signs off on marketing")
        await asyncio.sleep(0.2)
        return s

    s = asyncio.run(run())
    typed = [u for u in s.transcript.finals if u.typed]
    assert typed and "Spencer (typed): He said his partner Fred Terry" in s.transcript.text()
    content = s.engine.client.messages.calls[-1]["messages"][0]["content"]
    assert "ground truth" in content and "Fred Terry signs off" in content
    assert s.metrics.rep_words == 0                                              # typed text isn't talk time
    assert any(k == "line" and d.get("typed") for k, d in events)


def test_context_has_last_card_covered_lines_and_confirmed_names():
    events = []
    s = _v2_session(events)
    s.glossary = {"Prospect": "Fred Terry", "Company": "Terry Roofing"}
    s._last_card_text = "I'll send the Meet link now."
    s.transcript.add(Utterance(REP, "I just sent you the Google Meet link.", 1, 2))
    ctx = s._context_block("live")
    assert "Prospect: Fred Terry" in ctx and "Use ONLY these names" in ctx
    assert "Already covered by Spencer" in ctx and "sent you the Google Meet link" in ctx
    assert "Your last card to Spencer was" in ctx
    assert "Call stage: Cold call / Discovery" in ctx and "Landing the plane:" not in ctx
    s.set_stage("confirming")
    assert "Landing the plane:" in s._context_block("live")
    s.set_stage("presenting")
    assert "checking-for-agreement" in s._context_block("live") and "Landing the plane:" not in s._context_block("live")


def test_side_conversation_pauses_then_resumes():
    events = []

    async def run():
        s = _v2_session(events, live=True)
        s.engine.client = _FakeClient(REPLY)
        s.stage_state.apply({"stage": "side", "conversation_mode": "side"}, 60)
        s._stage_changed("discovery", "side")
        await s.on_stt(_ev(PROSPECT, "Hold on, the guy is backing into the tow hitch out here.", 61))
        await asyncio.sleep(0.3)
        n_side = len(s.engine.client.messages.calls)
        old, new = s.stage_state.apply({"stage": "discovery", "conversation_mode": "business"}, 90)
        s._stage_changed(old, new)
        await s.on_stt(_ev(PROSPECT, "Okay sorry, so the roofing calls have dropped off a lot.", 91))
        await asyncio.sleep(0.3)
        return s, n_side

    s, n_side = asyncio.run(run())
    assert n_side == 0
    assert len(s.engine.client.messages.calls) == 1
    states = [d.get("state") for k, d in events if k == "coach"]
    assert "paused" in states and "resumed" in states


def test_land_the_plane_suggested_only_after_sustained_derail_not_rapport():
    from coach.stage import StageState
    st = StageState()
    st.apply({"stage": "discovery", "conversation_mode": "rapport"}, 100)
    assert st.off_sale_seconds(400) == 0                      # rapport is never derailment
    st.apply({"stage": "side", "conversation_mode": "side"}, 400)
    assert st.off_sale_seconds(500) == 100
    assert st.off_sale_seconds(590) >= 180 - 10
    st.apply({"stage": "discovery", "conversation_mode": "business"}, 600)
    assert st.off_sale_seconds(700) == 0


def test_stage_pin_overrides_detection():
    from coach.stage import StageState
    st = StageState()
    st.apply({"stage": "presenting", "conversation_mode": "business"}, 10)
    assert st.effective_for(10) == "presenting"
    st.pin("confirming")
    st.apply({"stage": "discovery"}, 20)
    assert st.effective_for(20) == "confirming"
    st.pin(None)
    assert st.effective_for(20) == "discovery"


def test_metrics_v2_formulas():
    m = Metrics()
    # 55% rep talk at 203 wpm, like the 11/16 call
    m.add_utterance(Utterance(REP, " ".join(["word"] * 203), 0, 60))
    m.add_utterance(Utterance(PROSPECT, " ".join(["word"] * 120), 60, 49))
    sc = m.scores()
    assert m.rep_share == 55 and sc["Listening"] == 100 - 3 * 10           # target 30-45%
    assert sc["Pacing"] == 100                                            # 203 wpm is inside 170-220
    assert "target 170–220" in m.details()["Pacing"]
    fast = Metrics()
    fast.add_utterance(Utterance(REP, " ".join(["word"] * 240), 0, 60))
    assert fast.scores()["Pacing"] == 100 - 2 * (240 - 220)
    assert any("240 wpm" in r for r in fast.recommendations())
    p = Metrics()
    p.add_utterance(Utterance(REP, "And this shows who called you, right? Does that make sense?", 0, 4), stage="presenting")
    assert p.checkins == 2 and p.questions == 0                           # presenting check-ins aren't discovery


def test_selling_notes_proposed_after_call_and_saved_only_when_approved(tmp_path):
    from coach import notes as notes_mod
    cfg = load_config()
    cfg["notes"]["style_file"] = str(tmp_path / "style.md")
    n = notes_mod.new_proposal({"text": "Quote price only after budget is known.", "source": "typed",
                                "timestamp": "12:30", "quote": "", "conflicts_with_transcript": False}, "2026-11-16_13-15")
    assert n["status"] == "proposed" and notes_mod.load_style(cfg) == ""     # nothing saved yet
    notes_mod.save_note(cfg, n["text"], n["call"], n["timestamp"])
    style = notes_mod.load_style(cfg)
    assert "- Quote price only after budget is known." in style and "call 2026-11-16_13-15 at 12:30" in style
    flagged = notes_mod.new_proposal({"text": "He agreed to $700.", "conflicts_with_transcript": True,
                                      "conflict_reason": "He said $500 at [06:13]."}, None)
    assert flagged["status"] == "flagged" and "06:13" in flagged["reason"]
    # Approved notes load into the coach's context, separate from the playbook.
    eng = CoachEngine(cfg, PROMPTS, api_key_present=False)
    eng.style_notes = style
    blocks = eng.system_blocks()
    assert blocks[-1]["text"].startswith("# Spencer's selling notes") and "cache_control" in blocks[-1]
    assert all("cache_control" not in b for b in blocks[:-1])


def test_notes_are_not_saved_during_the_call(tmp_path):
    cfg_notes = tmp_path / "style.md"
    events = []

    async def run():
        s = _v2_session(events, notes__style_file=str(cfg_notes))
        s.add_coach_note("I never give pricing before budget")
        return s

    s = asyncio.run(run())
    assert not cfg_notes.exists()
    assert s.coach_notes[0]["text"] == "I never give pricing before budget"
    assert any(k == "coach_notes" for k, _ in events)



# ---------------------------------------------------------------- 11/17 additions
def test_one_question_per_line():
    from coach.engine import one_question
    assert one_question("Makes sense. How much does one job profit you? And how many do you need a month?") == \
        "Makes sense. How much does one job profit you?"
    assert one_question("What types of jobs are you after right now?") == "What types of jobs are you after right now?"
    assert one_question("Totally fair, let's do that.") == "Totally fair, let's do that."


def test_cards_are_trimmed_to_one_question():
    events = []
    two = ("Say this next: Got it. How much are you spending on marketing now? Where is that going?\n"
           "Tactic: Miner: situation\nWatch-out: one at a time")

    async def run():
        s = _v2_session(events, live=True)
        s.engine.client = _FakeClient(two)
        await s.on_stt(_ev(PROSPECT, "We run a few Facebook ads but the phone is pretty quiet.", 0))
        await asyncio.sleep(0.3)
        return s

    asyncio.run(run())
    done = [d for k, d in events if k == "coach" and d.get("state") == "done"]
    streamed = [d for k, d in events if k == "coach" and d.get("state") == "streaming"]
    assert done and done[0]["say"] == "Got it. How much are you spending on marketing now?"
    assert all(d["say"].count("?") <= 1 for d in streamed)


def test_blue_collar_questions_in_discovery_and_configurable():
    events = []
    s = _v2_session(events)
    ctx = s._context_block("live")
    assert "How much does one job profit you" in ctx and "Where is that marketing money going" in ctx
    s2 = _v2_session(events, coach__discovery_questions=["What's your average ticket on a re-roof?"])
    ctx2 = s2._context_block("live")
    assert "average ticket on a re-roof" in ctx2 and "one job profit" not in ctx2
    s.set_stage("presenting")
    assert "one job profit" not in s._context_block("live")          # only in discovery


def test_pain_recap_before_asking_for_a_time():
    events = []
    s = _v2_session(events)
    s.set_stage("confirming")
    ctx = s._context_block("live")
    assert "recap their pain in their own words" in ctx and "then ask for the time" in ctx
    from coach.engine import LIVE_INSTRUCTION
    assert "ONE question" in LIVE_INSTRUCTION and "recap of their pain" in LIVE_INSTRUCTION

    async def run():
        s.engine.client = _FakeClient(REPLY)
        await s.land_now()
        await asyncio.sleep(0.2)
    asyncio.run(run())
    assert "recap of their pain" in s.engine.client.messages.calls[-1]["messages"][0]["content"]


def test_pace_target_from_config():
    events = []
    s = _v2_session(events, metrics__wpm_target=[180, 230])
    assert s.metrics.wpm_target == (180, 230)


# ---------------------------------------------------------------- momentum: keep going
def test_momentum_guidance():
    events = []
    s = _v2_session(events)
    s.stage_state.apply({"stage": "discovery", "conversation_mode": "business", "momentum": "productive"}, 30)
    ctx = s._context_block("live")
    assert "going well" in ctx and "Don't redirect" in ctx and "You're doing great." in ctx
    s.stage_state.apply({"momentum": "stalled"}, 60)
    assert "stalling" in s._context_block("live") and "going well" not in s._context_block("live")
    s.stage_state.apply({"stage": "side", "conversation_mode": "side", "momentum": "productive"}, 90)
    assert "going well" not in s._context_block("live")            # never during side talk


def test_keep_going_cards_and_turning_points(tmp_path):
    events = []
    keep = ("Say this next: Great conversation. Mention the review tool, since he said customers check reviews first.\n"
            "Tactic: Keep momentum\nWatch-out: Don't change course")

    async def run():
        s = _v2_session(events, live=True, storage__calls_dir=str(tmp_path))
        s.engine.client = _FakeClient(keep)
        s.stage_state.apply({"stage": "discovery", "conversation_mode": "business", "momentum": "productive"}, 0)
        await s.on_stt(_ev(PROSPECT, "Honestly most of my customers check our Google reviews before they call.", 1))
        await asyncio.sleep(0.3)
        return s

    s = asyncio.run(run())
    done = [d for k, d in events if k == "coach" and d.get("state") == "done"]
    assert done and done[0]["mode"] == "keep_going" and done[0]["say"].startswith("Great conversation.")
    assert s._timeline and s._timeline[0]["mode"] == "keep_going"
    from coach.engine import _timeline_text
    assert "KEEP GOING (discovery): Great conversation." in _timeline_text(s._timeline)

    from coach.storage import CallStore
    st = CallStore(str(tmp_path))
    st.write_summary({"overview": "o", "key_wins": [], "missed_opportunities": [], "missed_moments": [],
                      "turning_points": [{"time": "12:30", "what_happened": "Tied reviews to his goal",
                                          "worked": True, "why": "He'd just said customers check reviews"}],
                      "next_steps": []}, {"title": "t"})
    md = (st.dir / "summary.md").read_text()
    assert "## Turning points" in md and "[12:30] Tied reviews to his goal: **Worked.**" in md
    st.finalize(keep=False)


def test_summary_request_includes_coaching_timeline():
    cfg = load_config()
    eng = CoachEngine(cfg, PROMPTS, api_key_present=False)
    eng.client = _FakeClient(REPLY)
    asyncio.run(eng.post_call_summary("[00:01] Rep: hi", {"overall": 70}, 1,
                                      timeline=[{"t": "00:05", "mode": "keep_going", "stage": "discovery",
                                                 "say": "Great conversation. Mention reviews."}]))
    kw = eng.client.messages.calls[-1]
    content = kw["messages"][0]["content"]
    assert "[00:05] KEEP GOING (discovery): Great conversation." in content and "turning_points" in content
    assert "turning_points" in kw["output_config"]["format"]["schema"]["required"]


# ---------------------------------------------------------------- Spencer's discovery questions
def test_discovery_question_bank_loads_and_guides(tmp_path):
    import shutil
    from coach.config import PROMPT_FILES, load_prompts
    for f in PROMPT_FILES.values():
        (tmp_path / f).write_text("x", encoding="utf-8")
    p = load_prompts(tmp_path)
    assert p.discovery == ""                                       # optional
    (tmp_path / "discovery-questions.md").write_text(
        "How long have you been in business?\nHow much does a job like that bring in for you?", encoding="utf-8")
    p = load_prompts(tmp_path)
    assert "How long have you been in business?" in p.discovery

    cfg = load_config()
    eng = CoachEngine(cfg, p, api_key_present=False)
    assert any("Spencer's discovery questions" in b["text"] and "not a sequence" in b["text"]
               for b in eng.system_blocks())

    events = []
    s = CallSession(cfg, p, lambda k, d: events.append((k, d)), "replay_text")
    ctx = s._context_block("live")
    assert "not a script, so there's no required order" in ctx and "decision-maker check" in ctx
    assert "one job profit you, after materials" not in ctx        # his bank replaces the built-in list
    s.set_stage("presenting")
    assert "no required order" not in s._context_block("live")



def test_short_call_with_a_set_is_kept(tmp_path):
    """The landing practice replay is about a minute long but books Thursday at 2."""
    cfg = load_config()
    cfg["storage"]["calls_dir"] = str(tmp_path)
    cfg["replay"]["speed"] = 40
    cfg["landing"]["tracker_delay_seconds"] = 0
    events = []

    async def run():
        s = CallSession(cfg, PROMPTS, lambda k, d: events.append((k, d)), "replay_text",
                        str(ROOT / "samples" / "set_demo_practice.txt"))
        client = _FakeClient(REPLY)
        client.messages = client.beta.messages = _CloseFakeMessages(REPLY)
        s.engine.client = client
        await s.start()
        await asyncio.wait_for(s.wait_ended(), timeout=60)
        return s

    s = asyncio.run(run())
    assert s._accum < 600 and s._appointment_set()
    assert any(k == "summary" and d.get("state") == "done" for k, d in events)
    assert not any(k == "summary" and d.get("state") == "discarded" for k, d in events)


# ================================================================ Call breakdown
def test_breakdown_reads_transcripts_and_guesses_the_rep():
    from coach import breakdown as bd
    rows = bd.parse_text("Mike Johnson: Hello?\nSpencer: Hey Mike, this is Spencer with Olly Olly. Got a minute?\n"
                         "Mike Johnson: Sure.\n")
    assert bd.guess_rep(rows, "Spencer Faircloth") == "Spencer"
    diar = [{"t": 0, "speaker": "Speaker 1", "text": "Hello, Mike's Roofing."},
            {"t": 2, "speaker": "Speaker 2", "text": "Hi Mike, my name is Spencer, calling from Olly Olly. How are calls coming in?"}]
    assert bd.guess_rep(diar, "Spencer Faircloth") == "Speaker 2"
    ours = bd.parse_text("[00:05] Rep: What made you take the call?\n[00:09] Prospect: Phones are slow.\n"
                         "[00:12] Spencer (typed): note\n")
    assert len(ours) == 2 and ours[0]["t"] == 5
    assert bd.normalize(ours, "Rep").splitlines()[1] == "[00:09] Prospect: Phones are slow."


def test_breakdown_plan_progress_rules():
    from coach import breakdown as bd
    plan = {"rep": "Spencer", "steps": [
        {"id": "s1", "text": "Pain recap before the ask", "status": "active", "history": []},
        {"id": "s2", "text": "Ask budget before pricing", "status": "active", "history": []}]}
    bd.apply_progress(plan, [{"step_id": "s1", "status": "improved"}, {"step_id": "s2", "status": "not_yet"}], "b1")
    assert [s["status"] for s in plan["steps"]] == ["active", "active"]
    ch = bd.apply_progress(plan, [{"step_id": "s1", "status": "improved"}, {"step_id": "s2", "status": "not_yet"}], "b2")
    assert plan["steps"][0]["status"] == "mastered" and plan["steps"][1]["status"] == "needs_training"
    assert {c["to"] for c in ch} == {"mastered", "needs_training"}
    bd.apply_progress(plan, [{"step_id": "s2", "status": "no_opportunity"}], "b3")       # doesn't count either way
    assert plan["steps"][1]["status"] == "needs_training"
    bd.apply_final_steps(plan, [{"step": "Ask budget before pricing", "carry_over_id": "s2"},
                                {"step": "One question at a time", "why": "w", "how_to_practice": "h",
                                 "success_looks_like": "s", "carry_over_id": ""}], ["s2"], "b3")
    ids = {s["id"]: s for s in plan["steps"]}
    assert ids["s2"]["status"] == "needs_training"                                   # carried over, same step
    assert any(s["text"] == "One question at a time" and s["status"] == "active" for s in plan["steps"])
    assert len([s for s in plan["steps"] if s["text"] == "Ask budget before pricing"]) == 1


class _BdFakeMessages(_FakeMessages):
    def __init__(self):
        super().__init__(REPLY)
        self.round = 0

    async def create(self, **kw):
        self.calls.append(kw)
        content = kw["messages"][0]["content"]
        if "Break down these sales calls" in content:
            self.round += 1
            step_progress = []
            if "s1:" in content:
                step_progress = [{"step_id": "s1", "step": "Pain recap before the ask", "status": "improved",
                                  "evidence": "Recapped crews before asking for Thursday", "time": "00:40"}]
            res = {"overview": "Good discovery, rushed close.", "patterns": [], "step_progress": step_progress,
                   "calls": [{"call_id": 1, "title": "Roofer", "strengths": [
                       {"time": "00:12", "category": "discovery_question", "quote": "What happens if retail stays slow?",
                        "why": "Consequence question"}],
                       "improvements": [{"time": "00:44", "category": "confirmation", "quote": "Can you accept it?",
                                         "issue": "No reschedule ask", "try_instead": "If anything comes up, can you give me a day's notice?"}]}]}
        else:
            res = {"response_to_rep": "Fair point on the timing.", "training_flags": [], "carry_over": [],
                   "action_steps": [{"step": "Pain recap before the ask", "why": "Makes the reason stick",
                                     "how_to_practice": "Say their pain back first", "success_looks_like": "Recap on every ask",
                                     "carry_over_id": ""}]}

        class B:
            type = "text"
            text = json.dumps(res)

        class M:
            stop_reason = "end_turn"
            content = [B()]
        return M()


def test_breakdown_end_to_end(tmp_path):
    import time as _time
    from coach import breakdown as bd
    from coach.breakdown_controller import BreakdownController
    from coach.runner import AsyncRunner
    import coach.breakdown_controller as bc

    cfg = load_config()
    cfg["breakdown"]["dir"] = str(tmp_path / "bd")
    fake = _BdFakeMessages()

    class Eng(CoachEngine):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            client = _FakeClient(REPLY)
            client.messages = client.beta.messages = fake
            self.client = client
    orig = bc.CoachEngine
    bc.CoachEngine = Eng
    posts = []
    runner = AsyncRunner()
    try:
        c = BreakdownController(cfg, PROMPTS, lambda k, d: posts.append((k, d)), runner, True)
        c.set_rep("Spencer Faircloth")
        call = tmp_path / "roofer.txt"
        call.write_text((ROOT / "samples" / "set_demo_practice.txt").read_text(), encoding="utf-8")
        c.add_paths([str(call)])

        def wait(cond, t=10):
            end = _time.time() + t
            while not cond() and _time.time() < end:
                _time.sleep(0.05)
            assert cond()
        wait(lambda: c.calls)
        assert c.calls[0]["rep"] == "Rep"
        c.analyze(); wait(lambda: c.analysis and not c.busy)
        imp = c.analysis["calls"][0]["improvements"][0]
        assert imp["id"] == 1
        c.reflect("1", "I was rushing because he had a crew waiting.")
        c.reflect("general", "I want to slow down at the close.")
        c.finalize(); wait(lambda: c.final and not c.busy)
        plan = bd.load_plan(cfg, "Spencer Faircloth")
        assert [s["text"] for s in plan["steps"]] == ["Pain recap before the ask"]
        saved = list((tmp_path / "bd" / "spencer-faircloth").glob("*/breakdown.md"))
        md = saved[0].read_text()
        assert "Rep's take: I was rushing" in md and "Action steps for the next calls" in md
        prompt = fake.calls[-1]["messages"][0]["content"]
        assert "I was rushing because he had a crew waiting." in prompt and "slow down at the close" in prompt

        # Next time: the earlier step is checked.
        c.reset(); c.add_paths([str(call)]); wait(lambda: c.calls)
        c.analyze(); wait(lambda: c.analysis and not c.busy)
        assert "s1: Pain recap before the ask" in fake.calls[-1]["messages"][0]["content"]
        plan = bd.load_plan(cfg, "Spencer Faircloth")
        assert plan["steps"][0]["history"][-1]["status"] == "improved"
        snap = c.snapshot()
        assert snap["history"] and snap["plan"][0]["text"] == "Pain recap before the ask"
    finally:
        bc.CoachEngine = orig
        runner.stop()


def test_live_coach_knows_current_action_steps(tmp_path):
    from coach import breakdown as bd
    cfg = load_config()
    cfg["breakdown"]["dir"] = str(tmp_path)
    bd.save_plan(cfg, {"rep": cfg["rep_name"], "steps": [
        {"id": "s1", "text": "Recap pain before asking for the time", "status": "active", "history": []},
        {"id": "s2", "text": "Old step", "status": "retired", "history": []}]})
    events = []

    async def run():
        s = CallSession(cfg, PROMPTS, lambda k, d: events.append((k, d)), "replay_text",
                        str(ROOT / "samples" / "set_demo_practice.txt"))
        await s.start()
        ctx = s._context_block("live")
        await s.end()
        return ctx

    ctx = asyncio.run(run())
    assert "current action steps" in ctx and "Recap pain before asking for the time" in ctx and "Old step" not in ctx


# ================================================================ Reading the room
def test_exit_signals_levels():
    from coach.exit import ExitState
    e = ExitState()
    assert e.hear_prospect("Our phones have been slow since spring.", 10) == 0
    assert e.hear_prospect("Hey man, I'm on a roof right now.", 20) == 1
    assert "callback" in e.guidance(False) and e.level() == 1 and not e.quiet()
    assert e.hear_prospect("Look, I really gotta go.", 30) == 2
    assert "End the call now" in e.guidance(False)
    e.firm_sent = True
    assert e.quiet()
    h = ExitState()
    assert h.hear_prospect("Stop calling me!", 5) == 2
    n = ExitState()
    n.hear_prospect("Not interested.", 5)
    assert n.level() == 1
    n.hear_prospect("I told you, we're all set.", 9)
    assert n.level() == 2
    # The tracker can clear it when they re-engage.
    n.apply_tracker({"prospect_wants_out": False, "momentum": "productive"})
    assert n.level() == 0
    w = ExitState(wrapping=True)
    assert w.quiet() and "Don't suggest another question" in w.guidance(True)
    assert "already agreed" in ExitState().guidance(True)


def test_prospect_who_has_to_go_gets_a_wrap_card_then_quiet(tmp_path):
    script = tmp_path / "busy.txt"
    script.write_text(
        "Rep: Hey Mike, Spencer with Olly Olly. How are calls coming in for the roofing side?\n"
        "Prospect: Honestly I'm on a job right now, I gotta go.\n"
        "Rep: Totally get it, when's a better time?\n"
        "Prospect: I said I gotta go man.\n"
        "Rep: No problem.\n"
        "Prospect: Yeah, and we're not really looking for marketing at all right now anyway.\n")
    cfg = load_config()
    cfg["storage"]["calls_dir"] = str(tmp_path / "calls")
    cfg["replay"]["speed"] = 40
    cfg["live_coach"]["min_gap_seconds"] = 0
    events = []

    async def run():
        s = CallSession(cfg, PROMPTS, lambda k, d: events.append((k, d)), "replay_text", str(script))
        s.engine.client = _FakeClient(REPLY)
        await s.start()
        await asyncio.wait_for(s.wait_ended(), timeout=30)
        return s

    s = asyncio.run(run())
    calls = s.engine.client.messages.calls
    prompts = [c["messages"][0]["content"] if isinstance(c["messages"][0]["content"], str)
               else json.dumps(c["messages"][0]["content"]) for c in calls]
    coaching = [p for p in prompts if "Spencer will read" in p or "The prospect just" in p]
    assert any("Take the hint" in p for p in coaching)            # first "gotta go": soft
    assert any("End the call now" in p for p in coaching)          # second: firm
    firm_i = max(i for i, p in enumerate(coaching) if "End the call now" in p)
    assert all("not really looking" not in p for p in coaching[firm_i + 1:])   # then quiet
    wraps = [d for k, d in events if k == "coach" and d.get("mode") == "wrap"]
    assert wraps and "Time to end the call" in wraps[-1]["question"]
    assert s.exit.level() == 2


def test_no_more_questions_after_the_set_and_goodbye():
    from coach.exit import ExitState
    cfg = load_config()
    events = []
    s = CallSession(cfg, PROMPTS, lambda k, d: events.append((k, d)), "replay_text",
                    str(ROOT / "samples" / "set_demo_practice.txt"))
    s.stage_state.meeting_agreed = True
    assert "already agreed" in s._context_block("live")
    s.exit = ExitState(wrapping=True)
    ctx = s._context_block("live")
    assert "Don't suggest another question" in ctx and "Keep going" not in ctx


# ================================================================ One rulebook for coach and review
def test_review_uses_the_coach_rules_and_knows_what_spencer_read():
    from coach.engine import LIVE_INSTRUCTION, SHARED_RULES, _timeline_text
    assert "Not after every answer" in LIVE_INSTRUCTION
    t = _timeline_text([{"t": "02:51", "mode": "coach", "stage": "confirming", "used": True,
                         "say": "Does Thursday at 10 or Friday at 2 work better?"},
                        {"t": "01:10", "mode": "coach", "stage": "discovery", "say": "x"}])
    assert "[02:51] COACH (confirming) SPENCER SAID THIS:" in t and "[01:10] COACH (discovery): x" in t
    assert "either/or choice of times" in SHARED_RULES

    async def run():
        eng = CoachEngine(load_config(), PROMPTS, True)
        eng.client = _FakeClient(REPLY)
        fake = _CloseFakeMessages(REPLY)
        eng.client.messages = eng.client.beta.messages = fake
        try:
            await eng.post_call_summary("[00:01] Rep: hi", {}, 1, timeline=[{"t": "00:05", "say": "Hi", "used": True}])
        except Exception:
            pass
        return fake.calls[-1]["messages"][0]["content"]
    prompt = asyncio.run(run())
    assert SHARED_RULES in prompt and "SPENCER SAID THIS" in prompt and "coach's call, not his mistake" in prompt


def test_card_spencer_reads_is_marked_used():
    cfg = load_config()
    s = CallSession(cfg, PROMPTS, lambda k, d: None, "replay_text", str(ROOT / "samples" / "set_demo_practice.txt"))
    s._last_say = "Would Thursday at ten or Friday at two be better for you?"
    s._last_timeline = {"t": "03:06", "say": s._last_say, "used": False}
    s._timeline.append(s._last_timeline)
    from coach.stt.base import SttEvent
    import time as _t
    ev = SttEvent(speaker=REP, text="Would Thursday at ten or maybe Friday at two be good for you?",
                  final=True, start=186.0, duration=4.0, spoke_end_mono=_t.monotonic(), speech_final=True)
    s.running = True
    asyncio.run(s.on_stt(ev))
    assert s._timeline[-1]["used"]
