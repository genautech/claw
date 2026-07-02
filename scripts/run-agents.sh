#!/usr/bin/env bash
# ============================================================
# PolyAgents Autonomous Runner
# ============================================================
# Runs trading agents in sequence or by phase group.
#
# Usage:
#   bash scripts/run-agents.sh [all|smart-cycle|preflight|analysis|decision|execution|recovery|observability|...]
#   bash scripts/run-agents.sh all --with-lock [--cycle-id ID] [--source NAME]
#
# Phases (smart-cycle):
#   preflight     → ensure-running + LatencyNinja
#   analysis      → PolyClaw, PolyWhale, Polybot
#   decision      → auto-accept recommendations (if autoExecute)
#   execution     → Executor --process-recs
#   recovery      → AutoCorrect + Brimo check
#   observability → MC heartbeat (SmartLoop)
# ============================================================

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DATA_DIR="$ROOT/data"
LOGS_DIR="$ROOT/logs"
MC_API="http://localhost:8000/api/v1"
MC_TOKEN="28564452b9b917626d3826260fa50fc0648905bb6e4fff85f4904bb248ee43ff"

# shellcheck source=lib/cycle-lock.sh
source "$ROOT/scripts/lib/cycle-lock.sh"

green='\033[0;32m'; yellow='\033[1;33m'; red='\033[0;31m'; nc='\033[0m'
log()  { echo -e "${green}[$(date +%H:%M:%S)]${nc} $*"; }
warn() { echo -e "${yellow}[$(date +%H:%M:%S)]${nc} $*"; }
err()  { echo -e "${red}[$(date +%H:%M:%S)]${nc} $*"; }

mkdir -p "$DATA_DIR" "$LOGS_DIR" "$ROOT/memory"

WITH_LOCK=0
CYCLE_ID=""
CYCLE_SOURCE="manual"
COMMAND=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --with-lock) WITH_LOCK=1; shift ;;
    --cycle-id) CYCLE_ID="$2"; shift 2 ;;
    --source) CYCLE_SOURCE="$2"; shift 2 ;;
    --phase)
      if [[ -n "${COMMAND}" && "${COMMAND}" != "phase" ]]; then
        err "Não misture --phase com outro comando"
        exit 1
      fi
      COMMAND="phase"
      PHASE_ARG="$2"
      shift 2
      ;;
    *)
      if [[ -z "${COMMAND}" ]]; then
        COMMAND="$1"
      fi
      shift
      ;;
  esac
done

COMMAND="${COMMAND:-all}"

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
  local llm_flag=""
  if [[ -n "${ANTHROPIC_API_KEY:-}" ]] || { [[ -f "$HOME/.secrets/.env" ]] && grep -q '^ANTHROPIC_API_KEY=' "$HOME/.secrets/.env" 2>/dev/null; }; then
    llm_flag="--llm"
  fi
  python3 "$ROOT/scripts/agent_polywhale.py" $llm_flag || warn "PolyWhale: Analysis failed"
  log "🐋 PolyWhale: Cycle complete"
}

run_polybot() {
  log "🤖 Polybot Analyzer: Scanning competitor wallets..."
  mc_heartbeat "Polybot Analyzer" "healthy"
  python3 "$ROOT/scripts/agent_polybot_analyzer.py" --all --apply-config || warn "Polybot: Analysis failed"
  log "🤖 Polybot Analyzer: Cycle complete"
}

run_decision() {
  log "🎯 Decision: Verificando autoExecute..."
  python3 - <<PY || true
import json
from pathlib import Path

root = Path("$ROOT")
config_path = root / "data" / "dashboard-config.json"
status_path = root / "data" / "recommendation-status.json"
recs_path = root / "data" / "recommendations.jsonl"

try:
    cfg = json.loads(config_path.read_text())
except Exception:
    cfg = {}

if not cfg.get("autoExecute"):
  print("autoExecute desligado — aprovação manual")
  raise SystemExit(0)

min_conf = str(cfg.get("minConfidence", "MEDIUM")).upper()
conf_rank = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}
min_rank = conf_rank.get(min_conf, 2)
min_edge = float(cfg.get("minEdge", 5))

status = {}
if status_path.exists():
    try:
        status = json.loads(status_path.read_text())
    except Exception:
        status = {}

if not recs_path.exists():
    raise SystemExit(0)

