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
2. The **recording notice** appears. Tick "I will tell the prospect this call is recorded" to enable Start. Every call starts with this, and it's noted in `metrics.json`. Say the line it shows at the top of the call, and stop if they say no.
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

### Calls that go nowhere aren't saved

When a call ends, it's thrown away (no files and no summary charge) if any of these is true:
- it was **under 45 seconds**
- the prospect said **fewer than 25 words**
- it hit a **voicemail greeting**

The summary panel then says why, with a **Save anyway** button if you want to keep it. You can change the limits under `call_filter` in `config.yaml`.

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
| Discovery | Your questions per 5 minutes (target 4), plus the share that are open (what, how, why) |
| Listening | Your share of talk time from Deepgram's word timings. 100 inside 40–60%, minus 3 points per % outside |
| Objection handling | Share of detected objections you met with a question or a Voss label ("It sounds like…") within 30 seconds |
| Pacing | Your words per minute. 100 inside 140–170 wpm, minus 2 points per wpm outside |
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
- **Prospect side is silent:** run `--list-devices`, make sure Meet or your dialer plays through the device named in `loopback_device` (or your default output on Windows), and check that call volume isn't muted.
- **Your words show up as Prospect:** your voice is getting into the PC's sound output. The app filters out repeats of what you just said, and the **You / Them meters** in the transcript header show it live: while you talk, only **You** should move. If **Them** moves too, fix it at the source:
  1. **Windows "Listen to this device":** Settings → System → Sound → More sound settings → **Recording** tab → your headset mic → **Properties** → **Listen** tab. Untick **Listen to this device**.
  2. **Headset sidetone:** in your headset's app (Jabra Direct, Poly Lens, Logitech G HUB, and similar), turn sidetone off. Or use the headset's own hardware sidetone if it has one.
  3. **Same mic everywhere:** make Windows' default input the headset mic Aloware uses (Settings → System → Sound → Input), or name it in `audio.mic_device`.
  4. **Echo from the prospect's speakerphone** can't be fixed on your side. The echo filter catches most of it.
- **Labels are backwards on a call:** click **⇄ Swap** in the transcript header. It flips past lines, scores, and everything after for that call. If it happens on every call, your two devices are reversed: run `python main.py --list-devices` and set `audio.mic_device` and `audio.loopback_device` explicitly.
- **The hotkey only works when the app has focus:** pynput couldn't register a global hotkey. The pill says "(window only)". On macOS, grant Accessibility permission.
- **Fonts look different offline:** the page uses Inter from Google Fonts and falls back to Segoe UI.
