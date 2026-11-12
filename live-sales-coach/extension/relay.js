// Olly Coach Bridge: isolated content script. Forwards events from page-hook.js
// to the background worker, and says hello once so the coach shows "Dialer: linked".
(function () {
  window.addEventListener('message', (e) => {
    if (e.source !== window) return;
    const d = e.data;
    if (!d || d.__olly_coach_bridge !== true) return;
    const { event, type, source, phone, contact, callId, direction } = d;
    try {
      chrome.runtime.sendMessage({ kind: 'call-event', event, type, source, phone, contact, callId, direction });
    } catch (x) { /* extension reloaded; ignore */ }
  });

  if (window.top === window && location.hostname === 'app.hubspot.com') {
    try { chrome.runtime.sendMessage({ kind: 'call-event', event: 'hello' }); } catch (x) {}
  }
})();
