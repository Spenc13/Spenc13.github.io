'use strict';
/* Home Dojo play area: the character maker, each girl's room, and visiting her sister.
 * Loaded before app.js; uses its helpers (api, esc, toast, $app, starSvg, kidHeader) at call time. */

const opt = (group, id) => CATALOG.avatar[group].find((o) => o.id === id) || CATALOG.avatar[group][0];
const INK = '#2b2140';

// ---------- character drawing ----------
/** An original cartoon kid built from the chosen options. headOnly crops to the face. */
function avatarSvg(a, { headOnly = false, cls = 'avatar-svg' } = {}) {
  const S = opt('skin', a.skin).color;
  const H = opt('hairColor', a.hairColor).color;
  const O = opt('outfitColor', a.outfitColor).color;
  const style = a.hairStyle;
  const pants = { dress: S, tee: '#3d5a9e', overalls: O, hoodie: '#4b4560' }[a.outfit] || '#3d5a9e';
  const parts = [];

  // hair behind the head
  const back = {
    long: '<path d="M26 54Q26 18 60 18Q94 18 94 54L97 122Q78 130 60 126Q42 130 23 122Z"/>',
    bob: '<path d="M25 56Q25 18 60 18Q95 18 95 56L95 88Q80 94 60 92Q40 94 25 88Z"/>',
    pigtails: '<circle cx="21" cy="64" r="15"/><circle cx="99" cy="64" r="15"/><circle cx="18" cy="86" r="11"/><circle cx="102" cy="86" r="11"/>',
    ponytail: '<ellipse cx="96" cy="50" rx="13" ry="28" transform="rotate(22 96 50)"/>',
    bun: '<circle cx="60" cy="17" r="15"/>',
    curly: [[28, 40], [24, 60], [28, 80], [92, 40], [96, 60], [92, 80], [40, 24], [80, 24]]
      .map(([x, y]) => `<circle cx="${x}" cy="${y}" r="14"/>`).join(''),
  }[style] || '';
  parts.push(`<g fill="${H}">${back}</g>`);

  if (!headOnly) {
    // legs + shoes
    parts.push(`<rect x="47" y="130" width="11" height="28" rx="5" fill="${pants}"/><rect x="62" y="130" width="11" height="28" rx="5" fill="${pants}"/>`);
    if (a.outfit === 'dress') parts.push(`<rect x="47" y="138" width="11" height="20" rx="5" fill="${S}"/><rect x="62" y="138" width="11" height="20" rx="5" fill="${S}"/>`);
    parts.push(`<ellipse cx="51" cy="159" rx="9" ry="5" fill="${INK}"/><ellipse cx="69" cy="159" rx="9" ry="5" fill="${INK}"/>`);
    // arms
    const sleeve = a.outfit === 'dress' ? S : O;
    parts.push(`<path d="M43 92Q31 108 32 124M77 92Q89 108 88 124" stroke="${sleeve}" stroke-width="9" stroke-linecap="round" fill="none"/>`);
    parts.push(`<circle cx="32" cy="126" r="5.5" fill="${S}"/><circle cx="88" cy="126" r="5.5" fill="${S}"/>`);
    // body / outfit
    const body = {
      dress: `<path d="M44 86Q60 80 76 86L93 140Q60 149 27 140Z" fill="${O}"/><circle cx="43" cy="92" r="7" fill="${O}"/><circle cx="77" cy="92" r="7" fill="${O}"/><path d="M52 87Q60 95 68 87" stroke="#fff" stroke-width="4" fill="none" stroke-linecap="round"/><path d="M33 132Q60 140 87 132" stroke="#fff" stroke-width="3" fill="none" opacity=".6"/>`,
      tee: `<path d="M41 88Q60 82 79 88L81 124L39 124Z" fill="${O}"/><path d="M40 120H80V138H40Z" fill="${pants}"/><path d="M60 98l2.6 5.4 5.9.7-4.3 4 1.1 5.8L60 111l-5.3 2.9 1.1-5.8-4.3-4 5.9-.7z" fill="#fff" opacity=".85"/>`,
      overalls: `<path d="M41 88Q60 82 79 88L81 124L39 124Z" fill="#fff"/><rect x="47" y="98" width="26" height="26" rx="4" fill="${O}"/><path d="M48 99L44 88M72 99L76 88" stroke="${O}" stroke-width="4" stroke-linecap="round"/><path d="M39 118H81V138H39Z" fill="${O}"/><circle cx="52" cy="104" r="2" fill="#fff"/><circle cx="68" cy="104" r="2" fill="#fff"/>`,
      hoodie: `<path d="M39 88Q60 80 81 88L84 128L36 128Z" fill="${O}"/><rect x="47" y="110" width="26" height="13" rx="6" fill="#000" opacity=".12"/><path d="M55 88V100M65 88V100" stroke="#fff" stroke-width="2" stroke-linecap="round"/><path d="M40 126H80V138H40Z" fill="${pants}"/>`,
    }[a.outfit];
    parts.push(body);
  }

  // neck, ears, head
  parts.push(`<rect x="54" y="76" width="12" height="12" fill="${S}"/><circle cx="28" cy="58" r="6" fill="${S}"/><circle cx="92" cy="58" r="6" fill="${S}"/><circle cx="60" cy="54" r="32" fill="${S}"/>`);

  // hair in front
  const fringe = '<path d="M28 52Q28 20 60 20Q92 20 92 52Q84 36 67 35Q62 44 54 36Q38 38 28 52Z"/>';
  const front = {
    short: '<path d="M27 54Q26 18 60 18Q94 18 93 54Q88 33 60 31Q34 33 27 54Z"/>',
    bob: '<path d="M27 56Q26 18 60 18Q94 18 93 56L89 42Q60 37 31 42Z"/>',
    curly: [[36, 30], [48, 22], [60, 20], [72, 22], [84, 30]].map(([x, y]) => `<circle cx="${x}" cy="${y}" r="12"/>`).join(''),
  }[style] || fringe;
  parts.push(`<g fill="${H}">${front}</g>`);
  if (style === 'pigtails') parts.push(`<circle cx="31" cy="48" r="4.5" fill="${O}"/><circle cx="89" cy="48" r="4.5" fill="${O}"/>`);

  // face
  const eye = (x, kind) => ({
    round: `<circle cx="${x}" cy="58" r="4.6" fill="${INK}"/><circle cx="${x + 1.6}" cy="56.4" r="1.6" fill="#fff"/>`,
    happy: `<path d="M${x - 5} 60Q${x} 53 ${x + 5} 60" stroke="${INK}" stroke-width="3" fill="none" stroke-linecap="round"/>`,
    sparkle: `<circle cx="${x}" cy="58" r="6.2" fill="${INK}"/><circle cx="${x + 2}" cy="55.6" r="2.2" fill="#fff"/><circle cx="${x - 2}" cy="60.5" r="1.1" fill="#fff"/>`,
  }[kind]);
  const eyes = a.eyes === 'wink' ? eye(48, 'round') + eye(72, 'happy') : eye(48, a.eyes) + eye(72, a.eyes);
  parts.push(eyes);
  parts.push('<ellipse cx="41" cy="68" rx="5.5" ry="3.2" fill="#ff7a9a" opacity=".35"/><ellipse cx="79" cy="68" rx="5.5" ry="3.2" fill="#ff7a9a" opacity=".35"/>');
  parts.push({
    smile: `<path d="M52 70Q60 78 68 70" stroke="${INK}" stroke-width="3" fill="none" stroke-linecap="round"/>`,
    grin: `<path d="M50 69Q60 83 70 69Z" fill="${INK}"/><path d="M52.5 70H67.5L66 73.5H54Z" fill="#fff"/>`,
    open: `<ellipse cx="60" cy="73" rx="5" ry="6" fill="${INK}"/><ellipse cx="60" cy="76.5" rx="3.4" ry="2.4" fill="#ff7a9a"/>`,
    tongue: `<path d="M52 70Q60 78 68 70" stroke="${INK}" stroke-width="3" fill="none" stroke-linecap="round"/><path d="M56.5 74Q60 81 63.5 74Z" fill="#ff7a9a"/>`,
  }[a.mouth]);

  // extras
  parts.push({
    none: '',
    bow: '<path d="M83 26L71 17V35ZM83 26L95 17V35Z" fill="#ff4f8b"/><circle cx="83" cy="26" r="4.5" fill="#d6336c"/>',
    crown: '<path d="M42 25L46 8L53 18L60 4L67 18L74 8L78 25Z" fill="#ffc531" stroke="#e3a400" stroke-width="2" stroke-linejoin="round"/><circle cx="60" cy="17" r="2.6" fill="#ff4f8b"/>',
    glasses: `<g stroke="${INK}" stroke-width="2.6" fill="#fff" fill-opacity=".25"><circle cx="48" cy="58" r="8.5"/><circle cx="72" cy="58" r="8.5"/></g><path d="M56.5 57H63.5" stroke="${INK}" stroke-width="2.6"/>`,
    flower: '<g fill="#fff">' + [0, 72, 144, 216, 288].map((d) => `<circle cx="${86 + 5.5 * Math.cos((d * Math.PI) / 180)}" cy="${32 + 5.5 * Math.sin((d * Math.PI) / 180)}" r="4.6"/>`).join('') + '</g><circle cx="86" cy="32" r="3.6" fill="#ffc531"/>',
    catears: `<path d="M30 36L32 8L52 24ZM90 36L88 8L68 24Z" fill="${H}"/><path d="M34 30L35 15L45 24ZM86 30L85 15L75 24Z" fill="#ff9fbd"/>`,
    headband: `<path d="M29 44Q60 14 91 44" stroke="${O}" stroke-width="6" fill="none" stroke-linecap="round"/>`,
  }[a.accessory] || '');

  const vb = headOnly ? '16 0 88 88' : '0 0 120 166';
  return `<svg class="${cls}" viewBox="${vb}" aria-hidden="true">${parts.join('')}</svg>`;
}

