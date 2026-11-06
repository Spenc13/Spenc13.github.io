'use strict';
const { test, before, after } = require('node:test');
const assert = require('node:assert/strict');
const http = require('node:http');
const { readConfig } = require('../src/config');
const { createApp } = require('../src/server');
const store = require('../src/db');

const env = {
  MOM_PIN: '1111', DAD_PIN: '2222', MOM_NAME: 'Mom', DAD_NAME: 'Dad',
  KID1_NAME: 'Ava', KID2_NAME: 'Bea', KID2_PIN: '', SESSION_SECRET: 'test-secret',
};
let server, base;

before(async () => {
  const config = readConfig(env);
  assert.deepEqual(config.errors, []);
  server = http.createServer(createApp(config, store.openDb(':memory:')));
  await new Promise((r) => server.listen(0, r));
  base = `http://127.0.0.1:${server.address().port}`;
});
after(() => server.close());

async function call(path, { method = 'GET', body, cookie, csrf = true } = {}) {
  const headers = { 'Content-Type': 'application/json' };
  if (csrf) headers['X-Requested-With'] = 'home-dojo';
  if (cookie) headers.Cookie = cookie;
  const res = await fetch(base + path, { method, headers, body: body && JSON.stringify(body) });
  const setCookie = res.headers.get('set-cookie');
  return { status: res.status, data: await res.json(), cookie: setCookie && setCookie.split(';')[0] };
}

const login = async (pin) => (await call('/api/login/parent', { method: 'POST', body: { pin } })).cookie;

test('config rejects missing or identical PINs', () => {
  assert.ok(readConfig({}).errors.some((e) => e.includes('MOM_PIN')));
  assert.ok(readConfig({ MOM_PIN: '1234', DAD_PIN: '1234' }).errors.some((e) => e.includes('different')));
  assert.ok(readConfig({ MOM_PIN: '12', DAD_PIN: '5678' }).errors.some((e) => e.includes('4 to 8 digits')));
});

test('wrong PIN is refused', async () => {
  const r = await call('/api/login/parent', { method: 'POST', body: { pin: '9999' } });
  assert.equal(r.status, 401);
});

test('each PIN logs in as the right parent and entries record that parent', async () => {
  const mom = await login('1111');
  const dad = await login('2222');
  assert.equal((await call('/api/me', { cookie: mom })).data.name, 'Mom');
  assert.equal((await call('/api/me', { cookie: dad })).data.name, 'Dad');

  const { data: d } = await call('/api/dashboard', { cookie: mom });
  const kind = d.behaviors.find((b) => b.grp === 'kind');
  const r = await call('/api/points', { method: 'POST', cookie: dad, body: { kidId: 1, behaviorId: kind.id, direction: 1 } });
  assert.equal(r.status, 200);
  assert.equal(r.data.entry.parent, 'Dad');
  assert.equal(r.data.entry.kidName, 'Ava');
  assert.equal(r.data.entry.behavior, kind.label);
  assert.equal(r.data.entry.group, 'kind');
  assert.ok(!Number.isNaN(Date.parse(r.data.entry.createdAt)));
});

test('behaviors cover kind, helping and listening', async () => {
  const { data } = await call('/api/dashboard', { cookie: await login('1111') });
  assert.deepEqual([...new Set(data.behaviors.map((b) => b.grp))].sort(), ['helping', 'kind', 'listening']);
  assert.equal(data.kids.length, 2);
  assert.deepEqual(data.rewards, []);
});

test('scores never go below zero, and the attempt is still logged', async () => {
  const mom = await login('1111');
  const { data: d } = await call('/api/dashboard', { cookie: mom });
  const b = d.behaviors.find((x) => x.grp === 'listening');
  assert.equal(d.kids.find((k) => k.id === 2).score, 0);
  const r = await call('/api/points', { method: 'POST', cookie: mom, body: { kidId: 2, behaviorId: b.id, direction: -1 } });
  assert.equal(r.data.entry.score, 0);
  assert.equal(r.data.entry.applied, 0);
  assert.equal(r.data.entry.requested, -1);
  const log = (await call('/api/log', { cookie: mom })).data.log;
  assert.equal(log[0].id, r.data.entry.id);
  assert.equal(log[0].parent, 'Mom');
});

test('kids see only their own score and cannot edit', async () => {
  const kid = (await call('/api/login/kid', { method: 'POST', body: { kidId: 2 } })).cookie;
  const me = await call('/api/kid?id=1', { cookie: kid });
  assert.equal(me.data.kid.name, 'Bea'); // ignores ?id for kids
  assert.equal(me.data.kids, undefined);
  assert.equal((await call('/api/dashboard', { cookie: kid })).status, 401);
  assert.equal((await call('/api/log', { cookie: kid })).status, 401);
  const r = await call('/api/points', { method: 'POST', cookie: kid, body: { kidId: 2, behaviorId: 1, direction: 1 } });
  assert.equal(r.status, 401);
  assert.equal((await call('/api/rewards', { method: 'POST', cookie: kid, body: { name: 'x', threshold: 1 } })).status, 401);
});