for line in recs_path.read_text().strip().split("\n"):
    if not line.strip():
        continue
    try:
        rec = json.loads(line)
    except Exception:
        continue
    rid = rec.get("id") or rec.get("market_id") or rec.get("timestamp")
    if not rid or status.get(rid, {}).get("status") in ("accepted", "rejected", "executed"):
        continue
    if rec.get("source") != "polywhale_v2":
        continue
    conf = str(rec.get("confidence", "LOW")).upper()
    edge = float(rec.get("edge", 0) or 0) * 100
    if conf_rank.get(conf, 0) >= min_rank and edge >= min_edge:
        status[rid] = {
            "status": "accepted",
            "updatedAt": __import__("datetime").datetime.utcnow().isoformat() + "Z",
            "auto": True,
        }

status_path.write_text(json.dumps(status, indent=2))
print(f"autoExecute: {sum(1 for v in status.values() if v.get('auto'))} recs auto-aceitas")
PY
  log "🎯 Decision: Complete"
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
import json, shlex, os
config_path = os.path.expanduser("~/.openclaw/openclaw.json")
try:
    with open(config_path, "r") as f:
        config = json.load(f)
    env = config.get("skills", {}).get("entries", {}).get("polymarket-exec", {}).get("env", {})
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
    export EXEC_API_TOKEN=${EXEC_API_TOKEN:-"$(openssl rand -hex 32)"}

    run_decision

    log "⚡ Executor: Processando recomendações do PolyWhale..."
    python3 "$ROOT/scripts/polymarket-exec.py" --process-recs >> "/tmp/run-agents.log" 2>&1 || warn "Executor: Falha ao processar recomendações"
  else
    warn "⚡ Executor: API offline (port 8789)"
  fi

  echo "$(date -u +"%Y-%m-%d %H:%M:%S"),000 [INFO] Heartbeat check - executor cycle complete" >> "/tmp/run-agents.log" 2>/dev/null || true
  log "⚡ Executor: Cycle complete"
}

