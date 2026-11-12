// Olly Coach Bridge: background worker. Sends call events to the Live Sales Coach
// app on this computer (http://127.0.0.1:8765). If the app isn't open, events are
// simply dropped; nothing is stored and nothing leaves the computer.
const COACH_URL = 'http://127.0.0.1:8765/phone';   // match phone_bridge.port in config.yaml

const lastSent = new Map();   // dedupe key -> time
const SEEN_TTL = 10 * 60 * 1000;

function shouldSend(msg) {
  const now = Date.now();
  let key, ttl;
  if (msg.event === 'seen') { key = "seen:" + msg.type; ttl = SEEN_TTL; }
  else if (msg.event === 'hello') { key = "hello"; ttl = 60 * 1000; }
  else { key = msg.event + ":" + (msg.callId || ""); ttl = 3000; }
  const last = lastSent.get(key) || 0;
  if (now - last < ttl) return false;
  lastSent.set(key, now);
  if (lastSent.size > 500) lastSent.clear();
  return true;
}

chrome.runtime.onMessage.addListener((msg) => {
  if (!msg || msg.kind !== 'call-event' || !shouldSend(msg)) return;
  const body = {};
  for (const k of ['event', 'type', 'source', 'phone', 'contact', 'callId', 'direction']) {
    if (msg[k]) body[k] = String(msg[k]).slice(0, 120);
  }
  fetch(COACH_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-Olly-Coach': '1' },
    body: JSON.stringify(body)
  }).catch(() => { /* coach app not running */ });
});
