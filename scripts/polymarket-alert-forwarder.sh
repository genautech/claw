#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOG_FILE="$ROOT/logs/polymarket-hooks.log"
STATE_FILE="$ROOT/memory/polymarket-alert-forwarder.state"

mkdir -p "$ROOT/memory"
[[ -f "$LOG_FILE" ]] || exit 0

LAST_LINE=0
if [[ -f "$STATE_FILE" ]]; then
  LAST_LINE=$(cat "$STATE_FILE" 2>/dev/null || echo 0)
fi

TOTAL=$(wc -l < "$LOG_FILE" | tr -d ' ')
if (( TOTAL <= LAST_LINE )); then
  echo "$TOTAL" > "$STATE_FILE"
  exit 0
fi

NEW_ALERTS=$(sed -n "$((LAST_LINE+1)),$TOTAL p" "$LOG_FILE" | grep "\[ALERT\]" || true)

echo "$TOTAL" > "$STATE_FILE"

[[ -n "$NEW_ALERTS" ]] || exit 0

SUMMARY=$(printf '%s
' "$NEW_ALERTS" | tail -n 5)
TEXT="Polymarket hook alerts detectados:\n$SUMMARY"

openclaw system event --mode now --text "$TEXT" >/dev/null 2>&1 || true