const DOLL = { skin: 's1', hairStyle: 'long', hairColor: 'blonde', eyes: 'happy', mouth: 'smile', outfit: 'dress', outfitColor: 'teal', accessory: 'bow' };

// ---------- furniture drawing ----------
function artSvg(art, tint) {
  const wood = '#c98b5a';
  const dark = '#9a6a3f';
  const svg = (vb, body) => `<svg viewBox="${vb}" aria-hidden="true">${body}</svg>`;
  switch (art) {
    case 'bed': return svg('0 0 140 80', `<rect x="2" y="6" width="20" height="72" rx="6" fill="${dark}"/><rect x="122" y="34" width="15" height="44" rx="5" fill="${dark}"/><rect x="14" y="58" width="114" height="12" fill="${wood}"/><rect x="14" y="40" width="114" height="22" rx="6" fill="#fff"/><path d="M50 35H124A4 4 0 0 1 128 39V64H50Z" fill="${tint}"/><path d="M50 46H128" stroke="#fff" stroke-width="3" opacity=".5"/><rect x="22" y="28" width="30" height="16" rx="8" fill="#fff" stroke="#e6dccb" stroke-width="2"/>`);
    case 'rug': return svg('0 0 140 36', `<ellipse cx="70" cy="18" rx="68" ry="16" fill="${tint}" opacity=".55"/><ellipse cx="70" cy="18" rx="52" ry="10.5" fill="none" stroke="#fff" stroke-width="3" stroke-dasharray="6 5"/>`);
    case 'lamp': return svg('0 0 40 120', `<path d="M8 34H32L26 6H14Z" fill="#ffd76a" stroke="#e3a400" stroke-width="2"/><rect x="18.5" y="34" width="3" height="76" fill="#6b5a4a"/><ellipse cx="20" cy="113" rx="13" ry="5" fill="#6b5a4a"/>`);
    case 'dresser': return svg('0 0 90 86', `<rect x="0" y="4" width="90" height="9" rx="3" fill="${dark}"/><rect x="4" y="12" width="82" height="66" fill="${wood}"/>${[0, 1, 2].map((i) => `<rect x="10" y="${18 + i * 20}" width="70" height="16" rx="3" fill="#dfa972"/><circle cx="45" cy="${26 + i * 20}" r="2.8" fill="${dark}"/>`).join('')}<rect x="8" y="78" width="8" height="8" fill="${dark}"/><rect x="74" y="78" width="8" height="8" fill="${dark}"/>`);
    case 'bookshelf': {
      const books = (y) => ['#ff6fa8', '#3b82f6', '#22b07d', '#ffc531', '#7c5cff', '#f25454'].map((c, i) => `<rect x="${10 + i * 8.5}" y="${y - (i % 2 ? 22 : 26)}" width="7" height="${i % 2 ? 22 : 26}" rx="1.5" fill="${c}"/>`).join('');
      return svg('0 0 70 110', `<rect width="70" height="110" rx="3" fill="${dark}"/><rect x="5" y="5" width="60" height="100" fill="#7d5230"/><rect x="5" y="36" width="60" height="4" fill="${dark}"/><rect x="5" y="70" width="60" height="4" fill="${dark}"/>${books(36)}${books(70)}${books(105)}`);
    }
    case 'tv': return svg('0 0 110 100', `<rect x="8" y="2" width="94" height="60" rx="7" fill="${INK}"/><rect x="13" y="7" width="84" height="50" rx="3" fill="#4fa3ff"/><path d="M13 57L40 30L60 50L72 40L97 57Z" fill="#22b07d"/><circle cx="80" cy="22" r="7" fill="#ffc531"/><rect x="50" y="62" width="10" height="9" fill="${INK}"/><rect x="4" y="70" width="102" height="28" rx="4" fill="${wood}"/><path d="M55 72V96" stroke="${dark}" stroke-width="2"/><circle cx="49" cy="84" r="2" fill="${dark}"/><circle cx="61" cy="84" r="2" fill="${dark}"/>`);
    case 'console': return svg('0 0 90 54', `<rect x="4" y="8" width="46" height="18" rx="5" fill="#ece8f5" stroke="#b9b2cc" stroke-width="2"/><circle cx="40" cy="17" r="2.5" fill="#22b07d"/><rect x="10" y="14" width="18" height="6" rx="2" fill="#cfc8e0"/><path d="M50 22Q60 26 58 36" stroke="#b9b2cc" stroke-width="2" fill="none"/><path d="M50 36Q42 36 42 45Q42 53 50 51L57 46H73L80 51Q88 53 88 45Q88 36 80 36Z" fill="${INK}"/><circle cx="51" cy="42" r="3" fill="#fff" opacity=".7"/><circle cx="77" cy="40" r="2.3" fill="#f25454"/><circle cx="81" cy="44" r="2.3" fill="#3b82f6"/>`);
    case 'desk': return svg('0 0 130 80', `<rect x="0" y="18" width="130" height="9" rx="3" fill="${wood}"/><rect x="6" y="27" width="8" height="52" fill="${dark}"/><rect x="84" y="27" width="40" height="34" fill="${wood}"/><rect x="88" y="31" width="32" height="12" rx="2" fill="#dfa972"/><rect x="88" y="46" width="32" height="12" rx="2" fill="#dfa972"/><circle cx="104" cy="37" r="2" fill="${dark}"/><circle cx="104" cy="52" r="2" fill="${dark}"/><rect x="116" y="61" width="8" height="18" fill="${dark}"/><rect x="20" y="4" width="10" height="14" rx="2" fill="${tint}"/><path d="M23 4L22 -4M27 4L29 -3" stroke="${INK}" stroke-width="1.6"/>`);
    case 'beanbag': return svg('0 0 90 60', `<path d="M10 55Q2 30 30 16Q52 4 70 18Q92 34 82 55Q46 63 10 55Z" fill="${tint}"/><path d="M26 24Q38 14 52 16" stroke="#fff" stroke-width="5" fill="none" stroke-linecap="round" opacity=".45"/>`);
    case 'fishtank': return svg('0 0 100 92', `<rect x="6" y="60" width="88" height="30" rx="3" fill="${wood}"/><rect x="4" y="4" width="92" height="56" rx="5" fill="#bfe7ff" stroke="#7ab8d9" stroke-width="3"/><rect x="6" y="48" width="88" height="10" fill="#f3dca0"/><path d="M20 48Q16 34 22 22M24 48Q28 36 25 28" stroke="#22b07d" stroke-width="3" fill="none"/><g fill="#ff9f1c"><ellipse cx="50" cy="26" rx="9" ry="6"/><path d="M41 26L34 20V32Z"/></g><g fill="#ff6fa8"><ellipse cx="74" cy="40" rx="7" ry="4.5"/><path d="M81 40L87 35V45Z"/></g><circle cx="56" cy="24" r="1.4" fill="${INK}"/><circle cx="70" cy="39" r="1.2" fill="${INK}"/><circle cx="58" cy="14" r="2" fill="#fff"/><circle cx="62" cy="9" r="1.5" fill="#fff"/>`);
    case 'doll': return avatarSvg(DOLL, { cls: '' });
    default: return '';
  }
}