test('kids replay unseen changes once, oldest first', async () => {
  const mom = await login('1111');
  const kid = (await call('/api/login/kid', { method: 'POST', body: { kidId: 1 } })).cookie;
  let { data } = await call('/api/kid', { cookie: kid });
  await call('/api/kid/seen', { method: 'POST', cookie: kid, body: { logId: data.unseen.at(-1)?.id ?? 0 } });
  assert.deepEqual((await call('/api/kid', { cookie: kid })).data.unseen, []);

  const { data: d } = await call('/api/dashboard', { cookie: mom });
  const [b1, b2] = d.behaviors;
  const add = (bid, dir) => call('/api/points', { method: 'POST', cookie: mom, body: { kidId: 1, behaviorId: bid, direction: dir } });
  const e1 = (await add(b1.id, 1)).data.entry;
  const e2 = (await add(b2.id, 1)).data.entry;
  const e3 = (await add(b1.id, -1)).data.entry;
  await add(b1.id, 1); // other girl's changes must not show up
  await call('/api/points', { method: 'POST', cookie: mom, body: { kidId: 2, behaviorId: b1.id, direction: 1 } });

  ({ data } = await call('/api/kid', { cookie: kid }));
  assert.deepEqual(data.unseen.slice(0, 3).map((u) => [u.id, u.applied, u.score]),
    [[e1.id, 1, e1.score], [e2.id, 1, e2.score], [e3.id, -1, e3.score]]);
  assert.equal(data.unseen[0].emoji, b1.emoji);
  assert.equal(data.unseen.length, 4);

  // Parents previewing a girl don't get (or consume) her replay.
  assert.equal((await call('/api/kid?id=1', { cookie: mom })).data.unseen, undefined);
  assert.equal((await call('/api/kid/seen', { method: 'POST', cookie: mom, body: { logId: 1 } })).status, 401);

  await call('/api/kid/seen', { method: 'POST', cookie: kid, body: { logId: e3.id } });
  assert.equal((await call('/api/kid', { cookie: kid })).data.unseen.length, 1);
  await call('/api/kid/seen', { method: 'POST', cookie: kid, body: { logId: 1 } }); // never moves backwards
  assert.equal((await call('/api/kid', { cookie: kid })).data.unseen.length, 1);
});

test('rewards can be added with a threshold and removed', async () => {
  const mom = await login('1111');
  assert.equal((await call('/api/rewards', { method: 'POST', cookie: mom, body: { name: 'Park', threshold: 0 } })).status, 400);
  const add = await call('/api/rewards', { method: 'POST', cookie: mom, body: { name: 'Park', threshold: 15 } });
  assert.deepEqual(add.data.rewards.map((r) => [r.name, r.threshold]), [['Park', 15]]);
  const del = await call(`/api/rewards/${add.data.rewards[0].id}`, { method: 'DELETE', cookie: mom });
  assert.deepEqual(del.data.rewards, []);
});

test('cashing in needs a grown-up PIN and enough stars, then takes the stars and logs it', async () => {
  const mom = await login('1111');
  const kid = (await call('/api/login/kid', { method: 'POST', body: { kidId: 2 } })).cookie;
  const { data: d } = await call('/api/dashboard', { cookie: mom });
  const b = d.behaviors[0];
  const start = d.kids.find((k) => k.id === 2).score;
  for (let i = 0; i < 4; i++) await call('/api/points', { method: 'POST', cookie: mom, body: { kidId: 2, behaviorId: b.id, direction: 1 } });
  const cheap = (await call('/api/rewards', { method: 'POST', cookie: mom, body: { name: 'Sticker', threshold: 3 } })).data.rewards.find((r) => r.name === 'Sticker');
  const pricey = (await call('/api/rewards', { method: 'POST', cookie: mom, body: { name: 'Zoo', threshold: 999 } })).data.rewards.find((r) => r.name === 'Zoo');
  const cash = (rewardId, pin, cookie = kid) => call('/api/kid/cash-in', { method: 'POST', cookie, body: { rewardId, pin } });

  assert.equal((await cash(cheap.id, '0000')).status, 401); // kid can't approve herself
  assert.equal((await cash(cheap.id, '2222', mom)).status, 401); // only from a kid's screen
  assert.equal((await cash(pricey.id, '2222')).status, 400); // not enough stars
  const ok = await cash(cheap.id, '2222');
  assert.equal(ok.status, 200);
  assert.deepEqual([ok.data.entry.parent, ok.data.entry.behavior, ok.data.entry.group, ok.data.entry.applied, ok.data.entry.score],
    ['Dad', 'Sticker', 'reward', -3, start + 4 - 3]);
  assert.equal((await call('/api/kid', { cookie: kid })).data.kid.score, start + 1);
  const log = (await call('/api/log', { cookie: mom })).data.log;
  assert.equal(log[0].id, ok.data.entry.id);
  assert.equal((await call('/api/kid', { cookie: kid })).data.unseen.at(-1).emoji, '🎁');
});

