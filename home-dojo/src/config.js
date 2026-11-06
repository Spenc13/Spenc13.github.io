'use strict';
// All secrets and family details come from environment variables, never the code.
const crypto = require('node:crypto');

function readConfig(env = process.env) {
  const errors = [];
  const pin = (name) => {
    const v = (env[name] || '').trim();
    if (!v) return '';
    if (!/^\d{4,8}$/.test(v)) errors.push(`${name} must be 4 to 8 digits`);
    return v;
  };

  const parents = [
    { key: 'mom', name: (env.MOM_NAME || 'Mom').trim(), pin: pin('MOM_PIN') },
    { key: 'dad', name: (env.DAD_NAME || 'Dad').trim(), pin: pin('DAD_PIN') },
  ];
  for (const p of parents) if (!p.pin) errors.push(`${p.key.toUpperCase()}_PIN is required`);
  if (parents[0].pin && parents[0].pin === parents[1].pin) {
    errors.push('MOM_PIN and DAD_PIN must be different so each entry is logged with the right parent');
  }

  const kids = [1, 2].map((n) => ({
    id: n,
    name: (env[`KID${n}_NAME`] || (n === 1 ? 'Big Sister' : 'Little Sister')).trim(),
    color: (env[`KID${n}_COLOR`] || (n === 1 ? '#7c5cff' : '#ff6fa8')).trim(),
    emoji: (env[`KID${n}_EMOJI`] || (n === 1 ? '🦄' : '🐰')).trim(),
    // "Young" mode: picture-first view with big stars (for the 3-year-old).
    young: /^(1|true|yes)$/i.test(env[`KID${n}_YOUNG`] || (n === 2 ? 'true' : 'false')),
    pin: pin(`KID${n}_PIN`), // optional: leave empty for tap-your-picture login
  }));
  for (const k of kids) {
    if (!/^#[0-9a-f]{6}$/i.test(k.color)) errors.push(`KID${k.id}_COLOR must look like #ff6fa8`);
  }

  let sessionSecret = env.SESSION_SECRET || '';
  let ephemeralSecret = false;
  if (!sessionSecret) {
    sessionSecret = crypto.randomBytes(32).toString('hex');
    ephemeralSecret = true;
  }

  const goal = parseInt(env.DEFAULT_GOAL || '10', 10);

  return {
    errors,
    parents,
    kids,
    sessionSecret,
    ephemeralSecret,
    defaultGoal: Number.isFinite(goal) && goal > 0 ? goal : 10,
    port: parseInt(env.PORT || '3000', 10),
    dbPath: env.DB_PATH || './data/home-dojo.sqlite',
    secureCookies: /^(1|true|yes)$/i.test(env.SECURE_COOKIES || (env.NODE_ENV === 'production' ? 'true' : 'false')),
  };
}

module.exports = { readConfig };
