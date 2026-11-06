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
let lastKidScore = null;

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

/** Where a score sits between the last reward reached and the next one. */
function progressFor(score, rewards, defaultGoal) {
  const sorted = [...rewards].sort((a, b) => a.threshold - b.threshold);
  const next = sorted.find((r) => r.threshold > score);
  if (next) {
    const prev = sorted.filter((r) => r.threshold <= score).pop();
    const from = prev ? prev.threshold : 0;
    return { from, to: next.threshold, reward: next.name, fraction: (score - from) / (next.threshold - from) };
  }
  // No rewards yet (or all reached): fill a bar every `defaultGoal` points.
  const from = Math.floor(score / defaultGoal) * defaultGoal;
  return { from, to: from + defaultGoal, reward: null, fraction: (score - from) / defaultGoal };
}

const STAR_PATH = 'M12 2.5l2.9 6.1 6.6.8-4.9 4.6 1.3 6.6L12 17.3l-5.9 3.3 1.3-6.6-4.9-4.6 6.6-.8z';
function starsHtml(p, popIndex = -1) {
  const span = p.to - p.from;
  // Show one star per point when it fits; otherwise ten stars as a gauge.
  const slots = span <= 20 ? span : 10;
  const filled = span <= 20 ? Math.round(p.fraction * span) : Math.floor(p.fraction * 10);
  let out = '';
  for (let i = 0; i < slots; i++) {
    const cls = `star${i < filled ? ' on' : ''}${i === popIndex ? ' pop' : ''}`;
    out += `<svg class="${cls}" viewBox="0 0 24 24" aria-hidden="true"><path d="${STAR_PATH}"/></svg>`;
  }
  // Two even rows when there are many stars (e.g. 5 + 5), one row otherwise.
  const cols = slots > 6 ? Math.ceil(slots / 2) : slots;
  return { html: `<div class="stars" style="--cols:${cols}" role="img" aria-label="${filled} of ${slots} stars">${out}</div>`, filled };
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
  lastKidScore = null;
  boot();
}

// ---------- kid view ----------
async function showKid() {
  const render = async () => {
    const { kid, rewards, defaultGoal } = await api('/api/kid');
    const p = progressFor(kid.score, rewards, defaultGoal);
    const gained = lastKidScore !== null && kid.score > lastKidScore;
    const stars = starsHtml(p);
    const popIndex = gained ? stars.filled - 1 : -1;
    const toGo = p.to - kid.score;

    $app.innerHTML = `
      <section class="kid-view ${kid.young ? 'young' : ''}" style="--kid:${esc(kid.color)}">
        <div class="avatar" aria-hidden="true">${esc(kid.emoji)}</div>
        <h1>${esc(kid.name)}</h1>
        <div class="goal">
          ${starsHtml(p, popIndex).html}
          ${barHtml(p.fraction)}
          <p class="goal-label">${p.reward
            ? `${'⭐'.repeat(Math.min(toGo, 3))} ${toGo} more for <b>${esc(p.reward)}</b>`
            : kid.young ? '' : `${toGo} more ${toGo === 1 ? 'star' : 'stars'} to fill your bar!`}</p>
        </div>
        <p class="score"><b>${kid.score}</b> ${kid.score === 1 ? 'star' : 'stars'}</p>
        <button class="corner-btn" id="switch">Switch</button>
      </section>`;
    document.getElementById('switch').onclick = logout;
    if (gained) celebrate();
    lastKidScore = kid.score;
  };
  await render();
  poll(render, 5000);
}

function celebrate() {
  const burst = document.createElement('div');
  burst.className = 'burst';
  for (let i = 0; i < 14; i++) {
    const s = document.createElement('span');
    s.textContent = ['⭐', '🌟', '✨'][i % 3];
    s.style.left = '50%';
    s.style.top = '45%';
    const angle = (i / 14) * Math.PI * 2;
    s.style.setProperty('--dx', `${Math.cos(angle) * 260}px`);
    s.style.setProperty('--dy', `${Math.sin(angle) * 260}px`);
    burst.appendChild(s);
  }
  document.body.appendChild(burst);
  setTimeout(() => burst.remove(), 1500);
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
  const p = progressFor(k.score, dash.rewards, dash.defaultGoal);
  return `
    <div class="score-card" data-score-kid="${k.id}" style="--kid:${esc(k.color)}">
      <span class="emoji" aria-hidden="true">${esc(k.emoji)}</span>
      <span class="name">${esc(k.name)}</span>
      <span class="pts">${k.score}<small>points</small></span>
      ${barHtml(p.fraction)}
      <span class="next">${p.reward ? `${p.to - k.score} to ${esc(p.reward)}` : `${p.to - k.score} to fill the bar`}</span>
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
              <li><span>${esc(r.name)} · <b>${r.threshold}</b> pts</span>
              <button class="x" data-del-reward="${r.id}" aria-label="Remove ${esc(r.name)}">✕</button></li>`).join('')}</ul>`
          : `<p class="empty" style="margin-bottom:12px">No rewards yet. Add one when you’re ready. Until then, the bar fills every ${dash.defaultGoal} points.</p>`}
        <form class="reward-form" id="reward-form">
          <input name="name" placeholder="Reward (e.g. Ice cream trip)" maxlength="80" required>
          <input name="threshold" type="number" inputmode="numeric" min="1" placeholder="Points" required>
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
  const verb = direction > 0 ? `+${b.points}` : `−${b.points}`;
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