function itemVisual(def, tint) {
  return def.emoji ? `<span class="emoji-art">${def.emoji}</span>` : artSvg(def.art, tint);
}

// ---------- room ----------
const WINDOW = '<svg class="room-window" viewBox="0 0 80 70" aria-hidden="true"><rect x="2" y="2" width="76" height="66" rx="6" fill="#fff"/><rect x="8" y="8" width="64" height="54" rx="3" fill="#bfe3ff"/><circle cx="56" cy="22" r="7" fill="#ffd76a"/><ellipse cx="26" cy="24" rx="12" ry="6" fill="#fff"/><path d="M40 8V62M8 35H72" stroke="#fff" stroke-width="4"/></svg>';

function roomHtml(room, avatar, tint, { editable }) {
  const wall = CATALOG.walls.find((w) => w.id === room.wall) || CATALOG.walls[0];
  const floor = CATALOG.floors.find((f) => f.id === room.floor) || CATALOG.floors[0];
  const things = room.items.map((it) => {
    const def = CATALOG.items.find((d) => d.id === it.id);
    if (!def) return '';
    const z = def.layer === 'floor' ? 1 : 10 + Math.round(it.y);
    return `<div class="thing ${def.emoji ? 'is-emoji' : ''}" data-thing="${def.id}" style="left:${it.x}%;top:${it.y}%;width:${def.size}%;z-index:${z};--size:${def.size}"
      role="img" aria-label="${esc(def.name)}">${itemVisual(def, tint)}${editable ? `<button class="thing-x" data-remove="${def.id}" aria-label="Take out ${esc(def.name)}">✕</button>` : ''}</div>`;
  }).join('');
  const me = `<div class="thing me" data-thing="me" style="left:${room.me.x}%;top:${room.me.y}%;z-index:${10 + Math.round(room.me.y)}">${avatarSvg(avatar)}</div>`;
  return `
    <div class="room ${editable ? 'editable' : ''}" id="room" style="--wall:${wall.color};--floor:${floor.color};--tint:${esc(tint)}">
      <div class="room-wall"></div>
      <div class="room-floor floor-${floor.id}"></div>
      ${WINDOW}
      ${things}${me}
    </div>`;
}

