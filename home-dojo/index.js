'use strict';
const { readConfig } = require('./src/config');
const { start } = require('./src/server');

const config = readConfig();
if (config.errors.length) {
  console.error('Home Dojo cannot start. Fix these environment variables:\n  - ' + config.errors.join('\n  - '));
  process.exit(1);
}
if (config.ephemeralSecret) {
  console.warn('SESSION_SECRET is not set: everyone will be logged out whenever the server restarts.');
}
start(config);
