#!/usr/bin/env bash
# ============================================================
# PolyAgents Autonomous Runner
# ============================================================
# Runs all trading agents in sequence, each writing to their
# respective JSONL data files for the dashboard to display.
#
# Usage:
#   bash scripts/run-agents.sh [all|polyclaw|polywhale|executor|ninja]
#
# Data flow:
#   PolyClaw   → data/simulated_trades.jsonl
#   PolyWhale  → data/recommendations.jsonl
#   Executor   → data/executions.jsonl + logs/polymarket-exec.log
#   Ninja      → logs/latency-report.json
#
# Dashboard reads from: http://localhost:8888
# Mission Control:      http://localhost:3000
# ============================================================

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DATA_DIR="$ROOT/data"
LOGS_DIR="$ROOT/logs"
MC_API="http://localhost:8000/api/v1"
MC_TOKEN="28564452b9b917626d3826260fa50fc0648905bb6e4fff85f4904bb248ee43ff"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

green='\033[0;32m'; yellow='\033[1;33m'; red='\033[0;31m'; nc='\033[0m'
log()  { echo -e "${green}[$(date +%H:%M:%S)]${nc} $*"; }
warn() { echo -e "${yellow}[$(date +%H:%M:%S)]${nc} $*"; }
err()  { echo -e "${red}[$(date +%H:%M:%S)]${nc} $*"; }

mkdir -p "$DATA_DIR" "$LOGS_DIR"

mc_heartbeat() {
  local agent_name="$1"
  local status="${2:-healthy}"
  curl -s -X POST -H "Authorization: Bearer $MC_TOKEN" -H "Content-Type: application/json" \
    "$MC_API/agents/heartbeat" \
    -d "{\"name\":\"$agent_name\",\"status\":\"$status\"}" >/dev/null 2>&1 || true
}

run_polyclaw() {
  log "🐾 PolyClaw: Scanning markets for paper trades..."
  mc_heartbeat "PolyClaw" "healthy"
  python3 "$ROOT/scripts/agent_polyclaw.py" || warn "PolyClaw: Analysis failed"
  log "🐾 PolyClaw: Cycle complete"
}

run_polywhale() {
  log "🐋 PolyWhale: Analyzing markets for recommendations..."
  mc_heartbeat "PolyWhale" "healthy"
  python3 "$ROOT/scripts/agent_polywhale.py" || warn "PolyWhale: Analysis failed"
  log "🐋 PolyWhale: Cycle complete"
}

run_executor() {
  log "⚡ Executor: Checking for pending orders..."
  mc_heartbeat "Polymarket Executor" "healthy"

  if lsof -Pi :8789 -sTCP:LISTEN -t >/dev/null 2>&1; then
    local health
    health=$(curl -s http://127.0.0.1:8789/health 2>/dev/null || echo "{}")
    log "⚡ Executor: API online - $health"
    
    log "⚡ Executor: Carregando credenciais..."
    python3 - <<'PY' > /tmp/clawd-polymarket-env.sh
import json, sys, shlex, os
config_path = os.path.expanduser("~/.openclaw/openclaw.json")
try:
    with open(config_path, "r") as f:
        config = json.load(f)
    env = config.get("skills", {}).get("entries", {}).get("polymarket-exec", {}).get("env", {})
except Exception:
    env = {}
for k, v in env.items():
    if v is None or v == "": continue
    print(f"export {k}={shlex.quote(str(v))}")
PY
    source /tmp/clawd-polymarket-env.sh || true
    rm -f /tmp/clawd-polymarket-env.sh
    export EXEC_API_TOKEN=${EXEC_API_TOKEN:-"$(openssl rand -hex 32)"}

    log "⚡ Executor: Processando recomendações do PolyWhale..."
    python3 "$ROOT/scripts/polymarket-exec.py" --process-recs >> "/tmp/run-agents.log" 2>&1 || warn "Executor: Falha ao processar recomendações"
  else
    warn "⚡ Executor: API offline (port 8789)"
  fi

  echo "$(date -u +"%Y-%m-%d %H:%M:%S"),000 [INFO] Heartbeat check - executor cycle complete" >> "/tmp/run-agents.log" 2>/dev/null || true
  log "⚡ Executor: Cycle complete"
}

run_ninja() {
  log "🥷 LatencyNinja: Running latency checks..."
  mc_heartbeat "LatencyNinja" "healthy"

  python3 -c "
import json, time, socket, ssl, urllib.request
from datetime import datetime, timezone
from pathlib import Path

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
checks = {}
start = time.time()
try:
    req = urllib.request.Request('https://gamma-api.polymarket.com/markets?limit=1', headers={'User-Agent': 'LatencyNinja/1.0'})
    urllib.request.urlopen(req, timeout=5, context=ctx)
    checks['gamma_api'] = {'latency_ms': round((time.time()-start)*1000,1), 'status': 'ok'}
except Exception as e:
    checks['gamma_api'] = {'latency_ms': -1, 'status': 'error'}

start = time.time()
try:
    urllib.request.urlopen('http://127.0.0.1:8789/health', timeout=3)
    checks['executor_api'] = {'latency_ms': round((time.time()-start)*1000,1), 'status': 'ok'}
except:
    checks['executor_api'] = {'latency_ms': -1, 'status': 'offline'}

start = time.time()
try:
    s = socket.create_connection(('127.0.0.1', 6379), timeout=2)
    s.sendall(b'PING\r\n'); s.recv(64); s.close()
    checks['redis'] = {'latency_ms': round((time.time()-start)*1000,1), 'status': 'ok'}
except:
    checks['redis'] = {'latency_ms': -1, 'status': 'offline'}

report = {'timestamp': datetime.now(timezone.utc).isoformat(), 'checks': checks, 'all_healthy': all(c.get('status')=='ok' for c in checks.values())}
try:
    Path('$LOGS_DIR/latency-report.json').write_text(json.dumps(report, indent=2))
except PermissionError:
    Path('/tmp/latency-report.json').write_text(json.dumps(report, indent=2))
for n, c in checks.items():
    s = 'ok' if c['status']=='ok' else 'WARN' if c['status']=='slow' else 'FAIL'
    print(f'  {s} {n}: {c[\"latency_ms\"]}ms')
" || warn "LatencyNinja: Check failed"

  log "🥷 LatencyNinja: Cycle complete"
}

case "${1:-all}" in
  all)
    log "🚀 Running all PolyAgents..."
    echo ""
    run_polyclaw
    echo ""
    run_polywhale
    echo ""
    run_executor
    echo ""
    run_ninja
    echo ""
    log "✅ All agents completed cycle"
    ;;
  polyclaw)  run_polyclaw ;;
  polywhale) run_polywhale ;;
  executor)  run_executor ;;
  ninja)     run_ninja ;;
  *)
    echo "Usage: $0 [all|polyclaw|polywhale|executor|ninja]"
    exit 1
    ;;
esac