let playState = null;
let saveTimer = null;
let pendingSave = null;

/** Save shortly after the last change; the snapshot is taken now so later page changes can't alter it. */
function queueSave(kind) {
  const req = kind === 'room'
    ? ['/api/room', { room: JSON.parse(JSON.stringify(playState.room)) }]
    : ['/api/avatar', { avatar: { ...playState.avatar } }];
  pendingSave = { ...(pendingSave || {}), [kind]: req };
  clearTimeout(saveTimer);
  saveTimer = setTimeout(flushSave, 400);
}

/** Send any waiting save right away (called before leaving a page). */
async function flushSave() {
  clearTimeout(saveTimer);
  const todo = pendingSave;
  pendingSave = null;
  if (!todo) return;
  for (const [path, body] of Object.values(todo)) {
    try {
      await api(path, { method: 'PUT', body });
    } catch (err) {
      toast(err.message);
    }
  }
}

async function sisterOf(kidId) {
  const { kids } = await api('/api/login-options');
  return kids.find((k) => k.id !== kidId) || null;
}

async function showRoom() {
  const data = await api('/api/room');
  const sister = await sisterOf(data.kid.id);
  playState = { kid: data.kid, room: data.room, avatar: data.kid.avatar, earned: data.earned, tab: playState?.tab || 'things', selected: null };
  renderRoom(sister, data.madeCharacter);
}

