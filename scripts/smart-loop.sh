#!/usr/bin/env bash
# ============================================================
# Smart Loop — Orquestrador inteligente de agentes (24/7)
# ============================================================
# Substitui autoloop.sh com fases, lock, intervalo dinâmico e estado.
#
# Usage:
#   bash scripts/smart-loop.sh          # loop infinito
#   bash scripts/smart-loop.sh --once   # um ciclo e sai
# ============================================================

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CONFIG_FILE="$ROOT/data/loop-config.json"
STATE_FILE="$ROOT/data/loop-state.json"
PID_FILE="/tmp/clawd-smart-loop.pid"
LOG_FILE="/tmp/smart-loop.log"

# shellcheck source=lib/cycle-lock.sh
source "$ROOT/scripts/lib/cycle-lock.sh"

green='\033[0;32m'; yellow='\033[1;33m'; red='\033[0;31m'; nc='\033[0m'
log()  { echo -e "${green}[$(date +%H:%M:%S)]${nc} $*" | tee -a "$LOG_FILE"; }
warn() { echo -e "${yellow}[$(date +%H:%M:%S)]${nc} $*" | tee -a "$LOG_FILE"; }
err()  { echo -e "${red}[$(date +%H:%M:%S)]${nc} $*" | tee -a "$LOG_FILE"; }

RUN_ONCE=0
if [[ "${1:-}" == "--once" ]]; then
  RUN_ONCE=1
fi

echo $$ > "$PID_FILE"

read_config() {
  python3 - <<PY
import json
from pathlib import Path
defaults = {
    "intervalSeconds": 900,
    "minIntervalSeconds": 300,
    "maxIntervalSeconds": 1800,
    "phases": ["preflight", "arbitrage", "analysis", "decision", "execution", "recovery", "observability"],
    "accelerateOnPendingRecs": True,
    "accelerateOnErrors": True,
    "writeMemorySummary": True,
    "rateLimitBackoffSeconds": 60,
}
path = Path("$CONFIG_FILE")
cfg = defaults.copy()
if path.exists():
    try:
        cfg.update(json.loads(path.read_text()))
    except Exception:
        pass
print(json.dumps(cfg))
PY
}

compute_interval() {
  local cfg_json="$1"
  python3 - <<PY
import json
from datetime import datetime, timezone
from pathlib import Path

cfg = json.loads('''$cfg_json''')
root = Path("$ROOT")
base = int(cfg.get("intervalSeconds", 900))
min_i = int(cfg.get("minIntervalSeconds", 300))
max_i = int(cfg.get("maxIntervalSeconds", 1800))
interval = base

# Acelerar se recs pendentes
if cfg.get("accelerateOnPendingRecs"):
    status_path = root / "data" / "recommendation-status.json"
    recs_path = root / "data" / "recommendations.jsonl"
    status = {}
    if status_path.exists():
        try:
            status = json.loads(status_path.read_text())
        except Exception:
            pass
    pending = 0
    if recs_path.exists():
        for line in recs_path.read_text().strip().split("\n"):
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            rid = rec.get("id") or rec.get("market_id") or rec.get("timestamp")
            if rid and status.get(rid, {}).get("status") not in ("accepted", "rejected", "executed"):
                pending += 1
    if pending > 0:
        interval = min(interval, min_i)

# Acelerar se erros recentes ou correções aprovadas na fila
if cfg.get("accelerateOnErrors"):
    for fname in ("corrections.jsonl", "approved_corrections.jsonl"):
        corrections = root / "data" / fname
        if corrections.exists():
            lines = [l for l in corrections.read_text().strip().split("\n") if l.strip()]
            if lines:
                try:
                    last = json.loads(lines[-1])
                    ts = last.get("timestamp") or last.get("createdAt")
                    if ts:
                        interval = min(interval, min_i)
                        break
                except Exception:
                    pass

# Desacelerar se rate limit flag no state
state_path = root / "data" / "loop-state.json"
if state_path.exists():
    try:
        state = json.loads(state_path.read_text())
        if state.get("rateLimited"):
            interval = max_i
    except Exception:
        pass

# Desacelerar se sem edges no último ciclo
latency = root / "logs" / "latency-report.json"
if latency.exists():
    try:
        report = json.loads(latency.read_text())
        if not report.get("all_healthy"):
            interval = min(max(interval, min_i), max_i)
    except Exception:
        pass

interval = max(min_i, min(interval, max_i))
print(interval)
PY
}

write_loop_state() {
  local cycle_id="$1"
  local cycle_num="$2"
  local started_at="$3"
  local completed_at="$4"
  local interval_used="$5"
  local phases_json="$6"
  local errors_json="$7"
  local summary="$8"
  local rate_limited="${9:-false}"

  python3 - <<PY
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

interval = int("$interval_used")
completed = "$completed_at"
next_run = (datetime.fromisoformat(completed.replace("Z", "+00:00")) + timedelta(seconds=interval)).strftime("%Y-%m-%dT%H:%M:%SZ")

state = {
    "cycleId": "$cycle_id",
    "cycleNumber": int("$cycle_num"),
    "startedAt": "$started_at",
    "completedAt": completed,
    "phases": json.loads('''$phases_json'''),
    "nextRunAt": next_run,
    "intervalUsed": interval,
    "errors": json.loads('''$errors_json'''),
    "summary": """$summary""",
    "lockHeld": False,
    "smartLoopPid": int(open("$PID_FILE").read().strip()) if Path("$PID_FILE").exists() else None,
    "rateLimited": """$rate_limited""" == "true",
}
Path("$STATE_FILE").write_text(json.dumps(state, indent=2))

if """${WRITE_MEMORY:-0}""" == "1":
    mem_dir = Path("$ROOT/memory")
    mem_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    mem_file = mem_dir / f"{today}.md"
    line = f"\\n## SmartLoop ciclo {cycle_num} ({completed})\\n- {state['summary']}\\n- Próximo ciclo: {next_run}\\n"
    with open(mem_file, "a") as f:
        f.write(line)

print(json.dumps({"nextRunAt": next_run, "intervalUsed": interval}))
PY
}

