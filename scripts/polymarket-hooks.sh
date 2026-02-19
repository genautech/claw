#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CFG="$ROOT/config/polymarket-hooks.json"
DATA_DIR="$ROOT/data"
NOW_EPOCH="$(date +%s)"

alert() { echo "[ALERT] $*"; }
info() { echo "[INFO] $*"; }

json_get() {
  python3 - "$CFG" "$1" <<'PY'
import json, sys
cfg=json.load(open(sys.argv[1]))
path=sys.argv[2].split('.')
obj=cfg
for p in path:
    obj=obj[p]
print(obj)
PY
}

check_health() {
  local exec_url gateway_ok exec_ok
  exec_url="$(json_get health.executorUrl)"

  if openclaw health >/dev/null 2>&1; then
    gateway_ok=1
  else
    gateway_ok=0
  fi

  if curl -fsS --max-time 5 "$exec_url" >/dev/null 2>&1; then
    exec_ok=1
  else
    exec_ok=0
  fi

  (( gateway_ok == 1 )) || alert "Gateway offline"
  (( exec_ok == 1 )) || alert "Executor offline ($exec_url)"

  if (( gateway_ok == 1 && exec_ok == 1 )); then
    info "Health OK"
  fi
}

check_trade() {
  local rec_file exec_file stale_mins max_fail
  rec_file="$DATA_DIR/recommendations.jsonl"
  exec_file="$DATA_DIR/executions.jsonl"
  stale_mins="$(json_get trade.recommendationStaleMinutes)"
  max_fail="$(json_get trade.maxConsecutiveFailures)"

  if [[ -f "$rec_file" && -s "$rec_file" ]]; then
    local rec_mtime age_min
    rec_mtime=$(stat -f %m "$rec_file")
    age_min=$(( (NOW_EPOCH - rec_mtime) / 60 ))
    if (( age_min > stale_mins )); then
      alert "Recommendations stale: ${age_min}m > ${stale_mins}m"
    else
      info "Recommendations freshness OK (${age_min}m)"
    fi
  else
    alert "No recommendations found in data/recommendations.jsonl"
  fi

  if [[ -f "$exec_file" && -s "$exec_file" ]]; then
    python3 - "$exec_file" "$max_fail" <<'PY'
import json,sys
path=sys.argv[1]
max_fail=int(sys.argv[2])
consec=0
with open(path,'r',encoding='utf-8') as f:
    lines=f.readlines()[-200:]
for ln in reversed(lines):
    try:
        obj=json.loads(ln)
    except Exception:
        continue
    if obj.get('success') is False:
        consec += 1
    else:
        break
if consec >= max_fail:
    print(f"[ALERT] Consecutive execution failures: {consec} (>= {max_fail})")
else:
    print(f"[INFO] Consecutive execution failures: {consec}")
PY
  else
    info "No executions yet"
  fi
}

check_risk() {
  local exec_file max_order
  exec_file="$DATA_DIR/executions.jsonl"
  max_order="$(json_get risk.maxOrderUsd)"

  if [[ ! -f "$exec_file" || ! -s "$exec_file" ]]; then
    info "No executions for risk checks"
    return
  fi

  python3 - "$exec_file" "$max_order" <<'PY'
import json,sys
path=sys.argv[1]
max_order=float(sys.argv[2])
viol=0
with open(path,'r',encoding='utf-8') as f:
    for ln in f.readlines()[-500:]:
        try:
            o=json.loads(ln)
        except Exception:
            continue
        details=o.get('details') or {}
        size=details.get('sizeUsd')
        if isinstance(size,(int,float)) and size>max_order:
            viol+=1
if viol:
    print(f"[ALERT] Risk violation: {viol} orders above maxOrderUsd={max_order}")
else:
    print("[INFO] Risk limits OK")
PY
}

check_resolution() {
  local exec_file stale_h
  exec_file="$DATA_DIR/executions.jsonl"
  stale_h="$(json_get resolution.staleResolutionHours)"

  if [[ ! -f "$exec_file" || ! -s "$exec_file" ]]; then
    info "No executions to evaluate resolution cadence"
    return
  fi

  local mtime age_h
  mtime=$(stat -f %m "$exec_file")
  age_h=$(( (NOW_EPOCH - mtime) / 3600 ))
  if (( age_h > stale_h )); then
    alert "No execution activity for ${age_h}h (threshold ${stale_h}h)"
  else
    info "Execution activity recent (${age_h}h)"
  fi
}

case "${1:-all}" in
  health) check_health ;;
  trade) check_trade ;;
  risk) check_risk ;;
  resolution) check_resolution ;;
  all)
    check_health
    check_trade
    check_risk
    check_resolution
    ;;
  *)
    echo "Usage: $0 [health|trade|risk|resolution|all]"
    exit 1
    ;;
esac