test('each girl edits only her own character and room; sisters can visit', async () => {
  const CATALOG = require('../public/catalog');
  const mom = await login('1111');
  const ava = (await call('/api/login/kid', { method: 'POST', body: { kidId: 1 } })).cookie;
  const bea = (await call('/api/login/kid', { method: 'POST', body: { kidId: 2 } })).cookie;

  // Defaults before she makes anything.
  let r = (await call('/api/room', { cookie: ava })).data;
  assert.equal(r.mine, true);
  assert.equal(r.madeCharacter, false);
  assert.deepEqual(r.room, CATALOG.defaultRoom());

  // Character: valid options save, unknown ones are refused.
  const avatar = { ...CATALOG.defaultAvatar(1, false), hairStyle: 'curly', accessory: 'crown' };
  assert.equal((await call('/api/avatar', { method: 'PUT', cookie: ava, body: { avatar: { ...avatar, hairStyle: 'mohawk' } } })).status, 400);
  assert.equal((await call('/api/avatar', { method: 'PUT', cookie: ava, body: { avatar } })).status, 200);
  assert.equal((await call('/api/avatar', { method: 'PUT', cookie: mom, body: { avatar } })).status, 401);
  const opts = (await call('/api/login-options')).data.kids;
  assert.equal(opts.find((k) => k.id === 1).avatar.accessory, 'crown');

  // Room: starter items are free, locked ones are refused until she has earned enough.
  const earned = (await call('/api/room', { cookie: ava })).data.earned;
  const lockedTv = CATALOG.items.find((i) => i.id === 'tv');
  const room = { wall: 'lilac', floor: 'pinkcarpet', items: [{ id: 'bed', x: 20, y: 90 }, { id: 'teddy', x: 40, y: 80 }], me: { x: 50, y: 85 } };
  assert.equal((await call('/api/room', { method: 'PUT', cookie: ava, body: { room } })).status, 200);
  const withTv = { ...room, items: [...room.items, { id: 'tv', x: 70, y: 70 }] };
  const tvRes = await call('/api/room', { method: 'PUT', cookie: ava, body: { room: withTv } });
  assert.equal(tvRes.status, earned >= lockedTv.unlock ? 200 : 403);
  assert.equal((await call('/api/room', { method: 'PUT', cookie: ava, body: { room: { ...room, items: [room.items[0], room.items[0]] } } })).status, 400);
  assert.equal((await call('/api/room', { method: 'PUT', cookie: ava, body: { room: { ...room, wall: 'plaid' } } })).status, 400);

  // Earning stars unlocks the TV.
  const { data: d } = await call('/api/dashboard', { cookie: mom });
  for (let i = earned; i < lockedTv.unlock; i++) {
    await call('/api/points', { method: 'POST', cookie: mom, body: { kidId: 1, behaviorId: d.behaviors[0].id, direction: 1 } });
  }
  assert.equal((await call('/api/room', { method: 'PUT', cookie: ava, body: { room: withTv } })).status, 200);

  // Her sister can visit (read-only) but a PUT only ever touches her own room.
  const visit = (await call('/api/room?kid=1', { cookie: bea })).data;
  assert.equal(visit.mine, false);
  assert.equal(visit.room.wall, 'lilac');
  assert.equal(visit.kid.avatar.accessory, 'crown');
  await call('/api/room', { method: 'PUT', cookie: bea, body: { room: { ...room, wall: 'mint', items: [] } } });
  assert.equal((await call('/api/room?kid=1', { cookie: bea })).data.room.wall, 'lilac');
  assert.equal((await call('/api/room', { cookie: bea })).data.room.wall, 'mint');
  assert.equal((await call('/api/room?kid=1')).status, 401); // not logged in
});

test('mutations without the app header are rejected', async () => {
  const r = await call('/api/login/parent', { method: 'POST', body: { pin: '1111' }, csrf: false });
  assert.equal(r.status, 403);
});

test('tampered session cookie is ignored', async () => {
  const mom = await login('1111');
  const [name, value] = mom.split('=');
  const [body] = value.split('.');
  const forged = Buffer.from(JSON.stringify({ role: 'parent', who: 'dad', exp: Date.now() + 1e9 })).toString('base64url');
  assert.equal((await call('/api/me', { cookie: `${name}=${forged}.${value.split('.')[1]}` })).data.role, null);
  assert.ok(body);
});

test('static app and manifest are served', async () => {
  const html = await fetch(base + '/');
  assert.match(await html.text(), /Home Dojo/);
  const m = await fetch(base + '/manifest.webmanifest');
  assert.equal(m.headers.get('content-type'), 'application/manifest+json');
  assert.equal((await fetch(base + '/..%2fsrc%2fconfig.js')).status, 403);
});
