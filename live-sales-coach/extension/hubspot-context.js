// Olly Coach Bridge: pre-call glossary from the HubSpot record you're calling from.
// Reads the contact's name and associated company from the open record page so the
// coach uses confirmed names instead of guessing from speech-to-text. Read-only.
(function () {
  if (window.top !== window || window.__ollyCoachContext) return;
  window.__ollyCoachContext = true;

  const RECORD = /\/(?:contacts\/\d+\/(?:record\/0-1|contact)\/\d+|contacts\/\d+\/(?:record\/0-2|company)\/\d+)/;
  const NAME_SELECTORS = [
    '[data-selenium-test="highlightTitle"]', '[data-test-id="highlight-title"]',
    '[data-selenium-test="profileHighlightTitle"]', 'h1[data-selenium-test]', 'header h1'
  ];

  function clean(t) {
    t = (t || '').replace(/\s+/g, ' ').trim();
    return t.length > 1 && t.length < 80 ? t : '';
  }

  function nameFromTitle() {
    let t = document.title || '';
    t = t.split(/\s[|–—-]\s/)[0];
    return /hubspot|contacts?$|companies$|^record$/i.test(t) ? '' : clean(t);
  }

  function readRecord() {
    const isCompany = /record\/0-2|\/company\//.test(location.pathname);
    let name = '';
    for (const sel of NAME_SELECTORS) {
      const el = document.querySelector(sel);
      if (el && clean(el.textContent)) { name = clean(el.textContent); break; }
    }
    name = name || nameFromTitle();
    let company = '';
    if (isCompany) {
      company = name; name = '';
    } else {
      const link = document.querySelector('a[href*="/record/0-2/"], a[href*="/company/"]');
      company = link ? clean(link.textContent) : '';
    }
    return { contact: name, company };
  }

  let last = '';
  setInterval(() => {
    if (!RECORD.test(location.pathname)) return;
    const r = readRecord();
    const key = r.contact + '|' + r.company;
    if (!r.contact && !r.company) return;
    if (key === last) return;
    last = key;
    try {
      chrome.runtime.sendMessage({ kind: 'call-event', event: 'context', source: 'hubspot',
                                   contact: r.contact || undefined, company: r.company || undefined });
    } catch (x) { /* extension reloaded */ }
  }, 2000);
})();
