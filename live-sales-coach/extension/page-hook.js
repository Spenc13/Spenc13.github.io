// Olly Coach Bridge: runs in the page (HubSpot + Aloware frames) at document_start.
// Watches the calling messages HubSpot and the Aloware dialer exchange and turns
// them into three simple events: ringing, answered, ended.
//
// It only reads message *types* (and a phone number / contact name when present).
// It never changes, blocks, or sends anything to HubSpot or Aloware.
(function () {
  if (window.__ollyCoachBridgeHooked) return;
  window.__ollyCoachBridgeHooked = true;

  // Message types from HubSpot's calling-extensions protocol and the Aloware widget.
  // "learn mode" also reports any other call-related type it sees (see relay.js),
  // so we can add markers if Aloware uses different names.
  const RINGING = new Set(['OUTGOING_CALL_STARTED', 'CLICK_TO_DIAL', 'DIAL_NUMBER',
                           'INCOMING_CALL', 'INCOMING_CALL_STARTED']);
  const ANSWERED = new Set(['CALL_ANSWERED']);
  const ENDED = new Set(['CALL_ENDED', 'CALL_COMPLETED', 'END_CALL', 'CALL_FAILED',
                         'INCOMING_CALL_ENDED', 'OUTGOING_CALL_ENDED']);
  const INTERESTING = /call|dial|ring|answer|hang|voicemail|disposition/i;

  function parse(x) {
    if (x && typeof x === 'object') return x;
    if (typeof x !== 'string' || x.length > 20000 || x.charAt(0) !== '{') return null;
    try { return JSON.parse(x); } catch (e) { return null; }
  }
  function typeOf(o) {
    if (!o || typeof o !== 'object') return null;
    const t = o.type || o.messageType || o.eventType || o.event || o.action;
    return typeof t === 'string' && t.length < 80 ? t : null;
  }
  function pick(o, keys, depth) {
    if (!o || typeof o !== 'object' || depth > 3) return null;
    for (const k of keys) {
      if (typeof o[k] === 'string' && o[k].trim()) return o[k].trim();
    }
    for (const v of Object.values(o)) {
      if (v && typeof v === 'object') {
        const r = pick(v, keys, depth + 1);
        if (r) return r;
      }
    }
    return null;
  }

  function handle(raw, source) {
    const o = parse(raw);
    if (!o || o.__olly_coach_bridge || o.__dialer_signal) return;
    const type = typeOf(o);
    if (!type) return;
    const upper = type.toUpperCase();
    let event = null;
    if (RINGING.has(upper)) event = 'ringing';
    else if (ANSWERED.has(upper)) event = 'answered';
    else if (ENDED.has(upper)) event = 'ended';
    else if (INTERESTING.test(type)) event = 'seen';
    if (!event) return;
    const msg = { __olly_coach_bridge: true, event, type, source };
    if (event !== 'seen') {
      msg.phone = pick(o, ['phoneNumber', 'toNumber', 'fromNumber', 'number', 'phone'], 0);
      msg.contact = pick(o, ['contactName', 'callerName', 'name'], 0);
      msg.callId = pick(o, ['callId', 'callSid', 'engagementId', 'externalCallId'], 0);
      if (event === 'ringing') msg.direction = upper.indexOf('INCOMING') === 0 ? 'inbound' : 'outbound';
    }
    window.postMessage(msg, window.location.origin);
  }

  // Cross-frame messages (the Aloware iframe and HubSpot talk this way).
  window.addEventListener('message', (e) => handle(e.data, 'postMessage'), true);

  // BroadcastChannel (HubSpot's cross-tab softphone channel).
  try {
    const NB = window.BroadcastChannel;
    if (NB) {
      const B = function (name) {
        const ch = new NB(name);
        try { ch.addEventListener('message', (e) => handle(e.data, 'broadcast:' + name)); } catch (x) {}
        return ch;
      };
      B.prototype = NB.prototype;
      window.BroadcastChannel = B;
      try {
        const own = new NB('hubspot-softphone-calling');
        own.addEventListener('message', (e) => handle(e.data, 'broadcast:hubspot-softphone-calling'));
      } catch (x) {}
    }
  } catch (e) {}

  // WebSocket frames (the dialer's live call-state updates). JSON frames only.
  try {
    const NW = window.WebSocket;
    const W = function (...a) {
      const ws = new NW(...a);
      try { ws.addEventListener('message', (e) => handle(e.data, 'websocket')); } catch (x) {}
      return ws;
    };
    W.prototype = NW.prototype;
    W.CONNECTING = NW.CONNECTING; W.OPEN = NW.OPEN; W.CLOSING = NW.CLOSING; W.CLOSED = NW.CLOSED;
    window.WebSocket = W;
  } catch (e) {}
})();
