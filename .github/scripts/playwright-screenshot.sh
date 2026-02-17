#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/../configure-ralph"

echo "🎭 Playwright Screenshot Helper"
cd "$REPO_ROOT"

if [ -f "$REPO_ROOT/backend/server.js" ]; then
  cd "$REPO_ROOT/backend"
  [ ! -d "node_modules" ] && npm install
  node server.js &
  SERVER_PID=$!
  trap 'kill $SERVER_PID 2>/dev/null; wait $SERVER_PID 2>/dev/null' EXIT

  APP_URL="${RALPH_APP_URL}"
  for i in $(seq 1 "$RALPH_SERVER_STARTUP_WAIT"); do
    curl -s "$APP_URL" >/dev/null 2>&1 && break
    [ "$i" -eq "$RALPH_SERVER_STARTUP_WAIT" ] && echo "❌ Server failed to start" && exit 1
    sleep "$RALPH_SERVER_STARTUP_SLEEP"
  done
  echo "✅ Server ready"
fi

cd "$REPO_ROOT"
export APP_URL="${RALPH_APP_URL}"
export SCREENSHOT_PREFIX="${RALPH_SCREENSHOT_PREFIX}"
export SCREENSHOT_VIEWPORT_WIDTH="${RALPH_SCREENSHOT_VIEWPORT_WIDTH}"
export SCREENSHOT_VIEWPORT_HEIGHT="${RALPH_SCREENSHOT_VIEWPORT_HEIGHT}"
export SCREENSHOT_TIMEOUT="${RALPH_SCREENSHOT_TIMEOUT}"
export SCREENSHOT_WAIT="${RALPH_SCREENSHOT_WAIT}"
export SCREENSHOT_TEXT_PREVIEW="${RALPH_SCREENSHOT_TEXT_PREVIEW}"
export SCREENSHOT_TEXT_SHORT="${RALPH_SCREENSHOT_TEXT_SHORT}"
export SCREENSHOT_DEFAULT_PAGES="${RALPH_SCREENSHOT_DEFAULT_PAGES}"
node .github/scripts/visual-check.js
echo "✅ Screenshots complete"


