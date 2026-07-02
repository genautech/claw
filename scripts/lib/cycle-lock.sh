#!/usr/bin/env bash
# Shared cycle lock — prevents overlapping agent cycles (autoloop vs dashboard).

CYCLE_LOCK_FILE="${CYCLE_LOCK_FILE:-/tmp/clawd-cycle.lock}"
CYCLE_LOCK_META="${CYCLE_LOCK_META:-/tmp/clawd-cycle.meta.json}"

cycle_lock_read_meta() {
  if [[ -f "$CYCLE_LOCK_META" ]]; then
    cat "$CYCLE_LOCK_META"
  else
    echo "{}"
  fi
}

cycle_lock_is_held() {
  if [[ ! -f "$CYCLE_LOCK_FILE" ]]; then
    return 1
  fi
  if command -v flock >/dev/null 2>&1; then
    if flock -n "$CYCLE_LOCK_FILE" -c true 2>/dev/null; then
      return 1
    fi
    return 0
  fi
  [[ -f "$CYCLE_LOCK_META" ]]
}

cycle_lock_acquire() {
  local cycle_id="${1:-}"
  local source="${2:-unknown}"

  if ! command -v flock >/dev/null 2>&1; then
    return 0
  fi

  exec 200>"$CYCLE_LOCK_FILE"
  if ! flock -n 200; then
    return 1
  fi

  local started_at
  started_at=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
  if [[ -z "$cycle_id" ]]; then
    cycle_id="cycle-${started_at}"
  fi

  export CYCLE_LOCK_META
  CYCLE_ID="$cycle_id" CYCLE_SOURCE="$source" CYCLE_STARTED="$started_at" python3 - <<PY
import json, os
meta = {
    "cycleId": os.environ.get("CYCLE_ID", ""),
    "source": os.environ.get("CYCLE_SOURCE", ""),
    "startedAt": os.environ.get("CYCLE_STARTED", ""),
    "pid": os.getpid(),
}
with open("$CYCLE_LOCK_META", "w") as f:
    json.dump(meta, f, indent=2)
PY
  export CYCLE_LOCK_FD=200
  export CYCLE_LOCK_ACTIVE=1
  export CYCLE_LOCK_CYCLE_ID="$cycle_id"
  return 0
}

cycle_lock_release() {
  if [[ "${CYCLE_LOCK_ACTIVE:-}" == "1" ]] && [[ -n "${CYCLE_LOCK_FD:-}" ]]; then
    flock -u "$CYCLE_LOCK_FD" 2>/dev/null || true
  fi
  rm -f "$CYCLE_LOCK_META"
  unset CYCLE_LOCK_ACTIVE CYCLE_LOCK_FD CYCLE_LOCK_CYCLE_ID
}
