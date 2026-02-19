#!/usr/bin/env bash
# ============================================================
# Start Polymarket Executor
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PORT=8789

# Check if already running
if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
  echo "⚠️  Executor already running on port $PORT"
  exit 0
fi

# Load env from OpenClaw config if available
if command -v openclaw >/dev/null; then
  openclaw config get skills.entries.polymarket-exec.env 2>/dev/null | python3 - <<'PY' > /tmp/clawd-polymarket-env.sh
import json, sys, shlex
try:
    env = json.load(sys.stdin)
except Exception:
    env = {}
for k, v in env.items():
    if v is None or v == "":
        continue
    print(f"export {k}={shlex.quote(str(v))}")
PY

  # shellcheck disable=SC1091
  source /tmp/clawd-polymarket-env.sh || true
  rm -f /tmp/clawd-polymarket-env.sh
fi

# Check required vars
if [[ -z "${POLYMARKET_PK:-}" ]]; then
  echo "⚠️  POLYMARKET_PK not set. Configure in ~/.openclaw/openclaw.json"
  echo "   Or export: export POLYMARKET_PK=0x..."
fi

if [[ -z "${POLYMARKET_ADDRESS:-}" ]]; then
  echo "⚠️  POLYMARKET_ADDRESS not set. Configure in ~/.openclaw/openclaw.json"
  echo "   Or export: export POLYMARKET_ADDRESS=0x..."
fi

# Generate token if not set
if [[ -z "${EXEC_API_TOKEN:-}" ]]; then
  EXEC_API_TOKEN=$(openssl rand -hex 32)
  echo "⚠️  Generated EXEC_API_TOKEN: ${EXEC_API_TOKEN:0:16}..."
  echo "   Save this in your config!"
  export EXEC_API_TOKEN
fi

# Start executor
echo "🚀 Starting Polymarket Executor..."
echo ""
echo "   Port: $PORT"
echo "   Dry Run: ${DRY_RUN:-false}"
echo "   Max Trade: \$${MAX_TRADE_USD:-100}"
echo "   API Token: ${EXEC_API_TOKEN:0:16}..."
echo ""
echo "   API URL: http://127.0.0.1:$PORT"
echo "   Health: http://127.0.0.1:$PORT/health"
echo ""

cd "$PROJECT_DIR"
python3 scripts/polymarket-exec.py --serve --port $PORT --token "$EXEC_API_TOKEN"