function renderRoom(sister, madeCharacter = true) {
  const { kid, room, earned } = playState;
  const nextLocked = CATALOG.items.filter((i) => i.unlock > earned).sort((a, b) => a.unlock - b.unlock)[0];
  const placed = new Set(room.items.map((i) => i.id));

  $app.innerHTML = `
    <section class="kid-view play-view ${kid.young ? 'young' : ''}" style="--kid:${esc(kid.color)}">
      ${kidHeader(kid)}
      ${roomHtml(room, playState.avatar, kid.color, { editable: true })}
      <div class="play-actions">
        <button class="pill-big" id="go-me">${madeCharacter ? '✏️ Change me' : '✨ Make my character'}</button>
        ${sister ? `<button class="pill-big" id="go-visit">👀 Visit ${esc(sister.name)}</button>` : ''}
        <button class="pill-big" id="go-piggy">🐷 Piggy bank</button>
      </div>
      <div class="tray">
        <div class="tray-tabs" role="tablist">
          <button role="tab" class="${playState.tab === 'things' ? 'on' : ''}" data-tab="things">🧸 Things</button>
          <button role="tab" class="${playState.tab === 'paint' ? 'on' : ''}" data-tab="paint">🎨 Paint</button>
        </div>
        ${playState.tab === 'things' ? `
          <p class="tray-note">${starSvg('star on')} <b>${earned}</b> stars earned${nextLocked ? ` · ${nextLocked.unlock - earned} more to unlock <b>${esc(nextLocked.name)}</b>` : ' · everything is unlocked!'}</p>
          <div class="tray-grid">
            ${CATALOG.items.map((d) => {
              const locked = d.unlock > earned;
              return `<button class="tray-item ${locked ? 'locked' : ''} ${placed.has(d.id) ? 'placed' : ''}" data-item="${d.id}" aria-label="${esc(d.name)}${locked ? `, locked, needs ${d.unlock} stars` : placed.has(d.id) ? ', in your room' : ''}">
                <span class="tray-art">${itemVisual(d, kid.color)}</span>
                <span class="tray-name">${esc(d.name)}</span>
                ${locked ? `<span class="lock">🔒 ${d.unlock}</span>` : placed.has(d.id) ? '<span class="check">✓</span>' : ''}
              </button>`;
            }).join('')}
          </div>` : `
          <p class="tray-label">Walls</p>
          <div class="swatches">${CATALOG.walls.map((w) => `<button class="swatch ${room.wall === w.id ? 'on' : ''}" data-wall="${w.id}" style="background:${w.color}" aria-label="${w.id} walls"></button>`).join('')}</div>
          <p class="tray-label">Floor</p>
          <div class="swatches">${CATALOG.floors.map((f) => `<button class="swatch floor-${f.id} ${room.floor === f.id ? 'on' : ''}" data-floor="${f.id}" style="--floor:${f.color}" aria-label="${f.id} floor"></button>`).join('')}</div>`}
      </div>
      <button class="corner-btn" id="switch">Switch</button>
    </section>`;

  document.getElementById('switch').onclick = logout;
  document.getElementById('go-me').onclick = () => { location.hash = 'me'; };
  document.getElementById('go-piggy').onclick = () => { location.hash = ''; };
  if (sister) document.getElementById('go-visit').onclick = () => { location.hash = `visit-${sister.id}`; };
  $app.querySelectorAll('[data-tab]').forEach((b) => { b.onclick = () => { playState.tab = b.dataset.tab; renderRoom(sister, madeCharacter); }; });

  $app.querySelectorAll('[data-item]').forEach((b) => {
    b.onclick = () => {
      const def = CATALOG.items.find((d) => d.id === b.dataset.item);
      if (def.unlock > earned) return toast(`Earn ${def.unlock - earned} more ${def.unlock - earned === 1 ? 'star' : 'stars'} to unlock ${def.name}!`);
      const i = room.items.findIndex((it) => it.id === def.id);
      if (i >= 0) room.items.splice(i, 1);
      else room.items.push({ id: def.id, x: def.spot[0], y: def.spot[1] });
      queueSave('room');
      renderRoom(sister, madeCharacter);
    };
  });
  $app.querySelectorAll('[data-wall]').forEach((b) => { b.onclick = () => { room.wall = b.dataset.wall; queueSave('room'); renderRoom(sister, madeCharacter); }; });
  $app.querySelectorAll('[data-floor]').forEach((b) => { b.onclick = () => { room.floor = b.dataset.floor; queueSave('room'); renderRoom(sister, madeCharacter); }; });
  $app.querySelectorAll('[data-remove]').forEach((b) => {
    b.onpointerdown = (e) => e.stopPropagation();
    b.onclick = () => {
      room.items = room.items.filter((it) => it.id !== b.dataset.remove);
      queueSave('room');
      renderRoom(sister, madeCharacter);
    };
  });
  enableDragging(document.getElementById('room'));
}

