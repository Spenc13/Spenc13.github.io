# Live Sales Coach

A desktop app for Olly Olly sales calls. It listens to a live call (Google Meet, or a softphone or dialer on your PC), transcribes both sides, and shows coaching on your second monitor while you talk: what to say next, which tactic it is, and what to watch out for. It scores the call as it goes and writes a summary when you hang up.

- **Shell:** Python + PySide6 (QtWebEngine), showing `web/live-call-coach.html`
- **Speech-to-text:** Deepgram streaming. Your mic is labeled **Rep** and the call audio is labeled **Prospect**.
- **Coach:** Claude (Anthropic Messages API), using your coach instructions, playbook, and offer reference, with prompt caching
- **Saved locally:** `calls/YYYY-MM-DD_HH-MM/` with `transcript.txt`, `coaching.jsonl`, `metrics.json`, `summary.md`

---

## 1. Install (Windows 10/11)

You need Python 3.11 or newer from python.org. Check "Add python.exe to PATH" during install.

Open **PowerShell** in this folder (`live-sales-coach`):

```bash
python -m venv .venv
```

```bash
.venv\Scripts\activate
```

```bash
pip install -r requirements.txt
```

This installs PySide6, the Anthropic SDK, websockets, sounddevice, PyAudioWPatch (WASAPI loopback), and pynput (global hotkey).

On macOS, use `source .venv/bin/activate` instead. PyAudioWPatch is skipped there automatically.

## 2. Add your private files

These files are **gitignored on purpose**. This repository is public (it hosts your GitHub Pages site), and these files hold Olly Olly pricing and your photo. Download them from Google Drive and save them here:

| Save as | From Drive |
|---|---|
| `prompts/coach-instructions.md` | coach-instructions.md (download as Markdown or plain text) |
| `prompts/playbook-hormozi-miner-voss.md` | playbook-hormozi-miner-voss.md |
| `prompts/offer-reference.md` | offer-reference.md |
| `prompts/discovery-questions.md` (optional) | discovery-questions.md, your discovery question bank |
| `web/spencer.png` | spencer.png |

The coach instructions are sent **verbatim** as the system prompt: everything below the `-----` line, as the file itself says. The playbook and offer reference are sent as context with every request. If a prompt file is missing, the app tells you and won't start a call. If `spencer.png` is missing, the avatar shows your initials.

## 3. API keys

Copy `.env.example` to `.env` and fill in both keys:

```
DEEPGRAM_API_KEY=...      # console.deepgram.com → API Keys (free credit to start)
ANTHROPIC_API_KEY=...     # console.anthropic.com → API Keys
```

`.env` is gitignored. Keys are read from the environment only. They are never written to code, logs, or call files.

## 4. Audio routing

**Wear a headset.** If the prospect comes out of your laptop speakers, your mic hears them too, and their words also show up as "Rep."

### Windows (WASAPI loopback, no extra software)

- **Rep:** your default microphone, or set `audio.mic_device` in `config.yaml`.
- **Prospect:** a loopback recording of whatever your **default output device** plays. Google Meet in Chrome or Edge, Zoom, and softphones (RingCentral, Dialpad, Aircall, Google Voice, Teams) all play through it.

If calls play through a device that isn't your default (for example, Meet set to a USB headset), name it:

```bash
python main.py --list-devices
```

Then set `audio.loopback_device: "Headset Earphone"` in `config.yaml`. Use part of the name shown next to `LOOPBACK`.

**Phone calls**
- **Softphone or dialer on the PC:** works as-is through loopback.
- **Physical cell phone:** the PC can't hear it. Use Windows **Phone Link** (Bluetooth calling routes call audio through the PC), or forward calls to a softphone or Google Voice on the PC.

### macOS (BlackHole)

