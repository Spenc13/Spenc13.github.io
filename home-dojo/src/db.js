'use strict';
// SQLite storage for Home Dojo. One file, shared by every device.
const { DatabaseSync } = require('node:sqlite');
const fs = require('node:fs');
const path = require('node:path');

const DEFAULT_BEHAVIORS = [
  // group, label, emoji
  ['kind', 'Kind words', '💬'],
  ['kind', 'Sharing', '🤝'],
  ['kind', 'Gentle hands', '🫶'],
  ['helping', 'Clean up toys', '🧸'],
  ['helping', 'Help with chores', '🧺'],
  ['helping', 'Get ready by myself', '👕'],
  ['listening', 'Listen the first time', '👂'],
  ['listening', 'Inside voice', '🤫'],
  ['listening', 'Bedtime routine', '🌙'],
];

function openDb(dbPath) {
  if (dbPath !== ':memory:') fs.mkdirSync(path.dirname(path.resolve(dbPath)), { recursive: true });
  const db = new DatabaseSync(dbPath);
  db.exec(`
    PRAGMA journal_mode = WAL;
    PRAGMA foreign_keys = ON;
    PRAGMA busy_timeout = 5000;

    CREATE TABLE IF NOT EXISTS kids (
      id     INTEGER PRIMARY KEY,
      name   TEXT NOT NULL,
      color  TEXT NOT NULL,
      emoji  TEXT NOT NULL,
      young  INTEGER NOT NULL DEFAULT 0,
      score  INTEGER NOT NULL DEFAULT 0 CHECK (score >= 0)
    );

    CREATE TABLE IF NOT EXISTS behaviors (
      id         INTEGER PRIMARY KEY AUTOINCREMENT,
      grp        TEXT NOT NULL CHECK (grp IN ('kind','helping','listening')),
      label      TEXT NOT NULL,
      emoji      TEXT NOT NULL DEFAULT '',
      points     INTEGER NOT NULL DEFAULT 1 CHECK (points > 0),
      sort_order INTEGER NOT NULL DEFAULT 0,
      active     INTEGER NOT NULL DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS rewards (
      id         INTEGER PRIMARY KEY AUTOINCREMENT,
      name       TEXT NOT NULL,
      threshold  INTEGER NOT NULL CHECK (threshold > 0),
      created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS score_log (
      id              INTEGER PRIMARY KEY AUTOINCREMENT,
      created_at      TEXT NOT NULL,
      kid_id          INTEGER NOT NULL REFERENCES kids(id),
      kid_name        TEXT NOT NULL,
      behavior_id     INTEGER REFERENCES behaviors(id),
      behavior_label  TEXT NOT NULL,
      behavior_group  TEXT NOT NULL,
      parent          TEXT NOT NULL,
      requested_delta INTEGER NOT NULL,
      applied_delta   INTEGER NOT NULL,
      score_after     INTEGER NOT NULL
    );
    CREATE INDEX IF NOT EXISTS score_log_created ON score_log(created_at DESC);
  `);

  const behaviorCount = db.prepare('SELECT COUNT(*) AS n FROM behaviors').get().n;
  if (behaviorCount === 0) {
    const ins = db.prepare('INSERT INTO behaviors (grp, label, emoji, sort_order) VALUES (?, ?, ?, ?)');
    DEFAULT_BEHAVIORS.forEach(([g, l, e], i) => ins.run(g, l, e, i));
  }
  return db;
}

function tx(db, fn) {
  db.exec('BEGIN IMMEDIATE');
  try {
    const out = fn();
    db.exec('COMMIT');
    return out;
  } catch (err) {
    db.exec('ROLLBACK');
    throw err;
  }
}

/** Make the kids table match the configured kids (names/colors come from env). */
function syncKids(db, kids) {
  const upsert = db.prepare(`
    INSERT INTO kids (id, name, color, emoji, young) VALUES (?, ?, ?, ?, ?)
    ON CONFLICT(id) DO UPDATE SET name = excluded.name, color = excluded.color,
      emoji = excluded.emoji, young = excluded.young`);
  for (const k of kids) upsert.run(k.id, k.name, k.color, k.emoji, k.young ? 1 : 0);
}

function getKids(db) {
  return db.prepare('SELECT id, name, color, emoji, young, score FROM kids ORDER BY id').all()
    .map((k) => ({ ...k, young: !!k.young }));
}

function getKid(db, id) {
  const k = db.prepare('SELECT id, name, color, emoji, young, score FROM kids WHERE id = ?').get(id);
  return k ? { ...k, young: !!k.young } : null;
}

function getBehaviors(db) {
  return db.prepare(
    'SELECT id, grp, label, emoji, points FROM behaviors WHERE active = 1 ORDER BY sort_order, id'
  ).all();
}

function getRewards(db) {
  return db.prepare('SELECT id, name, threshold FROM rewards ORDER BY threshold, id').all();
}

function addReward(db, name, threshold) {
  const r = db.prepare('INSERT INTO rewards (name, threshold, created_at) VALUES (?, ?, ?)')
    .run(name, threshold, new Date().toISOString());
  return Number(r.lastInsertRowid);
}

function deleteReward(db, id) {
  return db.prepare('DELETE FROM rewards WHERE id = ?').run(id).changes > 0;
}

/**
 * Add or subtract a behavior's points for one kid. Scores never drop below 0;
 * every request is logged, including the amount actually applied.
 */
function applyPoints(db, { kidId, behaviorId, direction, parent }) {
  return tx(db, () => {
    const kid = db.prepare('SELECT id, name, score FROM kids WHERE id = ?').get(kidId);
    if (!kid) throw httpError(404, 'Unknown daughter');
    const b = db.prepare('SELECT id, grp, label, points FROM behaviors WHERE id = ? AND active = 1').get(behaviorId);
    if (!b) throw httpError(404, 'Unknown behavior');

    const requested = direction * b.points;
    const newScore = Math.max(0, kid.score + requested);
    const applied = newScore - kid.score;
    const createdAt = new Date().toISOString();

    db.prepare('UPDATE kids SET score = ? WHERE id = ?').run(newScore, kid.id);
    const r = db.prepare(`
      INSERT INTO score_log (created_at, kid_id, kid_name, behavior_id, behavior_label, behavior_group,
                             parent, requested_delta, applied_delta, score_after)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`)
      .run(createdAt, kid.id, kid.name, b.id, b.label, b.grp, parent, requested, applied, newScore);

    return {
      id: Number(r.lastInsertRowid), createdAt, kidId: kid.id, kidName: kid.name,
      behavior: b.label, group: b.grp, parent, requested, applied, score: newScore,
    };
  });
}

function getLog(db, limit = 50) {
  return db.prepare(`
    SELECT id, created_at AS createdAt, kid_id AS kidId, kid_name AS kidName,
           behavior_label AS behavior, behavior_group AS "group", parent,
           requested_delta AS requested, applied_delta AS applied, score_after AS score
    FROM score_log ORDER BY id DESC LIMIT ?`).all(limit);
}

function httpError(status, message) {
  const e = new Error(message);
  e.status = status;
  return e;
}

module.exports = {
  openDb, syncKids, getKids, getKid, getBehaviors, getRewards, addReward, deleteReward,
  applyPoints, getLog, httpError,
};