/** Drag things around the room; a tap without moving selects it (showing its ✕). */
function enableDragging(roomEl) {
  roomEl.querySelectorAll('.thing').forEach((el) => {
    el.onpointerdown = (e) => {
      if (e.button) return;
      e.preventDefault();
      el.setPointerCapture(e.pointerId);
      const rect = roomEl.getBoundingClientRect();
      const startX = e.clientX;
      const startY = e.clientY;
      const startLeft = parseFloat(el.style.left);
      const startTop = parseFloat(el.style.top);
      let moved = false;
      el.classList.add('dragging');
      el.onpointermove = (ev) => {
        const dx = ev.clientX - startX;
        const dy = ev.clientY - startY;
        if (!moved && Math.hypot(dx, dy) < 6) return;
        moved = true;
        const x = Math.min(100, Math.max(0, startLeft + (dx / rect.width) * 100));
        const y = Math.min(100, Math.max(12, startTop + (dy / rect.height) * 100));
        el.style.left = `${x}%`;
        el.style.top = `${y}%`;
        el.style.zIndex = el.dataset.thing === 'rug' ? 1 : 10 + Math.round(y);
      };
      el.onpointerup = el.onpointercancel = () => {
        el.onpointermove = null;
        el.classList.remove('dragging');
        const x = Math.round(parseFloat(el.style.left) * 10) / 10;
        const y = Math.round(parseFloat(el.style.top) * 10) / 10;
        if (moved) {
          if (el.dataset.thing === 'me') playState.room.me = { x, y };
          else {
            const it = playState.room.items.find((i) => i.id === el.dataset.thing);
            if (it) Object.assign(it, { x, y });
          }
          queueSave('room');
        } else if (el.dataset.thing !== 'me') {
          const was = el.classList.contains('selected');
          roomEl.querySelectorAll('.thing.selected').forEach((t) => t.classList.remove('selected'));
          if (!was) el.classList.add('selected');
        } else {
          wiggle(el);
        }
      };
    };
  });
  roomEl.addEventListener('pointerdown', (e) => {
    if (e.target === roomEl || e.target.closest('.room-wall, .room-floor, .room-window')) {
      roomEl.querySelectorAll('.thing.selected').forEach((t) => t.classList.remove('selected'));
    }
  });
}

