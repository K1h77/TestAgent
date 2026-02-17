#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "🎭 Playwright Screenshot Helper"
cd "$REPO_ROOT"

# Install and start backend if it exists
if [ -f "$REPO_ROOT/backend/server.js" ]; then
  cd "$REPO_ROOT/backend"
  [ ! -d "node_modules" ] && npm install
  node server.js &
  SERVER_PID=$!
  trap 'kill $SERVER_PID 2>/dev/null; wait $SERVER_PID 2>/dev/null' EXIT

  APP_URL="${APP_URL:-http://localhost:3000}"
  for i in $(seq 1 30); do
    curl -s "$APP_URL" >/dev/null 2>&1 && break
    [ $i -eq 30 ] && echo "❌ Server failed to start" && exit 1
    sleep 1
  done
  echo "✅ Server ready"
fi

cd "$REPO_ROOT"
export APP_URL="${APP_URL:-http://localhost:3000}"
export SCREENSHOT_PREFIX="${SCREENSHOT_PREFIX:-visual-check}"
node .github/scripts/visual-check.js
echo "✅ Screenshots complete"