run_one_cycle() {
  local cycle_num="$1"
  local cfg_json="$2"
  local cycle_id="cycle-$(date -u +"%Y%m%dT%H%M%SZ")-${cycle_num}"
  local started_at completed_at
  started_at=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

  local phases_json='[]'
  local errors_json='[]'
  local summary="Ciclo $cycle_num completo"
  local rate_limited="false"

  export CYCLE_LOCK_META
  if ! cycle_lock_acquire "$cycle_id" "smart-loop"; then
    warn "Ciclo $cycle_num ignorado — outro ciclo em andamento"
    return 1
  fi

  trap cycle_lock_release EXIT

  local phase_results
  phase_results=$(python3 - <<PY
import json, subprocess, os
root = "$ROOT"
cfg = json.loads('''$cfg_json''')
phases = cfg.get("phases", [])
results = []
errors = []
env = os.environ.copy()

for phase in phases:
    entry = {"name": phase, "status": "ok", "startedAt": __import__("datetime").datetime.utcnow().isoformat() + "Z"}
    try:
        proc = subprocess.run(
            ["bash", f"{root}/scripts/run-agents.sh", "--phase", phase],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=600,
        )
        entry["exitCode"] = proc.returncode
        if proc.returncode != 0:
            entry["status"] = "error"
            errors.append({"phase": phase, "message": (proc.stderr or proc.stdout or "failed")[:500]})
        if "429" in (proc.stderr or "") or "rate limit" in (proc.stderr or "").lower():
            errors.append({"phase": phase, "message": "rate_limit_detected"})
    except Exception as e:
        entry["status"] = "error"
        entry["exitCode"] = -1
        errors.append({"phase": phase, "message": str(e)[:500]})
    entry["completedAt"] = __import__("datetime").datetime.utcnow().isoformat() + "Z"
    results.append(entry)

print(json.dumps({"phases": results, "errors": errors}))
PY
)

  phases_json=$(echo "$phase_results" | python3 -c "import json,sys; d=json.load(sys.stdin); print(json.dumps(d['phases']))")
  errors_json=$(echo "$phase_results" | python3 -c "import json,sys; d=json.load(sys.stdin); print(json.dumps(d['errors']))")

  if echo "$errors_json" | grep -q "rate_limit"; then
    rate_limited="true"
    local backoff
    backoff=$(echo "$cfg_json" | python3 -c "import json,sys; print(json.load(sys.stdin).get('rateLimitBackoffSeconds',60))")
    warn "Rate limit detectado — backoff ${backoff}s"
    sleep "$backoff"
  fi

  completed_at=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
  local interval_used
  interval_used=$(compute_interval "$cfg_json")

  local write_mem=0
  if echo "$cfg_json" | python3 -c "import json,sys; print(1 if json.load(sys.stdin).get('writeMemorySummary') else 0)" | grep -q 1; then
    write_mem=1
  fi
  WRITE_MEMORY=$write_mem write_loop_state "$cycle_id" "$cycle_num" "$started_at" "$completed_at" "$interval_used" "$phases_json" "$errors_json" "$summary" "$rate_limited"

  cycle_lock_release
  trap - EXIT

  echo "$interval_used"
}

echo "==========================================================="
echo " 🧠 Smart Loop — Agência Autônoma Inteligente"
echo "==========================================================="
log "PID $$ gravado em $PID_FILE"
log "Log: $LOG_FILE"

CYCLE=1
while true; do
  cfg_json=$(read_config)
  interval_base=$(echo "$cfg_json" | python3 -c "import json,sys; print(json.load(sys.stdin).get('intervalSeconds',900))")

  echo ""
  echo "==========================================================="
  echo " 🔄 CICLO $CYCLE - $(date)"
  echo "==========================================================="

  interval_used=$(run_one_cycle "$CYCLE" "$cfg_json" || echo "$interval_base")

  log "💤 Ciclo $CYCLE completo. Próximo em $((interval_used / 60)) min."

  echo 'AGENT_LOOP_WAKE_trading {"prompt":"Smart loop cycle completed — check data/loop-state.json"}' >> "$LOG_FILE"

  if [[ "$RUN_ONCE" -eq 1 ]]; then
    log "Modo --once: encerrando."
    exit 0
  fi

  for (( i=interval_used; i>0; i--)); do
    min=$((i / 60))
    sec=$((i % 60))
    printf "\r⏳ Próximo ciclo (%d) em: %02d:%02d... " $((CYCLE + 1)) "$min" "$sec"
    sleep 1
  done
  printf "\n"
  ((CYCLE++))
done