async function showVisit(sisterId) {
  const data = await api(`/api/room?kid=${sisterId}`);
  const me = await api('/api/kid');
  const { kid, room } = data;
  $app.innerHTML = `
    <section class="kid-view play-view ${me.kid.young ? 'young' : ''}" style="--kid:${esc(kid.color)}">
      <header class="kid-head"><span class="mini-avatar" aria-hidden="true">${avatarSvg(kid.avatar, { headOnly: true })}</span><h1>${esc(kid.name)}’s room</h1></header>
      ${roomHtml(room, kid.avatar, kid.color, { editable: false })}
      <p class="visit-note">👀 Just looking! Only ${esc(kid.name)} can change this room.</p>
      <div class="play-actions"><button class="pill-big" id="go-room">🏠 Back to my room</button></div>
      <button class="corner-btn" id="switch">Switch</button>
    </section>`;
  document.getElementById('switch').onclick = logout;
  document.getElementById('go-room').onclick = () => { location.hash = 'room'; };
  // things wiggle when tapped, but nothing moves
  $app.querySelectorAll('.thing').forEach((t) => { t.onclick = () => wiggle(t); });
}

// ---------- character maker ----------
const MAKER_TABS = [
  ['skin', '🖐️', 'Skin'], ['hairStyle', '💇', 'Hair'], ['hairColor', '🖍️', 'Hair color'], ['eyes', '👀', 'Eyes'],
  ['mouth', '😄', 'Mouth'], ['outfit', '👗', 'Clothes'], ['outfitColor', '🌈', 'Clothes color'], ['accessory', '👑', 'Extras'],
];

