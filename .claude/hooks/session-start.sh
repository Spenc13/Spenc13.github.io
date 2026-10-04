#!/bin/bash
# Prepares cloud sessions for browser testing with playwright-cli.
set -euo pipefail

# Only needed in Claude Code cloud sessions; local machines manage their own setup.
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

if ! command -v playwright-cli >/dev/null 2>&1; then
  npm install -g @playwright/cli@latest >/dev/null 2>&1
fi

# Preinstall the DataForSEO MCP server so `npx` in .mcp.json starts it instantly;
# downloading it on demand can exceed Claude Code's 30s MCP connect timeout.
if ! command -v dataforseo-mcp-server >/dev/null 2>&1; then
  npm install -g dataforseo-mcp-server >/dev/null 2>&1
fi

# The cloud container ships Chromium (not Google Chrome), so point playwright-cli at it.
if [ -x /opt/pw-browsers/chromium ]; then
  mkdir -p "$CLAUDE_PROJECT_DIR/.playwright"
  cat > "$CLAUDE_PROJECT_DIR/.playwright/cli.config.json" <<'JSON'
{ "browser": { "browserName": "chromium", "launchOptions": { "channel": "chromium", "executablePath": "/opt/pw-browsers/chromium" } } }
JSON
fi
