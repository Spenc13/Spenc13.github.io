'use strict';
/* Home Dojo front end: login, kid view, parent dashboard. No framework. */

const $app = document.getElementById('app');
const $sheet = document.getElementById('sheet-root');
const $toast = document.getElementById('toast');

const GROUPS = {
  kind: { label: 'Kind', icon: '💗', color: 'var(--kind)' },
  helping: { label: 'Helping', icon: '🙌', color: 'var(--helping)' },
  listening: { label: 'Listening', icon: '👂', color: 'var(--listening)' },
};

let pollTimer = null;

// ---------- utilities ----------
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

async function api(path, opts = {}) {
  const res = await fetch(path, {
    method: opts.method || 'GET',
    headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'home-dojo' },
    body: opts.body ? JSON.stringify(opts.body) : undefined,
    credentials: 'same-origin',
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = new Error(data.error || `Error ${res.status}`);
    err.status = res.status;
    throw err;
  }
  return data;
}

function toast(msg) {
  $toast.textContent = msg;
  $toast.classList.add('show');
  clearTimeout(toast.t);
  toast.t = setTimeout(() => $toast.classList.remove('show'), 2600);
}

function stopPolling() {
  clearInterval(pollTimer);
  pollTimer = null;
}

function poll(fn, ms) {
  stopPolling();
  pollTimer = setInterval(() => { if (!document.hidden) fn().catch(handleAuthError); }, ms);
}

function handleAuthError(err) {
  if (err.status === 401) boot();
}

/** The cheapest reward still out of reach, if any. */
function nextReward(score, rewards) {
  return [...rewards].sort((a, b) => a.threshold - b.threshold).find((r) => r.threshold > score) || null;
}

const STAR_PATH = 'M12 2.5l2.9 6.1 6.6.8-4.9 4.6 1.3 6.6L12 17.3l-5.9 3.3 1.3-6.6-4.9-4.6 6.6-.8z';
const starSvg = (cls = 'star') => `<svg class="${cls}" viewBox="0 0 24 24" aria-hidden="true"><path d="${STAR_PATH}"/></svg>`;

/** A piggy bank in the girl's color with her star count painted on its side. */
function piggyHtml(score) {
  const digits = String(score).length;
  return `
    <svg class="piggy" viewBox="0 0 320 250" aria-hidden="true">
      <path class="pig-tail" d="M44 128c-22-4-30-26-14-34 14-7 22 14 8 20" fill="none" stroke-width="8" stroke-linecap="round"/>
      <rect class="pig-dark" x="78" y="180" width="34" height="50" rx="14"/>
      <rect class="pig-dark" x="200" y="180" width="34" height="50" rx="14"/>
      <path class="pig-dark" d="M196 66l18-46 30 42z"/>
      <ellipse class="pig-body" cx="160" cy="132" rx="122" ry="88"/>
      <ellipse class="pig-shine" cx="104" cy="84" rx="34" ry="13" transform="rotate(-18 104 84)"/>
      <rect x="128" y="46" width="64" height="12" rx="6" fill="#2b2140" opacity=".75"/>
      <ellipse class="pig-dark" cx="284" cy="138" rx="26" ry="32"/>
      <ellipse cx="277" cy="130" rx="5" ry="8" fill="#2b2140" opacity=".6"/>
      <ellipse cx="292" cy="146" rx="5" ry="8" fill="#2b2140" opacity=".6"/>
      <circle cx="238" cy="104" r="9" fill="#2b2140"/>
      <circle cx="241" cy="101" r="3" fill="#fff"/>
    </svg>
    <div class="pig-label d${Math.min(digits, 4)}" role="img" aria-label="${score} ${score === 1 ? 'star' : 'stars'} in the piggy bank">
      ${starSvg('star on')}<span>${score}</span>
    </div>`;
}

const barHtml = (fraction) => `<div class="bar"><i style="width:${Math.round(Math.min(1, Math.max(0, fraction)) * 100)}%"></i></div>`;

