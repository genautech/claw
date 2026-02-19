#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HOOK_SCRIPT="$ROOT/scripts/polymarket-hooks.sh"
HOOK_LOG="$ROOT/logs/polymarket-hooks.log"
EXEC_LOG="$ROOT/logs/polymarket-exec.log"

green='\033[0;32m'; yellow='\033[1;33m'; red='\033[0;31m'; nc='\033[0m'
ok(){ echo -e "${green}[OK]${nc} $*"; }
warn(){ echo -e "${yellow}[WARN]${nc} $*"; }
err(){ echo -e "${red}[ERR]${nc} $*"; }

status_cmd() {
  echo "=== Agent Manager Status ==="
  if openclaw gateway health >/dev/null 2>&1; then ok "Gateway online"; else err "Gateway offline"; fi

  if lsof -Pi :8787 -sTCP:LISTEN -t >/dev/null 2>&1; then ok "Dashboard online (:8787)"; else warn "Dashboard offline"; fi
  if lsof -Pi :8789 -sTCP:LISTEN -t >/dev/null 2>&1; then ok "Polymarket executor online (:8789)"; else warn "Polymarket executor offline"; fi

  if [[ -f "$HOOK_LOG" ]]; then
    local alerts
    alerts=$(tail -n 200 "$HOOK_LOG" | grep -c "\[ALERT\]" || true)
    if [[ "$alerts" -gt 0 ]]; then warn "Hook alerts (last 200 lines): $alerts"; else ok "No recent hook alerts"; fi
  else
    warn "Hook log not found: $HOOK_LOG"
  fi
}

start_cmd() {
  openclaw gateway start || true
  bash "$ROOT/scripts/start-dashboard.sh" || true
  bash "$ROOT/scripts/start-executor.sh" || true
  ok "Start sequence executed"
}

stop_cmd() {
  openclaw gateway stop || true
  if lsof -Pi :8789 -sTCP:LISTEN -t >/dev/null 2>&1; then kill "$(lsof -ti :8789)" || true; fi
  if lsof -Pi :8787 -sTCP:LISTEN -t >/dev/null 2>&1; then kill "$(lsof -ti :8787)" || true; fi
  ok "Stop sequence executed"
}

hooks_cmd() {
  "$HOOK_SCRIPT" all
}

logs_cmd() {
  echo "--- polymarket-hooks.log ---"
  tail -n 80 "$HOOK_LOG" 2>/dev/null || true
  echo "--- polymarket-exec.log ---"
  tail -n 80 "$EXEC_LOG" 2>/dev/null || true
}

case "${1:-status}" in
  status) status_cmd ;;
  start) start_cmd ;;
  stop) stop_cmd ;;
  restart) stop_cmd; sleep 1; start_cmd ;;
  hooks) hooks_cmd ;;
  logs) logs_cmd ;;
  *)
    echo "Usage: $0 [status|start|stop|restart|hooks|logs]"
    exit 1
    ;;
esac
