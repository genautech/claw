#!/usr/bin/env bash
# ============================================================
# Clawd Dashboard Launcher
# ============================================================
# Starts the local monitoring dashboard on port 8787
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DASHBOARD_DIR="$PROJECT_DIR/dashboard-web"
PORT=8787

# Get gateway token
TOKEN=$(openclaw config get gateway.auth.token 2>/dev/null | grep -v "Doctor" | grep -v "^│" | grep -v "^├" | grep -v "^└" | tr -d ' "' || echo "")

if [[ -z "$TOKEN" ]]; then
  echo "⚠️  Could not read gateway token from config"
  echo "   Dashboard will prompt for token on load"
  TOKEN=""
fi

# Check if port is already in use
if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
  echo "⚠️  Port $PORT is already in use"
  echo "   Dashboard may already be running"
  echo ""
fi

# Check if already running
SERVER_PID=""
if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
  echo "⚠️  Dashboard already running on port $PORT"
  echo ""
else
  # Start HTTP server in background
  cd "$DASHBOARD_DIR"
  python3 -m http.server $PORT > /tmp/clawd-dashboard.log 2>&1 &
  SERVER_PID=$!
  echo "🚀 Starting Clawd Dashboard (PID: $SERVER_PID)..."
  sleep 2
fi

# Construct URL
DASHBOARD_URL="http://127.0.0.1:$PORT"
if [[ -n "$TOKEN" ]]; then
  DASHBOARD_URL="$DASHBOARD_URL/#token=$TOKEN"
fi

echo ""
echo "════════════════════════════════════════"
echo "   📊 Clawd Monitoring Dashboard"
echo "════════════════════════════════════════"
echo ""
echo "   URL: $DASHBOARD_URL"
echo ""
echo "   Opening in browser..."
echo ""

# Open in browser
if command -v open >/dev/null; then
  open "$DASHBOARD_URL"
elif command -v xdg-open >/dev/null; then
  xdg-open "$DASHBOARD_URL"
else
  echo "   Please open the URL above in your browser"
fi

echo ""
echo "   Press Ctrl+C to stop (or run: pkill -f 'http.server $PORT')"
echo ""

# Keep script running if server was started here
if [[ -n "$SERVER_PID" ]] && kill -0 $SERVER_PID 2>/dev/null; then
  wait $SERVER_PID
fi