async function showMaker() {
  const data = await api('/api/room');
  playState = { ...(playState || {}), kid: data.kid, avatar: { ...data.kid.avatar }, makerTab: playState?.makerTab || 'hairStyle' };
  if (!data.madeCharacter) queueSave('avatar'); // first visit: keep the starting look
  renderMaker();
}

function renderMaker() {
  const { kid, avatar } = playState;
  const tab = playState.makerTab;
  const colorTab = ['skin', 'hairColor', 'outfitColor'].includes(tab);
  const headTab = ['hairStyle', 'hairColor', 'eyes', 'mouth', 'skin'].includes(tab);
  const options = CATALOG.avatar[tab];

  $app.innerHTML = `
    <section class="kid-view maker-view ${kid.young ? 'young' : ''}" style="--kid:${esc(kid.color)}">
      <div class="maker-stage">
        <div class="maker-preview" id="preview">${avatarSvg(avatar)}</div>
        <button class="pill-big" id="surprise">🎲 Surprise me</button>
      </div>
      <div class="maker-panel">
        <div class="maker-tabs" role="tablist">
          ${MAKER_TABS.map(([id, icon, label]) => `<button role="tab" class="${tab === id ? 'on' : ''}" data-mtab="${id}" aria-label="${label}"><span>${icon}</span><small>${label}</small></button>`).join('')}
        </div>
        <div class="maker-options ${colorTab ? 'colors' : ''}">
          ${options.map((o) => {
            const on = avatar[tab] === o.id;
            if (colorTab) return `<button class="swatch big ${on ? 'on' : ''}" data-pick="${o.id}" style="background:${o.color}" aria-label="${o.id}"></button>`;
            const preview = { ...avatar, [tab]: o.id };
            return `<button class="maker-opt ${on ? 'on' : ''}" data-pick="${o.id}" aria-label="${o.id}">${avatarSvg(preview, { headOnly: headTab })}</button>`;
          }).join('')}
        </div>
        <button class="big-btn done-btn" id="done">✅ Done</button>
      </div>
    </section>`;

  $app.querySelectorAll('[data-mtab]').forEach((b) => { b.onclick = () => { playState.makerTab = b.dataset.mtab; renderMaker(); }; });
  $app.querySelectorAll('[data-pick]').forEach((b) => {
    b.onclick = () => {
      avatar[tab] = b.dataset.pick;
      queueSave('avatar');
      renderMaker();
      wiggle(document.getElementById('preview'));
    };
  });
  document.getElementById('surprise').onclick = () => {
    for (const [key, list] of Object.entries(CATALOG.avatar)) avatar[key] = list[Math.floor(Math.random() * list.length)].id;
    queueSave('avatar');
    renderMaker();
    wiggle(document.getElementById('preview'));
  };
  document.getElementById('done').onclick = () => { location.hash = 'room'; };
}
