# Olly Coach Bridge (Chrome extension)

A small companion extension that runs **alongside Olly Phone**, which it doesn't change or replace. It also watches **Google Meet**: when you join a meeting the coach pops up, and when you leave, coaching ends. It only checks whether Meet's in-call controls are on screen and reads the meeting name from the tab title.

It tells the Live Sales Coach app on your computer when a HubSpot/Aloware call:

- **rings:** the coach shows "Dialer: calling (512) 555-0123"
- **is answered:** the coach pops up with "They picked up: …" and the recording notice. One click starts coaching.
- **ends:** coaching ends and the call is saved, unless it went nowhere.

It only reads the *type* of the messages HubSpot and Aloware already pass around, plus the phone number or contact name when present. It never clicks, changes, or sends anything to HubSpot or Aloware. Events go only to `127.0.0.1:8765`, which is your own computer. If the coach app isn't open, they're dropped.

## Install (one time)

1. Open Chrome and go to `chrome://extensions`.
2. Turn on **Developer mode** (top right).
3. Click **Load unpacked** and choose this folder: `Spenc13.github.io\live-sales-coach\extension`.
4. "Olly Coach Bridge" appears next to Olly Phone. Leave both on.
5. Reload any open HubSpot tabs and the Olly Phone dialer window (or restart Chrome).

Open the coach app (`python main.py`) and then HubSpot. The coach's header should say **Dialer: linked**.

After a `git pull` that changes this folder, click the **↻ reload** icon on the extension card in `chrome://extensions`, then reload your HubSpot and Meet tabs. Chrome may show that the extension now also reads `meet.google.com`. That's the Meet watcher.

**Meet in another language:** the watcher looks for Meet's "Leave call" button. If your Meet is in a language other than English and the coach doesn't pop up when you join, tell Claude which language it is.

## If "answered" or "ended" doesn't trigger

HubSpot and Aloware don't publish exactly which message names they send, so the extension watches the standard HubSpot calling names (`CALL_ANSWERED`, `CALL_ENDED`, and others) and also records **every call-related message type it sees** in `calls/.phone-events.log`. That log holds type names only, never audio or numbers.

After a practice call, open that log (it's in the `calls` folder; turn on hidden items in File Explorer) and send the lines to Claude. Adding the right names is a one-line change in `page-hook.js`.

Until then, press **Start call** and **End call** yourself. Everything else works the same.