1. Install BlackHole 2ch (`brew install blackhole-2ch`, or download it from existential.audio).
2. Open **Audio MIDI Setup** → **+** → **Create Multi-Output Device**. Tick your headset **and** BlackHole 2ch, and set your headset as the clock source.
3. In Meet or your dialer, set **Speaker** to the Multi-Output Device. You still hear the call, and BlackHole gets a copy.
4. In `config.yaml`, set `audio.loopback_device: "BlackHole 2ch"`. Leave `mic_device` blank or set it to your headset mic.
5. The first run asks for **Microphone** permission. The global hotkey needs **Accessibility** permission for Terminal or Python.

## 5. Run

```bash
python main.py
```

1. Pick **Live call** (or a replay) in the dropdown and press **Start call**.
2. The **recording notice** appears. Tick "I will tell the prospect this call is recorded" to enable Start, and say the line it shows (a shorter mid-call version appears if you're joining partway through). **If your dialer already announces recording on every call,** also tick **"Don't ask again."** From then on, Start begins right away, and with the dialer link coaching **starts by itself when the prospect picks up**. Turn the prompt back on in **Call menu → Ask before each recording** (or set `recording.consent_mode` in `config.yaml`). Each call's `metrics.json` records which applied (`consent_basis`).
3. Talk. With **Live coach** on (the default, toggled in the header), a new "Say this next" line streams in **every time the prospect finishes talking**. It's written as your exact words, so you can read it out loud. If they keep talking, the coach drops the half-written line and starts over with what they just said. When you say the line, the card dims and shows **✓ You said it**, so a bright card always means a fresh line. With Live coach off, cards appear only on objections and buying signals. You can also:
   - Type a question in the ask bar and press **Enter**.
   - Press **Ctrl+Shift+Space** (Cmd+Shift+Space on Mac) from any app to ask about the last ~20 seconds.
   - Click a quick prompt: *Ask a deeper question*, *Pause and let them talk*, *Confirm the pain*.
4. Press **End call**. The app sends the full transcript and metrics to Claude once for the summary, then saves everything to `calls/`.

**Past calls** (header button) lists every saved call, newest first, with its score. Open one to read the summary, scores, coaching cards, transcript, and recommendations, then **Copy summary** (to paste into HubSpot) or **Open folder**. The same two buttons appear in the summary panel when a call ends.

**Stay on top** (header checkbox or the View menu) keeps the window above Meet. The window remembers its size and position, so it reopens on your second monitor.

## 6. HubSpot / Aloware dialer link (optional, recommended)

The `extension/` folder has **Olly Coach Bridge**, a small Chrome extension that runs alongside Olly Phone. With it:
- **When the prospect picks up,** the coach pops up with "They picked up: (number)" and the recording notice. One click starts coaching. Unanswered calls never record.
- **When you hang up,** coaching ends and the summary runs automatically.

Install it from `chrome://extensions` → Developer mode → **Load unpacked** → choose the `extension` folder. Full steps are in [`extension/README.md`](extension/README.md). The header shows **Dialer: linked** when it's working.

### Call stages (v2)

The coach works out which stage the call is in from the conversation: whether a demo has started, whether you're reviewing a package or screen, and whether a meeting has been agreed. The current stage shows under the header, and **one click pins it** (**Auto** hands it back).

| Stage | What the coach focuses on |
|---|---|
| **Cold / Discovery** | your own **discovery questions** if `prompts/discovery-questions.md` exists (a bank, not a script: it picks whichever fits the moment, uses your wording, fills in the brackets, and makes sure the decision-maker check happens before the presentation); otherwise a built-in blue-collar set (`coach.discovery_questions` in `config.yaml`). No pitching, no scheduling |
| **Presenting** | checking-for-agreement questions (target **about 25 per presentation**, counted live), recapping their problems in their words, transitions; no discovery questions |
| **Confirming** | asking for the time **after a one-sentence pain recap in their own words**, the calendar invite, the decision maker and any approval steps (for example, a franchisor sign-off), and the reschedule-notice ask; no pitch content |
| **Side conversation** | coaching **pauses** ("Side conversation: coaching paused") and resumes when the business topic returns |

**Scheduling prompts only appear in Confirming.** Rapport small talk isn't a side conversation, and the coach never pushes to close during rapport. **Coaching on** turns cards off entirely; the transcript and scores keep running. **Every turn** switches between a line after every finished prospect turn and keyword-only cards.

### Card rules

- **One question per line.** The coach never stacks two questions in one card, and the app trims any card that tries to down to its first question.
- **Pain recap before the ask.** Whenever a card asks for a time or appointment, it opens with one sentence recapping the prospect's pain in their own words, then asks, so the reason to show up sticks. This also applies to **✈ Land it** and the Confirming stage.

### When you're on a roll

The coach judges whether the conversation is **productive** (the prospect is engaged and it's moving forward), **neutral**, or **stalled**:
- **Productive:** it doesn't redirect you, so you keep your train of thought. Cards turn green with **✓ Keep going**, and give brief encouragement plus **one point to mention**, tied to what the prospect just said (for example: "Great conversation. Mention the review tool, since he said customers check reviews first").
- **Stalled:** cards go back to helping you move it forward with one clear question.
- **After the call:** the summary sees every card and whether it said keep going or redirect, plus your typed notes. It adds **Turning points**, the key moments, each with whether it worked and **why**.

### How cards are timed

A card is generated only after a **finished prospect turn**: a complete sentence at a pause, or about **1.5 s of silence**. It's never generated on a fragment. While they're still talking, the coaching panel shows **Listening…**. Each request includes:
- the last 4 minutes of both speakers
- your last few lines, marked "already covered"
- the last card it showed you
- anything you typed
- the confirmed names

That way it doesn't repeat itself, or ask for something you already did.

### Typing during the call

The box at the top is always available. Type **what you said, what they said, what the transcript missed, or a question**. It's treated as **ground truth**, used right away, and logged in the transcript as **"You (typed)"**.

### Names (pre-call glossary)

When you call from a HubSpot record, the companion extension reads the contact's **name and company** from the open record. The coach uses **only confirmed names**: from HubSpot, or names you type, such as "His name is Fred Terry". Names it merely hears in the transcript are never trusted. The names are also passed to speech-to-text, which helps it spell them.

### Coach notes (selling style)

- **Anytime:** type how you sell in **Coach notes** (for example, "I never give pricing before budget").
- **After each call:** the coach proposes notes from the transcript, **each citing the [mm:ss] it came from**, plus anything you typed. **Approve, edit, or reject** each one.
- **Saved only on approval:** nothing is saved during a call. Approved notes go to `spencer-selling-style.md`, which is kept on this computer (it's gitignored), and load into every future call, separate from the playbook.
- **The transcript wins:** if a note conflicts with the transcript, it's **flagged** and can't be approved until you edit it. Edited notes are re-checked against the transcript before they're saved.

### Transcript and scoring rules

- **Lines are sorted by audio time,** and consecutive lines from the same speaker merge into one turn.
- **Backchannels** ("mhmm", "yeah", "right?") aren't turns. They show as a small aside on the other person's line, and don't count toward talk time or trigger cards.
- **Listening:** target **30–45% you**.
- **Pacing:** target **170–220 wpm** (change it with `metrics.wpm_target` in `config.yaml`).
- **Discovery:** counts **real questions** only. Tag questions and fragments don't count, and open questions are weighted more.
- **Objections:** count as handled when a coach card responded to them.
- **The outcome follows one path at a time.**
- **The summary** lists **specific moments to fix**, with timestamps (missed consequence questions, skipped budget checks).

### Landing the plane

Every call should end with one outcome. The **Landing the plane** panel is **hidden until you click ✈ Land the plane**. The coach only suggests it after about **3 minutes off the sale** (rapport doesn't count). It tracks the outcome in the background either way, for the score and summary:

| Path | What has to happen |
|---|---|
| **Set the demo** | ① a date and time, by phone or Google Meet ② decision maker confirmed (they're the only one, or the other person gets on the invite) ③ ask them to accept the calendar invite and to give reasonable notice if they need to reschedule |
| **Go OTF** | they have time now, and you send a Google Meet link |
| **Off the phone** | no time within 48 business hours, so set a later date; or not interested, so close politely |

How it works:
- **Automatic ticks:** a background check reads the conversation and ticks items as they're actually agreed (details like "Thu 2pm · Google Meet" or "Also needs: his partner" appear under them). **Click any item** to tick or untick it yourself. Your choice wins.
- **The coach steers toward the close.** Every suggested line knows what's still missing.
- **"Before you hang up"** (Confirming stage): if you start saying goodbye ("talk soon", "thanks for your time") with something missing, the coach fires a card with the exact line to close the loop.
- **✈ Land it** asks for the closing line any time.
- **Saved with the call:** the outcome sets **Next-step clarity**, appears in `summary.md` with its checklist, and shows as a badge in **Past calls** (for example "✓ Demo set: Thu 2pm"). Missing steps lead the post-call summary's next steps.

Practice it with `samples/set_demo_practice.txt`, where Spencer forgets the reschedule ask.

### Google Meet

The same extension also watches **Google Meet**:
- **When you join a meeting,** the coach pops up with "You joined: Google Meet · (meeting name)".
- **When you leave,** coaching ends and the call is saved, unless it went nowhere.

Meet doesn't announce recording the way your dialer does, so **Meet calls always show the recording notice**, even with "Don't ask again" on for the dialer. If your Meets are recorded by Meet itself (Meet tells everyone when recording or note-taking starts), set `recording.meet_consent_mode: announced` in `config.yaml` to skip it.

**If the other person isn't transcribed on Meet,** Meet is probably playing through a different speaker than the app records. After about 25 seconds, the app warns you and names the device it's listening to. Fix it either way:
- In Meet: **⋮ → Settings → Audio → Speakers**, choose that device (or your Windows default).
- In `config.yaml`: set `audio.loopback_device` to the speaker Meet uses (see `python main.py --list-devices`).

### On-the-fly (OTF) presentations: phone to Meet

If you're being coached on an Aloware call and move the prospect onto a Google Meet, **coaching carries straight over**: no prompt, no restart, one saved call. Hanging up the phone after you've joined the Meet doesn't stop it. Coaching ends when you leave the Meet.

If nothing is running yet, **Ctrl+Shift+Space starts coaching from any app** (the same as clicking Start call). The recording notice is a single button, and **Enter** confirms it.

### Starting partway through a call

You can press **Start call** at any point. If the dialer shows the call was answered more than 15 seconds earlier, the call is marked **Partial call (joined at m:ss)**. The coach and the post-call summary are told the beginning wasn't heard, so a "missing" intro isn't counted against you. The scores are labeled partial, and the caller's number is kept even if you canceled the "They picked up" prompt.

### Which calls are saved

A call is saved (folder, summary, and Past calls) only if:
- **an appointment was set**: a demo date and time were agreed, or you went OTF and presented on the spot; or
- **the conversation lasted 10 minutes or longer.**

Anything else isn't saved or graded, and costs no summary request. Right before deciding, the coach runs one last check, so a set made in the final seconds still counts. The summary panel says why a call wasn't saved, with a **Save anyway** button if you want to keep it. Change the length, or whether a set always counts, under `call_filter` in `config.yaml` (`min_minutes`, `keep_if_set`).

## 7. Replay mode (practice without a live call)

Replays run through the same pipeline as a live call: transcript, triggers, coach, scoring, summary, and saving. The dropdown lists the samples, or choose **Replay a file…**

```bash
python main.py --replay samples/roofing_send_me_something.txt
```

```bash
python main.py --replay samples/remodeler_too_expensive.txt --speed 2
```

```bash
python main.py --replay samples/pool_burned_by_agency.txt --headless
```

`--headless` prints the call and coaching in the terminal with no window. Use it for a quick check of your keys and prompts.

| Sample | What it tests |
|---|---|
| `roofing_send_me_something.txt` | Roofer tries to end the call with "send me something"; Spencer sends pricing too early |
| `remodeler_too_expensive.txt` | Remodeler says "too expensive," asks for month-to-month, and has to check with her husband |
| `pool_burned_by_agency.txt` | Pool owner burned by an agency asks for a guarantee, then shows buying signals |

In each sample, Spencer makes realistic mistakes, so you can see whether the coach and the scores catch them.

**Your own scripts:** one line per turn, starting `Rep:` or `Prospect:`. Add `[pause 2]` for silence, and `# title: ...` to name the script.

**Recordings:** `--replay mycall.wav` streams a 16-bit WAV to Deepgram in real time. A **stereo** file uses the left channel as Rep and the right as Prospect. A **mono** file uses Deepgram diarization, which assumes the first voice is Rep.

**Live coach cost:** one short request per prospect turn. The prompts are cached, so each costs about a third of a cent on Sonnet 5.5, roughly $0.20 to $0.40 for a 30-minute call. Settings are under `live_coach` and `coach.live_mode` / `coach.live_thinking` in `config.yaml`.

## 8. Latency

Every coaching card shows how long it took, measured from **when the prospect stopped talking** to when the first line of the card appeared. That total includes Deepgram's finalization time. The header shows the last value against the **3-second target**, and every card's latency is logged in `coaching.jsonl` (`latency_s`, `latency_complete_s`, `api_seconds`).

Settings that affect speed, in `config.yaml`:
- `coach.effort: low` (the default) keeps thinking short.
- `coach.thinking: between_tools` turns extended thinking off on Sonnet 5.5, which is the fastest option. Live coach lines already use it (`coach.live_thinking`).
- `stt.endpointing_ms` sets how long Deepgram waits after speech stops before finalizing (default 300 ms).
- **Prompt caching:** the instructions, playbook, and offer reference are cached after the first request. A card that hit the cache says "prompt cache hit."

## 9. How scoring works (no fake numbers)

Everything is computed from the transcript as the call goes. A score shows "–" until there's enough of the call to judge, and it's left out of the overall score until then.

| Bar | Computed from |
|---|---|
| Discovery | Real questions only (no tag questions or fragments), per 5 minutes outside presenting (target 4), weighted by how many are open (what, how, why) |
| Listening | Your share of talk time from Deepgram's word timings. 100 inside 30–45%, minus 3 points per % outside |
| Objection handling | Share of detected objections a coach card responded to (or, with coaching off, that you met with a question or a Voss label within 30 seconds) |
| Pacing | Your words per minute. 100 inside 170–220 wpm (`metrics.wpm_target`), minus 2 points per wpm outside |
| Next-step clarity | Asked (55), with a specific day or time (+20), and the prospect agreed (+25). Shows 25 if nothing has been asked by minute 5 |

The objection and buying-signal check is a fast local keyword list in `coach/triggers.py`. It only decides **when** to call the coach. Claude decides **what** to say. Auto triggers are debounced: at most one every 8 seconds, and the same objection type at most once every 45 seconds. Both are configurable.

## 10. What leaves your computer

- **Deepgram:** audio from your mic and from the call, for transcription.
- **Anthropic:** the prompt files, a short running summary, and the last 4 minutes of transcript with each coaching request, plus the full transcript once for the post-call summary.
- **Nothing else.** Calls are saved only in `calls/`, which is gitignored. Check your company's policy and your state's recording-consent rules. Some states require every party's consent.

## 11. When something is down

The header has a status pill for each service.
- **Speech-to-text down** (bad key, no network): the pill turns red. The app reconnects with backoff, and the other audio side keeps transcribing.
- **Coach down** (no key, API error, rate limit): the coaching card says so. The transcript, scoring, and saving keep running, and the summary file records that the summary couldn't be written.
- **Refusals:** server-side fallback is on (`coach.server_fallback`), so a declined request is retried on a fallback model automatically.

## 12. Speech-to-text provider

Deepgram is built in. The STT layer is pluggable (`coach/stt/`): subclass `SpeechStream` and register it in `make_stream()`. I couldn't confirm that Wispr Flow has a public streaming API for system audio. It's a dictation app, and the only "API" found was an unofficial, reverse-engineered SDK. If you get official API access, it can be added as a provider.

## 13. Configuration

Settings live in `config.yaml`, and each one is commented there. The main ones:
- `coach.model`: default `claude-sonnet-5-5`
- `coach.transcript_window_minutes`: 4
- `triggers.*`: auto on or off, and the debounce timings
- `hotkey.*`: the key combination, global or window-only, and lookback seconds
- `audio.*`: devices and backend
- `window.stay_on_top`

## 14. Tests

```bash
pytest -q
```

The tests run offline, with no keys or audio. They cover reply parsing, trigger detection and debounce, metric math, the request shape (verbatim instructions, cache breakpoint, fallback), and a full text replay that checks all four saved files.

## Troubleshooting

- **"Missing prompt files":** see step 2.
- **The other person isn't transcribed, or your own voice shows up as Prospect (Bluetooth headsets especially):** on Windows the app **listens to every speaker and follows the one playing the other person**. When it switches, a toast says "Call audio is playing on …". That covers Bluetooth headsets that switch to a separate "Hands-Free" speaker during calls, and Meet or Aloware set to a different speaker. A speaker that only carries your own voice (sidetone) is ignored. To choose by hand, use **Call audio** in the transcript header. It shows 🔊 next to whichever speaker has sound. If you connected the headset after opening the app, use **View → Rescan audio devices** between calls.
- **Prospect side is silent:** run `--list-devices`, make sure Meet or your dialer plays through the device named in `loopback_device` (or your default output on Windows), and check that call volume isn't muted.
- **Your words show up as Prospect:** your voice is getting into the PC's sound output. The app filters out repeats of what you just said, and the **You / Them meters** in the transcript header show it live: while you talk, only **You** should move. If **Them** moves too, fix it at the source:
  1. **Windows "Listen to this device":** Settings → System → Sound → More sound settings → **Recording** tab → your headset mic → **Properties** → **Listen** tab. Untick **Listen to this device**.
  2. **Headset sidetone:** in your headset's app (Jabra Direct, Poly Lens, Logitech G HUB, and similar), turn sidetone off. Or use the headset's own hardware sidetone if it has one.
  3. **Same mic everywhere:** make Windows' default input the headset mic Aloware uses (Settings → System → Sound → Input), or name it in `audio.mic_device`.
  4. **Echo from the prospect's speakerphone** can't be fixed on your side. The echo filter catches most of it.
- **The other person's lines are missing and the transcript header says "N echo lines hidden":** your mic is also hearing them, usually because they're in the same room during a test. Click **Show all** to turn the echo filter off for that call, or test from separate rooms. Real prospects aren't in your room, so this doesn't happen on real calls. Short replies, and replies that start after you finish talking, are never hidden.
- **You just plugged in or switched a headset:** use **View → Rescan audio devices** (between calls).
- **Labels are backwards on a call:** click **⇄ Swap** in the transcript header. It flips past lines, scores, and everything after for that call. If it happens on every call, your two devices are reversed: run `python main.py --list-devices` and set `audio.mic_device` and `audio.loopback_device` explicitly.
- **The hotkey only works when the app has focus:** pynput couldn't register a global hotkey. The pill says "(window only)". On macOS, grant Accessibility permission.
- **Fonts look different offline:** the page uses Inter from Google Fonts and falls back to Segoe UI.
