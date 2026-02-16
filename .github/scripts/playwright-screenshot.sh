#!/bin/bash

##############################################################################
# Playwright Screenshot Helper Script for Ralph Agent
#
# This script:
# 1. Installs Playwright and Chromium browser
# 2. Starts the backend server
# 3. Runs the visual check script (screenshots + text summary)
# 4. Cleans up (stops server)
#
# Usage:
#   .github/scripts/playwright-screenshot.sh
#
# Environment Variables:
#   APP_URL - URL to test (default: http://localhost:3000)
#   SCREENSHOT_PREFIX - Prefix for screenshot filenames (default: visual-check)
#   SKIP_INSTALL - Skip Playwright installation (default: false)
##############################################################################

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "🎭 Playwright Screenshot Helper"
echo "================================"
echo "Repository root: $REPO_ROOT"

# Navigate to repo root
cd "$REPO_ROOT"

# ==========================================
# 1. Install Playwright (if needed)
# ==========================================
if [ "$SKIP_INSTALL" != "true" ]; then
  echo "📦 Installing Playwright dependencies..."
  
  # Install playwright npm package if not already installed
  # Check if playwright binary exists
  if ! command -v npx >/dev/null 2>&1 || ! npx playwright --version >/dev/null 2>&1; then
    echo "  Installing playwright npm package..."
    npm install --no-save playwright
  else
    echo "  ✅ Playwright npm package already installed"
  fi
  
  # Install Chromium browser
  echo "  Installing Chromium browser..."
  npx playwright install chromium --with-deps
  
  echo "✅ Playwright installation complete"
else
  echo "⏭️  Skipping Playwright installation (SKIP_INSTALL=true)"
fi

# ==========================================
# 2. Install backend dependencies
# ==========================================
echo ""
echo "📦 Installing backend dependencies..."
cd "$REPO_ROOT/backend"
if [ ! -d "node_modules" ]; then
  npm install
else
  echo "  ✅ Backend dependencies already installed"
fi

# ==========================================
# 3. Start the backend server
# ==========================================
echo ""
echo "🚀 Starting backend server..."
cd "$REPO_ROOT/backend"

# Start server in background
node server.js &
SERVER_PID=$!

echo "  Server PID: $SERVER_PID"

# Function to cleanup server on exit
cleanup() {
  echo ""
  echo "🧹 Cleaning up..."
  if [ -n "$SERVER_PID" ]; then
    echo "  Stopping server (PID: $SERVER_PID)..."
    kill $SERVER_PID 2>/dev/null || true
    wait $SERVER_PID 2>/dev/null || true
    echo "  ✅ Server stopped"
  fi
}

# Register cleanup function
trap cleanup EXIT

# Wait for server to start
echo "  Waiting for server to be ready..."
MAX_RETRIES=30
RETRY_COUNT=0
APP_URL="${APP_URL:-http://localhost:3000}"

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
  if curl -s "$APP_URL" >/dev/null 2>&1; then
    echo "  ✅ Server is ready!"
    break
  fi
  
  RETRY_COUNT=$((RETRY_COUNT + 1))
  if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
    echo "  ❌ Server failed to start after $MAX_RETRIES attempts"
    exit 1
  fi
  
  echo "  Waiting... (attempt $RETRY_COUNT/$MAX_RETRIES)"
  sleep 1
done

# ==========================================
# 4. Run visual check script
# ==========================================
echo ""
echo "🎯 Running visual check script..."
cd "$REPO_ROOT"

export APP_URL="${APP_URL:-http://localhost:3000}"
export SCREENSHOT_PREFIX="${SCREENSHOT_PREFIX:-visual-check}"

node .github/scripts/visual-check.js

echo ""
echo "✅ Playwright screenshot helper completed successfully!"
