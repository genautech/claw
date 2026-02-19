#!/usr/bin/env bash
# ============================================================
# Clawd Full Environment Launcher
# ============================================================
# Starts OpenClaw gateway, dashboard, and prints all access URLs
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DASHBOARD_DIR="$PROJECT_DIR/dashboard-web"
GATEWAY_PORT=18789
DASHBOARD_PORT=8787

# Get gateway token
TOKEN=$(openclaw config get gateway.auth.token 2>/dev/null | grep -v "Doctor" | grep -v "^│" | grep -v "^├" | grep -v "^└" | tr -d ' "' || echo "")

if [[ -z "$TOKEN" ]]; then
  echo "⚠️  Could not read gateway token from config"
  TOKEN=""
fi

echo "═══════════════════════════════════════════════════════════"
echo "   🚀 Starting Clawd Environment"
echo "═══════════════════════════════════════════════════════════"
echo ""

# 1. Check/Start Gateway
echo "1️⃣  Checking OpenClaw Gateway..."
if openclaw gateway status >/dev/null 2>&1; then
  GATEWAY_STATUS=$(openclaw health 2>/dev/null | head -1 || echo "unknown")
  if echo "$GATEWAY_STATUS" | grep -q "ok\|running"; then
    echo "   ✅ Gateway already running"
  else
    echo "   ⚠️  Gateway process exists but may not be healthy"
    echo "   Starting gateway..."
    openclaw gateway start 2>/dev/null || true
    sleep 3
  fi
else
  echo "   🚀 Starting gateway..."
  openclaw gateway start 2>/dev/null || true
  sleep 3
fi

# 2. Start Dashboard
echo ""
echo "2️⃣  Starting Dashboard..."
if lsof -Pi :$DASHBOARD_PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
  echo "   ✅ Dashboard already running on port $DASHBOARD_PORT"
else
  cd "$DASHBOARD_DIR"
  python3 -m http.server $DASHBOARD_PORT > /tmp/clawd-dashboard.log 2>&1 &
  DASHBOARD_PID=$!
  echo "   ✅ Dashboard started (PID: $DASHBOARD_PID)"
  sleep 2
fi

# 3. Print all URLs
echo ""
echo "═══════════════════════════════════════════════════════════"
echo "   📍 Access URLs"
echo "═══════════════════════════════════════════════════════════"
echo ""

if [[ -n "$TOKEN" ]]; then
  echo "   🌐 OpenClaw Control UI:"
  echo "      http://127.0.0.1:$GATEWAY_PORT/#token=$TOKEN"
  echo ""
  echo "   💬 Web Chat:"
  echo "      http://127.0.0.1:$GATEWAY_PORT/chat?session=agent%3Amain%3Amain&token=$TOKEN"
  echo ""
else
  echo "   🌐 OpenClaw Control UI:"
  echo "      http://127.0.0.1:$GATEWAY_PORT/"
  echo ""
  echo "   💬 Web Chat:"
  echo "      http://127.0.0.1:$GATEWAY_PORT/chat?session=agent%3Amain%3Amain"
  echo ""
fi

echo "   📊 Clawd Dashboard:"
if [[ -n "$TOKEN" ]]; then
  echo "      http://127.0.0.1:$DASHBOARD_PORT/#token=$TOKEN"
else
  echo "      http://127.0.0.1:$DASHBOARD_PORT/"
fi

echo ""
echo "═══════════════════════════════════════════════════════════"
echo ""

# 4. Open dashboard in browser
if command -v open >/dev/null; then
  if [[ -n "$TOKEN" ]]; then
    open "http://127.0.0.1:$DASHBOARD_PORT/#token=$TOKEN"
  else
    open "http://127.0.0.1:$DASHBOARD_PORT/"
  fi
elif command -v xdg-open >/dev/null; then
  if [[ -n "$TOKEN" ]]; then
    xdg-open "http://127.0.0.1:$DASHBOARD_PORT/#token=$TOKEN"
  else
    xdg-open "http://127.0.0.1:$DASHBOARD_PORT/"
  fi
fi

echo "   ✅ Environment ready!"
echo ""
echo "   Press Ctrl+C to stop dashboard (gateway runs as service)"
echo ""
