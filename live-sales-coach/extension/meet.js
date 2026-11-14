// Olly Coach Bridge: Google Meet watcher (top frame of meet.google.com).
// Tells the coach when you join a meeting ("answered") and when you leave ("ended").
// It only looks at whether the in-call controls are on screen and reads the
// meeting name from the tab title. It never clicks or changes anything in Meet.
(function () {
  if (window.top !== window || window.__ollyCoachMeet) return;
  window.__ollyCoachMeet = true;

  const LEAVE = [
    '[aria-label="Leave call"]', '[data-tooltip="Leave call"]',
    '[aria-label="Leave meeting"]', '[aria-label^="Leave call"]'
  ].join(',');
  const PRE_JOIN = /^(join now|ask to join|switch here|join here too|rejoin)$/i;

  function meetingCode() {
    const m = location.pathname.match(/^\/([a-z]{3,4}-[a-z]{3,4}-[a-z]{3,4})/i);
    return m ? m[1].toLowerCase() : null;
  }

  function meetingName() {
    const el = document.querySelector('[data-meeting-title]');
    let t = (el && (el.getAttribute('data-meeting-title') || el.textContent)) || document.title || '';
    t = t.replace(/^\s*(google\s+)?meet\s*[-–—:|]\s*/i, '').replace(/\s*[-–—|]\s*google meet\s*$/i, '').trim();
    const code = meetingCode();
    if (!t || t.toLowerCase() === code || /^meet$/i.test(t)) return null;
    return t.slice(0, 100);
  }

  function inCall() {
    if (!meetingCode()) return false;
    const buttons = document.querySelectorAll('button, [role="button"]');
    for (const b of buttons) {
      if (PRE_JOIN.test((b.textContent || '').trim())) return false;   // still in the lobby
    }
    return !!document.querySelector(LEAVE);
  }

  function send(event) {
    const msg = { kind: 'call-event', event, source: 'meet', callId: meetingCode() || undefined };
    const name = meetingName();
    if (name) msg.contact = name;
    try { chrome.runtime.sendMessage(msg); } catch (x) { /* extension reloaded */ }
  }

  try { chrome.runtime.sendMessage({ kind: 'call-event', event: 'hello', source: 'meet' }); } catch (x) {}

  let joined = false, onStreak = 0, offStreak = 0;
  setInterval(() => {
    const now = inCall();
    if (now) { onStreak++; offStreak = 0; } else { offStreak++; onStreak = 0; }
    if (!joined && onStreak >= 2) { joined = true; send('answered'); }         // in the call for ~1 s
    else if (joined && offStreak >= 6) { joined = false; send('ended'); }      // gone for ~3 s
  }, 500);

  window.addEventListener('pagehide', () => { if (joined) { joined = false; send('ended'); } });
})();
