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

test('rewards can be added with a threshold and removed', async () => {
  const mom = await login('1111');
  assert.equal((await call('/api/rewards', { method: 'POST', cookie: mom, body: { name: 'Park', threshold: 0 } })).status, 400);
  const add = await call('/api/rewards', { method: 'POST', cookie: mom, body: { name: 'Park', threshold: 15 } });
  assert.deepEqual(add.data.rewards.map((r) => [r.name, r.threshold]), [['Park', 15]]);
  const del = await call(`/api/rewards/${add.data.rewards[0].id}`, { method: 'DELETE', cookie: mom });
  assert.deepEqual(del.data.rewards, []);
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
