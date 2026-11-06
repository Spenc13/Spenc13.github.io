'use strict';
// Home Dojo server: plain Node (no framework), SQLite via node:sqlite.
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const store = require('./db');

const PUBLIC_DIR = path.join(__dirname, '..', 'public');
const COOKIE = 'dojo_session';
const KID_SESSION_DAYS = 365;
const PARENT_SESSION_DAYS = 90;
const MAX_FAILS = 5;
const LOCKOUT_MS = 60 * 1000;

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.webmanifest': 'application/manifest+json',
  '.json': 'application/json',
  '.png': 'image/png',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
};

function createApp(config, db) {
  const { httpError } = store;
  store.syncKids(db, config.kids);
  const failures = new Map(); // ip -> { count, until }

  // ---------- sessions (HMAC-signed cookie) ----------
  const sign = (data) => crypto.createHmac('sha256', config.sessionSecret).update(data).digest('base64url');

  function makeToken(payload, days) {
    const body = Buffer.from(JSON.stringify({ ...payload, exp: Date.now() + days * 864e5 })).toString('base64url');
    return `${body}.${sign(body)}`;
  }

  function readToken(token) {
    if (!token || !token.includes('.')) return null;
    const [body, sig] = token.split('.');
    const expected = sign(body);
    if (sig.length !== expected.length || !crypto.timingSafeEqual(Buffer.from(sig), Buffer.from(expected))) return null;
    try {
      const p = JSON.parse(Buffer.from(body, 'base64url').toString());
      return p.exp > Date.now() ? p : null;
    } catch {
      return null;
    }
  }

  function getSession(req) {
    const cookies = Object.fromEntries((req.headers.cookie || '').split(';').map((c) => {
      const i = c.indexOf('=');
      return [c.slice(0, i).trim(), decodeURIComponent(c.slice(i + 1).trim())];
    }));
    const s = readToken(cookies[COOKIE]);
    if (!s) return null;
    // Re-check against current config so a removed parent/kid loses access.
    if (s.role === 'parent' && !config.parents.some((p) => p.key === s.who)) return null;
    if (s.role === 'kid' && !config.kids.some((k) => k.id === s.kidId)) return null;
    return s;
  }

  function setSession(res, payload, days) {
    const parts = [`${COOKIE}=${makeToken(payload, days)}`, 'Path=/', 'HttpOnly', 'SameSite=Lax', `Max-Age=${days * 86400}`];
    if (config.secureCookies) parts.push('Secure');
    res.setHeader('Set-Cookie', parts.join('; '));
  }

  function clearSession(res) {
    res.setHeader('Set-Cookie', `${COOKIE}=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0`);
  }

  // ---------- PIN checks with lockout ----------
  const pinEquals = (a, b) => {
    const ha = crypto.createHash('sha256').update(String(a)).digest();
    const hb = crypto.createHash('sha256').update(String(b)).digest();
    return crypto.timingSafeEqual(ha, hb);
  };

  function clientIp(req) {
    return (req.headers['x-forwarded-for'] || '').split(',')[0].trim() || req.socket.remoteAddress || '?';
  }

  function checkLock(ip) {
    const f = failures.get(ip);
    if (f && f.until > Date.now()) {
      throw httpError(429, `Too many tries. Wait ${Math.ceil((f.until - Date.now()) / 1000)} seconds.`);
    }
  }

  function recordFail(ip) {
    const f = failures.get(ip) || { count: 0, until: 0 };
    f.count += 1;
    if (f.count >= MAX_FAILS) {
      f.count = 0;
      f.until = Date.now() + LOCKOUT_MS;
    }
    failures.set(ip, f);
  }

  // ---------- helpers ----------
  const publicKid = (k) => ({ id: k.id, name: k.name, color: k.color, emoji: k.emoji, young: k.young, score: k.score });

  function requireParent(s) {
    if (!s || s.role !== 'parent') throw httpError(401, 'Parent login required');
    return config.parents.find((p) => p.key === s.who);
  }

  function readJson(req) {
    return new Promise((resolve, reject) => {
      let size = 0;
      const chunks = [];
      req.on('data', (c) => {
        size += c.length;
        if (size > 10_000) {
          reject(httpError(413, 'Request too large'));
          req.destroy();
        } else chunks.push(c);
      });
      req.on('end', () => {
        if (!chunks.length) return resolve({});
        try {
          resolve(JSON.parse(Buffer.concat(chunks).toString()));
        } catch {
          reject(httpError(400, 'Invalid JSON'));
        }
      });
      req.on('error', reject);
    });
  }

  function send(res, status, data) {
    const body = JSON.stringify(data);
    res.writeHead(status, {
      'Content-Type': 'application/json; charset=utf-8',
      'Cache-Control': 'no-store',
      'Content-Length': Buffer.byteLength(body),
    });
    res.end(body);
  }

  // ---------- API ----------
  async function api(req, res, url) {
    const s = getSession(req);
    const route = `${req.method} ${url.pathname}`;

    // Mutating requests must come from our own page (CSRF guard on top of SameSite cookies).
    if (req.method !== 'GET' && req.headers['x-requested-with'] !== 'home-dojo') {
      throw httpError(403, 'Bad request origin');
    }

    switch (route) {
      case 'GET /api/me': {
        if (!s) return send(res, 200, { role: null });
        if (s.role === 'parent') return send(res, 200, { role: 'parent', name: requireParent(s).name });
        return send(res, 200, { role: 'kid', kidId: s.kidId });
      }

      case 'GET /api/login-options':
        return send(res, 200, {
          kids: config.kids.map((k) => ({ id: k.id, name: k.name, color: k.color, emoji: k.emoji, young: k.young, needsPin: !!k.pin })),
        });

      case 'POST /api/login/parent': {
        const ip = clientIp(req);
        checkLock(ip);
        const { pin } = await readJson(req);
        const parent = config.parents.find((p) => pinEquals(p.pin, pin ?? ''));
        if (!parent) {
          recordFail(ip);
          throw httpError(401, 'That PIN didn’t match');
        }
        failures.delete(ip);
        setSession(res, { role: 'parent', who: parent.key }, PARENT_SESSION_DAYS);
        return send(res, 200, { role: 'parent', name: parent.name });
      }

      case 'POST /api/login/kid': {
        const ip = clientIp(req);
        checkLock(ip);
        const { kidId, pin } = await readJson(req);
        const kid = config.kids.find((k) => k.id === Number(kidId));
        if (!kid) throw httpError(404, 'Unknown daughter');
        if (kid.pin && !pinEquals(kid.pin, pin ?? '')) {
          recordFail(ip);
          throw httpError(401, 'Try again');
        }
        failures.delete(ip);
        setSession(res, { role: 'kid', kidId: kid.id }, KID_SESSION_DAYS);
        return send(res, 200, { role: 'kid', kidId: kid.id });
      }

      case 'POST /api/logout':
        clearSession(res);
        return send(res, 200, { ok: true });

      case 'GET /api/kid': {
        // A kid sees only her own name, score and progress. Parents may preview any kid.
        let kidId;
        if (s?.role === 'kid') kidId = s.kidId;
        else if (s?.role === 'parent') kidId = Number(url.searchParams.get('id'));
        else throw httpError(401, 'Login required');
        const kid = store.getKid(db, kidId);
        if (!kid) throw httpError(404, 'Unknown daughter');
        return send(res, 200, { kid: publicKid(kid), rewards: store.getRewards(db), defaultGoal: config.defaultGoal });
      }

      case 'GET /api/dashboard': {
        const parent = requireParent(s);
        return send(res, 200, {
          parent: parent.name,
          kids: store.getKids(db).map(publicKid),
          behaviors: store.getBehaviors(db),
          rewards: store.getRewards(db),
          log: store.getLog(db, 30),
          defaultGoal: config.defaultGoal,
        });
      }

      case 'GET /api/log': {
        requireParent(s);
        const limit = Math.min(Math.max(parseInt(url.searchParams.get('limit') || '100', 10) || 100, 1), 1000);
        return send(res, 200, { log: store.getLog(db, limit) });
      }

      case 'POST /api/points': {
        const parent = requireParent(s);
        const { kidId, behaviorId, direction } = await readJson(req);
        if (direction !== 1 && direction !== -1) throw httpError(400, 'direction must be 1 or -1');
        const entry = store.applyPoints(db, {
          kidId: Number(kidId), behaviorId: Number(behaviorId), direction, parent: parent.name,
        });
        return send(res, 200, { entry, kids: store.getKids(db).map(publicKid) });
      }

      case 'POST /api/rewards': {
        requireParent(s);
        const { name, threshold } = await readJson(req);
        const n = String(name || '').trim().slice(0, 80);
        const t = Number(threshold);
        if (!n) throw httpError(400, 'Reward needs a name');
        if (!Number.isInteger(t) || t < 1 || t > 100000) throw httpError(400, 'Points must be a whole number above 0');
        store.addReward(db, n, t);
        return send(res, 200, { rewards: store.getRewards(db) });
      }

      default: {
        const m = url.pathname.match(/^\/api\/rewards\/(\d+)$/);
        if (m && req.method === 'DELETE') {
          requireParent(s);
          if (!store.deleteReward(db, Number(m[1]))) throw httpError(404, 'Reward not found');
          return send(res, 200, { rewards: store.getRewards(db) });
        }
        throw httpError(404, 'Not found');
      }
    }
  }

  // ---------- static files ----------
  function serveStatic(req, res, url) {
    let rel = decodeURIComponent(url.pathname);
    if (rel === '/' || !path.extname(rel)) rel = '/index.html'; // single-page app
    const file = path.normalize(path.join(PUBLIC_DIR, rel));
    if (!file.startsWith(PUBLIC_DIR + path.sep)) {
      res.writeHead(403).end();
      return;
    }
    fs.readFile(file, (err, buf) => {
      if (err) {
        res.writeHead(404, { 'Content-Type': 'text/plain' }).end('Not found');
        return;
      }
      const ext = path.extname(file);
      res.writeHead(200, {
        'Content-Type': MIME[ext] || 'application/octet-stream',
        // HTML/JS/CSS/SW revalidate so updates reach the iPads; icons can cache.
        'Cache-Control': ext === '.png' || ext === '.svg' ? 'public, max-age=86400' : 'no-cache',
      });
      res.end(buf);
    });
  }

  return async function handler(req, res) {
    res.setHeader('X-Content-Type-Options', 'nosniff');
    res.setHeader('Referrer-Policy', 'same-origin');
    res.setHeader('X-Frame-Options', 'DENY');
    const url = new URL(req.url, 'http://localhost');
    try {
      if (url.pathname === '/healthz') return send(res, 200, { ok: true });
      if (url.pathname.startsWith('/api/')) return await api(req, res, url);
      if (req.method !== 'GET' && req.method !== 'HEAD') throw httpError(405, 'Method not allowed');
      return serveStatic(req, res, url);
    } catch (err) {
      const status = err.status || 500;
      if (status === 500) console.error(err);
      if (!res.headersSent) send(res, status, { error: status === 500 ? 'Something went wrong' : err.message });
    }
  };
}

function start(config) {
  const db = store.openDb(config.dbPath);
  const server = http.createServer(createApp(config, db));
  server.listen(config.port, () => console.log(`Home Dojo listening on http://localhost:${config.port}`));
  return server;
}

module.exports = { createApp, start };
