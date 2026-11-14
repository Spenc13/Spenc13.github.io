# Test plan: before the first real prospect

Allow about 45 minutes. Do it on the computer and headset you'll use for calls. Tick each box before moving on. If a step fails, the fix is usually in the README troubleshooting section.

## A. Setup checks (5 min)

- [ ] `pytest -q` passes (offline: no keys or audio needed).
- [ ] `python main.py --replay samples/roofing_send_me_something.txt --headless` prints the transcript, at least one `** COACH` card, and a post-call summary. This confirms both keys and all three prompt files.
- [ ] Open `calls/<newest>/`. It has `transcript.txt`, `coaching.jsonl`, `metrics.json`, and `summary.md`, and none of them contain an API key.

## B. Replay all three samples in the app (10 min)

Run `python main.py` and play each sample from the dropdown.

| Sample | Expect |
|---|---|
| Roofing: "send me something" | An auto card at "send me something" that qualifies before sending (Miner), not "sure, I'll email it." Objection handling is about 50%: Spencer asks one good question, then agrees to email pricing without asking another. |
| Remodeler: "too expensive" | Cards for price and month-to-month. The coach runs the **payment waterfall before any discount** and is honest that Growth and Strategic month-to-month is a last resort. A decision-maker card at "run it by my husband." |
| Pool: burned by an agency | A Voss label for the agency story. At "guarantee," the coach **does not invent a guarantee** and says to confirm it with leadership. Buying signals at "when can you start" and "who else." Next-step clarity shows **agreed** after "Thursday at ten works." |

For each card, check:
- [ ] Three parts: Say this next / Tactic / Watch-out, under about 80 words.
- [ ] Prices and terms match `offer-reference.md` exactly. Growth $400–550, Strategic $500–750, Elite $1,100 (12-month) or $1,300 (6-month), and Elite is never month-to-month.
- [ ] The latency label is **3.0 s or less** for most cards. Note any that aren't.
- [ ] Typing a question in the ask bar gets a card within a few seconds.
- [ ] The three quick-prompt buttons each get a relevant card.
- [ ] The talk ratio, question count, and scores change as the call plays, and the summary appears after it ends.

## B2. Live coach (parrot mode)

- [ ] With **Live coach** checked, replay a sample. A new line appears after each prospect turn, streaming in within about 1 to 2 seconds of them finishing.
- [ ] Read a line out loud on a practice call. The card dims and shows **✓ You said it**.
- [ ] Short replies ("yeah", "okay") don't produce a new card, unless they're a question or an objection.
- [ ] Uncheck **Live coach**. Cards now appear only on objections and buying signals.

## C. Audio routing (10 min)

- [ ] `python main.py --list-devices` shows your headset mic and a LOOPBACK device for your headset or speakers.
- [ ] Start a **Live call**. The recording notice appears, and Start stays disabled until the box is ticked.
- [ ] Say a sentence. It appears as **Rep**, gray and italic while partial, then solid.
- [ ] Play a YouTube video of someone talking through the same output Meet uses. It appears as **Prospect**.
- [ ] Your voice doesn't also appear as Prospect, and the video doesn't appear as Rep.
- [ ] Watch the **You / Them** meters in the transcript header. Talking moves only **You**, and the video moves only **Them**. If **Them** moves when you talk, follow README → Troubleshooting → "Your words show up as Prospect."
- [ ] Click **⇄ Swap** once. All labels flip. Click it again to flip them back.

## D. Practice call with a colleague (15 min)

Call a teammate on **Google Meet**, or through your dialer for phone calls. Give them one of the sample scripts to improvise from. Don't let them read it word for word.

- [ ] Say the recording notice line at the start.
- [ ] They say "send me something." An auto card appears within about 3 seconds of them finishing.
- [ ] Press **Ctrl+Shift+Space** while Meet has focus. You get a card about the last ~20 seconds. (This checks the global hotkey.)
- [ ] **Stay on top:** click into Meet. The coach window stays visible on monitor 2.
- [ ] **Pause** for 20 seconds, then **Resume**. The timer pauses, and nothing is transcribed while paused.
- [ ] **Failure drill:** turn Wi-Fi off for 10 seconds, then on. The speech-to-text pill goes red, then back to OK. The app doesn't crash, and transcription resumes.
- [ ] End the call. The summary has wins, misses, and next steps that match what actually happened.
- [ ] Read `summary.md` and `coaching.jsonl`. Note the average `latency_s`.

## D2. Dialer link (if you installed Olly Coach Bridge)

- [ ] Open the coach, then HubSpot. The header says **Dialer: linked**.
- [ ] Click-to-dial a colleague from HubSpot. The pill shows **Dialer: calling (number)**.
- [ ] They answer. The coach pops up with **"They picked up: (number)"**. Tick the box and start.
- [ ] Hang up from the dialer. Coaching ends by itself and the summary appears.
- [ ] Dial a number that won't answer, or that goes to voicemail. Nothing records, or the call ends with **"Not saved because it reached voicemail."**
- [ ] If "picked up" or "ended" never triggered, send Claude the lines in `calls/.phone-events.log`.

## D2b. Google Meet

- [ ] After reloading the extension, join a test Meet with a colleague. The coach pops up with **"You joined: Google Meet · …"** and the recording notice, even if "Don't ask again" is on for the dialer.
- [ ] Both of you are transcribed and labeled correctly, and the **Them** meter moves when they talk.
- [ ] If the other side is silent, the app warns after about 25 seconds and names the device. Fix Meet's speaker setting as the warning says.
- [ ] Leave the meeting. Coaching ends by itself and the call is saved as **"Meet: (meeting name)"**.

## D3. Consent mode and joining late

- [ ] On a dialer call, click **Cancel** on "They picked up", wait 30 seconds, then press **Start call**. The notice shows the mid-call line, the call is titled with the number, and the score card says **Partial call (joined at 0:3x)**.
- [ ] If your dialer announces recording: tick **Don't ask again** once. On the next dialer call, coaching starts by itself when the prospect answers.
- [ ] **Call menu → Ask before each recording** turns the notice back on.

## E. Go / no-go

Go live with a real prospect only if:
- [ ] Most cards appeared in 3 seconds or less on the practice call.
- [ ] No card invented a price, term, guarantee, discount, or deadline.
- [ ] Both speakers were labeled correctly on Meet (and on your dialer, if you use one).
- [ ] You're comfortable saying the recording notice, and you know what to do if a prospect says no: end the recording, keep the call.

If latency is over target, try these in order: set `coach.thinking: between_tools`, lower `stt.endpointing_ms` to 200, and check your network.