function timeAgo(iso) {
  const d = new Date(iso);
  const s = (Date.now() - d.getTime()) / 1000;
  if (s < 60) return 'just now';
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  const sameDay = d.toDateString() === new Date().toDateString();
  return sameDay
    ? d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })
    : d.toLocaleString([], { weekday: 'short', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
}

// ---------- boot ----------
async function boot() {
  stopPolling();
  closeSheet();
  try {
    const me = await api('/api/me');
    if (me.role === 'parent') return showDashboard();
    if (me.role === 'kid') return showKid();
    return showLogin();
  } catch {
    $app.innerHTML = `<div class="login"><div class="brand"><div class="logo">📡</div><h1>Can’t reach Home Dojo</h1><p>Check the Wi-Fi, then tap to try again.</p></div><button class="grownup-btn" id="retry">Try again</button></div>`;
    document.getElementById('retry').onclick = boot;
  }
}

// ---------- login ----------
async function showLogin() {
  const { kids } = await api('/api/login-options');
  $app.innerHTML = `
    <section class="login">
      <div class="brand"><div class="logo">🥋</div><h1>Home Dojo</h1><p>Kind · Helping · Listening</p></div>
      <p class="who-label">Who’s here?</p>
      <div class="kid-cards">
        ${kids.map((k) => `
          <button class="kid-card" data-kid="${k.id}" style="--kid:${esc(k.color)}" aria-label="${esc(k.name)}">
            <span class="emoji">${esc(k.emoji)}</span><span class="name">${esc(k.name)}</span>
          </button>`).join('')}
      </div>
      <button class="grownup-btn" id="grownup">🔒 Grown-ups</button>
    </section>`;

  $app.querySelectorAll('[data-kid]').forEach((btn) => {
    btn.onclick = async () => {
      const kid = kids.find((k) => k.id === Number(btn.dataset.kid));
      if (kid.needsPin) {
        showPinPad({
          title: `${kid.emoji} ${kid.name}`,
          submit: (pin) => api('/api/login/kid', { method: 'POST', body: { kidId: kid.id, pin } }),
        });
      } else {
        await api('/api/login/kid', { method: 'POST', body: { kidId: kid.id } });
        boot();
      }
    };
  });
  document.getElementById('grownup').onclick = () => showPinPad({
    title: '🔒 Grown-up PIN',
    submit: (pin) => api('/api/login/parent', { method: 'POST', body: { pin } }),
  });
}

function showPinPad({ title, submit }) {
  let pin = '';
  const maxLen = 8;
  $app.innerHTML = `
    <section class="login">
      <div class="brand"><h1 style="font-size:36px">${esc(title)}</h1></div>
      <div class="pinpad">
        <div class="pin-dots" id="dots"></div>
        <div class="pin-error" id="pin-error"></div>
        <div class="keys">
          ${[1, 2, 3, 4, 5, 6, 7, 8, 9].map((n) => `<button data-n="${n}">${n}</button>`).join('')}
          <button class="ghost" data-del aria-label="Delete">⌫</button>
          <button data-n="0">0</button>
          <button class="ghost" data-go aria-label="Enter">OK</button>
        </div>
      </div>
      <button class="back-link" id="back">← Back</button>
    </section>`;
  const dots = document.getElementById('dots');
  const errEl = document.getElementById('pin-error');
  const draw = () => {
    dots.innerHTML = Array.from({ length: Math.max(4, pin.length) }, (_, i) => `<span class="${i < pin.length ? 'on' : ''}"></span>`).join('');
  };
  draw();

  const go = async () => {
    if (pin.length < 4) return;
    try {
      await submit(pin);
      boot();
    } catch (err) {
      pin = '';
      draw();
      errEl.textContent = err.message;
      dots.classList.remove('shake');
      void dots.offsetWidth;
      dots.classList.add('shake');
    }
  };

  $app.querySelectorAll('[data-n]').forEach((b) => {
    b.onclick = () => { if (pin.length < maxLen) { pin += b.dataset.n; errEl.textContent = ''; draw(); } };
  });
  $app.querySelector('[data-del]').onclick = () => { pin = pin.slice(0, -1); draw(); };
  $app.querySelector('[data-go]').onclick = go;
  document.getElementById('back').onclick = boot;
}

async function logout() {
  await api('/api/logout', { method: 'POST' });
  boot();
}

// ---------- kid view ----------
let replaying = false;

async function showKid() {
  const render = async () => {
    if (replaying) return; // let the piggy finish its show
    const { kid, rewards, unseen = [] } = await api('/api/kid');
    if (location.hash === '#rewards') return renderKidRewards(kid, rewards); // replay waits for the piggy
    if (!unseen.length) return renderPiggy(kid, rewards);
    // Start from what she last saw, then play each change since.
    const start = unseen[0].score - unseen[0].applied;
    renderPiggy({ ...kid, score: start }, rewards, { hint: false });
    await replay(unseen);
    api('/api/kid/seen', { method: 'POST', body: { logId: unseen.at(-1).id } }).catch(() => {});
    if (location.hash !== '#rewards') renderPiggy(kid, rewards);
  };
  window.onhashchange = () => render().catch(handleAuthError);
  await render();
  poll(render, 5000);
}

function kidHeader(kid) {
  return `<header class="kid-head"><span class="mini-avatar" aria-hidden="true">${esc(kid.emoji)}</span><h1>${esc(kid.name)}</h1></header>`;
}

function renderPiggy(kid, rewards, { hint: showHint = true } = {}) {
  const next = nextReward(kid.score, rewards);
  const affordable = rewards.filter((r) => r.threshold <= kid.score).length;
  let hint = '';
  if (affordable) hint = `🎉 You have enough for ${affordable === 1 ? 'a reward' : `${affordable} rewards`}!`;
  else if (next) hint = `${next.threshold - kid.score} more for <b>${esc(next.name)}</b>`;

  $app.innerHTML = `
    <section class="kid-view ${kid.young ? 'young' : ''}" style="--kid:${esc(kid.color)}">
      ${kidHeader(kid)}
      <div class="piggy-wrap" id="piggy">
        <div class="replay-caption" aria-live="polite"></div>
        <div class="drops" aria-hidden="true"></div>
        ${piggyHtml(kid.score)}
      </div>
      <p class="piggy-hint">${hint && showHint && !kid.young ? hint : ''}</p>
      <button class="big-btn" id="to-rewards">🎁 Rewards${affordable ? ` <span class="dot">${affordable}</span>` : ''}</button>
      <button class="corner-btn" id="switch">Switch</button>
    </section>`;
  document.getElementById('switch').onclick = logout;
  document.getElementById('to-rewards').onclick = () => { location.hash = 'rewards'; };
  const piggy = document.getElementById('piggy');
  piggy.onclick = () => (replaying ? (replay.skip = true) : wiggle(piggy));
}

function renderKidRewards(kid, rewards) {
  const sorted = [...rewards].sort((a, b) => a.threshold - b.threshold);
  $app.innerHTML = `
    <section class="kid-view rewards-view ${kid.young ? 'young' : ''}" style="--kid:${esc(kid.color)}">
      ${kidHeader(kid)}
      <div class="mini-bank">🐷 ${starSvg('star on')} <b>${kid.score}</b></div>
      <h2 class="rewards-title">🎁 Rewards</h2>
      ${sorted.length ? `<ul class="reward-cards">${sorted.map((r) => {
        const ok = kid.score >= r.threshold;
        return `
          <li class="reward-card ${ok ? 'ok' : ''}">
            <span class="reward-name">${esc(r.name)}</span>
            <span class="price">${starSvg('star on')}<b>${r.threshold}</b></span>
            ${ok
              ? '<span class="reward-status">🎉 You have enough!</span>'
              : `<span class="reward-status">${barHtml(kid.score / r.threshold)}<small>${r.threshold - kid.score} more</small></span>`}
          </li>`;
      }).join('')}</ul>`
        : '<p class="no-rewards">No rewards yet.<br>Ask Mom or Dad! 💬</p>'}
      <button class="big-btn" id="to-piggy">🐷 My piggy bank</button>
      <button class="corner-btn" id="switch">Switch</button>
    </section>`;
  document.getElementById('switch').onclick = logout;
  document.getElementById('to-piggy').onclick = () => { history.length > 1 && location.hash ? history.back() : (location.hash = ''); };
}

function wiggle(el) {
  el.classList.remove('wiggle');
  void el.offsetWidth;
  el.classList.add('wiggle');
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function setPigCount(n) {
  const label = document.querySelector('.pig-label');
  if (!label) return;
  label.className = `pig-label d${Math.min(String(n).length, 4)} bump`;
  label.querySelector('span').textContent = n;
  label.setAttribute('aria-label', `${n} ${n === 1 ? 'star' : 'stars'} in the piggy bank`);
  setTimeout(() => label.classList.remove('bump'), 350);
}

/**
 * Play score changes one by one: stars drop into the slot for a plus and fly
 * out of it for a minus, with the behavior shown above the pig and the count
 * on its side ticking along. Tapping the pig skips to the end.
 */
async function replay(entries) {
  replaying = true;
  replay.skip = false;
  const piggy = document.getElementById('piggy');
  const drops = piggy.querySelector('.drops');
  const caption = piggy.querySelector('.replay-caption');
  const step = entries.length > 8 ? 650 : 1100; // speed up long catch-ups
  try {
    await sleep(500);
    for (const e of entries) {
      if (replay.skip || !document.body.contains(piggy)) break;
      const up = e.applied > 0;
      caption.innerHTML = `<span class="cap-emoji">${esc(e.emoji || '⭐')}</span>
        <span class="cap-text">${esc(e.behavior)}</span>
        <b class="${up ? 'up' : 'down'}">${up ? '+' : '−'}${Math.abs(e.applied)}</b>`;
      caption.classList.remove('show');
      void caption.offsetWidth;
      caption.classList.add('show');

      const n = Math.min(Math.abs(e.applied), 3);
      for (let i = 0; i < n; i++) {
        const d = document.createElement('span');
        d.className = up ? 'drop' : 'lift';
        d.innerHTML = starSvg('star on');
        d.style.animationDuration = `${step * 0.8}ms`;
        d.style.animationDelay = `${i * 120}ms`;
        drops.appendChild(d);
        setTimeout(() => d.remove(), step + i * 120 + 200);
      }
      // the count changes as the star lands in (or leaves) the slot
      await sleep(up ? step * 0.7 : step * 0.25);
      setPigCount(e.score);
      if (up) wiggle(piggy); else nudge(piggy);
      await sleep(up ? step * 0.3 : step * 0.75);
    }
  } finally {
    caption.classList.remove('show');
    replaying = false;
  }
}

function nudge(el) {
  el.classList.remove('nudge');
  void el.offsetWidth;
  el.classList.add('nudge');
}

// ---------- parent dashboard ----------
let dash = null;

async function showDashboard() {
  dash = await api('/api/dashboard');
  renderDashboard();
  poll(async () => {
    if ($sheet.firstChild || document.activeElement?.tagName === 'INPUT') return; // don't redraw mid-tap
    dash = await api('/api/dashboard');
    renderDashboard();
  }, 10000);
}

function scoreCardHtml(k) {
  const next = nextReward(k.score, dash.rewards);
  const affordable = dash.rewards.filter((r) => r.threshold <= k.score).length;
  let note = 'No rewards yet';
  if (affordable) note = `Has enough for ${affordable} ${affordable === 1 ? 'reward' : 'rewards'}`;
  else if (next) note = `${next.threshold - k.score} more for ${esc(next.name)}`;
  return `
    <div class="score-card" data-score-kid="${k.id}" style="--kid:${esc(k.color)}">
      <span class="emoji" aria-hidden="true">${esc(k.emoji)}</span>
      <span class="name">${esc(k.name)}</span>
      <span class="pts">${k.score}<small>${k.score === 1 ? 'star' : 'stars'}</small></span>
      <span class="next">🐷 ${note}</span>
    </div>`;
}

function renderDashboard() {
  const byGroup = Object.keys(GROUPS).map((g) => ({ g, items: dash.behaviors.filter((b) => b.grp === g) }));

  $app.innerHTML = `
    <div class="wrap">
      <header class="topbar">
        <div><h1>🥋 Home Dojo</h1><span class="hello">Hi, ${esc(dash.parent)}</span></div>
        <button class="pill-btn" id="logout">Log out</button>
      </header>

      <section class="scoreboard">${dash.kids.map(scoreCardHtml).join('')}</section>

      <section class="groups">
        ${byGroup.map(({ g, items }) => `
          <div class="group" style="--g:${GROUPS[g].color}">
            <h2>${GROUPS[g].icon} ${GROUPS[g].label}</h2>
            ${items.map((b) => `
              <div class="behavior">
                <button class="pm minus" data-b="${b.id}" data-d="-1" aria-label="Minus ${esc(b.label)}">−</button>
                <div class="label"><span aria-hidden="true">${esc(b.emoji)}</span>${esc(b.label)}</div>
                <button class="pm plus" data-b="${b.id}" data-d="1" aria-label="Plus ${esc(b.label)}">+</button>
              </div>`).join('')}
          </div>`).join('')}
      </section>

      <section class="panel">
        <h2>🎁 Rewards</h2>
        ${dash.rewards.length
          ? `<ul class="rewards">${dash.rewards.map((r) => `
              <li><span>${esc(r.name)} · ⭐ <b>${r.threshold}</b></span>
              <button class="x" data-del-reward="${r.id}" aria-label="Remove ${esc(r.name)}">✕</button></li>`).join('')}</ul>`
          : `<p class="empty" style="margin-bottom:12px">No rewards yet. Add one with its star price, and the girls will see it on their Rewards page.</p>`}
        <form class="reward-form" id="reward-form">
          <input name="name" placeholder="Reward (e.g. Ice cream trip)" maxlength="80" required>
          <input name="threshold" type="number" inputmode="numeric" min="1" placeholder="Stars" required>
          <button type="submit">Add</button>
        </form>
      </section>

      <section class="panel">
        <h2>📝 Recent activity</h2>
        ${dash.log.length ? `<ul class="log">${dash.log.map(logItemHtml).join('')}</ul>` : '<p class="empty">Nothing logged yet.</p>'}
      </section>
    </div>`;

  document.getElementById('logout').onclick = logout;
  $app.querySelectorAll('.pm').forEach((btn) => {
    btn.onclick = () => chooseKid(Number(btn.dataset.b), Number(btn.dataset.d));
  });
  $app.querySelectorAll('[data-del-reward]').forEach((btn) => {
    btn.onclick = async () => {
      if (!confirm('Remove this reward?')) return;
      dash.rewards = (await api(`/api/rewards/${btn.dataset.delReward}`, { method: 'DELETE' })).rewards;
      renderDashboard();
    };
  });
  document.getElementById('reward-form').onsubmit = async (e) => {
    e.preventDefault();
    const f = new FormData(e.target);
    try {
      dash.rewards = (await api('/api/rewards', {
        method: 'POST', body: { name: f.get('name'), threshold: Number(f.get('threshold')) },
      })).rewards;
      renderDashboard();
      toast('Reward added 🎁');
    } catch (err) {
      toast(err.message);
    }
  };
}

function logItemHtml(e) {
  const cls = e.applied > 0 ? 'up' : e.applied < 0 ? 'down' : 'zero';
  const sign = e.applied > 0 ? `+${e.applied}` : e.applied === 0 ? '0' : String(e.applied).replace('-', '−');
  const note = e.applied !== e.requested ? ' (already at 0)' : '';
  return `
    <li>
      <span class="delta ${cls}">${sign}</span>
      <span class="what">${esc(e.kidName)} · ${esc(e.behavior)}${note}
        <small>${GROUPS[e.group]?.label || esc(e.group)} · by ${esc(e.parent)} · now ${e.score}</small></span>
      <time datetime="${esc(e.createdAt)}" title="${esc(new Date(e.createdAt).toLocaleString())}">${timeAgo(e.createdAt)}</time>
    </li>`;
}

function chooseKid(behaviorId, direction) {
  const b = dash.behaviors.find((x) => x.id === behaviorId);
  const g = GROUPS[b.grp];
  const verb = direction > 0 ? `+${b.points} ⭐` : `−${b.points} ⭐`;
  $sheet.innerHTML = `
    <div class="sheet-backdrop" id="backdrop">
      <div class="sheet" role="dialog" aria-modal="true" aria-label="Choose daughter">
        <h2><span class="tag" style="background:${direction > 0 ? 'var(--plus)' : 'var(--minus)'}">${verb}</span>
          ${esc(b.emoji)} ${esc(b.label)} <small style="color:${g.color}">· ${g.label}</small></h2>
        <div class="kid-cards">
          ${dash.kids.map((k) => `
            <button class="kid-card" data-pick="${k.id}" style="--kid:${esc(k.color)}">
              <span class="emoji">${esc(k.emoji)}</span><span class="name">${esc(k.name)}</span>
            </button>`).join('')}
        </div>
        <button class="back-link" id="cancel">Cancel</button>
      </div>
    </div>`;
  document.getElementById('backdrop').onclick = (e) => { if (e.target.id === 'backdrop') closeSheet(); };
  document.getElementById('cancel').onclick = closeSheet;
  $sheet.querySelectorAll('[data-pick]').forEach((btn) => {
    btn.onclick = async () => {
      btn.disabled = true;
      try {
        const { entry, kids } = await api('/api/points', {
          method: 'POST', body: { kidId: Number(btn.dataset.pick), behaviorId, direction },
        });
        closeSheet();
        dash.kids = kids;
        dash.log = [entry, ...dash.log].slice(0, 30);
        renderDashboard();
        document.querySelector(`[data-score-kid="${entry.kidId}"]`)?.classList.add('bump');
        toast(entry.applied === 0 && entry.requested < 0
          ? `${entry.kidName} is already at 0`
          : `${entry.applied > 0 ? '+' : '−'}${Math.abs(entry.applied)} ${entry.behavior} · ${entry.kidName}`);
      } catch (err) {
        btn.disabled = false;
        toast(err.message);
        handleAuthError(err);
      }
    };
  });
}

function closeSheet() {
  $sheet.innerHTML = '';
}

document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeSheet(); });
document.addEventListener('visibilitychange', () => { if (!document.hidden && !$sheet.firstChild) boot(); });

if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => navigator.serviceWorker.register('/sw.js').catch(() => {}));
}

boot();