run_execution() {
  log "⚡ Execution: Processando ordens aprovadas..."
  mc_heartbeat "Polymarket Executor" "healthy"

  if ! lsof -Pi :8789 -sTCP:LISTEN -t >/dev/null 2>&1; then
    warn "⚡ Execution: API offline (port 8789)"
    return 0
  fi

  python3 - <<'PY' > /tmp/clawd-polymarket-env.sh
import json, shlex, os
config_path = os.path.expanduser("~/.openclaw/openclaw.json")
try:
    with open(config_path, "r") as f:
        config = json.load(f)
    env = config.get("skills", {}).get("entries", {}).get("polymarket-exec", {}).get("env", {})
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
  export EXEC_API_TOKEN=${EXEC_API_TOKEN:-"$(openssl rand -hex 32)"}

  python3 "$ROOT/scripts/polymarket-exec.py" --process-recs >> "/tmp/run-agents.log" 2>&1 || warn "Execution: Falha ao processar recomendações"
  log "⚡ Execution: Complete"
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
except Exception:
    checks['gamma_api'] = {'latency_ms': -1, 'status': 'error'}

start = time.time()
try:
    urllib.request.urlopen('http://127.0.0.1:8789/health', timeout=3)
    checks['executor_api'] = {'latency_ms': round((time.time()-start)*1000,1), 'status': 'ok'}
except Exception:
    checks['executor_api'] = {'latency_ms': -1, 'status': 'offline'}

start = time.time()
try:
    s = socket.create_connection(('127.0.0.1', 6379), timeout=2)
    s.sendall(b'PING\r\n'); s.recv(64); s.close()
    checks['redis'] = {'latency_ms': round((time.time()-start)*1000,1), 'status': 'ok'}
except Exception:
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

run_preflight() {
  log "🛫 Pre-flight: Verificando serviços..."
  bash "$ROOT/scripts/ensure-running.sh" >/dev/null 2>&1 || warn "Pre-flight: ensure-running reported issues"
  run_ninja
  log "🛫 Pre-flight: Complete"
}

run_analysis() {
  log "🔬 Analysis: Polybot (calibrar) → PolyWhale → PolyClaw..."
  run_polybot
  echo ""
  run_polywhale
  echo ""
  run_polyclaw
  log "🔬 Analysis: Complete"
}

run_autocorrect() {
  log "🔧 AutoCorrect: Escaneando erros de execução..."
  mc_heartbeat "AutoCorrect" "healthy"
  python3 "$ROOT/scripts/agent_autocorrect.py" || warn "AutoCorrect: Scan failed"
  log "🔧 AutoCorrect: Complete"
}

run_brimo_check() {
  log "🐻 Brimo: Verificando posições..."
  mc_heartbeat "Brimo" "healthy"

  if ! pgrep -f "brimo.py --monitor" >/dev/null 2>&1; then
    warn "Brimo daemon não está rodando — apenas check-once"
  fi

  python3 "$ROOT/scripts/brimo.py" --check-once || warn "Brimo: Check failed"
  log "🐻 Brimo: Complete"
}

run_recovery() {
  log "🩹 Recovery: AutoCorrect + Brimo..."
  run_autocorrect
  echo ""
  run_brimo_check
  log "🩹 Recovery: Complete"
}

run_arbitrage() {
  log "🥷 Arbitrage: scan + pipeline bridge..."
  mc_heartbeat "ArbitrageNinja" "healthy"

  if ! pgrep -f "agent_ninja_arbitrage.py" >/dev/null 2>&1; then
    warn "ArbitrageNinja agent offline — quick scan via timeout"
    timeout 45 python3 "$ROOT/scripts/agent_ninja_arbitrage.py" --market auto --duration 40 2>/dev/null || warn "Arbitrage scan skipped"
  else
    log "ArbitrageNinja daemon já rodando"
  fi

  python3 "$ROOT/scripts/arb-to-pipeline.py" || warn "arb-to-pipeline failed"
  log "🥷 Arbitrage: Complete"
}

run_observability() {
  log "📡 Observability: tokens + heartbeat..."
  mc_heartbeat "SmartLoop" "healthy"
  python3 "$ROOT/scripts/collect-token-usage.py" >/dev/null 2>&1 || warn "Token usage collect skipped"
  log "📡 Observability: Complete"
}

run_smart_cycle() {
  log "🚀 Smart cycle — todas as fases..."
  run_preflight
  echo ""
  run_arbitrage
  echo ""
  run_analysis
  echo ""
  run_decision
  echo ""
  run_execution
  echo ""
  run_recovery
  echo ""
  run_observability
  log "✅ Smart cycle complete"
}

run_legacy_all() {
  log "🚀 Running all PolyAgents (legacy)..."
  run_polyclaw
  echo ""
  run_polywhale
  echo ""
  run_polybot
  echo ""
  run_executor
  echo ""
  run_ninja
  log "✅ All agents completed cycle"
}

run_command() {
  case "$COMMAND" in
    all) run_legacy_all ;;
    smart-cycle) run_smart_cycle ;;
    preflight) run_preflight ;;
    arbitrage) run_arbitrage ;;
    analysis) run_analysis ;;
    decision) run_decision ;;
    execution) run_execution ;;
    recovery) run_recovery ;;
    observability) run_observability ;;
    polyclaw) run_polyclaw ;;
    polywhale) run_polywhale ;;
    polybot) run_polybot ;;
    executor) run_executor ;;
    ninja) run_ninja ;;
    autocorrect) run_autocorrect ;;
    brimo-check) run_brimo_check ;;
    phase)
      case "${PHASE_ARG:-}" in
        preflight) run_preflight ;;
        arbitrage) run_arbitrage ;;
        analysis) run_analysis ;;
        decision) run_decision ;;
        execution) run_execution ;;
        arbitrage) run_arbitrage ;;
        recovery) run_recovery ;;
        observability) run_observability ;;
        *)
          err "Fase desconhecida: ${PHASE_ARG:-}"
          exit 1
          ;;
      esac
      ;;
    *)
      echo "Usage: $0 [all|smart-cycle|preflight|arbitrage|analysis|decision|execution|recovery|observability|...] [--with-lock]"
      echo "       $0 --phase <preflight|arbitrage|analysis|decision|execution|recovery|observability>"
      exit 1
      ;;
  esac
}

if [[ "$WITH_LOCK" -eq 1 ]]; then
  if [[ -z "$CYCLE_ID" ]]; then
    CYCLE_ID="cycle-$(date -u +"%Y%m%dT%H%M%SZ")"
  fi
  export CYCLE_LOCK_META
  if ! cycle_lock_acquire "$CYCLE_ID" "$CYCLE_SOURCE"; then
    err "Ciclo em andamento — lock ativo ($(cycle_lock_read_meta))"
    exit 2
  fi
  trap cycle_lock_release EXIT
fi

run_command
