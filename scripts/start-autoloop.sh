#!/usr/bin/env bash
# ============================================================
# Start Smart Loop (intelligent agent cycle) in background
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_FILE="/tmp/smart-loop.log"
PATTERN="scripts/smart-loop.sh"
PID_FILE="/tmp/clawd-smart-loop.pid"

cd "$PROJECT_DIR"

if pgrep -f "$PATTERN" >/dev/null 2>&1; then
  echo "✓ Smart Loop já está rodando (pgrep -f $PATTERN)"
  echo "  Log: $LOG_FILE"
  echo "  PID: $(cat "$PID_FILE" 2>/dev/null || echo '?')"
  exit 0
fi

nohup bash "$PROJECT_DIR/scripts/smart-loop.sh" >> "$LOG_FILE" 2>&1 &
sleep 1

if pgrep -f "$PATTERN" >/dev/null 2>&1; then
  echo "✓ Smart Loop iniciado em background"
  echo "  Log: $LOG_FILE"
  echo "  Estado: data/loop-state.json"
  echo "  Config: data/loop-config.json"
else
  echo "✗ Falha ao iniciar smart-loop — veja $LOG_FILE"
  exit 1
fi
